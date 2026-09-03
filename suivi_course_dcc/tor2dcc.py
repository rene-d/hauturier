#!/usr/bin/env python3
"""Tracker The Ocean Race Atlantic 2026 -> fichiers Adrena pour qtVlm.

Produit deux fichiers aux chemins **stables** :

    <sortie>/<course>.dcc   descriptif de la flotte
    <sortie>/<course>.txt   positions (posreport)

Mettre à jour = relancer la commande. Les deux fichiers sont réécrits en
place, de façon atomique : qtVlm peut les relire à tout moment sans jamais
tomber sur un fichier tronqué.

    python3 tor2dcc.py                    # trace complète, dans out/
    python3 tor2dcc.py --pas 600          # un point toutes les 10 min
    python3 tor2dcc.py --depuis 24        # dernières 24 h seulement
    python3 tor2dcc.py --loop 300         # rafraîchit toutes les 5 minutes

Par défaut le posreport contient **toute la trace** de chaque bateau, soit un
point par minute depuis le départ. Voir FORMAT-DCC.md pour le format.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import dcc
import tracker
from tracker import FleetEntry, TrackPoint

DEFAULT_OUT = Path("out")
MIN_PERIOD = 60  # la source publie un point par minute : inutile d'aller plus vite


def slugify(race: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in race).strip("_").lower() or "course"


def write_atomic(path: Path, text: str) -> None:
    """Écrit via un temporaire puis renomme : jamais de fichier à demi écrit."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(text.encode(dcc.ENCODING, errors="strict"))
    os.replace(tmp, path)


def echantillonner(
    points: list[TrackPoint],
    *,
    pas: int | None,
    depuis: float | None,
    dernier_seulement: bool,
) -> list[TrackPoint]:
    """Réduit une trace. Le dernier point est toujours conservé."""
    if dernier_seulement:
        return points[-1:]

    retenus = points
    if depuis is not None:
        limite = datetime.now(UTC) - timedelta(hours=depuis)
        retenus = [p for p in retenus if p.at >= limite] or points[-1:]

    if pas:
        ecart = timedelta(seconds=pas)
        filtres = [retenus[0]]
        for point in retenus[1:]:
            if point.at - filtres[-1].at >= ecart:
                filtres.append(point)
        if filtres[-1] is not retenus[-1]:
            filtres.append(retenus[-1])
        retenus = filtres
    return retenus


def build(
    entries: list[FleetEntry],
    *,
    serie: str | None,
    pas: int | None,
    depuis: float | None,
    dernier_seulement: bool,
) -> tuple[list[dcc.Competitor], list[dcc.Fix]]:
    competitors: list[dcc.Competitor] = []
    fixes: list[dcc.Fix] = []
    for entry in entries:
        team = entry.team
        competitors.append(
            dcc.Competitor(
                name=team.name,
                kind=serie if serie is not None else team.country,
                ident=team.track_id,
                skipper="",
            )
        )
        retenus = echantillonner(
            entry.points, pas=pas, depuis=depuis, dernier_seulement=dernier_seulement
        )
        fixes.extend(
            dcc.Fix(ident=team.track_id, lat=p.lat, lon=p.lon, at=p.at) for p in retenus
        )
    return competitors, fixes


def refresh(outdir: Path, args: argparse.Namespace) -> tuple[Path, Path, int, int]:
    race, entries = tracker.fetch_fleet(args.event)
    race = args.race or race

    competitors, fixes = build(
        entries,
        serie=args.serie,
        pas=args.pas,
        depuis=args.depuis,
        dernier_seulement=args.dernier_point,
    )

    outdir.mkdir(parents=True, exist_ok=True)
    stem = slugify(race)
    dcc_path = outdir / f"{stem}.dcc"
    pos_path = outdir / f"{stem}.txt"

    write_atomic(dcc_path, dcc.format_dcc(race, competitors, generated=datetime.now(UTC)))
    write_atomic(pos_path, dcc.format_posreport(fixes, pad=not args.no_pad))
    return dcc_path, pos_path, len(competitors), len(fixes)


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
    parser.add_argument(
        "--race", help="nom de course (défaut : celui annoncé par la source)"
    )
    parser.add_argument(
        "--serie",
        help="valeur du champ « type » (défaut : le pays de l'équipe, "
        "la source ne publiant pas la série)",
    )
    parser.add_argument(
        "--pas",
        type=int,
        metavar="SECONDES",
        help="sous-échantillonne la trace (la source publie 1 point/minute)",
    )
    parser.add_argument(
        "--depuis",
        type=float,
        metavar="HEURES",
        help="ne garder que les N dernières heures",
    )
    parser.add_argument(
        "--dernier-point",
        action="store_true",
        help="une seule position par bateau, la plus récente",
    )
    parser.add_argument(
        "--no-pad",
        action="store_true",
        help="degrés sans zéro-padding (`3.2160W` au lieu de `003.2160W`) — "
        "variante à trancher dans qtVlm, cf. FORMAT-DCC.md",
    )
    parser.add_argument(
        "--loop",
        type=int,
        metavar="SECONDES",
        help=f"rafraîchir en continu (minimum {MIN_PERIOD} s)",
    )
    args = parser.parse_args(argv)

    if args.loop is not None and args.loop < MIN_PERIOD:
        parser.error(f"--loop : {MIN_PERIOD} s minimum (la source publie 1 point/minute)")

    while True:
        try:
            dcc_path, pos_path, boats, fixes = refresh(args.outdir, args)
        except RuntimeError as exc:
            if args.loop is None:
                raise
            print(
                f"échec, nouvelle tentative dans {args.loop} s : {exc}", file=sys.stderr
            )
        else:
            print(
                f"{datetime.now(UTC):%H:%M:%S}  {boats} bateaux, "
                f"{fixes} positions  ->  {pos_path}"
            )
        if args.loop is None:
            print(f"descriptif : {dcc_path}")
            return 0
        time.sleep(args.loop)


if __name__ == "__main__":
    sys.exit(main())
