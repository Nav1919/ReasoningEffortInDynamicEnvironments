"""Explicit verified Ollama profiles, not guesses based on model tag names.

Offline listing: python model_capabilities.py. Tests: test_model_capabilities.py.
Server-advertised thinking.values are preferred; documented fallback is versioned.
"""
import copy
import json
from reasoning_modes import thinking_value

EVIDENCE = 'https://github.com/ollama/ollama/blob/v0.35.1/docs/capabilities/thinking.mdx'
PROFILES = {
    'qwen3-boolean-v1': {'family': 'qwen3', 'values': [False, True]},
    'gpt-oss-effort-v1': {'family': 'gpt-oss', 'values': ['low', 'medium', 'high']},
}
OPTIONS = {'num_predict', 'num_ctx', 'temperature', 'seed'}


def profile_definition(name):
    if not isinstance(name, str) or name not in PROFILES:
        raise ValueError('Unknown capability profile; add verified evidence first')
    return copy.deepcopy(PROFILES[name])


def contains(values, value):
    # bool is a subclass of int: 0 must not be accepted as False.
    return any(type(item) is type(value) and item == value for item in values)


def validate_modes(profile, modes):
    definition = profile_definition(profile)
    if not isinstance(modes, dict) or not modes:
        raise ValueError('At least one named mode is required')
    seen = []
    for name, mode in modes.items():
        if not isinstance(name, str) or not name:
            raise ValueError('Mode names must be nonempty strings')
        value = thinking_value(mode)
        if not contains(definition['values'], value) or contains(seen, value):
            raise ValueError('Unsupported or duplicate reasoning mode')
        seen.append(value)
    return copy.deepcopy(modes)


def verify_capabilities(profile, modes, metadata, server_version):
    """Check actual model family/controls; keep evidence separate from readiness."""
    validate_modes(profile, modes)
    definition = profile_definition(profile)
    if metadata.get('details', {}).get('family') != definition['family']:
        raise ValueError('Installed model family does not match verified profile')
    advertised = metadata.get('thinking', {}).get('values')
    if advertised is None:
        if server_version != '0.35.1':
            raise ValueError('No thinking metadata; fallback verified only for Ollama 0.35.1')
        values, source = definition['values'], 'explicit_verified_profile'
    else:
        if not isinstance(advertised, list):
            raise ValueError('Malformed thinking capability metadata')
        values, source = advertised, 'installed_server_metadata'
    for mode in modes.values():
        if not contains(values, thinking_value(mode)):
            raise ValueError('Installed model does not support the requested control')
    return dict(profile=profile, source=source, server_version=server_version,
                advertised_values=advertised, verified_values=definition['values'],
                evidence=EVIDENCE, limitation='Control support is not scientific validity')


if __name__ == '__main__':
    print(json.dumps({'profiles': PROFILES, 'fallback_evidence': EVIDENCE}, indent=2))
