"""Read-only completeness gate for a proposed held-out audit bundle (stdlib only).

Run: python evaluation_audit.py BUNDLE.json --format json|text --source-root DIR
Input: explicit frozen configuration, splits, expected conditions/policies and
recorded episode references; schema and limits: docs/weekend/evaluation-audit.md.
Output: deterministic JSON or text on stdout; exit 0 only for a complete audit,
1 for refused comparisons, 2 for unreadable input. Never writes source evidence.
Test: python -m unittest test_evaluation_audit -v (synthetic fixtures only).
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


# Canonical JSON makes the digest independent of key order, but not of settings.
# Reject NaN/Infinity and non-JSON values rather than inventing a normalization.
def config_digest(value):
    """Return lowercase SHA-256 of canonical UTF-8 JSON; see the schema doc."""
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _mapping(value, name):
    _require(isinstance(value, dict) and bool(value), name + ' must be a nonempty object')
    _require(all(isinstance(k, str) and k.strip() for k in value),
             name + ' keys must be nonempty strings')
    return value


def _digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _load_json(path):
    # Duplicate JSON keys otherwise silently overwrite settings or episode data.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError('non-finite JSON number: ' + value)

    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=reject_constant)


# Shape validation is deliberately separate from evidence checks. Invalid shapes
# fail closed with a diagnostic, not a traceback or a partially passing report.
def _validate(bundle):
    _require(isinstance(bundle, dict), 'bundle must be an object')
    _require(type(bundle.get('schema_version')) is int and bundle['schema_version'] == 1,
             'schema_version must be 1')
    config = _mapping(bundle.get('frozen_config'), 'frozen_config')
    for field in ('model', 'settings', 'modes'):
        _mapping(config.get(field), 'frozen_config.' + field)
    _require(_digest(bundle.get('frozen_config_digest')), 'invalid frozen_config_digest')
    for field in ('policies', 'conditions', 'starts'):
        entries = _mapping(bundle.get(field), field)
        for key, entry in entries.items():
            _mapping(entry, field + '.' + key)
    _mapping(bundle.get('policy_digests'), 'policy_digests')
    _require(set(bundle['policies']) == set(bundle['policy_digests']),
             'policy_digests must cover exactly the policies')
    _require(all(_digest(d) for d in bundle['policy_digests'].values()),
             'invalid policy digest')
    splits = _mapping(bundle.get('splits'), 'splits')
    _require(set(splits) == {'development', 'held_out'}, 'exactly two splits required')
    for name, starts in splits.items():
        _require(isinstance(starts, list) and starts, name + ' must be a nonempty list')
        _require(all(isinstance(s, str) and s in bundle['starts'] for s in starts),
                 name + ' contains unknown start IDs')
    _require(set(bundle['starts']) == set(splits['development'] + splits['held_out']),
             'every declared start must belong to a split')
    _require(isinstance(bundle.get('episodes'), list), 'episodes must be a list')
    _mapping(bundle.get('sources'), 'sources')
    _require(set(bundle['sources']) == {'runner', 'simulator', 'policies'},
             'sources must contain runner, simulator and policies')
    config_digest(bundle)  # Also reject non-finite/non-JSON API input.


def audit(bundle, source_root):
    """Audit caller-selected cells and local source bytes, returning a JSON object.

    No comparison statistics are computed. `comparison_allowed` means only that
    this structural/provenance gate passed, not that a scientific claim is valid.
    """
    report = {'schema_version': 1, 'comparison_allowed': False, 'issues': [],
              'expected_episodes': 0, 'recorded_episodes': 0, 'coverage': []}

    def issue(code, location, detail):
        report['issues'].append({'code': code, 'location': location, 'detail': detail})

    try:
        _validate(bundle)
    except (ValueError, TypeError, OverflowError) as exc:
        issue('invalid_input', 'bundle', str(exc))
        return report

    root = Path(source_root).resolve()

    # References are relative to an explicit root; no network, traversal, or
    # absolute paths. Symlinks resolving outside the root are rejected as well.
    def source(reference, location):
        if not isinstance(reference, dict) or not _digest(reference.get('sha256')):
            issue('provenance', location, 'source requires path and lowercase SHA-256')
            return
        name = reference.get('path')
        if not isinstance(name, str) or not name or Path(name).is_absolute():
            issue('provenance', location, 'source path must be nonempty and relative')
            return
        try:
            path = (root / name).resolve()
            _require(path.is_relative_to(root), 'source escapes source root')
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            _require(actual == reference['sha256'], 'source checksum mismatch')
            return path
        except (OSError, ValueError, RuntimeError) as exc:
            issue('provenance', location, str(exc))

    for role, reference in sorted(bundle['sources'].items()):
        revision = reference.get('revision') if isinstance(reference, dict) else None
        if not isinstance(revision, str) or not revision.strip():
            issue('provenance', 'sources.' + role, 'explicit source revision required')
        source(reference, 'sources.' + role)

    frozen = bundle['frozen_config_digest']
    if config_digest(bundle['frozen_config']) != frozen:
        issue('config_digest', 'frozen_config', 'declared digest differs from configuration')
    for policy, config in sorted(bundle['policies'].items()):
        if config_digest(config) != bundle['policy_digests'][policy]:
            issue('policy_digest', policy, 'declared digest differs from policy')

    splits = bundle['splits']
    for name, ids in splits.items():
        if len(set(ids)) != len(ids):
            issue('duplicate_start', name, 'duplicate start IDs in split')
    # Identity is the complete start specification, not merely its display ID.
    # This catches identical seeds/situations relabeled to hide split leakage.
    identities = {}
    for name, ids in splits.items():
        identities[name] = {config_digest(bundle['starts'][s]) for s in ids}
        if len(identities[name]) != len(set(ids)):
            issue('duplicate_start', name, 'multiple IDs alias an identical start')
    if identities['development'] & identities['held_out']:
        issue('split_overlap', 'splits', 'development and held-out start identities overlap')

    expected = {(s, c, p) for s in splits['held_out']
                for c in bundle['conditions'] for p in bundle['policies']}
    report['expected_episodes'] = len(expected)
    report['recorded_episodes'] = len(bundle['episodes'])
    counts = Counter()
    successful = Counter()
    episode_ids = set()
    raw_sources = set()
    for index, episode in enumerate(bundle['episodes']):
        location = 'episodes[' + str(index) + ']'
        if not isinstance(episode, dict):
            issue('invalid_episode', location, 'episode must be an object')
            continue
        episode_id = episode.get('episode_id')
        if not isinstance(episode_id, str) or not episode_id.strip():
            issue('invalid_episode', location, 'nonempty episode_id required')
        elif episode_id in episode_ids:
            issue('duplicate_episode', location, 'episode_id already recorded')
        else:
            episode_ids.add(episode_id)
        key = tuple(episode.get(k) for k in ('start_id', 'condition_id', 'policy_id'))
        if not all(isinstance(k, str) for k in key) or key not in expected:
            issue('unexpected_episode', location, 'episode is not an expected held-out cell')
            continue
        counts[key] += 1
        start, condition, policy = key
        for field, wanted in (('frozen_config', bundle['frozen_config']),
                              ('start', bundle['starts'][start]),
                              ('condition', bundle['conditions'][condition]),
                              ('policy', bundle['policies'][policy])):
            digest = frozen if field == 'frozen_config' else config_digest(wanted)
            if (episode.get(field + '_digest') != digest
                    or config_digest(episode.get(field)) != config_digest(wanted)):
                issue('mismatched_' + field, location, field + ' payload or digest differs')
        if episode.get('status') != 'completed':
            issue('failed_episode', location, 'episode status is not completed')
        else:
            successful[key] += 1
        reference = episode.get('source')
        path = source(reference, location + '.source')
        if path is not None:
            try:
                recorded = _load_json(path)
                supplied = {k: v for k, v in episode.items() if k != 'source'}
                _require(config_digest(recorded) == config_digest(supplied),
                         'raw episode does not match supplied episode metadata')
            except (OSError, ValueError, TypeError) as exc:
                issue('provenance', location + '.source', str(exc))
            resolved = str(path)
            if resolved in raw_sources:
                issue('duplicate_source', location, 'raw episode source reused')
            raw_sources.add(resolved)

    # Keep every expected cell visible, including missing, failed and duplicated
    # cells. Never silently take an intersection or select the best retry.
    for key in sorted(expected):
        count = counts[key]
        if count == 0:
            issue('missing_episode', '/'.join(key), 'no episode recorded')
        elif count > 1:
            issue('duplicate_cell', '/'.join(key), 'multiple episodes recorded')
        report['coverage'].append(dict(zip(('start_id', 'condition_id', 'policy_id'), key),
                                       recorded=count, completed=successful[key]))
    report['comparison_allowed'] = not report['issues']
    return report


def human_summary(report):
    """Render the same counts, coverage and refusal reasons as the JSON report."""
    lines = ['Comparison gate: ' + ('PASS' if report['comparison_allowed'] else 'REFUSED'),
             f"Episodes: {report['recorded_episodes']} recorded / {report['expected_episodes']} expected"]
    for cell in report['coverage']:
        lines.append('{start_id}/{condition_id}/{policy_id}: {recorded} recorded, '
                     '{completed} completed'.format(**cell))
    for item in report['issues']:
        lines.append('{code} at {location}: {detail}'.format(**item))
    lines.append('Structural audit only; not evidence of policy improvement or scientific approval.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--format', choices=('json', 'text'), default='json')
    args = parser.parse_args(argv)
    try:
        bundle = _load_json(args.bundle)
    except (OSError, ValueError) as exc:
        parser.exit(2, 'Cannot read audit bundle: ' + str(exc) + '\n')
    report = audit(bundle, args.source_root)
    print(json.dumps(report, indent=2, sort_keys=True) if args.format == 'json'
          else human_summary(report))
    return 0 if report['comparison_allowed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
