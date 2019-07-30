# geohash
Decodes, encodes, finds neighbors

# Encoding geohash
## encode(lon, lat, precision)

```
>>> import geohash
>>> geohash.encode(-122.3493, 47.6205)
'c22yzv5cw8te'
>>> geohash.encode(-122.3493, 47.6205, precision=8)
'c22yzv5c'
```

Encodes your coordinate point to a geohash.  Coordinates are always lon, lat, with optional precision.  Precision defaults to 12.

# Decoding geohash
## decode(geohash, geotype)

```
>>> import geohash
>>> geohash.decode('c22yzv5cw8te')
(-122.349299993366, 47.62050001882017)
>>> geohash.decode('c22yzv5cw8te', geotype='pointerr')
[47.62050001882017, -122.349299993366, 8.381903171539307e-08, 1.6763806343078613e-07]
>>> geohash.decode('c22yzv5cw8te', geotype='polygon')
[(-122.34930016100407, 47.620499935001135), (-122.34929982572794, 47.620499935001135), (-122.34930016100407, 47.6205001026392), (-122.34929982572794, 47.6205001026392)]
```

Decodes to a tuple of lon, lat.  Geotype can be 'point' by default, or also 'pointerr' and 'polygon'.  Pointerr gives lon, lat, lon_err, lat_err, where the lon_err and lat_err are the +/- margin of error.  Polygon gives a list of the four points of the polygon containing the possible coordinates indicated by the given geohash.  

# Neighbors
## neighbors(geohash)

```
>>> import geohash
>>> geohash.neighbors('c22yzv')
['c22yzs', 'c22yzt', 'c22yzw', 'c22yzu', 'c22yzv', 'c22yzy', 'c23nbh', 'c23nbj', 'c23nbn']
```

Gives a list of all neighboring boxes of your given geohash.  Order is upper left, left, lower left, upper middle, self, lower middle, upper right, right, lower right.  

# Copyright
Original work of Aaron Seelye 2018-2019, use at your peril.  No warranty given.
