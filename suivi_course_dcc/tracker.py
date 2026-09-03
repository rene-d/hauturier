"""Accès au tracker PredictWind de The Ocean Race — seul point réseau du projet.

Relevé le 2026-09-02 par lecture du bundle du tracker. Rien n'est deviné ici :
tout ce qui suit a été observé sur le réseau (voir `tests/fixtures/`).

La page https://www.theoceanrace.com/fr/atlantic/2026/tracker n'expose aucune
donnée : la carte est une iframe vers PredictWind. Deux étapes :

1. ``https://cdn.predictwind.com/ocean-race/?event=atlantic``
   Le HTML porte un ``<div id="inline-data">`` dont les attributs ``data-*``
   sont le bootstrap JSON (lu côté client par ``jQuery.data()``) :

   - ``data-event-config`` : ``{"key", "label", "teamDocType", ...}``
   - ``data-team-info``    : ``{"<nom d'équipe>": {"trackDisplay", "trackId",
     "country", "colour", "media", "updated"}}``

2. ``https://cdn.predictwind.com/tracking/data/<trackDisplay>.json`` ::

     {"route":   [{"t": <epoch s>, "p": {"lat": .., "lon": ..},
                   "bsp": .., "bearing": .., "twd": .., "tws": ..}, ...],
      "updated": <epoch s>, "live": {...}, "images": [...]}

   ``route`` est une liste de points, ou une liste de segments de points : le
   client officiel lui applique ``.flat()`. Les points sont chronologiques,
   espacés d'environ 60 s.

3. Les URL des ressources annexes sont portées par la balise ``<body>``, pas
   par ``#inline-data`` (relevé le 2026-09-03) :

   - ``data-boundaries-json-url`` : ``/ocean-race/atlantic/boundaries.json``,
     ``{"<clé>": {"name", "lat": [...], "lon": [...], "timestamp"}}`` — deux
     tableaux parallèles, **pas** du GeoJSON, polygone laissé **ouvert** ;
   - ``data-whale-sightings-url``, ``data-atlas-metadata-url``,
     ``data-base-projected-route-json-url`` : non exploités ici.

   ``#inline-data`` porte par ailleurs le parcours : ``data-course`` (liste de
   ``{"lat", "lon", "type"}``), ``data-start-line`` et ``data-finish-line``
   (deux points chacun).

Seuls ``t`` et ``p`` sont retenus : le posreport ne transporte que position et
heure. BSP, cap et vent n'y ont aucune destination.

La source ne fournit **ni skipper ni série** — vérifié aussi sur son API de
contenu. Le champ « type » du DCC reçoit donc le pays de l'équipe, faute de
mieux ; `--serie` permet de le forcer.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

CDN = "https://cdn.predictwind.com"
BOOTSTRAP_URL = CDN + "/ocean-race/?event={event}"
TRACK_URL = CDN + "/tracking/data/{track}.json"
DEFAULT_EVENT = "atlantic"
TIMEOUT = 30

# Sans User-Agent, le CDN peut répondre autrement qu'à un navigateur.
_UA = "tor2dcc/1.0 (+https://github.com/; contact: usage personnel)"


@dataclass(frozen=True, slots=True)
class Team:
    name: str
    country: str
    track_display: str  # identifiant du fichier de trace
    track_id: int  # identifiant numérique stable, réutilisé comme ID DCC


@dataclass(frozen=True, slots=True)
class LatLon:
    """Position seule : parcours et zones n'ont pas d'horodatage."""

    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class Zone:
    """Zone d'exclusion. La source laisse le polygone ouvert."""

    key: str
    name: str
    points: list[LatLon]
    at: datetime

    @property
    def closed(self) -> list[LatLon]:
        """Anneau fermé — exigé par KML, implicite dans la source."""
        if self.points[0] == self.points[-1]:
            return self.points
        return [*self.points, self.points[0]]


@dataclass(frozen=True, slots=True)
class Course:
    """Parcours théorique et lignes, tels que publiés par le bootstrap."""

    route: list[LatLon]
    start_line: list[LatLon]
    finish_line: list[LatLon]


@dataclass(frozen=True, slots=True)
class TrackPoint:
    at: datetime
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class FleetEntry:
    """Un bateau et sa trace, dans l'ordre chronologique."""

    team: Team
    points: list[TrackPoint]


class _InlineData(HTMLParser):
    """Attributs de ``#inline-data`` (données) et de ``<body>`` (URL annexes)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attrs: dict[str, str] = {}
        self.body: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {k: v for k, v in attrs if v is not None}
        if found.get("id") == "inline-data":
            self.attrs = found
        elif tag == "body":
            self.body = found


def _parse_html(html: str) -> _InlineData:
    parser = _InlineData()
    parser.feed(html)
    if not parser.attrs:
        raise RuntimeError(
            "élément #inline-data absent : la page du tracker a changé de "
            "structure, relever à nouveau le bootstrap avant de continuer"
        )
    return parser


def _attr(parser: _InlineData, name: str) -> str:
    value = parser.attrs.get(name) or parser.body.get(name)
    if value is None:
        raise RuntimeError(
            f"attribut {name} absent du bootstrap — le schéma a changé, "
            f"le relever à nouveau plutôt que de deviner"
        )
    return value


def _latlons(raw: str, name: str) -> list[LatLon]:
    """Liste de ``{"lat", "lon", ...}``. Un point mal formé est une erreur."""
    points: list[LatLon] = []
    for n, item in enumerate(json.loads(raw)):
        if not isinstance(item, dict) or "lat" not in item or "lon" not in item:
            raise RuntimeError(f"{name}, point {n} inattendu : {item!r}")
        points.append(LatLon(lat=float(item["lat"]), lon=float(item["lon"])))
    if not points:
        raise RuntimeError(f"{name} vide")
    return points


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{url} : HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url} : {exc.reason}") from exc


def parse_bootstrap(html: str) -> tuple[str, list[Team]]:
    """Extrait (nom de course, équipes) du HTML du tracker."""
    parser = _parse_html(html)

    raw_teams = parser.attrs.get("data-team-info")
    raw_config = parser.attrs.get("data-event-config")
    if raw_teams is None or raw_config is None:
        missing = [
            n
            for n, v in (("data-team-info", raw_teams), ("data-event-config", raw_config))
            if v is None
        ]
        raise RuntimeError(f"#inline-data sans {', '.join(missing)}")

    config: dict[str, Any] = json.loads(raw_config)
    label = str(config.get("label") or config.get("key") or "Ocean Race")

    teams: list[Team] = []
    for name, info in json.loads(raw_teams).items():
        track_display = info.get("trackDisplay")
        track_id = info.get("trackId")
        # Ni l'un ni l'autre ne peut manquer en silence : sans trackDisplay il
        # n'y a pas de trace à lire, sans trackId le posreport ne se rattache
        # à rien. Un schéma qui change doit se voir tout de suite.
        if not track_display or track_id in (None, ""):
            raise RuntimeError(
                f"équipe {name!r} sans trackDisplay/trackId "
                f"(clés reçues : {sorted(info)}) — le schéma du bootstrap a "
                f"probablement changé, le relever à nouveau"
            )
        teams.append(
            Team(
                name=str(name),
                country=str(info.get("country") or ""),
                track_display=str(track_display),
                track_id=int(track_id),
            )
        )
    if not teams:
        raise RuntimeError("aucune équipe dans le bootstrap")
    return label, sorted(teams, key=lambda t: t.name)


def parse_track(payload: dict[str, Any]) -> list[TrackPoint]:
    """Aplatit et normalise ``route``. Un point mal formé est une erreur."""
    route = payload.get("route")
    if not isinstance(route, list):
        raise RuntimeError(f"'route' absent ou non listé : {type(route).__name__}")

    flat: list[Any] = []
    for item in route:
        flat.extend(item) if isinstance(item, list) else flat.append(item)

    points: list[TrackPoint] = []
    for n, item in enumerate(flat):
        if not isinstance(item, dict) or "t" not in item or "p" not in item:
            raise RuntimeError(f"point {n} inattendu : {item!r}")
        position = item["p"]
        points.append(
            TrackPoint(
                at=datetime.fromtimestamp(float(item["t"]), UTC),
                lat=float(position["lat"]),
                lon=float(position["lon"]),
            )
        )
    points.sort(key=lambda p: p.at)
    return points


def parse_course(html: str) -> Course:
    """Parcours théorique et lignes de départ/arrivée du bootstrap."""
    parser = _parse_html(html)
    course = Course(
        route=_latlons(_attr(parser, "data-course"), "data-course"),
        start_line=_latlons(_attr(parser, "data-start-line"), "data-start-line"),
        finish_line=_latlons(_attr(parser, "data-finish-line"), "data-finish-line"),
    )
    for name, line in (("départ", course.start_line), ("arrivée", course.finish_line)):
        if len(line) != 2:
            raise RuntimeError(f"ligne d'{name} : {len(line)} point(s), 2 attendus")
    return course


def boundaries_url(html: str) -> str:
    """URL des zones d'exclusion, telle qu'annoncée par la page. Jamais devinée."""
    path = _attr(_parse_html(html), "data-boundaries-json-url")
    return path if path.startswith("http") else CDN + path


def parse_boundaries(payload: dict[str, Any]) -> list[Zone]:
    """``{clé: {name, lat[], lon[], timestamp}}`` -> zones, tri par nom."""
    zones: list[Zone] = []
    for key, item in payload.items():
        lat, lon = item.get("lat"), item.get("lon")
        if not isinstance(lat, list) or not isinstance(lon, list) or len(lat) != len(lon):
            raise RuntimeError(
                f"zone {key!r} : 'lat'/'lon' absents ou de longueurs différentes "
                f"(clés reçues : {sorted(item)}) — schéma changé, le relever"
            )
        if len(lat) < 3:
            raise RuntimeError(f"zone {key!r} : {len(lat)} point(s), polygone impossible")
        # « Exclusion zone: Ice Exclusion Zone » -> « Ice Exclusion Zone ».
        name = str(item["name"]).split(":", 1)[-1].strip()
        zones.append(
            Zone(
                key=str(key),
                name=name,
                points=[
                    LatLon(float(a), float(b)) for a, b in zip(lat, lon, strict=True)
                ],
                at=datetime.fromtimestamp(float(item["timestamp"]), UTC),
            )
        )
    if not zones:
        raise RuntimeError("aucune zone dans boundaries.json")
    return sorted(zones, key=lambda z: z.name)


def fetch_bootstrap(event: str = DEFAULT_EVENT) -> tuple[str, list[Team]]:
    html = _get(BOOTSTRAP_URL.format(event=event)).decode("utf-8", errors="replace")
    return parse_bootstrap(html)


def fetch_track(track_display: str) -> list[TrackPoint]:
    payload = json.loads(_get(TRACK_URL.format(track=track_display)))
    return parse_track(payload)


def fetch_course_and_zones(event: str = DEFAULT_EVENT) -> tuple[Course, list[Zone]]:
    """Parcours, lignes et zones d'exclusion. Deux requêtes, une seule page lue."""
    html = _get(BOOTSTRAP_URL.format(event=event)).decode("utf-8", errors="replace")
    zones = parse_boundaries(json.loads(_get(boundaries_url(html))))
    return parse_course(html), zones


def fetch_fleet(event: str = DEFAULT_EVENT) -> tuple[str, list[FleetEntry]]:
    """Nom de course et trace complète de chaque bateau pisté."""
    race, teams = fetch_bootstrap(event)
    entries: list[FleetEntry] = []
    for team in teams:
        points = fetch_track(team.track_display)
        if not points:
            # Bateau annoncé mais sans trace (pas encore parti, balise muette).
            # On continue sur le reste de la flotte, mais jamais en silence.
            print(
                f"aucun point pour {team.name!r} "
                f"({TRACK_URL.format(track=team.track_display)})",
                file=sys.stderr,
            )
            continue
        entries.append(FleetEntry(team=team, points=points))
    if not entries:
        raise RuntimeError(
            f"{len(teams)} équipe(s) annoncée(s), aucune position exploitable"
        )
    return race, entries
