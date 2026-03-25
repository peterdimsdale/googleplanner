#!/usr/bin/env python3
"""Resource planner for pension calc development using OR-Tools CP-SAT.

Usage:
    python3 planner.py example_project.yaml
    python3 planner.py myproject.yaml -o plan.html -v
"""

import argparse
import sys
from pathlib import Path

import yaml
from solver import solve_project
from report import generate_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimised resource planner — uses OR-Tools CP-SAT to schedule "
                    "tasks across your team and produces a self-contained HTML Gantt."
    )
    parser.add_argument("project", help="Project YAML file")
    parser.add_argument("-o", "--output", default="plan.html", help="Output HTML (default: plan.html)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose solver output")
    args = parser.parse_args()

    project_path = Path(args.project)
    if not project_path.exists():
        print(f"ERROR: file not found: {args.project}", file=sys.stderr)
        sys.exit(1)

    with open(project_path, encoding="utf-8") as f:
        project_data = yaml.safe_load(f)

    if args.verbose:
        p = project_data["project"]
        print(f"Project     : {p['name']}")
        print(f"Start date  : {p.get('start_date', 'today')}")
        print(f"Team        : {len(project_data['team'])} members")
        print(f"Tasks       : {len(project_data['tasks'])} tasks")
        print()

    result = solve_project(project_data, verbose=args.verbose)

    if result is None:
        print(
            "ERROR: Could not find a feasible schedule.\n"
            "       Check that every task has at least one team member with the required skill,\n"
            "       and that there are no circular dependencies.",
            file=sys.stderr,
        )
        sys.exit(1)

    html = generate_report(project_data, result)
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")

    print(f"Plan     : {output_path.resolve()}")
    print(f"Makespan : {result['makespan']} working days")
    print(f"Status   : {result['status']}")


if __name__ == "__main__":
    main()
