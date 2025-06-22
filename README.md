# WUKONG Engine <!-- omit in toc -->

Engine for constructing knowledge graphs from unstructured documents, using the power of LLMs.

# 📚 Table of Contents <!-- omit in toc -->
- [🐵 WUKONG: Weaving Unstructured Knowledge Onto Navigable Graphs](#-wukong-weaving-unstructured-knowledge-onto-navigable-graphs)
- [🚀 Setup](#-setup)
  - [Pre-requisites](#pre-requisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
- [🛠️ Usage](#️-usage)
  - [Data Directory](#data-directory)
  - [Engine Configuration](#engine-configuration)
  - [Running the Engine](#running-the-engine)
- [📁 Folder Structure](#-folder-structure)
- [🛤️ Roadmap](#️-roadmap)

# 🐵 WUKONG: Weaving Unstructured Knowledge Onto Navigable Graphs

The **WUKONG** engine is a tool designed to process **unstructured documents** and construct a **knowledge graph** based on a user-defined data model.
It leverages the power of **Large Language Models (LLMs)** to extract entities and relations from the documents, and then organizes this information into a structured **property graph** format that can be easily managed, queried and navigated by graph database engines (e.g. `MillenniumDB`, `Neo4j`). The original documents are also stored in the graph, allowing for easy retrieval and context-aware querying. The knowledge graphs produced by this engine are particularly useful for applications in **information retrieval**, **data integration**, and **AI assistants**.

# 🚀 Setup

## Pre-requisites

Before installing or running the **WUKONG** engine, ensure you have the following installed:

- **Python 3.13+**

  The engine requires `Python 3.13` or higher.
  A very useful tool for managing **Python** versions is [pyenv](https://github.com/pyenv/pyenv).

- **Poetry 2.1+** (optional but recommended)

  For managing dependencies, virtual environments and packaging.
  Install by following the [Poetry installation guide](https://python-poetry.org/docs/#installation).
  If you prefer not to use **Poetry**, you can install dependencies and manage virtual environments manually using **pip**.

- **Git**

  For version control and cloning the repository.

- **Docker** (optional)

  For containerization and running the engine in a consistent environment.
  Install Docker by ...TODO: provide instructions or link to the Docker installation guide.

## Installation

To set up the **WUKONG** engine, follow these steps:

1. Clone the repository and navigate to the project directory:

```sh
git clone https://github.com/MillenniumDB/wukong-engine.git
cd wukong-engine
```

2. Install dependencies:

Make sure that you have the correct **Python** version set up in your environment (this is simple with **pyenv** commands).

If using **Poetry** (recommended), simply run the following command in the project directory.

```sh
# Example using Poetry
poetry install
```

If using **pip** on your own:

```sh
# Example using pip
python -m venv venv  # Create a virtual environment
source venv/bin/activate  # Activate the virtual environment (on Windows use `venv\Scripts\activate`)
python -m pip install -r requirements.txt  # Install dependencies
python -m pip install -e .  # Install the package in editable mode
```

## Environment Variables

The following environment variables are required for the engine to function properly:

```env
OPENAI_API_KEY=your_openai_api_key
```

For local development/usage, create a `.env` file in the root directory of the project and add the required variables there.

For production/deployment, set these variables directly in your server/cloud environment.

# 🛠️ Usage

## Data Directory

To run the **WUKONG** engine, a data directory containing the documents to be processed is required.
This data directory must follow a specific structure to be recognized as valid by the engine.
The expected structure is as follows:

```
your-data-dir/
├── docs/
│   ├── text/
│   │   ├── document1.txt
│   │   ├── document2.txt
│   │   └── ...
├── data_model.json
└── ...
```

The `docs/text/` directory should contain the **plain text** files to be processed (with `.txt` extension).

The `data_model.json` file should define the desired **entity/relation** schema for the knowledge graph, in **JSON** format.
For a detailed description of the data model schema and available options, refer to the [Data Model](docs/data-model.md) documentation.

An example data directory is provided for testing purposes, located in `data/example/`.

## Engine Configuration

The **WUKONG** engine can be configured by editing the `config.toml` file that is present in the root directory of the project.
The configuration file comes with default settings to run the engine normally, but you can customize it to suit your needs.

For more information on the available configuration options, refer to the [Configuration](docs/configuration.md) documentation.

## Running the Engine

After setting up a data directory and looking at the configuration, you can run the **WUKONG** engine using the following command (from the root directory of the project):

```sh
poetry run python -m wukong_engine <path/to/data_dir>
```

If you are not using **Poetry**, you can run the engine directly inside your virtual environment:

```sh
source venv/bin/activate  # Activate the virtual environment (on Windows use `venv\Scripts\activate`)
python -m wukong_engine <path/to/data_dir>
```

After executing the command, the engine will process the documents in the specified data directory and generate a **knowledge graph** based on the provided data model. This process may take some time depending on the size and number of documents and the complexity of the data model (from a few seconds to multiple hours or more).

The resulting **knowledge graph** files will be exported to the `<path/to/data_dir>/exports/` directory.

# 📁 Folder Structure

TODO: Reference code-structure.

```
wukong-engine/
├── src/               # Main source code
├── tests/             # Test suite
├── docs/              # Documentation files
├── pyproject.toml     # Build system and config
├── README.md          # Project overview
└── ...
```

# 🛤️ Roadmap

TODO: Reference CHANGELOG and development.

- [ ] Support YAML format for data models
- [ ] Add CLI with subcommands
- [ ] More robust validation
- [ ] Publish to PyPI