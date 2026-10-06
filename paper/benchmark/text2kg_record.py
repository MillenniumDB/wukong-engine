"""Record what a completed extraction run consumed, so its cost survives the workspace.

Job counts, token usage and timing live only in each workspace's staging
database, which is not tracked. For every ontology this writes:

    - `<results>/runs/<onto>.json`, tracked: job and token counts (in total and
      per job type and context level), the run's start and end, the engine
      version and commit, the engine configuration, and hashes of the workspace
      definitions the run was built from
    - `<results>/archive/<onto>/`, not tracked: a compressed copy of the staging
      database and the run's log, kept so that any later analysis can be done
      without re-running

An ontology that already has a run record is skipped unless `--force` is
given. The archive is large; back it up outside the repository.

Example:
    python3 paper/benchmark/text2kg_record.py \
        --results paper/benchmark/results --prefix tekgen_ --config config/default.toml
"""

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_setup import ONTOLOGIES  # noqa: E402

# Repository root, for the engine version and commit
ROOT = Path(__file__).resolve().parents[2]

# Workspace definitions a run is built from
DEFINITIONS = ('knowledge_model.json', 'document_collections.json', 'text2kg_mapping.json')

TOKEN_COLUMNS = ('input_tokens', 'cached_tokens', 'cache_write_tokens', 'output_tokens', 'reasoning_tokens')


def read_usage(staging: Path) -> dict[str, object]:
    """Read job counts, token usage and timing from a staging database.

    Args:
        staging: Path to the workspace's `extraction.db`.

    Returns:
        The number of documents and chunks; job, failed-job and token counts in total and per job type and context
        level; the first job's creation and the last job's completion as ISO timestamps; and the seconds between them.
    """
    sums = ', '.join(f'COALESCE(SUM({column}), 0)' for column in TOKEN_COLUMNS)
    connection = sqlite3.connect(f'file:{staging}?mode=ro', uri=True)
    try:
        documents = connection.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        chunks = connection.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
        total = connection.execute(
            f"SELECT COUNT(*), COALESCE(SUM(job_status != 'COMPLETED'), 0), {sums} FROM extraction_jobs",  # noqa: S608
        ).fetchone()
        by_kind = connection.execute(
            f"SELECT job_type, context_level, COUNT(*), COALESCE(SUM(job_status != 'COMPLETED'), 0), {sums}"  # noqa: S608
            ' FROM extraction_jobs GROUP BY job_type, context_level ORDER BY job_type, context_level',
        ).fetchall()
        started, finished = connection.execute(
            'SELECT MIN(created_at), MAX(finished_at) FROM extraction_jobs',
        ).fetchone()
    finally:
        connection.close()

    def counts(row: tuple[int, ...]) -> dict[str, int]:
        return {'jobs': row[0], 'failed': row[1], **dict(zip(TOKEN_COLUMNS, row[2:], strict=True))}

    def timestamp(millis: int | None) -> str | None:
        return datetime.fromtimestamp(millis / 1000, UTC).isoformat() if millis else None

    return {
        'documents': documents,
        'chunks': chunks,
        'total': counts(total),
        'by_job': [
            {'job_type': job_type, 'context_level': level, **counts(row)} for job_type, level, *row in by_kind
        ],
        'started': timestamp(started),
        'finished': timestamp(finished),
        'seconds': round((finished - started) / 1000) if started and finished else 0,
    }


def engine_revision() -> dict[str, object]:
    """Identify the engine the run was made with.

    Returns:
        The engine version from `pyproject.toml`, the current commit, and whether the working tree had uncommitted
        changes. The commit is None outside a git checkout.
    """
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    try:
        commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True, capture_output=True, text=True,  # noqa: S607
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ['git', 'status', '--porcelain', '--untracked-files=no'],  # noqa: S607
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {'version': version, 'commit': commit, 'uncommitted_changes': dirty}


def sha256(path: Path) -> str:
    """Hash a file.

    Args:
        path: File to hash.

    Returns:
        The hex SHA-256 digest of the file's bytes.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(staging: Path, log: Path, out_dir: Path) -> None:
    """Copy the staging database and the run's log into the archive, compressed.

    The database is copied through SQLite's backup API, since it runs in WAL mode and a plain file copy could miss
    committed pages still held in the write-ahead log.

    Args:
        staging: Path to the workspace's `extraction.db`.
        log: Path to the run's log; skipped if it does not exist.
        out_dir: Archive directory for this ontology, created if needed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / 'extraction.db'
        source = sqlite3.connect(f'file:{staging}?mode=ro', uri=True)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        finally:
            source.close()
            target.close()
        with snapshot.open('rb') as raw, gzip.open(out_dir / 'extraction.db.gz', 'wb') as packed:
            shutil.copyfileobj(raw, packed)
    if log.exists():
        with log.open('rb') as raw, gzip.open(out_dir / f'{log.name}.gz', 'wb') as packed:
            shutil.copyfileobj(raw, packed)


def main() -> int:
    """Write the run record of every selected ontology and archive its state.

    Returns:
        The process exit code: 1 if a selected ontology has no staging database, 0 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', type=Path, default=Path('paper/benchmark/results'))
    parser.add_argument('--workspace-root', type=Path, default=Path('paper/benchmark/workspaces'))
    parser.add_argument('--prefix', default='tekgen_')
    parser.add_argument('--config', type=Path, default=Path('config/default.toml'), help='Engine config of the run')
    parser.add_argument('--onto', action='append', choices=[*ONTOLOGIES], help='Ontology to record (repeatable)')
    parser.add_argument('--no-archive', action='store_true', help='Write the run records only')
    parser.add_argument('--force', action='store_true', help='Overwrite existing run records')
    args = parser.parse_args()

    engine = engine_revision()
    config = tomllib.loads(args.config.read_text(encoding='utf-8'))
    recorded_at = datetime.now(UTC).isoformat(timespec='seconds')

    missing = []
    for onto in args.onto or [*ONTOLOGIES]:
        workspace = args.workspace_root / f'{args.prefix}{onto}'
        staging = workspace / 'staging' / 'extraction.db'
        if not staging.exists():
            missing.append(onto)
            continue

        # A run is recorded once: re-recording a resumed or skipped run would attach the current config to it
        out = args.results / 'runs' / f'{onto}.json'
        if out.exists() and not args.force:
            print(f'{onto:12s} already recorded -> {out}')
            continue

        record = {
            'ontology': onto,
            'workspace': f'{args.prefix}{onto}',
            'recorded_at': recorded_at,
            'engine': engine,
            'config_file': str(args.config),
            'config': config,
            'definitions': {
                name: sha256(workspace / name) for name in DEFINITIONS if (workspace / name).exists()
            },
            'usage': read_usage(staging),
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')

        if not args.no_archive:
            archive(staging, args.results / 'logs' / f'{onto}.log', args.results / 'archive' / onto)

        total = record['usage']['total']
        print(f'{onto:12s} jobs={total["jobs"]} failed={total["failed"]} -> {out}')

    if missing:
        print(f'No staging database for: {", ".join(missing)}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
