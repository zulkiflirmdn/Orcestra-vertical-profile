#!/usr/bin/env python3
"""
Compute M4 MSE/GMS budget for all circles and append to the BEACH L4 zarr.
============================================================================

Runs the full M4 pipeline (cosine blend + ERA5 extension) and saves five
per-circle budget scalars to the zarr:

    gms_m4           (circle,)  –        GMS = vert_adv / vert_adv_dse
    vert_adv_m4      (circle,)  W m⁻²    vertical MSE advection <ω ∂h/∂p>
    vert_adv_dse_m4  (circle,)  W m⁻²    vertical DSE advection <ω ∂s/∂p>
    horiz_adv_m4     (circle,)  W m⁻²    horizontal MSE advection <v·∇h>
    col_h_m4         (circle,)  J m⁻²    column-integrated MSE

Then prints a summary table grouped by convective category.

Usage
-----
    python scripts/compute_mse_gms.py
    python scripts/compute_mse_gms.py --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import xarray as xr
import zarr

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.mse_budget import load_dataset, DEFAULT_ZARR
from scripts.era5_extension import load_era5_omega, compute_budget_m4

# Variable map: zarr_name → (budget_key, units, long_name)
_VARS = {
    "gms_m4":          ("gms_adv",      "",       "GMS_adv (M4) = vert_adv / vert_adv_dse"),
    "vert_adv_m4":     ("vert_adv",     "W m-2",  "M4 vertical MSE advection"),
    "vert_adv_dse_m4": ("vert_adv_dse", "W m-2",  "M4 vertical DSE advection"),
    "horiz_adv_m4":    ("horiz_adv",    "W m-2",  "M4 horizontal MSE advection"),
    "col_h_m4":        ("col_h",        "J m-2",  "M4 column-integrated MSE"),
}

# Category groups for the summary table
_GROUPS = {
    "Top-Heavy":    ["Top-Heavy", "Top-Heavy (Fully Ascending)"],
    "Bottom-Heavy": ["Bottom-Heavy", "Bottom-Heavy (Fully Ascending)"],
    "Inactive":     ["Inactive / Suppressed"],
}


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def compute_and_save(zarr_path: str = DEFAULT_ZARR, overwrite: bool = False) -> xr.Dataset:
    """
    Compute M4 MSE/GMS budget and append per-circle scalars to the zarr.

    Returns the loaded zarr dataset (with new variables) for further use.
    """
    print(f"Opening zarr: {zarr_path}")
    ds_check = xr.open_zarr(zarr_path)
    already = all(v in ds_check for v in _VARS)

    if already and not overwrite:
        print("Budget variables already present.  Pass --overwrite to recompute.")
        print_summary(ds_check)
        return ds_check

    ds_check.close()

    # ── Load inputs ───────────────────────────────────────────────────────
    print("Loading BEACH L4 dataset …")
    ds_beach = load_dataset(zarr_path)

    print("Loading ERA5 omega …")
    era5_ds = load_era5_omega()

    # ── Compute M4 budget ─────────────────────────────────────────────────
    print("Computing M4 MSE/GMS budget (blend_beach_era5 + compute_budget_ext) …")
    budget, _ = compute_budget_m4(ds_beach, era5_ds=era5_ds)
    print("  Done.")

    # ── Build dataset for zarr append ─────────────────────────────────────
    circle_coord = ds_beach["circle"]
    data_vars = {}
    for zarr_name, (bkey, units, long_name) in _VARS.items():
        vals = budget[bkey].values.astype("float32")
        data_vars[zarr_name] = xr.DataArray(
            vals, dims=["circle"],
            coords={"circle": circle_coord},
            attrs={"units": units, "long_name": long_name, "method": "M4_cosine_blend"},
        )

    ds_save = xr.Dataset(data_vars)
    encoding = {v: {"dtype": "float32"} for v in data_vars}

    print(f"Appending to zarr …")
    ds_save.to_zarr(zarr_path, mode="a", encoding=encoding)
    zarr.consolidate_metadata(zarr_path)
    print("Metadata consolidated.")

    # ── Summary ───────────────────────────────────────────────────────────
    ds_full = xr.open_zarr(zarr_path)
    print_summary(ds_full)
    return ds_full


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary(ds: xr.Dataset) -> None:
    """Print a formatted MSE/GMS budget table grouped by convective category."""
    cat_var = "category_plane" if "category_plane" in ds else "category_avg"
    cats    = ds[cat_var].values

    gms = ds["gms_m4"].values
    va  = ds["vert_adv_m4"].values
    vd  = ds["vert_adv_dse_m4"].values
    ha  = ds["horiz_adv_m4"].values
    ch  = ds["col_h_m4"].values

    W = 76
    print()
    print("=" * W)
    print("  MSE / GMS Budget Summary — M4 (Cosine Blend + ERA5 Extension)")
    print("=" * W)
    hdr = f"  {'Category':<22}  {'N':>4}  {'GMS mean±std':>14}  "
    hdr += f"{'vert_adv':>10}  {'horiz_adv':>10}  {'col_h':>12}"
    print(hdr)
    sub = f"  {'':22}  {'':>4}  {'(dimensionless)':>14}  "
    sub += f"{'W m⁻²':>10}  {'W m⁻²':>10}  {'MJ m⁻²':>12}"
    print(sub)
    print("-" * W)

    gms_group = {}
    for label, cat_list in _GROUPS.items():
        mask = np.isin(cats, cat_list)
        n    = int(mask.sum())
        if n == 0:
            continue
        g  = gms[mask]; ok = np.isfinite(g)
        gm = np.nanmean(g); gs = np.nanstd(g)
        vm = np.nanmean(va[mask])
        hm = np.nanmean(ha[mask])
        cm = np.nanmean(ch[mask]) / 1e6   # → MJ m⁻²
        gms_group[label] = gm
        print(f"  {label:<22}  {n:>4}  {gm:>+7.3f} ± {gs:.3f}  "
              f"{vm:>10.1f}  {hm:>10.1f}  {cm:>12.4f}")

    print("-" * W)
    if "Top-Heavy" in gms_group and "Bottom-Heavy" in gms_group:
        delta = gms_group["Top-Heavy"] - gms_group["Bottom-Heavy"]
        print(f"  ΔGMS  (Top-Heavy − Bottom-Heavy) = {delta:+.3f}")
    print("=" * W)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute M4 MSE/GMS budget and save to the BEACH L4 zarr"
    )
    parser.add_argument("--zarr", default=DEFAULT_ZARR, metavar="PATH",
                        help=f"zarr store path (default: {DEFAULT_ZARR})")
    parser.add_argument("--overwrite", action="store_true",
                        help="Recompute even if variables already present")
    args = parser.parse_args()
    compute_and_save(zarr_path=args.zarr, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
