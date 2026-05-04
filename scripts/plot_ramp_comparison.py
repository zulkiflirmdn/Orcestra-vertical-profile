#!/usr/bin/env python3
"""
Omega Profile Comparison — Before vs After Ramp Correction
==========================================================

Generates a spaghetti-style comparison figure mirroring the categorization
notebook's style.  Left column shows raw BEACH omega profiles; right column
shows profiles after the linear ramp correction (``omega_mass_corrected``).

Each row corresponds to one category group (Top-Heavy, Bottom-Heavy,
Inactive/Suppressed), and a final row shows all circles together.

Usage
-----
    python scripts/plot_ramp_comparison.py              # saves to outputs/figures/
    python scripts/plot_ramp_comparison.py --show       # also display interactively
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.mse_budget import load_dataset, omega_mass_corrected

# ---------------------------------------------------------------------------
# Constants (match categorization notebook style)
# ---------------------------------------------------------------------------

CATEGORY_GROUPS = {
    "Top-Heavy": {
        "cats":  ["Top-Heavy", "Top-Heavy (Fully Ascending)"],
        "color": "#d62728",
    },
    "Bottom-Heavy": {
        "cats":  ["Bottom-Heavy", "Bottom-Heavy (Fully Ascending)"],
        "color": "#1f77b4",
    },
    "Inactive /\nSuppressed": {
        "cats":  ["Inactive / Suppressed"],
        "color": "#888888",
    },
}

X_LIM = (-1.0, 0.5)       # Pa s⁻¹
Y_LIM = (1000, 100)        # hPa (inverted)

OUTPUT_DIR = Path("/home/565/zr7147/Proj/outputs/figures")


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _spaghetti_panel(ax, omega_2d, p_2d, mean_color, title, *, show_ylabel=True):
    """
    Draw individual profiles as thin gray lines + a thick colored mean.

    Parameters
    ----------
    omega_2d : (n_circles, n_alt) array   [Pa s⁻¹]
    p_2d     : (n_circles, n_alt) array   [Pa]
    """
    n_circles = omega_2d.shape[0]

    # Individual spaghetti lines
    for k in range(n_circles):
        o_k = omega_2d[k]
        p_k = p_2d[k] / 100.0   # → hPa
        valid = np.isfinite(o_k) & np.isfinite(p_k)
        if valid.sum() < 3:
            continue
        ax.plot(o_k[valid], p_k[valid],
                color="gray", alpha=0.22, lw=0.9, zorder=2)

    # Group mean
    mean_omega = np.nanmean(omega_2d, axis=0)
    mean_p     = np.nanmean(p_2d, axis=0) / 100.0
    valid_mean = np.isfinite(mean_omega) & np.isfinite(mean_p)
    ax.plot(mean_omega[valid_mean], mean_p[valid_mean],
            color=mean_color, lw=3.5, zorder=3, label="Mean")

    ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.7)
    ax.set_xlim(X_LIM)
    ax.set_ylim(Y_LIM)
    ax.set_xlabel("Vertical Velocity ω  (Pa s⁻¹)", fontsize=10)
    if show_ylabel:
        ax.set_ylabel("Pressure (hPa)", fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold", color=mean_color)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.25)


def make_comparison_figure(ds, omega_raw, omega_corr, cat_var="category_plane"):
    """
    Create a 4-row × 2-column comparison figure.

    Rows: Top-Heavy, Bottom-Heavy, Inactive/Suppressed, All Circles.
    Columns: Before ramp, After ramp.
    """
    n_groups = len(CATEGORY_GROUPS) + 1  # +1 for "All Circles"
    fig, axes = plt.subplots(n_groups, 2, figsize=(14, 6 * n_groups), sharey=True)
    fig.suptitle(
        "Omega Profile Spaghetti — Before vs After Ramp Correction\n",
        fontsize=16, fontweight="bold",
    )

    p_all = ds["p_mean"].values  # (circle, altitude)  [Pa]

    # ── Category rows ────────────────────────────────────────────────────
    for row, (label, cfg) in enumerate(CATEGORY_GROUPS.items()):
        if cat_var in ds:
            cat_vals = ds[cat_var].values
            cat_mask = np.isin(cat_vals, cfg["cats"])
        else:
            # fallback — plot all circles in each row
            cat_mask = np.ones(ds.sizes["circle"], dtype=bool)

        n = int(cat_mask.sum())
        col = cfg["color"]

        if n == 0:
            for c in range(2):
                axes[row, c].set_visible(False)
            continue

        o_raw_g  = omega_raw[cat_mask]
        o_corr_g = omega_corr[cat_mask]
        p_g      = p_all[cat_mask]

        _spaghetti_panel(
            axes[row, 0], o_raw_g, p_g, col,
            f"{label}  — BEFORE ramp  ({n} circles)",
            show_ylabel=True,
        )
        _spaghetti_panel(
            axes[row, 1], o_corr_g, p_g, col,
            f"{label}  — AFTER ramp  ({n} circles)",
            show_ylabel=False,
        )

    # ── "All Circles" row ────────────────────────────────────────────────
    row_all = n_groups - 1
    n_all   = ds.sizes["circle"]
    _spaghetti_panel(
        axes[row_all, 0], omega_raw, p_all, "#333333",
        f"All Circles — BEFORE ramp  ({n_all} circles)",
        show_ylabel=True,
    )
    _spaghetti_panel(
        axes[row_all, 1], omega_corr, p_all, "#333333",
        f"All Circles — AFTER ramp  ({n_all} circles)",
        show_ylabel=False,
    )

    # Column headers
    axes[0, 0].annotate(
        "Raw BEACH ω", xy=(0.5, 1.22), xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )
    axes[0, 1].annotate(
        "Ramp-Corrected ω", xy=(0.5, 1.22), xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


# ---------------------------------------------------------------------------
# Supplementary figure: overlay "before" and "after" means on the same axes
# ---------------------------------------------------------------------------

def make_overlay_figure(ds, omega_raw, omega_corr, cat_var="category_plane"):
    """
    One panel per category group.  Each panel overlays the raw mean (dashed)
    and corrected mean (solid) so the effect of the ramp is directly visible.
    """
    fig, axes = plt.subplots(1, len(CATEGORY_GROUPS), figsize=(16, 8), sharey=True)
    fig.suptitle(
        "Effect of Ramp Correction on Mean Omega Profile\n",
        fontsize=15, fontweight="bold",
    )

    p_all = ds["p_mean"].values

    for ax, (label, cfg) in zip(axes, CATEGORY_GROUPS.items()):
        if cat_var in ds:
            cat_vals = ds[cat_var].values
            cat_mask = np.isin(cat_vals, cfg["cats"])
        else:
            cat_mask = np.ones(ds.sizes["circle"], dtype=bool)

        n   = int(cat_mask.sum())
        col = cfg["color"]

        if n == 0:
            ax.set_visible(False)
            continue

        p_g = p_all[cat_mask]

        # Mean pressure grid (hPa)
        mean_p = np.nanmean(p_g, axis=0) / 100.0

        # Raw mean
        mean_raw  = np.nanmean(omega_raw[cat_mask], axis=0)
        # Corrected mean
        mean_corr = np.nanmean(omega_corr[cat_mask], axis=0)

        valid_raw  = np.isfinite(mean_raw) & np.isfinite(mean_p)
        valid_corr = np.isfinite(mean_corr) & np.isfinite(mean_p)

        ax.plot(mean_raw[valid_raw], mean_p[valid_raw],
                color=col, lw=2.5, ls="--", alpha=0.7, label="Before ramp")
        ax.plot(mean_corr[valid_corr], mean_p[valid_corr],
                color=col, lw=3.0, ls="-", label="After ramp")

        # Shade difference
        shared_valid = valid_raw & valid_corr
        ax.fill_betweenx(
            mean_p[shared_valid],
            mean_raw[shared_valid],
            mean_corr[shared_valid],
            alpha=0.15, color=col,
        )

        ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.7)
        ax.set_xlim(X_LIM)
        ax.set_ylim(Y_LIM)
        ax.set_xlabel("Vertical Velocity ω  (Pa s⁻¹)", fontsize=10)
        ax.set_title(f"{label}\n({n} circles)", fontsize=11,
                     fontweight="bold", color=col)
        ax.legend(fontsize=9, loc="upper right")
        ax.grid(True, alpha=0.25)

    axes[0].set_ylabel("Pressure (hPa)", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return fig


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Omega spaghetti comparison: before vs after ramp correction"
    )
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively (in addition to saving)")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR,
                        help="Output directory for saved figures")
    args = parser.parse_args()

    print("Loading BEACH L4 dataset …")
    ds = load_dataset()

    # Raw omega
    omega_raw = ds["omega"].values.copy()

    # Ramp-corrected omega (linear mass correction → ω=0 at profile top)
    print("Computing ramp-corrected omega …")
    omega_corr, delta_div = omega_mass_corrected(ds)

    # Detect which category variable is available
    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    print(f"Using category variable: {cat_var}")

    # ── Figure 1: side-by-side spaghetti ─────────────────────────────────
    print("Generating spaghetti comparison figure …")
    fig1 = make_comparison_figure(ds, omega_raw, omega_corr, cat_var=cat_var)

    args.out.mkdir(parents=True, exist_ok=True)
    path1 = args.out / "omega_ramp_comparison_spaghetti.png"
    fig1.savefig(path1, dpi=200, bbox_inches="tight")
    print(f"Saved → {path1}")

    # ── Figure 2: overlay means ──────────────────────────────────────────
    print("Generating overlay comparison figure …")
    fig2 = make_overlay_figure(ds, omega_raw, omega_corr, cat_var=cat_var)

    path2 = args.out / "omega_ramp_comparison_overlay.png"
    fig2.savefig(path2, dpi=200, bbox_inches="tight")
    print(f"Saved → {path2}")

    if args.show:
        plt.show()

    print("Done.")


if __name__ == "__main__":
    main()
