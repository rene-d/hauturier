#!/usr/bin/env python3

import matplotlib.pyplot as plt
import matplotlib.projections.polar
import numpy as np
import csv
import sys
from pathlib import Path


# # modification

# with open("SunOdyssey_410.pol", newline="") as csvfile:
#     reader = csv.reader(csvfile, delimiter=";")
#     rows = list(reader)

# with open("Maeva.pol", mode="w", newline="") as csvfile:

#     writer = csv.writer(csvfile, delimiter=";")
#     writer.writerow(rows[0])

#     for row in rows[1:]:
#         row = list(map(float, row))
#         twa = row[0]
#         if twa < 40 or twa >= 165:
#             for i in range(1, len(row)):
#                 row[i] = 0
#         else:
#             for i in range(1, len(row) - 1):
#                 row[i] *= 0.9

#         writer.writerow(map(lambda x: round(x, 1), row))


# tracé

pol_file = Path("Maeva.pol" if len(sys.argv) <= 1 else sys.argv[1])

with pol_file.open() as csvfile:
    reader = csv.reader(csvfile, delimiter=";")
    rows = list(reader)

tws_values = list(map(float, rows[0][1:]))

twa_values = []
bsp_matrix = []

for row in rows[1:]:
    twa = float(row[0])
    bsp = list(map(float, row[1:]))
    twa_values.append(twa)
    bsp_matrix.append(bsp)

theta = np.radians(twa_values)
# theta_sym = np.radians([360 - twa for twa in twa_values])  # symétrie miroir

theta_full = theta
bsp_full_matrix = bsp_matrix
# theta_full = np.concatenate([theta, theta_sym])
# bsp_full_matrix = bsp_matrix + bsp_matrix  # même vitesses copiées

fig, ax = plt.subplots(subplot_kw={"projection": "polar"})

ax: matplotlib.projections.polar.PolarAxes

ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)

ax.set_thetamin(0)
ax.set_thetamax(180)


# pour chaque TWS
for i, tws in enumerate(tws_values):
    r = [row[i] for row in bsp_full_matrix]
    ax.plot(theta_full, r, label=f"{tws:.0f} kt", linewidth=1)

# mise en forme
ax.set_xticks(np.arange(0, np.pi, np.pi / 18))
xlabels = [None] * 18
for i in range(0, 18):
    a = i * 10
    if 40 <= a <= 160 and (a == 40 or a == 160 or a % 20 == 10):
        xlabels[i] = str(a)
ax.set_xticklabels(labels=xlabels)

ax.yaxis.grid(True, linestyle="--", linewidth=0.8)  # pointillés


ax.set_title(f"Polaires {pol_file.stem}", va="bottom")
ax.set_rticks([4, 5, 6, 7, 8, 9, 10, 11])
ax.set_rlabel_position(225)
ax.grid(True)
ax.legend(loc="upper right", bbox_to_anchor=(1.1, 1.1))

plt.show()
