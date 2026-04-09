#!/usr/bin/env python3
"""Wrapper for EarthCARE STAC API download.

Usage:
    python earthcare_stac_download.py [options]

Examples:
    # Download EarthCARE data for ORCESTRA campaign
    python earthcare_stac_download.py

    # List available collections
    python earthcare_stac_download.py --list-collections

    # Custom bounding box and date range
    python earthcare_stac_download.py --lat-min 5 --lat-max 20 --lon-min -70 --lon-max -15 \\
        --start-date 2024-08-10 --end-date 2024-08-15

    # Use existing files without re-downloading
    python earthcare_stac_download.py --skip-download
"""

import sys
from pathlib import Path

# Add project scripts to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.earthcare_stac_download import main

if __name__ == "__main__":
    exit(main())
