#!/usr/bin/env python3
"""Create a dropsonde vertical velocity vs IMERG precipitation comparison figure.

This script generates a 2-panel figure:
1. Left panel: Dropsonde vertical velocity profile (omega vs pressure)
2. Right panel: IMERG precipitation map matched to the dropsonde time/location

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
    1000,
    925,
    850,
    700,
    500,
    300,
    200,
    100,
], dtype=float)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dropsonde vs IMERG comparison figure(s) (IMERG only)."
    )
    parser.add_argument(
        "--dropsonde-zarr",
        type=Path,
        default=Path("/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr"),
        help="Path to ORCESTRA dropsonde zarr dataset.",
    )
    parser.add_argument(
        "--categories-csv",
        type=Path,
        default=Path("/g/data/k10/zr7147/ORCESTRA_dropsondes_categories.csv"),
        help="Path to dropsonde category CSV.",
    )
    parser.add_argument(
        "--imerg-nc",
        type=Path,
        default=Path("/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc"),
        help="Path to merged IMERG NetCDF.",
    )
    parser.add_argument(
        "--circle",
        type=int,
        default=None,
        help="Plot one specific circle index.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Plot all circles for a specific UTC date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot all circles in the dropsonde dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/home/565/zr7147/Proj/outputs/figures/week3/vertical_velocity_vs_imerg.png"),
        help="Output PNG path for single-figure mode (used with --circle or default mode).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/home/565/zr7147/Proj/outputs/figures/week3"),
        help="Output directory for multi-figure mode (--date or --all).",
    )
    args = parser.parse_args()

    selected_modes = sum(
        [args.circle is not None, args.date is not None, bool(args.all)]
    )
    if selected_modes > 1:
        raise ValueError("Use only one of --circle, --date, or --all")

    return args


def get_profile_color(category: str) -> str:
    if "Top-Heavy" in category:
        return COLOR_TOP_HEAVY
    if "Bottom-Heavy" in category:
        return COLOR_BOTTOM_HEAVY
    return COLOR_OTHER


def create_geographic_circle(clat: float, clon: float, radius_m: float, n: int = 361) -> tuple[np.ndarray, np.ndarray]:
    radius_deg_lat = radius_m / 111000.0
    cos_lat = max(np.cos(np.deg2rad(clat)), 0.15)
    radius_deg_lon = radius_m / (111000.0 * cos_lat)
    theta = np.linspace(0.0, 2.0 * np.pi, n)
    lon_circle = clon + radius_deg_lon * np.cos(theta)
    lat_circle = clat + radius_deg_lat * np.sin(theta)
    return lon_circle, lat_circle


def find_default_circle(ds_sonde: xr.Dataset, df_cats: pd.DataFrame) -> int:
    if "category_evolutionary" not in df_cats.columns or "circle" not in df_cats.columns:
        raise ValueError("categories CSV must include 'circle' and 'category_evolutionary' columns")

    filtered = df_cats[
        df_cats["category_evolutionary"].fillna("").str.contains("Top-Heavy|Bottom-Heavy", regex=True)
    ].copy()

    if filtered.empty:
        raise ValueError("No Top-Heavy/Bottom-Heavy circles found in category CSV")

    circle_time = {}
    for c in ds_sonde["circle"].values:
        t = pd.to_datetime(ds_sonde.sel(circle=c)["circle_time"].values)
        circle_time[int(c)] = t

    filtered["circle_time"] = filtered["circle"].astype(int).map(circle_time)
    filtered = filtered.dropna(subset=["circle_time"]).sort_values("circle_time")

    if filtered.empty:
        raise ValueError("Could not map any circle times from dropsonde dataset")

    return int(filtered.iloc[0]["circle"])


def get_circle_metadata(df_cats: pd.DataFrame, circle_idx: int) -> tuple[str, float]:
    row = df_cats[df_cats["circle"].astype(int) == int(circle_idx)]
    category = str(row.iloc[0]["category_evolutionary"]) if not row.empty else "Uncategorized"
    angle = (
        float(row.iloc[0]["top_heaviness_angle"])
        if (not row.empty and "top_heaviness_angle" in row.columns)
        else np.nan
    )
    return category, angle


def sanitize_label(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        elif ch in (" ", "/"):
            keep.append("_")
    label = "".join(keep).strip("_")
    return label or "uncategorized"


def plot_one_circle(
    ds_sonde: xr.Dataset,
    df_cats: pd.DataFrame,
    ds_imerg: xr.Dataset,
    circle_idx: int,
    output_path: Path,
) -> dict:
    circle_ds = ds_sonde.sel(circle=circle_idx)
    category, angle = get_circle_metadata(df_cats, circle_idx)

    omega = circle_ds["omega"].values
    p_mean = circle_ds["p_mean"].values
    drop_time = pd.to_datetime(circle_ds["circle_time"].values)
    clat = float(circle_ds["circle_lat"].values)
    clon = float(circle_ds["circle_lon"].values)
    radius_m = float(circle_ds["circle_radius"].values)

    imerg_times = ds_imerg["time"].values
    drop_np = np.datetime64(drop_time)
    imerg_idx = int(np.abs(np.array([np.datetime64(str(t)) for t in imerg_times]) - drop_np).argmin())
    # IMERG time can be cftime; convert through string for robust display.
    imerg_time = pd.to_datetime(str(imerg_times[imerg_idx]))

    span_lat = max(radius_m / 111000.0 * 1.35, 0.6)
    span_lon = max(radius_m / (111000.0 * max(np.cos(np.deg2rad(clat)), 0.15)) * 1.35, 0.6)

    lat_min, lat_max = clat - span_lat, clat + span_lat
    lon_min, lon_max = clon - span_lon, clon + span_lon

    if lat_min > lat_max:
        lat_min, lat_max = lat_max, lat_min
    if lon_min > lon_max:
        lon_min, lon_max = lon_max, lon_min

    imerg_local = ds_imerg["precipitation"].isel(time=imerg_idx).sel(
        lon=slice(lon_min, lon_max), lat=slice(lat_min, lat_max)
    )

    if imerg_local.size == 0:
        raise RuntimeError(f"IMERG crop is empty for circle {circle_idx}")

    lon_circle, lat_circle = create_geographic_circle(clat, clon, radius_m)
    line_color = get_profile_color(category)

    fig = plt.figure(figsize=(14, 6.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.26)
    ax_prof = fig.add_subplot(gs[0, 0])
    ax_imerg = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())

    valid = np.isfinite(omega) & np.isfinite(p_mean)
    if valid.sum() == 0:
        raise RuntimeError(f"No valid dropsonde profile values for circle {circle_idx}")

    omega_valid = omega[valid]
    p_valid = p_mean[valid].astype(float) / 100.0

    # Plot against monotonically decreasing pressure in hPa so the y-axis
    # matches standard meteorological convention.
    pressure_order = np.argsort(p_valid)[::-1]
    omega_valid = omega_valid[pressure_order]
    p_valid = p_valid[pressure_order]

    p_top = float(np.nanmin(p_valid))
    p_bottom = float(np.nanmax(p_valid))
    pressure_ticks = STANDARD_PRESSURE_LEVELS_HPA[
        (STANDARD_PRESSURE_LEVELS_HPA >= p_top) & (STANDARD_PRESSURE_LEVELS_HPA <= p_bottom)
    ]
    if pressure_ticks.size == 0:
        pressure_ticks = np.array([p_bottom, p_top])

    ax_prof.plot(omega_valid, p_valid, color=line_color, lw=2.6)
    ax_prof.fill_betweenx(
        p_valid,
        omega_valid,
        0,
        where=(omega_valid < 0),
        color=line_color,
        alpha=0.14,
    )
    ax_prof.axvline(0, color="k", lw=1.0, ls="--", alpha=0.65)
    for level in pressure_ticks:
        ax_prof.axhline(level, color="0.75", lw=0.8, ls=":", zorder=0)

    ax_prof.set_ylim(p_bottom, p_top)
    ax_prof.set_xlabel(r"Vertical Velocity $\omega$ (Pa s$^{-1}$)", fontsize=11, fontweight="bold")
    ax_prof.set_ylabel("Pressure (hPa)", fontsize=11, fontweight="bold")
    ax_prof.set_yticks(pressure_ticks)
    ax_prof.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{int(value)}"))
    ax_prof.grid(True, alpha=0.25)
    ax_prof.set_title(f"Dropsonde Vertical Velocity | Circle {circle_idx} | {drop_time.strftime('%Y-%m-%d %H:%M')} UTC", fontsize=12, fontweight="bold")

    if np.isfinite(angle):
        info_text = f"Category: {category}\nTop-heaviness angle: {angle:.1f} deg"
    else:
        info_text = f"Category: {category}"

    ax_prof.text(
        0.03,
        0.04,
        info_text,
        transform=ax_prof.transAxes,
        ha="left",
        va="bottom",
        fontsize=9.5,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.88, edgecolor="0.75"),
    )

    mesh = ax_imerg.pcolormesh(
        imerg_local["lon"].values,
        imerg_local["lat"].values,
        imerg_local.values,
        cmap=PRECIP_CMAP,
        vmin=0,
        vmax=10,
        shading="nearest",
        transform=ccrs.PlateCarree(),
    )
    ax_imerg.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
    ax_imerg.coastlines(linewidth=1.0, alpha=0.7)
    ax_imerg.add_feature(cfeature.BORDERS, linewidth=0.5, alpha=0.5)
    gl = ax_imerg.gridlines(draw_labels=True, linewidth=0.4, alpha=0.45)
    gl.top_labels = False
    gl.right_labels = False

    ax_imerg.plot(lon_circle, lat_circle, color=line_color, lw=2.0, ls="--", transform=ccrs.PlateCarree(), zorder=4)
    ax_imerg.plot(
        clon,
        clat,
        marker="*",
        markersize=13,
        color=line_color,
        markeredgecolor="black",
        markeredgewidth=0.8,
        transform=ccrs.PlateCarree(),
        zorder=5,
    )
    ax_imerg.set_title(f"IMERG Precipitation ({imerg_time.strftime('%Y-%m-%d %H:%M')} UTC)", fontsize=12, fontweight="bold")

    cbar = plt.colorbar(mesh, ax=ax_imerg, orientation="horizontal", pad=0.1, fraction=0.08)
    cbar.set_label("Precipitation (mm hr$^{-1}$)", fontsize=10)

    fig.suptitle(
        "Vertical Velocity Profile vs IMERG Precipitation ",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {
        "output": str(output_path),
        "circle": int(circle_idx),
        "dropsonde_time": str(drop_time),
        "imerg_time": str(imerg_time),
        "category": category,
    }


def get_target_circles(ds_sonde: xr.Dataset, df_cats: pd.DataFrame, args: argparse.Namespace) -> list[int]:
    if args.circle is not None:
        return [int(args.circle)]

    all_circles = [int(c) for c in ds_sonde["circle"].values]

    if args.date:
        target_date = pd.to_datetime(args.date).date()
        selected = []
        for c in all_circles:
            circle_time = pd.to_datetime(ds_sonde.sel(circle=c)["circle_time"].values)
            if circle_time.date() == target_date:
                selected.append(c)
        return selected

    if args.all:
        return all_circles

    return [find_default_circle(ds_sonde, df_cats)]


def main() -> None:
    args = parse_args()

    if not args.dropsonde_zarr.exists():
        raise FileNotFoundError(f"Dropsonde zarr not found: {args.dropsonde_zarr}")
    if not args.categories_csv.exists():
        raise FileNotFoundError(f"Categories CSV not found: {args.categories_csv}")
    if not args.imerg_nc.exists():
        raise FileNotFoundError(f"IMERG NetCDF not found: {args.imerg_nc}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ds_sonde = xr.open_zarr(str(args.dropsonde_zarr))
    df_cats = pd.read_csv(args.categories_csv)
    ds_imerg = xr.open_dataset(str(args.imerg_nc))

    circles = get_target_circles(ds_sonde, df_cats, args)
    if not circles:
        raise ValueError("No circles matched the requested selection")

    multi_mode = args.all or (args.date is not None)

    print(f"Selected circles: {len(circles)}")
    saved = 0

    for circle_idx in circles:
        try:
            if multi_mode:
                category, _ = get_circle_metadata(df_cats, circle_idx)
                circle_time = pd.to_datetime(ds_sonde.sel(circle=circle_idx)["circle_time"].values)
                date_str = circle_time.strftime("%Y%m%d")
                time_str = circle_time.strftime("%H%M%S")
                cat_tag = sanitize_label(category)
                out_path = args.output_dir / f"vertical_velocity_vs_imerg_circle_{circle_idx:03d}_{date_str}_{time_str}_{cat_tag}.png"
            else:
                out_path = args.output

            info = plot_one_circle(ds_sonde, df_cats, ds_imerg, circle_idx, out_path)
            saved += 1
            print(
                f"Saved figure: {info['output']} | circle={info['circle']} | "
                f"dropsonde={info['dropsonde_time']} | imerg={info['imerg_time']}"
            )
        except Exception as exc:
            print(f"Skipped circle {circle_idx}: {exc}")

    print(f"Completed. Saved {saved}/{len(circles)} figure(s).")

    ds_sonde.close()
    ds_imerg.close()


if __name__ == "__main__":
    main()
