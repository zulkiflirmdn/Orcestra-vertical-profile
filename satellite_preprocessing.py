#!/usr/bin/env python3
"""
ORCESTRA Satellite Data Processing Script
=========================================

This script downloads and processes GPM IMERG satellite precipitation data
for the ORCESTRA campaign region.

Requirements:
- xarray
- h5netcdf
- dask
"""

import glob
import xarray as xr
import os
from dask.distributed import Client


def clean_imerg(ds):
    """Standardize IMERG tiles before merging.

    - Ensure coordinates are (time, lat, lon)
    - Normalize longitudes to [-180, 180) if needed
    - Crop to the ORCESTRA region so all tiles share the same grid
    """

    # 1) Transpose to standard (time, lat, lon)
    #    Use `...` so non-core dimensions (e.g., nv, latv, lonv) are preserved.
    ds = ds.transpose('time', 'lat', 'lon', ...)

    # 2) Fix longitude convention (0..360 -> -180..180) to avoid wrap-around artifacts
    if ds['lon'].max() > 180:
        ds = ds.assign_coords(lon=(((ds.lon + 180) % 360) - 180)).sortby('lon')

    # 3) Crop to ORCESTRA campaign bounding box
    #    Make sure we slice in the correct direction whether lat is ascending or descending.
    lat_min, lat_max = 5, 20
    if ds.lat[0] > ds.lat[-1]:
        lat_slice = slice(lat_max, lat_min)
    else:
        lat_slice = slice(lat_min, lat_max)

    ds = ds.sel(lon=slice(-65, -15), lat=lat_slice)

    return ds


def main():
    print("Starting ORCESTRA satellite data processing...")

    # Skip authentication and download - data already exists locally
    print("Using existing local GPM IMERG data...")

    # Define your Gadi Scratch directory for storage (Home is too small!)
    output_dir = "/g/data/k10/zr7147/GPM_IMERG_Data"
    os.makedirs(output_dir, exist_ok=True)

    print(f"Data directory: {output_dir}")
    output_path = "/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Initialize Dask client for parallel processing
    print("Setting up Dask client for parallel processing...")
    # Use 16 workers as specified in PBS script (32GB / 16 = 2GB per worker)
    client = Client(n_workers=16, threads_per_worker=1, memory_limit='2GB')
    print(f"Dask is ready! Dashboard: {client.dashboard_link}")

    # Open with Parallel Dask Processing
    print("Loading and processing data...")

    # Collect files in a deterministic order and apply a preprocessing step
    # so all tiles share the same coordinate grid before merging.
    input_files = sorted(glob.glob(os.path.join(output_dir, "*.HDF5")))

    ds_gpm = xr.open_mfdataset(
        input_files,
        concat_dim='time',
        combine='nested',
        engine='h5netcdf',
        group='/Grid',
        preprocess=clean_imerg,
        chunks={'time': 1, 'lat': 400, 'lon': 400},  # Chunk for memory efficiency
        parallel=True
    )

    # Sort by time (safe guard in case filenames don't sort perfectly)
    ds_gpm = ds_gpm.sortby('time')

    # Drop bounds variables that can trigger encoding issues for chunked arrays
    # (e.g., time_bnds uses object dtype in some IMERG files).
    ds_gpm = ds_gpm.drop_vars(['time_bnds', 'lat_bnds', 'lon_bnds'], errors='ignore')

    # Save with Compression (saves disk space on Gadi!)
    encoding = {var: {'zlib': True, 'complevel': 4} for var in ds_gpm.data_vars}

    # Physical Write to Disk
    print(f"Starting the combined write to: {output_path}...")
    print("This will process files one-by-one to keep RAM usage low.")

    ds_gpm.to_netcdf(
        output_path,
        mode='w',
        format='NETCDF4',
        encoding=encoding,
        compute=True
    )

    print("Success! Single cropped file created.")
    print(f"Output file: {output_path}")

    # Clean up
    client.close()

if __name__ == "__main__":
    main()