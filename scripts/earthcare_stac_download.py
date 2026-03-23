#!/usr/bin/env python3
"""Download and process EarthCARE data using ESA MAAP STAC API.

This module automates EarthCARE precipitation data download using the official
ESA MAAP STAC catalog, which provides direct API access without requiring manual
G-Portal authentication or specialized downloaderer packages.

Documentation:
    - ESA MAAP STAC Catalog: https://catalog.maap.eo.esa.int/doc/stac.html
    - STAC API Overview: https://stacspec.org/
    - EarthCARE Products: https://www.esa.int/Applications/Observing_the_Earth/EarthCARE

Key Features:
    - Automated search using STAC queries (no manual browsing)
    - Direct HTTP download from ESA repositories
    - Spatial and temporal filtering built-in
    - NetCDF output compatible with IMERG for direct comparison
"""

from __future__ import annotations

import argparse
import logging
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import requests
import xarray as xr
from dask.distributed import Client

from scripts.config import BoundingBox, default_earthcare_bbox, default_earthcare_input_dir, default_earthcare_output_path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════════════
# ESA MAAP STAC Configuration
# ════════════════════════════════════════════════════════════════════════════════════

ESA_MAAP_STAC_BASE = "https://catalog.maap.eo.esa.int"
ESA_MAAP_COLLECTIONS_ENDPOINT = f"{ESA_MAAP_STAC_BASE}/catalogue/collections"
ESA_MAAP_SEARCH_ENDPOINT = f"{ESA_MAAP_STAC_BASE}/catalogue/search"

# EarthCARE Products Available via STAC
EARTHCARE_PRODUCTS = {
    "MSI_COP": {
        "description": "EarthCARE MSI Cloud and Precipitation (precipitation data)",
        "collection_id": "EarthCARE_MSI_Cloud_and_Precipitation_2A",
    },
    "CPR_CLP": {
        "description": "EarthCARE CPR Cloud Properties (cloud reflectivity)",
        "collection_id": "EarthCARE_CPR_Cloud_Properties_2A",
    },
}

ORCESTRA_CONFIG = {
    'latitude_range': [0, 30],           # 0N-30N per SPEC
    'longitude_range': [-70, 0],         # 70W-0W per SPEC
    'start_date': '2024-08-10',
    'end_date': '2024-09-30',
    'product': 'MSI_COP',                # Precipitation data
    'timeout': 30,                       # HTTP request timeout (seconds)
    'max_retries': 3,                    # Retry failed downloads
}


def list_earthcare_collections() -> dict:
    """List all available EarthCARE collections from ESA MAAP STAC.

    Returns
    -------
    dict
        Mapping of collection IDs to collection metadata

    Raises
    ------
    requests.RequestException
        If the STAC catalog cannot be reached
    """

    logger.info(f"Fetching available collections from {ESA_MAAP_COLLECTIONS_ENDPOINT}...")

    try:
        response = requests.get(
            ESA_MAAP_COLLECTIONS_ENDPOINT,
            params={"q": "EarthCARE"},
            timeout=ORCESTRA_CONFIG['timeout']
        )
        response.raise_for_status()

        data = response.json()
        collections = {}

        # Extract EarthCARE collections
        for item in data.get("collections", []):
            collection_id = item.get("id", "")
            if "EarthCARE" in collection_id or "earthcare" in collection_id.lower():
                collections[collection_id] = {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "extent": item.get("extent", {}),
                }

        logger.info(f"Found {len(collections)} EarthCARE collections")
        return collections

    except requests.RequestException as e:
        logger.error(f"Failed to fetch collections: {e}")
        raise


def search_earthcare_data(
    bbox: BoundingBox,
    start_date: str,
    end_date: str,
    product: str = "MSI_COP",
    max_results: int = 1000,
) -> list[dict]:
    """Search for EarthCARE data using STAC API.

    Parameters
    ----------
    bbox : BoundingBox
        Spatial bounds [lat_min, lat_max, lon_min, lon_max]
    start_date : str
        Start date in YYYY-MM-DD format
    end_date : str
        End date in YYYY-MM-DD format
    product : str
        EarthCARE product type (default: MSI_COP for precipitation)
    max_results : int
        Maximum number of results to return (default: 1000)

    Returns
    -------
    list[dict]
        List of STAC items matching the search criteria

    Raises
    ------
    KeyError
        If the product is not recognized
    requests.RequestException
        If the STAC search fails
    """

    if product not in EARTHCARE_PRODUCTS:
        available = ", ".join(EARTHCARE_PRODUCTS.keys())
        raise KeyError(f"Unknown product '{product}'. Available: {available}")

    collection_id = EARTHCARE_PRODUCTS[product]["collection_id"]

    # Build STAC search query
    # STAC supports CQL2 filtering with standard operators
    search_query = {
        "collections": [collection_id],
        "bbox": [bbox.lon_min, bbox.lat_min, bbox.lon_max, bbox.lat_max],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "limit": min(max_results, 100),  # STAC pagination: fetch in chunks
    }

    logger.info(f"Searching for {product} EarthCARE data...")
    logger.info(f"  Collection: {collection_id}")
    logger.info(f"  Bbox: [{bbox.lon_min}, {bbox.lat_min}, {bbox.lon_max}, {bbox.lat_max}]")
    logger.info(f"  Date range: {start_date} to {end_date}")

    all_items = []
    offset = 0

    try:
        while len(all_items) < max_results:
            # Paginated search
            response = requests.post(
                ESA_MAAP_SEARCH_ENDPOINT,
                json=search_query,
                timeout=ORCESTRA_CONFIG['timeout'],
            )
            response.raise_for_status()

            data = response.json()
            items = data.get("features", [])

            if not items:
                logger.info(f"No more items found (returned to {len(all_items)} total)")
                break

            all_items.extend(items)
            logger.info(f"Found {len(items)} items (total: {len(all_items)})")

            # Check if there are more pages
            links = data.get("links", [])
            next_link = next((link for link in links if link.get("rel") == "next"), None)

            if not next_link:
                break

            # Prepare for next page
            search_query["limit"] = len(items)
            offset += len(items)

        logger.info(f"Total items found: {len(all_items)}")
        return all_items

    except requests.RequestException as e:
        logger.error(f"STAC search failed: {e}")
        raise


def download_file(
    url: str,
    output_path: Path,
    max_retries: int = 3,
) -> bool:
    """Download a single file with retry logic.

    Parameters
    ----------
    url : str
        HTTP URL to download from
    output_path : Path
        Local file path to save to
    max_retries : int
        Maximum number of retry attempts

    Returns
    -------
    bool
        True if successful, False otherwise
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            logger.info(f"  Downloading: {output_path.name}...", end=" ", flush=True)

            response = requests.get(
                url,
                timeout=ORCESTRA_CONFIG['timeout'],
                stream=True,
            )
            response.raise_for_status()

            # Get file size
            file_size = int(response.headers.get('content-length', 0))
            size_mb = file_size / 1e6

            # Write to file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logger.info(f"✓ ({size_mb:.1f} MB)")
            return True

        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.info(f"✗ Retry {attempt + 1}/{max_retries - 1}...")
            else:
                logger.info(f"✗ Failed")
                logger.error(f"Download failed for {output_path.name}: {e}")

    return False


def download_earthcare_stac(
    bbox: BoundingBox,
    date_range: tuple[str, str],
    output_dir: Path,
    product: str = "MSI_COP",
    skip_existing: bool = True,
) -> list[Path]:
    """Download EarthCARE data using ESA MAAP STAC API.

    Parameters
    ----------
    bbox : BoundingBox
        Spatial bounds for data download
    date_range : tuple[str, str]
        (start_date, end_date) in YYYY-MM-DD format
    output_dir : Path
        Directory to save downloaded NetCDF files
    product : str
        EarthCARE product type (default: MSI_COP)
    skip_existing : bool
        If True, skip files already downloaded

    Returns
    -------
    list[Path]
        List of successfully downloaded file paths
    """

    print("=" * 70)
    print(f"EarthCARE STAC Data Download ({EARTHCARE_PRODUCTS[product]['description']})")
    print("=" * 70)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSearching parameters:")
    print(f"  Bbox: lon [{bbox.lon_min}, {bbox.lon_max}], lat [{bbox.lat_min}, {bbox.lat_max}]")
    print(f"  Date range: {date_range[0]} to {date_range[1]}")
    print(f"  Product: {product}")
    print(f"  Output directory: {output_dir}\n")

    # Search for data
    try:
        items = search_earthcare_data(
            bbox=bbox,
            start_date=date_range[0],
            end_date=date_range[1],
            product=product,
        )
    except Exception as e:
        logger.error(f"Failed to search STAC catalog: {e}")
        return []

    if not items:
        logger.warning("No EarthCARE data found for the specified search criteria")
        return []

    # Download files
    downloaded_files = []
    failed_files = []

    logger.info(f"\n{'=' * 70}")
    logger.info(f"Downloading {len(items)} files...\n")

    for i, item in enumerate(items, 1):
        # Extract download links from STAC item
        assets = item.get("assets", {})

        # Look for NetCDF or data files
        download_urls = {}
        for asset_key, asset_info in assets.items():
            if asset_key in ["data", "nc", "NetCDF"] or "hdf5" in asset_key.lower() or "h5" in asset_key.lower():
                download_urls[asset_key] = asset_info.get("href", "")

        if not download_urls:
            logger.warning(f"No data assets found for item {i}/{len(items)}")
            continue

        # Download each asset
        for asset_key, url in download_urls.items():
            if not url:
                continue

            # Generate output filename
            item_id = item.get("id", f"item_{i}").replace("/", "_")
            ext = Path(url.split("?")[0]).suffix or ".nc"  # Remove query params
            filename = f"{item_id}_{asset_key}{ext}"
            output_path = output_dir / filename

            # Skip if exists
            if output_path.exists() and skip_existing:
                logger.info(f"  Skipping {filename} (already exists)")
                downloaded_files.append(output_path)
                continue

            # Download
            if download_file(url, output_path):
                downloaded_files.append(output_path)
            else:
                failed_files.append(filename)

    # Summary
    print("\n" + "=" * 70)
    print(f"✓ EarthCARE STAC Download Complete!")
    print(f"  Total items: {len(items)}")
    print(f"  Successfully downloaded: {len(downloaded_files)}")
    if failed_files:
        print(f"  Failed: {len(failed_files)}")
        for fname in failed_files[:5]:
            print(f"    - {fname}")
        if len(failed_files) > 5:
            print(f"    ... and {len(failed_files) - 5} more")
    print(f"  Output directory: {output_dir}")
    print("=" * 70)

    return downloaded_files


def clean_earthcare(ds: xr.Dataset, bbox: BoundingBox) -> xr.Dataset:
    """Standardize EarthCARE data and crop to bounding box.

    Parameters
    ----------
    ds : xr.Dataset
        Dataset loaded from EarthCARE NetCDF
    bbox : BoundingBox
        Bounding box for spatial cropping

    Returns
    -------
    xr.Dataset
        Cleaned and cropped dataset
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


def process_and_merge_earthcare(
    input_dir: Path,
    output_path: Path,
    bbox: BoundingBox,
    dask_workers: int = 4,
    dask_memory: str = "1800MiB",
) -> bool:
    """Merge and process EarthCARE files into standardized NetCDF.

    Parameters
    ----------
    input_dir : Path
        Directory containing downloaded EarthCARE files
    output_path : Path
        Output NetCDF file path
    bbox : BoundingBox
        Bounding box for spatial cropping
    dask_workers : int
        Number of Dask workers for parallel processing
    dask_memory : str
        Memory limit per Dask worker

    Returns
    -------
    bool
        True if successful, False otherwise
    """

    import glob

    logger.info("\n" + "=" * 70)
    logger.info("Merging and processing EarthCARE files...")
    logger.info("=" * 70)

    # Find all NetCDF/HDF5 files
    input_files = sorted(
        glob.glob(str(input_dir / "**" / "*.nc"), recursive=True) +
        glob.glob(str(input_dir / "**" / "*.h5"), recursive=True)
    )

    if not input_files:
        logger.error(f"No data files found in {input_dir}")
        return False

    logger.info(f"Found {len(input_files)} files to process")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = Client(
        n_workers=dask_workers,
        threads_per_worker=1,
        memory_limit=dask_memory,
    )
    ds_earthcare = None

    try:
        logger.info(f"Dask dashboard: {client.dashboard_link}")

        # Open and merge files
        logger.info("Opening and merging files...")
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

        # Remove ancillary coordinate variables
        ds_earthcare = ds_earthcare.drop_vars(
            ["time_bnds", "lat_bnds", "lon_bnds"],
            errors="ignore",
        )

        # Ensure precipitation variable exists
        if "precipitation" not in ds_earthcare.data_vars:
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
                    "Could not find precipitation variable. "
                    f"Available: {', '.join(ds_earthcare.data_vars)}"
                )

        # Encode and write
        encoding = {var: {"zlib": True, "complevel": 4} for var in ds_earthcare.data_vars}
        logger.info(f"Writing merged NetCDF to {output_path}...")
        ds_earthcare.to_netcdf(
            output_path,
            mode="w",
            format="NETCDF4",
            encoding=encoding,
            compute=True,
        )

        logger.info(f"✓ Merged EarthCARE written to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to merge EarthCARE files: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if ds_earthcare is not None:
            ds_earthcare.close()
        client.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Download and process EarthCARE data using ESA MAAP STAC API"
    )
    parser.add_argument(
        "--lat-min",
        type=float,
        default=None,
        help="Minimum latitude (default: from config.py)",
    )
    parser.add_argument(
        "--lat-max",
        type=float,
        default=None,
        help="Maximum latitude (default: from config.py)",
    )
    parser.add_argument(
        "--lon-min",
        type=float,
        default=None,
        help="Minimum longitude (default: from config.py)",
    )
    parser.add_argument(
        "--lon-max",
        type=float,
        default=None,
        help="Maximum longitude (default: from config.py)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=ORCESTRA_CONFIG['start_date'],
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=ORCESTRA_CONFIG['end_date'],
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for downloads (default: from config.py)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Output NetCDF path (default: from config.py)",
    )
    parser.add_argument(
        "--product",
        type=str,
        default="MSI_COP",
        choices=list(EARTHCARE_PRODUCTS.keys()),
        help="EarthCARE product type",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download and use existing files in output-dir",
    )
    parser.add_argument(
        "--list-collections",
        action="store_true",
        help="List available EarthCARE collections and exit",
    )

    return parser.parse_args()


def main():
    """Main workflow: search, download, and process EarthCARE data."""

    args = parse_args()

    # List collections if requested
    if args.list_collections:
        try:
            collections = list_earthcare_collections()
            print("\nAvailable EarthCARE Collections:")
            print("=" * 70)
            for coll_id, metadata in collections.items():
                print(f"\n  Collection ID: {coll_id}")
                print(f"    Title: {metadata.get('title', 'N/A')}")
                print(f"    Description: {metadata.get('description', 'N/A')}")
            print("\n" + "=" * 70)
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
        return

    # Get bounding box from args or config
    bbox = default_earthcare_bbox()
    if args.lat_min is not None:
        bbox.lat_min = args.lat_min
    if args.lat_max is not None:
        bbox.lat_max = args.lat_max
    if args.lon_min is not None:
        bbox.lon_min = args.lon_min
    if args.lon_max is not None:
        bbox.lon_max = args.lon_max

    output_dir = args.output_dir or default_earthcare_input_dir()
    output_path = args.output_path or default_earthcare_output_path()
    date_range = (args.start_date, args.end_date)

    logger.info("Starting EarthCARE STAC download workflow...")

    # Step 1: Download data (if not skipping)
    if not args.skip_download:
        downloaded_files = download_earthcare_stac(
            bbox=bbox,
            date_range=date_range,
            output_dir=output_dir,
            product=args.product,
            skip_existing=True,
        )

        if not downloaded_files:
            logger.warning("No files downloaded. Checking for existing files...")

    # Step 2: Process and merge
    success = process_and_merge_earthcare(
        input_dir=output_dir,
        output_path=output_path,
        bbox=bbox,
    )

    if success:
        logger.info("\n✓ EarthCARE processing complete!")
    else:
        logger.error("\n✗ EarthCARE processing failed")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
