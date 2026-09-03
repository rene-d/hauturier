from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

import dcc
from dcc import Competitor, Fix

UTC = UTC
NOW = datetime(2026, 9, 2, 14, 30, 0, tzinfo=UTC)


# --- en-tête -------------------------------------------------------------


def test_entete_six_champs_et_point_virgule_final() -> None:
    text = dcc.format_dcc("Pacific Cup", [], generated=NOW)
    head = text.splitlines()[0]
    assert head.endswith(";")
    assert head.count(";") == dcc.DCC_HEADER_FIELDS[dcc.DCC_VERSION]
    assert head.split(";")[2] == "02/09/26"  # JJ/MM/AA (invariant 1)


def test_ligne_concurrent_quatorze_champs() -> None:
    text = dcc.format_dcc(
        "Pacific Cup", [Competitor("Maeva", "SO410", 7, "R. Devichi")], generated=NOW
    )
    line = text.splitlines()[1]
    assert line.count(";") == dcc.DCC_COMPETITOR_FIELDS[dcc.DCC_VERSION]
    fields = line.split(";")[:-1]
    assert tuple(fields[2:5]) == dcc.COMPETITOR_CONST
    assert fields[7] == "7"
    assert fields[11] == "R. Devichi"


def test_fins_de_ligne_lf() -> None:
    """Mesuré sur l'oracle : LF, pas CRLF, avec newline terminal."""
    text = dcc.format_dcc("Pacific Cup", [], generated=NOW)
    assert "\r" not in text
    assert text.endswith("\n")


# --- nom de course -------------------------------------------------------


def test_slash_interdit_dans_le_nom_de_course() -> None:
    with pytest.raises(ValueError, match="chemin"):
        dcc.format_dcc("Route du Rhum 2026/2027", [], generated=NOW)


def test_point_virgule_dans_un_nom_ne_casse_pas_le_decoupage() -> None:
    text = dcc.format_dcc(
        "Pacific Cup", [Competitor("Foo;Bar", "J35", 3, "A;B")], generated=NOW
    )
    line = text.splitlines()[1]
    assert line.count(";") == dcc.DCC_COMPETITOR_FIELDS[dcc.DCC_VERSION]
    assert line.startswith("Foo,Bar;")


# --- posreport -----------------------------------------------------------


def test_posreport_magic_et_cinq_champs() -> None:
    text = dcc.format_posreport([Fix(7, 47.7482, -3.3616, NOW)])
    lines = text.splitlines()
    assert lines[0] == dcc.POSREPORT_MAGIC
    assert lines[1].count(";") == dcc.POSREPORT_FIELDS - 1
    assert not lines[1].endswith(";")  # contrairement au DCC (mesuré)


def test_horodatage_mm_jj_aa_et_utc() -> None:
    """Asymétrie assumée avec l'en-tête DCC (invariant 1)."""
    paris = timezone(timedelta(hours=2))
    fix = Fix(7, 47.7482, -3.3616, datetime(2026, 9, 2, 16, 30, tzinfo=paris))
    line = dcc.format_posreport([fix]).splitlines()[1]
    assert line.endswith("09/02/26 14:30:00")


def test_plusieurs_positions_par_bateau() -> None:
    """Une trace = N lignes pour un même ID, chacune horodatée.

    L'oracle YB n'en contient qu'une par bateau, mais rien dans le format ne
    l'impose et c'est ainsi qu'une trace se transmet en un seul fichier.
    """
    trace = [
        Fix(7, 47.7, -3.3, NOW),
        Fix(7, 47.8, -3.4, NOW + timedelta(minutes=1)),
        Fix(8, 47.9, -3.5, NOW),
    ]
    lignes = dcc.format_posreport(trace).splitlines()
    assert len(lignes) == 4
    assert [ligne.split(";")[1] for ligne in lignes[1:]] == ["7", "7", "8"]
    assert dcc.parse_posreport("\n".join(lignes) + "\n") == trace


# --- modèle -------------------------------------------------------------


def test_horodatage_naif_refuse() -> None:
    with pytest.raises(ValueError, match="naïf"):
        Fix(7, 47.7482, -3.3616, datetime(2026, 9, 2, 14, 30))


@pytest.mark.parametrize("lat,lon", [(91.0, 0.0), (0.0, -181.0)])
def test_fix_valide_ses_bornes(lat: float, lon: float) -> None:
    with pytest.raises(ValueError, match="hors bornes"):
        Fix(7, lat, lon, NOW)


def test_donnees_meteo_jetees() -> None:
    """Le posreport ne transporte que position + heure."""
    assert set(Fix.__slots__) == {"ident", "lat", "lon", "at"}


# --- écriture ------------------------------------------------------------


def test_ecriture_iso8859_1(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "x.dcc"
    dcc.write_latin1(path, dcc.format_dcc("Coupe été", [], generated=NOW))
    raw = path.read_bytes()
    assert "été".encode("iso-8859-1") in raw
    assert "été".encode("utf-8") not in raw  # noqa: UP012 — explicite exprès
