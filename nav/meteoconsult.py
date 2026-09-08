#!/usr/bin/env python3
"""Lecture des horaires de marée sur marine.meteoconsult.fr.

Le site publie une page HTML par port et par mois :

    https://marine.meteoconsult.fr/meteo-marine/horaires-des-marees/<slug>-<id>/<mois>-<annee>

Chaque journée y est un bloc `div.tide` contenant :
  - `div.tide-line` : un demi-cycle (une BM et/ou une PM) et son coefficient,
  - `div.ephemeris` : lever/coucher du soleil et phase de lune.

Les heures sont données dans le fuseau du port — heure légale française pour la
métropole, britannique pour Portsmouth ou Jersey — et le décalage avec UTC est
recalculé ici pour chaque horaire. Le pays et les coordonnées figurent dans la page,
ce qui permet de déduire le fuseau sans le demander à l'utilisateur.
"""

from __future__ import annotations

import html
import json
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from lxml import html as lxml_html

from lune import illumination, waxing

BASE = "https://marine.meteoconsult.fr"
PARIS = ZoneInfo("Europe/Paris")

# Le site publie chaque port à son heure locale. Il donne le pays dans la page, d'où
# se déduit le fuseau ; les rares pays à plusieurs fuseaux sont départagés par la
# longitude (cf. `timezone_of`).
COUNTRY_TZ = {
    "france": "Europe/Paris",
    "royaume-uni": "Europe/London",
    "irlande": "Europe/Dublin",
    "belgique": "Europe/Brussels",
    "pays-bas": "Europe/Amsterdam",
    "allemagne": "Europe/Berlin",
    "danemark": "Europe/Copenhagen",
    "norvege": "Europe/Oslo",
    "suede": "Europe/Stockholm",
    "finlande": "Europe/Helsinki",
    "islande": "Atlantic/Reykjavik",
    "espagne": "Europe/Madrid",
    "portugal": "Europe/Lisbon",
    "italie": "Europe/Rome",
    "malte": "Europe/Malta",
    "grece": "Europe/Athens",
    "croatie": "Europe/Zagreb",
    "maroc": "Africa/Casablanca",
    "tunisie": "Africa/Tunis",
}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

MOIS = [
    "janvier", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
]

# nom d'icône du site -> (nom de phase normalisé, libellé)
MOON_PHASES = {
    "newMoon": ("new", "nouvelle lune"),
    "waxingCrescent": ("waxing-crescent", "premier croissant"),
    "firstQuarter": ("first-quarter", "premier quartier"),
    "waxingGibbous": ("waxing-gibbous", "gibbeuse croissante"),
    "fullMoon": ("full", "pleine lune"),
    "waningGibbous": ("waning-gibbous", "gibbeuse décroissante"),
    "lastQuarter": ("last-quarter", "dernier quartier"),
    "waningCrescent": ("waning-crescent", "dernier croissant"),
}


class ScrapeError(RuntimeError):
    pass


@dataclass
class Tide:
    """Une pleine ou basse mer."""

    kind: str  # "PM" ou "BM"
    hour: str  # "08h11" -> "08:11"
    height: str | None  # hauteur en mètres, "6.80"
    coef: int | None  # coefficient, seulement sur les PM
    utc: str | None  # décalage horaire de `hour`, "+1" ou "+2"


@dataclass
class Day:
    date: str  # ISO
    tides: list[Tide] = field(default_factory=list)
    sunrise: str | None = None
    sunrise_utc: str | None = None
    sunset: str | None = None
    sunset_utc: str | None = None
    moon: str | None = None  # phase de lune, cf. MOON_PHASES
    moon_label: str | None = None
    moon_pct: int | None = None  # fraction éclairée du disque, en %
    moon_waxing: bool | None = None  # True si croissante, False si décroissante


@dataclass
class Port:
    id: int
    slug: str
    label: str = ""
    country: str = ""
    tz: str = ""       # fuseau déduit du pays ; le YAML peut le surcharger


def timezone_of(country: str, longitude: float | None) -> str | None:
    """Fuseau d'un port d'après son pays, la longitude départageant les archipels."""
    key = slugify(country)
    if key == "espagne" and longitude is not None and longitude < -11:
        return "Atlantic/Canary"
    if key == "portugal" and longitude is not None:
        if longitude < -20:
            return "Atlantic/Azores"
        if longitude < -14:
            return "Atlantic/Madeira"
    return COUNTRY_TZ.get(key)


def page_location(page: str) -> tuple[str, float | None]:
    """Pays et longitude annoncés par une page de marées."""
    country = ""
    for value in re.findall(r"[Pp]ays'\s*:\s*`([^`]*)`", page):
        if value and not value.isdigit():
            country = html.unescape(value)
            break
    m = re.search(r"Longitude\s*:\s*(-?\d+)\s*°", page)
    return country, float(m.group(1)) if m else None


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _port_from_url(url: str) -> Port | None:
    m = re.search(r"horaires-des-marees/([a-z0-9-]+?)-(\d+)(?:/|$)", url)
    return Port(id=int(m.group(2)), slug=m.group(1)) if m else None


class Client:
    """Client HTTP avec cache disque (les pages mensuelles sont stables)."""

    def __init__(self, cache_dir: Path | None = None, use_cache: bool = True, delay: float = 0.5):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.cache_dir = cache_dir or Path(__file__).with_name("cache")
        self.use_cache = use_cache
        self.delay = delay
        self._last_fetch = 0.0

    def get(self, url: str, cache_key: str | None = None) -> str:
        path = None
        if cache_key:
            path = self.cache_dir / f"{cache_key}.html"
            if self.use_cache and path.is_file():
                return path.read_text(encoding="utf-8")

        wait = self.delay - (time.monotonic() - self._last_fetch)
        if wait > 0:
            time.sleep(wait)
        r = self.session.get(url, timeout=30)
        self._last_fetch = time.monotonic()
        if r.status_code != 200:
            raise ScrapeError(f"HTTP {r.status_code} sur {url}")
        r.encoding = "utf-8"

        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(r.text, encoding="utf-8")
        return r.text

    # ------------------------------------------------------------------ ports

    def search(self, query: str) -> list[Port]:
        """Cherche un lieu de marée par son nom.

        Le formulaire de recherche redirige directement (302) vers la page du port
        quand la réponse est unique, et renvoie sinon une liste de résultats.
        """
        url = f"{BASE}/meteo-marine/recherche-horaires-marees"
        r = self.session.get(url, params={"q": query}, timeout=30, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            port = _port_from_url(r.headers["Location"])
            return [port] if port else []
        if r.status_code != 200:
            raise ScrapeError(f"HTTP {r.status_code} sur {url}?q={query}")
        r.encoding = "utf-8"

        doc = lxml_html.fromstring(r.text)
        ports = []
        for a in doc.xpath("//a[.//div[contains(@class,'nameResult')]]"):
            port = _port_from_url(a.get("href", ""))
            if port:
                city = a.xpath(".//div[@class='city']/text()")
                if city:
                    port.label = city[0].strip()
                ports.append(port)
        return ports

    def resolve(self, name: str) -> Port:
        """Nom de port -> page « horaires des marées », avec cache disque."""
        index_file = self.cache_dir / "ports.json"
        index = json.loads(index_file.read_text()) if index_file.is_file() else {}
        key = slugify(name)
        if self.use_cache and key in index:
            port = Port(**index[key])
            if port.tz:            # une entrée de cache antérieure n'a pas le fuseau
                return port
            self.describe(port)
            index[key] = asdict(port)
            index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True))
            return port

        ports = self.search(name)
        if not ports:
            raise ScrapeError(f"lieu de marée introuvable : {name!r}")
        port = ports[0]
        self.describe(port)

        index[key] = asdict(port)
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True))
        return port

    def describe(self, port: Port) -> None:
        """Complète un port : nom affichable, pays, fuseau — lus dans sa page."""
        today = date.today()
        page = self.month_page(port, today.year, today.month, check=False)
        if not port.label:
            m = re.search(r"<title>\s*(.*?)\s+-\s+Horaires des Mar", page)
            port.label = html.unescape(m.group(1)) if m else port.slug.replace("-", " ").title()
        port.country, longitude = page_location(page)
        port.tz = timezone_of(port.country, longitude) or ""

    def port_name(self, port: Port) -> str:
        """Nom affichable du port, lu dans le titre de sa page de marées."""
        copy = Port(id=port.id, slug=port.slug)
        self.describe(copy)
        return copy.label

    # ------------------------------------------------------------------ marées

    def month_page(self, port: Port, year: int, month: int, check: bool = True) -> str:
        """Page mensuelle d'un port.

        Le site ne publie pas les mois écoulés : il sert alors la même période de
        l'année suivante, sans rien signaler. On le détecte sur le titre de la page.
        """
        url = f"{BASE}/meteo-marine/horaires-des-marees/{port.slug}-{port.id}/{MOIS[month - 1]}-{year}"
        key = f"tides/{port.id}-{year}{month:02d}"
        page = self.get(url, cache_key=key)
        if check:
            m = re.search(r"Horaires des Mar\w+\s+(\w+)\s+(\d{4})", page)
            if m and (m.group(1).lower(), int(m.group(2))) != (MOIS[month - 1], year):
                (self.cache_dir / f"{key}.html").unlink(missing_ok=True)
                raise ScrapeError(
                    f"{MOIS[month - 1]} {year} n'est pas publié pour {port.label or port.slug} : "
                    f"le site renvoie {m.group(1)} {m.group(2)} "
                    f"(les mois écoulés ne sont plus disponibles)"
                )
        return page

    def month(self, port: Port, year: int, month: int, tz: ZoneInfo = PARIS) -> dict[str, Day]:
        """Retourne les marées d'un mois, indexées par date ISO."""
        page = self.month_page(port, year, month)
        days = parse_month(page, year, month, tz)
        if not days:
            raise ScrapeError(f"aucune marée trouvée pour {port.label} en {MOIS[month - 1]} {year}")
        return days


def _text(node) -> str:
    return " ".join(node.text_content().split())


def _hour(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s*h\s*(\d{2})", text)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def utc_offset(day: date, hour: str | None, tz: ZoneInfo = PARIS) -> str | None:
    """Décalage avec UTC d'une heure locale : "+2" (CEST), "+1" (CET ou BST), "+0"..."""
    if not hour:
        return None
    h, m = (int(x) for x in hour.split(":"))
    delta = datetime(day.year, day.month, day.day, h, m, tzinfo=tz).utcoffset()
    return f"{delta.total_seconds() / 3600:+g}"


def parse_month(page: str, year: int, month: int, tz: ZoneInfo = PARIS) -> dict[str, Day]:
    doc = lxml_html.fromstring(page)
    days: dict[str, Day] = {}

    blocks = doc.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' tide ')]")
    for block in blocks:
        anchor = block.xpath(".//a[@class='days-anchor']/@id")
        if not anchor:
            continue
        dd, mm = anchor[0].split("-")
        if int(mm) != month:
            continue
        d = date(year, month, int(dd))
        day = Day(date=d.isoformat())

        for line in block.xpath(".//div[@class='tide-line']"):
            coef = line.xpath(".//div[contains(@class,'coef')]//span/text()")
            coef = int(coef[0].strip()) if coef and coef[0].strip().isdigit() else None
            for tide in line.xpath(".//div[@class='low-tide' or @class='high-tide']"):
                hour = _hour(_text(tide.xpath(".//span[@class='hour']")[0]))
                height = tide.xpath(".//span[@class='height']/text()")
                height = f"{float(re.sub(r'[^0-9.]', '', height[0])):.2f}" if height else None
                high = tide.get("class") == "high-tide"
                day.tides.append(
                    Tide(kind="PM" if high else "BM", hour=hour, height=height,
                         coef=coef if high else None, utc=utc_offset(d, hour, tz))
                )

        eph = block.xpath(".//div[contains(@class,'ephemeris')]")
        if eph:
            hours = eph[0].xpath(".//div[contains(@class,'sun')]//div[@class='label']")
            for label in hours:
                txt = _text(label)
                if txt.startswith("Lever"):
                    day.sunrise = _hour(txt)
                    day.sunrise_utc = utc_offset(d, day.sunrise, tz)
                elif txt.startswith("Coucher"):
                    day.sunset = _hour(txt)
                    day.sunset_utc = utc_offset(d, day.sunset, tz)
            icon = eph[0].xpath(".//div[@class='moon-icon']//svg/@class")
            if icon:
                m = re.search(r"icon-(\w+)", icon[0])
                if m and m.group(1) in MOON_PHASES:
                    day.moon, day.moon_label = MOON_PHASES[m.group(1)]
                    noon = datetime(d.year, d.month, d.day, 12, tzinfo=tz)
                    day.moon_pct = round(illumination(noon) * 100)
                    day.moon_waxing = waxing(noon)

        days[day.date] = day

    return days


if __name__ == "__main__":  # petit utilitaire de mise au point
    import sys

    c = Client()
    for name in sys.argv[1:] or ["Brest"]:
        p = c.resolve(name)
        print(f"{p.label} -> id={p.id} slug={p.slug}")
        today = date.today()
        for d in list(c.month(p, today.year, today.month).values())[:3]:
            print(" ", json.dumps(asdict(d), ensure_ascii=False))
