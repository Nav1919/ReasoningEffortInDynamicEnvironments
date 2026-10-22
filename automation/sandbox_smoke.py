"""No-model runtime test for the real Codex Linux sandbox.

Run inside the worker: python3 /smoke/sandbox_smoke.py. Mount this file read-only
at /smoke/sandbox_smoke.py and use the repository working directory. It proves
the worker home is writable outside the sandbox, then checks workspace writes,
home/Git-metadata write denial, and network-socket denial inside it. Outputs
JSON evidence and preserves a nonzero failure status. No credentials required.
Tested by the manual Docker smoke command documented in docs/automation.md.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import uuid


def denied_write(directory):
    path = directory / (".research-sandbox-probe-" + uuid.uuid4().hex)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except PermissionError:
        return
    else:
        os.close(descriptor)
        path.unlink()
        raise AssertionError("Write unexpectedly allowed: " + str(directory))


def inside():
    with tempfile.NamedTemporaryFile(dir=Path.cwd()) as handle:
        handle.write(b"workspace write verified")
        handle.flush()
    denied_write(Path("/opt/data"))
    metadata = Path.cwd() / ".git"
    if metadata.is_file():
        metadata = Path(metadata.read_text().strip().removeprefix("gitdir: "))
    if not metadata.is_dir():
        raise AssertionError("Git metadata unavailable for the smoke check")
    denied_write(metadata)
    try:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError:
        pass
    else:
        connection.close()
        raise AssertionError("IP socket unexpectedly allowed")
    print(json.dumps({"workspace_write": True, "outside_write_denied": True,
        "git_write_denied": True, "network_socket_denied": True, "uid": os.geteuid()}))


def main():
    if "--inside" in sys.argv:
        inside()
        return 0
    if os.geteuid() == 0:
        raise AssertionError("Smoke test must run as the nonroot worker")
    with tempfile.NamedTemporaryFile(dir="/opt/data"):
        pass
    result = subprocess.run(["/usr/local/bin/codex", "sandbox", "linux", "--",
        sys.executable, str(Path(__file__).resolve()), "--inside"],
        capture_output=True, text=True)
    print(json.dumps({"sandbox_exit": result.returncode,
        "stdout": result.stdout.strip(), "stderr": result.stderr.strip()[:2000]}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
