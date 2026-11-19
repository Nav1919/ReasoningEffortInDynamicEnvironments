"""Validate a proposed experiment manifest without simulator imports or inference.

Usage: python experiment_manifest.py MANIFEST.json [COMPARISON.json ...]
API: validate_manifest(mapping); validate_comparison(sequence_of_mappings).
Inputs: explicit JSON scientific controls described in docs/weekend/run-manifest.md.
Output: unchanged validated mapping (API), or success/error text and exit 0/2 (CLI).
No files are written. Tests: python -m unittest test_experiment_manifest -v;
see test_experiment_manifest.py for synthetic fixtures and failure checks.
"""

import argparse
import json
import math
from pathlib import Path


class ManifestError(ValueError):
    """An incomplete, ambiguous, or unmatched experiment specification."""


def _object(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ManifestError(f'{where}: expected exactly {sorted(keys)}')


def _text(value, where):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ManifestError(f'{where}: expected nonempty text without NUL')


def _json_value(value, where):
    # Reject Python-only values and nonfinite numbers, including nested ones.
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _json_value(item, where)
        return
    if isinstance(value, dict) and all(isinstance(k, str) and k.strip() for k in value):
        for item in value.values():
            _json_value(item, where)
        return
    raise ManifestError(f'{where}: expected finite JSON values')


def _settings(value, where):
    if not isinstance(value, dict) or not value:
        raise ManifestError(f'{where}: supply a nonempty settings object')
    _json_value(value, where)


def validate_manifest(manifest):
    """Check structure and split integrity; do not select or approve science."""
    _object(manifest, ('frozen_model', 'simulator', 'environment', 'pressure',
                       'common_settings', 'modes', 'active_mode', 'seeds',
                       'output_path'), 'manifest')
    for key in ('frozen_model', 'simulator'):
        _object(manifest[key], ('name', 'revision'), key)
        for field in ('name', 'revision'):
            _text(manifest[key][field], f'{key}.{field}')
    _object(manifest['environment'], ('name', 'difficulty'), 'environment')
    _text(manifest['environment']['name'], 'environment.name')
    _settings(manifest['environment']['difficulty'], 'environment.difficulty')
    _object(manifest['pressure'], ('control', 'value', 'units', 'semantics'), 'pressure')
    for key in ('control', 'units', 'semantics'):
        _text(manifest['pressure'][key], f'pressure.{key}')
    if manifest['pressure']['value'] is None:
        raise ManifestError('pressure.value: supply the actual control value')
    _json_value(manifest['pressure']['value'], 'pressure.value')
    _settings(manifest['common_settings'], 'common_settings')
    _object(manifest['modes'], ('quick', 'deliberate'), 'modes')
    for mode in ('quick', 'deliberate'):
        _settings(manifest['modes'][mode], f'modes.{mode}')
    # The two modes are overlays on common settings, not hidden replacements.
    quick, deliberate = (manifest['modes'][m] for m in ('quick', 'deliberate'))
    if set(quick) != set(deliberate) or quick == deliberate:
        raise ManifestError('modes: use the same explicit keys with distinct settings')
    if set(quick) & set(manifest['common_settings']):
        raise ManifestError('modes: must not override common_settings')
    if manifest['active_mode'] not in ('quick', 'deliberate'):
        raise ManifestError('active_mode: expected quick or deliberate')
    _object(manifest['seeds'], ('development', 'held_out'), 'seeds')
    for split, seeds in manifest['seeds'].items():
        if (not isinstance(seeds, list) or not seeds
                or any(type(seed) is not int for seed in seeds)):
            raise ManifestError(f'seeds.{split}: supply a nonempty integer list')
        if len(set(seeds)) != len(seeds):
            raise ManifestError(f'seeds.{split}: duplicate seeds')
    if set(manifest['seeds']['development']) & set(manifest['seeds']['held_out']):
        raise ManifestError('seeds: development and held_out overlap')
    _text(manifest['output_path'], 'output_path')
    return manifest


def validate_comparison(manifests):
    """Require matched declared controls, allowing mode and output to differ."""
    if len(manifests) < 2:
        raise ManifestError('comparison: supply at least two manifests')
    for manifest in manifests:
        validate_manifest(manifest)
    # JSON serialization distinguishes booleans from numbers and preserves seed
    # order (paired execution order is a declared control, not silently sorted).
    def controls(manifest):
        return {k: v for k, v in manifest.items() if k not in ('active_mode', 'output_path')}
    reference = controls(manifests[0])
    outputs = set()
    for index, manifest in enumerate(manifests):
        for key, value in controls(manifest).items():
            if json.dumps(value, sort_keys=True) != json.dumps(reference[key], sort_keys=True):
                raise ManifestError(f'comparison[{index}]: mismatched {key}')
        output = Path(manifest['output_path']).resolve()
        if output in outputs:
            raise ManifestError('comparison: output paths must be distinct')
        outputs.add(output)
    return manifests


# Reject duplicate JSON keys rather than accepting a hidden last-value override.
def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifests', nargs='+', type=Path)
    args = parser.parse_args(argv)
    try:
        manifests = [json.loads(path.read_text(encoding='utf-8'),
                                object_pairs_hook=_unique_object)
                     for path in args.manifests]
        for manifest in manifests:
            validate_manifest(manifest)
        if len(manifests) > 1:
            validate_comparison(manifests)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f'invalid manifest: {error}\n')
    print(f'Validated {len(manifests)} manifest(s); scientific approval not implied.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
