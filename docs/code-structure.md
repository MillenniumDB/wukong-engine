# Code Structure Overview

## `src/`

Main logic of the tool.

- `core/`
  - `validator.py`: Validates data models
  - `config_loader.py`: Loads and validates config files

- `cli/`
  - `main.py`: Entry point for CLI
  - `commands.py`: CLI subcommand definitions

- `utils/`
  - Helper functions and shared logic

## `tests/`

Pytest-based tests covering validation, configuration, and CLI behavior.
