"""CLI number forms, dictionary ordering and saved HTTP error bodies."""
import copy
import io
import unittest
from urllib.error import HTTPError
from comparison_plan import build_plan
from experiment_identity import resolve_run
from run_model_freeway import build_comparison_request, request_action
from test_experiment_config import recipe


class PlanConsistencyTests(unittest.TestCase):
    def test_cli_float_tick_has_exact_same_prompt_and_identity(self):
        c=recipe()
        self.assertEqual(resolve_run(c,'off',1,0),resolve_run(c,'off',1.0,0))
        self.assertEqual(build_comparison_request({},c,'off',1),
                         build_comparison_request({},c,'off',1.0))
        with self.assertRaises(ValueError):
            resolve_run(c,'off',True,0)
        with self.assertRaises(ValueError):
            resolve_run(c,'off',1,True)

    def test_reordered_config_does_not_change_plan(self):
        c=recipe()
        c['tick_intervals']=[1]
        reordered=copy.deepcopy(c)
        reordered['modes']={k:c['modes'][k] for k in reversed(c['modes'])}
        reordered['starts']={k:c['starts'][k] for k in reversed(c['starts'])}
        self.assertEqual(build_plan(c),build_plan(reordered))

    def test_server_error_body_is_preserved(self):
        def unavailable(*args,**kwargs):
            raise HTTPError('http://localhost',503,'unavailable',{},io.BytesIO(b'{"error":"busy"}'))
        response,error,_,_=request_action({},None,provider=unavailable)
        self.assertEqual(response,{'error':'busy'})
        self.assertIn('HTTPError',error)
