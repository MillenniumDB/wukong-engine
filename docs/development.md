<!-- omit from toc -->
# 🛠️ Development Guidelines

This document outlines the development practices and setup for the project.

<!-- omit from toc -->
## 📚 Table of Contents
- [🚀 Getting Started](#-getting-started)
- [🎨 Code Style](#-code-style)
- [🧾 Code Documentation](#-code-documentation)
- [🧪 Testing](#-testing)
- [🌿 Branching Strategy](#-branching-strategy)
- [🏷️ Naming Conventions](#️-naming-conventions)
  - [Commit Messages](#commit-messages)
  - [Branch Names](#branch-names)
  - [Pull Request Titles](#pull-request-titles)
- [🧱 Project Structure](#-project-structure)
- [🤝 Contributing](#-contributing)

## 🚀 Getting Started

To set up the project for development, follow these steps:

1. Perform the general set up for the project outlined in the [README](../README.md) **(Setup & Usage sections)**. For the sake of consistency in project development, make sure to **adhere to all the recommendations (optional or not)** provided there.

2. Switch to the development branch and create a new feature branch:

```sh
git checkout develop  # Make sure you're on the develop branch
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

The project uses **docstrings** to document **functions, classes, and modules**. This is crucial for maintaining code readability and understanding the purpose of each component. The **Ruff** linter configuration used in the project enforces these standards.

These **docstrings** should follow the [Google Style Format](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) for consistency and clarity. Here’s a brief example of this format, using a generic function:

```python
def my_function(param1: int, param2: str) -> bool:
    """Brief description of the function.

    Args:
        param1: Description of the first parameter.
        param2: Description of the second parameter.

    Returns:
        Description of the return value.
    """
    # Function implementation
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🧪 Testing

Currently, the project **does not implement** testing functionalities. For now, making sure that the code works well with the provided **example data directory** is sufficient. The example directory is located at `data/example/`.

[📚 Back to Table of Contents](#-table-of-contents)

## 🌿 Branching Strategy

The project uses a simple branching model:

- `main`: Stable release-ready code. Always production-safe.
- `develop`: Active development branch. All feature branches should be based here.

Please create your own branches **from** `develop`, and open pull requests **targeting** `develop`.

> 🤝 For branch naming conventions and contribution workflow, see our [Contribution Guide](../.github/CONTRIBUTING.md).

[📚 Back to Table of Contents](#-table-of-contents)

## 🏷️ Naming Conventions

### Commit Messages

For writing **commit messages**, use the following convention:

`<optional-emoji> <type>(optional scope): short description`

Here are the available values for `<type>` with some commit message examples:

| Type       | Purpose                                              | Commit Example                                                   |
| ---------- | ---------------------------------------------------- | ---------------------------------------------------------------- |
| `feat`     | Introduces a new feature                             | `feat(api): add validator for user input`                        |
| `fix`      | Fixes a bug                                          | `fix: correct file not found error in document processing`       |
| `docs`     | Adds or improves documentation                       | `docs(readme): improve usage section`                            |
| `style`    | Code style changes (formatting, whitespace, etc.)    | `style: improve order of functions in processing module`         |
| `refactor` | Code refactoring that doesn't change behavior        | `refactor(llm): simplify prompt generation logic`                |
| `perf`     | Improves performance                                 | `perf(parser): optimize text parsing with regex pre-compilation` |
| `test`     | Adds or modifies tests                               | `test(llm): add edge case tests for LLM output parser`           |
| `build`    | Changes that affect the build system or dependencies | `build(docker): restructure build process`                       |
| `ci`       | Changes to CI/CD pipelines or configs                | `ci: add linting step to GitHub Actions`                         |
| `chore`    | Routine tasks like maintenance, dependency updates   | `chore: update dependency versions`                              |
| `revert`   | Reverts a previous commit                            | `revert: revert "feat: add text deduplication"`                  |

The `<optional-emoji>` can be used to visually categorize the commit, but is not strictly required.
The project uses the emoji convention from [Gitmoji](https://gitmoji.dev/), which is also available in the [VS Code Gitmoji Extension](https://marketplace.visualstudio.com/items?itemName=seatonjiang.gitmoji-vscode).

### Branch Names

For naming **short-lived branches**, use the following convention:

`<type>/<short-descriptive-name>`

Here are the available values for `<type>` with some branch name examples:

| Type       | Purpose                                              | Branch Example               |
| ---------- | ---------------------------------------------------- | ---------------------------- |
| `feat`     | New features or enhancements                         | `feat/api-support`           |
| `fix`      | Bug fixes                                            | `fix/login-error`            |
| `hotfix`   | Urgent fixes to production code                      | `hotfix/fix-login-crash`     |
| `release`  | Preparing a new release                              | `release/v1.0.0`             |
| `docs`     | Documentation-only changes                           | `docs/api-reference`         |
| `refactor` | Code restructuring without behavior change           | `refactor/simplify-pipeline` |
| `perf`     | Performance improvements                             | `perf/cache-optimization`    |
| `test`     | Experimental work or testing                         | `test/improve-config-tests`  |
| `build`    | Changes that affect the build system or dependencies | `build/migrate-to-poetry`    |
| `ci`       | Changes to CI/CD pipelines or configs                | `ci/setup-github-actions`    |
| `chore`    | Routine tasks like maintenance, dependency updates   | `chore/update-dependencies`  |

### Pull Request Titles

For naming **pull requests**, use the following convention:

`<type>(optional scope): short description`

Here, `<type>` can be any of the **branch types** listed previously.

Example **PR** titles:

- `feat(core): add support for custom data models`
- `hotfix(parsing): resolve critical error with document parsing`

[📚 Back to Table of Contents](#-table-of-contents)

## 🧱 Project Structure

The project is organized into several directories and files, each serving a specific purpose.

For a detailed description of the entire project structure and its components, refer to the [Project Structure](./project-structure.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🤝 Contributing

To contribute to this project — including code changes, documentation, or testing — please refer to our [Contributing Guide](../.github/CONTRIBUTING.md). It includes conventions for branches, commits, pull requests, and more.

[📚 Back to Table of Contents](#-table-of-contents)