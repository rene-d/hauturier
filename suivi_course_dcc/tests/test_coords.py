"""Coordonnées : vérifiées contre des points géographiques connus.

`21.2502N` / `157.4598W` est le mouillage de Kaneohe Bay (Oahu), arrivée de
la Pacific Cup — donc 21° 25,02' N et 157° 45,98' W.
"""

from __future__ import annotations

import pytest

from dcc import format_coord, parse_coord

KANEOHE_LAT = 21 + 25.02 / 60  # 21.4170°N
KANEOHE_LON = -(157 + 45.98 / 60)  # 157.7663°W


def test_parse_point_connu() -> None:
    assert parse_coord("21.2502N") == pytest.approx(KANEOHE_LAT, abs=1e-9)
    assert parse_coord("157.4598W") == pytest.approx(KANEOHE_LON, abs=1e-9)


def test_format_point_connu() -> None:
    assert format_coord(KANEOHE_LAT, "lat") == "21.2502N"
    assert format_coord(KANEOHE_LON, "lon") == "157.4598W"


def test_hemispheres() -> None:
    assert format_coord(-21.417, "lat") == "21.2502S"
    assert format_coord(157.766333, "lon") == "157.4598E"
    assert parse_coord("21.2502S") < 0
    assert parse_coord("157.4598E") > 0


def test_zero_est_nord_et_est() -> None:
    # Convention : 0 est positif, donc N/E. Arbitraire mais déterministe.
    assert format_coord(0.0, "lat") == "00.0000N"
    assert format_coord(0.0, "lon") == "000.0000E"


def test_carry_des_minutes() -> None:
    """59,996' arrondit à 60,00' : le degré doit être incrémenté."""
    value = 21 + 59.996 / 60
    assert format_coord(value, "lat") == "22.0000N"


def test_carry_ne_deborde_pas_des_bornes() -> None:
    assert format_coord(90.0, "lat") == "90.0000N"
    assert format_coord(-180.0, "lon") == "180.0000W"
    with pytest.raises(ValueError):
        format_coord(90.001, "lat")
    with pytest.raises(ValueError):
        format_coord(-180.001, "lon")


def test_padding() -> None:
    """Largeur fixe (hypothèse NMEA) contre largeur libre : non tranché."""
    lorient = -3.36  # 3° 21,60' W : l'arrivée à Lorient discrimine, pas l'oracle
    assert format_coord(lorient, "lon", pad=True) == "003.2160W"
    assert format_coord(lorient, "lon", pad=False) == "3.2160W"
    assert parse_coord("003.2160W") == parse_coord("3.2160W")


def test_resolution() -> None:
    """0,01' ~ 18,5 m : deux points plus proches sont indistinguables."""
    assert format_coord(21.4170, "lat") == format_coord(21.41708, "lat")


@pytest.mark.parametrize("mauvais", ["21.250N", "21.25020N", "21.2502X", "2502N", ""])
def test_parse_refuse_les_formes_inattendues(mauvais: str) -> None:
    with pytest.raises(ValueError):
        parse_coord(mauvais)
