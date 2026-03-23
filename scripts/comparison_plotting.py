#!/usr/bin/env python3
"""Dropsonde vs Satellite comparison plotting.

Creates three-panel comparison figures matching dropsonde vertical velocity profiles
(left panel) with satellite precipitation from IMERG (top-right) and EarthCARE (bottom-right).

Requirements per SPEC_sonde_vs_satellite.md:
- Dropsonde panel: omega (Pa/s) vs Pressure (Pa), red for top-heavy, blue for bottom-heavy
- Satellite panels: WhiteBlueGreenYellowRed colormap, horizontal colorbar at bottom
- Time/location matching: Use dropsonde as reference
- Spatial cropping: Based on dropsonde circle radius

"""

from __future__ import annotations

import os
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr


class DropsondeSatelliteComparison:
    """Generate three-panel comparison figures for dropsonde vs satellite data."""

    # Color palette configuration (from SPEC)
    COLOR_TOP_HEAVY = "#d94832"  # Red
    COLOR_BOTTOM_HEAVY = "#2b83c6"  # Blue
    COLOR_INACTIVE = "#4d4d4d"  # Gray

    # Satellite colormap (WhiteBlueGreenYellowRed - use closest available)
    SATELLITE_CMAP = "RdYlGn"  # Note: exact WhiteBlueGreenYellowRed may require custom cmap

    # Figure configuration
    FIGSIZE = (16, 8)  # Larger to accommodate 3 panels
    WIDTH_RATIOS = [1.0, 1.2, 1.2]  # Left: dropsonde, Right: satellites
    WSPACE = 0.25

    def __init__(
        self,
        dropsonde_zarr_path: str | Path,
        categories_csv_path: str | Path,
        imerg_nc_path: str | Path,
        earthcare_nc_path: str | Path | None = None,
        output_dir: str | Path | None = None,
    ):
        """Initialize comparison workflow.

        Args:
            dropsonde_zarr_path: Path to ORCESTRA_dropsondes_categorized.zarr
            categories_csv_path: Path to ORCESTRA_dropsondes_categories.csv
            imerg_nc_path: Path to ORCESTRA_IMERG_Combined_Cropped.nc
            earthcare_nc_path: Path to ORCESTRA_EarthCARE_Combined_Cropped.nc (optional)
            output_dir: Directory to save comparison figures
        """

        self.dropsonde_zarr_path = Path(dropsonde_zarr_path)
        self.categories_csv_path = Path(categories_csv_path)
        self.imerg_nc_path = Path(imerg_nc_path)
        self.earthcare_nc_path = Path(earthcare_nc_path) if earthcare_nc_path else None
        self.output_dir = Path(
            output_dir or "/home/565/zr7147/Proj/outputs/figures/dropsonde_satellite_comparison"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load data
        print("Loading dropsonde and satellite data...")
        self.ds_sonde = xr.open_zarr(str(self.dropsonde_zarr_path))
        self.df_cats = pd.read_csv(str(self.categories_csv_path))
        self.ds_imerg = xr.open_dataset(str(self.imerg_nc_path))
        self.ds_earthcare = (
            xr.open_dataset(str(self.earthcare_nc_path))
            if self.earthcare_nc_path and self.earthcare_nc_path.exists()
            else None
        )

        # Pre-convert IMERG times for efficient matching
        self.imerg_times_np = np.array([np.datetime64(str(t)) for t in self.ds_imerg["time"].to_index()])

        if self.ds_earthcare is not None:
            self.earthcare_times_np = np.array(
                [np.datetime64(str(t)) for t in self.ds_earthcare["time"].to_index()]
            )
        else:
            self.earthcare_times_np = None

        print("✓ Data loaded successfully")

    def get_category_color(self, category: str) -> str:
        """Return color for dropsonde profile based on category.

        Per SPEC:
        - Top-heavy: red
        - Bottom-heavy: blue
        - Other: gray
        """

        if category.startswith("Top-Heavy"):
            return self.COLOR_TOP_HEAVY
        elif category.startswith("Bottom-Heavy"):
            return self.COLOR_BOTTOM_HEAVY
        else:
            return self.COLOR_INACTIVE

    def find_nearest_satellite_time(
        self,
        dropsonde_time: np.datetime64,
        satellite_times: np.ndarray,
    ) -> int:
        """Find nearest satellite observation time to dropsonde measurement.

        Args:
            dropsonde_time: Dropsonde observation time (numpy datetime64)
            satellite_times: Array of satellite times (numpy datetime64)

        Returns:
            Index of nearest satellite time
        """

        return int(np.abs(satellite_times - np.datetime64(dropsonde_time)).argmin())

    def compute_spatial_crop(
        self,
        circle_lat: float,
        circle_lon: float,
        circle_radius_m: float,
        map_radius_scale: float = 1.35,
        min_half_span_deg: float = 0.60,
    ) -> tuple[float, float, float, float]:
        """Compute spatial bounding box for cropping satellite data.

        Converts dropsonde circle radius (meters) to lat/lon degrees.

        Args:
            circle_lat: Circle center latitude
            circle_lon: Circle center longitude
            circle_radius_m: Circle radius in meters
            map_radius_scale: Expand by this factor beyond circle radius
            min_half_span_deg: Minimum half-span in degrees (prevent too-small crops)

        Returns:
            (lat_min, lat_max, lon_min, lon_max)
        """

        radius_deg_lat = circle_radius_m / 111000.0  # ~111 km per degree latitude
        cos_lat = max(np.cos(np.deg2rad(circle_lat)), 0.15)
        radius_deg_lon = circle_radius_m / (111000.0 * cos_lat)

        half_span_lat = max(radius_deg_lat * map_radius_scale, min_half_span_deg)
        half_span_lon = max(radius_deg_lon * map_radius_scale, min_half_span_deg)

        return (
            circle_lat - half_span_lat,
            circle_lat + half_span_lat,
            circle_lon - half_span_lon,
            circle_lon + half_span_lon,
        )

    def create_geographic_circle(
        self,
        circle_lat: float,
        circle_lon: float,
        circle_radius_m: float,
        num_points: int = 361,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Create geographic circle for plotting on map.

        Args:
            circle_lat: Center latitude
            circle_lon: Center longitude
            circle_radius_m: Radius in meters
            num_points: Number of points to define circle

        Returns:
            (circle_lon_array, circle_lat_array)
        """

        radius_deg_lat = circle_radius_m / 111000.0
        cos_lat = max(np.cos(np.deg2rad(circle_lat)), 0.15)
        radius_deg_lon = circle_radius_m / (111000.0 * cos_lat)

        theta = np.linspace(0, 2 * np.pi, num_points)
        circle_lon_array = circle_lon + radius_deg_lon * np.cos(theta)
        circle_lat_array = circle_lat + radius_deg_lat * np.sin(theta)

        return circle_lon_array, circle_lat_array

    def plot_comparison_figure(
        self,
        circle_idx: int,
        category: str,
        top_heaviness_angle: float,
        show_figure: bool = False,
    ) -> Path | None:
        """Generate three-panel figure for single dropsonde event.

        Panels:
        - Left: Dropsonde vertical velocity (omega Pa/s vs Pressure Pa)
        - Top-Right: IMERG precipitation
        - Bottom-Right: EarthCARE precipitation

        Args:
            circle_idx: Dropsonde circle index
            category: Categorization (from category_evolutionary)
            top_heaviness_angle: Top-heaviness angle metric
            show_figure: If True, display figure before saving

        Returns:
            Path to saved figure, or None if data unavailable
        """

        try:
            # Extract dropsonde data
            circle_ds = self.ds_sonde.sel(circle=circle_idx)
            omega_profile = circle_ds["omega"].values  # Pa/s
            p_profile = circle_ds["p_mean"].values  # Pa (NOT hPa per SPEC)
            drop_time = pd.to_datetime(circle_ds["circle_time"].values)
            clat = float(circle_ds["circle_lat"].values)
            clon = float(circle_ds["circle_lon"].values)
            circle_radius_m = float(circle_ds["circle_radius"].values)
            radius_km = circle_radius_m / 1000.0

            # Get profile color
            line_color = self.get_category_color(category)

            # Find nearest satellite times
            drop_np = np.datetime64(drop_time)
            imerg_nearest_idx = self.find_nearest_satellite_time(drop_np, self.imerg_times_np)
            imerg_time = pd.Timestamp(self.imerg_times_np[imerg_nearest_idx])

            if self.earthcare_times_np is not None:
                earthcare_nearest_idx = self.find_nearest_satellite_time(drop_np, self.earthcare_times_np)
                earthcare_time = pd.Timestamp(self.earthcare_times_np[earthcare_nearest_idx])
            else:
                earthcare_nearest_idx = None
                earthcare_time = None

            # Compute spatial crop
            lat_min, lat_max, lon_min, lon_max = self.compute_spatial_crop(
                clat, clon, circle_radius_m
            )

            # Get satellite data at matched times
            imerg_slice = self.ds_imerg["precipitation"].isel(time=imerg_nearest_idx)

            # Ensure lat bounds are in correct order
            if lat_min > lat_max:
                lat_min, lat_max = lat_max, lat_min
            if lon_min > lon_max:
                lon_min, lon_max = lon_max, lon_min

            imerg_local = imerg_slice.sel(
                lon=slice(lon_min, lon_max),
                lat=slice(lat_min, lat_max),
            )

            # Check if cropped data is valid
            if imerg_local.size == 0:
                print(f"  ✗ Circle {circle_idx}: Cropped satellite data is empty")
                plt.close(fig) if 'fig' in locals() else None
                return None

            if self.ds_earthcare is not None and earthcare_nearest_idx is not None:
                earthcare_slice = self.ds_earthcare["precipitation"].isel(time=earthcare_nearest_idx)
                earthcare_local = earthcare_slice.sel(
                    lon=slice(lon_min, lon_max),
                    lat=slice(lat_min, lat_max),
                )
            else:
                earthcare_local = None

            # Create geographic circle
            circle_lon, circle_lat = self.create_geographic_circle(clat, clon, circle_radius_m)

            # ════════════════════════════════════════════════════════════════════════════════════
            # CREATE FIGURE
            # ════════════════════════════════════════════════════════════════════════════════════
            fig = plt.figure(figsize=self.FIGSIZE)

            if earthcare_local is not None:
                # 2 rows: IMERG on top, EarthCARE on bottom
                gs = fig.add_gridspec(2, 2, width_ratios=self.WIDTH_RATIOS, wspace=self.WSPACE, hspace=0.3)
                ax_prof = fig.add_subplot(gs[:, 0])  # Dropsonde spans both rows
                ax_imerg = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
                ax_earthcare = fig.add_subplot(gs[1, 1], projection=ccrs.PlateCarree())
            else:
                # Single satellite panel (IMERG only)
                gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.2], wspace=self.WSPACE)
                ax_prof = fig.add_subplot(gs[0, 0])
                ax_imerg = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
                ax_earthcare = None

            # ────────────────────────────────────────────────────────────────────────────────────
            # LEFT PANEL: DROPSONDE VERTICAL VELOCITY
            # ────────────────────────────────────────────────────────────────────────────────────
            valid = np.isfinite(omega_profile) & np.isfinite(p_profile)

            if valid.sum() == 0:
                print(f"  ✗ Circle {circle_idx}: No valid omega data")
                plt.close(fig)
                return None

            ax_prof.plot(omega_profile[valid], p_profile[valid], color=line_color, lw=2.5)
            ax_prof.axvline(0, color="k", lw=1.0, ls="--", alpha=0.6)
            ax_prof.fill_betweenx(
                p_profile[valid],
                omega_profile[valid],
                0,
                where=(omega_profile[valid] < 0),
                color=line_color,
                alpha=0.15,
                label="Ascending (ω < 0)",
            )

            ax_prof.invert_yaxis()  # Pressure axis inverted
            ax_prof.set_ylim(1000, 100)  # 1000 Pa to 100 Pa
            ax_prof.set_xlabel("Vertical Velocity $\\omega$ (Pa s$^{-1}$)", fontsize=12, fontweight="bold")
            ax_prof.set_ylabel("Pressure (Pa)", fontsize=12, fontweight="bold")
            ax_prof.grid(True, alpha=0.25)
            ax_prof.legend(loc="upper right", fontsize=10)
            ax_prof.set_title(
                f"Dropsonde Vertical Velocity | Circle {circle_idx}",
                fontsize=12,
                fontweight="bold",
            )

            # Add info box
            ax_prof.text(
                0.02,
                0.04,
                f"Category: {category}\n"
                f"Angle: {top_heaviness_angle:.1f}°\n"
                f"Radius: {radius_km:.1f} km",
                transform=ax_prof.transAxes,
                fontsize=10,
                va="bottom",
                ha="left",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.85, edgecolor="0.75"),
            )

            # ────────────────────────────────────────────────────────────────────────────────────
            # TOP-RIGHT PANEL: IMERG PRECIPITATION
            # ────────────────────────────────────────────────────────────────────────────────────
            im_imerg = ax_imerg.pcolormesh(
                imerg_local["lon"].values,
                imerg_local["lat"].values,
                imerg_local.values,
                cmap="RdYlGn",  # TODO: Use WhiteBlueGreenYellowRed if custom cmap available
                vmin=0,
                vmax=10,
                shading="nearest",
                transform=ccrs.PlateCarree(),
            )

            ax_imerg.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
            ax_imerg.coastlines(linewidth=1.0, alpha=0.7)
            ax_imerg.add_feature(cfeature.BORDERS, linewidth=0.5, alpha=0.5)
            gl_imerg = ax_imerg.gridlines(draw_labels=True, linewidth=0.4, alpha=0.4)
            gl_imerg.top_labels = False
            gl_imerg.right_labels = False

            # Plot circle overlay
            ax_imerg.plot(
                circle_lon,
                circle_lat,
                color=line_color,
                lw=2.0,
                ls="--",
                transform=ccrs.PlateCarree(),
                zorder=4,
                label="Circle radius",
            )
            ax_imerg.plot(
                clon,
                clat,
                marker="*",
                markersize=15,
                color=line_color,
                markeredgecolor="black",
                markeredgewidth=0.8,
                transform=ccrs.PlateCarree(),
                zorder=5,
                label=f"Center",
            )
            ax_imerg.legend(loc="lower left", fontsize=9, framealpha=0.9)
            ax_imerg.set_title("IMERG Precipitation", fontsize=12, fontweight="bold")

            # Colorbar
            cbar_imerg = plt.colorbar(im_imerg, ax=ax_imerg, orientation="horizontal", pad=0.1, fraction=0.08)
            cbar_imerg.set_label("Precipitation (mm/hr)", fontsize=10)

            # ────────────────────────────────────────────────────────────────────────────────────
            # BOTTOM-RIGHT PANEL: EARTHCARE PRECIPITATION
            # ────────────────────────────────────────────────────────────────────────────────────
            if ax_earthcare is not None and earthcare_local is not None:
                im_earthcare = ax_earthcare.pcolormesh(
                    earthcare_local["lon"].values,
                    earthcare_local["lat"].values,
                    earthcare_local.values,
                    cmap="RdYlGn",  # TODO: Use WhiteBlueGreenYellowRed
                    vmin=0,
                    vmax=10,
                    shading="nearest",
                    transform=ccrs.PlateCarree(),
                )

                ax_earthcare.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
                ax_earthcare.coastlines(linewidth=1.0, alpha=0.7)
                ax_earthcare.add_feature(cfeature.BORDERS, linewidth=0.5, alpha=0.5)
                gl_ec = ax_earthcare.gridlines(draw_labels=True, linewidth=0.4, alpha=0.4)
                gl_ec.top_labels = False
                gl_ec.right_labels = False

                # Plot circle overlay
                ax_earthcare.plot(
                    circle_lon,
                    circle_lat,
                    color=line_color,
                    lw=2.0,
                    ls="--",
                    transform=ccrs.PlateCarree(),
                    zorder=4,
                    label="Circle radius",
                )
                ax_earthcare.plot(
                    clon,
                    clat,
                    marker="*",
                    markersize=15,
                    color=line_color,
                    markeredgecolor="black",
                    markeredgewidth=0.8,
                    transform=ccrs.PlateCarree(),
                    zorder=5,
                    label="Center",
                )
                ax_earthcare.legend(loc="lower left", fontsize=9, framealpha=0.9)
                ax_earthcare.set_title("EarthCARE Precipitation", fontsize=12, fontweight="bold")

                # Colorbar
                cbar_ec = plt.colorbar(
                    im_earthcare, ax=ax_earthcare, orientation="horizontal", pad=0.1, fraction=0.08
                )
                cbar_ec.set_label("Precipitation (mm/hr)", fontsize=10)

            # ────────────────────────────────────────────────────────────────────────────────────
            # OVERALL FIGURE TITLE
            # ────────────────────────────────────────────────────────────────────────────────────
            title_str = (
                f"Vertical Velocity Profile vs IMERG and EarthCARE Precipitation\n"
                f"Circle {circle_idx} | {category} | "
                f"Drop: {drop_time.strftime('%Y-%m-%d %H:%M:%S')} UTC | "
                f"IMERG: {imerg_time.strftime('%Y-%m-%d %H:%M')} UTC"
            )
            if earthcare_time is not None:
                title_str += f" | EarthCARE: {earthcare_time.strftime('%Y-%m-%d %H:%M')} UTC"

            fig.suptitle(title_str, fontsize=13, fontweight="bold", y=0.98)

            # ────────────────────────────────────────────────────────────────────────────────────
            # SAVE AND DISPLAY
            # ────────────────────────────────────────────────────────────────────────────────────
            out_name = f"circle_{circle_idx:03d}_{category.replace(' ', '_').replace('/', '-')}_comparison.png"
            out_path = self.output_dir / out_name

            plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
            print(f"  ✓ Saved: {out_path.name}")

            if show_figure:
                plt.show()
            else:
                plt.close(fig)

            return out_path

        except Exception as e:
            print(f"  ✗ Circle {circle_idx}: Error - {e}")
            return None

    def process_all_circles(
        self,
        filter_categories: list[str] | None = None,
        show_figures: bool = False,
    ) -> list[Path]:
        """Generate comparison figures for all dropsonde circles.

        Args:
            filter_categories: If provided, only process circles matching these categories.
                              Default: ["Top-Heavy", "Bottom-Heavy"] (dynamic regimes only)
            show_figures: If True, display each figure before saving

        Returns:
            List of paths to saved figures
        """

        if filter_categories is None:
            filter_categories = ["Top-Heavy", "Bottom-Heavy"]

        # Filter circles by category
        df_circles = self.df_cats[
            self.df_cats["category_evolutionary"].fillna("").apply(
                lambda x: any(cat in x for cat in filter_categories)
            )
        ].copy()

        # Sort by circle time
        circle_time_map = {
            int(c): pd.to_datetime(t)
            for c, t in zip(self.ds_sonde["circle"].values, self.ds_sonde["circle_time"].values)
        }
        df_circles["circle_time"] = df_circles["circle"].astype(int).map(circle_time_map)
        df_circles = (
            df_circles.dropna(subset=["circle_time"]).sort_values("circle_time").reset_index(drop=True)
        )

        print(f"\nGenerating {len(df_circles)} comparison figures...")
        print("=" * 80)

        saved_figures = []
        for i, row in df_circles.iterrows():
            circle_idx = int(row["circle"])
            category = str(row["category_evolutionary"])
            angle = float(row["top_heaviness_angle"])

            print(f"[{i+1:3d}/{len(df_circles)}] Processing circle {circle_idx}...", end=" ")

            out_path = self.plot_comparison_figure(circle_idx, category, angle, show_figure=show_figures)

            if out_path is not None:
                saved_figures.append(out_path)

        print("=" * 80)
        print(f"\n✓ Generated {len(saved_figures)} figures")
        print(f"✓ Output directory: {self.output_dir}\n")

        return saved_figures


def main():
    """Main entry point for standalone execution."""

    import argparse

    parser = argparse.ArgumentParser(description="Generate dropsonde vs satellite comparison figures")
    parser.add_argument(
        "--dropsonde",
        type=str,
        default="/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr",
        help="Path to dropsonde Zarr dataset",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default="/g/data/k10/zr7147/ORCESTRA_dropsondes_categories.csv",
        help="Path to categories CSV file",
    )
    parser.add_argument(
        "--imerg",
        type=str,
        default="/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc",
        help="Path to IMERG NetCDF",
    )
    parser.add_argument(
        "--earthcare",
        type=str,
        default=None,
        help="Path to EarthCARE NetCDF (optional)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/home/565/zr7147/Proj/outputs/figures/dropsonde_satellite_comparison",
        help="Output directory for figures",
    )
    parser.add_argument(
        "--filter-categories",
        type=str,
        nargs="+",
        default=["Top-Heavy", "Bottom-Heavy"],
        help="Categories to include (default: Top-Heavy and Bottom-Heavy)",
    )
    parser.add_argument(
        "--show", action="store_true", help="Display figures (default: save without displaying)"
    )

    args = parser.parse_args()

    # Create comparison object and process
    comp = DropsondeSatelliteComparison(
        dropsonde_zarr_path=args.dropsonde,
        categories_csv_path=args.categories,
        imerg_nc_path=args.imerg,
        earthcare_nc_path=args.earthcare,
        output_dir=args.output_dir,
    )

    comp.process_all_circles(filter_categories=args.filter_categories, show_figures=args.show)


if __name__ == "__main__":
    main()
