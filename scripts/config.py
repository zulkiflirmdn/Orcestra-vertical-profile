#!/usr/bin/env python3
"""Centralized paths and region settings for ORCESTRA processing scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BoundingBox:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


def default_imerg_bbox() -> BoundingBox:
    """Return IMERG crop bounds with env-var override support.

    Domain: 0N-30N, 70W-0W (per SPEC_sonde_vs_satellite.md)
    To use this wider domain, ensure GPM IMERG HDF5 files cover the full extent
    at /g/data/k10/zr7147/GPM_IMERG_Data/
    """

    return BoundingBox(
        lat_min=float(os.environ.get("ORCESTRA_LAT_MIN", "0")),
        lat_max=float(os.environ.get("ORCESTRA_LAT_MAX", "30")),
        lon_min=float(os.environ.get("ORCESTRA_LON_MIN", "-70")),
        lon_max=float(os.environ.get("ORCESTRA_LON_MAX", "0")),
    )


def default_imerg_input_dir() -> Path:
    """Directory containing downloaded IMERG HDF5 files."""

    return Path(os.environ.get("ORCESTRA_IMERG_INPUT_DIR", "/g/data/k10/zr7147/GPM_IMERG_Data"))


def default_imerg_output_path() -> Path:
    """Output path for merged/cropped IMERG NetCDF."""

    return Path(
        os.environ.get(
            "ORCESTRA_IMERG_OUTPUT_PATH",
            "/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc",
        )
    )


def default_era5_dir() -> Path:
    """Root directory for ERA5 reanalysis data."""
    return Path(os.environ.get("ORCESTRA_ERA5_DIR", "/g/data/k10/zr7147/ERA5"))


def default_era5_omega_path() -> Path:
    """ERA5 pressure-velocity (omega) file on pressure levels."""
    return Path(
        os.environ.get(
            "ORCESTRA_ERA5_OMEGA_PATH",
            "/g/data/k10/zr7147/ERA5/era5_omega_pressure_levels.nc",
        )
    )


def default_earthcare_bbox() -> BoundingBox:
    """Return EarthCARE crop bounds (same as IMERG for consistency).

    Domain: 0N-30N, 70W-0W (per SPEC)
    """

    return BoundingBox(
        lat_min=float(os.environ.get("ORCESTRA_EARTHCARE_LAT_MIN", "0")),
        lat_max=float(os.environ.get("ORCESTRA_EARTHCARE_LAT_MAX", "30")),
        lon_min=float(os.environ.get("ORCESTRA_EARTHCARE_LON_MIN", "-70")),
        lon_max=float(os.environ.get("ORCESTRA_EARTHCARE_LON_MAX", "0")),
    )


def default_earthcare_input_dir() -> Path:
    """Directory containing downloaded EarthCARE data files.

    User must set G-Portal credentials before downloading.
    See scripts/earthcare_preprocessing.py for credential configuration.
    """

    return Path(os.environ.get("ORCESTRA_EARTHCARE_INPUT_DIR", "/g/data/k10/zr7147/EarthCARE_Data"))


def default_earthcare_output_path() -> Path:
    """Output path for merged/cropped EarthCARE NetCDF."""

    return Path(
        os.environ.get(
            "ORCESTRA_EARTHCARE_OUTPUT_PATH",
            "/g/data/k10/zr7147/ORCESTRA_EarthCARE_Combined_Cropped.nc",
        )
    )


def earthcare_credentials() -> dict:
    """Return ESA Earth Online credentials for earthcare-downloader.

    IMPORTANT: Set these environment variables with your ESA account credentials.
    - ESA_EO_USERNAME: Your ESA Earth Online username
    - ESA_EO_PASSWORD: Your ESA Earth Online password

    Example:
        export ESA_EO_USERNAME="your_username"
        export ESA_EO_PASSWORD="your_password"
    """

    return {
        "username": os.environ.get("ESA_EO_USERNAME"),
        "password": os.environ.get("ESA_EO_PASSWORD"),
    }


# ════════════════════════════════════════════════════════════════════════════════════
# ORCESTRA Campaign EarthCARE Download Configuration
# ════════════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OrcuestraEarthcareConfig:
    """ORCESTRA-specific EarthCARE download parameters."""

    # Geographic Domain
    lat_min: float = 0  # 0°N
    lat_max: float = 30  # 30°N
    lon_min: float = -70  # 70°W
    lon_max: float = 0  # 0°W

    # Time Period
    start_date: str = "2024-08-10"  # YYYY-MM-DD
    end_date: str = "2024-09-30"  # YYYY-MM-DD

    # Products to Download
    products: tuple = ("CPR_CLP_2A", "CPR_ECO_2A", "AC__CLP_2B")

    # Download Settings
    max_workers: int = 5  # Concurrent downloads
    force_redownload: bool = False  # Skip existing files
    unzip_files: bool = True  # Auto-unzip archives
    organize_by_product: bool = True  # Create product subdirectories


def orcestra_earthcare_config() -> OrcuestraEarthcareConfig:
    """Get ORCESTRA EarthCARE download configuration with env-var overrides."""

    return OrcuestraEarthcareConfig(
        lat_min=float(os.environ.get("ORCESTRA_EARTHCARE_LAT_MIN", "0")),
        lat_max=float(os.environ.get("ORCESTRA_EARTHCARE_LAT_MAX", "30")),
        lon_min=float(os.environ.get("ORCESTRA_EARTHCARE_LON_MIN", "-70")),
        lon_max=float(os.environ.get("ORCESTRA_EARTHCARE_LON_MAX", "0")),
        start_date=os.environ.get("ORCESTRA_EARTHCARE_START", "2024-08-10"),
        end_date=os.environ.get("ORCESTRA_EARTHCARE_END", "2024-09-30"),
        max_workers=int(os.environ.get("ORCESTRA_EARTHCARE_WORKERS", "5")),
        force_redownload=os.environ.get("ORCESTRA_EARTHCARE_FORCE", "false").lower() == "true",
        unzip_files=os.environ.get("ORCESTRA_EARTHCARE_UNZIP", "true").lower() == "true",
    )
