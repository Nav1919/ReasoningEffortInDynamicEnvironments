"""Execute one saved frozen situation using the existing request/parser helpers.

Tests: test_frozen_comparison.py; no separate controller or experiment CLI.
"""
import copy
from decision_records import decision_record
from experiment_identity import fingerprint
from freeway_study import recreate, simulate, write_json
from run_model_freeway import request_action
from run_records import setup_run


def run_frozen(entry, path, provider, model_check, source_check, clock=None, preloaded=False, preload_run_id=None):
    record = setup_run(path, entry['resolved'], model_check=model_check, source_check=source_check)
    record.update(plan_run_id=entry['run_id'], attempt=entry['attempt'], design='frozen-six-v1',
                  situation=copy.deepcopy(entry['situation']), episode_outcome='not_applicable')
    try:
        if record['run_status'] != 'ready':
            return record
        env, actual = recreate(entry['situation']['requested_seed'], entry['situation']['preceding_actions'])
        if (actual != entry['situation']['actual_seed']
                or fingerprint(env.observe()) != fingerprint(entry['situation']['observation'])):
            raise ValueError('Saved situation does not match installed simulator replay')
        timeout = entry['resolved']['config']['request_timeout']
        policy = entry['resolved']['config'].get('warmup_policy', 'per_run_question')
        if policy == 'load_once' and preloaded:
            record['warmup'] = dict(kind='reuse_preloaded_model', preload_run_id=preload_run_id)
        else:
            warmup = copy.deepcopy(entry['request'])
            warm_provider = provider
            if policy == 'load_once':
                warmup = {key:warmup[key] for key in ['model','stream','keep_alive','options']}
                warmup['prompt'] = ''
                warm_provider = lambda endpoint, payload, timeout:provider('generate',payload,timeout=timeout)
            else:
                warmup['messages'] = [{'role':'user','content':'Return only S.'}]
            warm_timeout = entry['resolved']['config'].get('preload_timeout', timeout) if policy=='load_once' else timeout
            raw, error, start, end = request_action(warmup, None, warm_timeout, warm_provider, clock)
            if policy == 'load_once':
                if not error and (not isinstance(raw,dict) or raw.get('done_reason') != 'load'):
                    error = 'Expected a no-text load response from Ollama'
                details = dict(kind='model_load_no_text', response=raw, error=error)
            else:
                details = decision_record(raw,error)
            record['warmup'] = dict(request=warmup, **details, latency_seconds=end-start)
            if error:
                record.update(run_status='setup_failed', setup_failure=dict(stage='warmup',reason=error))
                return record
        record['run_status'] = 'running'
        write_json(path, record)
        raw, error, start, end = request_action(entry['request'], None, timeout, provider, clock)
        decision = dict(request=copy.deepcopy(entry['request']), **decision_record(raw,error),
                        latency_seconds=end-start, executed_action=None, reference_outcome=None)
        if decision['valid_action']:
            decision['reference_outcome'] = simulate(env, decision['parsed_action'])
            decision['immediate_safe'] = not decision['reference_outcome']['collision']
            category = entry['situation']['category']
            decision['relevant_choice'] = (decision['parsed_action']=='U' and decision['immediate_safe']
                if category=='safe_forward' else decision['immediate_safe'] if category=='dangerous_forward'
                else decision['parsed_action'] in entry['situation']['safe_progress_first_actions_at_horizon'])
        else:
            decision.update(immediate_safe=None, relevant_choice=None)
        record['decisions'] = [decision]
        record['run_status'] = 'failed' if error else 'complete'
        return record
    except BaseException as error:
        record.update(run_status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',
                      execution_error=dict(error_type=type(error).__name__,reason=str(error)))
        if record['run_status']=='interrupted':
            raise
        return record
    finally:
        write_json(path, record)
