#!/usr/bin/env python3
"""Fraction illuminée du disque lunaire.

Météo Consult ne publie que la phase en huit crans ; le pourcentage est calculé ici
par les formules de Meeus (« Astronomical Algorithms », ch. 47-48, forme abrégée),
précises à mieux que 0,5 % — largement assez pour une vignette et un pourcentage
arrondi, et sans éphéméride à embarquer.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from math import cos, radians, sin

UNIX_EPOCH_JD = 2440587.5


def julian_day(when: datetime) -> float:
    """Jour julien d'un instant (datetime *aware*)."""
    return when.timestamp() / 86400.0 + UNIX_EPOCH_JD


def phase_angle(when: datetime) -> float:
    """Angle de phase Soleil-Lune-Terre, en degrés (0° = pleine lune)."""
    t = (julian_day(when) - 2451545.0) / 36525

    # élongation moyenne de la Lune, anomalie moyenne du Soleil, anomalie de la Lune
    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t**2 + t**3 / 545868 - t**4 / 113065000
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t**2 + t**3 / 24490000
    mp = 134.9633964 + 477198.8675055 * t + 0.0087414 * t**2 + t**3 / 69699 - t**4 / 14712000

    return (
        180.0 - d
        - 6.289 * sin(radians(mp))
        + 2.100 * sin(radians(m))
        - 1.274 * sin(radians(2 * d - mp))
        - 0.658 * sin(radians(2 * d))
        - 0.214 * sin(radians(2 * mp))
        - 0.110 * sin(radians(d))
    )


def illumination(when: datetime) -> float:
    """Fraction du disque lunaire éclairée, de 0 (nouvelle lune) à 1 (pleine lune)."""
    return (1 + cos(radians(phase_angle(when)))) / 2


def waxing(when: datetime) -> bool:
    """Vrai si la Lune croît. Se déduit du sens de variation de l'illumination, ce
    qui reste juste les jours de nouvelle et de pleine lune, où la phase publiée
    par le site ne dit rien du sens."""
    return illumination(when + timedelta(hours=6)) > illumination(when)
