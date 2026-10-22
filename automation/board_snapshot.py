"""Stable source for Hermes's native monitor-script change detector.

Copy into the controller's scripts directory and select it as --monitor-script.
Reads the native research board through `hermes kanban list --json`; prints a
bounded JSON summary. No secrets, timestamps, model calls, writes or scheduling.
Hermes owns hashing, scheduling and delivery. Tests: tests/test_automation.py.
"""
import json
import subprocess

FIELDS = ("id", "title", "status", "assignee", "branch_name", "result", "last_failure_error")


def snapshot(tasks):
    # Ignore worker heartbeat/runtime bookkeeping so unchanged work does not
    # trigger inference every tick. Keep state transitions and actual outcomes.
    ordered = sorted(tasks, key=lambda task: task["id"])
    rows = [{key: (value[:600] if isinstance(value, str) else value)
             for key in FIELDS if (value := task.get(key)) is not None}
            for task in ordered[:200]]
    return json.dumps({"board": "research", "total": len(ordered),
        "truncated": len(ordered) > 200, "tasks": rows}, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    result = subprocess.run(["/opt/hermes/.venv/bin/hermes", "kanban", "--board", "research",
        "list", "--json"], check=True, capture_output=True, text=True, timeout=20)
    print(snapshot(json.loads(result.stdout)))
