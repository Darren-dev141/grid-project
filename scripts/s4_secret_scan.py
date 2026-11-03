"""Scan the exact Git index tree; emit metadata only and fail on candidates."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

RULES = [
    re.compile(rb'(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|sk-(?:proj-)?[A-Za-z0-9_-]{20,})'),
    re.compile(rb'(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[=:]\s*[\x22\x27]?([A-Za-z0-9_+/=-]{24,})'),
    re.compile(rb'(?i)(?:api_key|api%5fkey)=([a-z0-9]{32,})'),
]


def scan(prospective=False):
    root = Path(__file__).resolve().parents[1]
    git = ['git', '-c', f'safe.directory={root.as_posix()}', '-C', str(root)]
    args = ['ls-files', '--stage', '-z']
    if prospective:
        args = ['ls-files', '--cached', '--others', '--exclude-standard', '-z']
    listing = subprocess.run(git + args, capture_output=True, check=True)
    objects = {}
    conflicts = []
    if prospective:
        paths = sorted(set(p for p in listing.stdout.decode().split('\0') if p))
    else:
        for entry in listing.stdout.decode().split('\0'):
            if entry:
                metadata, path = entry.split('\t', 1)
                _, oid, stage = metadata.split()
                if stage != '0' or not re.fullmatch(r'[0-9a-f]{40}', oid):
                    conflicts.append(path)
                objects[path] = oid
        paths = sorted(objects)
    hits, errors, total = [], list(conflicts), 0
    if prospective:
        sys.path.insert(0, str(root / 'src'))
        from grid_pipeline.ledger import read_content
    for path in paths:
        try:
            if prospective:
                checked = root
                for part in Path(path).parts:
                    checked = checked / part
                    if checked.is_symlink():
                        raise OSError('prospective symlink is not a verified commit snapshot')
                raw = read_content(root / path)
            else:
                blob = subprocess.run(git + ['cat-file', 'blob', objects[path]], capture_output=True, check=True)
                raw = blob.stdout
            total += len(raw)
            for rule, pattern in enumerate(RULES, 1):
                for match in pattern.finditer(raw):
                    hits.append({'path': path, 'rule': rule, 'offset': match.start(),
                                 'sha256_prefix': hashlib.sha256(match.group()).hexdigest()[:12]})
        except (OSError, subprocess.CalledProcessError):
            errors.append(path)
    result = {'scope': 'prospective working files' if prospective else 'exact index blobs',
              'files': len(paths), 'bytes': total, 'candidates': hits, 'unreadable': errors}
    print(json.dumps(result, sort_keys=True))
    return bool(hits or errors)


if __name__ == '__main__':
    sys.exit(scan('--prospective' in sys.argv))
