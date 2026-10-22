"""Check that the experiment code and data of the paper are intact: no API key, no cost, a few seconds.

    - every Python file under paper/ and tests/ compiles, and every shell script parses (bash -n);
    - every JSON, JSON Lines and TOML file under paper/, config/ and workspaces/ parses;
    - every knowledge model under paper/ and workspaces/ loads and validates in the engine.

Usage (Python 3.14 environment with the engine installed; see paper/REPRODUCE.md):
    python tests/check_paper_files.py

Exits with status 0 when every check passes.
"""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def files(folders: tuple[str, ...], suffix: str) -> list[Path]:
    """Files with a suffix under some top-level folders, sorted."""
    return sorted(p for folder in folders for p in (ROOT / folder).rglob(f'*{suffix}') if p.is_file())


def check_all(what: str, paths: list[Path], check: object) -> list[str]:
    """Apply a check to every file; print one summary line and return the failures."""
    failures = []
    for path in paths:
        try:
            check(path)
        except Exception as exc:  # noqa: BLE001 - any error is a failure to report
            failures.append(f'{path.relative_to(ROOT)}: {type(exc).__name__}: {str(exc)[:200]}')
    print(f'  [{"ok" if not failures else "FAIL"}] {what}: {len(paths) - len(failures)} of {len(paths)}')
    for failure in failures[:10]:
        print(f'         {failure}')
    return failures


def compiles(path: Path) -> None:
    """Compile a Python file without writing bytecode."""
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')


def bash_parses(path: Path) -> None:
    """Parse a shell script with bash -n."""
    result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if result.returncode:
        raise SyntaxError(result.stderr.strip())


def json_parses(path: Path) -> None:
    """Parse a JSON file."""
    json.loads(path.read_text(encoding='utf-8'))


def jsonl_parses(path: Path) -> None:
    """Parse every non-empty line of a JSON Lines file."""
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'line {number}: {exc}') from exc


def toml_parses(path: Path) -> None:
    """Parse a TOML file."""
    tomllib.loads(path.read_text(encoding='utf-8'))


def model_loads(path: Path) -> None:
    """Load and validate a knowledge model with the engine's own loader."""
    from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider  # noqa: PLC0415

    LocalKnowledgeModelProvider().get(str(path))


def main() -> int:
    """Run every check and report."""
    data = ('paper', 'config', 'workspaces')
    failures = []
    failures += check_all('Python files compile', files(('paper', 'tests'), '.py'), compiles)
    failures += check_all('shell scripts parse', files(('paper', 'scripts'), '.sh'), bash_parses)
    failures += check_all('JSON files parse', files(data, '.json'), json_parses)
    failures += check_all('JSON Lines files parse', files(data, '.jsonl'), jsonl_parses)
    failures += check_all('TOML files parse', files(data, '.toml'), toml_parses)
    models = files(('paper', 'workspaces'), 'knowledge_model.json')
    failures += check_all('knowledge models load in the engine', models, model_loads)
    print('PASS' if not failures else f'FAIL ({len(failures)} files)')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
