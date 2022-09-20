#!/usr/bin/env python3

import datetime
import os
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pygrib
from grib import MeteoFrance
from scipy.ndimage import zoom
from shapely.geometry import Point, Polygon

# ------------------------------------------------------------------------------------------------

HD = True

a = MeteoFrance(model="Arome", HD=HD, time="17H")
grib = pygrib.open(a.local_filename)

message = grib.select(name="10 metre U wind component")[0]
print(message)

reference_time = datetime.datetime(message.year, message.month, message.day, message.hour, message.minute)

# le 10ème item du premier grib
# 10:10 metre U wind component:m s**-1 (instant):regular_ll:heightAboveGround:level 10 m:fcst time 2 hrs:from 202208271800
lats, lons = message.latlons()  # WGS84 projection
print(lats.shape, lats.min(), lats.max(), lons.shape, lons.min(), lons.max())

shape = lats.shape  # nota = lons.shape
shape = (750, 750)
x = np.linspace(lons.min(), lons.max(), shape[1])  # shape[1] == nombre de colonnes
y = np.linspace(lats.min(), lats.max(), shape[0])  # shape[0] == nombre de lignes
X, Y = np.meshgrid(x, y)

######
land_sea = MeteoFrance(model="Arome_static", HD=HD).open()
land_sea_mask = np.copy(land_sea.select(name="Land-sea mask")[0].values[::-1])
######

item = grib.select(name="10 metre U wind component")[0]
U = np.copy(item.values[::-1])

item = grib.select(name="10 metre V wind component")[0]
V = np.copy(item.values[::-1])

U = zoom(U, (shape[0] / U.shape[0], shape[1] / U.shape[1]))
V = zoom(V, (shape[1] / V.shape[0], shape[1] / V.shape[1]))


# https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/
# world = gpd.read_file("data/GSHHS_shp/f/GSHHS_f_L1.shp")
world = gpd.read_file("data/ne_10m_admin_0_countries.shp")

harbor = Point(-4.497736, 48.406435)  # brest
harbor = Point(9.435695, 42.684558)  # bastia
harbor = Point(-3.988496, 48.713752)  # roscoff

extent_x = 0.2
extent_y = 0.1
p1 = Point(harbor.x - extent_x, harbor.y - extent_y)
p2 = Point(harbor.x + extent_x, harbor.y - extent_y)
p3 = Point(harbor.x + extent_x, harbor.y + extent_y)
p4 = Point(harbor.x - extent_x, harbor.y + extent_y)

####

i1 = np.argmin(X[0] < p1.x)
i2 = np.argmax(X[0] >= p3.x)

j1 = np.argmin(Y[:, 0] < p1.y)
j2 = np.argmax(Y[:, 0] >= p3.y)

X = X[j1:j2, i1:i2]
Y = Y[j1:j2, i1:i2]
U = U[j1:j2, i1:i2]
V = V[j1:j2, i1:i2]

# land_sea_mark = land_sea_mark[j1:j2, i1:i2]
# land_sea_mark = 1 - land_sea_mark
# print(U.shape, V.shape, ls.shape)
# U = U * land_sea_mark
# V = V * land_sea_mark

###

# ratio = (lats.max() - lats.min()) / (lons.max() - lons.min())
ratio = (p3.y - p1.y) / (p3.x - p1.x)
size_int = 20
fig_size = (size_int, int(round(ratio * size_int)))
print("fig_size", fig_size)

#####

bb_polygon = Polygon([p1, p2, p3, p4])
bbox = gpd.GeoDataFrame(geometry=[bb_polygon])

france = gpd.overlay(world, bbox, how="intersection")
france.plot(color="white", edgecolor="black")

#####

fig, ax = plt.subplots(figsize=fig_size)

ax.barbs(X, Y, U * 1.852, V * 1.852, length=7, barbcolor="b", flagcolor="r", linewidth=1.75, zorder=999)
# ax.quiver(X, Y, U, V,  zorder=999)

france.geometry.boundary.plot(ax=ax, color=None, edgecolor="k", linewidth=2, alpha=0.25)

ax.set_title(f"run - ref {reference_time.isoformat()}")

plt.savefig("wind.png")
