"""Lecture du flux PredictWind, contre un relevé réel (aucun accès réseau)."""

from __future__ import annotations

from datetime import UTC
from typing import Any

import pytest

import tracker


def test_bootstrap_donne_la_flotte(tracker_html: str) -> None:
    race, teams = tracker.parse_bootstrap(tracker_html)
    assert race == "Ocean Race Atlantic"
    assert len(teams) == 6
    assert [t.name for t in teams] == sorted(t.name for t in teams)

    malizia = next(t for t in teams if t.name == "Team Malizia")
    assert malizia.track_display == "wlyvxprp"
    assert malizia.track_id == 422983
    assert malizia.country == "Germany"


def test_ids_uniques_et_numeriques(tracker_html: str) -> None:
    """Le trackId sert d'ID concurrent : il doit être unique."""
    _, teams = tracker.parse_bootstrap(tracker_html)
    idents = [t.track_id for t in teams]
    assert len(set(idents)) == len(idents)
    assert all(isinstance(i, int) for i in idents)


def test_bootstrap_absent_leve() -> None:
    with pytest.raises(RuntimeError, match="#inline-data absent"):
        tracker.parse_bootstrap("<html><body>rien</body></html>")


def test_bootstrap_incomplet_leve() -> None:
    with pytest.raises(RuntimeError, match="data-team-info"):
        tracker.parse_bootstrap('<div id="inline-data" data-event-config="{}"></div>')


def test_track_normalise(tracker_track: dict[str, Any]) -> None:
    points = tracker.parse_track(tracker_track)
    assert len(points) == 5
    assert all(p.at.tzinfo is UTC for p in points)
    assert points == sorted(points, key=lambda p: p.at)
    assert -90 <= points[0].lat <= 90
    assert -180 <= points[0].lon <= 180


def test_track_accepte_les_segments(tracker_track: dict[str, Any]) -> None:
    """Le client officiel applique `.flat()` : les deux formes existent."""
    plat = tracker.parse_track(tracker_track)
    segmente = tracker.parse_track(
        {"route": [tracker_track["route"][:2], tracker_track["route"][2:]]}
    )
    assert segmente == plat


@pytest.mark.parametrize(
    "casse",
    [
        {},
        {"route": "pas une liste"},
        {"route": [{"t": 1}]},  # pas de position
        {"route": [{"p": {"lat": 1, "lon": 2}}]},  # pas d'horodatage
    ],
)
def test_track_malforme_leve(casse: dict[str, Any]) -> None:
    with pytest.raises((RuntimeError, KeyError, TypeError)):
        tracker.parse_track(casse)


def test_donnees_meteo_jetees(tracker_track: dict[str, Any]) -> None:
    """Le DCC ne transporte que position + heure : bsp, twd, tws sont perdus."""
    assert "tws" in tracker_track["route"][0]
    point = tracker.parse_track(tracker_track)[0]
    assert set(point.__slots__) == {"at", "lat", "lon"}
