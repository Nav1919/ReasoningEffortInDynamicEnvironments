"""Execute an immutable saved plan, preserving every planned status.

Tests: test_comparison_execution.py. Never resumes/overwrites an old execution;
retries require a new plan attempt and output folder. No automatic model pulls.
"""
import json
from pathlib import Path
import subprocess
import sys
from comparison_plan import build_plan
from experiment_config import integer
from experiment_identity import fingerprint
from freeway_study import ROOT, write_json
from frozen_comparison import run_frozen
from model_provenance import verify_model
from run_model_freeway import post_json
from run_provenance import source_provenance


def checked_plan(folder):
    plan = json.loads((Path(folder)/'plan.json').read_text())
    expected = build_plan(plan['config'], plan['runs'][0]['attempt'])
    if fingerprint(plan) != fingerprint(expected):
        raise ValueError('Saved plan differs from reproducible recipe; regenerate a new plan')
    return plan


def live_entry(entry, path):
    config_path = path.parent.parent/'execution_config.json'
    if not config_path.exists():
        with config_path.open('x') as stream:
            json.dump(entry['resolved']['config'],stream,indent=2)
    r = entry['resolved']
    result = subprocess.run([sys.executable,str(ROOT/'run_model_freeway.py'),
        '--experiment-config',str(config_path),'--mode',r['selected_mode'],
        '--seed',str(r['requested_selector']),'--tick-seconds',str(r['tick_seconds']),
        '--replicate',str(r['replicate']),'--log-path',str(path)])
    if not path.exists():
        raise RuntimeError(f'Runner exited {result.returncode} without a run record')
    record = json.loads(path.read_text())
    record.update(plan_run_id=entry['run_id'],attempt=entry['attempt'],design='live-starts-v1')
    if result.returncode and record['run_status']=='complete':
        record['run_status']='failed'
    write_json(path,record)
    return record


def execute_plan(folder, limit=1, provider=post_json, model_check=None,
                 source_check=source_provenance, clock=None, live_runner=live_entry):
    folder = Path(folder)
    integer(limit)
    plan = checked_plan(folder)
    manifest = dict(status='running', comparison_id=plan['comparison_id'],
        runs=[dict(run_id=r['run_id'],status='planned',log=f"runs/{r['run_id']}.json")
              for r in plan['runs']])
    path = folder/'execution.json'
    with path.open('x') as stream:
        json.dump(manifest,stream,indent=2)
    (folder/'runs').mkdir(exist_ok=True)
    check = model_check or (lambda c:verify_model(c,provider))
    try:
        for index, (entry, status) in enumerate(zip(plan['runs'][:limit],manifest['runs'])):
            status['status']='running'
            write_json(path,manifest)
            log = folder/status['log']
            try:
                record = (run_frozen(entry,log,provider,check,source_check,clock,preloaded=index>0,
                                     preload_run_id=plan['runs'][0]['run_id'])
                          if plan['design']=='frozen-six-v1' else live_runner(entry,log))
                status['status']=record['run_status']
            except BaseException as error:
                status['status']='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed'
                status['error']=f'{type(error).__name__}: {error}'
                if not log.exists():
                    write_json(log,dict(resolved=entry['resolved'],run_status=status['status'],
                        plan_run_id=entry['run_id'],execution_error=status['error'],decisions=[]))
                raise
            finally:
                write_json(path,manifest)
            if status['status'] != 'complete':
                manifest['status']='stopped'
                break  # Never issue another request after a timeout/setup failure.
        else:
            manifest['status']='complete' if limit>=len(plan['runs']) else 'partial'
    except BaseException:
        manifest['status']='interrupted_or_failed'
        raise
    finally:
        write_json(path,manifest)
    return manifest
