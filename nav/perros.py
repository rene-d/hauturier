#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "lxml", "pyyaml"]
# ///
"""Ouverture d'une porte de bassin pour un seuil de hauteur d'eau donné.

Le port de Perros-Guirec ne publie pas la cote d'ouverture de son seuil basculant :
ce script sert à la trouver. Il liste les marées du mois et, pour chaque seuil
demandé, les heures auxquelles la hauteur d'eau le franchit en montant puis en
descendant. Les seuils d'ouverture et de fermeture peuvent différer.

Calé sur les 178 horaires de septembre et octobre 2026 du guide du port (bassin du
Linkin) : l'ouverture tombe à 7,40 m à moins d'une minute près (95 % à ±5 min).
La fermeture est plus haute que l'ouverture — la porte se referme bien avant que la
mer ne redescende à 7,40 m — mais elle ne suit un seuil constant qu'en vives-eaux :

    pleine mer > 9,20 m   fermeture à 8,10 m à 1,4 min près
    8,60 à 9,20 m         à 6 min près
    8,10 à 8,60 m         le modèle ferme ~24 min trop tôt
    < 8,10 m              seuil jamais atteint, repli à 7,40 m, ~21 min trop tard

Autrement dit, en dessous d'environ 8,60 m de pleine mer la règle du port n'est plus
une cote fixe : la cote de fermeture relevée y descend vers 7,60-7,70 m, et pour une
pleine mer de 7,48 m le guide ferme pile à l'étale. Sur les seules vives-eaux, le
couple 7,40 / 8,10 m reproduit le guide à 3,5 min près (88 % à ±5 min).

    ./perros.py                              # septembre 2026, seuils 7,40:8,00 / 8,05 / 8,10
    ./perros.py -s 7.40                      # un seul seuil, ouverture = fermeture
    ./perros.py -s 7.40:8.05 -s 7.40:8.15    # deux couples côte à côte
    ./perros.py -s 7.40:8.10                 # ouverture 7,40 m, fermeture 8,10 m
    ./perros.py -s 7.40:8.10:7.65            # + fermeture 7,65 m en mortes-eaux
    ./perros.py --limite-coef 70             # coefficient séparant les deux régimes
    ./perros.py --coef-mini 0                # ne pas exclure les mortes-eaux
    ./perros.py -j 12 -j 19 -j 25             # seulement ces jours
    ./perros.py -j 12-18                      # une plage de jours
    ./perros.py --mois 2026-10 --port Lézardrieux
    ./perros.py --hauteur "12 08:15" --hauteur "12 14:40"   # cote à une heure connue
    ./perros.py --modele twelfths            # règle des douzièmes au lieu du sinus

Le sens inverse (`--hauteur`) est le plus direct : relève deux ou trois horaires
d'ouverture réels sur le calendrier du port, demande la cote correspondante, et le
seuil se lit sur la colonne « hauteur ».
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from meteoconsult import Client, ScrapeError
from nav import JOURS_COURT, MOIS_LONG, aware, extrema, hm, peak_coefs
from porte import MODELS, Gate, gate_windows, height_at

DEFAULT_PORT = "Perros-Guirec"
DEFAULT_MONTH = "2026-09"
DEFAULT_THRESHOLDS = ["7.40:8.10", "7.40:8.10:7.65", "7.40"]


def parse_month(text: str) -> tuple[int, int]:
    try:
        year, month = text.split("-")
        return int(year), int(month)
    except ValueError:
        raise SystemExit(f"mois invalide : {text!r} (attendu AAAA-MM)")


def parse_thresholds(specs: list[str]) -> list[tuple[float, float, float | None]]:
    """« 7.40 », « 7.40:8.10 » (ouverture : fermeture), « 7.40:8.10:7.65 »
    (+ fermeture en mortes-eaux)."""
    out = []
    for spec in specs:
        parts = str(spec).split(":")
        try:
            lo = float(parts[0])
            hi = float(parts[1]) if len(parts) > 1 and parts[1] else lo
            neap = float(parts[2]) if len(parts) > 2 and parts[2] else None
        except (ValueError, IndexError):
            raise SystemExit(f"seuil invalide : {spec!r} "
                             f"(attendu « 7.40 », « 7.40:8.10 » ou « 7.40:8.10:7.65 »)")
        if len(parts) > 3:
            raise SystemExit(f"seuil invalide : {spec!r} (trois valeurs au plus)")
        out.append((lo, hi, neap))
    # dédoublonne en gardant l'ordre demandé ; `neap` peut être None, donc pas de tri
    return list(dict.fromkeys(out))


def parse_days(specs: list[str], last: int) -> set[int]:
    """Jours du mois demandés : « 12 », « 12-18 », répétables."""
    days: set[int] = set()
    for spec in specs:
        first, _, end = spec.partition("-")
        try:
            lo, hi = int(first), int(end or first)
        except ValueError:
            raise SystemExit(f"jour invalide : {spec!r} (attendu « 12 » ou « 12-18 »)")
        if not 1 <= lo <= hi <= last:
            raise SystemExit(f"jour hors du mois : {spec!r} (1 à {last})")
        days.update(range(lo, hi + 1))
    return days


def fmt(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--port", default=DEFAULT_PORT, help=f"port (défaut : {DEFAULT_PORT})")
    ap.add_argument("-m", "--mois", default=DEFAULT_MONTH, help=f"AAAA-MM (défaut : {DEFAULT_MONTH})")
    ap.add_argument("-s", "--seuil", action="append", metavar="OUV[:FERM[:FERM_ME]]",
                    help="seuils d'ouverture, de fermeture, et de fermeture en "
                         "mortes-eaux ; répétable")
    ap.add_argument("--limite-coef", type=int, default=70, metavar="COEF",
                    help="coefficient séparant vives-eaux et mortes-eaux (défaut : 70)")
    ap.add_argument("--coef-mini", type=int, default=49, metavar="COEF",
                    help="coefficient minimal pour que la porte s'ouvre (défaut : 49 ; "
                         "0 pour ne rien exclure)")
    ap.add_argument("--modele", choices=sorted(MODELS), default="sine",
                    help="interpolation entre extrêmes (défaut : sine)")
    ap.add_argument("--decalage-hauteur", type=float, default=0.0, metavar="M",
                    help="recalage des hauteurs de la source, en mètres")
    ap.add_argument("--decalage-temps", type=int, default=0, metavar="MIN",
                    help="recalage des horaires de la source, en minutes")
    ap.add_argument("-j", "--jour", action="append", metavar="JJ", default=[],
                    help="n'afficher que ce jour du mois ; répétable, accepte « 12-18 »")
    ap.add_argument("--hauteur", action="append", metavar='"JJ HH:MM"', default=[],
                    help="cote de la marée à cet instant du mois ; répétable")
    ap.add_argument("--timezone", default="Europe/Paris")
    args = ap.parse_args()

    tz = ZoneInfo(args.timezone)
    year, month = parse_month(args.mois)
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    days = parse_days(args.jour, last)
    thresholds = parse_thresholds(args.seuil or DEFAULT_THRESHOLDS)

    client = Client()
    try:
        port = client.resolve(args.port)
        tides = {}
        for y, m in ((year, month - 1) if month > 1 else (year - 1, 12), (year, month),
                     (year, month + 1) if month < 12 else (year + 1, 1)):
            try:  # les mois voisins ne servent qu'aux créneaux à cheval
                tides.update(client.month(port, y, m, tz))
            except ScrapeError as e:
                if (y, m) == (year, month):
                    raise
                print(f"  (mois voisin indisponible : {e})", file=sys.stderr)
    except ScrapeError as e:
        raise SystemExit(f"erreur : {e}")

    ext = extrema(tides, tz)

    print(f"{port.label} — {MOIS_LONG[month - 1]} {year}")
    print(f"Interpolation « {args.modele} », heures légales locales ({args.timezone}).")
    if days:
        print(f"Jours retenus : {', '.join(str(x) for x in sorted(days))}.")
    if args.decalage_hauteur or args.decalage_temps:
        print(f"Recalage de la source : {args.decalage_hauteur:+.2f} m, {args.decalage_temps:+d} min.")

    # --- sens inverse : cote de la marée à des instants donnés ------------------
    if args.hauteur:
        print("\ncote de la marée aux heures demandées :\n")
        print(f"  {'instant':16s} {'hauteur':>9s}")
        for spec in args.hauteur:
            try:
                day, hhmm = spec.split()
                when = aware(date(year, month, int(day)).isoformat(), hhmm, tz)
            except ValueError:
                raise SystemExit(f'instant invalide : {spec!r} (attendu "JJ HH:MM")')
            when -= timedelta(minutes=args.decalage_temps)
            h = height_at(ext, when, args.modele, args.decalage_hauteur)
            shown = f"{fmt(h)} m" if h is not None else "hors plage"
            print(f"  {when:%d/%m %H:%M}    {shown:>9s}")
        return 0

    # --- créneaux d'ouverture, une colonne par seuil ---------------------------
    coefs = peak_coefs(tides, tz)
    runs = [gate_windows(ext, Gate(threshold=lo, close=hi if hi != lo else None,
                                   neap_close=neap, neap_below=args.limite_coef,
                                   min_coef=args.coef_mini or None,
                                   model=args.modele, time_offset=args.decalage_temps,
                                   height_offset=args.decalage_hauteur), coefs)
            for lo, hi, neap in thresholds]

    def title(lo, hi, neap):
        if hi == lo and neap is None:
            return f"{fmt(lo)} m"
        if neap is None:
            return f"{fmt(lo)} → {fmt(hi)} m"
        return f"{fmt(lo)} → {fmt(hi)} / {fmt(neap)}"

    head = f"  {'jour':13s} {'pleine mer':>17s} {'coef':>5s}  "
    head += "  ".join(f"{title(*t):^22s}" for t in thresholds)
    print("\n" + head)
    print("  " + "-" * (len(head) - 2))

    for iso in sorted(tides):
        day = tides[iso]
        d = date.fromisoformat(iso)
        if d.month != month or (days and d.day not in days):
            continue
        for tide in day.tides:
            if tide.kind != "PM":
                continue
            peak = aware(iso, tide.hour, tz)
            label = f"{JOURS_COURT[d.weekday()]} {d.day:2d} {MOIS_LONG[month - 1][:4]}."
            row = (f"  {label:13s} "
                   f"{tide.hour:>7s} {fmt(float(tide.height)) + ' m':>9s} "
                   f"{tide.coef if tide.coef is not None else '--':>5}  ")
            for windows in runs:
                w = next((w for w in windows
                          if w.close and w.open <= peak <= w.close), None)
                if w is None:
                    cell = ("coef trop bas" if tide.coef and tide.coef < args.coef_mini
                            else "seuil non atteint")
                else:
                    o = w.open.astimezone(tz)
                    c = w.close.astimezone(tz)
                    over = (c.date() - o.date()).days
                    cell = (f"{o:%H:%M} → {c:%H:%M}" + (f"+{over}j" if over else "   ")
                            + f" {hm(w.duration):>5s}")
                row += f"{cell:^22s}  "
            print(row.rstrip())

    print(f"\n  « 7,40 → 8,10 / 7,65 » : ouverture, fermeture en vives-eaux, puis en")
    print(f"  mortes-eaux (coefficient < {args.limite_coef}).")
    if args.coef_mini:
        print(f"  « coef trop bas » : sous le coefficient {args.coef_mini}, le port ne manœuvre pas.")
    print("  « → HH:MM+1j » : fermeture le lendemain.")
    print("  En morte-eau la basse mer peut rester au-dessus du seuil : le même")
    print("  créneau couvre alors plusieurs pleines mers et se répète d'une ligne")
    print("  à l'autre — la porte n'a pas refermé entre les deux.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
