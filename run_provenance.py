"""Local source/environment fingerprints; tests: test_run_provenance.py.

No network. Unavailable revisions or hardware values remain null with reasons.
Installed wheels need not retain a checkout; direct_url metadata is inspected.
"""
import hashlib
import importlib.metadata
import inspect
import json
import platform
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlparse
import realtimegym

ROOT = Path(__file__).resolve().parent


def command(*args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def source_provenance(config):
    env, _, _ = realtimegym.make(config['environment']['id'], seed=0, render=False)
    source = Path(inspect.getfile(type(env)))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != config['environment']['source_sha256']:
        raise ValueError('Installed Freeway source differs from the recipe')
    sources = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(ROOT.glob('*.py')) if not p.name.startswith('test_')}
    commit = command('git', '-C', str(ROOT), 'rev-parse', 'HEAD')
    status = command('git', '-C', str(ROOT), 'status', '--porcelain', '--', *sources)
    revision = None
    try:
        dist = importlib.metadata.distribution('realtime-gym')
        direct = json.loads(dist.read_text('direct_url.json') or '{}')
        revision = direct.get('vcs_info', {}).get('commit_id')
        if revision is None and direct.get('dir_info', {}).get('editable'):
            directory = unquote(urlparse(direct['url']).path)
            revision = command('git', '-C', directory, 'rev-parse', 'HEAD')
    except (importlib.metadata.PackageNotFoundError, ValueError, KeyError):
        pass
    memory = command('sysctl', '-n', 'hw.memsize') if sys.platform == 'darwin' else None
    return dict(project_commit=commit, relevant_local_modifications=None if status is None else bool(status),
        source_sha256=sources, python=sys.version, dependencies={d.metadata['Name']:d.version
        for d in importlib.metadata.distributions() if d.metadata['Name']},
        realtimegym_revision=revision, freeway_source_sha256=digest,
        machine=dict(system=platform.system(), release=platform.release(), architecture=platform.machine(),
                     processor=platform.processor(), memory_bytes=int(memory) if memory else None),
        unavailable=dict(project_commit=None if commit else 'No readable Git revision',
                         realtimegym_revision=None if revision else 'No recoverable VCS metadata',
                         memory=None if memory else 'Not available through local hardware query'))
