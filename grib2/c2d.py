from operator import itemgetter
from pathlib import Path
import pyproj
import geopy.distance
import numpy as np
import math



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


def interpolate(coeff, heure, ve, me):
    heure += 6
    heure_floor = math.floor(heure)
    heure_ceil = math.ceil(heure)
    p = heure_ceil - heure

    # interpolation sur l'heure de vive eaux
    ve_u = ve[0][heure_floor] * p + ve[0][heure_ceil] * (1 - p)
    ve_v = ve[1][heure_floor] * p + ve[1][heure_ceil] * (1 - p)

    # interpolation sur l'heure de morte eau
    me_u = me[0][heure_floor] * p + me[0][heure_ceil] * (1 - p)
    me_v = me[1][heure_floor] * p + me[1][heure_ceil] * (1 - p)

    # interpolation sur le coefficient
    u = me_u + (coeff - 45) * (ve_u - me_u) / 50
    v = me_v + (coeff - 45) * (ve_v - me_v) / 50

    return u, v


def c2d_reader(coeff, heure, atlas="RADE_BREST_560"):
    """
    Retourne les coordonnées et les courants des points d'un atlas de courants de surface.
    """

    assert 20 <= coeff <= 120
    assert -6 <= heure <= 6

    atlas = Path(atlas)
    lines = atlas.read_text().splitlines()

    for i in range(1, len(lines), 3):
        coordinates = lines[i]
        latitude = to_angle(coordinates[0:9])
        longitude = to_angle(coordinates[9:18])

        ve = to_uv(lines[i + 1])
        me = to_uv(lines[i + 2])

        u, v = interpolate(coeff, heure, ve, me)

        yield longitude, latitude, u, v


def get_not_used():
    proj = pyproj.Proj("EPSG:3857")  # world mercator
    # proj = pyproj.Proj("EPSG:3395")  # world mercator
    proj = pyproj.Proj("EPSG:2154")  # RGF93 Lambert 93

    points = list(c2d_reader(95, -6))

    lon_min, lat_min, lon_max, lat_max = minmax(map(itemgetter(0, 1), points))

    print("range →", lon_min, lat_min, lon_max, lat_max)

    x_min, y_min = proj(lon_min, lat_min)
    x_max, y_max = proj(lon_max, lat_max)

    print(proj.name, proj.crs, "→", x_min, y_min, x_max, y_max)

    x = np.array(list(map(itemgetter(0), points)))
    y = np.array(list(map(itemgetter(1), points)))
    u = np.array(list(map(itemgetter(2), points)))
    v = np.array(list(map(itemgetter(3), points)))

    return x, y, u, v


def mesures():
    points = list(c2d_reader())

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


if __name__ == "__main__":
    me = (
        [1, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    )

    ve = (
        [2, 3, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [2, 3, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    )

    u, v = interpolate(20, -6, ve, me)
    print(u, v)
