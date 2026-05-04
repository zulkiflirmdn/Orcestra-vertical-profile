#!/usr/bin/env python3
"""
ERA5 Omega vs BEACH Omega — Spaghetti & Individual Comparison
=============================================================

Compares ERA5 reanalysis vertical velocity with BEACH L4 dropsonde-derived
omega profiles.  Left column = BEACH omega; right column = ERA5 omega.
An overlay figure shows both means on the same axes so the difference in
profile shape is immediately visible.

Figures generated
-----------------
1. omega_era5_beach_spaghetti.png      — 4-row × 2-col, rows=category groups
2. omega_era5_beach_overlay.png        — 3-panel mean comparison per category
3. omega_era5_beach_individual_<cat>.png  — per-circle grid, BEACH vs ERA5 overlaid

Usage
-----
    python scripts/plot_era5_beach_comparison.py
    python scripts/plot_era5_beach_comparison.py --show
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.mse_budget import load_dataset
from scripts.era5_extension import load_era5_omega, match_era5_to_circle

# ---------------------------------------------------------------------------
# Constants
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

# Full column: surface (~1050 hPa) to ERA5 top (20 hPa), in Pa, inverted
X_LIM      = (-0.8, 0.4)      # Pa s⁻¹
Y_LIM_FULL = (105000, 2000)   # Pa, inverted (surface at bottom)
Y_LIM_BEACH = (105000, 10000) # Pa, inverted (BEACH domain only)

OUTPUT_DIR = Path("/home/565/zr7147/Proj/outputs/figures")


# ---------------------------------------------------------------------------
# Pre-compute ERA5 profiles for all circles
# ---------------------------------------------------------------------------

def collect_era5_profiles(ds, era5_ds):
    """
    Match ERA5 omega to every circle in ds.

    Returns
    -------
    omega_e_list : list[ndarray or None]   Pa s⁻¹  per circle, ERA5 levels
    p_e_list     : list[ndarray or None]   Pa      per circle, ERA5 levels
    """
    ncircle = ds.sizes["circle"]
    omega_e_list = []
    p_e_list = []

    print(f"  Matching ERA5 to {ncircle} circles …")
    for i in range(ncircle):
        try:
            om_e, p_e, _, _ = match_era5_to_circle(
                era5_ds,
                float(ds["circle_lat"].values[i]),
                float(ds["circle_lon"].values[i]),
                ds["circle_time"].values[i],
            )
            omega_e_list.append(om_e)
            p_e_list.append(p_e)
        except Exception:
            omega_e_list.append(None)
            p_e_list.append(None)

    n_ok = sum(x is not None for x in omega_e_list)
    print(f"  ERA5 matched for {n_ok}/{ncircle} circles")
    return omega_e_list, p_e_list


# ---------------------------------------------------------------------------
# Spaghetti panel helpers
# ---------------------------------------------------------------------------

def _beach_panel(ax, omega_2d, p_2d, mean_color, title, *, show_ylabel=True):
    """Spaghetti panel for BEACH omega (on altitude/pressure grid)."""
    n = omega_2d.shape[0]
    for k in range(n):
        valid = np.isfinite(omega_2d[k]) & np.isfinite(p_2d[k])
        if valid.sum() < 3:
            continue
        ax.plot(omega_2d[k, valid], p_2d[k, valid],
                color="gray", alpha=0.20, lw=0.9, zorder=2)

    mean_o = np.nanmean(omega_2d, axis=0)
    mean_p = np.nanmean(p_2d, axis=0)
    valid_m = np.isfinite(mean_o) & np.isfinite(mean_p)
    ax.plot(mean_o[valid_m], mean_p[valid_m],
            color=mean_color, lw=3.5, zorder=3, label="Mean")

    ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.7)
    ax.set_xlim(X_LIM)
    ax.set_ylim(Y_LIM_FULL)
    ax.set_xlabel("ω  (Pa s⁻¹)", fontsize=10)
    if show_ylabel:
        ax.set_ylabel("Pressure (Pa)", fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold", color=mean_color)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.25)


def _era5_panel(ax, omega_list, p_list, cat_mask, mean_color, title,
                *, show_ylabel=False):
    """Spaghetti panel for ERA5 omega (discrete pressure levels, list of arrays)."""
    indices = np.where(cat_mask)[0]

    # Collect valid ERA5 profiles for this category
    om_valid = [omega_list[i] for i in indices if omega_list[i] is not None]
    p_valid  = [p_list[i]     for i in indices if p_list[i]  is not None]

    if not om_valid:
        ax.set_visible(False)
        return

    for om_k, p_k in zip(om_valid, p_valid):
        valid = np.isfinite(om_k) & np.isfinite(p_k)
        if valid.sum() < 3:
            continue
        ax.plot(om_k[valid], p_k[valid],
                color=mean_color, alpha=0.18, lw=0.9, zorder=2)

    # Mean — stack onto a common level grid (ERA5 levels are the same for all)
    # Safe: all ERA5 profiles share the same pressure levels
    om_arr = np.array(om_valid)   # (n_circles, n_levels)
    p_arr  = np.array(p_valid)
    mean_o = np.nanmean(om_arr, axis=0)
    mean_p = np.nanmean(p_arr, axis=0)
    valid_m = np.isfinite(mean_o) & np.isfinite(mean_p)
    ax.plot(mean_o[valid_m], mean_p[valid_m],
            color=mean_color, lw=3.5, zorder=3, label="Mean")

    ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.7)
    ax.set_xlim(X_LIM)
    ax.set_ylim(Y_LIM_FULL)
    ax.set_xlabel("ω  (Pa s⁻¹)", fontsize=10)
    if show_ylabel:
        ax.set_ylabel("Pressure (Pa)", fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold", color=mean_color)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.25)


# ---------------------------------------------------------------------------
# Figure 1: side-by-side spaghetti
# ---------------------------------------------------------------------------

def make_spaghetti_figure(ds, omega_e_list, p_e_list, cat_var="category_avg"):
    """4-row × 2-col spaghetti comparison: left=BEACH, right=ERA5."""
    n_groups = len(CATEGORY_GROUPS) + 1
    fig, axes = plt.subplots(n_groups, 2,
                             figsize=(14, 6 * n_groups), sharey=True)
    fig.suptitle(
        "Omega Spaghetti — BEACH (left) vs ERA5 (right)\n",
        fontsize=16, fontweight="bold",
    )

    omega_raw = ds["omega"].values
    p_all     = ds["p_mean"].values

    for row, (label, cfg) in enumerate(CATEGORY_GROUPS.items()):
        if cat_var in ds:
            cat_mask = np.isin(ds[cat_var].values, cfg["cats"])
        else:
            cat_mask = np.ones(ds.sizes["circle"], dtype=bool)

        n = int(cat_mask.sum())
        col = cfg["color"]

        if n == 0:
            for c in range(2):
                axes[row, c].set_visible(False)
            continue

        _beach_panel(
            axes[row, 0], omega_raw[cat_mask], p_all[cat_mask], col,
            f"{label}  — BEACH  ({n} circles)",
            show_ylabel=True,
        )
        _era5_panel(
            axes[row, 1], omega_e_list, p_e_list, cat_mask, col,
            f"{label}  — ERA5  ({n} circles)",
            show_ylabel=False,
        )

    # All-circles row
    row_all = n_groups - 1
    n_all   = ds.sizes["circle"]
    all_mask = np.ones(n_all, dtype=bool)

    _beach_panel(
        axes[row_all, 0], omega_raw, p_all, "#333333",
        f"All Circles — BEACH  ({n_all} circles)",
        show_ylabel=True,
    )
    _era5_panel(
        axes[row_all, 1], omega_e_list, p_e_list, all_mask, "#333333",
        f"All Circles — ERA5  ({n_all} circles)",
        show_ylabel=False,
    )

    axes[0, 0].annotate(
        "BEACH L4  ω", xy=(0.5, 1.22), xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )
    axes[0, 1].annotate(
        "ERA5  ω", xy=(0.5, 1.22), xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


# ---------------------------------------------------------------------------
# Figure 2: overlay means (BEACH vs ERA5) per category
# ---------------------------------------------------------------------------

def make_overlay_figure(ds, omega_e_list, p_e_list, cat_var="category_avg"):
    """One panel per category — BEACH mean (dashed) vs ERA5 mean (solid)."""
    fig, axes = plt.subplots(1, len(CATEGORY_GROUPS),
                             figsize=(16, 8), sharey=True)
    fig.suptitle(
        "Mean Omega Profile — BEACH vs ERA5\n",
        fontsize=15, fontweight="bold",
    )

    omega_raw = ds["omega"].values
    p_all     = ds["p_mean"].values

    for ax, (label, cfg) in zip(axes, CATEGORY_GROUPS.items()):
        if cat_var in ds:
            cat_mask = np.isin(ds[cat_var].values, cfg["cats"])
        else:
            cat_mask = np.ones(ds.sizes["circle"], dtype=bool)

        n   = int(cat_mask.sum())
        col = cfg["color"]

        if n == 0:
            ax.set_visible(False)
            continue

        # BEACH mean (dashed)
        mean_beach = np.nanmean(omega_raw[cat_mask], axis=0)
        mean_p_b   = np.nanmean(p_all[cat_mask], axis=0)
        valid_b    = np.isfinite(mean_beach) & np.isfinite(mean_p_b)
        ax.plot(mean_beach[valid_b], mean_p_b[valid_b],
                color=col, lw=2.5, ls="--", alpha=0.85, label="BEACH")

        # ERA5 mean (solid)
        indices  = np.where(cat_mask)[0]
        om_valid = [omega_e_list[i] for i in indices if omega_e_list[i] is not None]
        p_valid  = [p_e_list[i]     for i in indices if p_e_list[i]  is not None]
        if om_valid:
            om_arr  = np.array(om_valid)
            p_arr   = np.array(p_valid)
            mean_e  = np.nanmean(om_arr, axis=0)
            mean_pe = np.nanmean(p_arr, axis=0)
            valid_e = np.isfinite(mean_e) & np.isfinite(mean_pe)
            ax.plot(mean_e[valid_e], mean_pe[valid_e],
                    color=col, lw=3.0, ls="-", label="ERA5")

            # Shade difference in overlap pressure range
            # Interpolate BEACH mean to ERA5 pressure levels for shading
            p_shade  = mean_pe[valid_e]
            om_e_sh  = mean_e[valid_e]
            om_b_sh  = np.interp(p_shade, mean_p_b[valid_b][::-1],
                                 mean_beach[valid_b][::-1])
            ax.fill_betweenx(p_shade, om_b_sh, om_e_sh,
                             alpha=0.12, color=col)

        ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.7)
        ax.set_xlim(X_LIM)
        ax.set_ylim(Y_LIM_FULL)
        ax.set_xlabel("ω  (Pa s⁻¹)", fontsize=10)
        ax.set_title(f"{label}\n({n} circles)", fontsize=11,
                     fontweight="bold", color=col)
        ax.legend(fontsize=9, loc="upper right")
        ax.grid(True, alpha=0.25)

    axes[0].set_ylabel("Pressure (Pa)", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return fig


# ---------------------------------------------------------------------------
# Figure 3+: individual circle grids — BEACH vs ERA5 overlaid
# ---------------------------------------------------------------------------

def make_individual_grid(ds, omega_e_list, p_e_list, cat_label, cat_circles,
                         group_color):
    """
    One subplot per circle — BEACH (dashed gray) vs ERA5 (solid colored).
    """
    n = len(cat_circles)
    if n == 0:
        return None

    ncols = min(5, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(4 * ncols, 4.5 * nrows),
        sharey=True, sharex=True,
    )
    fig.suptitle(
        f"{cat_label} — Individual Circles: BEACH vs ERA5\n",
        fontsize=15, fontweight="bold", color=group_color,
    )

    omega_raw = ds["omega"].values
    p_all     = ds["p_mean"].values
    circle_vals = ds["circle"].values
    axes_flat = np.atleast_1d(axes).ravel()

    for idx, ax in enumerate(axes_flat):
        if idx >= n:
            ax.set_visible(False)
            continue

        c  = cat_circles[idx]
        ci = int(np.where(circle_vals == c)[0][0])

        p_hpa  = p_all[ci]
        o_raw  = omega_raw[ci]

        # BEACH
        valid_b = np.isfinite(o_raw) & np.isfinite(p_hpa)
        if valid_b.sum() >= 3:
            ax.plot(o_raw[valid_b], p_hpa[valid_b],
                    color="gray", ls="--", lw=1.5, alpha=0.8, label="BEACH")

        # ERA5
        om_e = omega_e_list[ci]
        p_e  = p_e_list[ci]
        if om_e is not None:
            valid_e = np.isfinite(om_e) & np.isfinite(p_e)
            if valid_e.sum() >= 3:
                ax.plot(om_e[valid_e], p_e[valid_e],
                        color=group_color, ls="-", lw=2.0, ms=4,
                        marker="o", label="ERA5")

        ax.axvline(0, color="black", lw=0.6, ls="--", alpha=0.5)

        try:
            ctime = str(ds["circle_time"].sel(circle=c).values)[:16]
        except Exception:
            ctime = ""
        ax.set_title(f"Circle {c}\n{ctime}", fontsize=8, color=group_color)
        ax.set_xlim(X_LIM)
        ax.set_ylim(Y_LIM_FULL)
        ax.grid(True, alpha=0.2)

        if idx == 0:
            ax.legend(fontsize=7, loc="upper right")

    for ax in axes_flat:
        if ax.get_visible():
            ax.set_xlabel("ω (Pa s⁻¹)", fontsize=8)
    for r in range(nrows):
        row_ax = axes_flat[r * ncols] if r * ncols < len(axes_flat) else None
        if row_ax is not None and row_ax.get_visible():
            row_ax.set_ylabel("Pressure (Pa)", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ERA5 omega vs BEACH omega comparison figures"
    )
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR,
                        help="Output directory")
    args = parser.parse_args()

    print("Loading BEACH L4 dataset …")
    ds = load_dataset()

    print("Loading ERA5 omega …")
    era5_ds = load_era5_omega()

    print("Matching ERA5 to each circle …")
    omega_e_list, p_e_list = collect_era5_profiles(ds, era5_ds)

    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    print(f"Using category variable: {cat_var}")

    args.out.mkdir(parents=True, exist_ok=True)

    # Figure 1: spaghetti
    print("Generating spaghetti comparison figure …")
    fig1 = make_spaghetti_figure(ds, omega_e_list, p_e_list, cat_var=cat_var)
    p1 = args.out / "omega_era5_beach_spaghetti.png"
    fig1.savefig(p1, dpi=200, bbox_inches="tight")
    plt.close(fig1)
    print(f"Saved → {p1}")

    # Figure 2: overlay means
    print("Generating overlay figure …")
    fig2 = make_overlay_figure(ds, omega_e_list, p_e_list, cat_var=cat_var)
    p2 = args.out / "omega_era5_beach_overlay.png"
    fig2.savefig(p2, dpi=200, bbox_inches="tight")
    plt.close(fig2)
    print(f"Saved → {p2}")

    # Figure 3+: individual circle grids per category
    print("Generating individual circle grids …")
    for label, cfg in CATEGORY_GROUPS.items():
        safe_label = label.replace("\n", "_").replace(" ", "_").replace("/", "")
        if cat_var in ds:
            cat_mask = np.isin(ds[cat_var].values, cfg["cats"])
        else:
            cat_mask = np.ones(ds.sizes["circle"], dtype=bool)

        circles = ds["circle"].values[cat_mask]
        n = len(circles)
        if n == 0:
            continue

        print(f"  {label}: {n} circles")
        fig_ind = make_individual_grid(
            ds, omega_e_list, p_e_list,
            label, circles, cfg["color"],
        )
        if fig_ind is not None:
            p_ind = args.out / f"omega_era5_beach_individual_{safe_label}.png"
            fig_ind.savefig(p_ind, dpi=180, bbox_inches="tight")
            plt.close(fig_ind)
            print(f"  Saved → {p_ind}")

    if args.show:
        plt.show()

    print("Done.")


if __name__ == "__main__":
    main()
