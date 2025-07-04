<!-- omit from toc -->
# 🧰 WUKONG Engine

Engine for constructing knowledge graphs from unstructured documents, using the power of LLMs.

<!-- omit from toc -->
## 📚 Table of Contents
- [🐵 WUKONG: Weaving Unstructured Knowledge Onto Navigable Graphs](#-wukong-weaving-unstructured-knowledge-onto-navigable-graphs)
- [⚙️ Setup](#️-setup)
  - [Pre-requisites](#pre-requisites)
  - [Installation](#installation)
  - [Environment](#environment)
- [🚀 Usage](#-usage)
  - [Data Directory](#data-directory)
  - [Engine Configuration](#engine-configuration)
  - [Running the Engine](#running-the-engine)
  - [Output Knowledge Graph](#output-knowledge-graph)
- [📦 Package Structure](#-package-structure)
- [🤝 Contributing](#-contributing)
- [🗺️ Roadmap](#️-roadmap)

## 🐵 WUKONG: Weaving Unstructured Knowledge Onto Navigable Graphs

The **WUKONG** engine is a tool designed to process **unstructured documents** and construct a **knowledge graph** based on a user-defined **data model**. It leverages the power of **Large Language Models (LLMs)** to extract entities and relations from the documents, and then organizes this information into a structured **property graph** format that can be easily managed, queried and navigated by graph database engines (e.g. `MillenniumDB`, `Neo4j`). The original documents are also stored in the graph, allowing for easy retrieval and context-aware querying. The knowledge graphs produced by this engine are particularly useful for applications in **information retrieval**, **data integration**, and **AI assistants**.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Setup

### Pre-requisites

Before setting up the project, ensure you have the following software installed:

- **Python 3.13+**

  The engine requires `Python 3.13` or higher.
  A very useful tool for managing **Python** versions is [pyenv](https://github.com/pyenv/pyenv).

- **Poetry 2.1+** (recommended)

  For managing dependencies, virtual environments and packaging.
  Install by following the [Poetry installation guide](https://python-poetry.org/docs/#installation).
  If you prefer not to use **Poetry**, you can install dependencies and manage virtual environments manually using **pip**.

- **Git**

  For version control and cloning the repository.

### Installation

To set up the project, follow these steps:

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

### Environment

The project requires certain **environment variables** to be set for proper operation. Refer to the `.env.example` file located in the root directory of the project, which serves as a template with placeholder values for the available environment variables.

> 🌍 For more information on these environment variables, see the dedicated section inside the [Configuration](docs/configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🚀 Usage

### Data Directory

To run the engine, a data directory containing the **data model** and the **documents** to be processed is required.
This data directory must follow a specific structure to be recognized as valid by the engine.
The expected structure is as follows:

```sh
your-data-dir/
├── docs/
│   ├── text/
│   │   ├── document_1.txt
│   │   ├── document_2.txt
│   │   └── ...
│   └── ...
├── data_model.json
└── ...
```

The `docs/text/` directory should contain the **plain text** files to be processed (with the `.txt` extension).

The `data_model.json` file should define the desired **entity/relation schema** for the knowledge graph, in **JSON** format.

> 🧬 For a detailed description of the data model schema and available options, refer to the [Data Model](docs/data-model.md) documentation.

An **example** data directory is provided for testing purposes, located in `data/example/`.

### Engine Configuration

The engine can be configured by editing the `config.toml` file that is present in the `config/` directory of the project.
The configuration file comes with default settings to run the engine normally, but you can customize it to suit your needs.

> ⚙️ For more information on the available configuration options, refer to the [Configuration](docs/configuration.md) documentation.

### Running the Engine

After setting up a **data directory** and looking at the **configuration**, you can run the engine using the following command (from the root of the project):

```sh
poetry run python -m wukong_engine <path/to/data_dir>
```

If you are not using **Poetry**, you can run the engine directly inside your own virtual environment:

```sh
source venv/bin/activate  # Activate the virtual environment (on Windows use `venv\Scripts\activate`)
python -m wukong_engine <path/to/data_dir>
```

As an example, if you want to run the engine on the provided **example data directory** (with **Poetry**), you can use the following command:

```sh
poetry run python -m wukong_engine data/example/
```

After executing the command, the engine will process the **documents** in the specified data directory and generate a **knowledge graph** based on the provided **data model**. This process may take some time depending on the size/number of documents and the complexity of the data model (from a few seconds to multiple hours or longer).

### Output Knowledge Graph

The resulting **knowledge graph** will contain all the extracted entities and relations specified in the **data model**, as well as the following **special entities**:

- `Document`: Represents the original documents.
- `Chunk`: Represents the text chunks obtained from the original documents, which are used for extracting the user-defined entities and relations.

Additionally, the graph will contain the following **special relations**:

- `ChunkOf`: Links the `Chunk` entities to their corresponding `Document` entities.
- `ExtractedFrom`: Links user-defined entities from the data model to the respective `Chunk` or `Document` entities from where they got extracted.

The output files for the **knowledge graph** will be exported to the `<path/to/data_dir>/exports/` directory.

[📚 Back to Table of Contents](#-table-of-contents)

## 📦 Package Structure

The engine is organized into several components, each serving a specific purpose in the overall architecture. The package structure is as follows:

```sh
src/wukong_engine/
├── __main__.py  # Entry point
├── config/      # Configuration and environment
├── core/        # Core logic for the engine pipeline
├── documents/   # Document pre-processing
├── extraction/  # Data extraction logic
├── graph/       # Graph database interaction
├── llm/         # LLM interaction
└── utils/       # Utility functions and shared components
```

> 🧱 For a detailed description of the entire project structure and its components, refer to the [Project Structure](docs/project-structure.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🤝 Contributing

Contributions are welcome!
Please review the following resources:

- 📜 [Code of Conduct](.github/CODE_OF_CONDUCT.md)
- 🤝 [Contribution Guide](.github/CONTRIBUTING.md)
- 🛠️ [Development Guidelines](./docs/development.md)

[📚 Back to Table of Contents](#-table-of-contents)

## 🗺️ Roadmap

Here are some planned features and improvements for future releases of the project:

- [ ] Support for more data types in the data model (e.g. `integer`, `float`, `bool`)
- [ ] Data validation for data model and configuration files
- [ ] Data validation for LLM responses
- [ ] Improved wrapper for LLM interaction

> 📝 For a detailed list of past updates, see the [Changelog](./CHANGELOG.md).

[📚 Back to Table of Contents](#-table-of-contents)