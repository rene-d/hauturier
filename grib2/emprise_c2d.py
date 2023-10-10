#!/usr/bin/env python3

# montre l'emprise des atlas de courants de surface

# %%

from operator import itemgetter
from pathlib import Path
import imgcat
import pyproj
from PIL import Image, ImageDraw, ImageFont
import geopy.distance
from c2d import *
import geopandas as gpd
from shapely import Point
import sqlite3
import numpy as np
from scipy.spatial import Delaunay
import matplotlib.pyplot as plt

# %%
iDirectionIncrementInDegrees = 0.003369
jDirectionIncrementInDegrees = 0.002253


# %%


class Limites:
    def __init__(self) -> None:
        self.db = sqlite3.connect("limites.db")

        self.db.executescript(
            "create table if not exists limites (lon float,lat float,earth boolean);"
            "create unique index if not exists limites_idx on limites (lon,lat);"
        )

        self.shp_file = (
            "././Limite_terre_mer_departement_29/SHAPE/Limite_terre-mer_departement_29_polygone.shp"
        )
        self.gdf = None

    def is_earth(self, lon, lat):
        if row := self.db.execute("select earth from limites where lon=? and lat=?", (lon, lat)).fetchone():
            return row[0]

        if self.gdf is None:
            print("lecture", self.shp_file)
            self.gdf = gpd.read_file(self.shp_file)
            self.gdf = self.gdf.to_crs(epsg=4326)

        earth = self.gdf.contains(Point(lon, lat)).any()
        self.db.execute("insert into limites values (?,?,?)", (lon, lat, 1 if earth else 0))
        self.db.commit()

        print(f"point ({lon}, {lat}) → {earth}")

        return earth


limites = Limites()


# %%

coeff = 95 # vive eau
heure = 0 # PM

print("lecture", "atlas des courants de surface")
points = list(c2d_reader(coeff, heure))

lon_min, lat_min, lon_max, lat_max = minmax(map(itemgetter(0, 1), points))

lon_min, lon_max = -4.447403, -4.38406
lat_min, lat_max = 48.362636, 48.3989


print("range →", lon_min, lat_min, lon_max, lat_max)


# %%

x_min, y_min = proj(lon_min, lat_min)
x_max, y_max = proj(lon_max, lat_max)

print(proj.name, proj.crs, "→", x_min, y_min, x_max, y_max)


R = 400 / (x_max - x_min)
D = 10

x_min -= 3 * D / R
x_max += 3 * D / R
y_min -= 3 * D / R
y_max += 3 * D / R


def to_xy(lon, lat):
    x, y = proj(lon, lat)
    x = round((x - x_min) * R)
    y = round((y_max - y) * R)
    return x, y


# %%

im = Image.new("RGB", (round((x_max - x_min) * R), round((y_max - y_min) * R)), (255, 255, 255))
draw = ImageDraw.Draw(im)
font = ImageFont.truetype("Roboto-Regular.woff2", 10)


# %%

lon = lon_min
while lon <= lon_max + iDirectionIncrementInDegrees:
    lat = lat_min
    while lat <= lat_max + jDirectionIncrementInDegrees:
        if limites.is_earth(lon, lat):
            color = "gray"

            x1, y1 = to_xy(lon - iDirectionIncrementInDegrees / 2, lat + jDirectionIncrementInDegrees / 2)
            x2, y2 = to_xy(lon + iDirectionIncrementInDegrees / 2, lat - jDirectionIncrementInDegrees / 2)

            draw.rectangle((x1, y1, x2, y2), fill=color, outline=color)

        else:
            color = "blue"

            x, y = to_xy(lon, lat)
            draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=color, outline=color)

        lat += jDirectionIncrementInDegrees

    lon += iDirectionIncrementInDegrees


# %%

D=3
p=[]
for i, (longitude, latitude, u, v) in enumerate(points):
    if lon_min <= longitude <= lon_max and lat_min <= latitude <= lat_max:
        x, y = to_xy(longitude, latitude)
        p.append((x,y))

        draw.rectangle((x - D, y - D, x + D, y + D), fill="red", outline="red")
        # draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill="red", outline="red")
        # draw.rectangle((x - D, y - D, x + D, y + D), fill=None, outline="red")
        # draw.text((x, y), str(i), fill="black", font=font, anchor="mm")

mpoints=np.array(p)
tri = Delaunay(mpoints)

for t in tri.simplices:
    xa,ya=mpoints[t[0]]
    xb,yb=mpoints[t[1]]
    xc,yc=mpoints[t[2]]

    draw.line([(xa,ya),(xb,yb)], fill="green", width=2)
    draw.line([(xb,yb),(xc,yc)], fill="green", width=2)
    draw.line([(xa,ya),(xc,yc)], fill="green", width=2)

im
# %%
# im.show()
im.save("emprise.png")
# imgcat.imgcat(im, height=20)


im


#%%
mpoints=np.array(p)
tri = Delaunay(mpoints)
plt.triplot(mpoints[:,0], mpoints[:,1], tri.simplices)
plt.plot(mpoints[:,0], mpoints[:,1], 'o')
plt.show()


# %%
im
# %%
plt
# %%
