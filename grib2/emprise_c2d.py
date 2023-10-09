#!/usr/bin/env python3

# montre l'emprise des atlas de courants de surface

from operator import itemgetter
from pathlib import Path
import imgcat
import pyproj
from PIL import Image, ImageDraw, ImageFont
import geopy.distance
from c2d import *


points = list(c2d_reader())

lon_min, lat_min, lon_max, lat_max = minmax(map(itemgetter(0, 1), points))

print("range →", lon_min, lat_min, lon_max, lat_max)

x_min, y_min = proj(lon_min, lat_min)
x_max, y_max = proj(lon_max, lat_max)

print(proj.name, proj.crs, "→", x_min, y_min, x_max, y_max)


R = 400 / (x_max - x_min)
D = 10

x_min -= 3*D/R
x_max += 3*D/R
y_min -= 3*D/R
y_max += 3*D/R


im = Image.new("RGB", (round((x_max - x_min) * R), round((y_max - y_min) * R)), (255, 255, 255))
draw = ImageDraw.Draw(im)
font = ImageFont.truetype("Roboto-Regular.woff2", 10)



###########################

lon = lon_min
while lon <= lon_max+iDirectionIncrementInDegrees:
    lat = lat_min
    while lat <= lat_max+jDirectionIncrementInDegrees:
        x, y = proj(lon, lat)
        x = round((x - x_min) * R)
        y = round((y_max - y) * R)
        draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill="blue", outline="blue")
        lat += jDirectionIncrementInDegrees
    lon += iDirectionIncrementInDegrees


###########################

for i, (longitude, latitude, _, _) in enumerate(points):
    x, y = proj(longitude, latitude)
    x = round((x - x_min) * R)
    y = round((y_max - y) * R)
    draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill="red", outline="red")
    draw.rectangle((x - D, y - D, x + D, y + D), fill=None, outline="red")
    draw.text((x, y), str(i), fill="black", font=font, anchor="mm")

    # text anchors: https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html


# im.show()
im.save("emprise.png")
imgcat.imgcat(im, height=20)


proj = pyproj.Proj("EPSG:3857")  # web mercator
proj = pyproj.Proj("EPSG:3395")  # world mercator
proj = pyproj.Proj("EPSG:2154")  # RGF93 Lambert 93
proj = pyproj.Proj("EPSG:27571")  # ED50 Lambert Zone I
proj = pyproj.Proj("EPSG:4326")  # WGS84


def dist(p1, p2):
    if proj.name == "longlat":
        lon1, lat1 = p1
        lon2, lat2 = p2
        return geopy.distance.distance((lat1, lon1), (lat2, lon2))
    else:
        x1, y1 = p1
        x2, y2 = p2
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


points = [proj(lon, lat) for lon, lat, _, _ in points]

print("espacement moyen horizontal (sur un parallèle):")
p1 = points[271]
p2 = points[296]
print("", p1, p2, dist(p1, p2) / 25)

print("espacement moyen vertical (sur un méridien):")
p1 = points[477]
p2 = points[136]
print("", p1, p2, dist(p1, p2) / 16)
