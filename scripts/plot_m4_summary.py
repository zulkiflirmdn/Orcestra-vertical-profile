#!/usr/bin/env python3
"""
M4 Summary Figure — 2×2 grid: omega profiles + IMERG composites by category
============================================================================

Top row    : category-mean M4 omega profiles (binned to 500 Pa) with GMS and
             vertical advection annotated.
Bottom row : IMERG precipitation composite for each category — the spatial-mean
             precipitation field averaged over all IMERG snapshots nearest to
             each circle's observation time, with circle centres marked.

Left column  : Top-Heavy
Right column : Bottom-Heavy

Usage
-----
    python scripts/plot_m4_summary.py
    python scripts/plot_m4_summary.py --show
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import numpy as np
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.mse_budget import load_dataset, DEFAULT_ZARR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMERG_PATH = Path("/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc")
OUTPUT_DIR = Path("/home/565/zr7147/Proj/outputs/figures")

COLOR = {"Top-Heavy": "#d62728", "Bottom-Heavy": "#1f77b4"}
CATS  = ["Top-Heavy", "Bottom-Heavy"]
CAT_LISTS = {
    "Top-Heavy":    ["Top-Heavy", "Top-Heavy (Fully Ascending)"],
    "Bottom-Heavy": ["Bottom-Heavy", "Bottom-Heavy (Fully Ascending)"],
}

# Omega profile plot limits (Pa, inverted)
BIN_PA    = 500.0
P_COMMON  = np.arange(2000.0, 105500.0, BIN_PA)
OMEGA_XLIM = (-0.8, 0.4)
P_YLIM     = (105000, 2000)

# IMERG colormap — WhiteBlueGreenYellowRed
_WBGYR = mcolors.LinearSegmentedColormap.from_list(
    "WhiteBlueGreenYellowRed",
    ["#ffffff", "#add8e6", "#0080ff", "#00b000", "#ffff00", "#ff8000", "#ff0000", "#800000"],
    N=256,
)
PRECIP_VMIN = 0.0
PRECIP_VMAX = 2.0   # mm hr⁻¹


# ---------------------------------------------------------------------------
# Pressure-binning helper (same logic as plot_ramp_comparison.py)
# ---------------------------------------------------------------------------

def _bin_profile(omega: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Box-average omega onto P_COMMON (500 Pa grid)."""
    valid = np.isfinite(omega) & np.isfinite(p)
    if valid.sum() < 3:
        return np.full(len(P_COMMON), np.nan)
    p_v, o_v = p[valid], omega[valid]
    p_lo  = np.floor(p_v.min() / BIN_PA) * BIN_PA
    p_hi  = np.ceil( p_v.max() / BIN_PA) * BIN_PA + BIN_PA
    edges = np.arange(p_lo, p_hi, BIN_PA)
    if len(edges) < 2:
        return np.full(len(P_COMMON), np.nan)
    o_sum, _ = np.histogram(p_v, bins=edges, weights=o_v)
    count, _ = np.histogram(p_v, bins=edges)
    p_ctr    = edges[:-1] + BIN_PA / 2.0
    result   = np.where(count > 0, o_sum / count, np.nan)
    has      = count > 0
    if has.sum() < 2:
        return np.full(len(P_COMMON), np.nan)
    return np.interp(P_COMMON, p_ctr[has], result[has], left=np.nan, right=np.nan)


# ---------------------------------------------------------------------------
# Omega panel
# ---------------------------------------------------------------------------

def _draw_omega_panel(ax, ds: xr.Dataset, cat: str, col: str) -> None:
    """
    Spaghetti + mean M4 omega profile for one category.
    Annotates GMS, vert_adv, and N on the panel.
    """
    cat_var  = "category_plane" if "category_plane" in ds else "category_avg"
    mask     = np.isin(ds[cat_var].values, CAT_LISTS[cat])
    n        = int(mask.sum())
    indices  = np.where(mask)[0]

    omega_m4 = ds["omega_m4"].values     # (circle, m4_level)
    p_m4     = ds["p_m4"].values
    gms_vals = ds["gms_m4"].values
    va_vals  = ds["vert_adv_m4"].values

    binned = []
    for ci in indices:
        ob = _bin_profile(omega_m4[ci], p_m4[ci])
        valid = np.isfinite(ob)
        if valid.sum() < 3:
            continue
        ax.plot(ob[valid], P_COMMON[valid],
                color=col, alpha=0.18, lw=0.9, zorder=2)
        binned.append(ob)

    if binned:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean_o = np.nanmean(np.stack(binned), axis=0)
            std_o  = np.nanstd( np.stack(binned), axis=0)
        valid_m = np.isfinite(mean_o)
        ax.fill_betweenx(P_COMMON[valid_m],
                         (mean_o - std_o)[valid_m],
                         (mean_o + std_o)[valid_m],
                         alpha=0.15, color=col, zorder=1)
        ax.plot(mean_o[valid_m], P_COMMON[valid_m],
                color=col, lw=2.8, zorder=3, label="Mean")

    ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.6)

    # Annotations
    g_ok  = gms_vals[mask][np.isfinite(gms_vals[mask])]
    va_ok = va_vals[mask][np.isfinite(va_vals[mask])]
    if len(g_ok):
        gms_mean = g_ok.mean()
        va_mean  = va_ok.mean()
        ax.text(
            0.04, 0.04,
            f"GMS = {gms_mean:+.3f}\n"
            f"vert adv = {va_mean:+.0f} W m⁻²\n"
            f"N = {n}",
            transform=ax.transAxes, fontsize=9,
            va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col, alpha=0.85),
            color=col, fontweight="bold",
        )

    ax.set_xlim(OMEGA_XLIM)
    ax.set_ylim(P_YLIM)
    ax.set_xlabel("Vertical Velocity ω  (Pa s⁻¹)", fontsize=10)
    ax.set_ylabel("Pressure (Pa)", fontsize=10)
    ax.set_title(f"{cat}", fontsize=12, fontweight="bold", color=col)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.25)


# ---------------------------------------------------------------------------
# IMERG composite panel
# ---------------------------------------------------------------------------

def _build_imerg_composite(ds: xr.Dataset, cat: str) -> np.ndarray | None:
    """
    Time-average IMERG precipitation for snapshots nearest to each circle time.
    Returns (lat, lon) array in mm hr⁻¹, or None if IMERG not available.
    """
    if not IMERG_PATH.exists():
        return None

    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    mask    = np.isin(ds[cat_var].values, CAT_LISTS[cat])
    times   = ds["circle_time"].values[mask]

    ds_imerg     = xr.open_dataset(IMERG_PATH)
    imerg_times  = ds_imerg["time"].values.astype("datetime64[ns]")

    slices = []
    for ct in times:
        t_ns  = np.datetime64(ct, "ns")
        t_idx = int(np.argmin(np.abs(imerg_times - t_ns)))
        p_slice = ds_imerg["precipitation"].isel(time=t_idx).values  # (lat, lon)
        slices.append(p_slice)

    ds_imerg.close()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        composite = np.nanmean(np.stack(slices, axis=0), axis=0)
    return composite   # (lat, lon)


def _draw_imerg_panel(ax, ds: xr.Dataset, cat: str, col: str,
                      composite: np.ndarray | None,
                      lat: np.ndarray, lon: np.ndarray) -> None:
    """Draw IMERG composite + circle centres on a map panel."""
    if composite is None:
        ax.text(0.5, 0.5, "IMERG not found", transform=ax.transAxes,
                ha="center", va="center", fontsize=12, color="gray")
        ax.set_title(f"{cat} — IMERG", fontsize=11, fontweight="bold", color=col)
        return

    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    mask    = np.isin(ds[cat_var].values, CAT_LISTS[cat])
    clats   = ds["circle_lat"].values[mask]
    clons   = ds["circle_lon"].values[mask]
    n       = int(mask.sum())

    im = ax.pcolormesh(lon, lat, composite,
                       cmap=_WBGYR, vmin=PRECIP_VMIN, vmax=PRECIP_VMAX,
                       shading="auto", rasterized=True)

    plt.colorbar(im, ax=ax, orientation="horizontal", pad=0.08, fraction=0.04,
                 label="Precipitation  (mm hr⁻¹)")

    # Circle centres
    ax.scatter(clons, clats, s=25, c=col, edgecolors="white",
               linewidths=0.5, zorder=5, label=f"Circles (N={n})")
    ax.legend(fontsize=8, loc="upper right",
              framealpha=0.85, edgecolor=col)

    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.set_title(f"{cat} — IMERG composite", fontsize=11,
                 fontweight="bold", color=col)
    ax.grid(True, alpha=0.25, ls=":")
    ax.set_aspect("equal")


# ---------------------------------------------------------------------------
# Main figure
# ---------------------------------------------------------------------------

def make_figure(ds: xr.Dataset) -> plt.Figure:
    """Build the 2×2 summary figure."""
    # Pre-compute IMERG composites (lazy — only loads time slices)
    print("Building IMERG composites …")
    composites = {cat: _build_imerg_composite(ds, cat) for cat in CATS}

    # IMERG lat/lon arrays (needed for pcolormesh)
    if IMERG_PATH.exists():
        ds_imerg = xr.open_dataset(IMERG_PATH)
        lat = ds_imerg["lat"].values
        lon = ds_imerg["lon"].values
        ds_imerg.close()
    else:
        lat = lon = None

    fig = plt.figure(figsize=(18, 16))
    gs  = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.28)

    axes_omega = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    axes_imerg = [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]

    # ── Top row: omega profiles ───────────────────────────────────────────
    for ax, cat in zip(axes_omega, CATS):
        _draw_omega_panel(ax, ds, cat, COLOR[cat])

    # Share y-axis between omega panels
    axes_omega[1].sharey(axes_omega[0])
    axes_omega[1].set_ylabel("")

    # ── Bottom row: IMERG composites ─────────────────────────────────────
    for ax, cat in zip(axes_imerg, CATS):
        _draw_imerg_panel(ax, ds, cat, COLOR[cat],
                          composites[cat], lat, lon)

    # ── Global ΔGMS annotation ───────────────────────────────────────────
    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    cats_all = ds[cat_var].values
    gms_all  = ds["gms_m4"].values

    th_mask = np.isin(cats_all, CAT_LISTS["Top-Heavy"])
    bh_mask = np.isin(cats_all, CAT_LISTS["Bottom-Heavy"])
    gms_th  = np.nanmean(gms_all[th_mask])
    gms_bh  = np.nanmean(gms_all[bh_mask])
    delta   = gms_th - gms_bh

    fig.suptitle(
        "ORCESTRA BEACH L4  ·  M4 Omega Profiles & IMERG Precipitation by Convective Category\n"
        f"ΔGMS (Top-Heavy − Bottom-Heavy) = {delta:+.3f}  "
        f"(GMS$_{{TH}}$ = {gms_th:+.3f},  GMS$_{{BH}}$ = {gms_bh:+.3f})",
        fontsize=13, fontweight="bold", y=0.98,
    )

    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="2×2 summary: M4 omega profiles + IMERG composites by category"
    )
    parser.add_argument("--zarr", default=DEFAULT_ZARR, metavar="PATH")
    parser.add_argument("--out",  default=OUTPUT_DIR, type=Path)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    print("Loading zarr …")
    ds = xr.open_zarr(args.zarr)

    # Check required variables
    required = ["omega_m4", "p_m4", "gms_m4", "vert_adv_m4"]
    missing  = [v for v in required if v not in ds]
    if missing:
        print(f"Missing variables: {missing}")
        print("Run  python scripts/save_m4_to_zarr.py  and  "
              "python scripts/compute_mse_gms.py  first.")
        sys.exit(1)

    print("Building figure …")
    fig = make_figure(ds)

    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "omega_imerg_m4_summary.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out_path}")

    if args.show:
        plt.show()

    print("Done.")


if __name__ == "__main__":
    main()
