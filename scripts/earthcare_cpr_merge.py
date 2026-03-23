#!/usr/bin/env python3
"""Efficiently merge EarthCARE CPR_CLP_2A HDF5 files into NetCDF using chunking.

Processes files in batches to avoid massive memory requirements.

Output: /g/data/k10/zr7147/ORCESTRA_EarthCARE_CPR_CLP_2A_merged.nc
"""

import logging
from pathlib import Path
from typing import List, Dict, Tuple
import warnings

import h5py
import numpy as np
import xarray as xr

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore', category=UserWarning)

INPUT_DIR = Path("/g/data/k10/zr7147/EarthCARE_Data/CPR_CLP_2A")
OUTPUT_FILE = Path("/g/data/k10/zr7147/ORCESTRA_EarthCARE_CPR_CLP_2A_merged.nc")
BATCH_SIZE = 10  # Process 10 files at a time


def extract_cpr_data(filepath: Path) -> Dict:
    """Extract key variables from CPR_CLP_2A HDF5 file."""
    try:
        with h5py.File(filepath, 'r') as f:
            latitude = f['ScienceData/Geo/latitude'][:]
            longitude = f['ScienceData/Geo/longitude'][:]
            height = f['ScienceData/Geo/height'][:]

            year = f['ScienceData/Geo/Scan_Time/Year'][:]
            month = f['ScienceData/Geo/Scan_Time/Month'][:]
            day = f['ScienceData/Geo/Scan_Time/DayOfMonth'][:]
            hour = f['ScienceData/Geo/Scan_Time/Hour'][:]
            minute = f['ScienceData/Geo/Scan_Time/Minute'][:]
            second = f['ScienceData/Geo/Scan_Time/Second'][:]

            time_str = np.array([
                f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}"
                for y, mo, d, h, mi, s in zip(year, month, day, hour, minute, second)
            ], dtype='datetime64[s]')

            vertical_velocity = f['ScienceData/Data/cloud_air_velocity_1km'][:]
            reflectivity = f['ScienceData/Data/cloud_radar_reflectivity_1km'][:]
            temperature = f['ScienceData/Data/GRID_temperature_1km'][:]
            pressure = f['ScienceData/Data/GRID_pressure_1km'][:]

            return {
                'latitude': latitude,
                'longitude': longitude,
                'height': height,
                'time': time_str,
                'vertical_velocity': vertical_velocity,
                'reflectivity': reflectivity,
                'temperature': temperature,
                'pressure': pressure,
            }
    except Exception as e:
        logger.warning(f"Error reading {filepath.name}: {e}")
        return None


def process_batch(files: List[Path]) -> Tuple[Dict, int]:
    """Process a batch of files and return combined data.

    Returns:
        Tuple of (data_dict, total_scans)
    """
    all_data = []
    valid_count = 0

    for filepath in files:
        data = extract_cpr_data(filepath)
        if data is not None:
            all_data.append(data)
            valid_count += 1

    if not all_data:
        return None, 0

    # Concatenate along scan dimension
    combined = {
        'latitude': np.concatenate([d['latitude'] for d in all_data]),
        'longitude': np.concatenate([d['longitude'] for d in all_data]),
        'height': np.concatenate([d['height'] for d in all_data], axis=0),
        'time': np.concatenate([d['time'] for d in all_data]),
        'vertical_velocity': np.concatenate([d['vertical_velocity'] for d in all_data], axis=0),
        'reflectivity': np.concatenate([d['reflectivity'] for d in all_data], axis=0),
        'temperature': np.concatenate([d['temperature'] for d in all_data], axis=0),
        'pressure': np.concatenate([d['pressure'] for d in all_data], axis=0),
    }

    total_scans = combined['latitude'].shape[0]
    return combined, total_scans


def merge_cpr_files_chunked(files: List[Path]) -> str:
    """Merge CPR files in chunks and write directly to NetCDF."""

    logger.info(f"Processing {len(files)} files in batches of {BATCH_SIZE}...")

    # Process first batch to establish schema
    logger.info(f"Processing batch 1/{(len(files) + BATCH_SIZE - 1) // BATCH_SIZE}...")
    first_batch = files[:BATCH_SIZE]
    data, total_frames = process_batch(first_batch)

    if data is None:
        raise ValueError("No valid data in first batch!")

    nlevels = data['vertical_velocity'].shape[1]

    logger.info(f"  Batch 1: {total_frames} scans × {nlevels} levels")

    # Create initial dataset
    ds = xr.Dataset(
        data_vars={
            'vertical_velocity': (['scan', 'level'], data['vertical_velocity'],
                                  {'units': 'Pa/s', 'long_name': 'Air Vertical Velocity'}),
            'reflectivity': (['scan', 'level'], data['reflectivity'],
                           {'units': 'dBZ', 'long_name': 'Radar Reflectivity'}),
            'temperature': (['scan', 'level'], data['temperature'],
                          {'units': 'K', 'long_name': 'Temperature'}),
            'pressure': (['scan', 'level'], data['pressure'],
                       {'units': 'Pa', 'long_name': 'Pressure'}),
            'height': (['scan', 'level'], data['height'],
                     {'units': 'm', 'long_name': 'Height above surface'}),
        },
        coords={
            'latitude': (['scan'], data['latitude']),
            'longitude': (['scan'], data['longitude']),
            'time': (['scan'], data['time']),
        }
    )

    # Process remaining batches and append
    current_offset = BATCH_SIZE
    batch_num = 2
    total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

    while current_offset < len(files):
        end = min(current_offset + BATCH_SIZE, len(files))
        batch_files = files[current_offset:end]

        logger.info(f"Processing batch {batch_num}/{total_batches}...")
        batch_data, batch_frames = process_batch(batch_files)

        if batch_data is not None:
            logger.info(f"  Batch {batch_num}: {batch_frames} scans")

            # Create batch dataset
            batch_ds = xr.Dataset(
                data_vars={
                    'vertical_velocity': (['scan', 'level'], batch_data['vertical_velocity']),
                    'reflectivity': (['scan', 'level'], batch_data['reflectivity']),
                    'temperature': (['scan', 'level'], batch_data['temperature']),
                    'pressure': (['scan', 'level'], batch_data['pressure']),
                    'height': (['scan', 'level'], batch_data['height']),
                },
                coords={
                    'latitude': (['scan'], batch_data['latitude']),
                    'longitude': (['scan'], batch_data['longitude']),
                    'time': (['scan'], batch_data['time']),
                }
            )

            # Concatenate along scan dimension
            ds = xr.concat([ds, batch_ds], dim='scan')

        current_offset = end
        batch_num += 1

    # Fix coordinate naming for consistency
    ds = ds.assign_coords({'scan': np.arange(ds.dims['scan']), 'level': np.arange(nlevels)})

    # Add attributes
    ds.attrs = {
        'title': 'EarthCARE CPR Cloud Profiling Radar - Merged L2 Product',
        'product': 'CPR_CLP_2A',
        'campaign': 'ORCESTRA',
        'domain': 'Atlantic (0N-30N, 70W-0W)',
        'time_period': f"{ds['time'].values[0]} to {ds['time'].values[-1]}",
        'source': 'ESA EarthCARE Mission',
        'processing_date': np.datetime64('today'),
    }

    logger.info(f"\nDataset Info:")
    logger.info(f"  Dimensions: {dict(ds.dims)}")
    logger.info(f"  Variables: {list(ds.data_vars)}")
    logger.info(f"  Time range: {ds['time'].values[0]} to {ds['time'].values[-1]}")
    logger.info(f"  Lat range:  {float(ds['latitude'].min()):.2f}° to {float(ds['latitude'].max()):.2f}°")
    logger.info(f"  Lon range:  {float(ds['longitude'].min()):.2f}° to {float(ds['longitude'].max()):.2f}°")

    # Write to NetCDF with compression
    logger.info("\nWriting to NetCDF...")
    encoding = {var: {'zlib': True, 'complevel': 4} for var in ds.data_vars}
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(OUTPUT_FILE, encoding=encoding, mode='w', format='NETCDF4')

    file_size_gb = OUTPUT_FILE.stat().st_size / (1024**3)
    logger.info(f"\n✅ Successfully wrote {OUTPUT_FILE}")
    logger.info(f"   Size: {file_size_gb:.2f} GB")
    logger.info(f"   Records: {ds.dims['scan']:,} scans × {ds.dims['level']} levels")

    return str(OUTPUT_FILE)


def main():
    logger.info("="*70)
    logger.info("EarthCARE CPR_CLP_2A HDF5 → NetCDF Merger (Chunked)")
    logger.info("="*70)
    logger.info(f"Input directory:  {INPUT_DIR}")
    logger.info(f"Output file:      {OUTPUT_FILE}")
    logger.info(f"Batch size:       {BATCH_SIZE} files")

    h5_files = sorted(INPUT_DIR.glob("*.h5"))
    if not h5_files:
        logger.error(f"No HDF5 files found in {INPUT_DIR}")
        return False

    logger.info(f"Found {len(h5_files)} CPR_CLP_2A files\n")

    try:
        output_path = merge_cpr_files_chunked(h5_files)
        logger.info(f"\n🎉 Merge complete! File ready at:")
        logger.info(f"   {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error during merge: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
