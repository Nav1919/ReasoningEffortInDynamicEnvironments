# These tests use tiny traffic scenes with answers we can check by hand.
# They also compare car cells with the installed game's own collision geometry.
# Run python -m unittest test_stage_a -v; no tests need a model or network connection.
import copy
import json
import unittest
import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from stage_a import FORMATS, distance, make_prompt, make_questions, read_scene, render_scene, score_answer


def example_observation():
    return {'state': {'player_states': 3, 'game_turn': 5, 'car_states': [
        [3, 8, 'right', 4, 11],
        [4, -8, 'left', 4, 11],
        [2, 48, 'right', 24, 23],
    ]}}


class SceneTests(unittest.TestCase):
    def test_phase_and_body_cells(self):
        scene = read_scene(example_observation())
        self.assertEqual(scene['cars'][0]['occupied_x'], [0])
        self.assertEqual(scene['cars'][1]['occupied_x'], [0])
        self.assertEqual(scene['cars'][2]['occupied_x'], [48, 36])
        self.assertEqual(distance(scene['cars'][1], scene), 12)

    def test_public_fields_only_and_no_mutation(self):
        observation = example_observation()
        observation['answer'] = 'SECRET ANSWER'
        before = copy.deepcopy(observation)
        scene = read_scene(observation)
        self.assertNotIn('SECRET', json.dumps(scene))
        self.assertEqual(observation, before)

    def test_absent_and_invalid_cars(self):
        observation = example_observation()
        observation['state']['car_states'].insert(0, [1, None, None, None, None])
        self.assertEqual(read_scene(observation)['cars'][0]['id'], 'C01')
        observation['state']['car_states'][0][3] = 4
        with self.assertRaises(ValueError):
            read_scene(observation)

    def test_cells_match_simulator(self):
        from freeway_study import recreate
        for start in range(5):
            game, _ = recreate(start, '')
            for tick in range(12):
                scene = read_scene(game.observe())
                physical = sorted([c for c in game.cars if c[3] is not None], key=lambda c: 9-c[1])
                for shown, actual in zip(scene['cars'], physical):
                    head, lane, timer, speed, length = actual
                    cells = [12*(head + offset*(-1 if speed > 0 else 1)-4) for offset in range(length)]
                    self.assertEqual(shown['occupied_x'], cells)
                    self.assertEqual(shown['lane'], 9-lane)
                game.step('S')


class RepresentationTests(unittest.TestCase):
    def test_all_formats_keep_every_car_and_do_not_mutate(self):
        scene = read_scene(example_observation())
        before = copy.deepcopy(scene)
        for name in FORMATS:
            text = render_scene(scene, name)
            self.assertEqual(text, render_scene(scene, name))
            for car in scene['cars']:
                self.assertIn(car['id'], text)
                self.assertIn(str(car['head_x']), text)
                self.assertIn(car['direction'], text)
                self.assertIn(str(car['speed']), text)
                self.assertIn(str(car['length']), text)
        self.assertEqual(scene, before)
        self.assertEqual(json.loads(render_scene(scene, 'json')), scene)

    def test_grid_marks_overlap_and_empty_lanes(self):
        text = render_scene(read_scene(example_observation()), 'grid')
        self.assertIn('3 | . | . | . | . | C00,P | . | . | . | .', text)
        self.assertIn('9 | . | . | . | . | . | . | . | . | .', text)

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            render_scene(read_scene(example_observation()), 'picture')


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.scene = read_scene(example_observation())
        self.questions = make_questions(self.scene, 473)

    def test_known_answers_and_same_prompts(self):
        answers = {q['probe']: q['answer'] for q in self.questions}
        self.assertEqual(answers['nearest'], {'cars': ['C00']})
        self.assertEqual(answers['counting'], {'count': 2})
        self.assertEqual(self.questions, make_questions(self.scene, 473))
        for question in self.questions:
            for name in FORMATS:
                prompt = make_prompt(render_scene(self.scene, name), question)
                self.assertIn(question['text'], prompt)
                self.assertTrue(prompt.endswith(question['schema']))
                self.assertNotIn('safe_actions', prompt)

    def test_perfect_and_malformed_answers(self):
        for question in self.questions:
            self.assertTrue(score_answer(question, json.dumps(question['answer']))['correct'])
            for bad in ('bad', '{}', 'null', '[]'):
                self.assertFalse(score_answer(question, bad)['valid'])
        occupancy = self.questions[0]
        self.assertFalse(score_answer(occupancy, '{"occupied": 1}')['valid'])

    def test_ties_empty_scene_and_signed_error(self):
        scene = copy.deepcopy(self.scene)
        scene['cars'][0]['lane'] = 2
        nearest = make_questions(scene, 0)[1]
        self.assertEqual(nearest['answer']['cars'], ['C00', 'C01'])
        self.assertTrue(score_answer(nearest, '{"cars": ["C01", "C00"]}')['correct'])
        self.assertFalse(score_answer(nearest, '{"cars": ["C00", "C00"]}')['valid'])
        scene['cars'] = []
        questions = make_questions(scene, 0)
        self.assertEqual(len(questions), 3)
        self.assertEqual(questions[1]['answer'], {'cars': []})
        question = dict(probe='localization', answer={'head_x': 8})
        result = score_answer(question, '{"head_x": 5}')
        self.assertEqual((result['signed_error'], result['absolute_error']), (-3, 3))

    def test_action_ties(self):
        question = dict(probe='action', answer={'action': ['U', 'S']}, safe_actions=['U', 'S', 'D'])
        self.assertTrue(score_answer(question, '{"action": "S"}')['correct'])
        result = score_answer(question, '{"action": "D"}')
        self.assertTrue(result['safe'])
        self.assertFalse(result['correct'])
        self.assertFalse(score_answer(question, '{"action": ""}')['valid'])


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from freeway_scenarios import generate
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.bank = cls.root/'bank.json'
        generate(cls.bank, count=4, selectors=1, ticks=3, horizon=3)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def prepare_run(self, folder, count=4):
        from run_stage_a import ROOT, prepare
        config = json.loads((ROOT/'configs/stage_a.json').read_text())
        config.update(bank=str(self.bank), count=count, sampling_seeds=[0], bootstrap_samples=100)
        path = folder.parent/(folder.name + '-config.json')
        path.write_text(json.dumps(config))
        return prepare(path, folder)

    def test_selection_questions_and_resume(self):
        from run_stage_a import execute, read_rows
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'run'
            other = Path(tmp)/'other'
            manifest = self.prepare_run(folder)
            self.prepare_run(other)
            self.assertEqual(manifest['request_count'], 144)
            self.assertEqual((folder/'requests.jsonl').read_bytes(), (other/'requests.jsonl').read_bytes())
            requests = read_rows(folder/'requests.jsonl')
            self.assertNotIn('answer', requests[0])
            self.assertNotIn('safe_actions', requests[0])
            self.assertEqual(execute(folder, 'perfect', 7)['added'], 7)
            self.assertEqual(execute(folder, 'perfect')['added'], 137)
            self.assertEqual(execute(folder, 'perfect')['added'], 0)
            rows = read_rows(folder/'responses.jsonl')
            self.assertEqual(sum(r['status'] == 'completed' for r in rows), 144)
            self.assertTrue(all(r['synthetic'] for r in rows))

    def test_changed_files_and_no_real_requests(self):
        from run_stage_a import execute, load_run
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'run'
            self.prepare_run(folder)
            with patch('run_stage_a.urlopen', side_effect=AssertionError('Network forbidden')):
                with self.assertRaises(ValueError):
                    execute(folder)
                execute(folder, 'mixed', 10)
            with (folder/'questions.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaises(ValueError):
                load_run(folder)

    def test_import_checks_and_failure_retention(self):
        from run_stage_a import execute, import_responses, read_rows
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'run'
            self.prepare_run(folder)
            execute(folder, 'mixed')
            rows = read_rows(folder/'responses.jsonl')
            self.assertTrue(any(r['status'] == 'error' for r in rows))
            self.assertEqual(execute(folder, 'mixed')['added'], 0)
            imported = Path(tmp)/'answers.jsonl'
            imported.write_text(json.dumps(dict(request_id='unknown', attempt_id='a', status='completed', text='{}', synthetic=True))+'\n')
            with self.assertRaises(ValueError):
                import_responses(folder, imported)
            self.assertEqual(rows, read_rows(folder/'responses.jsonl'))

    def test_backend_translation(self):
        from run_stage_a import ask_model
        model = dict(backend='ollama', name='example', endpoint='http://localhost:11434',
                     temperature=0.6, max_output_tokens=100, context_tokens=4096, thinking=False)
        request = dict(model=model, prompt='Question', seed=4)
        raw = dict(message={'content': '{"count": 2}'}, prompt_eval_count=10, eval_count=4, done_reason='stop')
        with patch('run_stage_a.urlopen', return_value=io.BytesIO(json.dumps(raw).encode())) as send:
            response = ask_model(request, 3)
            payload = json.loads(send.call_args.args[0].data)
            self.assertEqual(payload['options']['seed'], 4)
            self.assertFalse(payload['think'])
            self.assertEqual(response['output_tokens'], 4)
        model.update(backend='openai_compatible', endpoint='http://localhost:8000/v1')
        with self.assertRaises(ValueError):
            ask_model(request, 3)
        del model['thinking']
        raw = {'choices': [{'message': {'content': '{}'}, 'finish_reason': 'length'}]}
        with patch('run_stage_a.urlopen', return_value=io.BytesIO(json.dumps(raw).encode())) as send:
            response = ask_model(request, 3)
            self.assertEqual(send.call_args.args[0].full_url, 'http://localhost:8000/v1/chat/completions')
            self.assertIsNone(response['input_tokens'])
            self.assertEqual(response['finish_reason'], 'length')

    def test_timeout_and_unsupported_backend(self):
        from run_stage_a import ask_model
        model = dict(backend='ollama', name='example', endpoint='http://localhost:11434',
                     temperature=0, max_output_tokens=10, context_tokens=4096)
        with patch('run_stage_a.urlopen', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                ask_model(dict(model=model, prompt='q', seed=0), 1)
        model['backend'] = 'unknown'
        with self.assertRaises(ValueError):
            ask_model(dict(model=model, prompt='q', seed=0), 1)


if __name__ == '__main__':
    unittest.main()
