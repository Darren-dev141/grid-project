"""Reject partial snapshots before and after running the local S4 checks."""
from hashlib import sha256
from pathlib import Path
import subprocess
import sys


def check_snapshot(repo: Path) -> str:
    repo = Path(repo).resolve()
    git = ['git', '-c', f'safe.directory={repo.as_posix()}', '-C', str(repo)]
    for args in [('diff', '--name-only', '-z'),
                 ('ls-files', '--others', '--exclude-standard', '-z')]:
        result = subprocess.run([*git, *args], capture_output=True, check=True)
        if result.stdout:
            raise ValueError('unsafe staged snapshot: unstaged or untracked files exist')
    index = subprocess.run([*git, 'ls-files', '--stage', '-z'], capture_output=True, check=True)
    if any(b' 0\t' not in entry for entry in index.stdout.split(b'\0') if entry):
        raise ValueError('unsafe staged snapshot: unresolved index entries')
    return sha256(index.stdout).hexdigest()


def main():
    repo = Path(__file__).resolve().parents[2]
    try:
        before = check_snapshot(repo)
        commands = [[sys.executable, 'scripts/s4_secret_scan.py'],
                    [sys.executable, '-m', 'pytest', '-ra'],
                    [sys.executable, '-m', 'grid_pipeline.ledger', 'verify', '--integrity-only']]
        for command in commands:
            subprocess.run(command, cwd=repo, check=True)
        if check_snapshot(repo) != before:
            raise ValueError('staged snapshot changed during checks')
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'pre-commit checks failed: {exc}', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
