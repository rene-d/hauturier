#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "lxml", "pyyaml"]
# ///
"""Compare les créneaux de porte calculés au calendrier officiel du port.

Le port de Trébeurden publie un PDF annuel des horaires de porte : on le télécharge,
on en extrait les colonnes OUV/FERM, et on mesure l'écart avec le calcul de porte.py.

    ./verif_porte_trebeurden.py                # écarts avec les réglages par défaut
    ./verif_porte_trebeurden.py --calibrate    # balayage seuil × décalage
    ./verif_porte_trebeurden.py --details      # liste jour par jour

Nécessite `pdftotext` (poppler : brew install poppler).
"""

from __future__ import annotations

import argparse
import statistics as st
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from meteoconsult import Client, ScrapeError
from nav import extrema, gate_config, peak_coefs
from porte import Gate, gate_windows

PDF_URL = "https://port-trebeurden.fr/wp-content/uploads/2026/01/HORAIRES-PORTE-SPPT-2026.pdf"
YEAR = 2026
PORT = "Trébeurden"
TZ = "Europe/Paris"

# abscisses des colonnes dans le PDF (deux blocs : matin, après-midi)
COLUMNS = {"coef": (93, 314), "pm": (141, 362), "bm": (187, 409),
           "ouv": (229, 451), "ferm": (271, 493)}
MONTHS = {"JANVIER": 1, "FEVRIER": 2, "FÉVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5,
          "JUIN": 6, "JUILLET": 7, "AOUT": 8, "AOÛT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10,
          "NOVEMBRE": 11, "DECEMBRE": 12, "DÉCEMBRE": 12}


def official(cache: Path) -> list[tuple[str, datetime]]:
    """Horaires OUV/FERM du PDF officiel, en heure locale naïve.

    Le tableau a deux blocs par jour (matin, après-midi) ; une fermeture antérieure
    à son ouverture a lieu le lendemain, ce que le PDF signale par sa colonne « le N ».
    """
    pdf = cache / "porte-officiel.pdf"
    if not pdf.is_file():
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(requests.get(PDF_URL, timeout=60).content)
    xml = cache / "porte-officiel.xml"
    if not xml.is_file():
        subprocess.run(["pdftotext", "-bbox-layout", str(pdf), str(xml)], check=True)

    ns = {"x": "http://www.w3.org/1999/xhtml"}
    out = []
    for page in ET.parse(xml).getroot().findall(".//x:page", ns):
        rows: dict[int, list[tuple[float, str]]] = {}
        for w in page.findall(".//x:word", ns):
            rows.setdefault(round(float(w.get("yMin")) / 3), []).append(
                (float(w.get("xMin")), w.text or ""))
        month = None
        for key in sorted(rows):
            row = sorted(rows[key])
            for _, t in row:
                month = MONTHS.get(t.upper(), month)
            day = next((int(t) for x, t in row if x < 90 and t.isdigit() and int(t) <= 31), None)
            if month is None or day is None:
                continue

            cells: dict[tuple[str, int], str] = {}
            for x, t in row:
                if len(t) != 5 or t[2] != ".":
                    continue
                for name in ("ouv", "ferm"):
                    for i, col in enumerate(COLUMNS[name]):
                        if abs(col - x) < 12:
                            cells[(name, i)] = t

            for i in (0, 1):
                base = date(YEAR, month, day)
                for name in ("ouv", "ferm"):
                    t = cells.get((name, i))
                    if not t:
                        continue
                    when = datetime(base.year, base.month, base.day, int(t[:2]), int(t[3:]))
                    # une fermeture avant son ouverture est celle du lendemain
                    o = cells.get(("ouv", i))
                    if name == "ferm" and o and t < o:
                        when += timedelta(days=1)
                    out.append((name.upper(), when, i))
    return out


_EXTREMA: list | None = None
_COEFS: dict | None = None


def computed(threshold: float, model: str, offset: int, tz,
             height_offset: float = 0.0) -> list[tuple[str, datetime]]:
    global _EXTREMA, _COEFS
    if _EXTREMA is None:
        client = Client()
        port = client.resolve(PORT)
        tides: dict = {}
        for m in range(1, 13):
            try:  # le site ne publie pas les mois écoulés
                tides.update(client.month(port, YEAR, m, tz))
            except ScrapeError as e:
                print(f"  ignoré : {e}", file=sys.stderr)
        _EXTREMA = extrema(tides, tz)
        _COEFS = peak_coefs(tides, tz)
    out = []
    gate = Gate(threshold=threshold, model=model, time_offset=offset,
                height_offset=height_offset)
    for w in gate_windows(_EXTREMA, gate, _COEFS):
        out.append(("OUV", w.open.astimezone(tz).replace(tzinfo=None)))
        if w.close:
            out.append(("FERM", w.close.astimezone(tz).replace(tzinfo=None)))
    return out


def errors(ref, calc, months) -> list[tuple[int, str, datetime, datetime]]:
    """Écart en minutes entre chaque horaire officiel et le plus proche calculé."""
    out = []
    for kind, when, _ in ref:
        if when.month not in months:
            continue
        near = [t for k, t in calc if k == kind and abs((t - when).total_seconds()) < 6 * 3600]
        if not near:
            continue
        best = min(near, key=lambda t: abs(t - when))
        out.append((round((best - when).total_seconds() / 60), kind, when, best))
    return out


def summary(errs, label):
    d = sorted(e[0] for e in errs)
    n = len(d)
    if not n:
        print(f"{label}: aucun horaire apparié")
        return None
    mae = sum(abs(x) for x in d) / n
    p90 = sorted(abs(x) for x in d)[int(n * 0.9) - 1]
    within = sum(1 for x in d if abs(x) <= 10) * 100 / n
    print(f"{label}: n={n}  médiane={st.median(d):+.0f} min  |écart| moyen={mae:.1f}  "
          f"p90={p90}  ≤10 min={within:.0f}%")
    return mae


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--months", default="all", help="mois à comparer (défaut : tous ceux qui sont publiés)")
    ap.add_argument("--calibrate", action="store_true", help="balaye seuil et décalage")
    ap.add_argument("--details", action="store_true", help="liste chaque écart")
    args = ap.parse_args()

    from zoneinfo import ZoneInfo
    tz = ZoneInfo(TZ)
    months = set(range(1, 13)) if args.months == "all" else {int(x) for x in args.months.split(",")}

    ref = official(Path(__file__).with_name("cache"))
    g = gate_config("trebeurden", {}, PORT)
    calc = computed(g["threshold"], g["model"], g["time_offset"], tz, g["height_offset"])
    months &= {t.month for _, t in calc}  # seuls les mois réellement publiés
    print(f"calendrier officiel : {len(ref)} horaires, mois comparés {sorted(months)}\n")

    if args.calibrate:
        best = None
        for model in ("sine", "twelfths"):
            for threshold in [4.15 + 0.05 * i for i in range(13)]:
                for offset in range(0, 16, 2):
                    errs = errors(ref, computed(threshold, model, offset, tz,
                                                gate_config("trebeurden", {}, PORT)["height_offset"]), months)
                    d = [e[0] for e in errs]
                    mae = sum(abs(x) for x in d) / len(d)
                    if best is None or mae < best[0]:
                        best = (mae, model, threshold, offset, len(d))
        mae, model, threshold, offset, n = best
        print(f"meilleur réglage : model={model} threshold={threshold:.2f} "
              f"time_offset={offset}  (|écart| moyen {mae:.1f} min sur {n})")
        return 0

    errs = errors(ref, calc, months)
    summary(errs, f"seuil {g['threshold']:.2f} m, recalage {g['height_offset']:+.2f} m / "
                  f"{g['time_offset']:+d} min, {g['model']}")
    for kind in ("OUV", "FERM"):
        summary([e for e in errs if e[1] == kind], f"  {kind:4s}")

    worst = sorted(errs, key=lambda e: -abs(e[0]))[:10]
    print("\nplus grands écarts :")
    for d, kind, when, best in worst:
        print(f"  {d:+4d} min  {kind:4s} {when:%d/%m}  officiel {when:%H:%M}  calculé {best:%H:%M}")

    if args.details:
        print("\ndétail :")
        for d, kind, when, best in sorted(errs, key=lambda e: e[2]):
            print(f"  {when:%d/%m} {kind:4s} officiel {when:%H:%M}  calculé {best:%H:%M}  {d:+d} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
