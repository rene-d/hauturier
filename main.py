#!/usr/bin/env python3

import re
import sys


class Hour:
    def __init__(self, heures, minutes):
        self.heures = heures + minutes // 60
        self.minutes = minutes % 60

    def __str__(self):
        return f"{self.heures:02d}h{self.minutes:02d}"

    def diff_minutes(h1, h2) -> int:
        """ Retourne la différence en minutes entre deux heures. """
        return (h2.heures - h1.heures) * 60 + (h2.minutes - h1.minutes)

    def new(s):
        """ Initialise une heure à partir d'une chaîne de caractères. """
        m = re.match(r"^(\d+)[hH](\d+)$", s)
        if not m:
            return None
        hh, mm = int(m[1]), int(m[2])
        if not 0 <= hh < 24:
            return None
        if not 0 <= mm < 60:
            return None
        return Hour(hh, mm)

    def add_minutes(self, minutes):
        """ Ajoute des minutes à une heure. """
        return Hour(self.heures, self.minutes + int(minutes))


def read_token(prompt=None):
    """ Lit une chaîne de caractères délimitée par des espaces. """
    if prompt:
        sys.stdout.write(prompt)
    s = ""
    while True:
        c = sys.stdin.read(1)
        if not c:
            return s or None
        if c in "\n\r\t ":
            if s != "":
                return s
        else:
            s += c


print("Calcul de marées")
print()

h1 = Hour.new(read_token("Heure 1: "))
m1 = float(read_token("Hauteur 1: "))
h2 = Hour.new(read_token("Heure 2: "))
m2 = float(read_token("Hauteur 2: "))
print()

hm = h1.diff_minutes(h2) / 6
dz = (m2 - m1) / 12

print()
if dz < 0:
    print(f"PM: {h1} {m1:5.2f} m")
    print(f"BM: {h2} {m2:5.2f} m")
else:
    print(f"BM: {h1} {m1:5.2f} m")
    print(f"PM: {h2} {m2:5.2f} m")

print()
print(f"HM={hm:.3f} min  dz={abs(dz):.3f} m")

print()

douzaines = (1, 2, 3, 3, 2, 1)
cumul = (0, 1, 3, 6, 9, 11)

decalage_heure = 0
nom_heure = "hiver"

while True:
    s = read_token()

    if not s or s == ".":
        break

    if s == "été":
        decalage_heure = 60
        nom_heure = "été"
        continue

    h = Hour.new(s)
    if h:
        delta = (h1.diff_minutes(h) - decalage_heure) / hm
        hauteur = m1 + dz * (cumul[int(delta)] + douzaines[int(delta)] * (delta - int(delta)))
        print(f"hauteur marée à {h} (heure {nom_heure}) : {hauteur:.2f} m")
        continue

    m = float(s)
    if m:
        nb_dz = (m - m1) / dz
        for i in range(6):
            if cumul[i] <= int(nb_dz) < cumul[i] + douzaines[i]:
                delta = (i + (nb_dz - cumul[i]) / douzaines[i]) * hm
                h = h1.add_minutes(delta + decalage_heure)
                print(f"heure marée à {m:.2f} m : {h} (heure {nom_heure})")
                break