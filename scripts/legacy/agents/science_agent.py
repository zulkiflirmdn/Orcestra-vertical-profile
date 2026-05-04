#!/usr/bin/env python3
"""
Science Agent — ORCESTRA scientific analysis.

Two-layer design:
  1. Rule-based core  — always runs, no API key, directly computes from BEACH L4
  2. Haiku 4.5 layer  — optional (--interpret), adds scientific interpretation
                        Uses claude-haiku-4-5 (cheapest Claude) — sufficient for
                        domain Q&A on pre-computed summaries.  Set ANTHROPIC_API_KEY.

Specializations:
  profile   — omega profile shape analysis for one circle
  category  — top-heavy / bottom-heavy classification table
  imerg     — IMERG coverage check for a circle time window
  stats     — campaign-wide statistics (angle, IWV distribution)

Usage:
  python scripts/agents/science_agent.py --task profile --circle 5
  python scripts/agents/science_agent.py --task profile --circle 5 --interpret
  python scripts/agents/science_agent.py --task stats
  python scripts/agents/science_agent.py --task imerg --circle 5
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ZARR  = Path("/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr")
IMERG = Path("/g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc")
CSV   = Path("/g/data/k10/zr7147/ORCESTRA_dropsondes_categories.csv")

# Pressure levels used for profile feature extraction (Pa)
FEATURE_LEVELS_PA = np.array([100000, 85000, 70000, 50000, 30000, 20000], dtype=float)

# Top-heaviness angle thresholds (degrees, from pre-computed metric)
ANGLE_TOP_HEAVY_THRESHOLD    =  0.0   # positive → top-heavy
ANGLE_STRONG_THRESHOLD       = 10.0   # |angle| > 10 → strong signal


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_dataset() -> xr.Dataset:
    return xr.open_zarr(str(ZARR))


def load_imerg() -> xr.Dataset:
    return xr.open_dataset(str(IMERG))


def cftime_to_np64(t) -> np.datetime64:
    return np.datetime64(t.strftime("%Y-%m-%dT%H:%M:%S"))


# ---------------------------------------------------------------------------
# Profile analysis
# ---------------------------------------------------------------------------

def analyze_profile(ds: xr.Dataset, circle_idx: int) -> dict:
    """Extract key features from the omega profile for one circle."""
    c = ds.sel(circle=circle_idx)
    omega = c["omega"].values        # Pa/s, on altitude grid (meters)
    p     = c["p_mean"].values       # Pa

    valid = np.isfinite(omega) & np.isfinite(p)
    if valid.sum() < 10:
        return {"circle": circle_idx, "error": "insufficient valid data"}

    omega_v = omega[valid]
    p_v     = p[valid]

    # Interpolate omega onto standard pressure levels
    sort_idx = np.argsort(p_v)
    p_sorted = p_v[sort_idx]
    o_sorted = omega_v[sort_idx]

    omega_at_levels = {}
    for level in FEATURE_LEVELS_PA:
        if p_sorted.min() <= level <= p_sorted.max():
            omega_at_levels[int(level)] = float(np.interp(level, p_sorted, o_sorted))

    # Profile shape metrics
    lower_half = p_v > np.nanmedian(p_v)
    upper_half = p_v < np.nanmedian(p_v)
    omega_lower_mean = float(np.nanmean(omega_v[lower_half])) if lower_half.any() else np.nan
    omega_upper_mean = float(np.nanmean(omega_v[upper_half])) if upper_half.any() else np.nan

    # Level of max ascent (minimum omega = strongest upward motion)
    p_max_ascent = float(p_v[np.nanargmin(omega_v)])

    category  = str(c["category_avg"].values)
    angle     = float(c["top_heaviness_angle"].values)
    iwv       = float(c["iwv_mean"].values)
    clat      = float(c["circle_lat"].values)
    clon      = float(c["circle_lon"].values)
    ctime     = str(c["circle_time"].values)[:19]

    # Interpret shape
    if angle > ANGLE_STRONG_THRESHOLD:
        shape_label = "strongly top-heavy (deep stratiform signature)"
    elif angle > ANGLE_TOP_HEAVY_THRESHOLD:
        shape_label = "weakly top-heavy"
    elif angle > -ANGLE_STRONG_THRESHOLD:
        shape_label = "weakly bottom-heavy"
    else:
        shape_label = "strongly bottom-heavy (shallow convection dominant)"

    return {
        "circle": circle_idx,
        "time_utc": ctime,
        "lat": round(clat, 2),
        "lon": round(clon, 2),
        "category": category,
        "top_heaviness_angle_deg": round(angle, 2),
        "shape_interpretation": shape_label,
        "p_max_ascent_Pa": round(p_max_ascent),
        "p_max_ascent_hPa": round(p_max_ascent / 100),
        "omega_lower_mean_Pas": round(omega_lower_mean, 5),
        "omega_upper_mean_Pas": round(omega_upper_mean, 5),
        "iwv_kg_m2": round(iwv, 1),
        "omega_at_levels_Pa": {str(k): round(v, 5) for k, v in omega_at_levels.items()},
    }


def format_profile_report(info: dict) -> str:
    if "error" in info:
        return f"Circle {info['circle']}: ERROR — {info['error']}"
    lines = [
        f"[Science Agent] Profile Analysis — Circle {info['circle']}",
        "─" * 55,
        f"  Time       : {info['time_utc']} UTC",
        f"  Location   : {info['lat']}°N  {info['lon']}°E",
        f"  Category   : {info['category']}",
        f"  Angle      : {info['top_heaviness_angle_deg']}°  →  {info['shape_interpretation']}",
        f"  Max ascent : {info['p_max_ascent_hPa']} hPa  ({info['p_max_ascent_Pa']} Pa)",
        f"  ω lower    : {info['omega_lower_mean_Pas']} Pa s⁻¹  (below midpoint)",
        f"  ω upper    : {info['omega_upper_mean_Pas']} Pa s⁻¹  (above midpoint)",
        f"  IWV        : {info['iwv_kg_m2']} kg m⁻²",
        "  ω at standard levels (Pa s⁻¹):",
    ]
    for level, val in info["omega_at_levels_Pa"].items():
        lines.append(f"    {int(level)//100:>4} hPa : {val:+.5f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Campaign-wide statistics
# ---------------------------------------------------------------------------

def campaign_stats(ds: xr.Dataset) -> str:
    angles   = ds["top_heaviness_angle"].values.astype(float)
    cats     = ds["category_avg"].values
    iwv      = ds["iwv_mean"].values.astype(float)
    n        = len(angles)

    n_top    = int(np.sum([str(c) != "" and "Top-Heavy"    in str(c) for c in cats]))
    n_bot    = int(np.sum([str(c) != "" and "Bottom-Heavy" in str(c) for c in cats]))
    n_other  = n - n_top - n_bot

    lines = [
        "[Science Agent] Campaign Statistics",
        "─" * 55,
        f"  Total circles          : {n}",
        f"  Top-Heavy              : {n_top} ({100*n_top/n:.1f}%)",
        f"  Bottom-Heavy           : {n_bot} ({100*n_bot/n:.1f}%)",
        f"  Other / Suppressed     : {n_other} ({100*n_other/n:.1f}%)",
        "",
        "  Top-heaviness angle (deg):",
        f"    Mean   : {np.nanmean(angles):+.2f}",
        f"    Median : {np.nanmedian(angles):+.2f}",
        f"    Std    : {np.nanstd(angles):.2f}",
        f"    Min    : {np.nanmin(angles):+.2f}",
        f"    Max    : {np.nanmax(angles):+.2f}",
        "",
        "  Integrated Water Vapour (kg m⁻²):",
        f"    Mean   : {np.nanmean(iwv):.1f}",
        f"    Std    : {np.nanstd(iwv):.1f}",
        f"    Range  : {np.nanmin(iwv):.1f} – {np.nanmax(iwv):.1f}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Category summary table
# ---------------------------------------------------------------------------

def category_summary(ds: xr.Dataset) -> str:
    circles = ds["circle"].values
    rows = []
    for ci in circles:
        c = ds.sel(circle=ci)
        rows.append({
            "circle": int(ci),
            "time": str(c["circle_time"].values)[:16],
            "category": str(c["category_avg"].values),
            "angle": round(float(c["top_heaviness_angle"].values), 1),
            "iwv": round(float(c["iwv_mean"].values), 1),
        })

    lines = [
        "[Science Agent] Circle Category Summary",
        "─" * 65,
        f"  {'Circle':>6}  {'Time':>16}  {'Angle':>7}  {'IWV':>6}  Category",
        "  " + "-" * 60,
    ]
    for r in rows:
        lines.append(
            f"  {r['circle']:>6}  {r['time']:>16}  {r['angle']:>+7.1f}  "
            f"{r['iwv']:>6.1f}  {r['category']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# IMERG coverage check for a circle
# ---------------------------------------------------------------------------

def imerg_coverage(ds: xr.Dataset, circle_idx: int) -> str:
    spc = ds["sondes_per_circle"].values.astype(int)
    cum = np.concatenate([[0], np.cumsum(spc)])
    i_first = int(cum[circle_idx])
    i_last  = int(cum[circle_idx + 1]) - 1
    t_start = np.datetime64(ds["launch_time"].values[i_first], "s")
    t_end   = np.datetime64(ds["launch_time"].values[i_last],  "s")
    pad     = np.timedelta64(30, "m")

    ds_im   = load_imerg()
    raw     = ds_im["time"].values
    imerg_np = np.array([cftime_to_np64(t) for t in raw])

    mask    = (imerg_np >= t_start - pad) & (imerg_np <= t_end + pad)
    matched = imerg_np[mask]

    lines = [
        f"[Science Agent] IMERG Coverage — Circle {circle_idx}",
        "─" * 55,
        f"  Circle window : {t_start} → {t_end} UTC",
        f"  Search window : ±30 min padding",
        f"  IMERG matches : {len(matched)}",
    ]
    for t in matched:
        lines.append(f"    • {t} UTC")
    if len(matched) == 0:
        lines.append("  WARNING: No IMERG data found for this circle window")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optional Haiku interpretation layer (requires ANTHROPIC_API_KEY)
# Model: claude-haiku-4-5-20251001 — cheapest Claude, sufficient for
# domain Q&A on structured pre-computed summaries.
# ---------------------------------------------------------------------------

HAIKU_MODEL = "claude-haiku-4-5-20251001"

HAIKU_SYSTEM = """You are a scientific interpreter for an atmospheric science PhD project (ORCESTRA).
RQ2: Does convective organisation modulate the vertical velocity profile and GMS?
Theoretical chain: Organisation → Stratiform Fraction ↑ → Top-Heavy ω → GMS ↑ → Energy Export

Given a structured analysis report computed directly from BEACH L4 dropsonde data, provide
a concise scientific interpretation (3-5 sentences). Focus on what the numbers mean for RQ2.
Be specific — reference the actual values in the report. Do not repeat the numbers, interpret them."""


def haiku_interpret(report_text: str) -> str:
    """Send a pre-computed report to Haiku for scientific interpretation."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "(Haiku interpretation skipped — ANTHROPIC_API_KEY not set)"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            system=HAIKU_SYSTEM,
            messages=[{"role": "user", "content": report_text}],
        )
        return "\n[Haiku Interpretation]\n" + msg.content[0].text
    except Exception as e:
        return f"\n(Haiku interpretation failed: {e})"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Science Agent — ORCESTRA analysis")
    parser.add_argument(
        "--task",
        choices=["profile", "category", "stats", "imerg"],
        required=True,
    )
    parser.add_argument("--circle", type=int, default=None)
    parser.add_argument(
        "--interpret",
        action="store_true",
        help="Append Haiku 4.5 scientific interpretation (requires ANTHROPIC_API_KEY)",
    )
    args = parser.parse_args()

    ds = load_dataset()
    report = ""

    if args.task == "profile":
        if args.circle is None:
            parser.error("--task profile requires --circle N")
        info = analyze_profile(ds, args.circle)
        report = format_profile_report(info)

    elif args.task == "category":
        report = category_summary(ds)

    elif args.task == "stats":
        report = campaign_stats(ds)

    elif args.task == "imerg":
        if args.circle is None:
            parser.error("--task imerg requires --circle N")
        report = imerg_coverage(ds, args.circle)

    print(report)
    if args.interpret:
        print(haiku_interpret(report))


if __name__ == "__main__":
    main()
