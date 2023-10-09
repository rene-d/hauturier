from operator import itemgetter
from pathlib import Path
import imgcat
import pyproj
from PIL import Image, ImageDraw, ImageFont
import geopy.distance
import numpy as np

iDirectionIncrementInDegrees = 0.003369
jDirectionIncrementInDegrees = 0.002253

# ED50 Lambert Zone I   : https://epsg.io/27571
# RGF93 Lambert 93      : https://epsg.io/2154
# WGS84                 : https://epsg.io/4326
# WGS84 Pseudo-Mercator : https://epsg.io/3857


proj = pyproj.Proj("EPSG:3857")  # world mercator
# proj = pyproj.Proj("EPSG:3395")  # world mercator
# proj=pyproj.Proj("EPSG:2154") # RGF93 Lambert 93


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
    """
    Retourne les composantes u et v des courants -6h à +6h de la marée du port de référence.
    """
    assert line[40] == "*"
    u = [int(line[i * 3 : i * 3 + 3]) for i in range(13)]
    v = [int(line[i * 3 + 41 : i * 3 + 41 + 3]) for i in range(13)]
    return u, v


def minmax(points):
    """
    Retourne les coordonnées min et max d'une liste de points.
    """
    x_min = y_min = float("inf")
    x_max = y_max = float("-inf")
    for x, y in points:
        x_min = min(x_min, x)
        y_min = min(y_min, y)
        x_max = max(x_max, x)
        y_max = max(y_max, y)
    return x_min, y_min, x_max, y_max


def c2d_reader():
    """
    Retourne les coordonnées et les courants des points d'un atlas de courants de surface.
    """
    f = Path("RADE_BREST_560")
    lines = f.read_text().splitlines()

    for i in range(1, len(lines), 3):
        coordinates = lines[i]
        latitude = to_angle(coordinates[0:9])
        longitude = to_angle(coordinates[9:18])

        if not -4.447403 <= longitude <= -4.38406:
            continue
        if not     48.362636 <= latitude <=     48.40744:
            continue

        ve = to_uv(lines[i + 1])
        me = to_uv(lines[i + 2])

        yield longitude, latitude, ve, me


def get():
    points = list(c2d_reader())

    lon_min, lat_min, lon_max, lat_max = minmax(map(itemgetter(0, 1), points))

    print("range →", lon_min, lat_min, lon_max, lat_max)

    x_min, y_min = proj(lon_min, lat_min)
    x_max, y_max = proj(lon_max, lat_max)

    print(proj.name, proj.crs, "→", x_min, y_min, x_max, y_max)

    x = np.array(list(map(itemgetter(0), points)))
    y = np.array(list(map(itemgetter(1), points)))

    VIVE_EAU = 2
    MORTE_EAU = 3
    U = 0
    V = 1
    HEURE_AV6 = 0
    HEURE_PM = 6
    HEURE_AP6 = 12

    u = np.array(list(map(lambda m: m[U][0], map(itemgetter(VIVE_EAU), points))))
    v = np.array(list(map(lambda m: m[V][0], map(itemgetter(VIVE_EAU), points))))

    return x, y, u, v
