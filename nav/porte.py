#!/usr/bin/env python3
"""Horaires d'ouverture de la porte d'un bassin à flot, calculés depuis les marées.

La porte s'ouvre quand la hauteur d'eau franchit un seuil en montant et se referme
quand elle repasse sous ce seuil en descendant. Entre deux extrêmes de marée la
hauteur est interpolée, au choix :

  - `sine`      : loi sinusoïdale (par défaut, meilleur accord avec l'officiel),
  - `twelfths`  : règle des douzièmes (1/12, 2/12, 3/12, 3/12, 2/12, 1/12).

En morte-eau franche la basse mer peut rester au-dessus du seuil : la porte reste
alors ouverte plusieurs jours, ce que le calendrier officiel montre bien.

Le seuil d'ouverture et celui de fermeture peuvent différer, et le seuil de
fermeture peut lui-même dépendre du marnage : à Perros-Guirec la porte s'ouvre à
7,40 m mais se referme à 8,10 m en vives-eaux et 7,65 m en mortes-eaux, la bascule
se faisant au coefficient 70.

Deux seuils sont utiles :

  - la **cote d'ouverture de la porte** (4,30 m / zéro des cartes à Trébeurden),
  - la **cote de passage du bateau** = radier + tirant d'eau + pied de pilote.
    À Trébeurden le radier est à 2,80 m (il reste 1,50 m d'eau au-dessus quand la
    porte s'ouvre à 4,30 m), donc 2,80 + 2,10 + 0,40 = 5,30 m pour un tirant d'eau
    de 2,10 m avec 40 cm de marge.

Les hauteurs de la source sont recalées avant le calcul : `height_offset` est ce
qu'il faut ajouter à une hauteur publiée pour retrouver la référence du port. À
Trébeurden, Météo Consult donne des hauteurs ~0,25 m plus basses et des horaires
~8 min en avance ; avec ces corrections le calcul reproduit le calendrier officiel
2026 du port à 4,6 min près en moyenne (cf. `verif_porte_trebeurden.py`). C'est un
recalage constant, pas une correction d'amplitude : il suffit ici, sans plus.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

# Fractions cumulées de la règle des douzièmes.
CUM_FRACTIONS = [0, 1 / 12, 3 / 12, 6 / 12, 9 / 12, 11 / 12, 1]


def height_twelfths(f: float, h0: float, h1: float) -> float:
    i = min(int(f * 6), 5)
    within = f * 6 - i
    change = CUM_FRACTIONS[i] + within * (CUM_FRACTIONS[i + 1] - CUM_FRACTIONS[i])
    return h0 + change * (h1 - h0)


def height_sine(f: float, h0: float, h1: float) -> float:
    return (h0 + h1) / 2 - (h1 - h0) / 2 * math.cos(math.pi * f)


MODELS = {"sine": height_sine, "twelfths": height_twelfths}


@dataclass
class Gate:
    """Réglages d'une porte : seuils, modèle d'interpolation, recalage de la source.

    `close` vaut `threshold` par défaut (porte symétrique). `neap_close` s'y
    substitue quand le coefficient de la pleine mer est sous `neap_below` : le seuil
    de fermeture des bassins n'est pas toujours le même en vives et en mortes-eaux.
    Sous `min_coef`, la porte ne s'ouvre pas du tout — certains bassins renoncent à
    la manœuvre en mortes-eaux, même si la cote d'ouverture est atteinte.
    `height_offset` est ce qu'il faut ajouter à une hauteur publiée pour retrouver la
    référence du port, `time_offset` le décalage en minutes.
    """

    threshold: float
    close: float | None = None
    neap_close: float | None = None
    neap_below: int = 70
    min_coef: int | None = None
    model: str = "sine"
    time_offset: int = 0
    height_offset: float = 0.0

    def opening(self) -> float:
        return self.threshold - self.height_offset

    def closing(self, coef: int | None) -> float:
        level = self.close if self.close is not None else self.threshold
        if self.neap_close is not None and coef is not None and coef < self.neap_below:
            level = self.neap_close
        return level - self.height_offset


@dataclass
class Window:
    """Un créneau d'ouverture. `close` est None si la porte est encore ouverte."""

    open: datetime
    close: datetime | None = None

    @property
    def duration(self) -> timedelta | None:
        return self.close - self.open if self.close else None


def _crossing(t0: datetime, h0: float, t1: datetime, h1: float,
              threshold: float, model) -> datetime | None:
    """Instant où la hauteur franchit `threshold` entre deux extrêmes consécutifs."""
    if not min(h0, h1) <= threshold <= max(h0, h1):
        return None
    lo, hi = 0.0, 1.0
    rising = h1 > h0
    for _ in range(50):  # dichotomie : le modèle est monotone sur l'intervalle
        mid = (lo + hi) / 2
        if (model(mid, h0, h1) < threshold) == rising:
            lo = mid
        else:
            hi = mid
    return t0 + (t1 - t0) * ((lo + hi) / 2)


def height_at(extrema: list[tuple[datetime, float]], when: datetime,
              model: str = "sine", height_offset: float = 0.0) -> float | None:
    """Hauteur d'eau interpolée à un instant donné.

    Utile en sens inverse : à partir d'une heure d'ouverture relevée sur le terrain,
    elle donne la cote correspondante — donc le seuil de la porte.
    """
    f = MODELS[model]
    for (t0, h0), (t1, h1) in zip(extrema, extrema[1:]):
        if t0 <= when <= t1:
            return f((when - t0) / (t1 - t0), h0, h1) + height_offset
    return None


def gate_windows(extrema: list[tuple[datetime, float]], gate: Gate,
                 coefs: dict[datetime, int] | None = None) -> list[Window]:
    """Créneaux où la porte est ouverte.

    Elle s'ouvre quand la hauteur franchit le seuil d'ouverture en montant et se
    referme au seuil de fermeture en descendant. Si la pleine mer n'atteint pas ce
    dernier, la fermeture retombe sur le seuil d'ouverture, faute de quoi la porte ne
    se refermerait jamais. `coefs` donne le coefficient de chaque pleine mer, pour
    choisir entre le régime de vives-eaux et celui de mortes-eaux.

    `extrema` doit être trié et en datetime *aware* : l'interpolation se fait sur
    l'échelle absolue, sinon les nuits de changement d'heure décalent d'une heure.
    """
    f = MODELS[gate.model]
    opening = gate.opening()
    shift = timedelta(minutes=gate.time_offset)
    events = []
    for (t0, h0), (t1, h1) in zip(extrema, extrema[1:]):
        rising = h1 > h0
        if rising and gate.min_coef is not None:
            coef = (coefs or {}).get(t1)   # la pleine mer visée par cette montée
            if coef is not None and coef < gate.min_coef:
                continue                   # marée trop faible : pas de manœuvre
        closing = gate.closing((coefs or {}).get(t0))
        t = _crossing(t0, h0, t1, h1, opening if rising else closing, f)
        if t is None and not rising and closing != opening:
            t = _crossing(t0, h0, t1, h1, opening, f)  # pleine mer trop basse
        if t:
            events.append((t + shift, rising))

    windows: list[Window] = []
    for t, rising in events:
        if rising:
            if not windows or windows[-1].close is not None:
                windows.append(Window(open=t))
        elif windows and windows[-1].close is None:
            windows[-1].close = t
    return windows
