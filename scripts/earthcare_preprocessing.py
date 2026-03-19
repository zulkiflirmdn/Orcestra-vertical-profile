#!/usr/bin/env python3
"""Process EarthCARE CloudSat precipitation data into a cropped NetCDF product.

This module downloads and preprocesses EarthCARE precipitation data from the G-Portal
(JAXA's Earth Observation Research Center data portal) into a standardized NetCDF format
that matches IMERG for direct comparison with dropsonde observations.

Prerequisites:
    1. G-Portal account with EarthCARE data access
    2. Configure credentials below (earthcare_credentials dictionary)
    3. Download EarthCARE data files to /g/data/k10/zr7147/EarthCARE_Data/

Reference:
    - See GPortalUserManual_en.pdf for G-Portal documentation
    - EarthCARE data products: https://www.eorc.jaxa.jp/en/earthcare/

"""

from __future__ import annotations

import argparse
import glob
import os
import warnings
from pathlib import Path

import xarray as xr
from dask.distributed import Client

from scripts.config import BoundingBox, default_earthcare_bbox, default_earthcare_input_dir, default_earthcare_output_path

# ════════════════════════════════════════════════════════════════════════════════════
# EDITABLE CREDENTIALS SECTION
# ════════════════════════════════════════════════════════════════════════════════════
# Update these credentials with your G-Portal account information
# These can also be set via environment variables (see code below)
#
EARTHCARE_CREDENTIALS = {
    "username": os.environ.get("EARTHCARE_USERNAME", "YOUR_GPORTAL_USERNAME_HERE"),
    "password": os.environ.get("EARTHCARE_PASSWORD", "YOUR_GPORTAL_PASSWORD_HERE"),
    # G-Portal base URL (may change with updates)
    "gportal_url": os.environ.get(
        "EARTHCARE_GPORTAL_URL",
        "https://gportal.jaxa.jp/gw/",
    ),
}

# Optional: CloudSat/EarthCARE product IDs or dataset names to download
# Modify based on actual product availability in G-Portal
EARTHCARE_PRODUCT_ID = os.environ.get(
    "EARTHCARE_PRODUCT_ID",
    "EarthCARE_CPR_geophysical_variables",  # Example: CloudSat Radar Reflectivity
)
# ════════════════════════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and merge EarthCARE CloudSat precipitation data"
    )
    parser.add_argument("--input-dir", type=Path, default=default_earthcare_input_dir())
    parser.add_argument("--output-path", type=Path, default=default_earthcare_output_path())
    parser.add_argument("--lat-min", type=float, default=default_earthcare_bbox().lat_min)
    parser.add_argument("--lat-max", type=float, default=default_earthcare_bbox().lat_max)
    parser.add_argument("--lon-min", type=float, default=default_earthcare_bbox().lon_min)
    parser.add_argument("--lon-max", type=float, default=default_earthcare_bbox().lon_max)
    return parser.parse_args()


def get_dask_config() -> tuple[int, str]:
    """Build worker settings from PBS/Dask env vars."""

    worker_count = int(os.environ.get("ORCESTRA_DASK_WORKERS", os.environ.get("PBS_NCPUS", "4")))
    memory_limit = os.environ.get("ORCESTRA_DASK_MEMORY_LIMIT", "1800MiB")
    return max(1, worker_count), memory_limit


def download_earthcare_data(bbox: BoundingBox, credentials: dict) -> list[Path]:
    """Download EarthCARE data from G-Portal.

    Warning: This is a template function. Actual implementation requires:
    1. G-Portal API authentication (OAuth or username/password)
    2. Query construction with bbox and time parameters
    3. File download handling with progress tracking

    Args:
        bbox: Spatial bounding box (lat/lon)
        credentials: Dictionary with 'username', 'password', 'gportal_url'

    Returns:
        List of downloaded file paths

    Raises:
        ValueError: If credentials are not properly configured
        ConnectionError: If G-Portal connection fails
    """

    if credentials["username"] == "YOUR_GPORTAL_USERNAME_HERE":
        raise ValueError(
            "EARTHCARE_USERNAME not configured. "
            "Edit EARTHCARE_CREDENTIALS in scripts/earthcare_preprocessing.py "
            "or set EARTHCARE_USERNAME environment variable."
        )

    print("EarthCARE G-Portal Download")
    print("=" * 80)
    print(f"User: {credentials['username']}")
    print(f"G-Portal URL: {credentials['gportal_url']}")
    print(f"Domain: lat [{bbox.lat_min}, {bbox.lat_max}], lon [{bbox.lon_min}, {bbox.lon_max}]")
    print()

    # TODO: Implement actual G-Portal API calls
    # Reference: GPortalUserManual_en.pdf section on API authentication and data queries
    #
    # Example pseudocode:
    # ───────────────────────────────────────────────────────────────────────
    # 1. Authenticate to G-Portal:
    #    - Use OAuth2 or basic auth with provided credentials
    #    - Store session token for subsequent requests
    #
    # 2. Query available EarthCARE products in time/space range:
    #    - POST to /api/v1/query with bbox + time range
    #    - Filter by product type (e.g., CloudSat precipitation)
    #
    # 3. Download each product:
    #    - GET file URLs from query response
    #    - Download with progress tracking
    #    - Verify checksum (if provided)
    #    - Save to /g/data/k10/zr7147/EarthCARE_Data/
    #
    # 4. Return list of downloaded file paths
    # ───────────────────────────────────────────────────────────────────────

    # Placeholder: List downloaded files (if they exist)
    input_dir = Path(credentials.get("input_dir", "/g/data/k10/zr7147/EarthCARE_Data"))
    input_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files = sorted(glob.glob(str(input_dir / "*.nc")))
    if not downloaded_files:
        print(f"No EarthCARE NetCDF files found in {input_dir}")
        print("Please download EarthCARE data from G-Portal first:")
        print(f"  1. Go to {credentials['gportal_url']}")
        print("  2. Login with your G-Portal account")
        print("  3. Search for EarthCARE CloudSat precipitation products")
        print(f"  4. Download files with spatial extent: lat [{bbox.lat_min}, {bbox.lat_max}], lon [{bbox.lon_min}, {bbox.lon_max}]")
        print(f"  5. Place files in {input_dir}/")
        raise FileNotFoundError(f"No EarthCARE data files found in {input_dir}")

    print(f"Found {len(downloaded_files)} EarthCARE NetCDF files to process")
    return [Path(f) for f in downloaded_files]


def clean_earthcare(ds: xr.Dataset, bbox: BoundingBox) -> xr.Dataset:
    """Standardize EarthCARE coordinate ordering and crop to domain.

    Handles variations in EarthCARE data format to produce consistent structure
    matching IMERG for direct comparison.

    Args:
        ds: xarray Dataset with EarthCARE data
        bbox: Bounding box for spatial cropping

    Returns:
        Cleaned and cropped Dataset
    """

    # Ensure standard dimension order (time, lat, lon)
    if "time" in ds.dims and "lat" in ds.dims and "lon" in ds.dims:
        ds = ds.transpose("time", "lat", "lon", ...)

    # Handle longitude normalization (0-360 to -180-180)
    if "lon" in ds.coords:
        if ds["lon"].max() > 180:
            ds = ds.assign_coords(lon=(((ds.lon + 180) % 360) - 180)).sortby("lon")

    # Handle latitude direction (ascending or descending)
    if "lat" in ds.coords:
        if ds.lat[0] > ds.lat[-1]:
            lat_slice = slice(bbox.lat_max, bbox.lat_min)  # descending
        else:
            lat_slice = slice(bbox.lat_min, bbox.lat_max)  # ascending
    else:
        lat_slice = slice(bbox.lat_min, bbox.lat_max)

    # Spatial cropping
    if "lon" in ds.coords and "lat" in ds.coords:
        ds = ds.sel(lon=slice(bbox.lon_min, bbox.lon_max), lat=lat_slice)

    return ds


def main() -> None:
    args = parse_args()
    bbox = BoundingBox(args.lat_min, args.lat_max, args.lon_min, args.lon_max)

    input_dir = args.input_dir
    output_path = args.output_path

    print("Starting EarthCARE satellite preprocessing...")
    print(f"Input EarthCARE directory: {input_dir}")
    print(f"Output NetCDF path: {output_path}")
    print(
        "Crop bbox: "
        f"lat[{bbox.lat_min}, {bbox.lat_max}] "
        f"lon[{bbox.lon_min}, {bbox.lon_max}]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    worker_count, memory_limit = get_dask_config()
    print(f"Dask workers: {worker_count}")
    print(f"Dask memory per worker: {memory_limit}")

    # Step 1: Download EarthCARE data from G-Portal (if needed)
    try:
        input_files = download_earthcare_data(bbox, EARTHCARE_CREDENTIALS)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    except ValueError as e:
        print(f"Configuration Error: {e}")
        return

    if not input_files:
        raise FileNotFoundError(f"No EarthCARE files found in {input_dir}")

    print(f"Found {len(input_files)} EarthCARE files")

    # Step 2: Merge and crop EarthCARE files
    client = Client(n_workers=worker_count, threads_per_worker=1, memory_limit=memory_limit)
    ds_earthcare: xr.Dataset | None = None

    try:
        print(f"Dask dashboard: {client.dashboard_link}")

        # Open all EarthCARE files and merge
        ds_earthcare = xr.open_mfdataset(
            [str(f) for f in input_files],
            concat_dim="time",
            combine="nested",
            engine="netcdf4",
            preprocess=lambda ds: clean_earthcare(ds, bbox),
            chunks={"time": 1, "lat": 400, "lon": 400},
            parallel=True,
        )

        # Sort by time
        ds_earthcare = ds_earthcare.sortby("time")

        # Remove ancillary variables if present
        ds_earthcare = ds_earthcare.drop_vars(
            ["time_bnds", "lat_bnds", "lon_bnds"],
            errors="ignore",
        )

        # Ensure precipitation variable exists and is appropriately named
        if "precipitation" not in ds_earthcare.data_vars:
            # Check for alternative names (CloudSat uses different variable names)
            alt_names = ["precip", "precipitation_rate", "rain_rate", "CPR_reflectivity"]
            found = False
            for alt in alt_names:
                if alt in ds_earthcare.data_vars:
                    ds_earthcare = ds_earthcare.rename({alt: "precipitation"})
                    found = True
                    print(f"Renamed variable '{alt}' to 'precipitation'")
                    break
            if not found:
                warnings.warn(
                    "Could not find precipitation variable in EarthCARE data. "
                    "Available variables: " + ", ".join(ds_earthcare.data_vars)
                )

        # Encode and write
        encoding = {var: {"zlib": True, "complevel": 4} for var in ds_earthcare.data_vars}
        print("Writing merged NetCDF...")
        ds_earthcare.to_netcdf(
            output_path, mode="w", format="NETCDF4", encoding=encoding, compute=True
        )

        print("Success: merged and cropped EarthCARE written.")

    finally:
        if ds_earthcare is not None:
            ds_earthcare.close()
        client.close()


if __name__ == "__main__":
    main()
