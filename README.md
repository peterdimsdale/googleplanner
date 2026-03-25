# Google OR-Tools Resource Planner

Optimised resource scheduling for pension calc development projects.

You define your team, schemes, and tasks in a spreadsheet. The solver assigns work to people, respects skill requirements and task dependencies, prevents double-booking, and finds the schedule that finishes the project in the fewest working days. Output is a self-contained HTML Gantt chart.

Powered by [Google OR-Tools CP-SAT](https://github.com/google/or-tools) — a constraint programming solver that finds the mathematically optimal assignment, not just a reasonable one.

---

## How it works

The solver treats resource planning as a constraint satisfaction problem:

- Each task has a **duration** (working days) and a **required skill**
- Each team member has a set of **skills** and a **capacity** (fraction of full time)
- If a person's capacity is less than 1.0, their effective duration is scaled up automatically: `ceil(duration / capacity)` — so a 5-day task takes 7 elapsed days for someone at 0.8 capacity
- **Dependencies** between tasks are enforced: a task cannot start until all its predecessors have finished
- No person is double-booked — the solver guarantees this as a hard constraint
- The objective is to **minimise makespan** (total project duration)

---

## Setup

```bash
cd googleplanner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Workflow

### Step 1 — get the CSV template

```bash
python3 csv_to_yaml.py --template
# → tasks_template.csv
```

Open `tasks_template.csv` in Excel. It has these columns:

| Column | Description |
|---|---|
| `id` | Unique task identifier, no spaces — e.g. `schemeabc_transfer_value` |
| `name` | Display name shown in the Gantt — e.g. `SchemeABC - Transfer Value Calc` |
| `scheme` | Scheme name, used for colour-coding — e.g. `SchemeABC` |
| `type` | Task category label — e.g. `spec`, `calc_coding`, `testing`, `uat` |
| `duration` | Estimated working days for a full-time resource |
| `requires_skill` | Skill needed to do this task — must match a skill in the team |
| `depends_on` | Semicolon-separated IDs of tasks that must finish first — e.g. `schemeabc_spec;schemeabc_calc1`. Leave blank if none. |

Example rows:

```
id,name,scheme,type,duration,requires_skill,depends_on
schemeabc_spec,SchemeABC - Spec Review,SchemeABC,spec,3,spec_review,
schemeabc_retval,SchemeABC - Revaluation Calc,SchemeABC,calc_coding,5,senior_dev,schemeabc_spec
schemeabc_tv,SchemeABC - Transfer Value Calc,SchemeABC,calc_coding,3,senior_dev,schemeabc_spec
schemeabc_test,SchemeABC - Testing,SchemeABC,testing,3,testing,schemeabc_retval;schemeabc_tv
schemeabc_uat,SchemeABC - UAT,SchemeABC,uat,2,uat,schemeabc_test
```

### Step 2 — convert to YAML

```bash
python3 csv_to_yaml.py tasks.csv -o project.yaml
```

This validates every row, checks all `depends_on` IDs exist, and writes `project.yaml`.

### Step 3 — edit the team

Open `project.yaml` and replace the placeholder team with your real people:

```yaml
team:
  - name: Sarah
    skills: [senior_dev, spec_review]
    capacity: 1.0

  - name: Marcus
    skills: [senior_dev]
    capacity: 1.0

  - name: Priya
    skills: [developer, spec_review]
    capacity: 0.8          # 4 days/week — durations scaled automatically

  - name: Tom
    skills: [testing]
    capacity: 1.0

  - name: UAT Resource     # replace when known
    skills: [uat]
    capacity: 0.5
```

Skills are free-form strings — the only rule is that a task's `requires_skill` must match at least one skill in the team list.

### Step 4 — run the planner

```bash
python3 planner.py project.yaml -o plan.html
```

Open `plan.html` in any browser. The report is self-contained — no server needed.

---

## Files

| File | Purpose |
|---|---|
| `csv_to_yaml.py` | Converts your task spreadsheet to a YAML project file |
| `planner.py` | CLI entry point — reads YAML, runs solver, writes HTML |
| `solver.py` | OR-Tools CP-SAT model |
| `report.py` | HTML Gantt chart generator |
| `example_project.yaml` | Hand-written example with 3 schemes and 4 team members |
| `tasks_template.csv` | Blank CSV template to fill in |
| `test_planner.py` | Test suite — run with `python3 test_planner.py` |
| `requirements.txt` | `ortools`, `pyyaml` |

---

## CLI reference

### `csv_to_yaml.py`

```
python3 csv_to_yaml.py tasks.csv [options]

  -o, --output FILE        Output YAML file (default: project.yaml)
  --template               Write a blank CSV template and exit
  --project-name NAME      Project name written into the YAML
  --start-date YYYY-MM-DD  Project start date (default: today)
  -v, --verbose            Print each task and its dependencies
```

### `planner.py`

```
python3 planner.py project.yaml [options]

  -o, --output FILE        Output HTML file (default: plan.html)
  -v, --verbose            Print solver progress and schedule
```

---

## The HTML report

The output Gantt chart shows:

- **One row per team member** — tasks appear as coloured blocks on a timeline
- **Colour-coded by scheme** — each scheme gets a distinct colour
- **Hover tooltip** — shows task name, scheme, assigned person, start/end dates, and duration (with capacity note if the person is part-time)
- **Tasks table** — full list sorted by start date
- **Stats** — makespan, project start/end, scheme count, team size

---

## Tips

**Parallel calcs within a scheme**
If multiple calcs all depend only on the spec review (not on each other), the solver can assign them to different developers and run them in parallel — automatically.

**Part-time UAT testers**
Set `capacity: 0.5` for admin team members doing UAT on top of their day job. Enter `duration` as if they were full time; the elapsed days are calculated for you.

**Multiple UAT testers**
Add more than one person with the `uat` skill and the solver will distribute UAT tasks across them to minimise the schedule.

**Dependency on multiple predecessors**
Use semicolons in the `depends_on` cell: `schemeabc_calc1;schemeabc_calc2;schemeabc_calc3`. The task will not start until all of them are complete.

**Validating your CSV**
Run `csv_to_yaml.py` before editing the team section — it will catch missing columns, bad durations, and broken dependency references before the solver ever runs.

---

## Tests

```bash
source venv/bin/activate
python3 test_planner.py
```
