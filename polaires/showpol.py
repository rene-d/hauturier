#!/usr/bin/env python3

import argparse
import matplotlib.pyplot as plt
import matplotlib.projections.polar
import numpy as np
import csv
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("pol_file", nargs="?", default="Maeva.pol")
parser.add_argument("--pdf", metavar="OUTPUT", nargs="?", const=True,
                    help="exporte en PDF (chemin optionnel, sinon <fichier>.pdf)")
args = parser.parse_args()

pol_file = Path(args.pol_file)
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

if args.pdf is not None:
    pdf_path = Path(args.pdf) if args.pdf is not True else pol_file.with_suffix(".pdf")
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight")
    print(f"exporté : {pdf_path}")
else:
    plt.show()
