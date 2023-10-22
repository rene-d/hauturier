#!/usr/bin/env python3

# montre l'emprise des atlas de courants de surface

# %%

import json
import sqlite3
import subprocess
from operator import itemgetter
from pathlib import Path

import geopandas as gpd
import imgcat
import numpy as np
import pyproj
import requests
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import Delaunay, KDTree
from shapely import LineString, MultiPolygon, Point, Polygon

from c2d import c2d_reader, minmax

# %%
iDirectionIncrementInDegrees = 0.003369 * 5
jDirectionIncrementInDegrees = 0.002253 * 5


# %%
class Limites:
    """
    Classe pour gérer les limites terre/mer.
    """

    def __init__(self) -> None:
        self.db = sqlite3.connect("limites.db")

        self.db.executescript(
            "create table if not exists limites (lon float,lat float,earth boolean);"
            "create unique index if not exists limites_idx on limites (lon,lat);"
        )

        # self.shp_name = "Limite_terre_mer_departement_76"
        # self.shp_name = "Limite_terre_mer_facade_Manche_Atlantique"
        self.shp_name = "Limite_terre_mer_departement_29"

        self._gdf = None
        self.clip = None

    def set_clip(self, lon_min, lat_min, lon_max, lat_max):
        self.clip = (lon_min - 0.005, lat_min - 0.005, lon_max + 0.005, lat_max + 0.005)

    @property
    def gdf(self) -> gpd.GeoSeries:
        """
        Renvoie le GeoDataFrame des limites terre/mer.
        """
        if self._gdf is None:
            if not self.ensure_shp_file():
                raise Exception(f"fichier shp {self.shp_name} non trouvé")
            print("lecture", self.shp_file)

            self._gdf = gpd.read_file(self.shp_file)
            self._gdf = self._gdf.to_crs(epsg=4326)

            # réduction pour accélérer les calculs
            if self.clip is not None:
                print("clip", self.clip)
                self._gdf = self._gdf.clip_by_rect(*self.clip)

        return self._gdf

    def is_earth(self, lon, lat) -> bool:
        """
        Retourne True si le point est à l'intérieur des limites terre/mer, False sinon.
        """
        lon = round(lon, 6)
        lat = round(lat, 6)

        if row := self.db.execute("select earth from limites where lon=? and lat=?", (lon, lat)).fetchone():
            return bool(row[0])

        earth = self.gdf.contains(Point(lon, lat)).any()
        self.db.execute("insert into limites values (?,?,?)", (lon, lat, 1 if earth else 0))
        self.db.commit()

        print(f"point ({lon}, {lat}) → {earth}")

        return earth

    @property
    def shp_file(self):
        shapes = list((Path(self.shp_name) / "SHAPE").glob("*_polygone.shp"))
        if len(shapes) == 1 and shapes[0].is_file():
            return shapes[0]
        return None

    def ensure_shp_file(self):
        if self.shp_file is not None:
            return True

        print("téléchargement", self.shp_name)

        url = "https://services.data.shom.fr/x13f1b4faeszdyinv9zqxmx1/telechargement/prepackageGroup/LIMTM_PACK_DL/prepackage/{shp}/file/{shp}.7z"
        url = url.format(shp=self.shp_name)

        r = requests.get(url, headers={"referer": "https://diffusion.shom.fr"})
        r.raise_for_status()
        Path(f"{self.shp_name}.7z").write_bytes(r.content)

        subprocess.run(["7z", "x", "-y", f"{self.shp_name}.7z"], check=True)

        return self.shp_file is not None


limites = Limites()
# %%
coeff = 95  # vive eau
heure = 0  # PM
atlas = "RADE_BREST_560"

points = list(c2d_reader(coeff, heure, atlas))
lon_min, lat_min, lon_max, lat_max = minmax(map(itemgetter(0, 1), points))

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

# conversion WGS84 → RGF93 Lambert 93
proj_lambert93 = pyproj.Proj("EPSG:2154")  # RGF93 Lambert 93

# conversion RGF93 Lambert 93 → WGS84 Pseudo-Mercator
proj_mercator = pyproj.Transformer.from_crs("EPSG:2154", "EPSG:3857", always_xy=True).transform


x_min, y_min = proj_mercator(*proj_lambert93(lon_min, lat_min))
x_max, y_max = proj_mercator(*proj_lambert93(lon_max, lat_max))

print(proj_lambert93.name, proj_lambert93.crs, "→", x_min, y_min, x_max, y_max)


R = 4000 / (x_max - x_min)
D = 10

x_min -= 3 * D / R
x_max += 3 * D / R
y_min -= 3 * D / R
y_max += 3 * D / R


def to_img(x, y):
    """
    Convertit les coordonnées Lambert 93 en coordonnées image avec projection Web Mercator.
    """
    x, y = proj_mercator(x, y)
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

points_on_sea = []


def draw_point_on_earth():
    lon = lon_min
    while lon <= lon_max + iDirectionIncrementInDegrees:
        lat = lat_min
        while lat <= lat_max + jDirectionIncrementInDegrees:
            if limites.is_earth(lon, lat):
                pass

                # color = "gray"
                # x1, y1 = to_xy(lon - iDirectionIncrementInDegrees / 2, lat + jDirectionIncrementInDegrees / 2)
                # x2, y2 = to_xy(lon + iDirectionIncrementInDegrees / 2, lat - jDirectionIncrementInDegrees / 2)
                # draw.rectangle((x1, y1, x2, y2), fill=color, outline=color)

            else:
                color = "blue"

                x, y = to_xy(lon, lat)
                draw.rectangle((x - 1, y - 1, x + 1, y + 1), fill=color, outline=color)

                points_on_sea.append(proj_lambert93(lon, lat))

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

points_xy = []
points_uv = []

for i, (longitude, latitude, u, v) in enumerate(points):
    if lon_min <= longitude <= lon_max and lat_min <= latitude <= lat_max:
        # projection mercator
        x, y = proj_lambert93(longitude, latitude)

        points_xy.append((x, y))
        points_uv.append((u, v))

        x, y = to_img(x, y)
        draw.rectangle((x - 3, y - 3, x + 3, y + 3), fill="red", outline="red")

points_xy = np.array(points_xy)
tri = Delaunay(points_xy)


# récupère le trait de côte et convertit en coordonnées Lambert 93
gdf = limites.gdf.to_crs(proj_lambert93.crs.srs)

for poly in gdf.geometry:
    # if poly.is_empty:
    #     continue

    if isinstance(poly, Polygon):
        poly = [to_img(x, y) for x, y in poly.exterior.coords]
        draw.polygon(poly, fill="gray", outline="magenta")

    elif isinstance(poly, MultiPolygon):
        for p in poly.geoms:
            p = [to_img(x, y) for x, y in p.exterior.coords]
            draw.polygon(p, fill="gray", outline="magenta")


tri_ok = [False] * len(tri.simplices)

for i, t in enumerate(tri.simplices):
    xa, ya = points_xy[t[0]]
    xb, yb = points_xy[t[1]]
    xc, yc = points_xy[t[2]]

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
            # x, y = to_img((xa + xb + xc) / 3, (ya + yb + yc) / 3)
            # draw.text((x, y), str(round(area)), fill="black", font=font, anchor="mm")
            pass

    tri_ok[i] = True

    xa, ya = to_img(xa, ya)
    xb, yb = to_img(xb, yb)
    xc, yc = to_img(xc, yc)

    draw.line([(xa, ya), (xb, yb)], fill="green" if d1 <= 1210 else "red", width=2)
    draw.line([(xb, yb), (xc, yc)], fill="green" if d2 <= 1210 else "red", width=2)
    draw.line([(xc, yc), (xa, ya)], fill="green" if d3 <= 1210 else "red", width=2)

# %%
imgcat.imgcat(im, height=30)
im.save("emprise.png")

# %%

for (x, y), (u, v) in zip(points_xy, points_uv):
    x, y = to_img(x, y)
    draw.line([(x, y), (x + u * 10, y - v * 10)], fill="blue", width=10)

# %%


def to_str(x, y):
    return f"{round(x)}_{round(y)}"


interpolation = dict()

kd = KDTree(points_xy)

for x, y in points_on_sea:
    p = kd.query_ball_point([x, y], 610)

    def nearest(i):
        px, py = points_xy[i]

        if gdf.intersection(LineString([(x, y), (px, py)])).any():
            # draw.line((to_img(px, py), to_img(x, y)), fill="red", width=10)
            # if isinstance(segment, LineString):
            #     draw.line((to_img(*segment.coords[0]), to_img(*segment.coords[1])), fill="red", width=20)

            return float("+inf")

        return (px - x) ** 2 + (py - y) ** 2

    p = sorted(p, key=nearest)[:3]

    if len(p) == 0:
        continue

    # ex, ey = to_img(x, y)
    # draw.ellipse(((ex - 5, ey - 5), (ex + 5, ey + 5)), fill="blue", outline="blue")

    d = []

    for i in p:
        px, py = points_xy[i]
        d.append(((px - x) ** 2 + (py - y) ** 2) ** 0.5)
        # px, py = to_img(px, py)
        # draw.ellipse(((px - 5, py - 5), (px + 5, py + 5)), fill="black", outline="black")
        # draw.line(((ex, ey), (px, py)), fill="black", width=3)

    if len(p) == 3:
        u0, v0 = points_uv[p[0]]
        u1, v1 = points_uv[p[1]]
        u2, v2 = points_uv[p[2]]

        u = (u0 * d[1] * d[2] + u1 * d[2] * d[0] + u2 * d[0] * d[1]) / (d[0] * d[1] + d[1] * d[2] + d[2] * d[0])
        v = (v0 * d[1] * d[2] + v1 * d[2] * d[0] + v2 * d[0] * d[1]) / (d[0] * d[1] + d[1] * d[2] + d[2] * d[0])

        interpolation[to_str(x, y)] = (p, d)

    # elif len(p) == 2:
    #     u0, v0 = tri_points_uv[p[0]]
    #     u1, v1 = tri_points_uv[p[1]]

    #     u = (u0 * d[1] + u1 * d[0]) / (d[0] + d[1])
    #     v = (v0 * d[1] + v1 * d[0]) / (d[0] + d[1])

    else:
        u, v = points_uv[p[0]]

        interpolation[to_str(x, y)] = p[0]

    x, y = to_img(x, y)
    draw.line(((x, y), (x + u * 10, y - v * 10)), fill="cyan", width=10)


Path("interpol.json").write_text(json.dumps(interpolation, indent=2))


# %%
im.save("courants.png")
imgcat.imgcat(im, height=30)
