#!/usr/bin/env python3
"""Process local GPM IMERG files into one cropped NetCDF product."""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path

import xarray as xr
from dask.distributed import Client

from scripts.config import BoundingBox, default_imerg_bbox, default_imerg_input_dir, default_imerg_output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge and crop local IMERG files")
    parser.add_argument("--input-dir", type=Path, default=default_imerg_input_dir())
    parser.add_argument("--output-path", type=Path, default=default_imerg_output_path())
    parser.add_argument("--lat-min", type=float, default=default_imerg_bbox().lat_min)
    parser.add_argument("--lat-max", type=float, default=default_imerg_bbox().lat_max)
    parser.add_argument("--lon-min", type=float, default=default_imerg_bbox().lon_min)
    parser.add_argument("--lon-max", type=float, default=default_imerg_bbox().lon_max)
    return parser.parse_args()


def get_dask_config() -> tuple[int, str]:
    """Build worker settings from PBS/Dask env vars."""

    worker_count = int(os.environ.get("ORCESTRA_DASK_WORKERS", os.environ.get("PBS_NCPUS", "4")))
    memory_limit = os.environ.get("ORCESTRA_DASK_MEMORY_LIMIT", "1800MiB")
    return max(1, worker_count), memory_limit


def clean_imerg(ds: xr.Dataset, bbox: BoundingBox) -> xr.Dataset:
    """Standardize coordinate ordering and crop each IMERG tile."""

    ds = ds.transpose("time", "lat", "lon", ...)

    if ds["lon"].max() > 180:
        ds = ds.assign_coords(lon=(((ds.lon + 180) % 360) - 180)).sortby("lon")

    if ds.lat[0] > ds.lat[-1]:
        lat_slice = slice(bbox.lat_max, bbox.lat_min)
    else:
        lat_slice = slice(bbox.lat_min, bbox.lat_max)

    ds = ds.sel(lon=slice(bbox.lon_min, bbox.lon_max), lat=lat_slice)
    return ds


def main() -> None:
    args = parse_args()
    bbox = BoundingBox(args.lat_min, args.lat_max, args.lon_min, args.lon_max)

    input_dir = args.input_dir
    output_path = args.output_path

    print("Starting ORCESTRA satellite preprocessing...")
    print(f"Input IMERG directory: {input_dir}")
    print(f"Output NetCDF path: {output_path}")
    print(
        "Crop bbox: "
        f"lat[{bbox.lat_min}, {bbox.lat_max}] "
        f"lon[{bbox.lon_min}, {bbox.lon_max}]"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    worker_count, memory_limit = get_dask_config()
    print(f"Dask workers: {worker_count}")
    print(f"Dask memory per worker: {memory_limit}")

    input_files = sorted(glob.glob(str(input_dir / "*.HDF5")))
    if not input_files:
        raise FileNotFoundError(f"No IMERG HDF5 files found in {input_dir}")
    print(f"Found {len(input_files)} IMERG files")

    client = Client(n_workers=worker_count, threads_per_worker=1, memory_limit=memory_limit)
    ds_gpm: xr.Dataset | None = None

    try:
        print(f"Dask dashboard: {client.dashboard_link}")

        ds_gpm = xr.open_mfdataset(
            input_files,
            concat_dim="time",
            combine="nested",
            engine="h5netcdf",
            group="/Grid",
            preprocess=lambda ds: clean_imerg(ds, bbox),
            chunks={"time": 1, "lat": 400, "lon": 400},
            parallel=True,
        )

        ds_gpm = ds_gpm.sortby("time")
        ds_gpm = ds_gpm.drop_vars(["time_bnds", "lat_bnds", "lon_bnds"], errors="ignore")

        encoding = {var: {"zlib": True, "complevel": 4} for var in ds_gpm.data_vars}
        print("Writing merged NetCDF...")
        ds_gpm.to_netcdf(output_path, mode="w", format="NETCDF4", encoding=encoding, compute=True)

        print("Success: merged and cropped IMERG written.")
    finally:
        if ds_gpm is not None:
            ds_gpm.close()
        client.close()


if __name__ == "__main__":
    main()
