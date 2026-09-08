from __future__ import annotations

import pytest

from dcc import ENCODING, sanitize_field, to_latin1


def test_latin1_conserve_les_accents() -> None:
    # é, ñ, ø, ß sont encodables : aucune translittération.
    for text in ("Éole", "Peñón", "Sør", "Straße"):
        assert to_latin1(text) == text


def test_translitteration_hors_latin1() -> None:
    assert to_latin1("Łukasz") == "Lukasz"
    assert to_latin1("Cœur") == "Coeur"
    assert to_latin1("Tōkyō") == "Tokyo"
    assert to_latin1("l’Hydroptère") == "l'Hydroptère"


def test_jamais_de_point_dinterrogation() -> None:
    assert "?" not in to_latin1("Tōkyō")


def test_residu_non_translitterable_leve() -> None:
    with pytest.raises(ValueError, match="non translittérable"):
        to_latin1("帆船")


def test_point_virgule_devient_virgule() -> None:
    assert sanitize_field("Foo; Bar") == "Foo, Bar"


def test_sauts_de_ligne_ecrases() -> None:
    assert sanitize_field("Foo\r\nBar\tBaz") == "Foo Bar Baz"


def test_sortie_encodable() -> None:
    sanitize_field("Cœur de Lion — Tōkyō").encode(ENCODING)


def test_espaces_internes_preserves() -> None:
    """L'oracle contient `David  Raney` : ne pas normaliser gratuitement."""
    assert sanitize_field("David  Raney") == "David  Raney"


def test_extremites_rognees() -> None:
    assert sanitize_field("  LEON  ") == "LEON"
