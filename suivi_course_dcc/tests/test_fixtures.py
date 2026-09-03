"""Round-trip contre les oracles authentiques.

- `paccup2024-*` (YB Tracking) : v1.3, avec son posreport apparié. Si le
  parseur les relit et le sérialiseur les reproduit octet pour octet, le
  format est reproduit ; sinon c'est notre code qui a tort, pas l'oracle.
- `capmartinique2026.dcc` (Geovoile) : v1.5, lecture seule — on ne sait pas
  produire cette version, faute de posreport apparié observable.
"""

from __future__ import annotations

from datetime import datetime

import dcc
from conftest import FIXTURES


def test_dcc_relu_sans_perte(oracle_dcc: str) -> None:
    header, competitors = dcc.parse_dcc(oracle_dcc)
    assert header.version == dcc.DCC_VERSION
    assert header.posreport_magic == dcc.POSREPORT_MAGIC
    assert header.unknown == "0"
    assert len(competitors) == 64
    assert len({c.ident for c in competitors}) == 64


def test_dcc_round_trip_octet_pour_octet(oracle_dcc: str) -> None:
    header, competitors = dcc.parse_dcc(oracle_dcc)
    generated = datetime.strptime(header.generated, "%d/%m/%y")  # JJ/MM/AA
    rebuilt = dcc.format_dcc(header.race, competitors, generated=generated)
    assert rebuilt == oracle_dcc


def test_posreport_relu_sans_perte(oracle_posreport: str) -> None:
    fixes = dcc.parse_posreport(oracle_posreport)
    assert len(fixes) == 64
    assert all(f.at.tzinfo is not None for f in fixes)


def test_posreport_round_trip_octet_pour_octet(oracle_posreport: str) -> None:
    fixes = dcc.parse_posreport(oracle_posreport)
    assert dcc.format_posreport(fixes, pad=True) == oracle_posreport


def test_jointure_dcc_posreport(oracle_dcc: str, oracle_posreport: str) -> None:
    """Le posreport ne porte que des IDs : sans le DCC, il est orphelin."""
    _, competitors = dcc.parse_dcc(oracle_dcc)
    fixes = dcc.parse_posreport(oracle_posreport)
    assert {c.ident for c in competitors} == {f.ident for f in fixes}


def test_oracle_est_ascii_donc_ne_prouve_rien_sur_lencodage(oracle_dcc: str) -> None:
    """L'hypothèse ISO-8859-1 n'est pas testée par l'oracle : il est ASCII."""
    assert oracle_dcc.isascii()


# --------------------------------------------------------------------------
# Oracle v1.5 : Geovoile, Cap Martinique 2026
# --------------------------------------------------------------------------


def test_oracle_15_se_lit(oracle_dcc_15: str) -> None:
    header, competitors = dcc.parse_dcc(oracle_dcc_15)
    assert header.version == "1.5"
    assert header.race == "cap martinique"
    assert len(competitors) == 45


def test_le_magic_du_posreport_nest_pas_une_constante(oracle_dcc_15: str) -> None:
    """Geovoile écrit POSREPORT là où YB Tracking écrit POSADRENA."""
    header, _ = dcc.parse_dcc(oracle_dcc_15)
    assert header.posreport_magic == "POSREPORT"
    assert header.posreport_magic != dcc.POSREPORT_MAGIC


def test_url_de_mise_a_jour_en_15(oracle_dcc_15: str) -> None:
    header, _ = dcc.parse_dcc(oracle_dcc_15)
    assert header.url.startswith("https://www.geovoile.net/capmartinique/")


def test_champ_12_est_le_skipper(oracle_dcc_15: str) -> None:
    """Même place qu'en 1.3 — et non le nom du bateau répété."""
    _, competitors = dcc.parse_dcc(oracle_dcc_15)
    assert competitors[0].name == "Acromégalies, Pas Seulement…"
    assert competitors[0].skipper == "Perrin Laurent"
    assert all(c.skipper and c.skipper != c.name for c in competitors)


def test_ids_uniques_en_15(oracle_dcc_15: str) -> None:
    _, competitors = dcc.parse_dcc(oracle_dcc_15)
    idents = [c.ident for c in competitors]
    assert sorted(idents) == list(range(1, 46))


def test_oracle_15_est_du_cp1252_en_crlf() -> None:
    """0x85 et 0x92 sont des contrôles en ISO-8859-1 : lire en cp1252."""
    raw = (FIXTURES / "capmartinique2026.dcc").read_bytes()
    assert b"\x85" in raw
    assert raw.count(b"\r\n") == raw.count(b"\n") > 0  # CRLF partout
    assert raw.endswith(b"\r\n")
    assert "…" in raw.decode("cp1252")


def test_les_deux_versions_partagent_le_squelette(
    oracle_dcc: str, oracle_dcc_15: str
) -> None:
    """Champs constants communs aux deux producteurs, aux mêmes places."""
    lignes_13 = [ln.split(";") for ln in oracle_dcc.splitlines()[1:] if ln.strip()]
    lignes_15 = [ln.split(";") for ln in oracle_dcc_15.splitlines()[1:] if ln.strip()]
    for champs in (lignes_13, lignes_15):
        for ligne in champs:
            assert ligne[2] == "1"  # champ 3
            assert ligne[6] == ""  # champ 7
