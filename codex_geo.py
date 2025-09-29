"""Refactored geohash utilities with clearer abstractions and shared helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Union

# Constants -------------------------------------------------------------------
BASE32_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"
BASE32_DECODE_MAP = {char: index for index, char in enumerate(BASE32_ALPHABET)}
BITS_PER_CHAR = 5

LonLat = Tuple[float, float]
Polygon = List[LonLat]


@dataclass(frozen=True)
class DecodedCell:
    """Container for the decoded cell centre and half-width/height."""
    lon: float
    lat: float
    lon_err: float
    lat_err: float

    def to_point(self) -> LonLat:
        return self.lon, self.lat

    def to_pointerr(self) -> Tuple[float, float, float, float]:
        return self.lon, self.lat, self.lon_err, self.lat_err

    def to_polygon(self) -> Polygon:
        west, east = self.lon - self.lon_err, self.lon + self.lon_err
        south, north = self.lat - self.lat_err, self.lat + self.lat_err
        return [(west, south), (east, south), (west, north), (east, north)]


# Helpers ---------------------------------------------------------------------
def _bits_to_geohash(bits: Sequence[int]) -> str:
    if len(bits) % BITS_PER_CHAR:
        raise ValueError("Bit sequence length must be a multiple of 5")

    geohash_chars: List[str] = []
    accumulator = 0
    count = 0
    for bit in bits:
        accumulator = (accumulator << 1) | bit
        count += 1
        if count == BITS_PER_CHAR:
            geohash_chars.append(BASE32_ALPHABET[accumulator])
            accumulator = 0
            count = 0
    return "".join(geohash_chars)


def _geohash_to_bits(geohash: str) -> List[int]:
    bits: List[int] = []
    for char in geohash:
        try:
            value = BASE32_DECODE_MAP[char]
        except KeyError as exc:  # pragma: no cover - defensive path
            raise ValueError(
                "Invalid geohash character. Use 0-9 and b-h, j, k, m, n, p-z."
            ) from exc
        for shift in range(BITS_PER_CHAR - 1, -1, -1):
            bits.append((value >> shift) & 1)
    return bits


def _refine_interval(bits: Sequence[int], interval: List[float]) -> None:
    for bit in bits:
        mid = (interval[0] + interval[1]) / 2
        if bit:
            interval[0] = mid
        else:
            interval[1] = mid


def _total_bits(precision: int) -> int:
    if precision <= 0:
        raise ValueError("Precision must be a positive integer")
    return precision * BITS_PER_CHAR


def _wrap_longitude(lon: float) -> float:
    wrapped = ((lon + 180.0) % 360.0) - 180.0
    # Special-case 180.0 so it stays within inclusive bounds
    return -180.0 if wrapped == 180.0 else wrapped


# Public API ------------------------------------------------------------------
def encode(lon: float, lat: float, precision: int = 12) -> str:
    """Encode a (longitude, latitude) pair into a geohash string."""
    total_bits = _total_bits(precision)

    lon_interval = [-180.0, 180.0]
    lat_interval = [-90.0, 90.0]
    bits: List[int] = []
    use_lon = True

    for _ in range(total_bits):
        interval = lon_interval if use_lon else lat_interval
        value = lon if use_lon else lat
        mid = (interval[0] + interval[1]) / 2
        if value >= mid:
            bits.append(1)
            interval[0] = mid
        else:
            bits.append(0)
            interval[1] = mid
        use_lon = not use_lon

    return _bits_to_geohash(bits)


def decode(geohash: str, geotype: str = "point") -> Union[LonLat, Tuple[float, float, float, float], Polygon]:
    """Decode a geohash into point, pointerr, or polygon representations."""
    bits = _geohash_to_bits(geohash)

    lon_interval = [-180.0, 180.0]
    lat_interval = [-90.0, 90.0]
    lon_bits = bits[::2]
    lat_bits = bits[1::2]

    _refine_interval(lon_bits, lon_interval)
    _refine_interval(lat_bits, lat_interval)

    lon = sum(lon_interval) / 2
    lat = sum(lat_interval) / 2
    lon_err = (lon_interval[1] - lon_interval[0]) / 2
    lat_err = (lat_interval[1] - lat_interval[0]) / 2

    cell = DecodedCell(lon=lon, lat=lat, lon_err=lon_err, lat_err=lat_err)

    if geotype == "point":
        return cell.to_point()
    if geotype == "pointerr":
        return cell.to_pointerr()
    if geotype == "polygon":
        return cell.to_polygon()

    raise ValueError("geotype must be 'point', 'pointerr', or 'polygon'")


def neighbors(geohash: str) -> List[str]:
    """Return the 3x3 grid of neighbor hashes centred on the provided geohash."""
    lon, lat, lon_err, lat_err = decode(geohash, geotype="pointerr")
    lon_step = lon_err * 2
    lat_step = lat_err * 2

    results: List[str] = []
    precision = len(geohash)
    for lon_delta in (-1, 0, 1):
        candidate_lon = _wrap_longitude(lon + lon_delta * lon_step)
        for lat_delta in (1, 0, -1):
            candidate_lat = max(min(lat + lat_delta * lat_step, 90.0), -90.0)
            results.append(encode(candidate_lon, candidate_lat, precision=precision))
    return results


__all__ = ["encode", "decode", "neighbors", "DecodedCell"]
