#!/usr/bin/env python3
"""Convert a task CSV to a planner-ready YAML project file.

Each row in the CSV becomes exactly one task in the YAML.
No tasks are auto-generated — what you put in is what you get.

CSV columns (order doesn't matter, headers required):
    id              e.g.  schemeabc_transfer_value_calc
    name            e.g.  SchemeABC - Transfer Value Calc
    scheme          e.g.  SchemeABC
    type            e.g.  calc_coding
    duration        Working days as a whole number, e.g.  3
    requires_skill  e.g.  senior_dev
    depends_on      Semicolon-separated task IDs, e.g.  schemeabc_spec;schemeabc_other
                    Leave blank if no dependencies.

Usage:
    # Generate a blank CSV template:
    python3 csv_to_yaml.py --template

    # Convert your CSV to YAML:
    python3 csv_to_yaml.py tasks.csv -o project.yaml
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

import yaml


# ── Template ──────────────────────────────────────────────────────────────────

TEMPLATE_ROWS = [
    ["schemeabc_spec",                  "SchemeABC - Spec Review",          "SchemeABC", "spec",        3, "spec_review", ""],
    ["schemeabc_transfer_value_calc",   "SchemeABC - Transfer Value Calc",  "SchemeABC", "calc_coding", 3, "senior_dev",  "schemeabc_spec"],
    ["schemeabc_retirement_calc",       "SchemeABC - Retirement Calc",      "SchemeABC", "calc_coding", 5, "senior_dev",  "schemeabc_spec"],
    ["schemeabc_gmp_revaluation",       "SchemeABC - GMP Revaluation",      "SchemeABC", "calc_coding", 8, "senior_dev",  "schemeabc_spec"],
    ["schemeabc_test",                  "SchemeABC - Testing",              "SchemeABC", "testing",     3, "testing",     "schemeabc_transfer_value_calc;schemeabc_retirement_calc;schemeabc_gmp_revaluation"],
    ["schemeabc_uat",                   "SchemeABC - UAT",                  "SchemeABC", "uat",         2, "uat",         "schemeabc_test"],
    ["schemedef_spec",                  "SchemeDEF - Spec Review",          "SchemeDEF", "spec",        2, "spec_review", ""],
    ["schemedef_cetv_calc",             "SchemeDEF - CETV Calc",            "SchemeDEF", "calc_coding", 6, "senior_dev",  "schemedef_spec"],
    ["schemedef_test",                  "SchemeDEF - Testing",              "SchemeDEF", "testing",     3, "testing",     "schemedef_cetv_calc"],
    ["schemedef_uat",                   "SchemeDEF - UAT",                  "SchemeDEF", "uat",         2, "uat",         "schemedef_test"],
]

HEADERS = ["id", "name", "scheme", "type", "duration", "requires_skill", "depends_on"]


def write_template(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for row in TEMPLATE_ROWS:
            writer.writerow(row)
    print(f"Template written to {path.resolve()}")
    print("Fill it in and run:  python3 csv_to_yaml.py tasks.csv -o project.yaml")


# ── Reader ────────────────────────────────────────────────────────────────────

def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    tasks  = []
    errors = []

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return tasks, ["CSV appears to be empty"]

        # Normalise header names
        norm = {h.strip().lower() for h in reader.fieldnames}
        missing = set(HEADERS) - norm
        if missing:
            return tasks, [
                f"Missing columns: {', '.join(sorted(missing))}. "
                f"Found: {', '.join(sorted(norm))}"
            ]

        for i, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items()}

            # Skip blank rows
            if not any(row.values()):
                continue

            tid      = row["id"]
            name     = row["name"]
            scheme   = row["scheme"]
            typ      = row["type"]
            dur      = row["duration"]
            skill    = row["requires_skill"]
            deps_raw = row["depends_on"]

            if not tid:
                errors.append(f"Row {i}: missing id")
                continue
            if not name:
                errors.append(f"Row {i} ({tid}): missing name")
                continue
            if not scheme:
                errors.append(f"Row {i} ({tid}): missing scheme")
                continue
            if not typ:
                errors.append(f"Row {i} ({tid}): missing type")
                continue
            if not dur.isdigit() or int(dur) < 1:
                errors.append(f"Row {i} ({tid}): duration must be a positive whole number (got '{dur}')")
                continue
            if not skill:
                errors.append(f"Row {i} ({tid}): missing requires_skill")
                continue

            # Parse depends_on — semicolon-separated, strip whitespace
            depends_on = [d.strip() for d in deps_raw.split(";") if d.strip()]

            tasks.append({
                "id":             tid,
                "name":           name,
                "scheme":         scheme,
                "type":           typ,
                "duration":       int(dur),
                "requires_skill": skill,
                "depends_on":     depends_on,
            })

    return tasks, errors


def validate_dependencies(tasks: list[dict]) -> list[str]:
    """Check that every depends_on ID actually exists in the task list."""
    known = {t["id"] for t in tasks}
    errors = []
    for task in tasks:
        for dep in task.get("depends_on", []):
            if dep not in known:
                errors.append(f"Task '{task['id']}' depends_on '{dep}' which doesn't exist")
    return errors


# ── YAML writer ───────────────────────────────────────────────────────────────

class _Dumper(yaml.Dumper):
    pass


def _list_rep(dumper, data):
    # Write string-only lists inline; others as block
    if data and all(isinstance(i, str) for i in data):
        return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=False)


_Dumper.add_representer(list, _list_rep)


def write_yaml(project: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Generated by csv_to_yaml.py — edit team members before running planner.py\n\n")
        yaml.dump(project, f, Dumper=_Dumper, allow_unicode=True,
                  sort_keys=False, default_flow_style=False, indent=2)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a task CSV to a planner-ready YAML file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("csv_file", nargs="?",
        help="Input CSV file (omit when using --template)")
    parser.add_argument("-o", "--output", default="project.yaml",
        help="Output YAML file (default: project.yaml)")
    parser.add_argument("--template", action="store_true",
        help="Write a blank CSV template and exit")
    parser.add_argument("--template-out", default="tasks_template.csv",
        help="Filename for --template output (default: tasks_template.csv)")
    parser.add_argument("--project-name", default="Pension Calc Development",
        help="Project name")
    parser.add_argument("--start-date", default=date.today().isoformat(),
        help="Project start date YYYY-MM-DD (default: today)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.template:
        write_template(Path(args.template_out))
        return

    if not args.csv_file:
        parser.error("csv_file is required (or use --template to generate one)")

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"ERROR: file not found: {args.csv_file}", file=sys.stderr)
        sys.exit(1)

    tasks, errors = read_csv(csv_path)

    if errors:
        print(f"Found {len(errors)} error(s) in {args.csv_file}:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    dep_errors = validate_dependencies(tasks)
    if dep_errors:
        print(f"Found {len(dep_errors)} dependency error(s):")
        for e in dep_errors:
            print(f"  {e}")
        sys.exit(1)

    project = {
        "project": {
            "name":       args.project_name,
            "start_date": args.start_date,
        },
        "team": [
            {"name": "Developer 1", "skills": ["senior_dev", "spec_review"], "capacity": 1.0},
            {"name": "Developer 2", "skills": ["senior_dev"],               "capacity": 1.0},
            {"name": "Tester",      "skills": ["testing"],                   "capacity": 1.0},
            {"name": "UAT Resource","skills": ["uat"],                       "capacity": 0.5},
        ],
        "tasks": tasks,
    }

    output_path = Path(args.output)
    write_yaml(project, output_path)

    schemes = len({t["scheme"] for t in tasks})
    print(f"Tasks    : {len(tasks)}")
    print(f"Schemes  : {schemes}")
    print(f"Output   : {output_path.resolve()}")
    if args.verbose:
        print()
        for t in tasks:
            deps = ", ".join(t["depends_on"]) if t["depends_on"] else "—"
            print(f"  {t['id']:45s}  {t['duration']:2d}d  deps: {deps}")

    print()
    print("Next: edit the 'team' section in the YAML, then run:")
    print(f"  python3 planner.py {output_path}")


if __name__ == "__main__":
    main()
