#!/usr/bin/env python3
"""
Save M4 (cosine-blend + ERA5 extension) omega profiles to the BEACH L4 zarr.
=============================================================================

Appends four new variables with a 'm4_level' dimension to the canonical
zarr store at /g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr:

    omega_m4  (circle, m4_level)  float32  Pa s⁻¹   M4 blended + ERA5 extended ω
    p_m4      (circle, m4_level)  float32  Pa        pressure for extended column
    ta_m4     (circle, m4_level)  float32  K         temperature for extended column
    div_m4    (circle, m4_level)  float32  s⁻¹       divergence for extended column

'm4_level' indexes the stitched column: BEACH altitude levels (sorted descending
pressure) followed by ERA5 fine-grid levels (500 Pa spacing) above the BEACH
top, up to the ERA5 data top (~20 hPa).  NaN fills unused trailing positions.

These variables let MSE/GMS calculations load the extended profile directly
without re-running blend_beach_era5 each time.

Usage
-----
    python scripts/save_m4_to_zarr.py              # skip if vars already exist
    python scripts/save_m4_to_zarr.py --overwrite  # recompute and overwrite
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.mse_budget import load_dataset, DEFAULT_ZARR
from scripts.era5_extension import load_era5_omega, blend_beach_era5


# ---------------------------------------------------------------------------
# Core save function
# ---------------------------------------------------------------------------

def save_m4_to_zarr(zarr_path: str = DEFAULT_ZARR, overwrite: bool = False) -> None:
    """
    Compute M4 and append omega_m4 / p_m4 / ta_m4 / div_m4 to the zarr.

    Parameters
    ----------
    zarr_path : str   Path to the BEACH L4 zarr store.
    overwrite : bool  If True, recompute even if variables already exist.
    """
    # ── Guard: check whether vars already exist ───────────────────────────
    print(f"Opening zarr: {zarr_path}")
    ds_check = xr.open_zarr(zarr_path)
    already_saved = all(v in ds_check for v in ("omega_m4", "p_m4", "ta_m4", "div_m4"))

    if already_saved and not overwrite:
        n = ds_check.sizes.get("m4_level", "?")
        print(
            f"M4 variables already present (m4_level={n}).  "
            "Pass --overwrite to recompute."
        )
        return
    ds_check.close()

    # ── Load data ─────────────────────────────────────────────────────────
    print("Loading BEACH L4 dataset …")
    ds_beach = load_dataset(zarr_path)

    print("Loading ERA5 omega …")
    era5_ds = load_era5_omega()

    # ── Compute M4 ────────────────────────────────────────────────────────
    print("Computing M4 cosine blend + ERA5 extension …")
    ds_ext = blend_beach_era5(ds_beach, era5_ds=era5_ds)

    n_m4 = ds_ext.sizes["ext_level"]
    print(f"  Extended column: {n_m4} levels  "
          f"(BEACH: {ds_beach.sizes['altitude']}  ERA5 fine-grid: {n_m4 - ds_beach.sizes['altitude']})")

    # ── Build the dataset to save ─────────────────────────────────────────
    # Rename ext_level → m4_level and select only the variables needed.
    rename_map = {"ext_level": "m4_level"}

    ds_save = xr.Dataset(
        {
            "omega_m4": (
                ds_ext["omega_ext"]
                .rename(rename_map)
                .astype("float32")
                .assign_attrs({"units": "Pa s-1",
                               "long_name": "M4 omega: cosine-blended BEACH + ERA5 extension",
                               "method": "M4_cosine_blend_era5_extension"})
            ),
            "p_m4": (
                ds_ext["p_ext"]
                .rename(rename_map)
                .astype("float32")
                .assign_attrs({"units": "Pa",
                               "long_name": "pressure for M4 extended column"})
            ),
            "ta_m4": (
                ds_ext["ta_era5_ext"]
                .rename(rename_map)
                .astype("float32")
                .assign_attrs({"units": "K",
                               "long_name": "temperature: BEACH below, ERA5 above (M4)"})
            ),
            "div_m4": (
                ds_ext["div_era5_ext"]
                .rename(rename_map)
                .astype("float32")
                .assign_attrs({"units": "s-1",
                               "long_name": "divergence: BEACH below, ERA5 above (M4)"})
            ),
        }
    )

    # Attach m4_level as an explicit integer coordinate
    ds_save = ds_save.assign_coords(m4_level=np.arange(n_m4, dtype=np.int32))

    # Chunk to match the existing zarr pattern (all 89 circles in one chunk,
    # m4_level in one chunk — the extended arrays are small: ~89×1666×4 B ≈ 0.6 MB)
    chunk = {"circle": ds_beach.sizes["circle"], "m4_level": n_m4}
    ds_save = ds_save.chunk(chunk)

    # Encoding: float32, no compression (matching existing omega encoding)
    encoding = {
        v: {"dtype": "float32", "chunks": (chunk["circle"], chunk["m4_level"])}
        for v in ("omega_m4", "p_m4", "ta_m4", "div_m4")
    }

    # ── Write to zarr ─────────────────────────────────────────────────────
    mode = "a"   # append — adds new variables without touching existing ones
    print(f"Writing to zarr (mode='{mode}') …")
    ds_save.to_zarr(zarr_path, mode=mode, encoding=encoding)

    # Consolidate metadata so open_zarr picks up the new variables
    import zarr
    zarr.consolidate_metadata(zarr_path)
    print("Metadata consolidated.")

    # ── Verify ────────────────────────────────────────────────────────────
    print("Verifying …")
    ds_verify = xr.open_zarr(zarr_path)
    for v in ("omega_m4", "p_m4", "ta_m4", "div_m4"):
        arr = ds_verify[v]
        n_valid = int(np.isfinite(arr.values).sum())
        print(f"  {v}: shape={arr.shape}  finite={n_valid:,}")

    print(f"\nDone.  Load with:\n"
          f"  ds = xr.open_zarr('{zarr_path}')\n"
          f"  omega_m4 = ds['omega_m4']   # (circle, m4_level)\n"
          f"  p_m4     = ds['p_m4']       # (circle, m4_level)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save M4 extended omega profiles to the BEACH L4 zarr"
    )
    parser.add_argument(
        "--zarr", default=DEFAULT_ZARR, metavar="PATH",
        help=f"Path to the BEACH L4 zarr store (default: {DEFAULT_ZARR})",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Recompute and overwrite even if M4 variables already exist",
    )
    args = parser.parse_args()
    save_m4_to_zarr(zarr_path=args.zarr, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
