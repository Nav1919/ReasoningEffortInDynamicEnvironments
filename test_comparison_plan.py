"""Deterministic offline plans, coverage and balanced mode ordering."""
from collections import Counter
from pathlib import Path
import unittest
from comparison_plan import build_plan
from experiment_config import load_config
from test_experiment_config import recipe


class PlanTests(unittest.TestCase):
    def test_native_pilot_is_exactly_eighteen_matching_requests(self):
        c = load_config(Path(__file__).parent/'configs/native_effort_draft.json')
        plan = build_plan(c)
        self.assertEqual(len(plan['runs']),18)
        self.assertEqual(plan,build_plan(c))
        self.assertEqual(len({r['run_id'] for r in plan['runs']}),18)
        categories = Counter(r['situation']['category'] for r in plan['runs'])
        self.assertEqual(set(categories.values()),{6})
        for position in range(3):
            counts = Counter(r['resolved']['selected_mode'] for r in plan['runs'][position::3])
            self.assertEqual(set(counts.values()),{2})
        for offset in range(0,18,3):
            requests = [dict(r['request']) for r in plan['runs'][offset:offset+3]]
            for request in requests:
                request.pop('think')
            self.assertTrue(all(r==requests[0] for r in requests))

    def test_retries_and_live_plan_stay_in_development(self):
        c = recipe()
        c.update(design='live-starts-v1',tick_intervals=[1])
        first, retry = build_plan(c,1), build_plan(c,2)
        self.assertEqual(len(first['runs']),10)
        self.assertTrue({r['run_id'] for r in first['runs']}.isdisjoint(r['run_id'] for r in retry['runs']))
        self.assertTrue(all(r['start']['split']=='development' for r in first['runs']))
        self.assertTrue(all(r['status']=='planned' for r in first['runs']))
        self.assertEqual(first['comparison_id'],retry['comparison_id'])
