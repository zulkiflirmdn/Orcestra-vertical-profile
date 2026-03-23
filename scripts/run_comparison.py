#!/usr/bin/env python3
"""Generate 3-panel comparison figures: Dropsonde + IMERG + EarthCARE CPR.

Per SPEC: Left=Dropsonde omega, Top-Right=IMERG precipitation, Bottom-Right=EarthCARE.
EarthCARE CPR data is 1D curtain (along-track x height), shown as radar reflectivity cross-section.
"""

import os
import sys
import glob
import warnings
import h5py
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path('/g/data/k10/zr7147')
DROPSONDE_ZARR = DATA_DIR / 'ORCESTRA_dropsondes_categorized.zarr'
CATEGORIES_CSV = DATA_DIR / 'ORCESTRA_dropsondes_categories.csv'
IMERG_NC = DATA_DIR / 'ORCESTRA_IMERG_Combined_Cropped.nc'
CPR_CLP_DIR = DATA_DIR / 'EarthCARE_Data' / 'CPR_CLP_2A'
OUTPUT_DIR = Path('/home/565/zr7147/Proj/outputs/figures/dropsonde_satellite_comparison')

# Pressure-axis unit for dropsonde panel: set ORCESTRA_PRESSURE_UNIT=hPa (default) or Pa
PRESSURE_UNIT = os.getenv('ORCESTRA_PRESSURE_UNIT', 'hPa').strip().lower()
CPR_SEARCH_RADIUS_DEG = float(os.getenv('ORCESTRA_CPR_SEARCH_RADIUS_DEG', '5.0'))
CPR_MAX_TIME_HOURS = float(os.getenv('ORCESTRA_CPR_MAX_TIME_HOURS', '48'))

# SPEC colors
COLOR_TOP_HEAVY = '#d94832'
COLOR_BOTTOM_HEAVY = '#2b83c6'
COLOR_INACTIVE = '#4d4d4d'

# WhiteBlueGreenYellowRed colormap approximation
precip_colors = [
    '#FFFFFF', '#DDEEFF', '#99CCFF', '#3399FF', '#0066CC',
    '#00CC66', '#33FF33', '#99FF00', '#FFFF00', '#FFCC00',
    '#FF9900', '#FF6600', '#FF3300', '#CC0000', '#990000'
]
PRECIP_CMAP = mcolors.LinearSegmentedColormap.from_list('WhiteBlueGreenYellowRed', precip_colors, N=256)


def get_category_color(category):
    if 'Top-Heavy' in str(category):
        return COLOR_TOP_HEAVY
    elif 'Bottom-Heavy' in str(category):
        return COLOR_BOTTOM_HEAVY
    return COLOR_INACTIVE


def load_cpr_clp_files(cpr_dir):
    """Load all CPR_CLP_2A files, extract lat/lon/time/reflectivity for region matching."""
    h5_files = sorted(glob.glob(str(cpr_dir / '*.h5')))
    print(f'  Found {len(h5_files)} CPR_CLP_2A h5 files')

    cpr_data = []
    for fpath in h5_files:
        try:
            f = h5py.File(fpath, 'r')
            lat = f['ScienceData/Geo/latitude'][:]
            lon = f['ScienceData/Geo/longitude'][:]
            height = f['ScienceData/Geo/height'][:]
            ref = f['ScienceData/Data/cloud_radar_reflectivity_1km'][:]
            cwc = f['ScienceData/Data/cloud_water_content_1km'][:]

            yr = f['ScienceData/Geo/Scan_Time/Year'][:]
            mo = f['ScienceData/Geo/Scan_Time/Month'][:]
            dy = f['ScienceData/Geo/Scan_Time/DayOfMonth'][:]
            hr = f['ScienceData/Geo/Scan_Time/Hour'][:]
            mn = f['ScienceData/Geo/Scan_Time/Minute'][:]
            sc = f['ScienceData/Geo/Scan_Time/Second'][:]

            # Build time array
            times = []
            for i in range(len(yr)):
                try:
                    times.append(datetime(int(yr[i]), int(mo[i]), int(dy[i]), int(hr[i]), int(mn[i]), int(sc[i])))
                except:
                    times.append(None)

            cpr_data.append({
                'file': fpath,
                'lat': lat,
                'lon': lon,
                'height': height,
                'reflectivity': ref,
                'cwc': cwc,
                'times': times,
            })
            f.close()
        except Exception as e:
            continue

    print(f'  Successfully loaded {len(cpr_data)} CPR files')
    return cpr_data


def find_nearest_cpr(cpr_data_list, target_lat, target_lon, target_time, search_radius_deg=5.0, max_time_hours=48):
    """Find CPR track closest to dropsonde location and time."""
    best_file = None
    best_dist = float('inf')
    best_idx_range = None

    target_dt = pd.to_datetime(target_time)

    for cpr in cpr_data_list:
        lat = cpr['lat']
        lon = cpr['lon']

        # Find points near the dropsonde
        dist = np.sqrt((lat - target_lat)**2 + (lon - target_lon)**2)
        near_mask = dist < search_radius_deg

        if not np.any(near_mask):
            continue

        # Check time proximity
        near_idx = np.where(near_mask)[0]
        cpr_time = cpr['times'][near_idx[len(near_idx)//2]]
        if cpr_time is None:
            continue

        time_diff_hours = abs((target_dt - pd.Timestamp(cpr_time)).total_seconds()) / 3600
        if time_diff_hours > max_time_hours:
            continue

        min_dist = dist[near_mask].min()

        # Weight by both distance and time
        score = min_dist + time_diff_hours * 0.1  # weight time less than distance

        if score < best_dist:
            best_dist = score
            best_file = cpr
            # Get a wider slice around the nearest point
            center_idx = near_idx[len(near_idx)//2]
            # Take 500 pts around center for a good cross-section
            start = max(0, center_idx - 250)
            end = min(len(lat), center_idx + 250)
            best_idx_range = (start, end)

    return best_file, best_idx_range, best_dist


def create_geographic_circle(clat, clon, radius_m, num_points=361):
    """Create circle coordinates for map overlay."""
    radius_deg_lat = radius_m / 111000.0
    cos_lat = max(np.cos(np.deg2rad(clat)), 0.15)
    radius_deg_lon = radius_m / (111000.0 * cos_lat)
    theta = np.linspace(0, 2 * np.pi, num_points)
    return clon + radius_deg_lon * np.cos(theta), clat + radius_deg_lat * np.sin(theta)


def plot_comparison(circle_idx, circle_ds, category, angle, ds_imerg, cpr_data_list, output_dir):
    """Generate one 3-panel comparison figure."""
    try:
        omega = circle_ds['omega'].values
        p_mean = circle_ds['p_mean'].values
        drop_time = pd.to_datetime(circle_ds['circle_time'].values)
        clat = float(circle_ds['circle_lat'].values)
        clon = float(circle_ds['circle_lon'].values)
        radius_m = float(circle_ds['circle_radius'].values)

        line_color = get_category_color(category)

        # ── IMERG matching ──
        drop_np = np.datetime64(drop_time)
        imerg_times = ds_imerg['time'].values
        imerg_idx = int(np.abs(np.array([np.datetime64(str(t)) for t in imerg_times]) - drop_np).argmin())
        imerg_time = imerg_times[imerg_idx]

        # Spatial crop
        span_lat = max(radius_m / 111000.0 * 1.35, 0.6)
        cos_lat = max(np.cos(np.deg2rad(clat)), 0.15)
        span_lon = max(radius_m / (111000.0 * cos_lat) * 1.35, 0.6)
        lat_min, lat_max = clat - span_lat, clat + span_lat
        lon_min, lon_max = clon - span_lon, clon + span_lon

        if lat_min > lat_max:
            lat_min, lat_max = lat_max, lat_min
        if lon_min > lon_max:
            lon_min, lon_max = lon_max, lon_min

        imerg_local = ds_imerg['precipitation'].isel(time=imerg_idx).sel(
            lon=slice(lon_min, lon_max), lat=slice(lat_min, lat_max)
        )

        if imerg_local.size == 0:
            print(f'  X Circle {circle_idx}: Empty IMERG crop')
            return None

        # ── EarthCARE CPR matching ──
        cpr_file, cpr_range, cpr_dist = find_nearest_cpr(
            cpr_data_list,
            clat,
            clon,
            drop_time,
            search_radius_deg=CPR_SEARCH_RADIUS_DEG,
            max_time_hours=CPR_MAX_TIME_HOURS,
        )
        has_earthcare = cpr_file is not None and cpr_range is not None

        # ── Circle overlay ──
        circ_lon, circ_lat = create_geographic_circle(clat, clon, radius_m)

        # ═══════ CREATE FIGURE ═══════
        fig = plt.figure(figsize=(16, 8))

        if has_earthcare:
            gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.2], wspace=0.25, hspace=0.35)
            ax_prof = fig.add_subplot(gs[:, 0])
            ax_imerg = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
            ax_ec = fig.add_subplot(gs[1, 1])
        else:
            gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.2], wspace=0.25)
            ax_prof = fig.add_subplot(gs[0, 0])
            ax_imerg = fig.add_subplot(gs[0, 1], projection=ccrs.PlateCarree())
            ax_ec = None

        # ─── LEFT PANEL: Dropsonde vertical velocity ───
        valid = np.isfinite(omega) & np.isfinite(p_mean)
        if valid.sum() == 0:
            plt.close(fig)
            return None

        p_plot = p_mean[valid].astype(float)
        y_label = 'Pressure (Pa)'

        if PRESSURE_UNIT == 'hpa':
            p_plot = p_plot / 100.0
            y_label = 'Pressure (hPa)'

        ax_prof.plot(omega[valid], p_plot, color=line_color, lw=2.5)
        ax_prof.axvline(0, color='k', lw=1.0, ls='--', alpha=0.6)
        ax_prof.fill_betweenx(
            p_plot, omega[valid], 0,
            where=(omega[valid] < 0), color=line_color, alpha=0.15, label='Ascending (w < 0)'
        )
        ax_prof.invert_yaxis()
        ax_prof.set_xlabel(r'Vertical Velocity $\omega$ (Pa s$^{-1}$)', fontsize=12, fontweight='bold')
        ax_prof.set_ylabel(y_label, fontsize=12, fontweight='bold')

        # Optional meteorology-style limits when plotting in hPa.
        if PRESSURE_UNIT == 'hpa':
            ax_prof.set_ylim(1020, 100)
        ax_prof.grid(True, alpha=0.25)
        ax_prof.legend(loc='upper right', fontsize=10)
        ax_prof.set_title(f'Dropsonde Vertical Velocity | Circle {circle_idx}', fontsize=12, fontweight='bold')
        ax_prof.text(
            0.02, 0.04,
            f'Category: {category}\nAngle: {angle:.1f} deg\nRadius: {radius_m/1000:.1f} km',
            transform=ax_prof.transAxes, fontsize=10, va='bottom', ha='left',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.85, edgecolor='0.75')
        )

        # ─── TOP-RIGHT PANEL: IMERG precipitation ───
        im = ax_imerg.pcolormesh(
            imerg_local['lon'].values, imerg_local['lat'].values, imerg_local.values,
            cmap=PRECIP_CMAP, vmin=0, vmax=10, shading='nearest', transform=ccrs.PlateCarree()
        )
        ax_imerg.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
        ax_imerg.coastlines(linewidth=1.0, alpha=0.7)
        ax_imerg.add_feature(cfeature.BORDERS, linewidth=0.5, alpha=0.5)
        gl = ax_imerg.gridlines(draw_labels=True, linewidth=0.4, alpha=0.4)
        gl.top_labels = False
        gl.right_labels = False
        ax_imerg.plot(circ_lon, circ_lat, color=line_color, lw=2.0, ls='--', transform=ccrs.PlateCarree(), zorder=4)
        ax_imerg.plot(clon, clat, marker='*', markersize=15, color=line_color,
                      markeredgecolor='black', markeredgewidth=0.8, transform=ccrs.PlateCarree(), zorder=5)
        ax_imerg.set_title('IMERG Precipitation', fontsize=12, fontweight='bold')

        cbar = plt.colorbar(im, ax=ax_imerg, orientation='horizontal', pad=0.1, fraction=0.08)
        cbar.set_label('Precipitation (mm/hr)', fontsize=10)

        # ─── BOTTOM-RIGHT PANEL: EarthCARE CPR ───
        if ax_ec is not None and has_earthcare:
            s, e = cpr_range
            cpr_lat = cpr_file['lat'][s:e]
            cpr_height = cpr_file['height'][s:e, :] / 1000.0  # Convert to km
            cpr_ref = cpr_file['reflectivity'][s:e, :]

            # Mask fill values
            cpr_ref = np.where(cpr_ref > -900, cpr_ref, np.nan)

            # Get time of CPR pass
            cpr_time = cpr_file['times'][s + (e-s)//2]
            cpr_time_str = cpr_time.strftime('%Y-%m-%d %H:%M') if cpr_time else 'N/A'

            # Plot reflectivity curtain
            im_ec = ax_ec.pcolormesh(
                cpr_lat, cpr_height[:, 0] if cpr_height.ndim == 1 else np.arange(cpr_height.shape[1]),
                cpr_ref.T, cmap='jet', vmin=-30, vmax=20, shading='nearest'
            )

            # Better approach: use actual height values
            # x-axis = latitude along track, y-axis = height in km
            lat_2d = np.broadcast_to(cpr_lat[:, np.newaxis], cpr_height.shape)

            ax_ec.clear()
            im_ec = ax_ec.pcolormesh(
                lat_2d, cpr_height, cpr_ref,
                cmap='jet', vmin=-30, vmax=20, shading='nearest'
            )
            ax_ec.set_ylim(0, 18)
            ax_ec.set_xlabel('Latitude (deg)', fontsize=11)
            ax_ec.set_ylabel('Height (km)', fontsize=11)
            ax_ec.set_title(f'EarthCARE CPR Reflectivity | {cpr_time_str} UTC', fontsize=12, fontweight='bold')

            # Mark dropsonde location
            ax_ec.axvline(clat, color=line_color, lw=2.0, ls='--', alpha=0.8, label=f'Dropsonde ({clat:.1f}N)')
            ax_ec.legend(loc='upper right', fontsize=9, framealpha=0.9)

            cbar_ec = plt.colorbar(im_ec, ax=ax_ec, orientation='horizontal', pad=0.15, fraction=0.08)
            cbar_ec.set_label('Radar Reflectivity (dBZ)', fontsize=10)

        # ─── OVERALL TITLE ───
        title = (
            f"Vertical Velocity Profile vs IMERG and EarthCARE Precipitation\n"
            f"Circle {circle_idx} | {category} | "
            f"Drop: {drop_time.strftime('%Y-%m-%d %H:%M:%S')} UTC | "
            f"IMERG: {str(imerg_time)[:16]} UTC"
        )
        if has_earthcare and cpr_file and cpr_file['times'][cpr_range[0] + (cpr_range[1]-cpr_range[0])//2]:
            ec_t = cpr_file['times'][cpr_range[0] + (cpr_range[1]-cpr_range[0])//2]
            title += f" | EarthCARE: {ec_t.strftime('%Y-%m-%d %H:%M')} UTC"

        fig.suptitle(title, fontsize=13, fontweight='bold', y=0.99)

        # Save
        out_name = f"circle_{circle_idx:03d}_{category.replace(' ', '_').replace('/', '-')}_comparison.png"
        out_path = output_dir / out_name
        plt.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        return out_path, has_earthcare

    except Exception as e:
        print(f'  X Circle {circle_idx}: Error - {e}')
        import traceback
        traceback.print_exc()
        plt.close('all')
        return None, False


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print('=' * 80)
    print('DROPSONDE vs SATELLITE COMPARISON WORKFLOW')
    print('=' * 80)

    # Load dropsonde data
    print('\n1. Loading dropsonde data...')
    ds_sonde = xr.open_zarr(str(DROPSONDE_ZARR))
    df_cats = pd.read_csv(str(CATEGORIES_CSV))
    print(f'   Circles: {ds_sonde.sizes["circle"]}')
    print(f'   Categories: {df_cats["category_evolutionary"].value_counts().to_dict()}')

    # Load IMERG
    print('\n2. Loading IMERG precipitation data...')
    ds_imerg = xr.open_dataset(str(IMERG_NC))
    print(f'   Time steps: {ds_imerg.sizes["time"]}')
    print(f'   Lat range: {float(ds_imerg.lat.min()):.2f} to {float(ds_imerg.lat.max()):.2f}')
    print(f'   Lon range: {float(ds_imerg.lon.min()):.2f} to {float(ds_imerg.lon.max()):.2f}')

    # Load CPR data
    print('\n3. Loading EarthCARE CPR_CLP data...')
    cpr_data_list = load_cpr_clp_files(CPR_CLP_DIR)
    print(f'   EarthCARE search radius: {CPR_SEARCH_RADIUS_DEG:.1f} deg')
    print(f'   EarthCARE max time offset: {CPR_MAX_TIME_HOURS:.1f} hours')

    # Filter to Top-Heavy and Bottom-Heavy circles
    filter_cats = ['Top-Heavy', 'Bottom-Heavy']
    df_filtered = df_cats[
        df_cats['category_evolutionary'].fillna('').apply(
            lambda x: any(cat in x for cat in filter_cats)
        )
    ].copy()

    # Map circle times
    circle_time_map = {}
    for c in ds_sonde['circle'].values:
        try:
            t = pd.to_datetime(ds_sonde.sel(circle=c)['circle_time'].values)
            circle_time_map[int(c)] = t
        except:
            pass

    df_filtered['circle_time'] = df_filtered['circle'].astype(int).map(circle_time_map)
    df_filtered = df_filtered.dropna(subset=['circle_time']).sort_values('circle_time').reset_index(drop=True)

    print(f'\n4. Processing {len(df_filtered)} circles (Top-Heavy + Bottom-Heavy)...')
    print('=' * 80)

    saved = []
    earthcare_matched = 0
    for i, row in df_filtered.iterrows():
        circle_idx = int(row['circle'])
        category = str(row['category_evolutionary'])
        angle = float(row['top_heaviness_angle'])

        print(f'[{i+1:3d}/{len(df_filtered)}] Circle {circle_idx} ({category})...', end=' ')

        circle_ds = ds_sonde.sel(circle=circle_idx)
        out, has_earthcare = plot_comparison(circle_idx, circle_ds, category, angle, ds_imerg, cpr_data_list, OUTPUT_DIR)

        if out:
            saved.append(out)
            if has_earthcare:
                earthcare_matched += 1
            print(f'OK -> {out.name}')
        else:
            print('SKIPPED')

    print('=' * 80)
    print(f'\nDone! Generated {len(saved)} comparison figures.')
    print(f'EarthCARE matches: {earthcare_matched}/{len(saved)}')
    print(f'Output: {OUTPUT_DIR}')

    ds_sonde.close()
    ds_imerg.close()


if __name__ == '__main__':
    main()
