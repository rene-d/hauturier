#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyais"]
# ///
"""Carte AIS temps réel : collecte le flux de hera.navimetrix.com et le sert sur une carte web.

    ./aismap.py -p "48.7 -4.0" -r 50 --open

Le collecteur (`collect`) est celui de `hera.py` : une connexion TCP à
hera.navimetrix.com:5000 sur laquelle on envoie une ligne
`LAT .. LON .. RADIUS .. AGE ..`, puis un flux NMEA !AIVDM décodé par pyais.
Toute la richesse des messages est conservée telle quelle (`Ship.raw`) et
renvoyée à la page pour l'infobulle détaillée.

Le fond de carte vient des mbtiles hors ligne de Nav&Co
(~/Library/Application Support/com.mfdview.instruments/*.mbtiles), servis en
surimpression d'OpenStreetMap : là où la tuile locale manque, OSM reste visible.

    /                     la page
    /api/status           état de la connexion, réglages, fonds de carte
    /api/ships?since=N    positions (delta depuis la séquence N)
    /api/ship/<mmsi>      tout ce qui a été reçu d'une station + sa trace
    /api/tracks           traces récentes de toutes les stations
    /tiles/{z}/{x}/{y}.png  tuile locale (404 si absente -> OSM apparaît)
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections import deque
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import aisinfo
from pyais.stream import TCPConnection

HOST = "hera.navimetrix.com"
PORT = 5000

STATIC = Path(__file__).resolve().parent / "static"
MBTILES_DIR = Path("~/Library/Application Support/com.mfdview.instruments").expanduser()
VENDOR_CACHE = Path("~/.cache/aismap/vendor").expanduser()
VENDOR_URL = "https://unpkg.com/leaflet@1.9.4/dist/"

NM = 1852.0

# PNG 1×1 transparent, renvoyé là où les mbtiles n'ont pas de tuile.
EMPTY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001'0d0a2db40000000049454e44ae426082".replace("'", "")
)

# Champs sans intérêt pour l'affichage (bourrage binaire, entête de transport).
SKIP_FIELDS = {"spare_1", "spare_2", "spare_3", "partno", "dac", "fid"}

# Le message 8 DAC=1 FID=31 (météo) réutilise des noms de champs des autres
# messages (day, hour, minute, lat, lon...) : il est rangé à part.
METEO_TYPE = "MessageType8Dac1Fid31"


# ---------------------------------------------------------------------------
# Géodésie de poche
# ---------------------------------------------------------------------------


def distance_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Distance (m) et relèvement vrai (°) entre deux points, formule de haversine."""
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ, dλ = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    d = 2 * 6371008.8 * math.asin(math.sqrt(a))
    y = math.sin(dλ) * math.cos(φ2)
    x = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(dλ)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


# Valeurs « non disponible » des messages de position (ITU-R M.1371) : elles ne
# doivent pas être affichées comme des mesures.
NOT_AVAILABLE = {
    "speed": lambda v: v >= 102.3,
    "course": lambda v: v >= 360,
    "heading": lambda v: v >= 360,
    "turn": lambda v: v is None or abs(v) > 127,
    "draught": lambda v: v <= 0,
    "status": lambda v: v == 15,
}


def available(key: str, value):
    """Renvoie None si la valeur est la sentinelle « non disponible » du champ."""
    if value is None:
        return None
    test = NOT_AVAILABLE.get(key)
    try:
        return None if test and test(value) else value
    except TypeError:
        return value


def jsonable(value):
    """Rend une valeur décodée par pyais sérialisable en JSON."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


# ---------------------------------------------------------------------------
# Modèle
# ---------------------------------------------------------------------------


class Ship:
    """Tout ce qui a été reçu d'un MMSI, fusionné message après message."""

    __slots__ = ("first", "last", "last_pos", "meteo", "mmsi", "msgs", "raw", "seq", "track")

    def __init__(self, mmsi: int):
        self.mmsi = mmsi
        self.raw: dict = {}
        self.meteo: dict = {}
        self.msgs: dict[int, int] = {}
        self.first = self.last = time.time()
        self.last_pos: float | None = None
        self.track: deque[tuple[float, float, float]] = deque(maxlen=600)
        self.seq = 0

    # -- mise à jour ------------------------------------------------------

    def update(self, kind: str, fields: dict, now: float) -> None:
        self.last = now
        msg_type = fields.get("msg_type")
        if msg_type is not None:
            self.msgs[msg_type] = self.msgs.get(msg_type, 0) + 1

        target = self.meteo if kind == METEO_TYPE else self.raw
        for key, value in fields.items():
            if key in SKIP_FIELDS or value is None:
                continue
            value = jsonable(value)
            if value is None:
                continue
            if isinstance(value, str):
                value = value.strip().rstrip("@").strip()
                if not value:
                    continue
            target[key] = value

        if kind == METEO_TYPE:
            return

        lat, lon = fields.get("lat"), fields.get("lon")
        if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180:
            self.last_pos = now
            if not self.track or self._moved(lat, lon, now):
                self.track.append((round(now, 1), lat, lon))

    def _moved(self, lat: float, lon: float, now: float) -> bool:
        t, plat, plon = self.track[-1]
        if now - t > 300:
            return True
        return abs(lat - plat) > 1e-4 or abs(lon - plon) > 1e-4

    # -- lecture ----------------------------------------------------------

    @property
    def lat(self) -> float | None:
        return self.raw.get("lat")

    @property
    def lon(self) -> float | None:
        return self.raw.get("lon")

    @property
    def name(self) -> str:
        return self.raw.get("shipname") or self.raw.get("name") or ""

    def kind(self) -> str:
        """vessel | aton | coast | sar_aircraft | ... , d'après le MMSI et les messages reçus."""
        kind = aisinfo.mmsi_info(self.mmsi)["kind"]
        if kind != "vessel":
            return kind
        if 21 in self.msgs:
            return "aton"
        if 4 in self.msgs and not (self.msgs.keys() & {1, 2, 3, 5, 18, 19, 24}):
            return "coast"
        if 9 in self.msgs:
            return "sar_aircraft"
        return "vessel"

    def summary(self) -> dict:
        """Fiche courte : ce qu'il faut pour dessiner la cible et remplir la liste."""
        raw = self.raw
        code = raw.get("ship_type")
        label, group = aisinfo.ship_type(code)
        kind = self.kind()
        mmsi = aisinfo.mmsi_info(self.mmsi)

        d = {
            "mmsi": self.mmsi,
            "name": self.name,
            "kind": kind,
            "group": group if kind == "vessel" else kind,
            "type": code,
            "type_label": label,
            "country": mmsi["country"],
            "lat": self.lat,
            "lon": self.lon,
            "last": round(self.last, 1),
            "last_pos": round(self.last_pos, 1) if self.last_pos else None,
            "msgs": sum(self.msgs.values()),
            "seq": self.seq,
        }
        for key, out in (
            ("speed", "sog"), ("course", "cog"), ("heading", "hdg"),
            ("turn", "rot"), ("draught", "draught"), ("destination", "dest"),
            ("callsign", "callsign"), ("status", "status"),
        ):
            value = available(key, raw.get(key))
            if value is not None:
                d[out] = value
        if d.get("status") is not None:
            d["status_label"] = aisinfo.NAV_STATUS.get(d["status"], "")
        dims = [raw.get(k) for k in ("to_bow", "to_stern", "to_port", "to_starboard")]
        if any(dims):
            d["dim"] = [x or 0 for x in dims]
        if kind == "aton":
            d["aton"] = raw.get("aid_type")
            d["virtual"] = bool(raw.get("virtual_aid"))
            d["off_position"] = bool(raw.get("off_position"))
        if self.meteo:
            d["meteo"] = True
        return d

    def detail(self) -> dict:
        """Fiche complète : sections lisibles + météo + tous les champs bruts + trace."""
        raw = self.raw
        d = self.summary()
        d["first"] = round(self.first, 1)
        d["msg_types"] = {str(k): v for k, v in sorted(self.msgs.items())}
        d["mmsi_kind"] = aisinfo.mmsi_info(self.mmsi)["kind"]
        d["mid"] = aisinfo.mmsi_info(self.mmsi)["mid"]
        d["raw"] = dict(sorted(raw.items()))
        d["meteo_raw"] = dict(sorted(self.meteo.items()))
        d["meteo_clean"] = aisinfo.meteo_clean(self.meteo)
        d["track"] = [[t, lat, lon] for t, lat, lon in self.track]

        if raw.get("imo"):
            d["imo"] = raw["imo"]
        if raw.get("epfd") is not None:
            d["epfd"] = aisinfo.EPFD.get(raw["epfd"], f"code {raw['epfd']}")
        if raw.get("maneuver") is not None:
            d["maneuver"] = aisinfo.MANEUVER.get(raw["maneuver"], "")
        if raw.get("aid_type") is not None:
            d["aton_label"] = aisinfo.NAVAID.get(raw["aid_type"], f"code {raw['aid_type']}")
        if raw.get("accuracy") is not None:
            d["accuracy"] = bool(raw["accuracy"])
        if raw.get("raim") is not None:
            d["raim"] = bool(raw["raim"])
        # ETA du message 5 : mois/jour/heure/minute, 0 ou 24/60 = non renseigné.
        month, day = raw.get("month"), raw.get("day")
        hour, minute = raw.get("hour"), raw.get("minute")
        if month and day:
            eta = f"{day:02d}/{month:02d}"
            if hour is not None and hour < 24:
                eta += f" {hour:02d}:{minute or 0:02d}"
            d["eta"] = eta
        return d


class Fleet:
    """Le magasin, protégé par un verrou : le collecteur écrit, le serveur lit."""

    def __init__(self, max_age: float):
        self.lock = threading.Lock()
        self.ships: dict[int, Ship] = {}
        self.max_age = max_age
        self.seq = 0
        self.messages = 0
        self.rate = deque(maxlen=64)
        self.connected = False
        self.error = ""
        self.started = time.time()

    def update(self, message) -> None:
        fields = message.asdict()
        mmsi = fields.get("mmsi")
        if mmsi is None:
            return
        try:
            mmsi = int(mmsi)
        except (TypeError, ValueError):
            return

        now = time.time()
        with self.lock:
            self.messages += 1
            self.rate.append(now)
            ship = self.ships.get(mmsi)
            if ship is None:
                ship = self.ships[mmsi] = Ship(mmsi)
            self.seq += 1
            ship.seq = self.seq
            ship.update(type(message).__name__, fields, now)

    def purge(self) -> None:
        limit = time.time() - self.max_age
        with self.lock:
            for mmsi in [m for m, s in self.ships.items() if s.last < limit]:
                del self.ships[mmsi]

    def msg_rate(self) -> float:
        if len(self.rate) < 2:
            return 0.0
        span = self.rate[-1] - self.rate[0]
        return (len(self.rate) - 1) / span if span > 0 else 0.0


# ---------------------------------------------------------------------------
# Collecteur
# ---------------------------------------------------------------------------


def collect(fleet: Fleet, lat: float, lon: float, radius: float, age: float, log: Path | None) -> None:
    """Boucle de connexion au serveur AIS, avec reprise après coupure."""
    request = f"LAT {lat:.4f} LON {lon:.4f} RADIUS {radius:.1f} AGE {age:.0f}\n".encode()
    stream = open(log, "at", buffering=1) if log else None  # noqa: SIM115 - ouvert pour la durée du programme
    delay = 2.0

    while True:
        try:
            conn = TCPConnection(HOST, port=PORT)
            conn._fobj.settimeout(60)
            conn._fobj.send(request)
            fleet.connected, fleet.error = True, ""
            delay = 2.0
            print(f"connecté à {HOST}:{PORT} — {request.decode().strip()}", file=sys.stderr)

            for sentence in conn:
                try:
                    message = sentence.decode()
                except Exception:  # noqa: BLE001,S112 - une trame abîmée ne doit pas couper le flux
                    continue
                if stream:
                    print(message, file=stream)
                fleet.update(message)

        except Exception as e:  # noqa: BLE001 - le flux ne doit jamais tuer le serveur
            fleet.error = f"{type(e).__name__}: {e}"

        fleet.connected = False
        print(f"déconnecté ({fleet.error or 'flux terminé'}), reprise dans {delay:.0f} s", file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 60)


def housekeeping(fleet: Fleet, state: Path | None) -> None:
    """Purge des cibles trop vieilles et sauvegarde périodique de l'état."""
    while True:
        time.sleep(30)
        fleet.purge()
        if state:
            save_state(fleet, state)


def save_state(fleet: Fleet, path: Path) -> None:
    with fleet.lock:
        data = {
            str(s.mmsi): {
                "raw": s.raw, "meteo": s.meteo,
                "msgs": s.msgs, "first": s.first, "last": s.last,
                "last_pos": s.last_pos, "track": list(s.track)[-120:],
            }
            for s in fleet.ships.values()
        }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def load_state(fleet: Fleet, path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    limit = time.time() - fleet.max_age
    for mmsi, d in data.items():
        if not isinstance(d, dict) or d.get("last", 0) < limit:
            continue
        ship = Ship(int(mmsi))
        ship.raw = d.get("raw", {})
        ship.meteo = d.get("meteo", {})
        ship.msgs = {int(k): v for k, v in d.get("msgs", {}).items()}
        ship.first, ship.last = d.get("first", 0), d.get("last", 0)
        ship.last_pos = d.get("last_pos")
        ship.track.extend(tuple(p) for p in d.get("track", []))
        # Une séquence non nulle, sinon `since=0` les filtrerait à la première
        # requête et la carte s'ouvrirait vide.
        fleet.seq += 1
        ship.seq = fleet.seq
        fleet.ships[ship.mmsi] = ship
    return len(fleet.ships)


# ---------------------------------------------------------------------------
# Tuiles
# ---------------------------------------------------------------------------


class Tiles:
    """Lecture des mbtiles (schéma TMS : la ligne y est inversée)."""

    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.local = threading.local()
        self.meta = []
        for path in paths:
            db = sqlite3.connect(path)
            meta = dict(db.execute("SELECT name, value FROM metadata").fetchall())
            db.close()
            self.meta.append({
                "file": path.name,
                "name": meta.get("name", path.stem),
                "description": meta.get("description", ""),
                "minzoom": int(meta.get("minzoom", 0)),
                "maxzoom": int(meta.get("maxzoom", 18)),
                "bounds": meta.get("bounds", ""),
                "attribution": meta.get("attribution", ""),
                "format": meta.get("format", "png"),
            })

    def _connections(self) -> list[sqlite3.Connection]:
        conns = getattr(self.local, "conns", None)
        if conns is None:
            conns = self.local.conns = [
                sqlite3.connect(f"file:{p}?mode=ro", uri=True) for p in self.paths
            ]
        return conns

    def get(self, z: int, x: int, y: int) -> bytes | None:
        row = (1 << z) - 1 - y
        for db in self._connections():
            hit = db.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                (z, x, row),
            ).fetchone()
            if hit:
                return hit[0]
        return None


# ---------------------------------------------------------------------------
# Serveur HTTP
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    server_version = "aismap"
    protocol_version = "HTTP/1.1"

    fleet: Fleet
    tiles: Tiles
    config: dict
    verbose = False

    def log_message(self, fmt, *args):
        if self.verbose:
            super().log_message(fmt, *args)

    # -- utilitaires ------------------------------------------------------

    def send(self, body: bytes, ctype: str, cache: str = "no-store", code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, data) -> None:
        self.send(json.dumps(data, allow_nan=False).encode(), "application/json")

    def not_found(self) -> None:
        self.send(b"not found", "text/plain; charset=utf-8", code=404)

    # -- routage ----------------------------------------------------------

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        args = dict(kv.split("=", 1) for kv in query.split("&") if "=" in kv)
        parts = [p for p in path.split("/") if p]

        try:
            if path == "/":
                return self.static("index.html")
            if parts and parts[0] == "static":
                return self.static("/".join(parts[1:]))
            if parts and parts[0] == "vendor":
                return self.vendor("/".join(parts[1:]))
            if parts[:1] == ["tiles"] and len(parts) == 4:
                return self.tile(parts[1:])
            if path == "/api/status":
                return self.api_status()
            if path == "/api/ships":
                return self.api_ships(args)
            if path == "/api/tracks":
                return self.api_tracks(args)
            if parts[:2] == ["api", "ship"] and len(parts) == 3:
                return self.api_ship(parts[2])
        except BrokenPipeError:
            return
        self.not_found()

    do_HEAD = do_GET

    # -- fichiers ---------------------------------------------------------

    def static(self, name: str) -> None:
        path = (STATIC / name).resolve()
        if not path.is_file() or STATIC not in path.parents:
            return self.not_found()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
            ctype += "; charset=utf-8"
        self.send(path.read_bytes(), ctype)

    def vendor(self, name: str) -> None:
        """Leaflet, mis en cache sur disque au premier appel pour marcher hors ligne."""
        if ".." in name or name.startswith("/"):
            return self.not_found()
        path = VENDOR_CACHE / name
        if not path.is_file():
            try:
                with urllib.request.urlopen(VENDOR_URL + name, timeout=10) as r:
                    data = r.read()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            except (urllib.error.URLError, OSError, TimeoutError):
                self.send_response(302)
                self.send_header("Location", VENDOR_URL + name)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.send(path.read_bytes(), ctype, cache="max-age=86400")

    def tile(self, zxy: list[str]) -> None:
        try:
            z, x, y = int(zxy[0]), int(zxy[1]), int(zxy[2].split(".")[0])
        except ValueError:
            return self.not_found()
        data = self.tiles.get(z, x, y) or EMPTY_PNG
        self.send(data, "image/png", cache="max-age=86400")

    # -- API --------------------------------------------------------------

    def api_status(self) -> None:
        fleet = self.fleet
        with fleet.lock:
            total = len(fleet.ships)
            positioned = sum(1 for s in fleet.ships.values() if s.lat is not None)
        self.send_json({
            "connected": fleet.connected,
            "error": fleet.error,
            "source": f"{HOST}:{PORT}",
            "messages": fleet.messages,
            "rate": round(fleet.msg_rate(), 1),
            "ships": total,
            "positioned": positioned,
            "uptime": round(time.time() - fleet.started),
            "now": time.time(),
            "charts": self.tiles.meta,
            **self.config,
        })

    def _visible(self, args: dict) -> tuple[float, bool]:
        radius = float(args.get("radius", self.config["radius"])) * NM
        return radius, args.get("all") == "1"

    def api_ships(self, args: dict) -> None:
        since = int(args.get("since", 0))
        radius, show_all = self._visible(args)
        ref = self.config["ref"]
        limit = time.time() - self.fleet.max_age

        ships = []
        with self.fleet.lock:
            seq = self.fleet.seq
            for ship in self.fleet.ships.values():
                if ship.seq <= since or ship.last < limit:
                    continue
                summary = ship.summary()
                if summary["lat"] is not None:
                    dist, brg = distance_bearing(ref[0], ref[1], summary["lat"], summary["lon"])
                    if not show_all and dist > radius:
                        continue
                    summary["dist"] = round(dist / NM, 2)
                    summary["brg"] = round(brg)
                elif not show_all:
                    continue
                ships.append(summary)
        self.send_json({"seq": seq, "now": time.time(), "full": since == 0, "ships": ships})

    def api_ship(self, mmsi: str) -> None:
        try:
            key = int(mmsi)
        except ValueError:
            return self.not_found()
        with self.fleet.lock:
            ship = self.fleet.ships.get(key)
            detail = ship.detail() if ship else None
        if detail is None:
            return self.not_found()
        ref = self.config["ref"]
        if detail["lat"] is not None:
            dist, brg = distance_bearing(ref[0], ref[1], detail["lat"], detail["lon"])
            detail["dist"], detail["brg"] = round(dist / NM, 2), round(brg)
        self.send_json(detail)

    def api_tracks(self, args: dict) -> None:
        radius, show_all = self._visible(args)
        minutes = float(args.get("minutes", 120))
        ref, cutoff = self.config["ref"], time.time() - minutes * 60
        out = {}
        with self.fleet.lock:
            for ship in self.fleet.ships.values():
                if ship.lat is None or len(ship.track) < 2:
                    continue
                dist, _ = distance_bearing(ref[0], ref[1], ship.lat, ship.lon)
                if not show_all and dist > radius:
                    continue
                points = [[round(lat, 5), round(lon, 5)] for t, lat, lon in ship.track if t >= cutoff]
                if len(points) > 1:
                    out[str(ship.mmsi)] = points
        self.send_json(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_position(text: str) -> tuple[float, float]:
    lat, lon = (float(v) for v in text.replace(",", " ").split())
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"position hors limites : {text}")
    return lat, lon


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-p", "--position", default="48.7 -4.0", help="centre de la carte « lat lon »")
    parser.add_argument("-r", "--radius", type=float, default=50.0, help="rayon affiché (NM)")
    parser.add_argument("-a", "--age", type=float, default=60, help="âge maximal demandé au serveur (min)")
    parser.add_argument("-m", "--max-age", type=float, default=60, help="oubli d'une cible sans nouvelle (min)")
    parser.add_argument("--port", type=int, default=8765, help="port d'écoute du serveur web")
    parser.add_argument("--bind", default="127.0.0.1", help="adresse d'écoute")
    parser.add_argument("--state", default="aismap.json", help="fichier d'état (vide pour ne rien garder)")
    parser.add_argument("--log", help="journal des messages décodés")
    parser.add_argument("--mbtiles", help="fichier ou répertoire mbtiles", default=str(MBTILES_DIR))
    parser.add_argument("--no-connect", action="store_true", help="ne pas se connecter (relecture de l'état)")
    parser.add_argument("--open", action="store_true", help="ouvre le navigateur")
    parser.add_argument("-v", "--verbose", action="store_true", help="journalise les requêtes HTTP")
    args = parser.parse_args()

    try:
        lat, lon = parse_position(args.position)
    except ValueError as e:
        parser.error(f"position invalide : {args.position} ({e})")

    mb = Path(args.mbtiles).expanduser()
    paths = sorted(mb.glob("*.mbtiles")) if mb.is_dir() else ([mb] if mb.is_file() else [])
    tiles = Tiles(paths)
    for meta in tiles.meta:
        print(f"fond de carte : {meta['file']} — {meta['description']} (z{meta['minzoom']}-{meta['maxzoom']})", flush=True)
    if not paths:
        print(f"aucun mbtiles dans {mb} — OpenStreetMap seul", file=sys.stderr)

    fleet = Fleet(max_age=args.max_age * 60)
    state = Path(args.state).expanduser() if args.state else None
    if state and load_state(fleet, state):
        print(f"{len(fleet.ships)} cibles relues dans {state}", flush=True)

    Handler.fleet = fleet
    Handler.tiles = tiles
    Handler.verbose = args.verbose
    Handler.config = {
        "ref": [lat, lon],
        "radius": args.radius,
        "age": args.age,
        "max_age": args.max_age * 60,
    }

    if not args.no_connect:
        threading.Thread(
            target=collect,
            args=(fleet, lat, lon, args.radius, args.age, Path(args.log) if args.log else None),
            daemon=True,
        ).start()
    threading.Thread(target=housekeeping, args=(fleet, state), daemon=True).start()

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.daemon_threads = True
    url = f"http://{args.bind}:{args.port}/"
    print(f"carte AIS sur {url}  (Ctrl-C pour arrêter)", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt")
    finally:
        if state:
            save_state(fleet, state)
            print(f"état enregistré dans {state}")


if __name__ == "__main__":
    main()
