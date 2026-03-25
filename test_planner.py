"""Tests for the OR-Tools CP-SAT resource planner."""

import math
import unittest
from solver import solve_project, effective_days


def _base_project():
    return {
        "project": {"name": "Test", "start_date": "2026-03-24"},
        "team": [
            {"name": "Alice", "skills": ["dev"]},
            {"name": "Bob",   "skills": ["dev", "testing"]},
        ],
        "tasks": [
            {"id": "t1", "name": "Task 1", "scheme": "S1", "duration": 3, "requires_skill": "dev"},
            {"id": "t2", "name": "Task 2", "scheme": "S1", "duration": 2, "requires_skill": "dev"},
            {"id": "t3", "name": "Task 3", "scheme": "S1", "duration": 2, "requires_skill": "testing"},
        ],
    }


class TestEffectiveDays(unittest.TestCase):

    def test_full_time(self):
        self.assertEqual(effective_days(5, 1.0), 5)

    def test_part_time_rounds_up(self):
        self.assertEqual(effective_days(5, 0.8), 7)   # ceil(5 / 0.8) = 7
        self.assertEqual(effective_days(4, 0.5), 8)   # ceil(4 / 0.5) = 8
        self.assertEqual(effective_days(3, 0.6), 5)   # ceil(3 / 0.6) = 5

    def test_minimum_one_day(self):
        self.assertEqual(effective_days(1, 1.0), 1)
        self.assertGreaterEqual(effective_days(1, 0.1), 1)


class TestSolver(unittest.TestCase):

    def test_basic_solve(self):
        result = solve_project(_base_project())
        self.assertIsNotNone(result, "Expected a feasible solution")
        self.assertGreater(result["makespan"], 0)
        self.assertEqual(len(result["tasks"]), 3)

    def test_result_has_base_and_effective_duration(self):
        result = solve_project(_base_project())
        self.assertIsNotNone(result)
        for task in result["tasks"]:
            self.assertIn("base_duration", task)
            self.assertIn("duration", task)

    def test_capacity_scales_duration(self):
        """A 0.5-capacity person should take twice as many elapsed days."""
        data = {
            "project": {"name": "T"},
            "team": [
                {"name": "PartTimer", "skills": ["dev"], "capacity": 0.5},
            ],
            "tasks": [
                {"id": "t1", "name": "Task", "scheme": "S1",
                 "duration": 4, "requires_skill": "dev"},
            ],
        }
        result = solve_project(data)
        self.assertIsNotNone(result)
        t = result["tasks"][0]
        self.assertEqual(t["base_duration"], 4)
        self.assertEqual(t["duration"], 8)   # ceil(4 / 0.5) = 8

    def test_full_capacity_unchanged(self):
        """A 1.0-capacity person's duration should equal the base duration."""
        result = solve_project(_base_project())
        self.assertIsNotNone(result)
        for task in result["tasks"]:
            self.assertEqual(task["duration"], task["base_duration"])

    def test_all_tasks_assigned(self):
        result = solve_project(_base_project())
        self.assertIsNotNone(result)
        for task in result["tasks"]:
            self.assertIsNotNone(task["assigned_to"], f"Task {task['id']} has no assignment")

    def test_dependency_respected(self):
        data = _base_project()
        data["tasks"][1]["depends_on"] = ["t1"]
        result = solve_project(data)
        self.assertIsNotNone(result)
        t1 = next(t for t in result["tasks"] if t["id"] == "t1")
        t2 = next(t for t in result["tasks"] if t["id"] == "t2")
        self.assertGreaterEqual(t2["start"], t1["end"],
            f"t2 starts at {t2['start']} before t1 ends at {t1['end']}")

    def test_no_overlap_per_person(self):
        result = solve_project(_base_project())
        self.assertIsNotNone(result)
        by_person: dict[str, list] = {}
        for t in result["tasks"]:
            by_person.setdefault(t["assigned_to"], []).append((t["start"], t["end"]))
        for person, intervals in by_person.items():
            intervals.sort()
            for a, b in zip(intervals, intervals[1:]):
                self.assertLessEqual(a[1], b[0],
                    f"{person} has overlapping tasks: {a} and {b}")

    def test_skill_only_assigned_correctly(self):
        """Only Bob has 'testing', so t3 must go to Bob."""
        result = solve_project(_base_project())
        self.assertIsNotNone(result)
        t3 = next(t for t in result["tasks"] if t["id"] == "t3")
        self.assertEqual(t3["assigned_to"], "Bob",
            f"t3 requires 'testing', expected Bob but got {t3['assigned_to']}")

    def test_infeasible_no_skill_match(self):
        data = _base_project()
        data["tasks"].append({
            "id": "tx", "name": "Mystery Task", "scheme": "S1",
            "duration": 1, "requires_skill": "magic",
        })
        result = solve_project(data)
        self.assertIsNone(result, "Expected None when no team member has required skill")

    def test_chain_dependency(self):
        """A → B → C: each must start after the previous ends."""
        data = _base_project()
        data["tasks"][1]["depends_on"] = ["t1"]
        data["tasks"][2]["depends_on"] = ["t2"]
        data["tasks"][2]["requires_skill"] = "dev"
        result = solve_project(data)
        self.assertIsNotNone(result)
        tasks_by_id = {t["id"]: t for t in result["tasks"]}
        self.assertGreaterEqual(tasks_by_id["t2"]["start"], tasks_by_id["t1"]["end"])
        self.assertGreaterEqual(tasks_by_id["t3"]["start"], tasks_by_id["t2"]["end"])

    def test_makespan_equals_max_end(self):
        result = solve_project(_base_project())
        self.assertIsNotNone(result)
        max_end = max(t["end"] for t in result["tasks"])
        self.assertEqual(result["makespan"], max_end)

    def test_example_project(self):
        """Smoke test the full example_project.yaml."""
        import yaml
        from pathlib import Path
        yaml_path = Path(__file__).parent / "example_project.yaml"
        if not yaml_path.exists():
            self.skipTest("example_project.yaml not found")
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        result = solve_project(data)
        self.assertIsNotNone(result, "Example project should be feasible")
        self.assertGreater(result["makespan"], 0)
        print(f"\n  Example project makespan: {result['makespan']} working days")
        print(f"  Status: {result['status']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
