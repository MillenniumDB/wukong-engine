# WUKONG Engine

Engine that extracts structured knowledge from unstructured documents with
LLMs and exports it to graph formats (MillenniumDB, Neo4j). Python 3.14,
managed with Poetry. The CLI entry point is `wukong`
(`src/wukong_engine/presentation/cli`).

The docs in `docs/` are the source of truth. Read the relevant one before
working in an area instead of inferring from the code alone:

- `docs/architecture.md`: layering and dependency rules
- `docs/project-structure.md`: what lives where
- `docs/knowledge-model.md`, `docs/workspace.md`, `docs/configuration.md`:
  the domain, workspace layout and config options
- `docs/development.md`: code style, branching and naming conventions

## Commands

```sh
poetry install                                   # includes dev tools (ruff, pyright)
poetry run ruff check src                        # lint
poetry run ruff format src                       # format
poetry run pyright src                           # type-check
poetry run pytest                                # tests (no LLM calls)
poetry run wukong run workspaces/example data/example   # end-to-end run
```

Use `poetry run` so the locked tool versions are used, not a global install.
Lint/type-check `src/` (or the files you touched): `paper/benchmark/` holds
research scripts with their own dependencies and known violations.

## Architecture

Clean architecture with layers `core` (domain), `app` (use cases, services,
ports), `infrastructure` (adapters), `presentation` (CLI), wired together in
`bootstrap`. Dependencies point inward only: `core` imports nothing else,
`app` never imports `infrastructure` or `presentation`, and `presentation`
never imports `infrastructure` (it gets use cases through `bootstrap`).

## Code style

- Ruff selects `ALL` rules, minus a deliberate `ignore` list in
  `pyproject.toml`. New code must pass that config as-is. Don't add
  `# noqa` comments or change the ignore list without asking.
- Google-style docstrings (enforced by Ruff), single quotes, 120-char lines.

## Verification and tests

- `poetry run pytest` runs the small test suite under `tests/`, which never
  calls an LLM. Beyond it, the baseline check is an end-to-end run on the
  example workspace. It calls the configured LLM provider's API (needs
  `.env`, costs money), so ask before running it. `--reset` wipes the
  workspace's stored state.
- Adding tests is welcome where they add real value, e.g. pure domain logic,
  parsing, normalization and serialization. Use pytest under `tests/`,
  mirroring the layout of `src/wukong_engine/`.

## Dependencies

- Runtime dependencies go in the main Poetry group, and tools go in the
  `dev` group.
- The Docker image installs from `requirements.txt`, not Poetry. After
  changing runtime dependencies, regenerate it:
  `poetry export -f requirements.txt --without-hashes -o requirements.txt`

## Git workflow

- Never commit to `main`. Work on `<type>/<short-name>` topic branches, as
  described in `docs/development.md`.
- Commit messages follow `<emoji> <type>(<scope>): <description>` using the
  type table in `docs/development.md`. PR titles use the same format without
  the emoji.
- Topic branches are rebased onto `main` before the PR. Pushing the result
  with `--force-with-lease` is part of the workflow, but confirm before
  doing it.
