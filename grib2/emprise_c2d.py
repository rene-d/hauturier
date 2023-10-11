#!/usr/bin/env python3

# montre l'emprise des atlas de courants de surface

# %%

import subprocess
import json
from operator import itemgetter
from pathlib import Path
import imgcat
import pyproj
from PIL import Image, ImageDraw, ImageFont
import geopy.distance
import requests
from c2d import *
import geopandas as gpd
from shapely import Point, Polygon, MultiPolygon
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

        self.shp_file = Path("./Limite_terre_mer_departement_29/SHAPE/Limite_terre-mer_departement_29_polygone.shp")
        # self.shp_file = Path("./Limite_terre_mer_facade_Manche_Atlantique/SHAPE/Limite_terre-mer_facade_Manche_Atlantique_polygone.shp")

        self._gdf = None
        self.clip = None

    def set_clip(self, lon_min, lat_min, lon_max, lat_max):
        self.clip = (lon_min - 0.005, lat_min - 0.005, lon_max + 0.005, lat_max + 0.005)

    @property
    def gdf(self) -> gpd.GeoSeries:
        if self._gdf is None:
            self.ensure_shp_file()
            print("lecture", self.shp_file)
            self._gdf = gpd.read_file(self.shp_file)
            self._gdf = self._gdf.to_crs(epsg=4326)
            if self.clip is not None:
                print("clip", self.clip)
                self._gdf = self._gdf.clip_by_rect(*self.clip)
        return self._gdf

    def is_earth(self, lon, lat):
        lon = round(lon, 6)
        lat = round(lat, 6)

        if row := self.db.execute("select earth from limites where lon=? and lat=?", (lon, lat)).fetchone():
            return row[0]

        earth = self.gdf.contains(Point(lon, lat)).any()
        self.db.execute("insert into limites values (?,?,?)", (lon, lat, 1 if earth else 0))
        self.db.commit()

        print(f"point ({lon}, {lat}) → {earth}")

        return earth

    def ensure_shp_file(self):
        if self.shp_file.exists():
            return

        shp = "Limite_terre_mer_departement_29"

        print("téléchargement", shp)

        url = "https://services.data.shom.fr/x13f1b4faeszdyinv9zqxmx1/telechargement/prepackageGroup/LIMTM_PACK_DL/prepackage/{shp}/file/{shp}.7z"
        url = url.format(shp=shp)

        r = requests.get(url, headers={"referer": "https://diffusion.shom.fr"})
        r.raise_for_status()
        Path(f"{shp}.7z").write_bytes(r.content)
        subprocess.run(["7z", "x", f"{shp}.7z"], check=True)


limites = Limites()
# %%
coeff = 95  # vive eau
heure = 0  # PM

# print("lecture", "atlas des courants de surface")
points = list(c2d_reader(coeff, heure))
lon_min, lat_min, lon_max, lat_max = minmax(map(itemgetter(0, 1), points))

# lon_min, lon_max = -4.448 - iDirectionIncrementInDegrees * 45, -4.380
# lat_min, lat_max = 48.362636 - jDirectionIncrementInDegrees * 15, 48.3989

if Path("zone.json").exists():
    zone = json.loads(Path("zone.json").read_text())
    lon_min = min(map(itemgetter(0), zone))
    lat_min = min(map(itemgetter(1), zone))
    lon_max = max(map(itemgetter(0), zone))
    lat_max = max(map(itemgetter(1), zone))


limites.set_clip(lon_min, lat_min, lon_max, lat_max)

print("range →", lon_min, lat_min, lon_max, lat_max)
# %%

# ED50 Lambert Zone I   : https://epsg.io/27571
# RGF93 Lambert 93      : https://epsg.io/2154
# WGS84                 : https://epsg.io/4326
# WGS84 Pseudo-Mercator : https://epsg.io/3857
# WGS84 World Mercator  : https://epsg.io/3395

proj_lambert93 = pyproj.Proj("EPSG:2154")  # RGF93 Lambert 93

proj_img_merc = pyproj.Transformer.from_crs("EPSG:2154", "EPSG:3857", always_xy=True).transform


x_min, y_min = proj_img_merc(*proj_lambert93(lon_min, lat_min))
x_max, y_max = proj_img_merc(*proj_lambert93(lon_max, lat_max))

print(proj_lambert93.name, proj_lambert93.crs, "→", x_min, y_min, x_max, y_max)


R = 2000 / (x_max - x_min)
D = 10

x_min -= 3 * D / R
x_max += 3 * D / R
y_min -= 3 * D / R
y_max += 3 * D / R


def to_img(x, y):
    """
    Convertit les coordonnées Lambert 93 en coordonnées image avec projection Web Mercator.
    """
    x, y = proj_img_merc(x, y)
    x = round((x - x_min) * R)
    y = round((y_max - y) * R)
    return x, y


def to_xy(lon, lat):
    """
    Convertit les coordonnées longitude,latitude en coordonnées image avec projection Web Mercator.
    """
    x, y = proj_lambert93(lon, lat)
    return to_img(x, y)


# %%

im = Image.new("RGB", (round((x_max - x_min) * R), round((y_max - y_min) * R)), (255, 255, 255))
draw = ImageDraw.Draw(im)
font = ImageFont.truetype("Roboto-Regular.woff2", 30)


# %%

points_on_earth = []


def draw_point_on_earth():
    lon = lon_min
    while lon <= lon_max + iDirectionIncrementInDegrees:
        lat = lat_min
        while lat <= lat_max + jDirectionIncrementInDegrees:
            if limites.is_earth(lon, lat):
                color = "gray"

                # x1, y1 = to_xy(lon - iDirectionIncrementInDegrees / 2, lat + jDirectionIncrementInDegrees / 2)
                # x2, y2 = to_xy(lon + iDirectionIncrementInDegrees / 2, lat - jDirectionIncrementInDegrees / 2)
                # draw.rectangle((x1, y1, x2, y2), fill=color, outline=color)

                points_on_earth.append(proj_lambert93(lon, lat))

            else:
                color = "blue"

                x, y = to_xy(lon, lat)
                draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=color, outline=color)

            lat += jDirectionIncrementInDegrees

        lon += iDirectionIncrementInDegrees


draw_point_on_earth()


# %%
def is_point_in_triangle(p, p1, p2, p3):
    """
    Returns True if point p is inside the triangle defined by points p1, p2, and p3.
    """

    def sign(x1, y1, x2, y2, x3, y3):
        return (x1 - x3) * (y2 - y3) - (x2 - x3) * (y1 - y3)

    b1 = sign(p[0], p[1], p1[0], p1[1], p2[0], p2[1]) < 0
    b2 = sign(p[0], p[1], p2[0], p2[1], p3[0], p3[1]) < 0
    b3 = sign(p[0], p[1], p3[0], p3[1], p1[0], p1[1]) < 0

    return (b1 == b2) and (b2 == b3)


# %%

tri_points = []

for i, (longitude, latitude, u, v) in enumerate(points):
    if lon_min <= longitude <= lon_max and lat_min <= latitude <= lat_max:
        # projection mercator
        x, y = proj_lambert93(longitude, latitude)

        tri_points.append((x, y))

        x, y = to_img(x, y)
        draw.rectangle((x - 3, y - 3, x + 3, y + 3), fill="red", outline="red")

tri_points = np.array(tri_points)
tri = Delaunay(tri_points)

# récupère le trait de côte et convertit en coordonnées Lambert 93
gdf = limites.gdf.to_crs(proj_lambert93.crs.srs)

for poly in gdf.geometry:
    if poly.is_empty:
        continue

    if isinstance(poly, Polygon):
        poly = [to_img(x, y) for x, y in poly.exterior.coords]
        draw.polygon(poly, fill="gray", outline="magenta")

    elif isinstance(poly, MultiPolygon):
        for p in poly.geoms:
            p = [to_img(x, y) for x, y in p.exterior.coords]
            draw.polygon(p, fill="gray", outline="magenta")


tri_ok = [False] * len(tri.simplices)

for i, t in enumerate(tri.simplices):
    xa, ya = tri_points[t[0]]
    xb, yb = tri_points[t[1]]
    xc, yc = tri_points[t[2]]

    d1 = ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5
    d2 = ((xb - xc) ** 2 + (yb - yc) ** 2) ** 0.5
    d3 = ((xc - xa) ** 2 + (yc - ya) ** 2) ** 0.5
    if max(d1, d2, d3) > 1800:
        continue

    poly = Polygon([(xa, ya), (xb, yb), (xc, yc)])
    intersects = gdf.intersects(poly).any()
    if intersects:
        poly = gdf.intersection(Polygon([(xa, ya), (xb, yb), (xc, yc)]))
        area = poly.area.sum()

        if area > 2000:
            continue
        else:
            x, y = to_img((xa + xb + xc) / 3, (ya + yb + yc) / 3)
            draw.text((x, y), str(round(area)), fill="black", font=font, anchor="mm")

    tri_ok[i] = True

    xa, ya = to_img(xa, ya)
    xb, yb = to_img(xb, yb)
    xc, yc = to_img(xc, yc)

    draw.line([(xa, ya), (xb, yb)], fill="green" if d1 <= 1210 else "red", width=2)
    draw.line([(xb, yb), (xc, yc)], fill="green" if d2 <= 1210 else "red", width=2)
    draw.line([(xc, yc), (xa, ya)], fill="green" if d3 <= 1210 else "red", width=2)

# %%
im.save("emprise.png")
imgcat.imgcat(im, height=30)
