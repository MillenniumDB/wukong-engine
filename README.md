<!-- Banner Logo -->
<p align="center">
  <img src="/assets/logo/banner/1024-rounded.png" alt="Logo" width="100%"/>
</p>

<!-- omit from toc -->
# WUKONG Engine

Engine for extracting structured knowledge from unstructured documents using the power of LLMs, exportable to graph and other formats.

<!-- omit from toc -->
## 📚 Table of Contents
- [🐵 WUKONG: Weaving Unstructured Knowledge - Organize, Normalize, Generate](#-wukong-weaving-unstructured-knowledge---organize-normalize-generate)
- [⚙️ Setup](#️-setup)
  - [Pre-requisites](#pre-requisites)
  - [Installation](#installation)
  - [Environment](#environment)
- [🚀 Usage](#-usage)
  - [Workspace and Data](#workspace-and-data)
  - [Running the Engine](#running-the-engine)
  - [Output](#output)
  - [Engine Configuration](#engine-configuration)
- [🐳 Docker Support](#-docker-support)
  - [Building the Image](#building-the-image)
  - [Running the Engine with Docker](#running-the-engine-with-docker)
  - [Important Considerations](#important-considerations)
- [🤝 Contributing](#-contributing)

## 🐵 WUKONG: Weaving Unstructured Knowledge - Organize, Normalize, Generate

The **WUKONG** engine turns a collection of **plain text documents** into a typed, deduplicated, provenance-carrying body of **structured knowledge** that conforms, by construction, to a user-supplied **knowledge model**.

The knowledge model is a declarative file that specifies which entity and relationship types exist, which fields they carry, how each field is obtained, which documents each type should be read from, and — critically — what makes two extracted objects *the same object*. Everything downstream is derived from it: the prompts sent to the **LLM**, the structure it must reply with, and the validation, identity, deduplication and merging that follow.

A few properties are worth calling out:

- **Schema-guided.** The schema is an input, not an output. Output that cannot be validated against the knowledge model never becomes part of the result.
- **Grounded relationships.** Relationships are never extracted as free text triples. The **LLM** is shown a candidate set of already-extracted entities and may only connect those, so endpoints are valid by construction.
- **Declared identity.** Two objects are the same object when the knowledge model says they are — a normalized primary key and an explicit identity policy — rather than when a similarity threshold happens to fire.
- **Provenance by default.** The source documents and their chunks are part of the output, and every extracted object links back to the exact text it was read from.
- **Resumable and cost-aware.** Work is decomposed into durable, independently retryable units, so long runs over large corpora can be interrupted, resumed and partially re-run, either interactively or through cheaper asynchronous batch execution.

Extraction and representation are kept separate: what the engine produces is a canonical result, and a final rendering stage emits it in a target format. **Property graph** formats are what ship today (`MillenniumDB`, `Neo4j`), which makes the output well suited to **information retrieval**, **data integration** and **AI agents**.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Setup

### Pre-requisites

Before setting up the project, ensure you have the following software installed:

- **Python 3.14+**

    The engine requires `Python 3.14` or higher.
    A very useful tool for managing **Python** versions is [pyenv](https://github.com/pyenv/pyenv).

- **Poetry 2.1+** (recommended)

    For managing dependencies, virtual environments and packaging.
    Install by following the [Poetry installation guide](https://python-poetry.org/docs/#installation).

    If you prefer not to use **Poetry**, you can install dependencies and manage virtual environments manually using **pip**.

- **Git**

    For version control and cloning the repository.

- **Docker** (optional)

    For running the engine in a containerized environment without needing to install **Python** or dependencies on your system.
    This is especially recommended for **MacOS** and **Windows** users, since the project is only officially supported on **Linux** platforms.

    For **MacOS** and **Windows** users, install **Docker** by following the [Docker Desktop installation guide](https://docs.docker.com/get-docker/).
    For **Linux** users, if you want to use **Docker**, we recommend following the [Docker Engine installation guide](https://docs.docker.com/engine/install/) for a more native approach.

### Installation

Clone the repository and navigate to the project directory:

```sh
git clone https://github.com/MillenniumDB/wukong-engine.git
cd wukong-engine
```

Make sure that you have the correct **Python** version set up in your environment (this is simple with **pyenv** commands).

If using **Poetry** (recommended), simply run the following command in the project directory to install dependencies:

```sh
poetry install
```

If using **pip** on your own:

```sh
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
python -m pip install -r requirements.txt
python -m pip install -e .
```

> 🐳 If using **Docker**, you can skip the dependency installation steps and refer to the [Docker Support](#-docker-support) section for details on how to setup the project to run inside a container.

### Environment

The project requires certain **environment variables** to be set for proper operation. The `.env.example` file in the root directory of the project serves as a template with placeholder values. Copy it to a `.env` file and fill in the real values **before running the engine**:

```sh
cp .env.example .env
```

> 🌍 For more information on these environment variables, see the dedicated section inside the [Configuration](/docs/configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🚀 Usage

### Workspace and Data

Running the engine requires two directories:

- A **workspace** directory, which holds the **knowledge model** and the **document collection registry**, and which the engine also writes its run state and exports into.
- A **data** directory, which holds the **plain text documents** to read. The engine never writes to it.

```sh
your-workspace/                      your-data-dir/
├── knowledge_model.json             ├── some-collection/
├── document_collections.json        │   ├── document_1.txt
├── staging/       (generated)       │   └── document_2.txt
└── exports/       (generated)       └── another-collection/
                                         └── document_3.txt
```

- `knowledge_model.json` declares **what knowledge to extract**: the entity and relationship types, their fields, and how each one is obtained.
- `document_collections.json` declares **which documents to read**, by mapping named collections to paths inside the data directory.

The separation means one corpus can be shared by several workspaces that extract different knowledge from it, and a workspace can be re-pointed at a different corpus without moving any files.

> 🧬 For the knowledge model format and all available options, refer to the [Knowledge Model](/docs/knowledge-model.md) documentation.
>
> 🗂️ For the workspace layout and the document collection registry, refer to the [Workspace](/docs/workspace.md) documentation.

A ready-to-run **example** is provided: the workspace in `workspaces/example/` paired with the corpus in `data/example/`, a small set of invented mission reports, crew dossiers and incident reports from a fictional deep-space agency.

### Running the Engine

Before running the engine, ensure that **all environment variables** are properly configured and that you have a **valid workspace and data directory**.

> 🌍 For more information on the required environment variables, refer to the [Environment](#environment) section.
>
> 📂 For more information on the two directories, refer to the [Workspace and Data](#workspace-and-data) section.

Run the engine with the **default configuration** using the following command (from the root of the project):

```sh
poetry run wukong run <path/to/workspace_dir> <path/to/data_dir>
```

If you are not using **Poetry**, run the engine inside your own virtual environment:

```sh
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
wukong run <path/to/workspace_dir> <path/to/data_dir>
```

To try it on the provided **example**:

```sh
poetry run wukong run workspaces/example data/example
```

The following options are available:

| Option            | Description                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `--config <FILE>` | Use a custom configuration file. Defaults to `config/default.toml`.                                                     |
| `-v` / `-vv`      | Increase output verbosity. By default only warnings and errors are shown; `-v` adds info logs and `-vv` adds debug logs. |
| `--reset`         | Clear the stored data at the start of each active pipeline step, so it recomputes from scratch.                         |

The engine will read the documents, extract the entities and relationships declared in the knowledge model, and write the result into the workspace. Depending on the size of the corpus and the complexity of the model, this may take anywhere from a few seconds to many hours.

Runs are **resumable**: state is kept in the workspace, so an interrupted run loses at most the **LLM** calls in flight, and re-running skips work that has already completed.

> ⚙️ For details on providing a custom configuration, refer to the [Engine Configuration](#engine-configuration) section.
>
> 🐳 If using **Docker**, refer to the [Docker Support](#-docker-support) section.

### Output

The result is written to `<path/to/workspace_dir>/exports/`, in a subdirectory named after the configured format.

Alongside the entity and relationship types declared in the knowledge model, the output always contains the following **special entities**:

- `Document`: The original source documents.
- `Chunk`: The text chunks the documents were segmented into, carrying their text and their exact span.

...and the following **special relationships**:

- `ChunkOf`: Links each `Chunk` to its parent `Document`.
- `ExtractedFrom`: Links each extracted entity to every source context it was observed in.

Because the sources are part of the output, the result is self-contained: it can be queried for domain facts, for the text that supports them, or for both at once, without consulting the original corpus.

> 📂 For the exact layout of the exported files, refer to the [Workspace](/docs/workspace.md) documentation.

### Engine Configuration

The engine configuration is a **TOML** file, optionally provided with the `--config` option. If none is given, the engine uses `config/default.toml`, which runs the entire pipeline with the recommended values.

```sh
poetry run wukong run <path/to/workspace_dir> <path/to/data_dir> --config <path/to/config.toml>
```

For example, to run over the example data with a custom configuration in `config/custom.toml`:

```sh
poetry run wukong run workspaces/example data/example --config config/custom.toml
```

The configuration controls which pipeline steps run, which **LLM** is used and how, how documents are chunked, and which output format is produced. Every key is optional and falls back to a built-in default.

> ⚙️ For the configuration file format and all available options, refer to the [Configuration](/docs/configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🐳 Docker Support

The project provides support for running the engine inside a **Docker** container. This is particularly useful for users on **MacOS** and **Windows**, as the project is primarily developed and tested on **Linux** platforms.

### Building the Image

To build the **Docker** image, use the provided script, which builds it with the correct name and tag:

```sh
scripts/build_image.sh
```

Alternatively, build the image directly:

```sh
docker build -t wukong-engine:latest .
```

### Running the Engine with Docker

Before running the engine, ensure that **all environment variables** are properly configured (the **Docker** container requires a valid `.env` file in the root of the project) and that you have a **valid workspace and data directory**.

> 🌍 For more information on the required environment variables, refer to the [Environment](#environment) section.
>
> 📂 For more information on the two directories, refer to the [Workspace and Data](#workspace-and-data) section.

After building the image, run the engine with the provided script, which mounts the workspace, the data directory and the configuration file into the container:

```sh
scripts/wukong_run.sh <path/to/workspace_dir> <path/to/data_dir> [--config <path/to/config.toml>] [--reset]
```

For example, to run over the example data with a custom configuration file located at `config/custom.toml`:

```sh
scripts/wukong_run.sh workspaces/example data/example --config config/custom.toml
```

The container runs as your own user, so the files it writes into the workspace belong to you and need no ownership fixing afterwards.

> ⚙️ If the `--config` option is not given, the engine uses the default configuration at `config/default.toml`. For the available options, refer to the [Engine Configuration](#engine-configuration) section.

### Important Considerations

Make sure to take the following into consideration when setting up and running the engine with **Docker**:

- Ensure **Docker** is installed and configured to run on your system with the necessary permissions (without requiring `sudo` for every command).
- Ensure **Docker** is running before building the image and running the engine inside the container.
- Ensure that you have a properly configured `.env` file in the root of the project, with all the **required environment variables** set.
- Ensure that the **Docker** image is built successfully before running the engine.
- The paths you pass in the commands must exist on your local machine, since they will be mounted inside the container.
- The provided scripts are **Bash** scripts. On **Windows**, run them from **WSL** or **Git Bash**.
- The scripts may require **execution permissions** to run on your system. On **Linux/MacOS**, you can set them for all scripts in the project with:

    ```sh
    chmod +x scripts/*.sh
    ```

[📚 Back to Table of Contents](#-table-of-contents)

## 🤝 Contributing

Contributions are welcome!
Please review the following resources:

- 📜 [Code of Conduct](/.github/CODE_OF_CONDUCT.md)
- 🤝 [Contribution Guide](/.github/CONTRIBUTING.md)
- 🛠️ [Development Guidelines](/docs/development.md)
- 🏗️ [Architecture Guidelines](/docs/architecture.md)
- 🧱 [Project Structure](/docs/project-structure.md)

> 📝 For a detailed list of past updates, see the [Changelog](/CHANGELOG.md).

[📚 Back to Table of Contents](#-table-of-contents)
