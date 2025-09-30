# Critical Analysis of codex_geo.py Design Decisions

While [`codex_geo.py`](codex_geo.py:1) is a significant improvement over [`geohash.py`](geohash.py:1), there are several design decisions I would reconsider or improve upon.

---

## 1. Type-Polymorphic `decode()` Function ⚠️

### Current Design:
```python
def decode(geohash: str, geotype: str = "point") -> Union[LonLat, Tuple[float, float, float, float], Polygon]:
    # Returns different types based on string parameter
```

### Issues:
- **Type safety problem**: Return type depends on a string parameter, defeating static type checking
- **Runtime errors**: Typos like `geotype="pointer"` only fail at runtime
- **Poor IDE support**: Can't autocomplete or validate the `geotype` parameter
- **Union return type**: Forces callers to use type guards or ignore types

### Better Alternatives:

**Option A: Separate functions (most type-safe)**
```python
def decode_point(geohash: str) -> LonLat:
    """Decode to center point."""
    return DecodedCell.from_geohash(geohash).to_point()

def decode_with_error(geohash: str) -> Tuple[float, float, float, float]:
    """Decode to point with error bounds."""
    return DecodedCell.from_geohash(geohash).to_pointerr()

def decode_polygon(geohash: str) -> Polygon:
    """Decode to bounding polygon."""
    return DecodedCell.from_geohash(geohash).to_polygon()
```

**Option B: Enum for type parameter**
```python
from enum import Enum

class GeohashType(Enum):
    POINT = "point"
    POINT_ERR = "pointerr"
    POLYGON = "polygon"

@overload
def decode(geohash: str, geotype: Literal[GeohashType.POINT]) -> LonLat: ...
@overload
def decode(geohash: str, geotype: Literal[GeohashType.POINT_ERR]) -> Tuple[float, float, float, float]: ...
@overload
def decode(geohash: str, geotype: Literal[GeohashType.POLYGON]) -> Polygon: ...
```

**Option C: Return DecodedCell directly (my preference)**
```python
def decode(geohash: str) -> DecodedCell:
    """Decode geohash to a cell with all representations available."""
    # Callers choose: cell.to_point(), cell.to_polygon(), etc.
```

**Recommendation**: Option C is cleanest - return the rich [`DecodedCell`](codex_geo.py:16) object and let callers extract what they need.

---

## 2. Missing Input Validation 🐛

### Current Issue:
```python
def encode(lon: float, lat: float, precision: int = 12) -> str:
    # No validation of inputs!
```

### Problems:
- Accepts `lat=200.0` or `lon=500.0` silently
- Invalid precision values (negative, zero) only caught in helper
- Can produce incorrect geohashes from invalid inputs

### Better Approach:
```python
def encode(lon: float, lat: float, precision: int = 12) -> str:
    """Encode a (longitude, latitude) pair into a geohash string.
    
    Raises:
        ValueError: If lat not in [-90, 90], lon not in [-180, 180], or precision < 1
    """
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitude {lat} must be in range [-90, 90]")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude {lon} must be in range [-180, 180]")
    if precision < 1:
        raise ValueError(f"Precision {precision} must be >= 1")
    # ... rest of implementation
```

---

## 3. In-Place Mutation in `_refine_interval()` ⚠️

### Current Design:
```python
def _refine_interval(bits: Sequence[int], interval: List[float]) -> None:
    for bit in bits:
        mid = (interval[0] + interval[1]) / 2
        if bit:
            interval[0] = mid  # Mutates in place
        else:
            interval[1] = mid  # Mutates in place
```

### Issues:
- Mutates input parameter (side effect)
- Returns `None` but does work
- Harder to test and reason about
- Doesn't compose well with functional patterns

### Alternative Approach:
```python
def _refine_interval(bits: Sequence[int], initial_range: Tuple[float, float]) -> Tuple[float, float]:
    """Return refined interval endpoints based on bits."""
    low, high = initial_range
    for bit in bits:
        mid = (low + high) / 2
        if bit:
            low = mid
        else:
            high = mid
    return low, high
```

**Better**: Functional style with clear input/output, easier to test and reason about.

---

## 4. Polygon Corner Ordering 📐

### Current Implementation:
```python
def to_polygon(self) -> Polygon:
    west, east = self.lon - self.lon_err, self.lon + self.lon_err
    south, north = self.lat - self.lat_err, self.lat + self.lat_err
    return [(west, south), (east, south), (west, north), (east, north)]
```

### Issues:
- Returns 4 corners in arbitrary order: `[SW, SE, NW, NE]`
- Not clockwise or counterclockwise
- Missing 5th point to close polygon
- Non-standard for GeoJSON (which expects closed rings)

### GeoJSON-Compatible Approach:
```python
def to_polygon(self, closed: bool = True) -> Polygon:
    """Return bounding box corners in counter-clockwise order.
    
    Args:
        closed: If True, repeats first point to close the polygon
    """
    west, east = self.lon - self.lon_err, self.lon + self.lon_err
    south, north = self.lat - self.lat_err, self.lat + self.lat_err
    
    corners = [
        (west, south),   # SW - start
        (east, south),   # SE
        (east, north),   # NE
        (west, north),   # NW
    ]
    
    if closed:
        corners.append((west, south))  # Close the ring
    
    return corners
```

---

## 5. `neighbors()` Performance Trade-off 🐌

### Current Approach:
```python
def neighbors(geohash: str) -> List[str]:
    lon, lat, lon_err, lat_err = decode(geohash, geotype="pointerr")
    # ... calculate new coordinates
    results.append(encode(candidate_lon, candidate_lat, precision=precision))
```

### Performance Analysis:
- **Decodes** the geohash: O(n) where n = length
- **Encodes** 9 times: 9 * O(n)
- Total: ~10n operations

### Original Bit Manipulation Approach:
```python
# geohash.py approach (without boundary handling):
lon_int = int(lon_bits, 2)
lat_int = int(lat_bits, 2)
lon_list = [lon_int - 1, lon_int, lon_int + 1]
lat_list = [lat_int + 1, lat_int, lat_int - 1]
```

- Integer arithmetic: O(1) per neighbor
- Total: ~O(n) for bit extraction + 9 O(n) for encoding = ~10n
- But **fails at boundaries**

### Hybrid Approach (Best of Both):
```python
def neighbors(geohash: str) -> List[str]:
    """Return 3x3 grid of neighbors with proper boundary handling."""
    bits = _geohash_to_bits(geohash)
    lon_bits = bits[::2]
    lat_bits = bits[1::2]
    
    # Work in integer space
    lon_int = int(''.join(map(str, lon_bits)), 2)
    lat_int = int(''.join(map(str, lat_bits)), 2)
    
    lon_max = (1 << len(lon_bits)) - 1
    lat_max = (1 << len(lat_bits)) - 1
    
    results = []
    for lon_delta in (-1, 0, 1):
        lon_val = lon_int + lon_delta
        # Handle longitude wrapping
        if lon_val < 0:
            lon_val = lon_max
        elif lon_val > lon_max:
            lon_val = 0
            
        for lat_delta in (1, 0, -1):
            lat_val = lat_int + lat_delta
            # Clamp latitude (can't wrap)
            if lat_val < 0 or lat_val > lat_max:
                # Skip invalid neighbors at poles
                continue
                
            # Reconstruct geohash from bits
            lon_b = bin(lon_val)[2:].zfill(len(lon_bits))
            lat_b = bin(lat_val)[2:].zfill(len(lat_bits))
            combined = ''.join(l + t for l, t in zip(lon_b, lat_b))
            if len(lon_bits) > len(lat_bits):
                combined += lon_b[-1]
            
            results.append(_bits_to_geohash([int(b) for b in combined]))
    
    return results
```

**Trade-off**: More complex but faster and handles boundaries correctly in bit space.

---

## 6. Inconsistent Error Types

### Current Pattern:
```python
# Everything raises ValueError
raise ValueError("Invalid geohash character...")
raise ValueError("geotype must be...")
raise ValueError("Bit sequence length must be...")
raise ValueError("Precision must be...")
```

### Better Approach:
```python
class GeohashError(Exception):
    """Base exception for geohash operations."""

class InvalidGeohashError(GeohashError):
    """Raised when geohash string is invalid."""

class InvalidCoordinateError(GeohashError):
    """Raised when lat/lon is out of range."""

class InvalidPrecisionError(GeohashError):
    """Raised when precision is invalid."""

# Usage:
if not -90 <= lat <= 90:
    raise InvalidCoordinateError(f"Latitude {lat} out of range [-90, 90]")
```

**Benefits**: Callers can catch specific errors, better error handling.

---

## 7. Missing Utility Functions

### Useful Additions:

```python
def distance_meters(hash1: str, hash2: str) -> float:
    """Approximate distance between two geohash centers in meters."""
    
def common_prefix(hash1: str, hash2: str) -> str:
    """Return common prefix indicating shared precision."""
    
def parent(geohash: str) -> str:
    """Return parent (less precise) geohash."""
    return geohash[:-1] if len(geohash) > 1 else geohash

def children(geohash: str) -> List[str]:
    """Return all 32 child geohashes (one more precision level)."""
    return [geohash + char for char in BASE32_ALPHABET]

def bbox(geohash: str) -> Tuple[float, float, float, float]:
    """Return bounding box as (min_lon, min_lat, max_lon, max_lat)."""
    cell = decode(geohash)  # Returns DecodedCell
    return (
        cell.lon - cell.lon_err,
        cell.lat - cell.lat_err, 
        cell.lon + cell.lon_err,
        cell.lat + cell.lat_err
    )
```

---

## 8. Magic Numbers and Constants

### Current:
```python
BITS_PER_CHAR = 5  # Good!

# But embedded in code:
wrapped = ((lon + 180.0) % 360.0) - 180.0  # Magic numbers
interval = [-180.0, 180.0]  # Repeated
```

### Better:
```python
# At module level
BITS_PER_CHAR = 5
LON_RANGE = (-180.0, 180.0)
LAT_RANGE = (-90.0, 90.0)
LON_SPAN = 360.0
DEFAULT_PRECISION = 12

def _wrap_longitude(lon: float) -> float:
    wrapped = ((lon + LON_RANGE[1]) % LON_SPAN) - LON_RANGE[1]
    return LON_RANGE[0] if wrapped == LON_RANGE[1] else wrapped
```

---

## 9. Dataclass Could Be More Functional

### Current:
```python
@dataclass(frozen=True)
class DecodedCell:
    lon: float
    lat: float
    lon_err: float
    lat_err: float

    def to_point(self) -> LonLat:
        return self.lon, self.lat
```

### Enhanced Version:
```python
@dataclass(frozen=True)
class DecodedCell:
    """Represents a decoded geohash cell with center and error bounds."""
    
    lon: float
    lat: float
    lon_err: float
    lat_err: float

    @classmethod
    def from_geohash(cls, geohash: str) -> "DecodedCell":
        """Factory method to create from geohash string."""
        bits = _geohash_to_bits(geohash)
        # ... decoding logic here
        return cls(lon=lon, lat=lat, lon_err=lon_err, lat_err=lat_err)
    
    def to_point(self) -> LonLat:
        """Return center point as (lon, lat)."""
        return self.lon, self.lat
    
    def to_bbox(self) -> Tuple[float, float, float, float]:
        """Return bounding box: (min_lon, min_lat, max_lon, max_lat)."""
        return (
            self.lon - self.lon_err,
            self.lat - self.lat_err,
            self.lon + self.lon_err,
            self.lat + self.lat_err
        )
    
    @property
    def center(self) -> LonLat:
        """Alias for to_point()."""
        return self.to_point()
    
    @property 
    def width_meters(self) -> float:
        """Approximate cell width at center latitude."""
        return self.lon_err * 2 * 111_320 * cos(radians(self.lat))
    
    @property
    def height_meters(self) -> float:
        """Approximate cell height."""
        return self.lat_err * 2 * 110_540
```

---

## 10. Testing & Documentation Gaps

### Missing:
- No doctests or example usage
- No performance benchmarks
- No comparison with other geohash libraries
- No discussion of precision/accuracy trade-offs

### Could Add:
```python
def encode(lon: float, lat: float, precision: int = 12) -> str:
    """Encode (longitude, latitude) into a geohash string.
    
    Args:
        lon: Longitude in degrees [-180, 180]
        lat: Latitude in degrees [-90, 90]
        precision: Number of base32 characters [1, 12]
    
    Returns:
        Geohash string of specified precision
        
    Raises:
        InvalidCoordinateError: If coordinates out of range
        InvalidPrecisionError: If precision < 1
    
    Examples:
        >>> encode(-122.4194, 37.7749, precision=7)
        '9q8yyk8'
        >>> encode(0, 0, precision=1)
        's'
        
    Note:
        Precision 12 gives ~37mm × 19mm resolution.
        See module docstring for precision table.
    """
```

---

## Summary: My Design Decisions

If I were refactoring from scratch, I would:

1. ✅ **Return `DecodedCell` directly** from `decode()` - eliminate type polymorphism
2. ✅ **Add comprehensive input validation** with specific exception types
3. ✅ **Use immutable interval refinement** - more functional, easier to test
4. ✅ **Fix polygon ordering** - counter-clockwise, optionally closed
5. ⚖️ **Keep geographic `neighbors()` approach** - correctness over micro-optimization
6. ✅ **Define custom exception hierarchy** - better error handling
7. ✅ **Add utility functions** - `parent()`, `children()`, `bbox()`, `distance()`
8. ✅ **Extract magic numbers** to named constants
9. ✅ **Enhance `DecodedCell`** with factory method and utility properties
10. ✅ **Add comprehensive doctests** and examples

The current [`codex_geo.py`](codex_geo.py:1) is a solid refactoring, but these changes would make it production-grade and more Pythonic.