"""Static guard counterexamples include code that is never executed."""
from pathlib import Path
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize('source', [
    "from pathlib import Path\np = Path('ledger') / 'hidden.json'\np.read_bytes()",
    "from pathlib import Path as P\np = P.cwd() / 'ledger' / 'x'\nq = p\nq.open()",
    "import subprocess\nsubprocess.run(['python', '-c', \"open('ledger/x').read()\"])",
    "import hashlib\nfrom pathlib import Path\nhashlib.sha256(Path('ledger/x').read_bytes())",
    "from builtins import open as load\nload('ledger/x')",
    "from pathlib import Path\ndef load(path):\n    return path.read_bytes()\nload(Path('ledger/x'))",
    "from pathlib import Path\ndef location():\n    return Path('ledger/x')\nlocation().read_bytes()",
    "from pathlib import Path\np = Path('ledger/x')\nreader = p.read_bytes\nreader()",
])
def test_static_guard_rejects_unexecuted_python(source):
    from grid_pipeline.ledger_access import violations
    assert violations(source, '.py')


@pytest.mark.parametrize('source', [
    "$paths = @('ledger/definitions/v1.toml')\nGet-FileHash $paths",
    "$p = Join-Path $repo 'ledger'\nGet-FileHash (Join-Path $p 'definitions/v1.toml')",
    "p=ledger; cat \"$p/definitions/v1.toml\"",
])
def test_static_guard_rejects_powershell_hashing(source):
    from grid_pipeline.ledger_access import violations
    assert violations(source, '.ps1')


def test_repository_ledger_access_policy():
    from grid_pipeline.ledger_access import check_repository
    assert check_repository(Path(__file__).resolve().parents[1]) == []


@pytest.mark.parametrize('source', ['argument', 'environment', 'config'])
def test_external_child_cannot_receive_dynamic_ledger_path(monkeypatch, source):
    target = Path(__file__).resolve().parents[1] / 'ledger/definitions/stress-index-v1.toml'
    monkeypatch.setenv('LEDGER_FILE', str(target))
    config = {'input': os.environ['LEDGER_FILE']}
    # The child imports no grid package and its code contains no ledger path.
    child = 'import sys; open(sys.argv[1], "rb").read()'
    command = [sys.executable, '-c', child]
    if source == 'argument':
        command.append(os.environ['LEDGER_FILE'])
        monkeypatch.delenv('LEDGER_FILE')
    elif source == 'config':
        command.append(config['input'])
        monkeypatch.delenv('LEDGER_FILE')
    else:
        command = [sys.executable, '-c', 'import os; open(os.environ["LEDGER_FILE"], "rb").read()']
    with pytest.raises(PermissionError, match='external.*content'):
        subprocess.run(command, check=True, capture_output=True)


def test_external_child_receives_ledger_content_only(monkeypatch):
    from grid_pipeline.ledger import read_definition
    monkeypatch.delenv('LEDGER_FILE', raising=False)
    target = Path(__file__).resolve().parents[1] / 'ledger/definitions/stress-index-v1.toml'
    raw = read_definition(target)
    result = subprocess.run([sys.executable, '-c',
                             'import sys; print(len(sys.stdin.buffer.read()))'],
                            input=raw, capture_output=True, check=True)
    assert int(result.stdout) == len(raw)


def test_prospective_scanner_uses_ledger_owner(monkeypatch):
    import importlib.util
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('s4_scan_test', repo / 'scripts/s4_secret_scan.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listing = subprocess.CompletedProcess([], 0, b'ledger/definitions/stress-index-v1.toml\0', b'')
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs: listing)
    assert module.scan(prospective=True) is False


@pytest.mark.parametrize('value,cwd_suffix', [
    ('./ledger/definitions/stress-index-v1.toml', ''),
    ('.\\ledger\\definitions\\stress-index-v1.toml', ''),
    ('scripts/../ledger/definitions/stress-index-v1.toml', ''),
    ('./ledger/./definitions/../definitions//stress-index-v1.toml', ''),
    ('../ledger/definitions/stress-index-v1.toml', 'scripts'),
    ('./grid-project/ledger/definitions/stress-index-v1.toml', '..'),
])
@pytest.mark.parametrize('source', ['environment', 'config'])
def test_relative_dynamic_child_path_is_denied(monkeypatch, value, cwd_suffix, source):
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setenv('INPUT', value)
    config = {'path': os.environ['INPUT']}
    if source == 'environment':
        command = [sys.executable, '-c', 'import os; open(os.environ["INPUT"], "rb").read()']
    else:
        command = [sys.executable, '-c', 'import sys; open(sys.argv[1], "rb").read()', config['path']]
        monkeypatch.delenv('INPUT')
    with pytest.raises(PermissionError, match='external.*content'):
        subprocess.run(command, cwd=repo / cwd_suffix, capture_output=True, check=True)


def test_index_scanner_passes_only_blob_ids_not_ledger_names(monkeypatch):
    import importlib.util
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('s4_index_scan_test', repo / 'scripts/s4_secret_scan.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    oid = 'a' * 40
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert all('ledger/' not in str(arg).replace('\\', '/') and not str(arg).startswith(':')
                   for arg in command)
        if 'ls-files' in command:
            return subprocess.CompletedProcess(command, 0,
                f'100644 {oid} 0\tledger/definitions/stress-index-v1.toml\0'.encode(), b'')
        assert command[-3:] == ['cat-file', 'blob', oid]
        return subprocess.CompletedProcess(command, 0, b'fixture content only', b'')

    monkeypatch.setattr(module.subprocess, 'run', run)
    assert module.scan() is False
    assert len(calls) == 2
