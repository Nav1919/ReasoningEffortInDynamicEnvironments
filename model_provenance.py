"""Verify installed Ollama identity without inference; tests: test_model_provenance.

CLI: python model_provenance.py CONFIG. Uses version/tags/show only, never pulls.
Tags remain mutable: do not replace model artifacts during a controlled run.
"""
import argparse
import json
from experiment_config import load_config, validate_config
from model_capabilities import verify_capabilities
from run_model_freeway import post_json


def verify_model(config, provider=post_json):
    c = validate_config(config, ready=True)
    timeout, model = c['request_timeout'], c['model']
    version = provider('version', {}, timeout=timeout)['version']
    inventory = provider('tags', {}, timeout=timeout)
    installed = [m for m in inventory['models'] if m['name'] == model['tag']]
    if len(installed) != 1:
        raise ValueError('Expected exact installed model tag is unavailable; no automatic download')
    digest = installed[0]['digest'].removeprefix('sha256:')
    if digest != model['expected_digest']:
        raise ValueError('Installed model digest differs from the recorded recipe')
    metadata = provider('show', {'model':model['tag']}, timeout=timeout)
    capability = verify_capabilities(model['capability_profile'], c['modes'], metadata, version)
    return dict(tag=model['tag'], digest=digest, server_version=version,
                metadata=metadata, capability_evidence=capability)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    args = parser.parse_args()
    print(json.dumps(verify_model(load_config(args.config, ready=True)), indent=2))
