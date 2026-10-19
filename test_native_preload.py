"""Check native pilot question counts without model/network access."""
import json
from pathlib import Path
import tempfile
import unittest
from comparison_execution import execute_plan
from comparison_plan import build_plan
from experiment_config import load_config, validate_config
from test_experiment_config import ROOT, recipe


class NativePreloadTests(unittest.TestCase):
    def native_recipe(self):
        c=load_config(ROOT/'configs/native_effort_draft.json')
        c.update(schema_version=2,warmup_policy='load_once')
        return c

    def test_single_load_and_exactly_eighteen_questions(self):
        calls=[]
        def provider(endpoint,payload,timeout):
            calls.append((endpoint,payload))
            if endpoint=='generate':
                self.assertEqual(payload['prompt'],'')
                self.assertNotIn('messages',payload)
                return {'done':True,'done_reason':'load'}
            return {'message':{'content':'U'},'done_reason':'stop','eval_count':1}
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'plan.json').write_text(json.dumps(build_plan(self.native_recipe())))
            result=execute_plan(folder,limit=18,provider=provider,
                model_check=lambda c:{},source_check=lambda c:{})
            self.assertEqual(result['status'],'complete')
            self.assertEqual([e for e,p in calls].count('generate'),1)
            self.assertEqual([e for e,p in calls].count('chat'),18)
            records=[json.loads((folder/r['log']).read_text()) for r in result['runs']]
            self.assertEqual(records[0]['warmup']['kind'],'model_load_no_text')
            self.assertTrue(all(r['warmup']['kind']=='reuse_preloaded_model' for r in records[1:]))

    def test_old_recipes_stay_identical_and_policy_is_explicit(self):
        c=recipe()
        self.assertEqual(validate_config(c),c)
        self.assertNotIn('warmup_policy',validate_config(c))
        self.assertEqual(validate_config(self.native_recipe())['warmup_policy'],'load_once')
        for change in [{'warmup_policy':'skip'}, {'design':'live-starts-v1'}]:
            c=self.native_recipe()
            c.update(change)
            with self.assertRaises(ValueError):
                validate_config(c)

    def test_longer_load_does_not_extend_answer_timeout(self):
        c=self.native_recipe()
        c.update(schema_version=3,preload_timeout=600)
        timeouts=[]
        def provider(endpoint,payload,timeout):
            timeouts.append((endpoint,timeout))
            if endpoint=='generate':
                return {'done_reason':'load'}
            return {'message':{'content':'S'},'done_reason':'stop'}
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'plan.json').write_text(json.dumps(build_plan(c,attempt=2)))
            execute_plan(folder,limit=1,provider=provider,model_check=lambda c:{},source_check=lambda c:{})
        self.assertEqual(timeouts,[('generate',600),('chat',180)])
        for value in [0,True,float('inf')]:
            c['preload_timeout']=value
            with self.assertRaises(ValueError):
                validate_config(c)
