<!-- omit from toc -->
# 🛠️ Development

This document outlines the development practices and setup for the project.

<!-- omit from toc -->
## 📚 Table of Contents
- [🚀 Getting Started](#-getting-started)
- [🎨 Code Style](#-code-style)
- [🧾 Code Documentation](#-code-documentation)
- [🧪 Testing](#-testing)
- [🌿 Branching Strategy](#-branching-strategy)
- [🧱 Project Structure](#-project-structure)
- [🤝 Contributing](#-contributing)

## 🚀 Getting Started

To set up the project for development, follow these steps:

1. Perform the general set up for the project outlined in the [README](../README.md) **(Setup & Usage sections)**. For the sake of consistency in project development, make sure to **adhere to all the recommendations (optional or not)** provided there.

2. Switch to the development branch and create a new feature branch:

```sh
git checkout dev  # Make sure you're on the dev branch
git checkout -b my-feature-branch
```

Now you can start development inside your branch. Make sure to follow the development practices described in the sections below.

[📚 Back to Table of Contents](#-table-of-contents)

## 🎨 Code Style

The project follows multiple code style conventions and practices to ensure code quality, extensibility and maintainability. The following tools are used to enforce these standards:

- **Ruff**: A fast linter and formatter that supports multiple **Python** code style rules. The recommended way of using this tool is through its [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff), which provides real-time linting and formatting. The specific configuration used in the project is defined in the `pyproject.toml` file, which will be automatically detected and applied by the tool. If using **VS Code**, add the following fields to your `settings.json` to make sure that **Ruff** is properly configured:

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

(Complete later...)
Docstrings should follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for consistency and clarity.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧪 Testing

Currently, the project **does not implement** testing functionalities. For now, making sure that the code works well with the provided example data directory is sufficient. The example directory is located at `data/example/`.

[📚 Back to Table of Contents](#-table-of-contents)

## 🌿 Branching Strategy

This project uses a simple branching model:

- `main`: Stable release-ready code. Always production-safe.
- `dev`: Active development branch. All feature branches should be based here.

Please create your feature branches **from `dev`**, and open pull requests **targeting `dev`**.

> 🔗 For branch naming conventions and contribution workflow, see our [Contributions Guide](../.github/CONTRIBUTING.md).

[📚 Back to Table of Contents](#-table-of-contents)

## 🧱 Project Structure

The project is organized into several directories and files, each serving a specific purpose.

For a detailed description of the entire project structure and its components, refer to the [Project Structure](./project-structure.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🤝 Contributing

To contribute to this project — including code changes, documentation, or testing — please refer to our [Contributing Guide](../.github/CONTRIBUTING.md). It includes conventions for branches, commits, pull requests, and more.

[📚 Back to Table of Contents](#-table-of-contents)