<!-- omit from toc -->
# 🛠️ Development

This document outlines the development practices and setup for the project.

<!-- omit from toc -->
## 📚 Table of Contents
- [⚙️ Setup](#️-setup)
  - [Pre-requisites](#pre-requisites)
  - [Installation](#installation)
  - [Environment](#environment)
  - [Running the Project](#running-the-project)
- [🎨 Code Style](#-code-style)
- [🧾 Code Documentation](#-code-documentation)
- [🧪 Testing](#-testing)
- [📦 Package Structure](#-package-structure)
- [Later](#later)

## ⚙️ Setup

### Pre-requisites

Before setting up the project for development, ensure you have the following installed:

- **Python 3.13+**

  The engine is built to support `Python 3.13` or higher.
  A very useful tool for managing **Python** versions is [pyenv](https://github.com/pyenv/pyenv).

- **Poetry 2.1+**

  For managing dependencies, virtual environments and packaging.
  Install by following the [Poetry installation guide](https://python-poetry.org/docs/#installation).

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

First, make sure that you have the correct **Python** version set up in your environment (this is simple with **pyenv** commands).

Now run the following command in the project directory.

```sh
poetry install
```

### Environment

The project requires certain **environment variables** to be set for proper operation.
These variables are defined in the `.env.example` file located in the root directory of the project, which serves as a template with placeholder values.

For development, create a `.env` file in the root directory of the project and copy the contents from `.env.example` into it, replacing the placeholder values with the real ones for all the environment variables.

If new environment variables are required in the future, they should be added to the `.env.example` file and documented in their dedicated section inside the [Configuration](./configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

### Running the Project

The

[📚 Back to Table of Contents](#-table-of-contents)

## 🎨 Code Style

The project follows multiple code style conventions and practices to ensure code quality, extensibility and maintainability. The following tools are used to enforce these standards:

- **Ruff**: A fast linter and formatter that supports multiple **Python** code style rules. The recommended way of using this tool is through its [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff), which provides real-time linting and formatting. The specific configuration used in the project is defined in the `pyproject.toml` file, which will be automatically detected and applied by the tool. If using **VS Code**, add the following fields in your `settings.json` file to make sure that **Ruff** is properly configured:

```json
"editor.formatOnSave": true,
"editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
},
"ruff.configurationPreference": "filesystemFirst",
```

- **Pyright**: A static type checker for **Python** that helps catch type errors and enforce type annotations. The recommended way of using this tool is through the [Pylance VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance), which is usually installed automatically when installing the [Python VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python). Just like with **Ruff**, the specific configuration for **Pyright** is also defined in the `pyproject.toml` file and detected automatically by the tool.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧾 Code Documentation

Docstrings should follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for consistency and clarity.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧪 Testing

A

[📚 Back to Table of Contents](#-table-of-contents)

## 📦 Package Structure

The project is organized into several components, each serving a specific purpose in the overall architecture. The package structure is as follows:

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

For a detailed description of the entire project structure and its components, refer to the [Project Structure](./project-structure.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## Later

- ref to contributing