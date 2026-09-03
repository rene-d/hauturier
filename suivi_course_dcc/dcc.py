"""Sérialisation DCC (descriptif de course Adrena) et posreport.

Aucun I/O réseau : ce module ne manipule que des `Boat` normalisés.

Le format est de la rétro-ingénierie. Les constantes ci-dessous sont mesurées
sur deux oracles authentiques : `tests/fixtures/paccup2024-*` (YB Tracking,
v1.3, avec son posreport) et `tests/fixtures/capmartinique2026.dcc` (Geovoile,
v1.5). Voir FORMAT-DCC.md.

Ce module **écrit** du 1.3 : c'est la seule version dont on ait un posreport
apparié, donc la seule qu'on sache produire de bout en bout. Il **lit** les
deux, en branchant sur le champ 2.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

ENCODING = "iso-8859-1"

# En lecture seulement. L'oracle Geovoile contient 0x85 (…) et 0x92 (’), qui
# sont des contrôles en ISO-8859-1 : décoder en cp1252, sur-ensemble strict,
# évite de les perdre en silence. On continue d'écrire dans le sous-ensemble
# ISO-8859-1, que les deux producteurs emploient.
READ_ENCODING = "cp1252"

# Mesuré sur l'oracle : LF, pas CRLF (zéro octet 0x0d dans les deux fichiers),
# avec newline terminal. Ne pas « corriger » en CRLF sans nouvelle mesure.
EOL = "\n"

DCC_MAGIC = "Adrena - descriptif des concurrents"
DCC_VERSION = "1.3"

# Valeur écrite par ce module, et celle de l'oracle YB. Ce n'est **pas** une
# constante du format : c'est le champ 6 de l'en-tête qui dit quelle ligne
# magique porte le posreport apparié (Geovoile écrit "POSREPORT").
POSREPORT_MAGIC = "POSADRENA"

# Champs 3-5 des lignes concurrent : constants sur les 64 lignes de l'oracle,
# sémantique inconnue. Recopiés tels quels.
COMPETITOR_CONST = ("1", "3", "1")

# Par version : le champ 2 de l'en-tête branche le lecteur.
DCC_HEADER_FIELDS = {"1.3": 6, "1.5": 14}
DCC_COMPETITOR_FIELDS = {"1.3": 14, "1.5": 24}
# `;` final sur l'en-tête en 1.3, absent en 1.5.
DCC_HEADER_TRAILING = {"1.3": True, "1.5": False}
# Place de l'ID et du skipper : identique dans les deux versions.
FIELD_ID = 7
FIELD_SKIPPER = 11
POSREPORT_FIELDS = 5

Axis = Literal["lat", "lon"]


# --------------------------------------------------------------------------
# Encodage
# --------------------------------------------------------------------------

# Caractères courants hors ISO-8859-1 que NFKD ne décompose pas.
_TRANSLIT = {
    "Œ": "OE",
    "œ": "oe",  # Œ œ
    "Ł": "L",
    "ł": "l",  # Ł ł
    "Đ": "D",
    "đ": "d",  # Đ đ
    "Ħ": "H",
    "ħ": "h",  # Ħ ħ
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    "€": "EUR",
}


def _encodable(text: str) -> bool:
    try:
        text.encode(ENCODING)
    except UnicodeEncodeError:
        return False
    return True


def to_latin1(text: str) -> str:
    """Réduit `text` à un sous-ensemble encodable en ISO-8859-1.

    Les caractères déjà encodables sont conservés (é, ñ, ø, ß…) ; les autres
    sont translittérés — table explicite d'abord, puis NFKD dépouillé de ses
    diacritiques. Un résidu non encodable lève : le format n'a pas de
    caractère de remplacement, et émettre « ? » corromprait un nom de bateau.
    """
    out: list[str] = []
    for ch in text:
        if _encodable(ch):
            out.append(ch)
            continue
        repl = _TRANSLIT.get(ch)
        if repl is None:
            decomposed = unicodedata.normalize("NFKD", ch)
            repl = "".join(c for c in decomposed if not unicodedata.combining(c))
        if not repl or not _encodable(repl):
            raise ValueError(
                f"caractère non translittérable en {ENCODING} : {ch!r} (U+{ord(ch):04X})"
            )
        out.append(repl)
    return "".join(out)


# Whitespace autre que l'espace simple (CR, LF, TAB…) : casse le découpage.
_WHITESPACE = re.compile(r"[^\S ]+")
# Contrôles résiduels, y compris la plage C1 encodable en ISO-8859-1.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_field(text: str) -> str:
    """Rend `text` utilisable comme champ : ni `;`, ni saut de ligne.

    Le `;` est le séparateur et le format n'a pas d'échappement : on le
    remplace par une virgule (invariant 3). Les espaces internes sont
    conservés tels quels — l'oracle contient des doubles espaces
    (`David  Raney`), les écraser ferait diverger le round-trip.
    """
    cleaned = to_latin1(text).replace(";", ",")
    cleaned = _WHITESPACE.sub(" ", cleaned)
    cleaned = _CONTROL.sub("", cleaned)
    return cleaned.strip()


def write_latin1(path: Path, text: str) -> None:
    """Écrit `text` en ISO-8859-1 strict. Toute perte est une erreur."""
    path.write_bytes(text.encode(ENCODING, errors="strict"))


# --------------------------------------------------------------------------
# Coordonnées : degrés + minutes décimales concaténés, hémisphère suffixé
# --------------------------------------------------------------------------

_COORD_RE = re.compile(r"\A(\d{1,3})\.(\d{2})(\d{2})([NSEW])\Z")

_HEMIS = {"lat": ("N", "S"), "lon": ("E", "W")}
_LIMIT = {"lat": 90, "lon": 180}
_DEG_WIDTH = {"lat": 2, "lon": 3}


def format_coord(value: float, axis: Axis, *, pad: bool = True) -> str:
    """`21.4170`, 'lat' -> `21.2502N` (21° 25,02' N).

    `pad` : zéro-padding des degrés sur 2 (lat) / 3 (lon) chiffres. L'oracle
    ne contient aucune valeur discriminante (lat >= 21, lon >= 122) ; le
    défaut suit l'hypothèse NMEA et reste à trancher dans qtVlm.
    """
    if axis not in _HEMIS:
        raise ValueError(f"axe inconnu : {axis!r}")
    limit = _LIMIT[axis]
    if not -limit <= value <= limit:
        raise ValueError(f"{axis} hors bornes : {value!r}")

    positive, negative = _HEMIS[axis]
    hemis = positive if value >= 0 else negative

    magnitude = Decimal(str(abs(value)))
    degrees = int(magnitude)
    minutes = (magnitude - degrees) * 60
    minutes = minutes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Carry : 59,996' arrondi à 60,00' appartient au degré suivant.
    if minutes >= 60:
        degrees += 1
        minutes = Decimal("0.00")
    if degrees > limit:
        raise ValueError(f"{axis} hors bornes après arrondi : {value!r}")

    deg_text = f"{degrees:0{_DEG_WIDTH[axis]}d}" if pad else str(degrees)
    min_text = format(minutes, "05.2f").replace(".", "")
    return f"{deg_text}.{min_text}{hemis}"


def parse_coord(text: str) -> float:
    """`21.2502N` -> 21.417 (degrés décimaux signés)."""
    match = _COORD_RE.match(text)
    if match is None:
        raise ValueError(f"coordonnée illisible : {text!r}")
    degrees, whole_min, hundredths, hemis = match.groups()
    minutes = Decimal(whole_min) + Decimal(hundredths) / 100
    value = Decimal(degrees) + minutes / 60
    if hemis in ("S", "W"):
        value = -value
    return float(value)


# --------------------------------------------------------------------------
# Modèle
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Competitor:
    """Une ligne du DCC."""

    name: str
    kind: str
    ident: int
    skipper: str


@dataclass(frozen=True, slots=True)
class Fix:
    """Une ligne du posreport : un bateau, une position, un instant."""

    ident: int
    lat: float  # degrés décimaux signés, + = Nord
    lon: float  # degrés décimaux signés, + = Est
    at: datetime  # timezone-aware

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90:
            raise ValueError(f"latitude hors bornes : {self.lat!r}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"longitude hors bornes : {self.lon!r}")
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError(f"horodatage naïf pour l'ID {self.ident} : {self.at!r}")


@dataclass(frozen=True, slots=True)
class DccHeader:
    version: str  # "1.3" ou "1.5" : branche la lecture des lignes concurrent
    generated: str  # JJ/MM/AA en 1.3, JJ/MM/AAAA en 1.5 : conservé brut
    race: str
    unknown: str
    posreport_magic: str  # ligne magique attendue en tête du posreport apparié
    url: str = ""  # champ 14, v1.5 seulement : où le logiciel va chercher les positions


# --------------------------------------------------------------------------
# DCC
# --------------------------------------------------------------------------


def check_race_name(race: str) -> str:
    """Le nom de course sert de nom de fichier côté qtVlm (invariant 4)."""
    cleaned = sanitize_field(race)
    if not cleaned:
        raise ValueError("nom de course vide")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"nom de course contenant un séparateur de chemin : {race!r}")
    return cleaned


def format_dcc(
    race: str, competitors: Sequence[Competitor], *, generated: datetime
) -> str:
    """DCC complet. `generated` est daté en JJ/MM/AA (invariant 1)."""
    header = ";".join(
        (
            DCC_MAGIC,
            DCC_VERSION,
            f"{generated:%d/%m/%y}",
            check_race_name(race),
            "0",
            POSREPORT_MAGIC,
        )
    )
    lines = [header + ";"]
    for c in competitors:
        fields = (
            sanitize_field(c.name),
            sanitize_field(c.kind),
            *COMPETITOR_CONST,
            "",
            "",
            str(c.ident),
            "",
            "",
            "",
            sanitize_field(c.skipper),
            "",
            "",
        )
        attendu = DCC_COMPETITOR_FIELDS[DCC_VERSION]
        if len(fields) != attendu:
            raise AssertionError(f"{len(fields)} champs au lieu de {attendu}")
        lines.append(";".join(fields) + ";")
    return EOL.join(lines) + EOL


def parse_dcc(text: str) -> tuple[DccHeader, list[Competitor]]:
    """Parseur strict, 1.3 et 1.5 : une ligne inattendue lève.

    Le branchement se fait sur le champ 2, comme le veut le format : les deux
    versions n'ont ni le même nombre de champs, ni le même `;` final sur
    l'en-tête. L'ID (champ 8) et le skipper (champ 12) sont à la même place
    dans les deux — mesuré sur les deux oracles.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("DCC vide")

    head = lines[0].split(";")
    if head[0] != DCC_MAGIC:
        raise ValueError(f"magic DCC inattendu : {head[0]!r}")
    version = head[1] if len(head) > 1 else ""
    if version not in DCC_HEADER_FIELDS:
        raise ValueError(
            f"version DCC {version!r} inconnue "
            f"(connues : {', '.join(sorted(DCC_HEADER_FIELDS))})"
        )

    if DCC_HEADER_TRAILING[version]:
        if head[-1] != "":
            raise ValueError(f"en-tête DCC {version} sans `;` final")
        head = head[:-1]
    elif head[-1] == "":
        raise ValueError(f"en-tête DCC {version} avec un `;` final inattendu")
    attendu = DCC_HEADER_FIELDS[version]
    if len(head) != attendu:
        raise ValueError(
            f"en-tête DCC {version} : {len(head)} champs au lieu de {attendu}"
        )

    header = DccHeader(
        version=version,
        generated=head[2],
        race=head[3],
        unknown=head[4],
        posreport_magic=head[5],
        url=head[13] if version == "1.5" else "",
    )

    attendu = DCC_COMPETITOR_FIELDS[version]
    competitors: list[Competitor] = []
    for n, line in enumerate(lines[1:], start=2):
        fields = line.split(";")
        if fields[-1] != "":
            raise ValueError(f"ligne {n} : pas de `;` final")
        fields = fields[:-1]
        if len(fields) != attendu:
            raise ValueError(f"ligne {n} : {len(fields)} champs au lieu de {attendu}")
        # Les champs 3-5 ne valent `1;3;1` qu'en 1.3 : en 1.5 les places 4 et 5
        # portent des dimensions.
        if version == "1.3" and tuple(fields[2:5]) != COMPETITOR_CONST:
            raise ValueError(
                f"ligne {n} : champs 3-5 = {fields[2:5]}, "
                f"attendu {list(COMPETITOR_CONST)}"
            )
        competitors.append(
            Competitor(
                name=fields[0],
                kind=fields[1],
                ident=int(fields[FIELD_ID]),
                skipper=fields[FIELD_SKIPPER],
            )
        )
    return header, competitors


# --------------------------------------------------------------------------
# Posreport
# --------------------------------------------------------------------------


def format_posreport(fixes: Sequence[Fix], *, pad: bool = True) -> str:
    """Posreport complet.

    Les horodatages sont convertis en UTC (hypothèse : le fuseau attendu par
    qtVlm est UTC — non confirmé, cf. CLAUDE.md) et écrits en MM/JJ/AA.
    Contrairement au DCC, ces lignes n'ont pas de `;` final (mesuré).
    """
    lines = [POSREPORT_MAGIC]
    for fix in fixes:
        stamp = fix.at.astimezone(UTC)
        lines.append(
            ";".join(
                (
                    "1",
                    str(fix.ident),
                    format_coord(fix.lat, "lat", pad=pad),
                    format_coord(fix.lon, "lon", pad=pad),
                    f"{stamp:%m/%d/%y %H:%M:%S}",
                )
            )
        )
    return EOL.join(lines) + EOL


def parse_posreport(text: str, *, magic: str = POSREPORT_MAGIC) -> list[Fix]:
    """`magic` : la ligne magique attendue, celle du champ 6 du `.dcc` apparié.

    Ce n'est pas une constante du format — Geovoile écrit `POSREPORT` là où YB
    Tracking écrit `POSADRENA`.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or lines[0] != magic:
        lu = repr(lines[0]) if lines else "un fichier vide"
        raise ValueError(f"magic posreport attendu {magic!r}, lu {lu}")

    fixes: list[Fix] = []
    for n, line in enumerate(lines[1:], start=2):
        fields = line.split(";")
        if len(fields) != POSREPORT_FIELDS:
            raise ValueError(
                f"ligne {n} : {len(fields)} champs au lieu de {POSREPORT_FIELDS}"
            )
        if fields[0] != "1":
            raise ValueError(f"ligne {n} : type d'enregistrement {fields[0]!r} inconnu")
        at = datetime.strptime(fields[4], "%m/%d/%y %H:%M:%S").replace(tzinfo=UTC)
        fixes.append(
            Fix(
                ident=int(fields[1]),
                lat=parse_coord(fields[2]),
                lon=parse_coord(fields[3]),
                at=at,
            )
        )
    return fixes
