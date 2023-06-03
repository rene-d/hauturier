#!/usr/bin/env python3

import io
import zipfile
from pathlib import Path

import contextily as cx
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import requests
from scipy.ndimage import zoom
from shapely.geometry import Point, Polygon

from grib import MeteoFrance

# ------------------------------------------------------------------------------------------------


def get_ne_maps(data_dir: Path):
    # https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/

    if (data_dir / "ne_10m_admin_0_countries.shp").is_file():
        return

    r = requests.get(
        "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/cultural/ne_10m_admin_0_countries.zip",
        headers={"user-agent": "curl/7.79.1"},
        allow_redirects=True,
    )

    zip = zipfile.ZipFile(io.BytesIO(r.content), mode="r")
    for f in zip.filelist:
        zip.extract(f, path=data_dir)


# get_ne_maps(Path("data"))
# world = gpd.read_file("data/ne_10m_admin_0_countries.shp")
# world = gpd.read_file("data/Limite_terre-mer_facade_Manche_Atlantique_polygone.shp")
# world = world.to_crs("EPSG:4326")
#

# ------------------------------------------------------------------------------------------------
forecast = MeteoFrance(model="Arome", HD=True, echeance="07H")
grib = forecast.open()

message = grib.select(name="10 metre U wind component")[0]
print(message)

lats, lons = message.latlons()  # WGS84 projection
print(f"shape: {lats.shape}")
print(f"extent:  s={lats.min()} n={lats.max()} w={lons.min()} e={lons.max()}")

shape = (750, 750)
x = np.linspace(lons.min(), lons.max(), shape[1])  # shape[1] == nombre de colonnes
y = np.linspace(lats.min(), lats.max(), shape[0])  # shape[0] == nombre de lignes
X, Y = np.meshgrid(x, y)

item = grib.select(name="10 metre U wind component")[0]
U = np.copy(item.values[::-1])

item = grib.select(name="10 metre V wind component")[0]
V = np.copy(item.values[::-1])

U = zoom(U, (shape[0] / U.shape[0], shape[1] / U.shape[1]))
V = zoom(V, (shape[1] / V.shape[0], shape[1] / V.shape[1]))

######################################################

harbor = Point(-4.497736, 48.406435)  # Brest
harbor = Point(-3.988496, 48.713752)  # Roscoff

extent_x = 0.15
extent_y = 0.1
p1 = Point(harbor.x - extent_x, harbor.y - extent_y)
p2 = Point(harbor.x + extent_x, harbor.y - extent_y)
p3 = Point(harbor.x + extent_x, harbor.y + extent_y)
p4 = Point(harbor.x - extent_x, harbor.y + extent_y)

######################################################

i1 = np.argmin(X[0] < p1.x)
i2 = np.argmax(X[0] >= p3.x)

j1 = np.argmin(Y[:, 0] < p1.y)
j2 = np.argmax(Y[:, 0] >= p3.y)

X = X[j1:j2, i1:i2]
Y = Y[j1:j2, i1:i2]
U = U[j1:j2, i1:i2]
V = V[j1:j2, i1:i2]

# ratio = (lats.max() - lats.min()) / (lons.max() - lons.min())
ratio = (p3.y - p1.y) / (p3.x - p1.x)
size_int = 12
fig_size = (size_int, int(round(ratio * size_int)))

#########################################################################

fig, ax = plt.subplots(figsize=fig_size)

ax.set_title(f"run - ref {forecast.reference_time} - time {forecast.echeance}")
ax.barbs(X, Y, U * 1.852, V * 1.852, length=6, barbcolor="b", flagcolor="r", linewidth=1.25, zorder=999)

# cx.add_basemap(ax, crs="EPSG:4326", source="http://localhost:8000/{z}/{x}/{y}/shom")
cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.OpenStreetMap.France)

bb_polygon = Polygon([p1, p2, p3, p4])
bbox = gpd.GeoDataFrame(geometry=[bb_polygon], crs="EPSG:4326")
# world = gpd.overlay(world, bbox, how="intersection")
# world.geometry.boundary.plot(ax=ax, color=None, edgecolor="k", linewidth=2, alpha=0.75)
bbox.plot(ax=ax, alpha=0)

#########################################################################

plt.savefig("wind.png")
plt.show()
