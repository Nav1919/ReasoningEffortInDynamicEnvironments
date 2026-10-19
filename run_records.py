"""Create evidence before setup; never replace an earlier run.

Tests: test_run_records.py. Logs retain resolved settings on setup failure.
"""
import copy
import json
from pathlib import Path
from freeway_study import write_json
from model_provenance import verify_model
from run_provenance import source_provenance
from experiment_starts import start_registry


def setup_run(path, resolved, model_check=verify_model, source_check=source_provenance):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(resolved=copy.deepcopy(resolved), run_status='setup',
                  episode_outcome='not_started', setup_failure=None, provenance={},
                  decisions=[], steps=[])
    # Exclusive creation precedes all provider calls, including metadata requests.
    with path.open('x') as stream:
        json.dump(record, stream, indent=2)
    stage = 'environment_and_code'
    try:
        record['provenance']['source'] = source_check(resolved['config'])
        record['start_registry'] = start_registry(resolved['config'])
        record['start'] = next(s for s in record['start_registry']
                               if s['requested_selector'] == resolved['requested_selector'])
        stage = 'model_setup'
        record['provenance']['model'] = model_check(resolved['config'])
        record['run_status'] = 'ready'
    except BaseException as error:
        record['run_status'] = 'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'setup_failed'
        record['setup_failure'] = dict(stage=stage, error_type=type(error).__name__, reason=str(error))
        if record['run_status'] == 'interrupted':
            raise
    finally:
        write_json(path, record)
    return record
