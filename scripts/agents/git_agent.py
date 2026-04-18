#!/usr/bin/env python3
"""
Git Agent — enforces git hygiene for the ORCESTRA project.
Rule-based checks need no API key.
Optional commit message suggestion uses claude-haiku-4-5 (cheapest Claude).

Checks:
  - Staged files that violate .gitignore rules (large data files, outputs)
  - Large files accidentally staged (>500 KB)
  - Notebook outputs in staged notebooks
  - Files from /g/data/ paths referenced in staging area
  - Uncommitted changes summary

Actions:
  status   — show full hygiene report
  staged   — check only what is staged right now
  summary  — one-line commit-ready summary
  suggest  — Haiku 4.5 commit message suggestion (requires ANTHROPIC_API_KEY)

Usage:
  python scripts/agents/git_agent.py --action status
  python scripts/agents/git_agent.py --action staged
  python scripts/agents/git_agent.py --action summary
  python scripts/agents/git_agent.py --action suggest
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2]

# Extensions that must never be committed
BANNED_EXTENSIONS = {".nc", ".zarr", ".hdf5", ".h5", ".npy", ".npz"}

# Path fragments that must never appear in committed files
BANNED_PATH_FRAGMENTS = ["/g/data/", "GPM_IMERG_Data", "miniconda3", "orcestra_env"]

# Size threshold for a warning (bytes)
LARGE_FILE_THRESHOLD = 500 * 1024  # 500 KB


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=PROJ)
    return result.stdout.strip()


def get_staged_files() -> list[Path]:
    raw = _run("git diff --cached --name-only")
    return [PROJ / p for p in raw.splitlines() if p]


def get_modified_files() -> list[str]:
    return _run("git diff --name-only").splitlines()


def get_untracked_files() -> list[str]:
    return _run("git ls-files --others --exclude-standard").splitlines()


def get_recent_commits(n: int = 5) -> str:
    return _run(f"git log --oneline -{n}")


def get_branch() -> str:
    return _run("git rev-parse --abbrev-ref HEAD")


def get_diff_stat() -> str:
    return _run("git diff --cached --stat")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_staged_extensions(staged: list[Path]) -> list[dict]:
    issues = []
    for path in staged:
        if path.suffix.lower() in BANNED_EXTENSIONS:
            issues.append({
                "file": str(path.relative_to(PROJ)),
                "reason": f"Extension '{path.suffix}' must never be committed — data file",
            })
    return issues


def check_staged_size(staged: list[Path]) -> list[dict]:
    issues = []
    for path in staged:
        if path.exists() and path.stat().st_size > LARGE_FILE_THRESHOLD:
            size_kb = path.stat().st_size // 1024
            issues.append({
                "file": str(path.relative_to(PROJ)),
                "size_kb": size_kb,
                "reason": f"File is {size_kb} KB — unusually large for a code/doc file",
            })
    return issues


def check_staged_notebook_outputs(staged: list[Path]) -> list[dict]:
    issues = []
    for path in staged:
        if path.suffix != ".ipynb" or not path.exists():
            continue
        try:
            nb = json.loads(path.read_text())
        except Exception:
            continue
        output_cells = sum(
            1 for cell in nb.get("cells", []) if cell.get("outputs")
        )
        if output_cells:
            issues.append({
                "file": str(path.relative_to(PROJ)),
                "output_cells": output_cells,
                "reason": "Notebook has cell outputs — run 'jupyter nbconvert --clear-output' before committing",
            })
    return issues


def check_banned_path_fragments(staged: list[Path]) -> list[dict]:
    issues = []
    for path in staged:
        if not path.exists() or path.suffix in {".png", ".pdf", ".jpg"}:
            continue
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        for fragment in BANNED_PATH_FRAGMENTS:
            if fragment in text:
                issues.append({
                    "file": str(path.relative_to(PROJ)),
                    "fragment": fragment,
                    "reason": f"Contains '{fragment}' — hardcoded path should use config.py",
                })
                break
    return issues


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _fmt_section(title: str, items: list[dict], key_fields: list[str]) -> str:
    if not items:
        return f"  ✓ {title}\n"
    lines = [f"  ✗ {title} — {len(items)} issue(s):"]
    for item in items:
        parts = [f"    • {item.get('file', '?')}"]
        for k in key_fields:
            if k in item:
                parts.append(f"({item[k]})")
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def run_staged_check() -> str:
    staged = get_staged_files()
    if not staged:
        return "[Git Agent] Nothing staged.\n"

    ext_issues  = check_staged_extensions(staged)
    size_issues = check_staged_size(staged)
    nb_issues   = check_staged_notebook_outputs(staged)
    path_issues = check_banned_path_fragments(staged)

    all_issues = ext_issues + size_issues + nb_issues + path_issues
    verdict = "BLOCKED — fix issues before committing" if all_issues else "CLEAR — safe to commit"

    lines = [
        f"[Git Agent] Staged files: {len(staged)}  |  {verdict}",
        "─" * 55,
        _fmt_section("Banned extensions", ext_issues, ["reason"]),
        _fmt_section("Large files",       size_issues, ["size_kb", "reason"]),
        _fmt_section("Notebook outputs",  nb_issues,   ["output_cells", "reason"]),
        _fmt_section("Hardcoded paths",   path_issues, ["fragment", "reason"]),
    ]

    if all_issues:
        lines.append("\nFix the above before committing.")
    return "\n".join(lines)


def run_status() -> str:
    branch   = get_branch()
    modified = get_modified_files()
    untrack  = get_untracked_files()
    recent   = get_recent_commits()
    staged_report = run_staged_check()

    lines = [
        f"[Git Agent] Branch: {branch}",
        "─" * 55,
        staged_report,
        f"\nModified (unstaged): {len(modified)} file(s)",
        *[f"  {f}" for f in modified[:10]],
        f"\nUntracked: {len(untrack)} file(s)",
        *[f"  {f}" for f in untrack[:10]],
        f"\nRecent commits:\n{recent}",
    ]
    return "\n".join(lines)


def run_summary() -> str:
    staged = get_staged_files()
    stat   = get_diff_stat()
    branch = get_branch()
    verdict = "CLEAR" if not (
        check_staged_extensions(staged) +
        check_staged_size(staged) +
        check_staged_notebook_outputs(staged)
    ) else "BLOCKED"
    return (
        f"[Git Agent] Branch={branch}  Staged={len(staged)} files  "
        f"Status={verdict}\n{stat}"
    )


# ---------------------------------------------------------------------------
# Haiku commit message suggestion (requires ANTHROPIC_API_KEY)
# Model: claude-haiku-4-5-20251001 — cheapest Claude, ideal for short
# summarisation tasks like drafting a commit message from a diff stat.
# ---------------------------------------------------------------------------

HAIKU_MODEL = "claude-haiku-4-5-20251001"


def suggest_commit_message() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "[Git Agent] ANTHROPIC_API_KEY not set — cannot suggest commit message."

    staged = get_staged_files()
    if not staged:
        return "[Git Agent] Nothing staged — no commit message to suggest."

    stat    = get_diff_stat()
    diff    = _run("git diff --cached --unified=3")[:3000]  # cap to avoid large context
    branch  = get_branch()

    prompt = f"""Branch: {branch}
Staged diff stat:
{stat}

Diff (truncated):
{diff}

Write a single concise git commit message (imperative, ≤72 chars subject line, optional short body).
Follow conventional commits style if appropriate. Output ONLY the commit message, nothing else."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        suggestion = msg.content[0].text.strip()
        return f"[Git Agent — Haiku suggestion]\n{suggestion}"
    except Exception as e:
        return f"[Git Agent] Haiku suggestion failed: {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Git Agent — ORCESTRA git hygiene")
    parser.add_argument(
        "--action",
        choices=["status", "staged", "summary", "suggest"],
        default="status",
    )
    args = parser.parse_args()

    if args.action == "status":
        print(run_status())
    elif args.action == "staged":
        print(run_staged_check())
    elif args.action == "summary":
        print(run_summary())
    elif args.action == "suggest":
        print(suggest_commit_message())


if __name__ == "__main__":
    main()
