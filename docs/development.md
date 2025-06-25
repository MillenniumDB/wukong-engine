# Development

This document outlines the development practices and setup for the **WUKONG** engine project.

## Environment Setup

A

## Code Style

The project follows multiple code style conventions and practices to ensure code quality and maintainability. The following tools are used to enforce these standards:

- **Ruff**: A fast linter and formatter that supports multiple **Python** code style rules. The recommended way of using this tool is through its [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff), which provides real-time linting and formatting. The specific code style configuration used in the project is defined in the `pyproject.toml` file, and will be automatically detected and applied by **Ruff**. To make sure that the tool is properly configured, add the following settings in your `settings.json` file:

```json
"editor.formatOnSave": true,
"editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
},
"ruff.configurationPreference": "filesystemFirst",
```

- **Pyright**: A static type checker for **Python** that helps catch type errors and enforce type annotations. It is configured to run automatically on file save in the project. The configuration for **Pyright** is defined in the `pyproject.toml` file, which specifies the type checking rules and settings.

[Pylance VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
[Python VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python)

## Testing

A

## Documentation Standards

Docstrings should follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for consistency and clarity.

## Later

- ref to project-structure
- ref to contributing