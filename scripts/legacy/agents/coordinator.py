#!/usr/bin/env python3
"""
Coordinator — routes tasks to the right specialised agent.

Agent roles:
  data     → Gemini Data Agent    file counts, /g/data/ status, coverage checks
  science  → Science Agent        omega profiles, categories, IMERG matching (rule-based, no API key)
  quality  → Quality Agent        banned patterns, dead code, figure spec, notebook bloat
  git      → Git Agent            staged file hygiene, gitignore compliance, commit readiness

Used by the parent AI (Claude Code) to spread tasks without doing everything inline.

Usage:
  python scripts/agents/coordinator.py --task data    --action status
  python scripts/agents/coordinator.py --task science --action profile  --circle 5
  python scripts/agents/coordinator.py --task science --action stats
  python scripts/agents/coordinator.py --task science --action imerg    --circle 5
  python scripts/agents/coordinator.py --task quality --action all
  python scripts/agents/coordinator.py --task quality --action code
  python scripts/agents/coordinator.py --task git     --action status
  python scripts/agents/coordinator.py --task git     --action staged
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agents.data_agent    import run_task    as data_run
from scripts.agents.science_agent import (
    load_dataset, analyze_profile, format_profile_report,
    campaign_stats, category_summary, imerg_coverage,
)
from scripts.agents.quality_agent import run_checks  as quality_run
from scripts.agents.git_agent     import run_status, run_staged_check, run_summary, suggest_commit_message


# ---------------------------------------------------------------------------
# Routing table (for documentation and --help)
# ---------------------------------------------------------------------------

ROUTING = """
Model assignment (cost-aware):
  data    → Gemini 2.0 Flash Lite  (cheapest)  fallback: Flash → 2.5 Flash
  science → Rule-based core always; --interpret adds Haiku 4.5 (cheap Claude)
  quality → Pure Python             (no model)
  git     → Rule-based core always; --action suggest adds Haiku 4.5 (cheap Claude)

  data    [status | earthcare | notebooks | custom]   GEMINI_API_KEY required
  science [profile | category | stats | imerg]        no key; add --interpret for Haiku
  quality [all | code | figures | notebooks]          no key needed
  git     [status | staged | summary | suggest]       no key; suggest needs ANTHROPIC_API_KEY
"""


def main():
    parser = argparse.ArgumentParser(
        description="Coordinator — routes to specialised sub-agents",
        epilog=ROUTING,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        choices=["data", "science", "quality", "git"],
        required=True,
        help="Which agent to route to",
    )
    parser.add_argument(
        "--action",
        default=None,
        help="Action within the chosen agent (see routing table above)",
    )
    parser.add_argument(
        "--circle",
        type=int,
        default=None,
        help="Circle index (required for science --action profile/imerg)",
    )
    parser.add_argument(
        "--ask",
        type=str,
        default="",
        help="Custom question (used with --task data --action custom)",
    )
    parser.add_argument(
        "--interpret",
        action="store_true",
        help="Append Haiku 4.5 interpretation (--task science only)",
    )
    args = parser.parse_args()

    print(f"\n[Coordinator] task={args.task}  action={args.action or 'default'}")
    print("─" * 55)

    # ── Data Agent (Gemini) ──────────────────────────────────────────────────
    if args.task == "data":
        action = args.action or "status"
        result = data_run(action, extra=args.ask)
        print(result)

    # ── Science Agent (rule-based + optional Haiku) ──────────────────────────
    elif args.task == "science":
        from scripts.agents.science_agent import haiku_interpret
        action = args.action or "stats"
        ds = load_dataset()
        report = ""

        if action == "profile":
            if args.circle is None:
                print("ERROR: --action profile requires --circle N")
                sys.exit(1)
            info = analyze_profile(ds, args.circle)
            report = format_profile_report(info)

        elif action == "stats":
            report = campaign_stats(ds)

        elif action == "category":
            report = category_summary(ds)

        elif action == "imerg":
            if args.circle is None:
                print("ERROR: --action imerg requires --circle N")
                sys.exit(1)
            report = imerg_coverage(ds, args.circle)

        else:
            report = f"Unknown science action '{action}'. Choose: profile, stats, category, imerg"

        print(report)
        if args.interpret:
            print(haiku_interpret(report))

    # ── Quality Agent (rule-based) ───────────────────────────────────────────
    elif args.task == "quality":
        action = args.action or "all"
        print(quality_run(action))

    # ── Git Agent (rule-based) ───────────────────────────────────────────────
    elif args.task == "git":
        action = args.action or "status"
        if action == "status":
            print(run_status())
        elif action == "staged":
            print(run_staged_check())
        elif action == "summary":
            print(run_summary())
        elif action == "suggest":
            print(suggest_commit_message())
        else:
            print(f"Unknown git action '{action}'. Choose: status, staged, summary, suggest")


if __name__ == "__main__":
    main()
