#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "lxml", "pyyaml"]
# ///
"""Génère un carnet de marées PDF à partir d'un fichier de configuration YAML.

    ./nav.py -c config.yaml -o build/nav.pdf

Les horaires viennent de marine.meteoconsult.fr (cf. meteoconsult.py) et la mise
en page est faite par Typst (template.typ), qui lit le JSON produit ici.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from meteoconsult import BASE, MOIS, PARIS, Client, Port, ScrapeError
from porte import MODELS, Gate, gate_windows

HERE = Path(__file__).parent

# Portes de bassin à flot. Les réglages par défaut d'un port sont ceux qui
# reproduisent son calendrier officiel ; `verif_porte_trebeurden.py` et `perros.py` mesurent
# l'accord. Tout est surchargeable depuis le YAML.
GATE_DEFAULTS = {
    "threshold": None,      # cote d'ouverture / zéro des cartes
    "close": None,          # cote de fermeture (défaut : celle d'ouverture)
    "neap_close": None,     # cote de fermeture en mortes-eaux
    "neap_below": 70,       # coefficient sous lequel on passe en mortes-eaux
    "min_coef": None,       # sous ce coefficient, la porte ne s'ouvre pas du tout
    "sill": None,           # cote du radier, pour le créneau de passage du bateau
    "draft": None,          # tirant d'eau ; sans lui, seuls les créneaux de porte
    "clearance": 0.40,      # pied de pilote
    "height_offset": 0.0,   # recalage des hauteurs de la source, en mètres
    "time_offset": 0,       # recalage des horaires de la source, en minutes
    "model": "sine",
    "warn_coef": 70,        # au-delà, le courant dans la passe mérite un avertissement
}

GATE_PRESETS = {
    # Cote d'ouverture annoncée 4,30 m, radier à 2,80 m (il reste 1,50 m d'eau à
    # l'ouverture). Météo Consult y publie des hauteurs ~0,25 m plus basses et des
    # horaires ~8 min en avance ; l'accord avec le calendrier du port est alors de
    # 4,6 min en moyenne sur 436 horaires.
    "trebeurden": {"threshold": 4.30, "sill": 2.80, "height_offset": 0.25, "time_offset": 8},

    # Seuil basculant automatisé du bassin du Linkin. L'ouverture est à 7,40 m à
    # moins d'une minute près ; la fermeture suit deux régimes séparés au
    # coefficient 70 (8,10 m en vives-eaux, 7,65 m en mortes-eaux), ce qui ramène
    # l'écart de 10,3 à 4,3 min sur les 178 horaires de septembre-octobre 2026.
    # Le guide du port ne publie pas la cote du radier : pas de créneau bateau.
    # En dessous du coefficient 49, le guide ne donne aucune ouverture : le port ne
    # manœuvre pas, même si la cote de 7,40 m est atteinte.
    "perros-guirec": {"threshold": 7.40, "close": 8.10, "neap_close": 7.65,
                      "neap_below": 70, "min_coef": 49},
}

# Quand une basse mer frôle le seuil, quelques centimètres d'écart sur la hauteur
# déplacent la fermeture de plus d'une heure — voire la suppriment. Ces jours-là
# sont signalés comme incertains plutôt que donnés pour exacts.
GATE_MARGIN = 0.25

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
JOURS_COURT = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS_LONG = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def parse_date(value, default: date | None = None) -> date:
    if value is None and default is not None:
        return default
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        if value.strip().lower() in ("today", "aujourd'hui", "auj"):
            return date.today()
        return date.fromisoformat(value.strip())
    raise ValueError(f"date invalide : {value!r}")


def date_range(conf: dict) -> list[date]:
    start = parse_date(conf.get("start"), date.today())
    if "end" in conf:
        end = parse_date(conf["end"])
        if end < start:
            raise ValueError("`end` est antérieur à `start`")
        n = (end - start).days + 1
    else:
        n = int(conf.get("days", 7))
    if n < 1:
        raise ValueError("`days` doit être positif")
    return [start + timedelta(days=i) for i in range(n)]


def default_config() -> Path:
    """Configuration par défaut : `config.yaml`, ou `config.yml` s'il subsiste."""
    for name in ("config.yaml", "config.yml"):
        if (HERE / name).is_file():
            return HERE / name
    return HERE / "config.yaml"


def zone(name: str | None) -> ZoneInfo:
    """Fuseau d'un port ; les horaires publiés sont en heure locale du lieu."""
    if not name:
        return PARIS
    if isinstance(name, ZoneInfo):
        return name
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"fuseau horaire inconnu : {name!r}")


def aware(day: str, hour: str, tz) -> datetime:
    """Horaire local -> datetime avec fuseau (heure ambiguë du recul d'heure gérée)."""
    return datetime.fromisoformat(f"{day}T{hour}").replace(tzinfo=tz)


def extrema(tides: dict, tz) -> list[tuple[datetime, float]]:
    """Suite (instant, hauteur) triée sur l'échelle absolue."""
    out = []
    for iso in sorted(tides):
        for t in tides[iso].tides:
            if t.height is None:
                continue
            dt = aware(iso, t.hour, tz)
            # la nuit du recul d'heure, la 2e occurrence d'un horaire local répété
            # ne se distingue que par `fold`
            if out and dt <= out[-1][0]:
                dt = dt.replace(fold=1)
            out.append((dt, float(t.height)))
    return out


def hm(delta: timedelta) -> str:
    m = round(delta.total_seconds() / 60)
    if m >= 24 * 60:  # en morte-eau la porte reste ouverte plusieurs jours
        return f"{m // 1440}j{(m % 1440) // 60:02d}"
    return f"{m // 60}h{m % 60:02d}"


def long_date(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS_LONG[d.month - 1]} {d.year}"


def port_url(port: Port, d: date) -> str:
    return (
        f"{BASE}/meteo-marine/horaires-des-marees/{port.slug}-{port.id}"
        f"/{MOIS[d.month - 1]}-{d.year}#{d.day:02d}-{d.month:02d}"
    )


def gate_entry(entry: dict) -> dict | None:
    """Reconnaît un item « porte de bassin » et retourne ses surcharges YAML.

    Accepte `gate: <port>` ou, plus court, un nom commençant par « PORTE ».
    """
    ref = entry.get("gate")
    if not ref:
        name = entry.get("name") or entry.get("label") or ""
        m = re.match(r"\s*porte\s+(?:de\s+|du\s+|d')?(.+)", name, re.IGNORECASE)
        if not m:
            return None
        ref = m.group(1)
    over = {k: entry[k] for k in GATE_DEFAULTS if entry.get(k) is not None}
    return {"ref": ref, "over": over}


def gate_config(slug: str, over: dict, label: str) -> dict:
    """Réglages effectifs d'une porte : défauts, préréglage du port, puis YAML."""
    conf = dict(GATE_DEFAULTS)
    conf.update(GATE_PRESETS.get(slug, {}))
    conf.update(over)

    if conf["threshold"] is None:
        raise ValueError(
            f"aucune cote d'ouverture connue pour la porte de {label} : "
            f"donnez `threshold` dans le YAML (ports préréglés : {', '.join(sorted(GATE_PRESETS))})"
        )
    if conf["draft"] is not None and conf["sill"] is None:
        raise ValueError(
            f"cote du radier inconnue pour {label} : `draft` demande aussi `sill` "
            f"(le guide du port ne la publie pas toujours)"
        )
    if conf["model"] not in MODELS:
        raise ValueError(f"modèle de marée inconnu : {conf['model']!r} (attendu {'/'.join(MODELS)})")
    for k in ("threshold", "close", "neap_close", "sill", "draft", "clearance", "height_offset"):
        if conf[k] is not None:
            conf[k] = float(conf[k])
    conf["time_offset"] = int(conf["time_offset"])
    for k in ("neap_below", "min_coef", "warn_coef"):
        if conf[k] is not None:
            conf[k] = int(conf[k])
    return conf


def peak_coefs(tides: dict, tz) -> dict[datetime, int]:
    """Coefficient de chaque pleine mer, indexé par instant."""
    return {aware(iso, t.hour, tz): t.coef
            for iso in sorted(tides) for t in tides[iso].tides
            if t.kind == "PM" and t.coef is not None}


def gate_days(tides: dict, dates: list[date], tz, gate: dict) -> list[dict]:
    """Créneaux de porte — et de passage du bateau — répartis sur les jours demandés.

    Deux seuils sont suivis : la cote d'ouverture de la porte, et, si un tirant d'eau
    est donné, la cote à laquelle le bateau franchit le radier. Un créneau est
    rattaché au jour où il s'ouvre, comme le fait le calendrier officiel du port ;
    `close_day` dit de combien de jours la fermeture déborde, et un créneau entamé la
    veille qui se referme dans la journée apparaît sans heure d'ouverture.
    """
    ext = extrema(tides, tz)
    coefs = peak_coefs(tides, tz)
    peaks = sorted(coefs.items())

    base = Gate(threshold=gate["threshold"], close=gate["close"],
                neap_close=gate["neap_close"], neap_below=gate["neap_below"],
                min_coef=gate["min_coef"],
                model=gate["model"], time_offset=gate["time_offset"],
                height_offset=gate["height_offset"])
    series = [("gate", "porte", base)]
    if gate["draft"] is not None:
        level = gate["sill"] + gate["draft"] + gate["clearance"]
        # le bateau passe au-dessus du radier : un seul seuil, sans régime de marnage
        boat = replace(base, threshold=level, close=None, neap_close=None, min_coef=None)
        series.append(("boat", f"{gate['draft']:.2f} m".replace(".", ","), boat))

    runs = [(kind, label, gate_windows(ext, cfg, coefs)) for kind, label, cfg in series]

    days = []
    for d in dates:
        day = tides.get(d.isoformat())
        if day is None:
            days.append(None)
            continue

        out = []
        for rank, (kind, label, windows) in enumerate(runs):
            covered = False
            found = False
            for w in windows:
                opened = w.open.astimezone(tz)
                closed = w.close.astimezone(tz) if w.close else None
                if opened.date() != d and (opened.date() > d
                                           or (closed and closed.date() < d)):
                    continue
                if opened.date() < d and (closed is None or closed.date() > d):
                    covered = True       # la journée entière est dans un créneau
                    continue
                found = True
                own = opened.date() == d
                coef = max((c for t, c in peaks if opened <= t <= (closed or opened)),
                           default=None)
                out.append({
                    "kind": kind, "label": label, "rank": rank,
                    "sort": opened.hour * 60 + opened.minute if own else -1,
                    "open": opened.strftime("%H:%M") if own else None,
                    "open_utc": f"{opened.utcoffset().total_seconds() / 3600:+g}",
                    "close": closed.strftime("%H:%M") if closed else None,
                    "close_utc": f"{closed.utcoffset().total_seconds() / 3600:+g}" if closed else None,
                    "close_day": (closed.date() - d).days if closed else None,
                    "duration": hm(w.duration) if closed else None,
                    "coef": coef,
                    "warn": kind == "gate" and coef is not None and coef >= gate["warn_coef"],
                    "all_day": False,
                })
            if covered and not found:
                out.append({"kind": kind, "label": label, "rank": rank, "sort": -2,
                            "open": None, "open_utc": None, "close": None,
                            "close_utc": None, "close_day": None, "duration": None,
                            "coef": None, "warn": False, "all_day": True})
        out.sort(key=lambda w: (w["sort"], w["rank"]))

        # basse mer proche du seuil : le créneau calculé n'est pas fiable ce jour-là
        thresholds = [cfg.opening() for _, _, cfg in series] + [
            cfg.closing(c) for _, _, cfg in series for c in (None, 0)]
        uncertain = any(t.kind == "BM" and t.height is not None
                        and any(abs(float(t.height) - x) < GATE_MARGIN for x in thresholds)
                        for t in day.tides)

        # on reprend l'éphéméride du jour telle quelle (soleil, lune, %) : la
        # recopier champ par champ finissait par en oublier
        info = asdict(day)
        info.pop("tides")
        days.append({**info, "windows": out, "labelled": len(series) > 1,
                     "uncertain": uncertain})
    return days


def collect(conf: dict, client: Client) -> dict:
    """Résout les ports, télécharge les marées et construit le document."""
    dates = date_range(conf)
    months = sorted({(d.year, d.month) for d in dates})
    # les créneaux de porte débordent d'un jour de part et d'autre
    wide = sorted({(d.year, d.month) for d in (dates[0] - timedelta(days=1), *dates,
                                               dates[-1] + timedelta(days=2))})
    default_tz = conf.get("timezone")   # None = fuseau déduit de chaque port

    ports_out = []
    for entry in conf.get("ports") or []:
        if isinstance(entry, str):
            entry = {"name": entry}
        if not isinstance(entry, dict):
            raise ValueError(f"entrée de port invalide : {entry!r}")

        gate = gate_entry(entry)
        if entry.get("id"):
            port = Port(id=int(entry["id"]), slug=entry.get("slug", ""), label=entry.get("label", ""))
            if not port.slug:  # le slug est déduit du nom si absent
                port.slug = client.resolve(entry.get("name") or entry.get("label") or "").slug
            if not port.label:
                port.label = client.port_name(port)
        else:
            name = gate["ref"] if gate else (entry.get("name") or entry.get("label"))
            if not name:
                raise ValueError(f"port sans `name` ni `id` : {entry!r}")
            port = client.resolve(name)
            port.label = entry.get("label") or port.label

        # le site publie chaque port à son heure locale : on prend le fuseau déduit
        # de son pays, sauf indication explicite dans le YAML
        name = entry.get("timezone") or default_tz or port.tz
        if not name:
            print(f"    fuseau inconnu pour {port.country or 'ce port'}, "
                  f"Europe/Paris retenu — précisez `timezone` si besoin", file=sys.stderr)
        tz = zone(name)
        kind = "gate" if gate else "tides"
        if gate:
            gate = gate_config(port.slug, gate["over"], port.label)
            detail = f", porte à {gate['threshold']:.2f} m"
            if gate["close"] is not None and gate["close"] != gate["threshold"]:
                detail += f", fermeture à {gate['close']:.2f} m"
            if gate["neap_close"] is not None:
                detail += f" ({gate['neap_close']:.2f} m sous coef {gate['neap_below']})"
        else:
            detail = ""
        print(f"  {port.label} (id {port.id}, {tz}{detail})", file=sys.stderr)

        tides: dict[str, object] = {}
        for year, month in (wide if gate else months):
            try:
                tides.update(client.month(port, year, month, tz))
            except ScrapeError:
                # les mois de débordement d'une porte ne servent qu'aux créneaux à
                # cheval sur la frontière : leur absence n'est pas bloquante
                if (year, month) in months:
                    raise
                print(f"    {MOIS[month - 1]} {year} indisponible, ignoré", file=sys.stderr)

        if gate:
            if not entry.get("label"):
                port.label = f"Porte {port.label}"
            days = gate_days(tides, dates, tz, gate)
        else:
            days = [asdict(tides[d.isoformat()]) if d.isoformat() in tides else None for d in dates]

        ports_out.append({"label": port.label, "url": port_url(port, dates[0]),
                          "kind": kind, "days": days})

    columns = int(conf.get("columns", 3))
    # au-delà de 4 colonnes, le tableau ne tient plus en portrait
    landscape = conf.get("landscape")
    if landscape is None:
        landscape = columns >= 5

    first, last = dates[0], dates[-1]
    if first == last:
        period = long_date(first)
    else:
        period = f"du {long_date(first)} au {long_date(last)}"

    return {
        "title": conf.get("title") or "Marées",
        "period": period,
        "generated": long_date(date.today()),
        "columns": columns,
        "paper": conf.get("paper", "a4"),
        "flipped": bool(landscape),
        "source": {"name": "Météo Consult Marine", "url": BASE},
        "gate_note": conf.get("gate_note"),
        "dates": [
            {
                "iso": d.isoformat(),
                "label": f"{JOURS_COURT[d.weekday()]} {d.day} {MOIS_LONG[d.month - 1][:4]}.",
                "long": long_date(d),
            }
            for d in dates
        ],
        "ports": ports_out,
    }


def typst(data_file: Path, output: Path) -> None:
    if not shutil.which("typst"):
        raise SystemExit("typst introuvable dans le PATH (brew install typst)")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "typst", "compile",
        "--root", str(HERE),
        "--input", f"data={data_file.relative_to(HERE)}",
        str(HERE / "template.typ"), str(output),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", type=Path, default=HERE / "config.yaml", help="fichier YAML (défaut : config.yaml)")
    ap.add_argument("-o", "--output", type=Path, default=HERE / "build" / "nav.pdf", help="PDF à produire")
    ap.add_argument("--no-cache", action="store_true", help="ignore le cache HTTP")
    ap.add_argument("--open", action="store_true", help="ouvre le PDF une fois produit")
    ap.add_argument("--search", metavar="NOM", help="cherche l'identifiant d'un lieu de marée et sort")
    args = ap.parse_args()

    client = Client(use_cache=not args.no_cache)

    if args.search:
        for port in client.search(args.search):
            print(f"{port.id:6d}  {port.label or client.port_name(port)}")
        return 0

    conf = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if not conf.get("ports"):
        raise SystemExit(f"aucun port dans {args.config}")

    print(f"ports ({args.config}) :", file=sys.stderr)
    data = collect(conf, client)

    data_file = HERE / "build" / "data.json"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    typst(data_file, args.output)
    print(f"→ {args.output}", file=sys.stderr)
    if args.open:
        subprocess.run(["open", str(args.output)], check=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ScrapeError, ValueError) as e:
        sys.exit(f"erreur : {e}")
