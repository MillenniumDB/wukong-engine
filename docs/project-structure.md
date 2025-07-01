<!-- omit from toc -->
# 🧱 Project Structure

This document provides a detailed overview of the project structure.

<!-- omit from toc -->
## 📚 Table of Contents
- [💻 Source Code](#-source-code)
- [⚙️ Configuration](#️-configuration)
- [🗂️ Data](#️-data)
- [🧪 Tests](#-tests)
- [📖 Documentation](#-documentation)
- [🐙 GitHub](#-github)
- [🗃️ Project Files](#️-project-files)

## 💻 Source Code

The engine is implemented in **Python** and follows a modular architecture to facilitate maintainability and extensibility.
The source code is organized into a package named `wukong_engine`, which contains all the necessary modules and sub-packages to run the engine.
The package structure is as follows:

```sh
src/wukong_engine/
├── __main__.py
├── config/
├── core/
├── documents/
├── extraction/
├── graph/
├── llm/
└── utils/
```

The `__main__.py` file enables the package to be run as a script. It handles argument parsing, initializes logging, and executes the main pipeline.

The sub-packages contain modules that serve the following purposes:

- `config`: Loading and validating engine configuration.
- `core`: Main orchestration, including the engine pipeline execution and data model loading/validation.
- `documents`: Document preparation and pre-processing.
- `extraction`: Data extraction from documents and post-processing (cleaning and deduplication).
- `graph`: Exporting data to a knowledge graph format.
- `llm`: Communication with LLM APIs and prompting.
- `utils`: Shared utilities like logging, file/text helpers, and reusable design patterns.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Configuration

The configuration for the engine is managed inside the `config/` directory (in the root of the project).
The configuration is currently defined in a single file:

- `config.toml`: Defines customizable behavior for the tool, such as choosing which steps of the pipeline to execute, among other functional parameters.

The details for the engine configuration can be found in the [Configuration](./configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🗂️ Data

The engine processes documents and generates a knowledge graph based on a data model defined by the user.
To achieve this, the user must provide a data directory with a specific structure, containing the **documents** and the **data model**.

For testing purposes, an **example** data directory is provided inside the `data/` directory, containing the following:

```sh
data/example/
├── docs/
│   ├── original/
│   │   ├── document_1.pdf
│   │   └── document_2.pdf
│   └── text/
│       ├── document_1.txt
│       └── document_2.txt
└── data_model.json
```

- The `docs/original/` directory contains the original documents in their native **PDF** formats (these are only for the user, the engine never uses them).
- The `docs/text/` directory contains the **plain text** versions of the documents, to be used by the engine.
- The `data_model.json` file contains the example data model in **JSON** format.

To make use of the engine, the user must first create and set up their own data directory with the same structure as the example above.
The details for building your own data model schema can be found in the [Data Model](./data-model.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧪 Tests

The `tests/` directory is meant to contain a test suite for the engine. This is currently **not implemented**.

[📚 Back to Table of Contents](#-table-of-contents)

## 📖 Documentation

The `README.md` file located in the root of the project contains an overview of the project, its purpose, and how to set it up and run it.

The extended documentation for the central aspects of the project is organized in the `docs/` directory, which includes:

- `configuration.md`: Configuration file format and available options for engine configuration.
- `data-model.md`: Data model format and available options for specifying entities and relations.
- `development.md`: Development guidelines, including code style and testing practices.
- `project-structure.md`: Project structure and organization of the source code.

[📚 Back to Table of Contents](#-table-of-contents)

## 🐙 GitHub

The `.github/` directory contains repository-specific files used by **GitHub** to manage community standards and collaboration workflows. It currently includes:

- `CONTRIBUTING.md`: Guidelines for contributing to the project, including how to set up the project for external contributors, naming conventions, and how to submit changes.
- `CODE_OF_CONDUCT.md`: Code of conduct for contributors, outlining expected behavior and community standards.
- `ISSUE_TEMPLATE/`: Directory containing templates and settings for creating issues.
- `PULL_REQUEST_TEMPLATE.md`: Template for creating pull requests.

[📚 Back to Table of Contents](#-table-of-contents)

## 🗃️ Project Files

The root directory of the project contains several other files that serve specific purposes:

- `pyproject.toml`: Project settings, dependencies and tooling configuration.
- `CHANGELOG.md`: Records changes per released version of the project.
- `LICENSE`: The license under which the project is distributed.
- `poetry.lock`: Lock file for **Poetry**, containing the exact versions of dependencies used in the project.
- `requirements.txt`: Equivalent to `poetry.lock`, but in a format compatible with **pip**.
- `.env.example`: Example file for environment variables.
- `.gitignore`: Specifies files and directories that should be ignored by **Git** for source control.

[📚 Back to Table of Contents](#-table-of-contents)