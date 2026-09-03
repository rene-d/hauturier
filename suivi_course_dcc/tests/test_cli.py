"""Chaîne complète tracker -> fichiers, sans accès réseau.

`tracker._get` est le seul point de sortie : le remplacer par les relevés de
`tests/fixtures/` exerce tout le reste du code tel qu'il tourne en vrai.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import dcc
import tor2dcc
import tracker


@pytest.fixture
def hors_ligne(
    monkeypatch: pytest.MonkeyPatch, tracker_html: str, tracker_track: dict
) -> None:  # type: ignore[type-arg]
    corps = json.dumps(tracker_track).encode()

    def faux_get(url: str) -> bytes:
        if "/ocean-race/" in url:
            return tracker_html.encode("utf-8")
        if "/tracking/data/" in url:
            return corps
        raise AssertionError(f"URL inattendue : {url}")

    monkeypatch.setattr(tracker, "_get", faux_get)


def test_chaine_complete(hors_ligne: None, tmp_path: Path) -> None:
    assert tor2dcc.main([str(tmp_path)]) == 0

    dcc_path = tmp_path / "ocean_race_atlantic.dcc"
    pos_path = tmp_path / "ocean_race_atlantic.txt"
    assert dcc_path.exists() and pos_path.exists()

    header, competitors = dcc.parse_dcc(dcc_path.read_text(encoding=dcc.ENCODING))
    fixes = dcc.parse_posreport(pos_path.read_text(encoding=dcc.ENCODING))
    assert header.race == "Ocean Race Atlantic"
    assert len(competitors) == 6
    assert {c.ident for c in competitors} == {f.ident for f in fixes}


def test_trace_complete_par_defaut(hors_ligne: None, tmp_path: Path) -> None:
    """Le posreport porte toute la trace, pas seulement la dernière position."""
    tor2dcc.main([str(tmp_path)])
    fixes = dcc.parse_posreport(
        (tmp_path / "ocean_race_atlantic.txt").read_text(encoding=dcc.ENCODING)
    )
    assert len(fixes) == 6 * 5  # 6 bateaux x 5 points dans la fixture

    par_bateau = [f for f in fixes if f.ident == 422983]
    assert len(par_bateau) == 5
    assert par_bateau == sorted(par_bateau, key=lambda f: f.at)


def test_dernier_point(hors_ligne: None, tmp_path: Path) -> None:
    tor2dcc.main([str(tmp_path), "--dernier-point"])
    fixes = dcc.parse_posreport(
        (tmp_path / "ocean_race_atlantic.txt").read_text(encoding=dcc.ENCODING)
    )
    assert len(fixes) == 6
    assert len({f.ident for f in fixes}) == 6


def test_pas_sous_echantillonne(hors_ligne: None, tmp_path: Path) -> None:
    """La fixture est à 60 s : un pas de 120 s garde un point sur deux."""
    tor2dcc.main([str(tmp_path), "--pas", "120"])
    fixes = dcc.parse_posreport(
        (tmp_path / "ocean_race_atlantic.txt").read_text(encoding=dcc.ENCODING)
    )
    trace = [f for f in fixes if f.ident == 422983]
    assert len(trace) == 3
    assert (trace[1].at - trace[0].at).total_seconds() >= 120


def test_pas_conserve_le_dernier_point(hors_ligne: None, tmp_path: Path) -> None:
    """Le point le plus récent ne doit jamais tomber au sous-échantillonnage."""
    tor2dcc.main([str(tmp_path)])
    complet = dcc.parse_posreport(
        (tmp_path / "ocean_race_atlantic.txt").read_text(encoding=dcc.ENCODING)
    )
    tor2dcc.main([str(tmp_path), "--pas", "3600"])
    reduit = dcc.parse_posreport(
        (tmp_path / "ocean_race_atlantic.txt").read_text(encoding=dcc.ENCODING)
    )
    for ident in {f.ident for f in complet}:
        dernier = max((f for f in complet if f.ident == ident), key=lambda f: f.at)
        assert dernier in reduit


def test_depuis_filtre_sur_l_age(hors_ligne: None, tmp_path: Path) -> None:
    """La fixture date du 2026-09-02 : une fenêtre courte ne garde que le dernier."""
    tor2dcc.main([str(tmp_path), "--depuis", "0.001"])
    fixes = dcc.parse_posreport(
        (tmp_path / "ocean_race_atlantic.txt").read_text(encoding=dcc.ENCODING)
    )
    assert len(fixes) == 6


def test_id_concurrent_est_le_trackid(hors_ligne: None, tmp_path: Path) -> None:
    """Pas de mapping local : l'ID vient de la source, donc il est stable."""
    tor2dcc.main([str(tmp_path)])
    _, competitors = dcc.parse_dcc(
        (tmp_path / "ocean_race_atlantic.dcc").read_text(encoding=dcc.ENCODING)
    )
    malizia = next(c for c in competitors if c.name == "Team Malizia")
    assert malizia.ident == 422983


def test_mise_a_jour_en_place(hors_ligne: None, tmp_path: Path) -> None:
    """Relancer met à jour : mêmes chemins, aucun fichier qui s'accumule."""
    for _ in range(3):
        tor2dcc.main([str(tmp_path)])
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "ocean_race_atlantic.dcc",
        "ocean_race_atlantic.txt",
    ]


def test_aucun_temporaire_residuel(hors_ligne: None, tmp_path: Path) -> None:
    tor2dcc.main([str(tmp_path)])
    assert not list(tmp_path.glob("*.tmp")) and not list(tmp_path.glob(".*"))


def test_nom_de_course_force(hors_ligne: None, tmp_path: Path) -> None:
    tor2dcc.main([str(tmp_path), "--race", "Atlantic 2026"])
    assert (tmp_path / "atlantic_2026.dcc").exists()


def test_serie_forcee(hors_ligne: None, tmp_path: Path) -> None:
    """Par défaut le champ « type » reçoit le pays, faute de série publiée."""
    tor2dcc.main([str(tmp_path)])
    _, avant = dcc.parse_dcc(
        (tmp_path / "ocean_race_atlantic.dcc").read_text(encoding=dcc.ENCODING)
    )
    assert {c.kind for c in avant} == {
        "Japan",
        "New Zealand",
        "France",
        "Germany",
        "Switzerland",
    }

    tor2dcc.main([str(tmp_path), "--serie", "IMOCA"])
    _, apres = dcc.parse_dcc(
        (tmp_path / "ocean_race_atlantic.dcc").read_text(encoding=dcc.ENCODING)
    )
    assert {c.kind for c in apres} == {"IMOCA"}


def longitudes(path: Path) -> list[str]:
    lignes = path.read_text(encoding=dcc.ENCODING).splitlines()[1:]
    return [ligne.split(";")[3] for ligne in lignes]


def test_no_pad(hors_ligne: None, tmp_path: Path) -> None:
    """Les deux variantes de padding, à départager dans qtVlm."""
    pos = tmp_path / "ocean_race_atlantic.txt"

    tor2dcc.main([str(tmp_path)])
    assert all(lon.startswith("073.") for lon in longitudes(pos))

    tor2dcc.main([str(tmp_path), "--no-pad"])
    assert all(lon.startswith("73.") for lon in longitudes(pos))


def test_loop_trop_rapide_refuse(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        tor2dcc.main([str(tmp_path), "--loop", "10"])


def test_echec_reseau_bruyant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Une passe unique qui échoue doit échouer, pas produire un fichier vide."""

    def get_casse(url: str) -> bytes:
        raise RuntimeError("HTTP 503")

    monkeypatch.setattr(tracker, "_get", get_casse)
    with pytest.raises(RuntimeError, match="503"):
        tor2dcc.main([str(tmp_path)])
    assert not list(tmp_path.glob("*"))
