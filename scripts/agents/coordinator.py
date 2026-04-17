#!/usr/bin/env python3
"""
Coordinator — routes tasks to the right agent.

  data/file tasks    → Gemini (data_agent)
  science tasks      → Claude (science_agent)

Usage:
  python scripts/agents/coordinator.py --task data --action status
  python scripts/agents/coordinator.py --task data --action earthcare
  python scripts/agents/coordinator.py --task science --ask "why is circle 5 bottom-heavy?"
  python scripts/agents/coordinator.py --task science --ask "..." --circle 5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agents.data_agent import run_task as gemini_task
from scripts.agents.science_agent import ask_claude


DATA_TASKS    = ["status", "earthcare", "notebooks", "custom"]
SCIENCE_TASKS = ["interpret", "strategy", "methodology", "custom"]

ROUTING_GUIDE = """
Route to Gemini (data_agent) when:
  - checking file counts, sizes, missing data
  - scanning for EarthCARE remnants
  - checking notebook output bloat
  - any /g/data/ filesystem question

Route to Claude (science_agent) when:
  - interpreting omega profiles or categories
  - GMS computation strategy
  - ERA5 colocation decisions
  - writing methodology or results text
  - any question requiring RQ2 theoretical understanding
"""

def main():
    parser = argparse.ArgumentParser(
        description="Coordinator: routes to Gemini (data) or Claude (science)",
        epilog=ROUTING_GUIDE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task", choices=["data", "science"], required=True)
    parser.add_argument("--action", choices=DATA_TASKS, default="status",
                        help="Data agent action (used with --task data)")
    parser.add_argument("--ask", type=str, default="",
                        help="Question (used with --task science or --action custom)")
    parser.add_argument("--circle", type=int, default=None,
                        help="Circle index for science context")
    args = parser.parse_args()

    if args.task == "data":
        print(f"\n[Coordinator] → Gemini Data Agent  (task: {args.action})")
        print("─" * 50)
        result = gemini_task(args.action, extra=args.ask)

    elif args.task == "science":
        if not args.ask:
            parser.error("--task science requires --ask")
        print(f"\n[Coordinator] → Claude Science Agent")
        print("─" * 50)
        result = ask_claude(args.ask, circle_idx=args.circle)

    print(result)


if __name__ == "__main__":
    main()
