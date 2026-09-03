"""Présence de ce fichier : place la racine du projet dans sys.path."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


@pytest.fixture(scope="session")
def oracle_dcc() -> str:
    """Descriptif YB Tracking (Pacific Cup 2024), oracle de format."""
    path = FIXTURES / "paccup2024-adrenacompetitors.dcc"
    return path.read_text(encoding="iso-8859-1")


@pytest.fixture(scope="session")
def oracle_posreport() -> str:
    path = FIXTURES / "paccup2024-adrena.txt"
    return path.read_text(encoding="iso-8859-1")


@pytest.fixture(scope="session")
def oracle_dcc_15() -> str:
    """Descriptif Geovoile (Cap Martinique 2026), oracle de format v1.5.

    Décodé en cp1252 : le fichier contient 0x85 et 0x92, contrôles en
    ISO-8859-1 (cf. FORMAT-DCC.md).
    """
    return (FIXTURES / "capmartinique2026.dcc").read_text(encoding="cp1252")


@pytest.fixture(scope="session")
def tracker_html() -> str:
    """Bootstrap PredictWind relevé le 2026-09-02."""
    return (FIXTURES / "predictwind-inline-data.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def boundaries() -> dict:  # type: ignore[type-arg]
    """Zones d'exclusion PredictWind relevées le 2026-09-03."""
    import json

    return json.loads(
        (FIXTURES / "predictwind-boundaries.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="session")
def tracker_track() -> dict:  # type: ignore[type-arg]
    import json

    return json.loads((FIXTURES / "predictwind-track.json").read_text(encoding="utf-8"))
