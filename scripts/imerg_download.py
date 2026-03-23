#!/usr/bin/env python3
"""Download IMERG data from NASA Earthdata for ORCESTRA campaign."""

import argparse
import os
from pathlib import Path
from typing import Tuple

import earthaccess

from scripts.config import (
    default_imerg_bbox,
    default_imerg_input_dir,
    BoundingBox,
)


def download_imerg(
    bbox: BoundingBox,
    date_range: Tuple[str, str],
    output_dir: Path,
    skip_existing: bool = True,
) -> list:
    """
    Download IMERG data from NASA Earthdata using earthaccess.

    Parameters
    ----------
    bbox : BoundingBox
        Bounding box with lat_min, lat_max, lon_min, lon_max
    date_range : tuple
        Tuple of (start_date, end_date) in 'YYYY-MM-DD' format
    output_dir : Path
        Directory to save down HDF5 files
    skip_existing : bool
        If True, only download files not already in output_dir

    Returns
    -------
    list
        List of downloaded file paths
    """
    # Authenticate
    print("Authenticating with NASA Earthdata...")
    auth = earthaccess.login()
    if not auth:
        raise RuntimeError("Failed to authenticate with earthaccess")
    print("✓ Authenticated successfully")

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Convert BoundingBox to earthaccess format: (lon_min, lat_min, lon_max, lat_max)
    search_bbox = (bbox.lon_min, bbox.lat_min, bbox.lon_max, bbox.lat_max)
    print(f"Search region: lon [{bbox.lon_min}, {bbox.lon_max}], lat [{bbox.lat_min}, {bbox.lat_max}]")
    print(f"Date range: {date_range[0]} to {date_range[1]}")

    # Search for GPM IMERG Final Run (Half-Hourly)
    print("\nSearching for GPM_3IMERGHH files...")
    results = earthaccess.search_data(
        short_name="GPM_3IMERGHH",
        bounding_box=search_bbox,
        temporal=date_range,
    )

    if not results:
        print("❌ No files found for this region and date range")
        return []

    print(f"✓ Found {len(results)} half-hourly files")

    # Download files
    print("\nDownloading files...")
    downloaded_files = earthaccess.download(
        results,
        local_path=str(output_dir),
    )

    print(f"✓ Downloaded {len(downloaded_files)} files to {output_dir}")
    return downloaded_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download IMERG data from NASA Earthdata"
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
        default="2024-08-10",
        help="Start date in YYYY-MM-DD format (default: 2024-08-10)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2024-09-30",
        help="End date in YYYY-MM-DD format (default: 2024-09-30)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: from config.py)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they exist locally",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Get bounding box from args or config
    bbox = default_imerg_bbox()
    if args.lat_min is not None:
        bbox.lat_min = args.lat_min
    if args.lat_max is not None:
        bbox.lat_max = args.lat_max
    if args.lon_min is not None:
        bbox.lon_min = args.lon_min
    if args.lon_max is not None:
        bbox.lon_max = args.lon_max

    output_dir = args.output_dir or default_imerg_input_dir()

    date_range = (args.start_date, args.end_date)

    download_imerg(
        bbox=bbox,
        date_range=date_range,
        output_dir=output_dir,
        skip_existing=not args.force,
    )
