#!/usr/bin/env python3
"""Wrapper: Download IMERG data from NASA Earthdata.

This wrapper automatically handles the Python path setup.

Usage:
    cd /home/565/zr7147/Proj
    python imerg_download.py [options]

Options:
    --lat-min MIN           Minimum latitude (default: 0)
    --lat-max MAX           Maximum latitude (default: 30)
    --lon-min MIN           Minimum longitude (default: -70)
    --lon-max MAX           Maximum longitude (default: 0)
    --start-date DATE       Start date YYYY-MM-DD (default: 2024-08-10)
    --end-date DATE         End date YYYY-MM-DD (default: 2024-09-30)
    --force                 Re-download existing files

Examples:
    python imerg_download.py
    python imerg_download.py --lat-min 5 --lat-max 20
    python imerg_download.py --start-date 2024-08-15

See scripts/imerg_download.py for full documentation.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run
from scripts.imerg_download import download_imerg, parse_args

if __name__ == "__main__":
    args = parse_args()

    from scripts.config import default_imerg_bbox, default_imerg_input_dir

    bbox = default_imerg_bbox()
    if args.lat_min is not None:
        bbox.lat_min = args.lat_min
    if args.lat_max is not None:
        bbox.lat_max = args.lat_max
    if args.lon_min is not None:
        bbox.lon_min = args.lon_min
    if args.lon_max is not None:
        bbox.lon_max = args.lon_max

    output_dir = args.output_dir or default_imerg_input_dir()
    date_range = (args.start_date, args.end_date)

    download_imerg(
        bbox=bbox,
        date_range=date_range,
        output_dir=output_dir,
        skip_existing=not args.force,
    )
