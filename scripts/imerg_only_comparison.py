#!/usr/bin/env python3
"""Create a dropsonde vertical velocity vs IMERG precipitation comparison figure.

This script generates a figure with:
- Left panel : Dropsonde vertical velocity profile (omega vs pressure in Pa)
- Right panels: One IMERG panel per 30-min timestep that falls within the
  actual circle flight window (first sonde launch → last sonde launch).
  Typically 2 panels for a ~1 hr circle; more if the circle is longer.

circle_time in the BEACH L4 dataset is the MIDPOINT (mean of all sonde
launch times), NOT the start or end of the circle.  Start and end are
derived here from the per-sonde launch_time array via sondes_per_circle.

Default output:
    /home/565/zr7147/Proj/outputs/figures/week3/vertical_velocity_vs_imerg.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import xarray as xr

COLOR_TOP_HEAVY = "#d94832"
COLOR_BOTTOM_HEAVY = "#2b83c6"
COLOR_OTHER = "#4d4d4d"

PRECIP_COLORS = [
    "#FFFFFF",
    "#DDEEFF",
    "#99CCFF",
    "#3399FF",
    "#0066CC",
    "#00CC66",
    "#33FF33",
    "#99FF00",
    "#FFFF00",
    "#FFCC00",
    "#FF9900",
    "#FF6600",
    "#FF3300",
    "#CC0000",
    "#990000",
]
PRECIP_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "WhiteBlueGreenYellowRed", PRECIP_COLORS, N=256
)

STANDARD_PRESSURE_LEVELS_HPA = np.array([
    1000, 925, 850, 700, 500, 300, 200, 100,
], dtype=float)

# Padding added to each side of the circle flight window so that the 4
# surrounding IMERG 30-min snapshots are always captured.
IMERG_WINDOW_PAD = np.timedelta64(30, "m")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def cftime_to_np64(t) -> np.datetime64:
    """Convert a cftime object to numpy datetime64 via ISO string."""
    return np.datetime64(t.strftime("%Y-%m-%dT%H:%M:%S"))


def imerg_times_as_np64(ds_imerg: xr.Dataset) -> np.ndarray:
    """Return the IMERG time array as numpy datetime64, handling cftime."""
    raw = ds_imerg["time"].values
    if hasattr(raw[0], "strftime"):
        return np.array([cftime_to_np64(t) for t in raw])
    return raw.astype("datetime64[s]")


# ---------------------------------------------------------------------------
# Circle window helpers
# ---------------------------------------------------------------------------

def build_circle_sonde_index(ds_sonde: xr.Dataset) -> np.ndarray:
    """Return cumulative sonde start indices per circle.

    Returns array of shape (n_circles + 1,) where entry i is the sonde index
    of the first sonde in circle i and entry n_circles is the total sonde count.
    """
    spc = ds_sonde["sondes_per_circle"].values.astype(int)
    return np.concatenate([[0], np.cumsum(spc)])


def get_circle_time_window(
    ds_sonde: xr.Dataset,
    circle_idx: int,
    cum_index: np.ndarray,
) -> tuple[np.datetime64, np.datetime64]:
    """Return (t_start, t_end) for a circle using actual sonde launch times.

    circle_time in the dataset is the MIDPOINT of all launch times.
    True start = first sonde launch, true end = last sonde launch.
    """
    i = int(circle_idx)
    i_first = int(cum_index[i])
    i_last  = int(cum_index[i + 1]) - 1
    t_start = ds_sonde["launch_time"].values[i_first]
    t_end   = ds_sonde["launch_time"].values[i_last]
    return np.datetime64(t_start, "s"), np.datetime64(t_end, "s")


def find_imerg_indices_for_window(
    imerg_times_np: np.ndarray,
    t_start: np.datetime64,
    t_end: np.datetime64,
    pad: np.timedelta64 = IMERG_WINDOW_PAD,
) -> list[int]:
    """Return indices of IMERG timesteps within [t_start - pad, t_end + pad].

    The ±30 min padding around the actual sonde window ensures all 4 surrounding
    30-min IMERG snapshots are captured for a typical ~1 hr circle.
    Falls back to the 4 nearest if the padded window returns fewer than 4.
    """
    mask = (imerg_times_np >= t_start - pad) & (imerg_times_np <= t_end + pad)
    indices = list(np.where(mask)[0])
    if len(indices) < 4:
        midpoint = t_start + (t_end - t_start) // 2
        diffs = np.abs(imerg_times_np - midpoint)
        indices = list(np.argsort(diffs)[:4])
        indices.sort()
    return indices


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dropsonde vs IMERG comparison figure(s) (IMERG only)."
    )
    parser.add_argument(
        "--dropsonde-zarr",
        type=Path,
        default=Path("/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr"),
    )
    parser.add_argument(
        "--categories-csv",
        type=Path,
        default=Path("/g/data/k10/zr7147/ORCESTRA_dropsondes_categories.csv"),
    )
    parser.add_argument(
        "--imerg-nc",
        type=Path,
        default=Path("/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc"),
    )
    parser.add_argument("--circle", type=int, default=None)
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/home/565/zr7147/Proj/outputs/figures/week3/vertical_velocity_vs_imerg.png"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/565/zr7147/Proj/outputs/figures/week3"),
    )
    parser.add_argument(
        "--category-col",
        type=str,
        default="category_evolutionary",
        help="Column name in categories CSV to use for classification.",
    )
    parser.add_argument(
        "--angle-col",
        type=str,
        default="top_heaviness_angle",
        help="Column name in categories CSV for top-heaviness angle.",
    )
    args = parser.parse_args()

    selected_modes = sum([args.circle is not None, args.date is not None, bool(args.all)])
    if selected_modes > 1:
        raise ValueError("Use only one of --circle, --date, or --all")
    return args


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def get_profile_color(category: str) -> str:
    if "Top-Heavy" in category:
        return COLOR_TOP_HEAVY
    if "Bottom-Heavy" in category:
        return COLOR_BOTTOM_HEAVY
    return COLOR_OTHER


def get_circle_metadata(
    df_cats: pd.DataFrame,
    circle_idx: int,
    category_col: str = "category_evolutionary",
    angle_col: str = "top_heaviness_angle",
) -> tuple[str, float]:
    row = df_cats[df_cats["circle"].astype(int) == int(circle_idx)]
    category = str(row.iloc[0][category_col]) if not row.empty else "Uncategorized"
    angle = (
        float(row.iloc[0][angle_col])
        if (not row.empty and angle_col in row.columns)
        else np.nan
    )
    return category, angle


def create_geographic_circle(
    clat: float, clon: float, radius_m: float, n: int = 361
) -> tuple[np.ndarray, np.ndarray]:
    radius_deg_lat = radius_m / 111000.0
    cos_lat = max(np.cos(np.deg2rad(clat)), 0.15)
    radius_deg_lon = radius_m / (111000.0 * cos_lat)
    theta = np.linspace(0.0, 2.0 * np.pi, n)
    lon_circle = clon + radius_deg_lon * np.cos(theta)
    lat_circle = clat + radius_deg_lat * np.sin(theta)
    return lon_circle, lat_circle


def sanitize_label(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        elif ch in (" ", "/"):
            keep.append("_")
    label = "".join(keep).strip("_")
    return label or "uncategorized"


def find_default_circle(
    ds_sonde: xr.Dataset,
    df_cats: pd.DataFrame,
    category_col: str = "category_evolutionary",
) -> int:
    filtered = df_cats[
        df_cats[category_col].fillna("").str.contains(
            "Top-Heavy|Bottom-Heavy", regex=True
        )
    ].copy()
    if filtered.empty:
        raise ValueError("No Top-Heavy/Bottom-Heavy circles found in category CSV")

    circle_time_map = {
        int(c): pd.to_datetime(ds_sonde.sel(circle=c)["circle_time"].values)
        for c in ds_sonde["circle"].values
    }
    filtered["circle_time"] = filtered["circle"].astype(int).map(circle_time_map)
    filtered = filtered.dropna(subset=["circle_time"]).sort_values("circle_time")
    if filtered.empty:
        raise ValueError("Could not map any circle times from dropsonde dataset")
    return int(filtered.iloc[0]["circle"])


# ---------------------------------------------------------------------------
# Main plotting function
# ---------------------------------------------------------------------------

def plot_one_circle(
    ds_sonde: xr.Dataset,
    df_cats: pd.DataFrame,
    ds_imerg: xr.Dataset,
    imerg_times_np: np.ndarray,
    cum_index: np.ndarray,
    circle_idx: int,
    output_path: Path,
    category_col: str = "category_evolutionary",
    angle_col: str = "top_heaviness_angle",
) -> dict:
    circle_ds = ds_sonde.sel(circle=circle_idx)
    category, angle = get_circle_metadata(df_cats, circle_idx, category_col, angle_col)

    omega  = circle_ds["omega"].values
    p_mean = circle_ds["p_mean"].values
    circle_midtime = pd.to_datetime(circle_ds["circle_time"].values)
    clat   = float(circle_ds["circle_lat"].values)
    clon   = float(circle_ds["circle_lon"].values)
    radius_m = float(circle_ds["circle_radius"].values)

    # --- Actual circle flight window (start = first launch, end = last launch) ---
    t_start, t_end = get_circle_time_window(ds_sonde, circle_idx, cum_index)

    # --- All IMERG timesteps within the circle window, capped at 4 for 2×2 grid ---
    imerg_indices = find_imerg_indices_for_window(imerg_times_np, t_start, t_end)[:4]
    n_imerg = len(imerg_indices)

    # --- Spatial crop ---
    span_lat = max(radius_m / 111000.0 * 1.35, 0.6)
    span_lon = max(radius_m / (111000.0 * max(np.cos(np.deg2rad(clat)), 0.15)) * 1.35, 0.6)
    lat_min = min(clat - span_lat, clat + span_lat)
    lat_max = max(clat - span_lat, clat + span_lat)
    lon_min = min(clon - span_lon, clon + span_lon)
    lon_max = max(clon - span_lon, clon + span_lon)

    # Pre-crop IMERG panels
    imerg_crops = []
    for idx in imerg_indices:
        crop = ds_imerg["precipitation"].isel(time=idx).sel(
            lon=slice(lon_min, lon_max), lat=slice(lat_min, lat_max)
        )
        if crop.size == 0:
            raise RuntimeError(f"IMERG crop empty at time index {idx} for circle {circle_idx}")
        imerg_crops.append(crop)

    lon_circle, lat_circle = create_geographic_circle(clat, clon, radius_m)
    line_color = get_profile_color(category)

    # --- Figure layout: left = omega profile, right = 2×2 IMERG grid ---
    fig = plt.figure(figsize=(16, 9))
    gs_outer = GridSpec(1, 2, figure=fig, width_ratios=[1.0, 1.55], wspace=0.28)
    ax_prof = fig.add_subplot(gs_outer[0, 0])
    gs_right = gs_outer[0, 1].subgridspec(2, 2, hspace=0.42, wspace=0.22)
    ax_imergs = [
        fig.add_subplot(gs_right[i // 2, i % 2], projection=ccrs.PlateCarree())
        for i in range(n_imerg)
    ]

    # --- Omega profile (Pa units throughout) ---
    valid = np.isfinite(omega) & np.isfinite(p_mean)
    if valid.sum() == 0:
        raise RuntimeError(f"No valid dropsonde profile values for circle {circle_idx}")

    omega_v = omega[valid]
    p_v     = p_mean[valid].astype(float) / 100.0  # convert Pa → hPa for display

    order   = np.argsort(p_v)[::-1]  # descending pressure (surface at bottom)
    omega_v = omega_v[order]
    p_v     = p_v[order]

    p_top    = float(np.nanmin(p_v))
    p_bottom = float(np.nanmax(p_v))
    pressure_ticks = STANDARD_PRESSURE_LEVELS_HPA[
        (STANDARD_PRESSURE_LEVELS_HPA >= p_top) & (STANDARD_PRESSURE_LEVELS_HPA <= p_bottom)
    ]
    if pressure_ticks.size == 0:
        pressure_ticks = np.array([p_bottom, p_top])

    ax_prof.plot(omega_v, p_v, color=line_color, lw=2.6)
    ax_prof.fill_betweenx(p_v, omega_v, 0, where=(omega_v < 0), color=line_color, alpha=0.14)
    ax_prof.axvline(0, color="k", lw=1.0, ls="--", alpha=0.65)
    for level in pressure_ticks:
        ax_prof.axhline(level, color="0.75", lw=0.8, ls=":", zorder=0)

    ax_prof.set_ylim(p_bottom, p_top)
    ax_prof.set_xlabel(r"Vertical Velocity $\omega$ (Pa s$^{-1}$)", fontsize=11, fontweight="bold")
    ax_prof.set_ylabel("Pressure (hPa)", fontsize=11, fontweight="bold")
    ax_prof.set_yticks(pressure_ticks)
    ax_prof.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}"))
    ax_prof.grid(True, alpha=0.25)

    # Title for profile panel shows circle window (start → end) and midpoint
    t_start_str = pd.Timestamp(t_start).strftime("%H:%M")
    t_end_str   = pd.Timestamp(t_end).strftime("%H:%M")
    date_str    = circle_midtime.strftime("%Y-%m-%d")
    ax_prof.set_title(
        f"Vertical Velocity Profile | Circle {circle_idx}\n"
        f"{date_str}  {t_start_str}–{t_end_str} UTC",
        fontsize=11,
        fontweight="bold",
    )

    info_text = f"Category: {category}"
    if np.isfinite(angle):
        info_text += f"\nTop-heaviness: {angle:.1f}°"
    ax_prof.text(
        0.03, 0.04, info_text,
        transform=ax_prof.transAxes, ha="left", va="bottom", fontsize=9.5,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.88, edgecolor="0.75"),
    )

    # --- IMERG panels ---
    vmin, vmax = 0.0, 10.0
    mesh_last = None
    for panel_i, (ax_im, crop, idx) in enumerate(zip(ax_imergs, imerg_crops, imerg_indices)):
        imerg_t = pd.Timestamp(str(imerg_times_np[idx])).strftime("%Y-%m-%d %H:%M")
        mesh_last = ax_im.pcolormesh(
            crop["lon"].values,
            crop["lat"].values,
            crop.values,
            cmap=PRECIP_CMAP,
            vmin=vmin,
            vmax=vmax,
            shading="nearest",
            transform=ccrs.PlateCarree(),
        )
        ax_im.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
        ax_im.coastlines(linewidth=1.0, alpha=0.7)
        ax_im.add_feature(cfeature.BORDERS, linewidth=0.5, alpha=0.5)
        gl = ax_im.gridlines(draw_labels=True, linewidth=0.4, alpha=0.45)
        gl.top_labels = False
        gl.right_labels = False
        ax_im.plot(
            lon_circle, lat_circle,
            color=line_color, lw=2.0, ls="--",
            transform=ccrs.PlateCarree(), zorder=4,
        )
        ax_im.plot(
            clon, clat,
            marker="*", markersize=13, color=line_color,
            markeredgecolor="black", markeredgewidth=0.8,
            transform=ccrs.PlateCarree(), zorder=5,
        )
        ax_im.set_title(f"IMERG  {imerg_t} UTC", fontsize=10, fontweight="bold")

    # Shared horizontal colorbar spanning the full 2×2 grid at the bottom
    if mesh_last is not None:
        cbar = plt.colorbar(
            mesh_last, ax=ax_imergs, orientation="horizontal",
            pad=0.06, fraction=0.035, aspect=50,
        )
        cbar.set_label("Precipitation (mm hr$^{-1}$)", fontsize=10)

    fig.suptitle(
        f"Vertical Velocity Profile vs IMERG Precipitation  {date_str}",
        fontsize=13,
        fontweight="bold",
        y=1.01,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {
        "output": str(output_path),
        "circle": int(circle_idx),
        "circle_start": str(t_start),
        "circle_end": str(t_end),
        "circle_midtime": str(circle_midtime),
        "n_imerg_panels": n_imerg,
        "imerg_times": [str(imerg_times_np[i]) for i in imerg_indices],
        "category": category,
    }


# ---------------------------------------------------------------------------
# Circle selection helpers
# ---------------------------------------------------------------------------

def get_target_circles(
    ds_sonde: xr.Dataset,
    df_cats: pd.DataFrame,
    args: argparse.Namespace,
) -> list[int]:
    if args.circle is not None:
        return [int(args.circle)]

    all_circles = [int(c) for c in ds_sonde["circle"].values]

    if args.date:
        target_date = pd.to_datetime(args.date).date()
        return [
            c for c in all_circles
            if pd.to_datetime(ds_sonde.sel(circle=c)["circle_time"].values).date() == target_date
        ]

    if args.all:
        return all_circles

    return [find_default_circle(ds_sonde, df_cats, args.category_col)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    for path, label in [
        (args.dropsonde_zarr, "Dropsonde zarr"),
        (args.categories_csv, "Categories CSV"),
        (args.imerg_nc, "IMERG NetCDF"),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ds_sonde  = xr.open_zarr(str(args.dropsonde_zarr))
    df_cats   = pd.read_csv(args.categories_csv)
    ds_imerg  = xr.open_dataset(str(args.imerg_nc))
    imerg_times_np = imerg_times_as_np64(ds_imerg)
    cum_index = build_circle_sonde_index(ds_sonde)

    circles = get_target_circles(ds_sonde, df_cats, args)
    if not circles:
        raise ValueError("No circles matched the requested selection")

    multi_mode = args.all or (args.date is not None)
    print(f"Selected circles: {len(circles)}")
    saved = 0

    for circle_idx in circles:
        try:
            if multi_mode:
                category, _ = get_circle_metadata(df_cats, circle_idx, args.category_col, args.angle_col)
                circle_time = pd.to_datetime(ds_sonde.sel(circle=circle_idx)["circle_time"].values)
                date_str  = circle_time.strftime("%Y%m%d")
                time_str  = circle_time.strftime("%H%M%S")
                cat_tag   = sanitize_label(category)
                out_path  = args.output_dir / f"vertical_velocity_vs_imerg_circle_{circle_idx:03d}_{date_str}_{time_str}_{cat_tag}.png"
            else:
                out_path = args.output

            info = plot_one_circle(
                ds_sonde, df_cats, ds_imerg, imerg_times_np, cum_index,
                circle_idx, out_path, args.category_col, args.angle_col,
            )
            saved += 1
            print(
                f"Saved: {info['output']} | circle={info['circle']} "
                f"| window={info['circle_start']}–{info['circle_end']} "
                f"| n_imerg={info['n_imerg_panels']} {info['imerg_times']}"
            )
        except Exception as exc:
            print(f"Skipped circle {circle_idx}: {exc}")

    print(f"Completed. Saved {saved}/{len(circles)} figure(s).")
    ds_sonde.close()
    ds_imerg.close()


if __name__ == "__main__":
    main()
