"""Separate response failures, actions and missing measurements.

No model calls. Tests: test_decision_records.py. Ollama eval_count measures all
output tokens, not a separately measured reasoning-token count.
"""
import copy
from run_model_freeway import parse_action


def decision_record(response, error=None, application_status='not_applied'):
    malformed = (not isinstance(response, dict)
                 or not isinstance(response.get('message'), dict)
                 or not isinstance(response['message'].get('content'), str))
    if error:
        status = 'timeout' if ('timed out' in str(error).lower() or 'TimeoutError' in str(error)) else 'request_error'
    elif malformed:
        status = 'malformed_response'
    elif response.get('done_reason') == 'length':
        status = 'token_limit_truncation'
    elif parse_action(response) is None:
        status = 'invalid_action'
    else:
        status = 'completed'
    action = parse_action(response, error) if not malformed else None
    measurements, unavailable = {}, {}
    raw = response if isinstance(response, dict) else {}
    for field, provider_key in [('input_tokens','prompt_eval_count'), ('output_tokens','eval_count')]:
        value = raw.get(provider_key)
        valid = type(value) is int and value >= 0
        measurements[field] = value if valid else None
        if not valid:
            unavailable[field] = f'{provider_key} not supplied as a nonnegative integer'
    measurements['reasoning_tokens'] = None
    unavailable['reasoning_tokens'] = 'Ollama does not separately report reasoning-token usage here'
    return dict(request_status=status, response_status='received' if response is not None else 'absent',
                valid_action=action is not None, parsed_action=action,
                fallback_action=None if action else 'S', application_status=application_status,
                action_source='model' if action else 'invalid_fallback',
                measurements=measurements, measurement_unavailable=unavailable,
                response=copy.deepcopy(response), error=str(error) if error else None)
