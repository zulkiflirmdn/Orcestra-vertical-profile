#!/usr/bin/env python3
"""
Omega profile categorisation — ORCESTRA BEACH L4.

Implements the omega-plane angle method with radius (magnitude) filter:
  1. Compute projection coefficients c1, c2 onto orthogonal basis functions
  2. Magnitude r = sqrt(c1^2 + c2^2) — filter weak/ambiguous profiles
  3. Angle theta = atan2(c2, c1) — classify by quadrant

Categories (angle boundaries):
  r < R_THRESHOLD              → Inactive / Suppressed  (weak signal, overrides angle)
  |angle| > 150                → Inactive / Suppressed  (subsidence / stratiform)
  27 < angle <= 150            → Top-Heavy
   0 < angle <= 27             → Top-Heavy (Fully Ascending)
  -27 <= angle <= 0            → Bottom-Heavy (Fully Ascending)
  -150 < angle < -27           → Bottom-Heavy

Outputs:
  /g/data/k10/zr7147/processed/omega_plane_categorization.csv

Usage:
  python scripts/categorize_omega.py
  python scripts/categorize_omega.py --threshold 20 --out /g/data/k10/zr7147/processed/omega_plane_categorization.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_NC   = Path("/g/data/k10/zr7147/raw/orcestra_level4.nc")
DEFAULT_OUT  = Path("/g/data/k10/zr7147/processed/omega_plane_categorization.csv")

P_SFC = 1000.0   # hPa
P_TOP = 100.0    # hPa
R_THRESHOLD = 20.0


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _angle_to_category(angle: float) -> str:
    """Map omega-plane angle (degrees) to category label.

    Boundaries follow the expected_category scheme from the notebook:
      |angle| >= 150  → subsidence / near-neutral → Inactive / Suppressed
      27 < angle < 150  → Top-Heavy
       0 < angle <= 27  → Top-Heavy (Fully Ascending)
      -27 <= angle <= 0 → Bottom-Heavy (Fully Ascending)
     -150 < angle < -27 → Bottom-Heavy
    """
    if angle > 150 or angle <= -150:
        return "Inactive / Suppressed"
    elif 27 < angle <= 150:
        return "Top-Heavy"
    elif 0 < angle <= 27:
        return "Top-Heavy (Fully Ascending)"
    elif -27 <= angle <= 0:
        return "Bottom-Heavy (Fully Ascending)"
    else:  # -150 < angle < -27
        return "Bottom-Heavy"


def categorise_circle(
    omega: np.ndarray, p_hpa: np.ndarray, r_threshold: float
) -> tuple[float, float, float, float, str]:
    """Return (angle_deg, c1, c2, r_mag, category) for one circle's omega profile."""
    if np.isnan(omega).all():
        return np.nan, np.nan, np.nan, np.nan, "Missing Data"

    mask = ~np.isnan(omega) & ~np.isnan(p_hpa)
    o_v = -omega[mask]       # flip sign: ascent positive
    p_v = p_hpa[mask]

    # Sort ascending (P_TOP → P_SFC) so trapezoid integrates in the correct direction.
    # BEACH L4 altitude dim runs surface→tropopause, giving decreasing p_v which would
    # negate both c1 and c2, shifting every angle by ±180° and inverting categories.
    sort_idx = np.argsort(p_v)
    p_v = p_v[sort_idx]
    o_v = o_v[sort_idx]

    p_star = (p_v - P_TOP) / (P_SFC - P_TOP)
    c1 = np.trapezoid(o_v * np.sin(    np.pi * p_star), p_v)
    c2 = np.trapezoid(o_v * np.sin(2 * np.pi * p_star), p_v)

    r_mag = np.sqrt(c1**2 + c2**2)
    angle = np.degrees(np.arctan2(c2, c1))

    # Radius filter first: weak/ambiguous profiles → suppress regardless of angle
    if r_mag < r_threshold:
        return angle, c1, c2, r_mag, "Inactive / Suppressed"

    return angle, c1, c2, r_mag, _angle_to_category(angle)


def categorise_all(ds: xr.Dataset, r_threshold: float) -> pd.DataFrame:
    rows = []
    for c in ds.circle.values:
        omega = ds["omega"].sel(circle=c).values
        p_hpa = ds["p_mean"].sel(circle=c).values / 100.0
        angle, c1, c2, r_mag, category = categorise_circle(omega, p_hpa, r_threshold)
        rows.append({
            "circle":               int(c),
            "circle_time":          pd.Timestamp(ds["circle_time"].sel(circle=c).values),
            "angle_deg":            angle,
            "c1":                   c1,
            "c2":                   c2,
            "r_mag":                r_mag,
            "category_omega_plane": category,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Categorise ORCESTRA omega profiles")
    parser.add_argument("--nc",        type=Path, default=DEFAULT_NC)
    parser.add_argument("--out",       type=Path, default=DEFAULT_OUT)
    parser.add_argument("--threshold", type=float, default=R_THRESHOLD,
                        help="Radius magnitude threshold below which a circle is Inactive/Suppressed")
    args = parser.parse_args()

    print(f"Loading: {args.nc}")
    ds = xr.open_dataset(str(args.nc))

    print(f"Categorising {ds.dims['circle']} circles  (R_threshold={args.threshold})...")
    df = categorise_all(ds, args.threshold)

    print("\nCategory counts:")
    print(df["category_omega_plane"].value_counts().to_string())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
