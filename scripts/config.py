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
    """Return G-Portal credentials and configuration.

    IMPORTANT: Edit these values with your G-Portal account credentials.
    Username and password should be stored securely.
    """

    return {
        "username": os.environ.get("EARTHCARE_USERNAME", "YOUR_GPORTAL_USERNAME"),
        "password": os.environ.get("EARTHCARE_PASSWORD", "YOUR_GPORTAL_PASSWORD"),
        # G-Portal API endpoint (may vary by region/version)
        "gportal_url": os.environ.get(
            "EARTHCARE_GPORTAL_URL",
            "https://gportal.jaxa.jp/gw/",
        ),
    }
