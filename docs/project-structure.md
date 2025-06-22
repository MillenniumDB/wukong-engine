# Project Structure

This document provides a breakdown of the main components in the repository.

```
wukong-engine/
├── data/
├── docs/
├── src/
├── tests/
├── pyproject.toml
├── README.md
└── ...
```

```
wukong_engine/
├── __main__.py  # Entry point
├── config/      # Configuration and environment
├── core/        # Core logic for the engine pipeline
├── documents/   # Document pre-processing
├── extraction/  # Data extraction logic
├── graph/       # Graph database interaction
├── llm/         # LLM interaction
└── utils/       # Utility functions and shared components
```

## Code Packages

- `core/`: Core pipeline logic, data model processing
- `llm/`: Prompt generation and LLM API interaction
- `documents/`: Plain-text preprocessing and parsing
- ...

## Non-Code Folders

- `docs/`: Markdown documentation for the tool and its components
- `tests/`: Unit and integration tests for the core modules
- `examples/`: Example input files and usage workflows
- `config/`: Shared or default configuration files

## Root Files

- `README.md`: Main entrypoint documentation
- `pyproject.toml`: Build and dependency configuration (Poetry)
- `.env.example`: Sample environment variables