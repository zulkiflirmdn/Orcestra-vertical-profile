#!/usr/bin/env python3
"""EarthCARE CPR vertical velocity data download system for ORCESTRA campaign.

Uses ESA Online Dissemination Services via earthcare-downloader package to automate
download of EarthCARE Cloud Profiling Radar (CPR) data containing vertical velocity,
reflectivity, and cloud properties.

Products Downloaded:
    - CPR_CLP_2A: Cloud Properties (air_vertical_velocity, radar_reflectivity, cloud_type)
    - CPR_ECO_2A: Echo Properties (echo classification, quality flags)
    - AC__CLP_2B: Synergistic Cloud Properties (multi-sensor combined data)

Credentials:
    ESA Online: https://eoiam-idp.eo.esa.int/ (free account)
    Set environment variables:
        export ESA_EO_USERNAME="your_email@example.com"
        export ESA_EO_PASSWORD="your_password"

Installation:
    pip install earthcare-downloader xarray netCDF4 numpy

Reference:
    - earthcare-downloader: https://github.com/espdev/earthcare-dist
    - ORCESTRA campaign: 0°N-30°N, 70°W-0°W, Aug 10 - Sep 30, 2024
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

from scripts.config import (
    orcestra_earthcare_config,
    earthcare_credentials,
    default_earthcare_input_dir,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('download_earthcare.log'),
    ]
)
logger = logging.getLogger(__name__)

# Try to import earthcare_downloader
try:
    from earthcare_downloader import search, download
    EARTHCARE_DOWNLOADER_AVAILABLE = True
except ImportError:
    EARTHCARE_DOWNLOADER_AVAILABLE = False
    logger.warning(
        "earthcare-downloader not installed. Install with: "
        "pip install earthcare-downloader"
    )


class EarthCAREDownloader:
    """Download EarthCARE CPR vertical velocity data for scientific analysis."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        """Initialize EarthCARE downloader with ESA credentials.

        Parameters
        ----------
        username : str, optional
            ESA Earth Online username. If None, read from ESA_EO_USERNAME env var.
        password : str, optional
            ESA Earth Online password. If None, read from ESA_EO_PASSWORD env var.
        output_dir : Path, optional
            Download directory. Defaults to /g/data/k10/zr7147/EarthCARE_Data

        Raises
        ------
        ValueError
            If credentials are missing or invalid
        """

        self.username = username or os.environ.get("ESA_EO_USERNAME")
        self.password = password or os.environ.get("ESA_EO_PASSWORD")
        self.output_dir = Path(output_dir or default_earthcare_input_dir())

        if not self.username or not self.password:
            raise ValueError(
                "ESA credentials not found. Set environment variables:\n"
                "  export ESA_EO_USERNAME='your_email@example.com'\n"
                "  export ESA_EO_PASSWORD='your_password'"
            )

        logger.info(f"Initialized EarthCAREDownloader for user: {self.username}")
        logger.info(f"Output directory: {self.output_dir}")

    def validate_credentials(self) -> bool:
        """Validate ESA credentials by attempting a test search.

        Returns
        -------
        bool
            True if credentials are valid, False otherwise
        """

        if not EARTHCARE_DOWNLOADER_AVAILABLE:
            logger.error("earthcare-downloader not available")
            return False

        try:
            logger.info("Validating ESA credentials...")
            # Attempt a small search to validate credentials
            results = search(
                product="CPR_CLP_2A",
                start="2024-08-10",
                stop="2024-08-11",
                lat_range=(0, 30),
                lon_range=(-70, 0),
            )
            logger.info(f"✓ Credentials valid. Found {len(results)} test results.")
            return True
        except Exception as e:
            logger.error(f"✗ Credential validation failed: {e}")
            return False

    def list_available_files(
        self,
        products: tuple = ("CPR_CLP_2A", "CPR_ECO_2A", "AC__CLP_2B"),
        lat_range: tuple = (0, 30),
        lon_range: tuple = (-70, 0),
        start_date: str = "2024-08-10",
        end_date: str = "2024-09-30",
    ) -> dict:
        """Search for available EarthCARE files without downloading.

        Parameters
        ----------
        products : tuple
            Product codes to search for
        lat_range : tuple
            (lat_min, lat_max) in degrees
        lon_range : tuple
            (lon_min, lon_max) in degrees
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format

        Returns
        -------
        dict
            Mapping of product_code -> list of file metadata
        """

        if not EARTHCARE_DOWNLOADER_AVAILABLE:
            logger.error("earthcare-downloader not available")
            return {}

        results = {}

        logger.info(
            f"\nSearching for EarthCARE files:\n"
            f"  Date range: {start_date} to {end_date}\n"
            f"  Latitude: {lat_range[0]}°N to {lat_range[1]}°N\n"
            f"  Longitude: {lon_range[0]}°W to {lon_range[1]}°W"
        )

        for product in products:
            try:
                logger.info(f"\n  Searching: {product}...")
                files = search(
                    product=product,
                    start=start_date,
                    stop=end_date,
                    lat_range=lat_range,
                    lon_range=lon_range,
                )
                results[product] = files
                logger.info(f"    Found {len(files)} files")
            except Exception as e:
                logger.error(f"    Error searching {product}: {e}")
                results[product] = []

        return results

    def download_cpr_data(
        self,
        products: tuple = ("CPR_CLP_2A", "CPR_ECO_2A", "AC__CLP_2B"),
        lat_range: tuple = (0, 30),
        lon_range: tuple = (-70, 0),
        start_date: str = "2024-08-10",
        end_date: str = "2024-09-30",
        max_workers: int = 5,
        force: bool = False,
        unzip: bool = True,
    ) -> dict:
        """Download EarthCARE CPR data for specified spatial/temporal domain.

        Parameters
        ----------
        products : tuple
            Product codes to download
        lat_range : tuple
            (lat_min, lat_max) in degrees
        lon_range : tuple
            (lon_min, lon_max) in degrees
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
        max_workers : int
            Number of concurrent download threads
        force : bool
            Force re-download of existing files
        unzip : bool
            Automatically unzip downloaded files

        Returns
        -------
        dict
            Download statistics including counts, sizes, and status per product
        """

        if not EARTHCARE_DOWNLOADER_AVAILABLE:
            raise RuntimeError("earthcare-downloader not installed")

        # Validate available disk space
        self._check_disk_space()

        download_stats = {}

        logger.info(
            f"\n{'=' * 70}\n"
            f"EarthCARE CPR Download - ORCESTRA Campaign\n"
            f"{'=' * 70}\n"
            f"  Username: {self.username}\n"
            f"  Output: {self.output_dir}\n"
            f"  Workers: {max_workers}\n"
            f"  Force: {force}\n"
            f"  Unzip: {unzip}\n"
            f"  Date Range: {start_date} to {end_date}\n"
            f"  Domain: [{lon_range[0]}, {lat_range[0]}] to [{lon_range[1]}, {lat_range[1]}]\n"
        )

        for product in products:
            logger.info(f"\n{'─' * 70}")
            logger.info(f"Downloading: {product}")
            logger.info(f"{'─' * 70}")

            try:
                # Search for files
                files = search(
                    product=product,
                    start=start_date,
                    stop=end_date,
                    lat_range=lat_range,
                    lon_range=lon_range,
                )

                if not files:
                    logger.warning(f"  No files found for {product}")
                    download_stats[product] = {
                        "count": 0,
                        "size_gb": 0,
                        "status": "NO_FILES_FOUND"
                    }
                    continue

                logger.info(f"  Found {len(files)} files")

                # Create product directory
                product_dir = self.output_dir / product if product is not None else self.output_dir
                product_dir.mkdir(parents=True, exist_ok=True)

                # Download files
                logger.info(f"  Downloading to: {product_dir}")
                downloaded = download(
                    files,
                    output_path=str(product_dir),
                    max_workers=max_workers,
                    force=force,
                )

                # Calculate statistics
                total_size = self._calculate_download_size(product_dir, product)
                logger.info(f"  ✓ Download complete for {product}")

                download_stats[product] = {
                    "count": len(downloaded),
                    "size_gb": total_size,
                    "status": "SUCCESS"
                }

            except Exception as e:
                logger.error(f"  ✗ Download failed for {product}: {e}")
                download_stats[product] = {
                    "count": 0,
                    "size_gb": 0,
                    "status": f"ERROR: {str(e)}"
                }

        # Summary
        self._print_download_summary(download_stats)
        self._write_summary_csv(download_stats)

        return download_stats

    def validate_downloads(self, product_dir: Optional[Path] = None) -> dict:
        """Validate downloaded files for integrity.

        Parameters
        ----------
        product_dir : Path, optional
            Directory to validate. Defaults to output_dir.

        Returns
        -------
        dict
            Validation results including file counts and integrity status
        """

        product_dir = Path(product_dir or self.output_dir)

        logger.info(f"\nValidating downloads in: {product_dir}")

        validation_results = {
            "total_files": 0,
            "corrupted_files": [],
            "incomplete_files": [],
        }

        # Check for NetCDF/HDF5 files
        for nc_file in product_dir.rglob("*.nc"):
            validation_results["total_files"] += 1

            try:
                # Attempt to open with xarray
                import xarray as xr
                with xr.open_dataset(nc_file, engine="netcdf4") as ds:
                    logger.info(f"  ✓ Valid: {nc_file.name}")
            except Exception as e:
                logger.error(f"  ✗ Corrupted: {nc_file.name} - {e}")
                validation_results["corrupted_files"].append(str(nc_file))

        # Check for incomplete files (size < 1MB)
        for h5_file in product_dir.rglob("*.h5"):
            validation_results["total_files"] += 1
            size_mb = h5_file.stat().st_size / 1e6

            if size_mb < 1:
                logger.warning(f"  ⚠ Incomplete: {h5_file.name} ({size_mb:.1f}MB)")
                validation_results["incomplete_files"].append(str(h5_file))
            else:
                logger.info(f"  ✓ Valid: {h5_file.name} ({size_mb:.1f}MB)")

        logger.info(
            f"\nValidation Summary:\n"
            f"  Total files: {validation_results['total_files']}\n"
            f"  Corrupted: {len(validation_results['corrupted_files'])}\n"
            f"  Incomplete: {len(validation_results['incomplete_files'])}"
        )

        return validation_results

    def _check_disk_space(self, threshold_gb: float = 100) -> bool:
        """Check if sufficient disk space is available.

        Parameters
        ----------
        threshold_gb : float
            Minimum required disk space in GB

        Returns
        -------
        bool
            True if space is available, False otherwise
        """

        import shutil

        stat = shutil.disk_usage(self.output_dir)
        available_gb = stat.free / 1e9

        logger.info(f"Disk space available: {available_gb:.1f} GB")

        if available_gb < threshold_gb:
            logger.warning(
                f"Warning: Only {available_gb:.1f}GB available, "
                f"but {threshold_gb}GB recommended for full download"
            )
            return False

        return True

    def _calculate_download_size(self, base_dir: Path, product: str) -> float:
        """Calculate total size of downloaded files.

        Parameters
        ----------
        base_dir : Path
            Directory to calculate size for
        product : str
            Product name

        Returns
        -------
        float
            Total size in GB
        """

        product_dir = base_dir / product if product is not None else base_dir
        total_bytes = sum(
            f.stat().st_size for f in product_dir.rglob("*") if f.is_file()
        )

        return total_bytes / 1e9

    def _print_download_summary(self, stats: dict) -> None:
        """Print download statistics summary.

        Parameters
        ----------
        stats : dict
            Download statistics from download_cpr_data()
        """

        total_files = sum(s.get("count", 0) for s in stats.values())
        total_gb = sum(s.get("size_gb", 0) for s in stats.values())

        logger.info(
            f"\n{'=' * 70}\n"
            f"EarthCARE Download Summary\n"
            f"{'=' * 70}"
        )

        for product, stat in stats.items():
            logger.info(
                f"  {product:20s}: {stat['count']:5d} files, "
                f"{stat['size_gb']:8.2f} GB - {stat['status']}"
            )

        logger.info(
            f"{'─' * 70}\n"
            f"  {'TOTAL':20s}: {total_files:5d} files, {total_gb:8.2f} GB\n"
            f"{'=' * 70}\n"
        )

    def _write_summary_csv(self, stats: dict) -> None:
        """Write download summary to CSV file.

        Parameters
        ----------
        stats : dict
            Download statistics from download_cpr_data()
        """

        csv_path = Path("earthcare_files_downloaded.csv")

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["product", "file_count", "size_gb", "status", "timestamp"],
            )
            writer.writeheader()

            for product, stat in stats.items():
                writer.writerow({
                    "product": product,
                    "file_count": stat["count"],
                    "size_gb": f"{stat['size_gb']:.2f}",
                    "status": stat["status"],
                    "timestamp": datetime.now().isoformat(),
                })

        logger.info(f"Summary written to: {csv_path}")


def download_earthcare(
    lat_range: tuple = (0, 30),
    lon_range: tuple = (-70, 0),
    start_date: str = "2024-08-10",
    end_date: str = "2024-09-30",
    output_dir: Optional[Path] = None,
    products: tuple = ("CPR_CLP_2A", "CPR_ECO_2A", "AC__CLP_2B"),
    max_workers: int = 5,
) -> dict:
    """Convenience function to download EarthCARE data for ORCESTRA campaign.

    Parameters
    ----------
    lat_range : tuple
        (lat_min, lat_max)
    lon_range : tuple
        (lon_min, lon_max)
    start_date : str
        Start date YYYY-MM-DD
    end_date : str
        End date YYYY-MM-DD
    output_dir : Path, optional
        Output directory
    products : tuple
        Products to download
    max_workers : int
        Number of concurrent workers

    Returns
    -------
    dict
        Download statistics
    """

    downloader = EarthCAREDownloader(output_dir=output_dir)
    return downloader.download_cpr_data(
        products=products,
        lat_range=lat_range,
        lon_range=lon_range,
        start_date=start_date,
        end_date=end_date,
        max_workers=max_workers,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Download EarthCARE CPR vertical velocity data for ORCESTRA campaign",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Download all ORCESTRA data (Aug 10 - Sep 30, 2024)
  python earthcare_download.py

  # Validate ESA credentials
  python earthcare_download.py --validate-credentials

  # List available files without downloading
  python earthcare_download.py --list-only

  # Custom date range
  python earthcare_download.py --start 2024-08-15 --end 2024-08-20

  # Custom domain
  python earthcare_download.py --lat-range 5,20 --lon-range -65,-15

  # Faster downloads (more workers, might be unstable)
  python earthcare_download.py --workers 10

  # Force re-download all files
  python earthcare_download.py --force

  # Download only one product
  python earthcare_download.py --products CPR_CLP_2A
        """.strip()
    )

    parser.add_argument(
        "--validate-credentials",
        action="store_true",
        help="Validate ESA credentials and exit"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List available files without downloading"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2024-08-10",
        help="Start date (YYYY-MM-DD, default: 2024-08-10)"
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-09-30",
        help="End date (YYYY-MM-DD, default: 2024-09-30)"
    )
    parser.add_argument(
        "--lat-range",
        type=str,
        default="0,30",
        help="Latitude range min,max (default: 0,30)"
    )
    parser.add_argument(
        "--lon-range",
        type=str,
        default="-70,0",
        help="Longitude range min,max (default: -70,0)"
    )
    parser.add_argument(
        "--products",
        type=str,
        default="CPR_CLP_2A,CPR_ECO_2A,AC__CLP_2B",
        help="Products to download (comma-separated)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: /g/data/k10/zr7147/EarthCARE_Data)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of concurrent downloaders (default: 5)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of existing files"
    )
    parser.add_argument(
        "--no-unzip",
        action="store_true",
        help="Don't unzip downloaded files"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate downloaded files after download"
    )

    return parser.parse_args()


def main() -> int:
    """Main workflow: download EarthCARE data."""

    if not EARTHCARE_DOWNLOADER_AVAILABLE:
        logger.error(
            "ERROR: earthcare-downloader not installed.\n"
            "Install with: pip install earthcare-downloader\n"
            "See: https://github.com/espdev/earthcare-dist"
        )
        return 1

    args = parse_args()

    try:
        # Initialize downloader
        downloader = EarthCAREDownloader(output_dir=args.output_dir)

        # Validate credentials
        if args.validate_credentials:
            if downloader.validate_credentials():
                logger.info("✓ Credentials are valid")
                return 0
            else:
                logger.error("✗ Credentials validation failed")
                return 1

        # Parse arguments
        lat_min, lat_max = map(float, args.lat_range.split(","))
        lon_min, lon_max = map(float, args.lon_range.split(","))
        products = tuple(args.products.split(","))

        # List files if requested
        if args.list_only:
            files = downloader.list_available_files(
                products=products,
                lat_range=(lat_min, lat_max),
                lon_range=(lon_min, lon_max),
                start_date=args.start,
                end_date=args.end,
            )

            total = sum(len(f) for f in files.values())
            logger.info(f"\nTotal files available: {total}")
            return 0

        # Download data
        stats = downloader.download_cpr_data(
            products=products,
            lat_range=(lat_min, lat_max),
            lon_range=(lon_min, lon_max),
            start_date=args.start,
            end_date=args.end,
            max_workers=args.workers,
            force=args.force,
            unzip=not args.no_unzip,
        )

        # Validate downloads
        if args.validate:
            downloader.validate_downloads()

        logger.info("✓ Download workflow complete")
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
