#!/usr/bin/env python3
"""
Quality Agent — static analysis of the ORCESTRA codebase.
No LLM, no API key. Pure rule-based checks.

Checks:
  - Banned patterns in scripts (hPa, EarthCARE, hardcoded /g/data paths in wrong places)
  - Figure spec compliance (labels, colormap, colorbar placement)
  - Dead code detection (legacy EarthCARE files still present)
  - Notebook output bloat (uncommitted cell outputs)

Usage:
  python scripts/agents/quality_agent.py --check all
  python scripts/agents/quality_agent.py --check code
  python scripts/agents/quality_agent.py --check figures
  python scripts/agents/quality_agent.py --check notebooks
"""

import argparse
import ast
import json
import subprocess
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2]
SCRIPTS = PROJ / "scripts"
NOTEBOOKS = PROJ / "notebooks"
OUTPUTS = PROJ / "outputs"

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

# Patterns that must never appear in active scripts (not legacy/)
BANNED_CODE_PATTERNS = [
    ("hPa",           "Use Pa not hPa — CLAUDE.md rule"),
    ("earthcare",     "EarthCARE is dropped — remove reference"),
    ("EarthCARE",     "EarthCARE is dropped — remove reference"),
    ("import earthcare", "EarthCARE import — dead code"),
]

# Figure spec: these strings must appear in any comparison plot script
REQUIRED_FIGURE_STRINGS = [
    ("WhiteBlueGreenYellowRed", "IMERG colormap must be WhiteBlueGreenYellowRed"),
    ("orientation=\"horizontal\"", "Colorbar must be horizontal"),
    (r"Pa s\$^{-1}\$",            "x-axis label must use Pa s^-1 omega notation"),
]

# Legacy files that should not exist outside scripts/legacy/
DEAD_CODE_NAMES = [
    "earthcare_preprocessing.py",
    "earthcare_download.py",
    "earthcare_stac_download.py",
    "earthcare_cpr_merge.py",
]


# ---------------------------------------------------------------------------
# Check: banned patterns in active scripts
# ---------------------------------------------------------------------------

def check_code() -> list[dict]:
    issues = []
    active_scripts = [
        p for p in SCRIPTS.rglob("*.py")
        if "legacy" not in p.parts and "agents" not in p.parts
    ]
    for path in active_scripts:
        text = path.read_text(errors="replace")
        for pattern, reason in BANNED_CODE_PATTERNS:
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern in line and not line.strip().startswith("#"):
                    issues.append({
                        "file": str(path.relative_to(PROJ)),
                        "line": lineno,
                        "pattern": pattern,
                        "reason": reason,
                        "snippet": line.strip()[:80],
                    })
    return issues


# ---------------------------------------------------------------------------
# Check: dead EarthCARE files outside legacy/
# ---------------------------------------------------------------------------

def check_dead_code() -> list[dict]:
    issues = []
    for name in DEAD_CODE_NAMES:
        for found in PROJ.rglob(name):
            if "legacy" not in found.parts:
                issues.append({
                    "file": str(found.relative_to(PROJ)),
                    "reason": f"{name} is dead code (EarthCARE dropped) — move to legacy/ or delete",
                })
    return issues


# ---------------------------------------------------------------------------
# Check: figure spec compliance in plotting scripts
# ---------------------------------------------------------------------------

def check_figures() -> list[dict]:
    issues = []
    plot_scripts = list(SCRIPTS.glob("*comparison*.py")) + list(SCRIPTS.glob("*plot*.py"))
    for path in plot_scripts:
        text = path.read_text(errors="replace")
        for pattern, reason in REQUIRED_FIGURE_STRINGS:
            if pattern not in text:
                issues.append({
                    "file": str(path.relative_to(PROJ)),
                    "pattern": pattern,
                    "reason": reason,
                })
    return issues


# ---------------------------------------------------------------------------
# Check: notebook output bloat
# ---------------------------------------------------------------------------

def check_notebooks() -> list[dict]:
    issues = []
    for nb_path in NOTEBOOKS.rglob("*.ipynb"):
        try:
            nb = json.loads(nb_path.read_text())
        except Exception:
            continue
        has_outputs = False
        output_cell_count = 0
        for cell in nb.get("cells", []):
            outputs = cell.get("outputs", [])
            if outputs:
                has_outputs = True
                output_cell_count += 1
        if has_outputs:
            size_kb = nb_path.stat().st_size // 1024
            issues.append({
                "file": str(nb_path.relative_to(PROJ)),
                "output_cells": output_cell_count,
                "size_kb": size_kb,
                "reason": "Notebook has cell outputs — clear before committing",
            })
    return issues


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _section(title: str, items: list[dict], key_fields: list[str]) -> str:
    if not items:
        return f"  ✓ {title}: no issues\n"
    lines = [f"  ✗ {title}: {len(items)} issue(s)"]
    for item in items:
        parts = [f"    [{item.get('file', '?')}]"]
        for k in key_fields:
            if k in item:
                parts.append(f"{k}={item[k]}")
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def run_checks(mode: str) -> str:
    sections = []

    if mode in ("all", "code"):
        code_issues = check_code()
        dead_issues = check_dead_code()
        sections.append(_section("Banned patterns", code_issues, ["line", "pattern", "reason"]))
        sections.append(_section("Dead code", dead_issues, ["reason"]))

    if mode in ("all", "figures"):
        fig_issues = check_figures()
        sections.append(_section("Figure spec", fig_issues, ["pattern", "reason"]))

    if mode in ("all", "notebooks"):
        nb_issues = check_notebooks()
        sections.append(_section("Notebook outputs", nb_issues, ["output_cells", "size_kb", "reason"]))

    total_issues = sum(
        len(check_code()) + len(check_dead_code()) if mode in ("all", "code") else 0,
        # avoid re-running; just show sections above
    ) if False else None

    header = f"[Quality Agent] mode={mode}\n{'─' * 50}\n"
    return header + "".join(sections)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quality Agent — ORCESTRA static analysis")
    parser.add_argument(
        "--check",
        choices=["all", "code", "figures", "notebooks"],
        default="all",
    )
    args = parser.parse_args()
    print(run_checks(args.check))


if __name__ == "__main__":
    main()
