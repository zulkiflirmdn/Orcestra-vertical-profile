#!/usr/bin/env python3
"""
Omega Profile Comparison — Raw BEACH vs M4 (Cosine Blend + ERA5 Extension)
===========================================================================

Left column  : raw BEACH L4 omega profiles (no upper-boundary correction).
Right column : M4-corrected profiles — cosine blend in the top 50 hPa of the
               BEACH column + ERA5 extension to the ERA5 data top (~20 hPa).

All profiles are box-averaged onto a 500 Pa pressure grid before plotting.
This removes sub-hPa altitude-grid noise (the BEACH column has ~3–4 Pa per
10 m level near 200 hPa, so a 50 hPa blend zone contains ~1 200 raw levels),
while the ERA5 extension is already at 500 Pa spacing and maps cleanly to the
same grid.

Usage
-----
    python scripts/plot_ramp_comparison.py              # saves to outputs/figures/
    python scripts/plot_ramp_comparison.py --show       # also display interactively
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.mse_budget import load_dataset
from scripts.era5_extension import load_era5_omega, blend_beach_era5

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

X_LIM   = (-1.0, 0.5)       # Pa s⁻¹
Y_LIM   = (105000, 2000)     # Pa, inverted (surface at bottom, ERA5 top ~20 hPa)
BIN_PA  = 500.0              # pressure bin width for noise-free visualization

# Common pressure grid shared by all panels (ascending, for np.interp)
P_COMMON = np.arange(2000.0, 105500.0, BIN_PA)   # 207 levels

OUTPUT_DIR = Path("/home/565/zr7147/Proj/outputs/figures")


# ---------------------------------------------------------------------------
# Pressure-binning helper
# ---------------------------------------------------------------------------

def _bin_profile(omega, p):
    """
    Box-average omega onto P_COMMON (500 Pa grid).

    Each 500 Pa pressure bin is filled with the mean of all data points that
    fall in that bin.  Bins with no data → NaN.  The result is on P_COMMON so
    all profiles share the same pressure axis.

    Parameters
    ----------
    omega : 1-D array  Pa s⁻¹
    p     : 1-D array  Pa  (same length as omega, any order)

    Returns
    -------
    om_on_common : (len(P_COMMON),) array  — NaN where no data
    """
    valid = np.isfinite(omega) & np.isfinite(p)
    if valid.sum() < 3:
        return np.full(len(P_COMMON), np.nan)

    p_v, o_v = p[valid], omega[valid]

    # Bin edges aligned to BIN_PA
    p_lo  = np.floor(p_v.min() / BIN_PA) * BIN_PA
    p_hi  = np.ceil( p_v.max() / BIN_PA) * BIN_PA + BIN_PA
    edges = np.arange(p_lo, p_hi, BIN_PA)
    if len(edges) < 2:
        return np.full(len(P_COMMON), np.nan)

    o_sum, _ = np.histogram(p_v, bins=edges, weights=o_v)
    count, _ = np.histogram(p_v, bins=edges)
    p_ctr    = edges[:-1] + BIN_PA / 2.0
    result   = np.where(count > 0, o_sum / count, np.nan)

    # Interpolate the binned values to P_COMMON
    has = count > 0
    if has.sum() < 2:
        return np.full(len(P_COMMON), np.nan)

    om_on_common = np.interp(P_COMMON, p_ctr[has], result[has],
                             left=np.nan, right=np.nan)
    return om_on_common


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _spaghetti_panel(ax, omega_2d, p_2d, mean_color, title, *, show_ylabel=True):
    """
    Thin gray spaghetti + thick colored mean, both on the 500 Pa grid.

    Parameters
    ----------
    omega_2d : (n_circles, n_levels)  Pa s⁻¹
    p_2d     : (n_circles, n_levels)  Pa
    """
    n_circles = omega_2d.shape[0]
    binned = []

    for k in range(n_circles):
        ob = _bin_profile(omega_2d[k], p_2d[k])
        valid = np.isfinite(ob)
        if valid.sum() < 3:
            continue
        ax.plot(ob[valid], P_COMMON[valid],
                color="gray", alpha=0.22, lw=0.9, zorder=2)
        binned.append(ob)

    if binned:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_o = np.nanmean(np.stack(binned), axis=0)
        valid_m = np.isfinite(mean_o)
        ax.plot(mean_o[valid_m], P_COMMON[valid_m],
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
# Figure 1: side-by-side spaghetti (raw BEACH vs M4 + ERA5)
# ---------------------------------------------------------------------------

def make_comparison_figure(ds, omega_raw, p_raw, omega_m4, p_m4,
                           cat_var="category_avg"):
    """4-row × 2-col: left = raw BEACH, right = M4 blended + ERA5 extended."""
    n_groups = len(CATEGORY_GROUPS) + 1
    fig, axes = plt.subplots(n_groups, 2,
                             figsize=(14, 6 * n_groups), sharey=True)
    fig.suptitle(
        "Omega Profile — Raw BEACH vs M4 (Cosine Blend + ERA5 Extension)\n"
        "profiles box-averaged to 500 Pa for noise-free comparison",
        fontsize=15, fontweight="bold",
    )

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
            axes[row, 0], omega_raw[cat_mask], p_raw[cat_mask], col,
            f"{label}  — Raw BEACH  ({n} circles)",
            show_ylabel=True,
        )
        _spaghetti_panel(
            axes[row, 1], omega_m4[cat_mask], p_m4[cat_mask], col,
            f"{label}  — M4 + ERA5  ({n} circles)",
            show_ylabel=False,
        )

    row_all = n_groups - 1
    n_all   = ds.sizes["circle"]
    _spaghetti_panel(
        axes[row_all, 0], omega_raw, p_raw, "#333333",
        f"All Circles — Raw BEACH  ({n_all} circles)",
        show_ylabel=True,
    )
    _spaghetti_panel(
        axes[row_all, 1], omega_m4, p_m4, "#333333",
        f"All Circles — M4 + ERA5  ({n_all} circles)",
        show_ylabel=False,
    )

    axes[0, 0].annotate(
        "Raw BEACH ω  (no correction)", xy=(0.5, 1.22),
        xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )
    axes[0, 1].annotate(
        "M4: Cosine Blend + ERA5 Extension", xy=(0.5, 1.22),
        xycoords="axes fraction",
        fontsize=13, fontweight="bold", ha="center", color="#444444",
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


# ---------------------------------------------------------------------------
# Figure 2: overlay means (raw BEACH vs M4 + ERA5)
# ---------------------------------------------------------------------------

def make_overlay_figure(ds, omega_raw, p_raw, omega_m4, p_m4,
                        cat_var="category_avg"):
    """One panel per category — raw mean (dashed) vs M4 + ERA5 mean (solid)."""
    fig, axes = plt.subplots(1, len(CATEGORY_GROUPS), figsize=(16, 8), sharey=True)
    fig.suptitle(
        "Mean Omega Profile — Raw BEACH vs M4 (Cosine Blend + ERA5)\n"
        "profiles box-averaged to 500 Pa",
        fontsize=14, fontweight="bold",
    )

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

        # Bin every circle then average over circles on P_COMMON
        raw_binned = [_bin_profile(omega_raw[i], p_raw[i])
                      for i in np.where(cat_mask)[0]]
        m4_binned  = [_bin_profile(omega_m4[i],  p_m4[i])
                      for i in np.where(cat_mask)[0]]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_raw = np.nanmean(np.stack(raw_binned), axis=0)
            mean_m4  = np.nanmean(np.stack(m4_binned),  axis=0)

        valid_r = np.isfinite(mean_raw)
        valid_m = np.isfinite(mean_m4)

        ax.plot(mean_raw[valid_r], P_COMMON[valid_r],
                color=col, lw=2.5, ls="--", alpha=0.7, label="Raw BEACH")
        ax.plot(mean_m4[valid_m], P_COMMON[valid_m],
                color=col, lw=3.0, ls="-", label="M4 + ERA5")

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
# Figure 3+: individual circle grid — raw BEACH vs M4 on same axes
# ---------------------------------------------------------------------------

def make_individual_grid(ds, omega_raw, p_raw, omega_m4, p_m4,
                         cat_label, cat_circles, group_color):
    """
    One subplot per circle.
      • dashed gray    = raw BEACH ω (binned to 500 Pa, stops at BEACH top)
      • solid colored  = M4 + ERA5 ω (binned to 500 Pa, continues to ERA5 top)
      • red ×          = raw BEACH top (where obs data ends)
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
        f"{cat_label} — Individual Circles: Raw BEACH vs M4 + ERA5\n"
        "(500 Pa pressure bins)",
        fontsize=14, fontweight="bold", color=group_color,
    )

    circle_vals = ds["circle"].values
    axes_flat   = np.atleast_1d(axes).ravel()

    for idx, ax in enumerate(axes_flat):
        if idx >= n:
            ax.set_visible(False)
            continue

        c  = cat_circles[idx]
        ci = int(np.where(circle_vals == c)[0][0])

        # Bin profiles onto P_COMMON
        ob_raw = _bin_profile(omega_raw[ci], p_raw[ci])
        ob_m4  = _bin_profile(omega_m4[ci],  p_m4[ci])

        valid_r = np.isfinite(ob_raw)
        valid_m = np.isfinite(ob_m4)

        ax.plot(ob_raw[valid_r], P_COMMON[valid_r],
                color="gray", ls="--", lw=1.5, alpha=0.7, label="Raw BEACH")
        ax.plot(ob_m4[valid_m], P_COMMON[valid_m],
                color=group_color, ls="-", lw=2.0, label="M4 + ERA5")

        ax.axvline(0, color="black", lw=0.6, ls="--", alpha=0.5)

        # Mark the raw BEACH top (highest pressure bin with raw data)
        if valid_r.sum() >= 1:
            top_bin_idx = np.where(valid_r)[0][0]   # lowest pressure = first bin
            p_top_bin   = P_COMMON[top_bin_idx]
            o_top_bin   = ob_raw[top_bin_idx]
            ax.plot(o_top_bin, p_top_bin,
                    "x", color="red", ms=7, mew=2, zorder=5)
            ax.annotate(
                f"{p_top_bin/100:.0f} hPa",
                xy=(o_top_bin, p_top_bin), xytext=(6, 6),
                textcoords="offset points", fontsize=7,
                color="red", fontweight="bold",
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
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Omega spaghetti: raw BEACH vs M4 cosine blend + ERA5 extension"
    )
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively (in addition to saving)")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR,
                        help="Output directory for saved figures")
    args = parser.parse_args()

    print("Loading BEACH L4 dataset …")
    ds = load_dataset()

    print("Loading ERA5 omega …")
    era5_ds = load_era5_omega()

    print("Computing M4 cosine blend + ERA5 extension …")
    ds_ext = blend_beach_era5(ds, era5_ds=era5_ds)

    omega_raw = ds['omega'].values          # (circle, altitude) Pa s⁻¹ — raw BEACH
    p_raw     = ds['p_mean'].values         # (circle, altitude) Pa

    omega_m4  = ds_ext['omega_ext'].values  # (circle, ext_level) Pa s⁻¹ — M4 + ERA5
    p_m4      = ds_ext['p_ext'].values      # (circle, ext_level) Pa

    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    print(f"Using category variable: {cat_var}")

    args.out.mkdir(parents=True, exist_ok=True)

    # ── Figure 1: side-by-side spaghetti ─────────────────────────────────
    print("Generating spaghetti comparison figure …")
    fig1 = make_comparison_figure(ds, omega_raw, p_raw, omega_m4, p_m4,
                                  cat_var=cat_var)
    path1 = args.out / "omega_m4_ramp_comparison_spaghetti.png"
    fig1.savefig(path1, dpi=200, bbox_inches="tight")
    plt.close(fig1)
    print(f"Saved → {path1}")

    # ── Figure 2: overlay means ──────────────────────────────────────────
    print("Generating overlay comparison figure …")
    fig2 = make_overlay_figure(ds, omega_raw, p_raw, omega_m4, p_m4,
                               cat_var=cat_var)
    path2 = args.out / "omega_m4_ramp_comparison_overlay.png"
    fig2.savefig(path2, dpi=200, bbox_inches="tight")
    plt.close(fig2)
    print(f"Saved → {path2}")

    # ── Figure 3+: individual circle grids per category ──────────────────
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
            ds, omega_raw, p_raw, omega_m4, p_m4,
            label, circles, cfg["color"],
        )
        if fig_ind is not None:
            path_ind = args.out / f"omega_m4_ramp_individual_{safe_label}.png"
            fig_ind.savefig(path_ind, dpi=180, bbox_inches="tight")
            plt.close(fig_ind)
            print(f"  Saved → {path_ind}")

    if args.show:
        plt.show()

    print("Done.")


if __name__ == "__main__":
    main()
