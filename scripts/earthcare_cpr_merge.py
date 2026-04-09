#!/usr/bin/env python3
"""Wrapper for EarthCARE CPR_CLP_2A merge script.

Usage:
    python earthcare_cpr_merge.py

Output:
    /g/data/k10/zr7147/ORCESTRA_EarthCARE_CPR_CLP_2A_merged.nc
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run
from scripts.earthcare_cpr_merge import main

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
