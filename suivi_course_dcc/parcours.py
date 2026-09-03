#!/usr/bin/env python3
"""Parcours et zones d'exclusion PredictWind -> fichiers GPX et KML.

Complément cartographique de `tor2dcc.py`, qui ne produit que la flotte. Rien
n'est saisi à la main : tout vient du bootstrap du tracker et du
`boundaries.json` qu'il annonce (voir `tracker.py`).

    python3 parcours.py                   # -> out/*.gpx et out/*.kml

Deux formats, pour deux natures d'objet :

- les **routes** (parcours théorique, ligne de départ, ligne d'arrivée) en GPX,
  qui est ce que qtVlm importe comme route ;
- les **zones** en KML, dont le `<Polygon>` porte la notion de surface fermée
  que GPX n'a pas.

La source publie ses polygones **ouverts** : le retour au premier point est
implicite. KML exige un `LinearRing` fermé, la fermeture est donc ajoutée à
l'écriture — c'est la seule retouche géométrique de ce module.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

import tracker
from tracker import Course, LatLon, Zone

DEFAULT_OUT = Path("out")
ENCODING = "utf-8"  # GPX comme KML sont spécifiés en UTF-8

# Trait rouge, remplissage 20 % : KML code la couleur en aabbggrr, pas en rrggbb.
ZONE_LINE_COLOR = "ff0000ff"
ZONE_FILL_COLOR = "330000ff"

GPX_OPEN = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="tor2dcc" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 \
http://www.topografix.com/GPX/1/1/gpx.xsd">
  <metadata>
    <name>{name}</name>
    <desc>{desc}</desc>
  </metadata>
  <rte>
    <name>{name}</name>
"""

KML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <description>{desc}</description>
    <Style id="exclusion">
      <LineStyle><color>{line}</color><width>2</width></LineStyle>
      <PolyStyle><color>{fill}</color></PolyStyle>
    </Style>
    <Placemark>
      <name>{name}</name>
      <styleUrl>#exclusion</styleUrl>
      <Polygon>
        <tessellate>1</tessellate>
        <altitudeMode>clampToGround</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
{coords}
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""


def slugify(name: str) -> str:
    """« Ushant (Ouessant) TSS » -> « ushant-ouessant-tss »."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_name.lower())).strip("-")


def format_gpx(name: str, desc: str, points: list[LatLon], names: list[str]) -> str:
    """Une route GPX. `names` nomme chaque point (autant que de points)."""
    if len(names) != len(points):
        raise ValueError(f"{len(names)} nom(s) pour {len(points)} point(s)")
    body = "".join(
        f'    <rtept lat="{p.lat}" lon="{p.lon}">\n'
        f"      <name>{escape(label)}</name>\n"
        f"    </rtept>\n"
        for p, label in zip(points, names, strict=True)
    )
    header = GPX_OPEN.format(name=escape(name), desc=escape(desc))
    return f"{header}{body}  </rte>\n</gpx>\n"


def format_kml(zone: Zone) -> str:
    """Une zone en polygone KML. Coordonnées en `lon,lat,alt`, ordre KML."""
    ring = zone.closed
    coords = "\n".join(f"            {p.lon},{p.lat},0" for p in ring)
    desc = (
        f"Zone d'exclusion PredictWind, clé {zone.key}, "
        f"relevé {zone.at:%Y-%m-%dT%H:%M:%SZ}. Polygone de {len(ring) - 1} sommets, "
        f"fermé ici en répétant le premier point."
    )
    return KML_TEMPLATE.format(
        name=escape(zone.name),
        desc=escape(desc),
        line=ZONE_LINE_COLOR,
        fill=ZONE_FILL_COLOR,
        coords=coords,
    )


def route_names(count: int, ends: tuple[str, str] = ("START", "FINISH")) -> list[str]:
    """Extrémités nommées, points intermédiaires numérotés."""
    if count < 2:
        raise ValueError(f"route de {count} point(s)")
    return [ends[0], *[f"WP{i:03d}" for i in range(1, count - 1)], ends[1]]


def write(course: Course, zones: list[Zone], outdir: Path) -> list[Path]:
    """Écrit toutes les routes et toutes les zones. Retourne les chemins écrits."""
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Une ligne n'a pas de sens de parcours : ses extrémités sont numérotées,
    # la source ne disant pas laquelle est au vent.
    extremites = ("Extrémité 1", "Extrémité 2")
    routes = (
        ("course", "Parcours théorique", course.route, ("START", "FINISH")),
        ("ligne-depart", "Ligne de départ", course.start_line, extremites),
        ("ligne-arrivee", "Ligne d'arrivée", course.finish_line, extremites),
    )
    for stem, label, points, ends in routes:
        path = outdir / f"{stem}.gpx"
        desc = f"{label} — bootstrap PredictWind, {len(points)} points."
        path.write_text(
            format_gpx(label, desc, points, route_names(len(points), ends)),
            encoding=ENCODING,
        )
        written.append(path)

    for zone in zones:
        path = outdir / f"zone-{slugify(zone.name)}.kml"
        path.write_text(format_kml(zone), encoding=ENCODING)
        written.append(path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "outdir",
        nargs="?",
        type=Path,
        default=DEFAULT_OUT,
        help=f"répertoire de sortie (défaut : {DEFAULT_OUT}/)",
    )
    parser.add_argument(
        "--event",
        default=tracker.DEFAULT_EVENT,
        help=f"événement PredictWind (défaut : {tracker.DEFAULT_EVENT})",
    )
    args = parser.parse_args(argv)

    course, zones = tracker.fetch_course_and_zones(args.event)
    for path in write(course, zones, args.outdir):
        print(path)
    print(
        f"{len(course.route)} points de parcours, {len(zones)} zones",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
