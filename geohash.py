# Geohash utility.  Decodes, encodes, and finds neighbors.  Decode has cool options.
#
# Accuracy for typical geohash lengths (number of characters):
# Length  Width	Height
# 1       5,000km	5,000km
# 2       1,250km	625km
# 3       156km 	156km
# 4       39.1km	19.5km
# 5       4.89km	4.89km
# 6       1.22km	0.61km
# 7       153m  	153m
# 8       38.2m     19.1m
# 9       4.77m     4.77m
# 10      1.19m     0.596m
# 11      149mm     149mm
# 12      37.2mm    18.6mm
#
# Need to clean up neighbor code and sub-functions.

import math
import sys
from itertools import zip_longest


base32 = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'p',
          'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
dict32 = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'b': 10, 'c': 11, 'd': 12,
          'e': 13, 'f': 14, 'g': 15, 'h': 16, 'j': 17, 'k': 18, 'm': 19, 'n': 20, 'p': 21, 'q': 22, 'r': 23, 's': 24,
          't': 25, 'u': 26, 'v': 27, 'w': 28, 'x': 29, 'y': 30, 'z': 31}


def encode(lon: float, lat: float, precision: int = 12) -> str:
    """
    Encode lon-lat pair to geohash
    :param lon: Longitude
    :param lat: Latitude
    :param precision: Bits of precision.
    :return: Geohash string
    """
    lon_bits = get_bits(lon, precision, 180)
    lat_bits = get_bits(lat, precision, 90)
    geobits = ''.join(''.join(x) for x in zip_longest(lon_bits, lat_bits, fillvalue=''))
    geohash = ''
    for i in range(precision):
        geohash += base32[int(geobits[i*5:i*5+5], 2)]
    return geohash


def get_bits(degrees: float, precision: int, range_ends: int):
    """
    Gives the bit string of either lat or lon for zipping in encoding of geohash.
    :param degrees: The lon or lat, as a float
    :param precision: Number of characters for the end result geohash
    :param range_ends: 180 or 90 for lon or lat, respectively
    :return: string of bits
    """
    result = ''
    tup_range = (-range_ends, range_ends)
    for i in range(sum(divmod(precision * 5, 2))):
        mid = sum(tup_range) / 2
        if degrees > mid:
            result += '1'
            tup_range = (mid, tup_range[1])
        else:
            result += '0'
            tup_range = (tup_range[0], mid)
    return result


def decode(geohash: str, geotype: str = 'point'):
    """
    Decode geohash to point, pointerr, or polygon.
    point is (lon, lat) tuple.
    pointerr is (lon, lat, lon_err, lat_err).
    polygon is four tuples of the corners of the bounding box of possible area given by geohash.
        Useful in geojson queries.  Doesn't complete the box, so you'll need to do that yourself.
    :param geohash: Geohash string
    :param geotype: 'point', 'pointerr', 'pointround', or 'polygon'
    :return:
    """
    geobits = get_geobits(geohash)
    lon_bits = geobits[::2]
    lat_bits = geobits[1::2]
    lon, lon_err = get_degrees(lon_bits, 180)
    lat, lat_err = get_degrees(lat_bits, 90)
    if geotype == 'pointerr':
        response = [lat, lon, lat_err, lon_err]
    elif geotype == 'polygon':
        response = [((lon - lon_err), (lat - lat_err)), ((lon + lon_err), (lat - lat_err)), ((lon - lon_err), (lat + lat_err)), ((lon + lon_err), (lat + lat_err))]
    else:
        response = (lon, lat)
    return response


def get_degrees(bits: str, range_ends: int):
    """
    Returns tuple of degrees and degree of precision
    :param bits: string of bits of the lon or lat from the geohash unpacking
    :param range_ends: 180 or 90 for lon or lat, respectively
    :return: (degrees, DOP)
    """
    tup_range = (-range_ends, range_ends)
    for i in bits:
        mid = sum(tup_range) / 2
        if i == '0':
            tup_range = (tup_range[0], mid)
        else:
            tup_range = (mid, tup_range[1])
    degrees = sum(tup_range) / 2
    precision = abs(degrees - tup_range[0])
    return degrees, precision


def neighbors(geohash: str):
    geobits = get_geobits(geohash)
    lon_bits = geobits[::2]
    lat_bits = geobits[1::2]
    lon_int = int(lon_bits, 2)
    lat_int = int(lat_bits, 2)
    lon_len = len(lon_bits)
    lat_len = len(lat_bits)
    hash_len = len(geohash)
    lon_list = [lon_int - 1, lon_int, lon_int + 1]
    lat_list = [lat_int + 1, lat_int, lat_int - 1]
    geo_list = []
    for i in lon_list:
        lon_bits = bin(i)[2:].zfill(lon_len)
        for j in lat_list:
            lat_bits = bin(j)[2:].zfill(lat_len)
            geobits = ''.join(''.join(x) for x in zip_longest(lon_bits, lat_bits, fillvalue=''))
            geohash = ''
            for k in range(hash_len):
                geohash += base32[int(geobits[k * 5:k * 5 + 5], 2)]
            geo_list.append(geohash)
    return geo_list


def get_geobits(geohash: str):
    """
    Geohash in, bits out.
    :param geohash: string of the geohash
    :return: string of 1s and 0s.  Must be string to retain prepended zeroes and maintain length.
    """
    geobits = ''
    for i in geohash:
        try:
            geobits += str(bin(dict32[i])[2:].zfill(5))
        except KeyError:
            return "Invalid geohash character.  Use 0-9, b-h, j, k, m, n, p-z."
    return geobits


# print(decode('c22yzv5cw8te'))
# print(encode(-122.3493, 47.6205))
# print(neighbors('c22yzv'))
# Neighbours:
# c23n1k	c23n1s 	c23n1u
# c23n17	c23n1e 	c23n1g
# c23n16	c23n1d 	c23n1f
