#!/usr/bin/env python3
"""
Gemini Data Agent — scans /g/data/ and reports dataset status.
Handles: file counts, domain coverage checks, EarthCARE audit, notebook bloat.
Run: python scripts/agents/data_agent.py --task status
"""

import os
import time
import argparse
import subprocess
from pathlib import Path

from google import genai
from google.genai.errors import ClientError

GDATA = Path("/g/data/k10/zr7147")
PROJ  = Path("/home/565/zr7147/Proj")

MODELS = [
    "models/gemini-2.5-flash",        # best available, try first
    "models/gemini-2.0-flash-lite",   # lighter fallback
    "models/gemini-2.0-flash",        # final fallback
]

SYSTEM_PROMPT = """You are the Data Agent for an atmospheric science research project (ORCESTRA).
Inspect filesystem reports and answer questions about data readiness.

Key paths:
- BEACH L4 zarr:  /g/data/k10/zr7147/ORCESTRA_dropsondes_categorized.zarr (89 circles)
- IMERG NetCDF:   /g/data/k10/zr7147/ORCESTRA_IMERG_Combined_Cropped.nc
- Raw IMERG HDF5: /g/data/k10/zr7147/GPM_IMERG_Data/ (expect 2496 files)
- ERA5:           /g/data/k10/zr7147/ERA5/ (planned, not yet downloaded)

Rules:
- EarthCARE is DROPPED — flag any earthcare references as dead code
- Report status as READY / PARTIAL / MISSING
- Be concise — use bullet points"""


def collect_filesystem_report() -> str:
    """Run shell checks and return a compact report for Gemini."""
    checks = {
        "BEACH L4 zarr":      f"ls -lh {GDATA}/ORCESTRA_dropsondes_categorized.zarr 2>/dev/null | head -1 || echo MISSING",
        "Categories CSV":     f"ls -lh {GDATA}/ORCESTRA_dropsondes_categories.csv 2>/dev/null || echo MISSING",
        "IMERG NetCDF":       f"ls -lh {GDATA}/ORCESTRA_IMERG_Combined_Cropped.nc 2>/dev/null || echo MISSING",
        "Raw IMERG count":    f"find {GDATA}/GPM_IMERG_Data -name '*.HDF5' 2>/dev/null | wc -l",
        "ERA5 directory":     f"ls {GDATA}/ERA5/ 2>/dev/null | head -3 || echo MISSING",
        "EarthCARE remnants": f"find {PROJ}/scripts -name '*earthcare*' -o -name '*EarthCARE*' 2>/dev/null | grep -v __pycache__ || echo none",
        "Output figures":     f"find {PROJ}/outputs -name '*.png' 2>/dev/null | wc -l",
        "Large notebooks":    f"find {PROJ}/notebooks -name '*.ipynb' -size +100k 2>/dev/null | xargs -I{{}} basename {{}} || echo none",
    }

    lines = []
    for label, cmd in checks.items():
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        lines.append(f"{label}: {result.stdout.strip()}")

    return "\n".join(lines)


def run_task(task: str, extra: str = "") -> str:
    """Send a task to Gemini, auto-fallback through model list on quota errors."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    report = collect_filesystem_report()

    prompt_map = {
        "status":    f"Filesystem report:\n{report}\n\nGive a status table (READY/PARTIAL/MISSING) and flag any issues.",
        "earthcare": f"Filesystem report:\n{report}\n\nList EarthCARE remnants and say: delete or archive?",
        "notebooks": f"Filesystem report:\n{report}\n\nWhich notebooks are too large (likely have outputs)? What to do?",
        "custom":    f"Filesystem report:\n{report}\n\nQuestion: {extra}",
    }

    full_prompt = SYSTEM_PROMPT + "\n\n" + prompt_map.get(task, prompt_map["custom"])

    for model in MODELS:
        try:
            print(f"  trying {model}...")
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
            )
            print(f"  ✓ {model} responded\n")
            return response.text
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                print(f"  ✗ {model} quota exhausted, trying next...")
                time.sleep(3)
                continue
            if "503" in err or "UNAVAILABLE" in err:
                print(f"  ✗ {model} overloaded, retrying in 10s...")
                time.sleep(10)
                continue
            if "404" in err or "NOT_FOUND" in err:
                print(f"  ✗ {model} not available, trying next...")
                continue
            raise

    return "All Gemini models quota exhausted. Wait a few minutes and retry, or add billing to your Google AI project."


def main():
    parser = argparse.ArgumentParser(description="Gemini Data Agent for ORCESTRA project")
    parser.add_argument("--task", choices=["status", "earthcare", "notebooks", "custom"],
                        default="status")
    parser.add_argument("--ask", type=str, default="", help="Custom question (with --task custom)")
    args = parser.parse_args()

    print(f"\n[Gemini Data Agent] Task: {args.task}\n{'─'*50}")
    result = run_task(args.task, extra=args.ask)
    print(result)


if __name__ == "__main__":
    main()
