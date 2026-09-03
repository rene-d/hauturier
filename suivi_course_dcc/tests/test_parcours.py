"""Parcours, zones, et leur sérialisation GPX/KML. Aucun accès réseau."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

import parcours
import tracker

GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def test_le_parcours_relie_les_deux_lignes(tracker_html: str) -> None:
    course = tracker.parse_course(tracker_html)
    assert len(course.route) > 2
    assert len(course.start_line) == len(course.finish_line) == 2

    # Le parcours part du milieu de la ligne de départ et finit sur la ligne
    # d'arrivée — vérifié au centième de degré, pas contre la sortie du code.
    depart = course.route[0]
    milieu = sum(p.lat for p in course.start_line) / 2
    assert depart.lat == pytest.approx(milieu, abs=0.01)
    assert depart.lon == pytest.approx(course.start_line[0].lon, abs=0.01)
    assert course.route[-1].lat == pytest.approx(course.finish_line[0].lat, abs=0.01)


def test_boundaries_url_vient_de_la_page(tracker_html: str) -> None:
    assert tracker.boundaries_url(tracker_html) == (
        "https://cdn.predictwind.com/ocean-race/atlantic/boundaries.json"
    )


def test_zones_normalisees(boundaries: dict[str, Any]) -> None:
    zones = tracker.parse_boundaries(boundaries)
    noms = [z.name for z in zones]
    assert "Marine Mammal Exclusion Zone" in noms
    assert "Ice Exclusion Zone" in noms
    assert noms == sorted(noms)
    for zone in zones:
        assert not zone.name.startswith("Exclusion zone:")  # préfixe retiré
        assert len(zone.points) >= 3
        assert zone.at.tzinfo is not None


def test_polygone_ferme_a_l_export(boundaries: dict[str, Any]) -> None:
    zones = tracker.parse_boundaries(boundaries)
    zone = next(z for z in zones if z.name == "Ice Exclusion Zone")
    assert zone.points[0] != zone.points[-1]  # la source laisse ouvert
    assert zone.closed[0] == zone.closed[-1]
    assert len(zone.closed) == len(zone.points) + 1


def test_zone_deja_fermee_nest_pas_doublee() -> None:
    from datetime import UTC, datetime

    carre = [
        tracker.LatLon(0.0, 0.0),
        tracker.LatLon(1.0, 0.0),
        tracker.LatLon(1.0, 1.0),
        tracker.LatLon(0.0, 0.0),
    ]
    zone = tracker.Zone("k", "Carré", carre, datetime.now(UTC))
    assert zone.closed == carre


def test_schema_inattendu_est_une_erreur() -> None:
    with pytest.raises(RuntimeError, match="longueurs différentes"):
        tracker.parse_boundaries({"k": {"name": "x", "lat": [1, 2], "lon": [1]}})
    with pytest.raises(RuntimeError, match="polygone impossible"):
        tracker.parse_boundaries(
            {"k": {"name": "x", "lat": [1, 2], "lon": [1, 2], "timestamp": 0}}
        )
    with pytest.raises(RuntimeError, match="data-course"):
        tracker.parse_course('<div id="inline-data" data-team-info="{}"></div>')


def test_kml_est_un_polygone_lon_lat(boundaries: dict[str, Any]) -> None:
    zone = tracker.parse_boundaries(boundaries)[0]
    root = ElementTree.fromstring(parcours.format_kml(zone))
    coords = root.find(".//kml:coordinates", KML_NS)
    assert coords is not None and coords.text is not None
    triplets = [line.split(",") for line in coords.text.split()]
    assert len(triplets) == len(zone.closed)
    # KML écrit lon,lat,alt — l'inversion est l'erreur classique.
    lon, lat, alt = triplets[0]
    assert float(lat) == zone.points[0].lat
    assert float(lon) == zone.points[0].lon
    assert alt == "0"


def test_gpx_est_une_route_nommee(tracker_html: str) -> None:
    course = tracker.parse_course(tracker_html)
    xml = parcours.format_gpx(
        "essai", "desc", course.route, parcours.route_names(len(course.route))
    )
    root = ElementTree.fromstring(xml)
    points = root.findall(".//gpx:rte/gpx:rtept", GPX_NS)
    assert len(points) == len(course.route)
    assert not root.findall(".//gpx:wpt", GPX_NS)  # une route, pas des waypoints
    noms = [p.findtext("gpx:name", namespaces=GPX_NS) for p in points]
    assert noms[0] == "START"
    assert noms[-1] == "FINISH"


def test_write_produit_un_fichier_par_objet(
    tmp_path: Path, tracker_html: str, boundaries: dict[str, Any]
) -> None:
    course = tracker.parse_course(tracker_html)
    zones = tracker.parse_boundaries(boundaries)
    written = parcours.write(course, zones, tmp_path)

    assert len(written) == 3 + len(zones)
    assert sorted(p.name for p in written if p.suffix == ".gpx") == [
        "course.gpx",
        "ligne-arrivee.gpx",
        "ligne-depart.gpx",
    ]
    for path in written:
        ElementTree.fromstring(path.read_text(encoding="utf-8"))  # XML valide
    assert (tmp_path / "zone-marine-mammal-exclusion-zone.kml").exists()


def test_slugify() -> None:
    assert parcours.slugify("Ushant (Ouessant) TSS") == "ushant-ouessant-tss"
    assert parcours.slugify("Ice Exclusion Zone") == "ice-exclusion-zone"
