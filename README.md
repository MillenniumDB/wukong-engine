<!-- Banner Logo -->
<p align="center">
  <img src="/assets/logo/banner/1024-rounded.png" alt="Logo" width="100%"/>
</p>

<!-- omit from toc -->
# WUKONG Engine

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
  - [Running the Engine](#running-the-engine)
  - [Output Knowledge Graph](#output-knowledge-graph)
  - [Engine Configuration](#engine-configuration)
- [🐳 Docker Support](#-docker-support)
  - [Building the Image](#building-the-image)
  - [Running the Engine with Docker](#running-the-engine-with-docker)
  - [Important Considerations](#important-considerations)
- [📦 Package Structure](#-package-structure)
- [🤝 Contributing](#-contributing)
- [🗺️ Roadmap](#️-roadmap)

## 🐵 WUKONG: Weaving Unstructured Knowledge Onto Navigable Graphs

The **WUKONG** engine is a tool designed to process **unstructured documents** and construct a **knowledge graph** based on a user-defined **data model**. It leverages the power of **Large Language Models (LLMs)** to extract entities and relations from the documents, and then organizes this information into a structured **property graph** format that can be easily managed, queried and navigated by graph database engines (e.g. `MillenniumDB`, `Neo4j`). The original documents are also stored in the graph, allowing for easy retrieval and context-aware querying. The knowledge graphs produced by this engine are particularly useful for applications in **information retrieval**, **data integration**, and **AI agents**.

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

The project requires certain **environment variables** to be set for proper operation. Refer to the `.env.example` file located in the root directory of the project, which serves as a template with placeholder values for the available environment variables. Make sure to set these variables in your own environment **before running the engine**.

> 🌍 For more information on these environment variables, see the dedicated section inside the [Configuration](/docs/configuration.md) documentation.

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
│   │   ├── your-doc-subset-name-a/
│   │   │   ├── document_1.txt
│   │   │   ├── document_2.txt
│   │   │   └── ...
│   │   ├── your-doc-subset-name-b/
│   │   │   ├── document_1.txt
│   │   │   ├── document_2.txt
│   │   │   └── ...
│   │   └── ...
│   └── ...
└── data_model.json
```

The `docs/text/` directory should contain the **plain text** files to be processed, saved with the `.txt` extension (the filenames themselves are not restricted).
These files **must** be organized in user-defined sub-directories (e.g. `your-doc-subset-name-a/`, `your-doc-subset-name-b/`).

The `data_model.json` file should define the desired **parameters** and **entity/relation schema** for the knowledge graph, in **JSON** format.

> 🧬 For a detailed description of the data model schema and available options, refer to the [Data Model](/docs/data-model.md) documentation.

An **example** data directory is provided for testing purposes, located in `data/example/`.

### Running the Engine

Before running the engine, ensure that **all environment variables** are properly configured and that you have a **valid data directory** to provide the engine with.

> 🌍 For more information on the required environment variables, refer to the [Environment](#environment) section.
>
> 📂 For more information on the data directory structure, refer to the [Data Directory](#data-directory) section.

You can run the engine with the **default configuration** using the following command (from the root of the project):

```sh
poetry run python -m wukong_engine <path/to/data_dir>
```

If you are not using **Poetry**, you can run the engine directly inside your own virtual environment:

```sh
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
python -m wukong_engine <path/to/data_dir>
```

As an example, if you want to run the engine on the provided **example data directory** (with **Poetry**), you can use the following command:

```sh
poetry run python -m wukong_engine data/example/
```

After executing the command, the engine will process the **documents** in the specified data directory and generate a **knowledge graph** based on the provided **data model**. This process may take some time depending on the size/number of documents and the complexity of the data model (from a few seconds to multiple hours or longer).

> ⚙️ For details on how to provide a custom configuration for the engine, refer to the [Engine Configuration](#engine-configuration) section.
>
> 🐳 If using **Docker**, refer to the [Docker Support](#-docker-support) section for details on how to run the engine inside a container.

### Output Knowledge Graph

The resulting **knowledge graph** will contain all the extracted entities and relations specified in the **data model**, as well as the following **special entities**:

- `Document`: Represents the original documents.
- `Chunk`: Represents the text chunks obtained from the original documents, which are used for extracting the user-defined entities and relations.

Additionally, the graph will contain the following **special relations**:

- `ChunkOf`: Links the `Chunk` entities to their corresponding `Document` entities.
- `ExtractedFrom`: Links user-defined entities from the data model to the respective `Chunk` or `Document` entities from where they got extracted.

The output files for the **knowledge graph** will be exported to the `<path/to/data_dir>/exports/` directory.

### Engine Configuration

The engine configuration is managed through a **TOML** file, which can be **optionally provided** as a command-line argument when running the program. If no custom configuration is specified, the engine will use the default configuration located at `config/default.toml`, which runs the entire pipeline and considers the default values for all parameters.

You can run the engine with a custom configuration like this:

```sh
poetry run python -m wukong_engine <path/to/data_dir> --config <path/to/config.toml>
```

To illustrate, the following command shows how to run the engine over the **example data** using a **custom configuration**
hypothetically located in `config/test.toml`:

```sh
poetry run python -m wukong_engine data/example/ --config config/test.toml
```

> ⚙️ For more information on the configuration file format and available options, refer to the [Configuration](/docs/configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🐳 Docker Support

The project provides support for running the engine inside a **Docker** container. This is particularly useful for users on **MacOS** and **Windows**, as the project is primarily developed and tested on **Linux** platforms.

### Building the Image

To build the **Docker** image, you can use the provided **shell scripts**, which are designed to automatically build the image with the **correct name and tag**.

For **Linux, MacOS, and Bash/WSL for Windows**, run the following command from the root of the project directory:

```sh
scripts/build.sh
```

For **Windows PowerShell**:

```powershell
.\scripts\build.ps1
```

Alternatively, the following command can be used to build the image directly (without the shell scripts):

```sh
docker build -t wukong-engine:latest .
```

### Running the Engine with Docker

Before running the engine, ensure that **all environment variables** are properly configured (the **Docker** container requires a valid `.env` file) and that you have a **valid data directory** to provide the engine with.

> 🌍 For more information on the required environment variables, refer to the [Environment](#environment) section.
>
> 📂 For more information on the data directory structure, refer to the [Data Directory](#data-directory) section.

After building the **Docker** image, you can run the engine inside a **Docker** container using the provided **shell scripts**. These scripts will automatically mount the specified **data directory** and the **custom configuration file** (if provided) into the container, executing the engine in its native environment.

For **Linux, MacOS, and Bash/WSL for Windows**, run the following command from the root of the project directory:

```sh
scripts/run.sh <path/to/data_dir> --config <path/to/config.toml>
```

For **Windows PowerShell**:

```powershell
.\scripts\run.ps1 <path\to\data_dir> -config <path\to\config.toml>
```

An example command to run the engine on the provided **example data directory** using a **custom configuration file** located at `config/test.toml` would look like this (on **Linux, MacOS, or Bash/WSL for Windows**):

```sh
scripts/run.sh data/example/ --config config/test.toml
```

If using **Linux/MacOS**, the terminal will prompt you to enter your `sudo` password **at the end of the engine execution**. This is used to restore the ownership of the **output files** to your user, since the container runs with `root` privileges.

> ⚙️ If the `config` option is not provided in the execution command, the engine will use the default configuration located at `config/default.toml`. For more information on the available configuration options, refer to the [Engine Configuration](#engine-configuration) section.

### Important Considerations

Make sure to take the following into consideration when setting up and running the engine with **Docker**:

- Ensure **Docker** is installed and configured to run on your system with the necessary permissions (without requiring `sudo` for every command).
- Ensure **Docker** is running before building the image and running the engine inside the container.
- Ensure that you have a properly configured `.env` file in the root of the project, with all the **required environment variables** set.
- Ensure that the **Docker** image is built successfully before running the engine.
- The paths you pass in the commands must exist on your local machine, since they will be mounted inside the container.
- The provided scripts may require **execution permissions** to be able to run on your system.

    For **Linux/MacOS**, you can set the execution permissions for all scripts in the project with the following command:

    ```sh
    chmod +x scripts/*.sh
    ```

    For **Windows**, you may need to set the **PowerShell** execution policy to allow running scripts:

    ```powershell
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
    ```

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

> 🧱 For a detailed description of the entire project structure and its components, refer to the [Project Structure](/docs/project-structure.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🤝 Contributing

Contributions are welcome!
Please review the following resources:

- 📜 [Code of Conduct](/.github/CODE_OF_CONDUCT.md)
- 🤝 [Contribution Guide](/.github/CONTRIBUTING.md)
- 🛠️ [Development Guidelines](/docs/development.md)

[📚 Back to Table of Contents](#-table-of-contents)

## 🗺️ Roadmap

Here are some planned features and improvements for future releases of the project:

- [ ] Support for more data types in the data model (e.g. `integer`, `float`, `bool`)
- [ ] Data validation for data model and configuration files
- [ ] Data validation for LLM responses
- [ ] Improved wrapper for LLM interaction

> 📝 For a detailed list of past updates, see the [Changelog](/CHANGELOG.md).

[📚 Back to Table of Contents](#-table-of-contents)