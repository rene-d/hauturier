#!/usr/bin/env python3

# montre l'emprise des atlas de courants de surface

from operator import itemgetter
from pathlib import Path

import geopy.distance
import pyproj
from PIL import Image, ImageDraw, ImageFont

proj = pyproj.Proj("EPSG:3857")
# proj = pyproj.Proj("EPSG:4230")


def to_angle(s: str):
    """
    Retourne una latitude ou une longitude de 9 caractères sous forme de float ±DD.MMM.
    """
    assert len(s) == 9
    assert s[-4] == "."

    p = s.index(".")
    degrees = int(s[0 : p - 2])
    minutes = float(s[p - 2 :])
    assert 0 <= minutes < 60

    d = float(abs(degrees) + minutes / 60)
    if degrees < 0:
        d = -d
    return d


def to_uv(line):
    assert line[40] == "*"
    u = [int(line[i * 3 : i * 3 + 3]) for i in range(13)]
    v = [int(line[i * 3 + 41 : i * 3 + 41 + 3]) for i in range(13)]
    return u, v


f = Path("RADE_BREST_560")
d = f.read_text().splitlines()


def g():
    for i in range(1, len(d), 3):
        p = d[i]
        latitude = to_angle(p[0:9])
        longitude = to_angle(p[9:18])

        ve = to_uv(d[i + 1])
        me = to_uv(d[i + 2])

        # x,y=proj(longitude, latitude)
        # yield x,y, ve, me
        yield latitude, longitude, ve[0][0], ve[0][1]


c2d = list(g())

lat = list(map(itemgetter(0), c2d))
lon = list(map(itemgetter(1), c2d))

lat_min = min(lat)
lat_max = max(lat)

lon_min = min(lon)
lon_max = max(lon)

iDirectionIncrementInDegrees = 0.003369
jDirectionIncrementInDegrees = 0.002253

Ni = int((lon_max - lon_min) / iDirectionIncrementInDegrees) + 1
Nj = int((lat_max - lat_min) / jDirectionIncrementInDegrees) + 1

print(Ni, Nj)

# vdouble = [[0] * 27 for _ in range(73)]
# Ndouble = [[0] * 27 for _ in range(73)]

# for lat, lon, u, v in c2d:
#     speed = (u * u + v * v) ** 0.5

#     i = int((lon * 1_000_000 + 360_000_000 - 355352483) / 5383)
#     j = int((lat * 1_000_000 - 48268550) / 5383)

#     for x in range(i - 2, i + 3):
#         for y in range(j - 2, j + 3):
#             if 0 <= x < 73 and 0 <= y < 27:
#                 vdouble[x][y] += speed
#                 Ndouble[x][y] += 1

# for i in range(73):
#     for j in range(27):
#         if Ndouble[i][j] == 0:
#             vdouble[i][j] = 9999
#         else:
#             vdouble[i][j] /= Ndouble[i][j]


# inc = open("vdouble.inc", "w")
# for i in range(73):
#     for j in range(27):
#         v = vdouble[i][j]
#         print(f"  vdouble[{i*27+j}] = {v};", file=inc)
# inc.close()

# lon = sorted(lat)
# d = sorted([round((b - a)*1_000_000) for a, b in zip(lat, lat[1:])])

# print(d)


# exit()


def g():
    for p in d[1::3]:
        latitude = to_angle(p[0:9])
        longitude = to_angle(p[9:18])
        yield proj(longitude, latitude)
        # yield (latitude, longitude)


xy = list(g())

x = list(map(itemgetter(0), xy))
y = list(map(itemgetter(1), xy))

xmin = min(x)
ymin = min(y)
xmax = max(x)
ymax = max(y)


print(xmin, ymin, xmax, ymax)

R = 2000 / (xmax - xmin)
D = 10

im = Image.new("RGB", (round((xmax - xmin) * R), round((ymax - ymin) * R)), (255, 255, 255))
draw = ImageDraw.Draw(im)

for i, (x, y) in enumerate(xy):
    x = round((x - xmin) * R)
    y = round((ymax - y) * R)
    draw.rectangle((x - D, y - D, x + D, y + D), fill="red")
    draw.text((x, y), str(i), fill="black", anchor="ms")

im.show()


#     421    422
#
# 401    402
#
#     376    377

print(xy[421], xy[422], geopy.distance.distance(xy[421], xy[422]))
print(xy[421], xy[376], geopy.distance.distance(xy[421], xy[376]))
# print(geopy.distance.distance( xy[401], xy[402]))


# print(to_angle(" 4820.540"))
# print(to_angle(" 4820.000"))

# print(to_angle(" -430.500"))
# print(to_angle(" -429.690"))
