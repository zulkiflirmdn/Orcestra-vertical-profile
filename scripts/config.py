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


# EarthCARE functions removed — EarthCARE is dropped from this project (2026-05-04).
