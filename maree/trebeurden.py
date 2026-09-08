#!/usr/bin/env python3
"""
Calcul des horaires de marée à Trébeurden selon la règle des douzièmes.
Fractions par sixième d'intervalle : 1/12, 2/12, 3/12, 3/12, 2/12, 1/12.

Usage:
  python trebeurden.py                          # mode interactif
  python trebeurden.py --pm 10:45 7.20 --bm 17:00 1.40
  python trebeurden.py -p 10:45 7.20 -b 17:00 1.40
  python trebeurden.py --pm 10:45 7.20          # BM demandé interactivement
  python trebeurden.py --seuils 3.50 5.00       # seuils personnalisés
  python trebeurden.py --no-graph               # calcul seul, sans affichage
  python trebeurden.py -o maree_du_jour.png     # nom du fichier de sortie
"""

import argparse
import sys
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

# Fractions cumulées : 0, 1, 3, 6, 9, 11, 12 douzièmes
CUM_FRACTIONS = [0, 1/12, 3/12, 6/12, 9/12, 11/12, 1]


def parse_time(prompt):
    while True:
        s = input(prompt).strip()
        try:
            return datetime.strptime(s, "%H:%M")
        except ValueError:
            print("  Format invalide. Utilisez HH:MM (ex: 14:30)")


def parse_height(prompt):
    while True:
        s = input(prompt).strip().replace(",", ".")
        try:
            h = float(s)
            if 0.0 <= h <= 15.0:
                return h
            print("  Hauteur improbable. Réessayez.")
        except ValueError:
            print("  Valeur invalide. Entrez un nombre (ex: 5.80)")


def validate_time(value):
    """Type argparse : valide et retourne un datetime depuis HH:MM."""
    try:
        return datetime.strptime(value, "%H:%M")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Heure invalide '{value}' — attendu HH:MM")


def validate_height(value):
    """Type argparse : valide et retourne un float entre 0 et 15."""
    try:
        h = float(value.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"Hauteur invalide '{value}'")
    if not 0.0 <= h <= 15.0:
        raise argparse.ArgumentTypeError(f"Hauteur hors plage (0–15 m) : {h}")
    return h


def parse_tide_arg(values, label):
    """Valide la paire [HH:MM, hauteur] issue d'un argument --pm / --bm."""
    if len(values) != 2:
        print(f"  --{label.lower()} attend 2 valeurs : HH:MM HAUTEUR", file=sys.stderr)
        sys.exit(1)
    t = validate_time(values[0])
    h = validate_height(values[1])
    return t, h


def build_parser():
    p = argparse.ArgumentParser(
        description="Calcul des marées à Trébeurden — règle des douzièmes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  %(prog)s --pm 10:45 7.20 --bm 17:00 1.40\n"
            "  %(prog)s -p 23:30 6.80 -b 05:45 1.20\n"
            "  %(prog)s --pm 10:45 7.20 --seuils 3.50 4.80 5.30\n"
            "  %(prog)s --pm 10:45 7.20 --bm 17:00 1.40 --no-graph\n"
        ),
    )
    p.add_argument(
        "--pm", "-p",
        nargs=2, metavar=("HH:MM", "HAUTEUR"),
        help="Pleine mer : heure et hauteur en mètres",
    )
    p.add_argument(
        "--bm", "-b",
        nargs=2, metavar=("HH:MM", "HAUTEUR"),
        help="Basse mer : heure et hauteur en mètres",
    )
    p.add_argument(
        "--seuils", "-s",
        nargs="+", metavar="HAUTEUR", type=validate_height,
        default=[4.30, 5.30],
        help="Seuils à calculer en mètres (défaut : 4.30 5.30)",
    )
    p.add_argument(
        "--no-graph",
        action="store_true",
        help="Afficher uniquement les résultats, sans générer le graphe",
    )
    p.add_argument(
        "--output", "-o",
        default="trebeurden_maree.png",
        metavar="FICHIER",
        help="Nom du fichier image (défaut : trebeurden_maree.png)",
    )
    return p


def height_at_fraction(f, h_start, h_end):
    """Hauteur à la fraction f ∈ [0, 1] de l'intervalle, règle des douzièmes."""
    f = max(0.0, min(1.0, f))
    i = min(int(f * 6), 5)
    within = f * 6 - i
    change = CUM_FRACTIONS[i] + within * (CUM_FRACTIONS[i + 1] - CUM_FRACTIONS[i])
    return h_start + change * (h_end - h_start)


def find_times_for_height(target, h_start, h_end, t_start, duration_min):
    """Retourne la liste des datetime où la hauteur vaut target (dans l'intervalle)."""
    h_lo, h_hi = min(h_start, h_end), max(h_start, h_end)
    if not (h_lo <= target <= h_hi):
        return []
    results = []
    for i in range(6):
        f0, f1 = i / 6, (i + 1) / 6
        h0 = height_at_fraction(f0, h_start, h_end)
        h1 = height_at_fraction(f1, h_start, h_end)
        if abs(h1 - h0) < 1e-9:
            continue
        if min(h0, h1) <= target <= max(h0, h1):
            frac = f0 + (target - h0) / (h1 - h0) * (f1 - f0)
            results.append(t_start + timedelta(minutes=frac * duration_min))
    return results


def main():
    args = build_parser().parse_args()

    print("=== Calcul des marées à Trébeurden ===")
    print("    Règle des douzièmes\n")

    # PM : argument CLI ou saisie interactive
    if args.pm:
        t_pm, h_pm = parse_tide_arg(args.pm, "pm")
        print(f"Pleine mer (PM) : {t_pm.strftime('%H:%M')}  {h_pm:.2f} m")
    else:
        print("Pleine mer (PM) :")
        t_pm = parse_time("  Heure (HH:MM) : ")
        h_pm = parse_height("  Hauteur  (m)  : ")

    # BM : argument CLI ou saisie interactive
    if args.bm:
        t_bm, h_bm = parse_tide_arg(args.bm, "bm")
        print(f"Basse mer  (BM) : {t_bm.strftime('%H:%M')}  {h_bm:.2f} m")
    else:
        print("\nBasse mer (BM) :")
        t_bm = parse_time("  Heure (HH:MM) : ")
        h_bm = parse_height("  Hauteur  (m)  : ")

    thresholds = sorted(set(args.seuils))
    no_graph   = args.no_graph
    outfile    = args.output

    # Résolution de l'ordre chronologique (gestion du passage minuit).
    # forward_diff = durée en minutes de PM vers BM dans le sens direct (modulo 24h).
    # Si forward_diff < 12h, PM est avant BM ; sinon BM est avant PM.
    pm_min = t_pm.hour * 60 + t_pm.minute
    bm_min = t_bm.hour * 60 + t_bm.minute
    forward_diff = (bm_min - pm_min) % 1440

    ref = datetime(2000, 1, 1)
    dt_pm = ref.replace(hour=t_pm.hour, minute=t_pm.minute)
    dt_bm = ref.replace(hour=t_bm.hour, minute=t_bm.minute)

    if forward_diff <= 720:
        # PM avant BM
        if dt_bm <= dt_pm:
            dt_bm += timedelta(days=1)
        t_start, h_start, label_start = dt_pm, h_pm, "PM"
        t_end,   h_end,   label_end   = dt_bm, h_bm, "BM"
    else:
        # BM avant PM
        if dt_pm <= dt_bm:
            dt_pm += timedelta(days=1)
        t_start, h_start, label_start = dt_bm, h_bm, "BM"
        t_end,   h_end,   label_end   = dt_pm, h_pm, "PM"

    duration_min = (t_end - t_start).total_seconds() / 60
    marnage = abs(h_pm - h_bm)
    sens = "descendante (jusant)" if h_pm > h_bm else "montante (flot)"

    print(f"\n  Sens    : {label_start} → {label_end}  ({sens})")
    print(f"  Durée   : {int(duration_min // 60)}h{int(duration_min % 60):02d}")
    print(f"  Marnage : {marnage:.2f} m")
    print()

    # Calcul des seuils
    threshold_times: dict[float, list[datetime]] = {}
    for target in thresholds:
        times = find_times_for_height(target, h_start, h_end, t_start, duration_min)
        threshold_times[target] = times
        if times:
            ts = ", ".join(t.strftime("%H:%M") for t in times)
            print(f"  {target:.2f} m  →  {ts}")
        else:
            print(f"  {target:.2f} m  →  hors de la plage de marée")

    if no_graph:
        return

    # ── Graphe ───────────────────────────────────────────────────────────────
    N = 400
    times_plot  = [t_start + timedelta(minutes=i * duration_min / (N - 1)) for i in range(N)]
    heights_plot = [height_at_fraction(i / (N - 1), h_start, h_end) for i in range(N)]

    fig, ax = plt.subplots(figsize=(13, 6))

    ax.plot(times_plot, heights_plot, color="steelblue", linewidth=2.5,
            label="Hauteur d'eau (règle des douzièmes)")

    # Marqueurs PM et BM
    ax.plot(dt_pm, h_pm, "go", markersize=10, zorder=5,
            label=f"PM  {dt_pm.strftime('%H:%M')}  ({h_pm:.2f} m)")
    ax.plot(dt_bm, h_bm, "ro", markersize=10, zorder=5,
            label=f"BM  {dt_bm.strftime('%H:%M')}  ({h_bm:.2f} m)")

    # Seuils — couleurs cycliques si plus de 2
    palette = ["darkorange", "mediumpurple", "crimson", "teal", "saddlebrown"]
    colors_thresh = {t: palette[i % len(palette)] for i, t in enumerate(thresholds)}
    for target in thresholds:
        color = colors_thresh[target]
        ax.axhline(y=target, color=color, linestyle="--", linewidth=1.8,
                   label=f"Seuil {target:.2f} m")
        for t in threshold_times[target]:
            ax.plot(t, target, "x", color=color, markersize=13, markeredgewidth=2.5, zorder=6)
            ax.annotate(
                t.strftime("%H:%M"),
                xy=(t, target),
                xytext=(6, 7),
                textcoords="offset points",
                fontsize=10,
                color=color,
                fontweight="bold",
            )

    # Axe X : graduations toutes les 30 min
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 30)))
    plt.xticks(rotation=45, ha="right")

    ax.set_xlabel("Heure", fontsize=12)
    ax.set_ylabel("Hauteur (m)", fontsize=12)
    ax.set_title(
        "Évolution de la marée à Trébeurden\n(règle des douzièmes)",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3, linestyle=":")
    y_margin = 0.3
    ax.set_ylim(
        bottom=max(0.0, min(h_pm, h_bm) - y_margin),
        top=max(h_pm, h_bm) + y_margin,
    )

    plt.tight_layout()
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"\n  Graphe sauvegardé : {outfile}")


if __name__ == "__main__":
    main()
