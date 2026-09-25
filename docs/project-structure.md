<!-- omit from toc -->
# 🧱 Project Structure

This document provides an overview of how the repository is organized.

<!-- omit from toc -->
## 📚 Table of Contents
- [🌳 Top Level](#-top-level)
- [💻 Source Code](#-source-code)
- [⚙️ Configuration](#️-configuration)
- [🗂️ Workspaces](#️-workspaces)
- [📄 Data](#-data)
- [🧪 Tests](#-tests)
- [📜 Scripts](#-scripts)
- [📰 Paper](#-paper)
- [📖 Documentation](#-documentation)
- [🎨 Assets](#-assets)
- [🐙 GitHub](#-github)
- [🗃️ Project Files](#️-project-files)

## 🌳 Top Level

```sh
wukong-engine/
├── src/wukong_engine/   # The engine itself
├── config/              # Engine configuration files
├── workspaces/          # Knowledge models, run state and exports
├── data/                # Input document corpora
├── tests/               # Test suite
├── scripts/             # Docker helper scripts
├── paper/               # Research paper draft and benchmark harness
├── docs/                # Extended documentation
├── assets/              # Logos and other static files
└── .github/             # Community standards and issue/PR templates
```

[📚 Back to Table of Contents](#-table-of-contents)

## 💻 Source Code

The engine is implemented in **Python** and follows a layered architecture based on **clean architecture** principles, which are described in the [Architecture Guidelines](/docs/architecture.md).

The source lives in `src/` as a package named `wukong_engine`, organized into five layers:

```sh
src/wukong_engine/
├── core/            # Domain model, with no dependencies on anything else
│   ├── knowledge/   # Knowledge model (entity/relationship types, fields) and extracted elements
│   ├── documents/   # Documents, chunks, collections and context levels
│   ├── extraction/  # Extraction tasks, retrieval modes and compatibility rules
│   ├── pipeline/    # Pipeline steps, checkpoints and statuses
│   └── shared/      # Identity primitives and regex patterns
├── app/             # Use cases, services and ports (the engine's behaviour)
│   ├── workspace/           # Workspace layout, paths and validation
│   ├── model_ingestion/     # Loading the knowledge model and document registry
│   ├── document_ingestion/  # Reading, registering and segmenting documents
│   ├── data_extraction/     # Entity and relationship extraction, batching, retries, metrics
│   ├── knowledge_export/    # Rendering the extracted knowledge
│   ├── staging/             # Ports for the durable staging stores
│   ├── llm/                 # LLM abstractions and the model registry
│   ├── config/              # Application configuration model
│   └── workflows/           # The knowledge construction pipeline
├── infrastructure/  # Concrete adapters for the ports declared in `app`
│   ├── definitions/  # Loading knowledge models and document registries from JSON
│   ├── persistence/  # SQLite staging database
│   ├── storage/      # Filesystem document loading
│   ├── chunking/     # Recursive, boundary-aware segmentation and tokenization
│   ├── llm/          # OpenAI client
│   ├── export/graph/ # MillenniumDB and Neo4j exporters
│   ├── config/       # TOML loading and environment variables
│   ├── normalization/# Primary key normalization
│   ├── serialization/# Property value serialization
│   └── logging/      # Logging setup
├── bootstrap/       # Composition roots that wire everything together
└── presentation/    # Entry points — currently the CLI
```

Note that `core/knowledge/` holds the **knowledge model** and the extracted entities and relationships, which are representation-independent. Only `infrastructure/export/graph/` knows about graphs, because that is where the result is rendered into graph database formats.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Configuration

The `config/` directory holds engine configuration files in **TOML** format:

- `default.toml`: The default configuration, used when `--config` is not given. It runs the entire pipeline with the recommended values and is fully commented.

Any other `.toml` file you place here is ignored by **Git**, so you can keep your own configurations alongside the default one without them ending up in version control.

The available options are described in the [Configuration](/docs/configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🗂️ Workspaces

A **workspace** holds everything that defines and records a run: the knowledge model, the document collection registry, the staging database and the exports.

```sh
workspaces/example/
├── knowledge_model.json        # what knowledge to extract
├── document_collections.json   # which documents to read
├── staging/                    # created by the engine (not tracked)
└── exports/                    # created by the engine (not tracked)
```

Only the `example` workspace's two JSON definitions are tracked by **Git**. Your own workspaces, and the state the engine generates inside any workspace, are ignored.

The workspace layout is described in the [Workspace](/docs/workspace.md) documentation, and the knowledge model format in the [Knowledge Model](/docs/knowledge-model.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 📄 Data

The `data/` directory holds the input corpora — plain text documents, which the engine only ever reads. A small **example** corpus is tracked so the tool can be run immediately after cloning:

```sh
data/example/
├── missions/      # mission reports
│   ├── artemis_7_relay_deployment.txt
│   └── kepler_12_kuiper_survey.txt
├── crew/          # crew dossiers
│   ├── okonkwo_amara.txt
│   ├── vance_theo.txt
│   └── liang_mei.txt
└── incidents/     # incident reports
    ├── inc_0412_hull_breach.txt
    └── inc_0517_comms_blackout.txt
```

The corpus is a small set of invented documents from a fictional deep-space agency. The three subdirectories correspond to the three document collections declared in `workspaces/example/document_collections.json`, and the documents cross-reference each other so that the run produces a genuinely connected result.

Everything else under `data/` is ignored by **Git**, so your own corpora can live here without being committed.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧪 Tests

The `tests/` directory is meant to contain the test suite for the engine. This is currently **not implemented**.

[📚 Back to Table of Contents](#-table-of-contents)

## 📜 Scripts

The `scripts/` directory contains **Bash** helper scripts for the **Docker** workflow:

- `build_image.sh`: Builds the `wukong-engine:latest` **Docker** image.
- `wukong_run.sh`: Runs the engine inside a container, mounting the workspace, data directory and configuration file.

[📚 Back to Table of Contents](#-table-of-contents)

## 📰 Paper

The `paper/` directory holds the research paper and the material behind its evaluation:

- `paper-draft.md`: The current paper draft.
- `benchmark.md`: The full protocol, results and analysis of the Text2KGBench evaluation.
- `benchmark/`: The harness for that evaluation — scripts to compile ontologies into knowledge models, run the engine, convert its output back to triples, score it and report on it.

[📚 Back to Table of Contents](#-table-of-contents)

## 📖 Documentation

The `README.md` in the root of the project covers what the engine is, how to set it up, and how to run it.

The extended documentation lives in `docs/`:

- `knowledge-model.md`: The knowledge model format — entity types, relationship types, fields, identity and merging.
- `workspace.md`: The workspace layout, the document collection registry and the export output.
- `configuration.md`: Environment variables and the engine configuration file.
- `architecture.md`: The design principles and layering the implementation follows.
- `development.md`: Development guidelines, code style, testing practices and branching/naming conventions.
- `project-structure.md`: This document.

[📚 Back to Table of Contents](#-table-of-contents)

## 🎨 Assets

The `assets/` directory holds static files used by the project:

- `logo/`: The project's logo in several formats for different use cases (`banner/`, `icon/`, `stacked/`).

[📚 Back to Table of Contents](#-table-of-contents)

## 🐙 GitHub

The `.github/` directory holds the files **GitHub** uses to manage community standards and collaboration workflows:

- `CONTRIBUTING.md`: How to set up the project as an external contributor and how to submit changes.
- `CODE_OF_CONDUCT.md`: Expected behavior and community standards.
- `ISSUE_TEMPLATE/`: Templates and settings for creating issues.
- `PULL_REQUEST_TEMPLATE.md`: Template for creating pull requests.

[📚 Back to Table of Contents](#-table-of-contents)

## 🗃️ Project Files

The root directory contains:

- `pyproject.toml`: Project metadata, dependencies and tooling configuration (**Ruff**, **Pyright**).
- `poetry.lock`: Exact dependency versions resolved by **Poetry**.
- `requirements.txt`: The same dependency set in a **pip**-compatible format.
- `CHANGELOG.md`: Notable changes per released version.
- `LICENSE`: The license under which the project is distributed.
- `.env.example`: Template for the required environment variables.
- `Dockerfile`: Base image, dependencies and build steps for the **Docker** image.
- `.dockerignore`: Paths excluded from the **Docker** build context.
- `.gitignore`: Paths excluded from version control.
- `.gitattributes`: Per-path **Git** attributes, such as line endings.

[📚 Back to Table of Contents](#-table-of-contents)
