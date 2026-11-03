"""Exclusive IO owner for append-only, content-addressed forecast receipts."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
BOUNDARY_PATH = 'ledger/policy/s4-acceptance.json'
BOUNDARY_TAG = 's4-acceptance'
IDENTITY = 'Darren-dev141/grid-project'


class LedgerError(ValueError):
    pass


def read_content(path: Path) -> bytes:
    return Path(path).read_bytes()


read_definition = read_content


def receipt_paths(root: Path) -> list[Path]:
    return sorted((Path(root) / 'forecasts').rglob('*.json'))


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError('unsupported receipt value')


def _encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False, default=_json) + '\n').encode()


def _aware(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise LedgerError('issue timestamp must be timezone aware')
    return result


def _validate(raw: bytes, relative: Path, root: Path, committed_at=None,
              definition_bytes: bytes | None = None) -> dict:
    try:
        payload = json.loads(raw)
        if _encode(payload) != raw:
            raise LedgerError('receipt is not canonical JSON')
        if payload['schema_version'] != 1:
            raise LedgerError('unknown receipt schema')
        forecaster = payload['forecaster_id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', forecaster):
            raise LedgerError('invalid forecaster ID')
        target = date.fromisoformat(payload['target_date'])
        issued = _aware(payload['issued_at'])
        deadline = datetime.combine(target, time.min, ET)
        if issued >= deadline:
            raise LedgerError('receipt issued after target day began')
        if committed_at is not None and not issued.replace(microsecond=0) <= committed_at < deadline:
            raise LedgerError('receipt was not committed before target day')
        expected = Path('forecasts') / forecaster / target.isoformat() / (sha256(raw).hexdigest() + '.json')
        if relative != expected:
            raise LedgerError('receipt content hash or directory mismatch')
        forecast = payload['forecast']
        if not isinstance(forecast, dict) or forecast['target_date'] != target.isoformat():
            raise LedgerError('forecast target mismatch')
        if not isinstance(payload['geography'], str) or payload['geography'] != 'PJM-wide call, Maryland weather':
            raise LedgerError('geography label missing')
        definition = payload['definition']
        if definition is None and ('definition_sha256' in forecast or 'definition_version' in forecast):
            raise LedgerError('our forecasts require a frozen definition')
        if definition is not None:
            diagnostics = forecast['receipt']
            if (diagnostics['mode'] != 'prospective'
                    or _aware(diagnostics['issued_at']) != issued):
                raise LedgerError('prospective diagnostics and issue time must match envelope')
            version = definition['version']
            if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', version):
                raise LedgerError('invalid definition version')
            definition_raw = (definition_bytes if definition_bytes is not None else
                              read_definition(root / 'definitions' / (version + '.toml')))
            if sha256(definition_raw).hexdigest() != definition['sha256']:
                raise LedgerError('definition hash mismatch')
            if (forecast['definition_sha256'] != definition['sha256']
                    or forecast['definition_version'] != version
                    or forecast['thresholds_mw'] != definition['thresholds_mw']):
                raise LedgerError('frozen definition or thresholds mismatch')
        return payload
    except LedgerError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError, OSError) as exc:
        raise LedgerError('invalid or unreadable receipt') from exc


def append_forecast(root: Path, forecaster_id: str, forecast, issued_at: datetime) -> Path:
    """Write a prospective call once. S3 diagnostics are not published receipts."""
    now = datetime.now(timezone.utc)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None or issued_at > now:
        raise LedgerError('issue time must be aware and cannot be in the future')
    if now >= datetime.combine(forecast.target_date, time.min, ET):
        raise LedgerError('cannot append a forecast after its target day began')
    if forecast.receipt is None or forecast.receipt.mode != 'prospective':
        raise LedgerError('only prospective forecasts may be published')
    if forecast.receipt.issued_at != issued_at:
        raise LedgerError('forecast and envelope issue times differ')
    payload = {'schema_version': 1, 'forecaster_id': forecaster_id,
               'target_date': forecast.target_date.isoformat(), 'issued_at': issued_at.isoformat(),
               'geography': 'PJM-wide call, Maryland weather', 'forecast': asdict(forecast),
               'definition': {'version': forecast.definition_version,
                              'sha256': forecast.definition_sha256,
                              'thresholds_mw': forecast.thresholds_mw}}
    raw = _encode(payload)
    relative = Path('forecasts') / forecaster_id / forecast.target_date.isoformat() / (sha256(raw).hexdigest() + '.json')
    _validate(raw, relative, Path(root))
    destination = Path(root) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(raw)
    return destination


def _git_raw(repo: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-c', f'safe.directory={repo.resolve().as_posix()}',
                             '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise LedgerError('git verification failed; full history is required')
    return result.stdout


def _git(repo: Path, *args: str) -> str:
    return _git_raw(repo, *args).decode('utf-8')


def _tree_blobs(repo: Path, commit: str) -> dict[str, str]:
    blobs = {}
    for entry in _git_raw(repo, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if entry:
            metadata, path = entry.split(b'\t', 1)
            _, kind, oid = metadata.split()
            if kind == b'blob':
                blobs[path.decode('utf-8')] = oid.decode('ascii')
    return blobs


def read_object(repo: Path, oid: str) -> bytes:
    """Read Git object content by ID, never by a ledger path-bearing spec."""
    if not re.fullmatch(r'[0-9a-f]{40}', oid):
        raise LedgerError('invalid Git blob object ID')
    return _git_raw(repo, 'cat-file', 'blob', oid)


def _push_witnesses(repo: Path) -> list[tuple[str, datetime]]:
    """Read server-created push-run timestamps, never timestamps from repo files."""
    identity = 'Darren-dev141/grid-project'
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('GITHUB_REPOSITORY') != identity):
        raise LedgerError('prospective timing requires independent GitHub push witnesses')
    remote = _git(repo, 'remote', 'get-url', 'origin').strip().removesuffix('.git')
    if remote not in {f'https://github.com/{identity}', f'git@github.com:{identity}'}:
        raise LedgerError('push witness repository identity mismatch')
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise LedgerError('GitHub push witness access is unavailable')
    witnesses = []
    try:
        for page in range(1, 101):
            request = Request(
                f'https://api.github.com/repos/{identity}/actions/runs?event=push&per_page=100&page={page}',
                headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                         'X-GitHub-Api-Version': '2022-11-28'})
            with urlopen(request, timeout=30) as response:
                runs = json.load(response)['workflow_runs']
            for run in runs:
                if run['event'] == 'push' and re.fullmatch(r'[0-9a-f]{40}', run['head_sha']):
                    witnesses.append((run['head_sha'], _aware(run['created_at'])))
            if len(runs) < 100:
                return witnesses
    except Exception:
        # Do not expose HTTP headers, credentials, or response bodies on failure.
        raise LedgerError('independent GitHub push witness lookup failed') from None
    raise LedgerError('push witness pagination exceeded safe bound')


def _ancestor(repo: Path, commit: str, head: str) -> bool:
    result = subprocess.run(['git', '-c', f'safe.directory={repo.as_posix()}',
                             '-C', str(repo), 'merge-base', '--is-ancestor', commit, head],
                            capture_output=True)
    return result.returncode == 0


def _check_boundary(repo: Path, record: dict) -> None:
    if (record.get('schema_version') != 1 or record.get('tag_name') != BOUNDARY_TAG
            or not isinstance(record.get('bootstrap_run_id'), int) or record['bootstrap_run_id'] <= 0
            or any(not re.fullmatch(r'[0-9a-f]{40}', record.get(key, ''))
                   for key in ['acceptance_commit', 'acceptance_tree', 'tag_object'])):
        raise LedgerError('invalid acceptance boundary record')
    tag = 'refs/tags/' + BOUNDARY_TAG
    if (_git(repo, 'cat-file', '-t', tag).strip() != 'tag'
            or _git(repo, 'rev-parse', tag).strip() != record['tag_object']
            or _git(repo, 'rev-parse', tag + '^{commit}').strip() != record['acceptance_commit']
            or _git(repo, 'rev-parse', record['acceptance_commit'] + '^{tree}').strip() != record['acceptance_tree']
            or not _ancestor(repo, record['acceptance_commit'], 'HEAD')):
        raise LedgerError('acceptance boundary tag, tree, or ancestry mismatch')


def establish_boundary(repo: Path, commit: str, tag_object: str, bootstrap_run_id: int) -> Path:
    """Append the post-commit reference; host must separately verify and lock it."""
    repo = Path(repo).resolve()
    record = {'schema_version': 1, 'tag_name': BOUNDARY_TAG, 'acceptance_commit': commit,
              'acceptance_tree': _git(repo, 'rev-parse', commit + '^{tree}').strip(),
              'tag_object': tag_object, 'bootstrap_run_id': bootstrap_run_id}
    _check_boundary(repo, record)
    path = repo / BOUNDARY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(_encode(record))
    return path


def _github_json(repo: Path, suffix: str, *, missing_ok: bool = False):
    remote = _git(repo, 'remote', 'get-url', 'origin').strip().removesuffix('.git')
    if remote not in {f'https://github.com/{IDENTITY}', f'git@github.com:{IDENTITY}'}:
        raise LedgerError('GitHub evidence repository identity mismatch')
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            headers['Authorization'] = 'Bearer ' + token
    try:
        url = f'https://api.github.com/repos/{IDENTITY}' + ('/' + suffix if suffix else '')
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        raise LedgerError('GitHub acceptance evidence unavailable') from None
    except Exception:
        raise LedgerError('GitHub acceptance evidence unavailable') from None


def _remote_acceptance_tag(repo: Path):
    repository = _github_json(repo, '')
    if repository.get('full_name') != IDENTITY or repository.get('private') is not False:
        raise LedgerError('bootstrap requires readable expected public repository')
    return _github_json(repo, 'git/ref/tags/' + BOUNDARY_TAG, missing_ok=True)


def _verify_boundary_remote(repo: Path, record: dict) -> None:
    reference = _github_json(repo, 'git/ref/tags/' + BOUNDARY_TAG)
    tag = _github_json(repo, 'git/tags/' + record['tag_object'])
    run = _github_json(repo, 'actions/runs/' + str(record['bootstrap_run_id']))
    if (reference['object']['type'] != 'tag' or reference['object']['sha'] != record['tag_object']
            or tag['object']['type'] != 'commit' or tag['object']['sha'] != record['acceptance_commit']
            or run['head_sha'] != record['acceptance_commit'] or run['event'] != 'push'
            or run['conclusion'] != 'success' or run['path'] != '.github/workflows/ci.yml'):
        raise LedgerError('remote acceptance tag or successful bootstrap run mismatch')


def verify(repo: Path, *, integrity_only: bool = False, witness: bool = False) -> dict:
    repo = Path(repo).resolve()
    root = repo / 'ledger'
    if _git(repo, 'rev-parse', '--is-shallow-repository').strip() != 'false':
        raise LedgerError('shallow history cannot prove append-only ledger')
    receipts = receipt_paths(root)
    working = {}
    for path in receipts:
        if path.is_symlink():
            raise LedgerError('symlink receipt is forbidden')
        working[path.relative_to(root).as_posix()] = _validate(path.read_bytes(), path.relative_to(root), root)
    for path in root.rglob('*'):
        if path.is_symlink():
            raise LedgerError('ledger symlinks are forbidden')
        if path.is_file() and not (path in receipts or path == repo / BOUNDARY_PATH
                                  or (path.parent == root / 'definitions' and path.suffix == '.toml')):
            raise LedgerError('unexpected ledger file')
    for args in [('diff', '--no-ext-diff', '--no-textconv', '--name-status', '--no-renames', 'HEAD'),
                 ('diff', '--cached', '--no-ext-diff', '--no-textconv', '--name-status', '--no-renames')]:
        for line in _git(repo, *args).splitlines():
            if not line.split('\t', 1)[-1].startswith('ledger/'):
                continue
            if not line.startswith('A\t'):
                raise LedgerError('existing ledger files cannot be changed or deleted')
    for entry in _git(repo, 'ls-files', '--stage', '-z').split('\0'):
        if not entry:
            continue
        metadata, name = entry.split('\t', 1)
        if not name.startswith('ledger/'):
            continue
        mode, oid, stage = metadata.split()
        if mode != '100644' or stage != '0':
            raise LedgerError('ledger index must contain ordinary, resolved data files')
        if read_object(repo, oid) != (repo / name).read_bytes():
            raise LedgerError('staged ledger content differs from verified working content')
    introductions = {}
    boundary_origins = set()
    ledger_commits = set()
    trees = {}

    def tree(commit):
        if commit not in trees:
            trees[commit] = _tree_blobs(repo, commit)
        return trees[commit]
    # Enumerate the full reachable DAG without path simplification. Compare every
    # merge parent, including edges TREESAME to a different parent.
    commits = _git(repo, 'rev-list', '--all', '--full-history').splitlines()
    for commit in commits:
        committed_at = _aware(_git(repo, 'show', '-s', '--format=%cI', commit).strip())
        parents = _git(repo, 'rev-list', '--parents', '-n', '1', commit).split()[1:]
        additions = set()
        for parent in parents or [None]:
            args = ([parent, commit] if parent else ['--root', commit])
            changes = _git(repo, 'diff-tree', '--no-commit-id', '--name-status', '-r',
                           '--no-renames', *args)
            for line in changes.splitlines():
                status, name = line.split('\t', 1)
                if not name.startswith('ledger/'):
                    continue
                ledger_commits.add(commit)
                if status != 'A':
                    raise LedgerError('git history contains a ledger back-edit (including merge parent edges)')
                additions.add(name)
        for name in additions:
            if name == BOUNDARY_PATH:
                if not any(name in tree(parent)
                           for parent in parents):
                    boundary_origins.add(commit)
            if not name.startswith('ledger/forecasts/'):
                continue
            raw = read_object(repo, tree(commit)[name])
            payload = json.loads(raw)
            frozen = None
            if payload.get('definition') is not None:
                version = payload['definition']['version']
                if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', version):
                    raise LedgerError('invalid definition version')
                try:
                    frozen = read_object(repo, tree(commit)[f'ledger/definitions/{version}.toml'])
                except (LedgerError, KeyError):
                    raise LedgerError('definition missing at receipt commit') from None
            existed_in_parent = any(name in tree(parent)
                                    for parent in parents)
            _validate(raw, Path(name).relative_to('ledger'), root,
                      None if existed_in_parent else committed_at, frozen)
            if not existed_in_parent:
                introductions[(commit, name)] = payload
    now = datetime.now(timezone.utc)
    if any(_aware(payload['issued_at']) > now for payload in introductions.values()):
        raise LedgerError('historical receipt issue time is in the future on a reachable ref')
    historical_names = {Path(name).relative_to('ledger').as_posix() for _, name in introductions}
    pending = 0
    for name, payload in working.items():
        if _aware(payload['issued_at']) > now:
            raise LedgerError('receipt issue time is in the future')
        if name not in historical_names:
            deadline = datetime.combine(date.fromisoformat(payload['target_date']), time.min, ET)
            if now >= deadline:
                raise LedgerError('uncommitted receipt target day has already begun')
            pending += 1
    record = None
    acceptance = 'unanchored' if introductions or pending else 'bootstrap_no_receipts'
    if (repo / BOUNDARY_PATH).exists():
        raw = (repo / BOUNDARY_PATH).read_bytes()
        record = json.loads(raw)
        if _encode(record) != raw:
            raise LedgerError('noncanonical acceptance boundary')
        _check_boundary(repo, record)
        if len(boundary_origins) > 1:
            raise LedgerError('acceptance boundary has multiple origins')
        if boundary_origins:
            origin = next(iter(boundary_origins))
            if origin == record['acceptance_commit'] or not _ancestor(repo, record['acceptance_commit'], origin):
                raise LedgerError('acceptance boundary must reference an earlier code commit')
            if (not _ancestor(repo, origin, 'HEAD')
                    or read_object(repo, tree(origin)[BOUNDARY_PATH]) != raw):
                raise LedgerError('acceptance boundary differs from its append-only origin')
            acceptance = 'anchored_local'
        else:
            acceptance = 'pending_boundary_commit'
    historical = {}
    prospective = {}
    # A DAG can have multiple incomparable first introductions of identical
    # content. Keep the minimal ancestry frontier; never order it by dates.
    first_seen = {
        (commit, name): payload for (commit, name), payload in introductions.items()
        if not any(other != commit and candidate == name and _ancestor(repo, other, commit)
                   for other, candidate in introductions)
    }
    statuses = {name: 'pending_commit' for name in working if name not in historical_names}
    for (commit, name), payload in first_seen.items():
        if (acceptance == 'anchored_local' and commit != record['acceptance_commit']
                and _ancestor(repo, commit, record['acceptance_commit'])):
            historical[(commit, name)] = payload
        else:
            prospective[(commit, name)] = payload
    historical_paths = {name for _, name in historical}
    prospective_paths = {name for _, name in prospective}
    for name in historical_paths | prospective_paths:
        statuses[Path(name).relative_to('ledger').as_posix()] = (
            ('pending_witness' if record else 'unanchored') if name in prospective_paths
            else 'historical_not_required')
    witnessed = 0
    witnessed_origins = 0
    if witness:
        if pending:
            raise LedgerError('uncommitted receipt timing is pending; use --integrity-only before commit')
        if acceptance == 'pending_boundary_commit' or (introductions and acceptance != 'anchored_local'):
            raise LedgerError('witness verification requires committed acceptance boundary')
        if record:
            _verify_boundary_remote(repo, record)
            acceptance = 'anchored_remote'
        elif _remote_acceptance_tag(repo) is not None:
            raise LedgerError('remote acceptance anchor exists but boundary policy is absent')
        witnesses = _push_witnesses(repo) if prospective else []
        for name in {name for _, name in prospective}:
            origins = [(commit, payload) for (commit, candidate), payload in prospective.items() if candidate == name]
            payload = origins[0][1]
            issued = _aware(payload['issued_at'])
            deadline = datetime.combine(date.fromisoformat(payload['target_date']), time.min, ET)
            for commit, _ in origins:
                if not any(issued <= observed < deadline and _ancestor(repo, commit, head)
                           for head, observed in witnesses):
                    raise LedgerError('first-seen receipt origin lacks an independent push witness before target day')
                witnessed_origins += 1
            witnessed += 1
            statuses[Path(name).relative_to('ledger').as_posix()] = 'witnessed_existence'
    return {'receipts': len(receipts), 'history_commits': len(ledger_commits),
            'historical_receipt_additions': len(introductions), 'pending_receipts': pending,
            'timing': 'witness_checked' if witness else 'unverified_integrity_only',
            'witnessed_receipts': witnessed, 'witnessed_origins': witnessed_origins,
            'historical_receipts': len(historical_paths - prospective_paths),
            'prospective_receipts': len(prospective_paths),
            'historical_origins': len(historical), 'prospective_origins': len(prospective),
            'first_seen_commits': {
                Path(name).relative_to('ledger').as_posix(): sorted(commit for commit, candidate in first_seen if candidate == name)
                for name in {name for _, name in first_seen}}, 'acceptance': acceptance,
            'receipt_status': statuses, 'public_visibility': 'not_inferred'}


def select_receipt(repo: Path, forecaster_id: str, target_date: date) -> dict | None:
    """Select by integrity locally; report timing status without network gating."""
    verification = verify(repo, integrity_only=True)
    candidates = []
    root = Path(repo) / 'ledger'
    for path in receipt_paths(root):
        payload = _validate(path.read_bytes(), path.relative_to(root), root)
        if payload['forecaster_id'] == forecaster_id and payload['target_date'] == target_date.isoformat():
            payload['witness_status'] = verification['receipt_status'][path.relative_to(root).as_posix()]
            candidates.append((_aware(payload['issued_at']), path.stem, payload))
    return max(candidates, key=lambda item: item[:2])[2] if candidates else None


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'definition-hashes', 'establish-boundary'])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--integrity-only', action='store_true',
                        help='check integrity but explicitly do not certify public issue timing')
    modes.add_argument('--witness', action='store_true')
    parser.add_argument('--acceptance-commit')
    parser.add_argument('--tag-object')
    parser.add_argument('--bootstrap-run-id', type=int)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        if args.command == 'definition-hashes':
            result = {str(path.relative_to(args.repo)): sha256(read_definition(path)).hexdigest()
                      for path in sorted((args.repo / 'ledger/definitions').glob('*.toml'))}
        elif args.command == 'establish-boundary':
            if not all([args.acceptance_commit, args.tag_object, args.bootstrap_run_id]):
                raise LedgerError('boundary requires reviewed commit, annotated tag object, and successful run ID')
            path = establish_boundary(args.repo, args.acceptance_commit, args.tag_object, args.bootstrap_run_id)
            result = {'boundary_record': str(path), 'remote_acceptance': 'pending_verification'}
        else:
            result = verify(args.repo, integrity_only=args.integrity_only, witness=args.witness)
        print(json.dumps(result, sort_keys=True))
    except (LedgerError, ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, LedgerError) else 'invalid or unreadable ledger data'
        parser.exit(1, f'ledger verify failed: {reason}\n')


if __name__ == '__main__':
    main()
