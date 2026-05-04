#!/usr/bin/env python3
"""Organisation and moisture metrics for ORCESTRA dropsonde circles.

Public functions:
    compute_rain_fraction_all_circles  — rain area fraction + intensity proxies from IMERG
    compute_scai_all_circles           — SCAI (Simple Convective Aggregation Index, Tobin et al. 2012)
    compute_object_classification      — object-based MCS/scattered classification from IMERG
    get_era5_tcwv_at_circles           — ERA5 total column water vapour sampled at each circle
    build_circle_metrics               — single merged DataFrame (recommended entry point)

All return a pd.DataFrame indexed by circle number so they can be merged with
BEACH L4 metadata for plotting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path
from scipy import ndimage

from scripts.config import default_imerg_output_path, default_era5_dir

# Tobin et al. (2012) threshold — fraction of pixels exceeding this is the rain fraction
RAIN_THRESHOLD_MM_HR: float = 0.5
# Stratiform/convective proxy split — Semie & Bony (2020)
STRAT_UPPER_MM_HR: float = 3.0
# Object-based classification thresholds (area in km²)
MCS_AREA_THRESHOLD_KM2: float = 10_000.0   # ≥ this → MCS-scale organised
SCATTERED_AREA_THRESHOLD_KM2: float = 2_000.0  # all objects < this → scattered
# IMERG pixel size at equator (0.1° ≈ 11.1 km → ~123 km²)
IMERG_PIXEL_AREA_KM2: float = 11.1 * 11.1  # approximate, refined per latitude below


def simplify_category(cat: str) -> str:
    """Map verbose BEACH L4 category strings to short labels."""
    if "Top-Heavy" in cat:
        return "Top-Heavy"
    if "Bottom-Heavy" in cat:
        return "Bottom-Heavy"
    if "Suppressed" in cat or "Weak" in cat:
        return "Suppressed"
    return "Other"


def _haversine_km(lat0: float, lon0: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Vectorised Haversine distance (km) from a point to arrays of coordinates."""
    R = 6371.0
    dlat = np.deg2rad(lats - lat0)
    dlon = np.deg2rad(lons - lon0)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.deg2rad(lat0)) * np.cos(np.deg2rad(lats)) * np.sin(dlon / 2) ** 2
    )
    return 2.0 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _pixels_in_circle(
    ds_imerg: xr.Dataset,
    time_idx: int,
    circle_lat: float,
    circle_lon: float,
    radius_m: float,
) -> np.ndarray:
    """Extract IMERG precipitation pixels within a dropsonde circle at one timestep."""
    radius_km = radius_m / 1000.0
    # Bounding box with small margin to speed up selection
    deg_margin = radius_km / 111.0 * 1.05
    lat_lo = max(float(ds_imerg["lat"].values[0]),  circle_lat - deg_margin)
    lat_hi = min(float(ds_imerg["lat"].values[-1]), circle_lat + deg_margin)
    lon_lo = max(float(ds_imerg["lon"].values[0]),  circle_lon - deg_margin)
    lon_hi = min(float(ds_imerg["lon"].values[-1]), circle_lon + deg_margin)

    crop = (
        ds_imerg["precipitation"]
        .isel(time=time_idx)
        .sel(lat=slice(lat_lo, lat_hi), lon=slice(lon_lo, lon_hi))
    )
    if crop.size == 0:
        return np.array([])

    lats2d, lons2d = np.meshgrid(crop["lat"].values, crop["lon"].values, indexing="ij")
    dist = _haversine_km(circle_lat, circle_lon, lats2d, lons2d)
    vals = crop.values[dist <= radius_km]
    return vals[np.isfinite(vals) & (vals >= 0)]


def compute_rain_fraction_all_circles(
    ds_sonde: xr.Dataset,
    ds_imerg: xr.Dataset | None = None,
    threshold: float = RAIN_THRESHOLD_MM_HR,
) -> pd.DataFrame:
    """Compute rain area fraction and intensity metrics per dropsonde circle.

    Parameters
    ----------
    ds_sonde:
        BEACH L4 dataset (from open_zarr).
    ds_imerg:
        Combined IMERG NetCDF (precipitation in mm/hr). If None, loads from
        the default path in config.py.
    threshold:
        Precipitation threshold in mm/hr defining a "rainy" pixel (default 0.5).

    Returns
    -------
    pd.DataFrame with columns:
        circle                    — circle index
        rain_fraction             — fraction of pixels > threshold  (Tobin et al. 2012)
        mean_precip_rate          — mean precip rate over rainy pixels (mm/hr)
        stratiform_proxy_frac     — fraction with 0.5–3.0 mm/hr  (widespread, moderate)
        convective_proxy_frac     — fraction with > 3.0 mm/hr     (intense, clustered)
        n_pixels                  — total pixels used
        imerg_time                — actual IMERG timestamp matched
    """
    if ds_imerg is None:
        ds_imerg = xr.open_dataset(str(default_imerg_output_path()))

    # IMERG time may be cftime objects (Julian calendar) — convert via ISO string
    raw_times = ds_imerg["time"].values
    if hasattr(raw_times[0], "strftime"):
        imerg_times = pd.to_datetime([t.strftime("%Y-%m-%dT%H:%M:%S") for t in raw_times])
    else:
        imerg_times = pd.to_datetime(raw_times)

    records = []
    for circle_idx in ds_sonde["circle"].values:
        c = ds_sonde.sel(circle=circle_idx)
        circle_lat = float(c["circle_lat"].values)
        circle_lon = float(c["circle_lon"].values)
        radius_m   = float(c["circle_radius"].values)
        circle_t   = pd.Timestamp(str(c["circle_time"].values))

        # Nearest IMERG half-hour
        time_idx = int(np.argmin(np.abs(imerg_times - circle_t)))
        matched_time = imerg_times[time_idx]

        pixels = _pixels_in_circle(ds_imerg, time_idx, circle_lat, circle_lon, radius_m)

        if pixels.size == 0:
            records.append({
                "circle": int(circle_idx),
                "rain_fraction": np.nan,
                "mean_precip_rate": np.nan,
                "stratiform_proxy_frac": np.nan,
                "convective_proxy_frac": np.nan,
                "n_pixels": 0,
                "imerg_time": matched_time,
            })
            continue

        n = pixels.size
        rain_mask = pixels > threshold
        rain_fraction = rain_mask.sum() / n

        rainy = pixels[rain_mask]
        mean_precip_rate = float(rainy.mean()) if rainy.size > 0 else 0.0

        strat_mask = (pixels >= threshold) & (pixels < STRAT_UPPER_MM_HR)
        conv_mask  = pixels >= STRAT_UPPER_MM_HR

        records.append({
            "circle": int(circle_idx),
            "rain_fraction": float(rain_fraction),
            "mean_precip_rate": float(mean_precip_rate),
            "stratiform_proxy_frac": float(strat_mask.sum() / n),
            "convective_proxy_frac": float(conv_mask.sum() / n),
            "n_pixels": int(n),
            "imerg_time": matched_time,
        })

    return pd.DataFrame(records)


def _pixel_area_km2(lat: float, dlon: float = 0.1, dlat: float = 0.1) -> float:
    """Approximate area of a single IMERG pixel at a given latitude (km²)."""
    R = 6371.0
    lat_rad = np.deg2rad(lat)
    dx = R * np.cos(lat_rad) * np.deg2rad(dlon)
    dy = R * np.deg2rad(dlat)
    return dx * dy


def _extract_precip_field(
    ds_imerg: xr.Dataset,
    time_idx: int,
    circle_lat: float,
    circle_lon: float,
    radius_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract a 2D IMERG precipitation sub-field within a circle's bounding box.

    Returns (precip_2d, lats_1d, lons_1d) — the rectangular crop.
    Pixels outside the circle are NOT masked here so that connected-component
    labelling works on the full rectangular crop (edge objects still counted).
    """
    radius_km = radius_m / 1000.0
    deg_margin = radius_km / 111.0 * 1.3  # slightly wider margin for objects
    lat_lo = max(float(ds_imerg["lat"].values[0]),  circle_lat - deg_margin)
    lat_hi = min(float(ds_imerg["lat"].values[-1]), circle_lat + deg_margin)
    lon_lo = max(float(ds_imerg["lon"].values[0]),  circle_lon - deg_margin)
    lon_hi = min(float(ds_imerg["lon"].values[-1]), circle_lon + deg_margin)

    crop = (
        ds_imerg["precipitation"]
        .isel(time=time_idx)
        .sel(lat=slice(lat_lo, lat_hi), lon=slice(lon_lo, lon_hi))
    )
    return crop.values, crop["lat"].values, crop["lon"].values


def compute_scai_all_circles(
    ds_sonde: xr.Dataset,
    ds_imerg: xr.Dataset | None = None,
    threshold: float = RAIN_THRESHOLD_MM_HR,
) -> pd.DataFrame:
    """Compute the Simple Convective Aggregation Index (SCAI) per circle.

    SCAI = (N_obj / N_max) × (D_0 / L) × 1000

    where:
        N_obj  = number of connected precipitation objects (> threshold)
        N_max  = total number of pixels in the domain
        D_0    = geometric mean pairwise distance between object centroids (km)
        L      = diagonal length of the analysis domain (km)

    Low SCAI  → organised (few large clusters)
    High SCAI → scattered (many small objects)

    Reference: Tobin, I., et al. (2012), J. Climate, 25, 6885–6904.

    Parameters
    ----------
    ds_sonde : xr.Dataset
        BEACH L4 dataset.
    ds_imerg : xr.Dataset or None
        Combined IMERG NetCDF. Loaded from default path if None.
    threshold : float
        Rain threshold in mm/hr.

    Returns
    -------
    pd.DataFrame with columns:
        circle, scai, n_objects, largest_object_area_km2, domain_rain_coverage
    """
    if ds_imerg is None:
        ds_imerg = xr.open_dataset(str(default_imerg_output_path()))

    raw_times = ds_imerg["time"].values
    if hasattr(raw_times[0], "strftime"):
        imerg_times = pd.to_datetime([t.strftime("%Y-%m-%dT%H:%M:%S") for t in raw_times])
    else:
        imerg_times = pd.to_datetime(raw_times)

    records = []
    for circle_idx in ds_sonde["circle"].values:
        c = ds_sonde.sel(circle=circle_idx)
        circle_lat = float(c["circle_lat"].values)
        circle_lon = float(c["circle_lon"].values)
        radius_m   = float(c["circle_radius"].values)
        circle_t   = pd.Timestamp(str(c["circle_time"].values))

        time_idx = int(np.argmin(np.abs(imerg_times - circle_t)))

        precip_2d, lats, lons = _extract_precip_field(
            ds_imerg, time_idx, circle_lat, circle_lon, radius_m
        )

        if precip_2d.size == 0:
            records.append({
                "circle": int(circle_idx),
                "scai": np.nan,
                "n_objects": 0,
                "largest_object_area_km2": 0.0,
                "domain_rain_coverage": 0.0,
            })
            continue

        # Binary mask: rainy pixels
        rain_mask = np.where(np.isfinite(precip_2d) & (precip_2d > threshold), 1, 0)
        n_max = rain_mask.size

        # Connected components (8-connectivity)
        structure = ndimage.generate_binary_structure(2, 2)
        labelled, n_objects = ndimage.label(rain_mask, structure=structure)

        if n_objects == 0:
            records.append({
                "circle": int(circle_idx),
                "scai": 0.0,
                "n_objects": 0,
                "largest_object_area_km2": 0.0,
                "domain_rain_coverage": 0.0,
            })
            continue

        # Pixel area at circle latitude
        pix_area = _pixel_area_km2(circle_lat)

        # Object centroids and sizes
        centroids_ij = ndimage.center_of_mass(rain_mask, labelled, range(1, n_objects + 1))
        obj_sizes = ndimage.sum(rain_mask, labelled, range(1, n_objects + 1))
        largest_area = float(np.max(obj_sizes) * pix_area)

        # Convert centroids to lat/lon for distance computation
        centroids_ll = []
        for ci, cj in centroids_ij:
            clat = lats[0] + ci * (lats[-1] - lats[0]) / max(len(lats) - 1, 1)
            clon = lons[0] + cj * (lons[-1] - lons[0]) / max(len(lons) - 1, 1)
            centroids_ll.append((clat, clon))

        # Domain diagonal length (km)
        L = _haversine_km(lats[0], lons[0], np.array([lats[-1]]), np.array([lons[-1]]))[0]

        # Geometric mean pairwise distance D_0
        if n_objects == 1:
            D_0 = 0.0
        else:
            dists = []
            for i in range(n_objects):
                for j in range(i + 1, n_objects):
                    d = _haversine_km(
                        centroids_ll[i][0], centroids_ll[i][1],
                        np.array([centroids_ll[j][0]]), np.array([centroids_ll[j][1]]),
                    )[0]
                    if d > 0:
                        dists.append(d)
            if dists:
                D_0 = float(np.exp(np.mean(np.log(dists))))  # geometric mean
            else:
                D_0 = 0.0

        # SCAI = (N_obj / N_max) × (D_0 / L) × 1000
        scai = (n_objects / n_max) * (D_0 / max(L, 1e-6)) * 1000.0

        records.append({
            "circle": int(circle_idx),
            "scai": float(scai),
            "n_objects": int(n_objects),
            "largest_object_area_km2": largest_area,
            "domain_rain_coverage": float(rain_mask.sum() / n_max),
        })

    return pd.DataFrame(records)


def compute_object_classification(
    ds_sonde: xr.Dataset,
    ds_imerg: xr.Dataset | None = None,
    threshold: float = RAIN_THRESHOLD_MM_HR,
    mcs_threshold_km2: float = MCS_AREA_THRESHOLD_KM2,
    scattered_threshold_km2: float = SCATTERED_AREA_THRESHOLD_KM2,
) -> pd.DataFrame:
    """Classify each circle's precipitation field as Organised/Intermediate/Scattered.

    Classification is based on the largest contiguous precipitation object:
        - "Organised"    — largest object ≥ mcs_threshold_km2 (MCS-scale)
        - "Scattered"    — all objects < scattered_threshold_km2
        - "Intermediate" — in between
        - "Dry"          — no rainy pixels

    Parameters
    ----------
    ds_sonde : xr.Dataset
        BEACH L4 dataset.
    ds_imerg : xr.Dataset or None
        Combined IMERG NetCDF.
    threshold : float
        Rain threshold in mm/hr.
    mcs_threshold_km2 : float
        Area threshold for MCS-scale classification.
    scattered_threshold_km2 : float
        All-objects-below-this threshold for scattered classification.

    Returns
    -------
    pd.DataFrame with columns:
        circle, org_class, largest_obj_km2, n_rain_objects, total_rain_area_km2
    """
    # Compute SCAI first (it contains the object info we need)
    df_scai = compute_scai_all_circles(ds_sonde, ds_imerg, threshold)

    records = []
    for _, row in df_scai.iterrows():
        largest = row["largest_object_area_km2"]
        n_obj = row["n_objects"]

        if n_obj == 0:
            org_class = "Dry"
        elif largest >= mcs_threshold_km2:
            org_class = "Organised"
        elif largest < scattered_threshold_km2:
            org_class = "Scattered"
        else:
            org_class = "Intermediate"

        records.append({
            "circle": int(row["circle"]),
            "org_class": org_class,
            "largest_obj_km2": largest,
            "n_rain_objects": int(n_obj),
        })

    return pd.DataFrame(records)


def get_era5_tcwv_at_circles(
    ds_sonde: xr.Dataset,
    era5_ds: xr.Dataset | None = None,
) -> pd.DataFrame:
    """Sample ERA5 total column water vapour at each dropsonde circle.

    Uses nearest-neighbour in both time (6-hourly ERA5) and space (0.25° grid).

    Parameters
    ----------
    ds_sonde:
        BEACH L4 dataset.
    era5_ds:
        ERA5 single-level dataset containing 'tcwv'. If None, loads
        era5_single_levels.nc from the default ERA5 directory.

    Returns
    -------
    pd.DataFrame with columns:
        circle       — circle index
        era5_tcwv    — total column water vapour in kg m⁻²
        era5_time    — actual ERA5 timestamp matched
    """
    if era5_ds is None:
        era5_path = default_era5_dir() / "era5_single_levels.nc"
        era5_ds = xr.open_dataset(str(era5_path))

    era5_times = pd.to_datetime(era5_ds["valid_time"].values)
    era5_lats  = era5_ds["latitude"].values   # may be descending (30→0)
    era5_lons  = era5_ds["longitude"].values  # ascending (-70→0)

    records = []
    for circle_idx in ds_sonde["circle"].values:
        c = ds_sonde.sel(circle=circle_idx)
        clat     = float(c["circle_lat"].values)
        clon     = float(c["circle_lon"].values)
        circle_t = pd.Timestamp(str(c["circle_time"].values))

        t_idx   = int(np.argmin(np.abs(era5_times - circle_t)))
        lat_idx = int(np.argmin(np.abs(era5_lats - clat)))
        lon_idx = int(np.argmin(np.abs(era5_lons - clon)))

        tcwv = float(
            era5_ds["tcwv"].isel(
                valid_time=t_idx, latitude=lat_idx, longitude=lon_idx
            ).values
        )
        records.append({
            "circle": int(circle_idx),
            "era5_tcwv": tcwv,
            "era5_time": era5_times[t_idx],
        })

    return pd.DataFrame(records)


# Longitude boundary separating East and West Atlantic sampling regions.
# There is a natural data gap from -33°W to -44°W between the Cape Verde
# (MAESTRO) and Barbados (PERCUSION) legs of the ORCESTRA campaign.
EAST_WEST_BOUNDARY_LON: float = -38.0


def classify_region(lon: float, boundary: float = EAST_WEST_BOUNDARY_LON) -> str:
    """Classify a circle as 'East Atlantic' or 'West Atlantic'.

    The ORCESTRA campaign operated from two bases:
        East Atlantic  — Cape Verde / Mindelo  (~-25°W), Aug 2024
        West Atlantic  — Barbados              (~-55°W), Sep 2024

    A natural data gap at ~-38°W separates the two sampling regions.
    """
    return "East Atlantic" if lon > boundary else "West Atlantic"


def build_circle_metrics(
    ds_sonde: xr.Dataset,
    ds_imerg: xr.Dataset | None = None,
    era5_ds: xr.Dataset | None = None,
    threshold: float = RAIN_THRESHOLD_MM_HR,
) -> pd.DataFrame:
    """Build a single merged DataFrame with all per-circle organisation metrics.

    Combines:
        - rain fraction + intensity proxies (from IMERG)
        - ERA5 tcwv
        - BEACH L4 iwv_mean, category_avg, top_heaviness_angle, circle metadata

    This is the recommended entry point for notebooks.

    Returns
    -------
    pd.DataFrame, one row per circle, with all metrics and metadata.
    """
    # --- BEACH L4 metadata ---
    beach_rows = []
    for circle_idx in ds_sonde["circle"].values:
        c = ds_sonde.sel(circle=circle_idx)
        cat_raw = str(c["category_avg"].values)
        clon = float(c["circle_lon"].values)
        beach_rows.append({
            "circle": int(circle_idx),
            "circle_lat": float(c["circle_lat"].values),
            "circle_lon": clon,
            "circle_time": pd.Timestamp(str(c["circle_time"].values)),
            "circle_radius_km": float(c["circle_radius"].values) / 1000.0,
            "iwv_mean": float(c["iwv_mean"].values),
            "top_heaviness_angle": float(c["top_heaviness_angle"].values),
            "category_raw": cat_raw,
            "category": simplify_category(cat_raw),
            "region": classify_region(clon),
        })
    df_beach = pd.DataFrame(beach_rows)

    # --- IMERG rain fraction ---
    df_rain = compute_rain_fraction_all_circles(ds_sonde, ds_imerg, threshold)

    # --- IMERG SCAI + object classification ---
    df_scai = compute_scai_all_circles(ds_sonde, ds_imerg, threshold)
    df_obj = compute_object_classification(ds_sonde, ds_imerg, threshold)

    # --- ERA5 tcwv ---
    df_era5 = get_era5_tcwv_at_circles(ds_sonde, era5_ds)

    # --- Merge ---
    df = df_beach.merge(df_rain.drop(columns=["imerg_time"]), on="circle", how="left")
    df = df.merge(df_scai, on="circle", how="left")
    df = df.merge(df_obj, on="circle", how="left")
    df = df.merge(df_era5.drop(columns=["era5_time"]), on="circle", how="left")

    # --- Derived: stratiform ratio (tests the middle of the RQ2 chain) ---
    total_precip_frac = df["stratiform_proxy_frac"] + df["convective_proxy_frac"]
    df["strat_ratio"] = np.where(
        total_precip_frac > 0,
        df["stratiform_proxy_frac"] / total_precip_frac,
        np.nan,
    )

    return df
