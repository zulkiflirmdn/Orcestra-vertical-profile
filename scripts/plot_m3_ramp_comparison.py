#!/usr/bin/env python3
"""
Omega Profile Comparison — Before vs After M3 (ERA5-Anchored) Ramp Correction
==============================================================================

Mirrors the structure of plot_ramp_comparison.py but uses Method 3 (M3) instead
of the simple linear mass-conservation ramp.

M3 applies an O'Brien ramp that forces BEACH omega_top → ERA5 omega at the
junction pressure, rather than forcing omega_top → 0.  This makes the BEACH
profile continuous with ERA5 above, without imposing a false zero boundary.

Left column  : raw BEACH omega profiles (before M3 ramp)
Right column : M3-corrected BEACH omega profiles (after M3 ramp)

Each row corresponds to one category group (Top-Heavy, Bottom-Heavy,
Inactive/Suppressed), plus a final "All Circles" row.

Usage
-----
    python scripts/plot_m3_ramp_comparison.py
    python scripts/plot_m3_ramp_comparison.py --show
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
from scripts.era5_extension import load_era5_omega, apply_era5_anchored_correction

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

X_LIM = (-1.0, 0.5)       # Pa s⁻¹
Y_LIM = (105000, 10000)    # Pa, inverted (surface to ~100 hPa)

OUTPUT_DIR = Path("/home/565/zr7147/Proj/outputs/figures")


# ---------------------------------------------------------------------------
# Plotting helpers (same structure as plot_ramp_comparison.py)
# ---------------------------------------------------------------------------

def _spaghetti_panel(ax, omega_2d, p_2d, mean_color, title, *, show_ylabel=True):
    """Thin gray spaghetti + thick colored mean."""
    n_circles = omega_2d.shape[0]

    for k in range(n_circles):
        o_k = omega_2d[k]
        p_k = p_2d[k]
        valid = np.isfinite(o_k) & np.isfinite(p_k)
        if valid.sum() < 3:
            continue
        ax.plot(o_k[valid], p_k[valid],
                color="gray", alpha=0.22, lw=0.9, zorder=2)

    mean_omega = np.nanmean(omega_2d, axis=0)
    mean_p     = np.nanmean(p_2d, axis=0)
    valid_mean = np.isfinite(mean_omega) & np.isfinite(mean_p)
    ax.plot(mean_omega[valid_mean], mean_p[valid_mean],
            color=mean_color, lw=3.5, zorder=3, label="Mean")

    ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.7)
    ax.set_xlim(X_LIM)
    ax.set_ylim(Y_LIM)
    ax.set_xlabel("Vertical Velocity ω  (Pa s⁻¹)", fontsize=10)
    if show_ylabel:
        ax.set_ylabel("Pressure (Pa)", fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold", color=mean_color)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.25)


# ---------------------------------------------------------------------------
# Figure 1: side-by-side spaghetti (before vs after M3)
# ---------------------------------------------------------------------------

def make_comparison_figure(ds, omega_raw, omega_m3, cat_var="category_avg"):
    """4-row × 2-col: left=raw BEACH, right=M3-corrected BEACH."""
    n_groups = len(CATEGORY_GROUPS) + 1
    fig, axes = plt.subplots(n_groups, 2,
                             figsize=(14, 6 * n_groups), sharey=True)
    fig.suptitle(
        "Omega Profile — Before vs After M3 (ERA5-Anchored) Ramp Correction\n",
        fontsize=16, fontweight="bold",
    )

    p_all = ds["p_mean"].values

    for row, (label, cfg) in enumerate(CATEGORY_GROUPS.items()):
        if cat_var in ds:
            cat_mask = np.isin(ds[cat_var].values, cfg["cats"])
        else:
            cat_mask = np.ones(ds.sizes["circle"], dtype=bool)

        n   = int(cat_mask.sum())
        col = cfg["color"]

        if n == 0:
            for c in range(2):
                axes[row, c].set_visible(False)
            continue

        _spaghetti_panel(
            axes[row, 0], omega_raw[cat_mask], p_all[cat_mask], col,
            f"{label}  — BEFORE M3  ({n} circles)",
            show_ylabel=True,
        )
        _spaghetti_panel(
            axes[row, 1], omega_m3[cat_mask], p_all[cat_mask], col,
            f"{label}  — AFTER M3  ({n} circles)",
            show_ylabel=False,
        )

    row_all = n_groups - 1
    n_all   = ds.sizes["circle"]
    _spaghetti_panel(
        axes[row_all, 0], omega_raw, p_all, "#333333",
        f"All Circles — BEFORE M3  ({n_all} circles)",
        show_ylabel=True,
    )
    _spaghetti_panel(
        axes[row_all, 1], omega_m3, p_all, "#333333",
        f"All Circles — AFTER M3  ({n_all} circles)",
        show_ylabel=False,
    )

    axes[0, 0].annotate(
        "Raw BEACH ω  (before M3)", xy=(0.5, 1.22), xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )
    axes[0, 1].annotate(
        "M3-Corrected ω  (ERA5-anchored ramp)", xy=(0.5, 1.22),
        xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


# ---------------------------------------------------------------------------
# Figure 2: overlay means (before vs after M3)
# ---------------------------------------------------------------------------

def make_overlay_figure(ds, omega_raw, omega_m3, cat_var="category_avg"):
    """One panel per category — raw mean (dashed) vs M3 mean (solid)."""
    fig, axes = plt.subplots(1, len(CATEGORY_GROUPS), figsize=(16, 8), sharey=True)
    fig.suptitle(
        "Effect of M3 (ERA5-Anchored) Ramp Correction on Mean Omega Profile\n",
        fontsize=15, fontweight="bold",
    )

    p_all = ds["p_mean"].values

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

        p_g = p_all[cat_mask]
        mean_p = np.nanmean(p_g, axis=0)

        mean_raw = np.nanmean(omega_raw[cat_mask], axis=0)
        mean_m3  = np.nanmean(omega_m3[cat_mask], axis=0)

        valid_raw = np.isfinite(mean_raw) & np.isfinite(mean_p)
        valid_m3  = np.isfinite(mean_m3)  & np.isfinite(mean_p)

        ax.plot(mean_raw[valid_raw], mean_p[valid_raw],
                color=col, lw=2.5, ls="--", alpha=0.7, label="Before M3")
        ax.plot(mean_m3[valid_m3], mean_p[valid_m3],
                color=col, lw=3.0, ls="-", label="After M3")

        shared = valid_raw & valid_m3
        ax.fill_betweenx(
            mean_p[shared], mean_raw[shared], mean_m3[shared],
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

    axes[0].set_ylabel("Pressure (Pa)", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return fig


# ---------------------------------------------------------------------------
# Figure 3+: individual circle grid — before vs after M3, with junction
# ---------------------------------------------------------------------------

def make_individual_grid(ds, omega_raw, omega_m3, delta_div,
                         cat_label, cat_circles, group_color):
    """
    One subplot per circle.
      • dashed gray   = raw BEACH ω (before M3)
      • solid colored = M3-corrected ω (after M3 ramp)

    An annotation shows the junction mismatch removed by M3 (Δω = delta_om).
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
        f"{cat_label} — Individual Circles: Before vs After M3 Ramp\n",
        fontsize=15, fontweight="bold", color=group_color,
    )

    p_all       = ds["p_mean"].values
    axes_flat   = np.atleast_1d(axes).ravel()
    circle_vals = ds["circle"].values

    for idx, ax in enumerate(axes_flat):
        if idx >= n:
            ax.set_visible(False)
            continue

        c  = cat_circles[idx]
        ci = int(np.where(circle_vals == c)[0][0])

        p_k    = p_all[ci]
        o_raw  = omega_raw[ci]
        o_m3   = omega_m3[ci]

        valid_raw = np.isfinite(o_raw) & np.isfinite(p_k)
        valid_m3  = np.isfinite(o_m3)  & np.isfinite(p_k)

        ax.plot(o_raw[valid_raw], p_k[valid_raw],
                color="gray", ls="--", lw=1.5, alpha=0.7, label="Before")
        ax.plot(o_m3[valid_m3], p_k[valid_m3],
                color=group_color, ls="-", lw=2.0, label="After M3")

        ax.axvline(0, color="black", lw=0.6, ls="--", alpha=0.5)

        # Annotate the top of the raw profile (junction point)
        if valid_raw.sum() >= 3:
            top_idx = np.where(valid_raw)[0][-1]
            om_top  = o_raw[top_idx]
            p_top   = p_k[top_idx]
            ax.plot(om_top, p_top, "x", color="red", ms=7, mew=2, zorder=5)
            ax.annotate(
                f"ω_top={om_top:.3f}",
                xy=(om_top, p_top), xytext=(8, 8),
                textcoords="offset points", fontsize=7,
                color="red", fontweight="bold",
            )

        # Annotate junction correction if available
        dd = delta_div[ci]
        if np.isfinite(dd):
            ax.text(
                0.97, 0.04, f"Δdiv={dd:.2e} s⁻¹",
                transform=ax.transAxes, fontsize=6,
                ha="right", va="bottom", color="purple",
            )

        try:
            ctime = str(ds["circle_time"].sel(circle=c).values)[:16]
        except Exception:
            ctime = ""
        ax.set_title(f"Circle {c}\n{ctime}", fontsize=8, color=group_color)
        ax.set_xlim(X_LIM)
        ax.set_ylim(Y_LIM)
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
        description="Omega spaghetti: before vs after M3 ERA5-anchored ramp"
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

    print("Applying M3 (ERA5-anchored O'Brien ramp) correction …")
    ds_corr, delta_div = apply_era5_anchored_correction(ds, era5_ds=era5_ds)

    omega_raw = ds["omega"].values.copy()
    omega_m3  = ds_corr["omega"].values.copy()

    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    print(f"Using category variable: {cat_var}")

    args.out.mkdir(parents=True, exist_ok=True)

    # Figure 1: spaghetti comparison
    print("Generating spaghetti comparison figure …")
    fig1 = make_comparison_figure(ds, omega_raw, omega_m3, cat_var=cat_var)
    p1 = args.out / "omega_m3_ramp_comparison_spaghetti.png"
    fig1.savefig(p1, dpi=200, bbox_inches="tight")
    plt.close(fig1)
    print(f"Saved → {p1}")

    # Figure 2: overlay means
    print("Generating overlay comparison figure …")
    fig2 = make_overlay_figure(ds, omega_raw, omega_m3, cat_var=cat_var)
    p2 = args.out / "omega_m3_ramp_comparison_overlay.png"
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
            ds, omega_raw, omega_m3, delta_div,
            label, circles, cfg["color"],
        )
        if fig_ind is not None:
            p_ind = args.out / f"omega_m3_ramp_individual_{safe_label}.png"
            fig_ind.savefig(p_ind, dpi=180, bbox_inches="tight")
            plt.close(fig_ind)
            print(f"  Saved → {p_ind}")

    if args.show:
        plt.show()

    print("Done.")


if __name__ == "__main__":
    main()
