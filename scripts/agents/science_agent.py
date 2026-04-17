#!/usr/bin/env python3
"""
Claude Science Agent — scientific reasoning for ORCESTRA analysis.
Handles: omega interpretation, GMS decisions, ERA5 strategy, methodology.
Run: python scripts/agents/science_agent.py --ask "your question"
"""

import os
import argparse
import xarray as xr
import numpy as np
import anthropic

# ── Config ────────────────────────────────────────────────────────────────────

ZARR = "/g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr"

SYSTEM_PROMPT = """
You are the Science Agent for an atmospheric science PhD project studying tropical convection.

Research question (RQ2):
Does convective organisation modulate the vertical velocity profile and Gross Moist Stability (GMS)?

Theoretical chain:
Convective Organisation → Stratiform Fraction ↑ → Top-Heavy ω → GMS ↑ → Efficient Energy Export

Dataset: BEACH Level 4 (ORCESTRA/HALO, Aug-Sep 2024, tropical Atlantic)
- omega(circle, altitude): vertical velocity [Pa/s], altitude in METERS
- p_mean(circle, altitude): pressure [Pa] — use for y-axis, never hPa
- top_heaviness_angle: pre-computed metric per circle
- category_avg: "Top-Heavy (Average Method)" or "Bottom-Heavy (Average Method)"
- color convention: Top-Heavy = red, Bottom-Heavy = blue

Satellite data:
- IMERG: precipitation, READY
- ERA5: environmental context (SST, CWV, winds) — replacing EarthCARE

Rules:
- Always use Pa, never hPa
- EarthCARE is dropped — do not reference it
- Processing logic goes in scripts/*.py, exploration in notebooks
"""


def load_circle_summary(circle_idx: int) -> str:
    """Load basic circle metadata to give Claude context."""
    try:
        ds = xr.open_zarr(ZARR)
        c = ds.isel(circle=circle_idx)
        return (
            f"Circle {circle_idx}: {str(c.circle_id.values)}\n"
            f"Time: {str(c.circle_time.values)[:19]} UTC\n"
            f"Lat: {float(c.circle_lat):.2f}N  Lon: {float(c.circle_lon):.2f}E\n"
            f"Category: {str(c.category_avg.values)}\n"
            f"Top-heaviness angle: {float(c.top_heaviness_angle):.3f}\n"
            f"IWV mean: {float(c.iwv_mean):.1f} kg/m2\n"
        )
    except Exception as e:
        return f"Could not load circle {circle_idx}: {e}"


def ask_claude(question: str, circle_idx: int = None) -> str:
    """Send a scientific question to Claude."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    context = ""
    if circle_idx is not None:
        context = f"\nCircle data:\n{load_circle_summary(circle_idx)}\n"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context + question}],
    )
    return message.content[0].text


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Claude Science Agent for ORCESTRA project")
    parser.add_argument("--ask", type=str, required=True, help="Scientific question")
    parser.add_argument("--circle", type=int, default=None, help="Circle index for context")
    args = parser.parse_args()

    print(f"\n[Claude Science Agent]\n{'─'*50}")
    result = ask_claude(args.ask, circle_idx=args.circle)
    print(result)


if __name__ == "__main__":
    main()
