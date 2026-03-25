"""OR-Tools CP-SAT solver for resource scheduling.

Task durations are specified as working days for a full-time resource.
If a team member has capacity < 1.0 (e.g. 0.8 = 4 days/week), their
effective duration is scaled up automatically: ceil(duration / capacity).

The solver assigns tasks, respects skill requirements and dependencies,
prevents double-booking, and minimises total project duration (makespan).
"""

import math
from typing import Optional
from ortools.sat.python import cp_model


def effective_days(base_duration: int, capacity: float) -> int:
    """Elapsed working days for a task given a person's fractional availability."""
    return max(1, math.ceil(base_duration / capacity))


def solve_project(data: dict, verbose: bool = False) -> Optional[dict]:
    """Solve the resource scheduling problem.

    Returns a dict with 'makespan', 'status', and 'tasks' (each annotated
    with 'start', 'end', 'duration', 'base_duration', 'assigned_to'),
    or None if infeasible / no skill match found.
    """
    model = cp_model.CpModel()

    team  = data["team"]
    tasks = data["tasks"]

    # Skill lookup
    person_skills = {p["name"]: set(p.get("skills", [])) for p in team}

    # Per-person capacity (default 1.0 = full time)
    person_capacity = {p["name"]: float(p.get("capacity", 1.0)) for p in team}

    if verbose:
        print("Capacities  :")
        for pname, cap in person_capacity.items():
            print(f"  {pname}: {cap}")
        print()

    # ── Pre-compute effective duration for every eligible (task, person) pair ─

    task_person_dur: dict[tuple[str, str], int] = {}
    for task in tasks:
        tid      = task["id"]
        base_dur = task["duration"]
        req_skill = task.get("requires_skill")
        eligible = 0
        for person in team:
            pname = person["name"]
            if req_skill is None or req_skill in person_skills[pname]:
                task_person_dur[(tid, pname)] = effective_days(
                    base_dur, person_capacity[pname]
                )
                eligible += 1
        if eligible == 0:
            if verbose:
                print(f"ERROR: No eligible person for task '{tid}' "
                      f"(requires_skill: {req_skill})")
            return None

    # Horizon: sum of worst-case durations per task
    horizon = sum(
        max(task_person_dur.get((t["id"], p["name"]), 0) for p in team)
        for t in tasks
    ) + 10

    if verbose:
        print(f"Horizon     : {horizon} working days")

    # ── Decision variables ────────────────────────────────────────────────────

    task_starts: dict[str, cp_model.IntVar] = {}
    task_ends: dict[str, cp_model.IntVar] = {}   # actual end depends on assignment

    for task in tasks:
        tid = task["id"]
        task_starts[tid] = model.new_int_var(0, horizon, f"s_{tid}")
        task_ends[tid]   = model.new_int_var(0, horizon, f"e_{tid}")

    # ── Assignment variables + per-person optional intervals ─────────────────

    assignments: dict[tuple[str, str], cp_model.IntVar] = {}
    person_opt_intervals: dict[str, list] = {p["name"]: [] for p in team}

    for task in tasks:
        tid = task["id"]
        for person in team:
            pname = person["name"]
            if (tid, pname) not in task_person_dur:
                continue

            dur      = task_person_dur[(tid, pname)]
            assigned = model.new_bool_var(f"a_{tid}__{pname}")
            assignments[(tid, pname)] = assigned

            # End time specific to this (task, person) pairing
            ep = model.new_int_var(0, horizon, f"ep_{tid}__{pname}")
            model.add(ep == task_starts[tid] + dur)

            # Optional interval — only active when this person is assigned
            opt_iv = model.new_optional_interval_var(
                task_starts[tid], dur, ep, assigned, f"oi_{tid}__{pname}"
            )
            person_opt_intervals[pname].append(opt_iv)

            # When assigned, pin the shared task_end to this person's end time
            model.add(task_ends[tid] == ep).only_enforce_if(assigned)

    # ── Constraints ──────────────────────────────────────────────────────────

    # Exactly one eligible person per task
    for task in tasks:
        tid = task["id"]
        eligible_vars = [v for (t, _), v in assignments.items() if t == tid]
        model.add_exactly_one(eligible_vars)

    # No two tasks overlap for the same person
    for pname, intervals in person_opt_intervals.items():
        if len(intervals) > 1:
            model.add_no_overlap(intervals)

    # Dependency constraints: successor starts after predecessor ends
    task_map = {t["id"]: t for t in tasks}
    for task in tasks:
        tid = task["id"]
        for dep_id in task.get("depends_on", []):
            if dep_id not in task_map:
                if verbose:
                    print(f"WARNING: Unknown dependency '{dep_id}' for task '{tid}'")
                continue
            model.add(task_starts[tid] >= task_ends[dep_id])

    # ── Objective: minimise makespan ─────────────────────────────────────────

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, list(task_ends.values()))
    model.minimize(makespan)

    # ── Solve ─────────────────────────────────────────────────────────────────

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    if verbose:
        solver.parameters.log_search_progress = True

    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if verbose:
            print(f"Solver status: {solver.status_name(status)}")
        return None

    makespan_val = solver.value(makespan)

    if verbose:
        print(f"Solver status : {solver.status_name(status)}")
        print(f"Makespan      : {makespan_val} working days")

    # ── Extract solution ──────────────────────────────────────────────────────

    result_tasks = []
    for task in tasks:
        tid       = task["id"]
        start_val = solver.value(task_starts[tid])
        end_val   = solver.value(task_ends[tid])

        assigned_to   = None
        sched_days    = None
        for person in team:
            pname = person["name"]
            if (tid, pname) in assignments and solver.value(assignments[(tid, pname)]):
                assigned_to = pname
                sched_days  = task_person_dur[(tid, pname)]
                break

        result_tasks.append({
            "id":            tid,
            "name":          task["name"],
            "scheme":        task.get("scheme", "General"),
            "type":          task.get("type", "dev"),
            "base_duration": task["duration"],   # full-time estimate from YAML
            "duration":      sched_days,         # actual elapsed days after capacity scaling
            "start":         start_val,
            "end":           end_val,
            "assigned_to":   assigned_to,
            "depends_on":    task.get("depends_on", []),
        })

    result_tasks.sort(key=lambda t: (t["start"], t["name"]))

    return {
        "makespan": makespan_val,
        "status":   solver.status_name(status),
        "tasks":    result_tasks,
    }
