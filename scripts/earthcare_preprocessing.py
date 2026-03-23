#!/usr/bin/env python3
"""Download and process EarthCARE CPR data for ORCESTRA campaign.

This module automates EarthCARE data download using the earthcare-downloader package
and processes the data into a standardized NetCDF format matching IMERG for direct
comparison with dropsonde observations.

Prerequisites:
    1. ESA Earth Online account with EarthCARE data access
    2. Set ESA_EO_USERNAME and ESA_EO_PASSWORD environment variables
    3. Install earthcare-downloader: pip install earthcare-downloader

Primary Products:
    - CPR_CLP_2A: Cloud Properties (reflectivity, vertical velocity)
    - CPR_ECO_2A: Echo Properties (reflectivity profiles)

Reference:
    - earthcare-downloader: https://pypi.org/project/earthcare-downloader/
    - EarthCARE data products: https://www.esa.int/Applications/Observing_the_Earth/EarthCARE
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import warnings
from pathlib import Path

import xarray as xr
from dask.distributed import Client

from scripts.config import BoundingBox, default_earthcare_bbox, default_earthcare_input_dir, default_earthcare_output_path, earthcare_credentials

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════════════
# ORCESTRA Campaign Configuration for earthcare-downloader
# ════════════════════════════════════════════════════════════════════════════════════

ORCESTRA_CONFIG = {
    'latitude_range': [0, 30],           # Wider buffer (0N-30N per SPEC)
    'longitude_range': [-70, 0],         # Wider buffer (70W-0W per SPEC)
    'start_date': '2024-08-10',
    'end_date': '2024-09-30',
    'products': [
        'CPR_CLP_2A',    # PRIMARY: Cloud Properties (vertical velocity, reflectivity)
        'CPR_ECO_2A',    # PRIMARY: Echo Properties (reflectivity profiles)
        'AC__CLP_2B',    # SECONDARY: Synergistic Cloud Properties
    ]
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and merge EarthCARE CPR data for ORCESTRA"
    )
    parser.add_argument("--input-dir", type=Path, default=default_earthcare_input_dir())
    parser.add_argument("--output-path", type=Path, default=default_earthcare_output_path())
    parser.add_argument("--lat-min", type=float, default=default_earthcare_bbox().lat_min)
    parser.add_argument("--lat-max", type=float, default=default_earthcare_bbox().lat_max)
    parser.add_argument("--lon-min", type=float, default=default_earthcare_bbox().lon_min)
    parser.add_argument("--lon-max", type=float, default=default_earthcare_bbox().lon_max)
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip download step and use existing files in input-dir")
    return parser.parse_args()


def get_dask_config() -> tuple[int, str]:
    """Build worker settings from PBS/Dask env vars."""
    worker_count = int(os.environ.get("ORCESTRA_DASK_WORKERS", os.environ.get("PBS_NCPUS", "4")))
    memory_limit = os.environ.get("ORCESTRA_DASK_MEMORY_LIMIT", "1800MiB")
    return max(1, worker_count), memory_limit


def download_earthcare_data(output_dir: Path, credentials: dict) -> list[Path]:
    """Download EarthCARE CPR products using earthcare-downloader.

    Args:
        output_dir: Directory to save downloaded files
        credentials: Dict with 'username' and 'password' keys

    Returns:
        List of downloaded file paths

    Raises:
        ValueError: If credentials are not properly configured
        ImportError: If earthcare-downloader is not installed
    """

    # Check credentials
    if not credentials.get('username') or not credentials.get('password'):
        raise ValueError(
            "ESA Earth Online credentials not configured. "
            "Set ESA_EO_USERNAME and ESA_EO_PASSWORD environment variables.\n"
            "Example:\n"
            "  export ESA_EO_USERNAME='your_username'\n"
            "  export ESA_EO_PASSWORD='your_password'"
        )

    # Import earthcare_downloader
    try:
        from earthcare_downloader import search, download
    except ImportError:
        raise ImportError(
            "earthcare-downloader not installed. "
            "Install it with: pip install earthcare-downloader"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Download directory: {output_dir.absolute()}")

    all_files = []

    # Download each product type
    for product in ORCESTRA_CONFIG['products']:
        logger.info(f"\n{'='*60}")
        logger.info(f"Searching for product: {product}")
        logger.info(f"{'='*60}")

        try:
            # Search for files
            logger.info(f"Searching {product} from {ORCESTRA_CONFIG['start_date']} to {ORCESTRA_CONFIG['end_date']}")
            files = search(
                product=product,
                start=ORCESTRA_CONFIG['start_date'],
                stop=ORCESTRA_CONFIG['end_date'],
                lat_range=ORCESTRA_CONFIG['latitude_range'],
                lon_range=ORCESTRA_CONFIG['longitude_range'],
            )

            logger.info(f"Found {len(files)} files for {product}")

            # Download files if available
            if files:
                logger.info(f"Starting download for {product}...")
                product_dir = output_dir / product
                product_dir.mkdir(parents=True, exist_ok=True)

                paths = download(
                    files,
                    output_path=str(product_dir),
                    max_workers=5,  # Concurrent downloads
                    force=False      # Skip existing files
                )
                logger.info(f"Downloaded {len(paths)} files to {product_dir}")
                all_files.extend(paths)
            else:
                logger.warning(f"No files found for {product}")

        except Exception as e:
            logger.error(f"Error downloading {product}: {str(e)}")
            continue

    return all_files


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
    """Main workflow: download and process EarthCARE data."""

    args = parse_args()
    bbox = BoundingBox(args.lat_min, args.lat_max, args.lon_min, args.lon_max)
    input_dir = args.input_dir
    output_path = args.output_path

    logger.info("Starting EarthCARE satellite preprocessing...")
    logger.info(f"Input EarthCARE directory: {input_dir}")
    logger.info(f"Output NetCDF path: {output_path}")
    logger.info(
        f"Crop bbox: lat[{bbox.lat_min}, {bbox.lat_max}] lon[{bbox.lon_min}, {bbox.lon_max}]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Download EarthCARE data (if not skipping)
    input_files = []
    if not args.skip_download:
        try:
            creds = earthcare_credentials()
            input_files = download_earthcare_data(input_dir, creds)
        except (ValueError, ImportError) as e:
            logger.error(f"Download error: {e}")
            return
        except Exception as e:
            logger.error(f"Failed to download EarthCARE data: {e}")
            logger.info("Trying to use existing files in input directory...")

    # Step 2: Find available EarthCARE NetCDF files
    if not input_files:
        input_files = sorted(glob.glob(str(input_dir / "**" / "*.nc"), recursive=True))

    if not input_files:
        logger.error(f"No EarthCARE NetCDF files found in {input_dir}")
        logger.info("Please ensure EarthCARE data is downloaded and available in:")
        logger.info(f"  {input_dir}")
        return

    logger.info(f"Found {len(input_files)} EarthCARE files to process")

    # Step 3: Merge and crop EarthCARE files
    worker_count, memory_limit = get_dask_config()
    logger.info(f"Dask workers: {worker_count}")
    logger.info(f"Dask memory per worker: {memory_limit}")

    client = Client(n_workers=worker_count, threads_per_worker=1, memory_limit=memory_limit)
    ds_earthcare: xr.Dataset | None = None

    try:
        logger.info(f"Dask dashboard: {client.dashboard_link}")

        # Open all EarthCARE files and merge
        logger.info("Opening and merging EarthCARE files...")
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
            # Check for alternative names (EarthCARE uses different variable names)
            alt_names = ["precip", "precipitation_rate", "rain_rate", "CPR_reflectivity", "reflectivity"]
            found = False
            for alt in alt_names:
                if alt in ds_earthcare.data_vars:
                    ds_earthcare = ds_earthcare.rename({alt: "precipitation"})
                    found = True
                    logger.info(f"Renamed variable '{alt}' to 'precipitation'")
                    break
            if not found:
                warnings.warn(
                    "Could not find precipitation variable in EarthCARE data. "
                    "Available variables: " + ", ".join(ds_earthcare.data_vars)
                )

        # Encode and write
        encoding = {var: {"zlib": True, "complevel": 4} for var in ds_earthcare.data_vars}
        logger.info("Writing merged NetCDF...")
        ds_earthcare.to_netcdf(
            output_path, mode="w", format="NETCDF4", encoding=encoding, compute=True
        )

        logger.info(f"Success! Merged and cropped EarthCARE written to {output_path}")

    finally:
        if ds_earthcare is not None:
            ds_earthcare.close()
        client.close()


if __name__ == "__main__":
    main()
