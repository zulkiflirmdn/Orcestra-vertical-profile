#!/usr/bin/env python3
"""Wrapper for EarthCARE CPR download using ESA Online Dissemination Services.

This wrapper scripts automatically handles the Python path setup for running
the EarthCARE downloader with the earthcare-downloader package.

Installation:
    pip install earthcare-downloader xarray netCDF4

Setup Credentials:
    Create ESA Online account: https://eoiam-idp.eo.esa.int/
    Set environment variables:
        export ESA_EO_USERNAME="your_email@example.com"
        export ESA_EO_PASSWORD="your_password"

Usage:
    cd /home/565/zr7147/Proj
    python earthcare_download.py [options]

Examples:
    # Download all ORCESTRA data (Aug 10 - Sep 30, 2024)
    python earthcare_download.py

    # Validate ESA credentials
    python earthcare_download.py --validate-credentials

    # List available files without downloading
    python earthcare_download.py --list-only

    # Custom date range
    python earthcare_download.py --start 2024-08-15 --end 2024-08-20

    # Custom domain and faster download (more workers)
    python earthcare_download.py --lat-range 5,20 --lon-range -65,-15 --workers 10

    # Force re-download all files
    python earthcare_download.py --force

    # Download single product only
    python earthcare_download.py --products CPR_CLP_2A

See --help for all options.

Products Available:
    - CPR_CLP_2A: Cloud Profiling Radar Cloud Properties (air_vertical_velocity, cloud_type)
    - CPR_ECO_2A: Cloud Profiling Radar Echo Properties (echo classification)
    - AC__CLP_2B: Synergistic Cloud Properties (multi-sensor)

Output:
    - Raw files: /g/data/k10/zr7147/EarthCARE_Data/{product}/
    - Summary: earthcare_files_downloaded.csv
    - Logs: download_earthcare.log

For more information:
    - See scripts/earthcare_download.py for full implementation
    - See docs/EARTHCARE_STAC_GUIDE.md for alternative methods
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run
from scripts.earthcare_download import main

if __name__ == "__main__":
    sys.exit(main())
