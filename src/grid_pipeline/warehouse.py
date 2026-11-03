"""Run the local dbt project with isolated artifacts and loud failures."""
import os
from pathlib import Path
import subprocess
import sys


def build(database: Path, *, select: list[str] | None = None,
          artifact_root: Path | None = None) -> None:
    """Build and test dbt, raising on failure. No ingestion or dependency install.

    Uses the running interpreter's installed dbt package. Callers may select a
    sub-DAG while the retired price models still require a verified node variable.
    """
    database = Path(database).resolve()
    artifacts = Path(artifact_root).resolve() if artifact_root else database.parent / 'dbt'
    project = Path(__file__).resolve().parents[2] / 'dbt'
    env = os.environ.copy()
    env['GRID_DATABASE'] = str(database)
    env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
    args = [sys.executable, '-m', 'grid_pipeline.dbt_runner',
            'build', '--indirect-selection', 'cautious',
            '--project-dir', str(project), '--profiles-dir', str(project),
            '--target-path', str(artifacts / 'target'), '--log-path', str(artifacts / 'logs')]
    if select:
        args.extend(['--select', *select])
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f'dbt build failed ({result.returncode}):\n{result.stdout}{result.stderr}')
