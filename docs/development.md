<!-- omit from toc -->
# 🛠️ Development Guidelines

This document outlines the development practices and setup for the project.

<!-- omit from toc -->
## 📚 Table of Contents
- [🚀 Getting Started](#-getting-started)
- [🧱 Project Structure](#-project-structure)
- [🎨 Code Style](#-code-style)
- [🧾 Code Documentation](#-code-documentation)
- [🧪 Testing](#-testing)
- [🌿 Branching Strategy](#-branching-strategy)
  - [Core Branch](#core-branch)
  - [Supporting Branches](#supporting-branches)
    - [Topic Branches](#topic-branches)
    - [Release Branches](#release-branches)
    - [Hotfix Branches](#hotfix-branches)
- [🏷️ Naming Conventions](#️-naming-conventions)
  - [Commit Messages](#commit-messages)
  - [Supporting Branch Names](#supporting-branch-names)
  - [Pull Request Titles](#pull-request-titles)
- [📦 Project Versioning](#-project-versioning)
- [⚙️ Tooling \& Infrastructure](#️-tooling--infrastructure)
  - [Dependency Management](#dependency-management)
  - [Containerization](#containerization)
  - [Continuous Integration/Deployment](#continuous-integrationdeployment)

## 🚀 Getting Started

Perform the general set up for the project outlined in the [README](../README.md) **(Setup & Usage sections)**. For the sake of consistency in project development, make sure to **adhere to all the recommendations** provided there.

After that, create a new feature branch from `main`:

```sh
git checkout -b my-feature-branch
```

Now you can start development inside your branch. Make sure to follow the development practices described in the sections below.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧱 Project Structure

The project is organized into several directories and files, each serving a specific purpose.

For a detailed description of the entire project structure and its components, refer to the [Project Structure](./project_structure.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 🎨 Code Style

The project follows multiple code style conventions and practices to ensure code quality, extensibility and maintainability. The following tools are used to enforce these standards.

**Ruff**: A fast linter and formatter that supports multiple **Python** code style rules. The recommended way of using this tool is through the [Ruff VS Code Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff), which provides real-time linting and formatting. The specific configuration used in the project is defined in the `pyproject.toml` file, which will be automatically detected and applied by the tool. If using **VS Code**, add the following fields to your `settings.json` to make sure that **Ruff** is properly configured:

```json
"editor.formatOnSave": true,
"editor.codeActionsOnSave": {
    "source.fixAll": "explicit",
    "source.organizeImports": "explicit"
},
"notebook.formatOnSave.enabled": true,
"notebook.defaultFormatter": "charliermarsh.ruff",
"notebook.codeActionsOnSave": {
    "notebook.source.fixAll": "explicit",
    "notebook.source.organizeImports": "explicit"
},
"[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
},
"ruff.configurationPreference": "filesystemFirst",
```

**Pyright**: A static type checker for **Python** that helps catch type errors and enforce type annotations. The recommended way of using this tool is through the [Pylance VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance), which is usually installed automatically when installing the [Python VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python). Just like with **Ruff**, the specific configuration for **Pyright** is also defined in the `pyproject.toml` file and detected automatically by the tool.

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

> 🎨 For more details on how to write docstrings in this format, refer to the [Google Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

[📚 Back to Table of Contents](#-table-of-contents)

## 🧪 Testing

Currently, the project **does not implement** testing functionalities. For now, making sure that the code works well with the provided **example data directory** is sufficient. The example directory is located at `data/example/`.

[📚 Back to Table of Contents](#-table-of-contents)

## 🌿 Branching Strategy

The project uses a variant of the **GitHub Flow** branching model to manage development and releases. This model is designed to be simple and effective for continuous delivery, allowing for quick iterations and deployments.

> 🤝 For an overview of the expected workflow for external contributors, refer to our [Contribution Guide](../.github/CONTRIBUTING.md).

### Core Branch

The project has a single core branch that serves as the foundation for development:

- `main`: Development branch containing the latest stable features. All changes should be merged into this branch after review and testing.

> 🚫 Never commit directly to `main`.

### Supporting Branches

Supporting branches are created and used for specific purposes, and can be categorized into three main types, as described below.

#### Topic Branches

Used for general development of new features, bug fixes, or other changes.

- **Base:** `main`
- **Example:** `feat/add-new-parser`

Topic branches can serve **multiple development purposes**. See the [Naming Conventions](#️-naming-conventions) section for more details on all available branch types (excluding `release` and `hotfix`).

The expected workflow for these branches is as follows:

1. Create the topic branch from `main` and use it for development
2. After the changes are ready, **rebase** the topic branch onto the latest `main`, reordering commits if necessary and fixing any conflicts that may arise
3. While **rebasing** interactively, take the opportunity to **pick/reword/squash/fixup commits** where necessary, to keep the history clean
4. After the local **rebase** is complete, make sure to also update the remote topic branch on **GitHub** with `git push --force-with-lease`
5. Open a **Pull Request** from the topic branch targeting `main`, and merge it after the review is complete
6. After the **PR** is merged into `main`, delete the topic branch

#### Release Branches

Used to prepare a new release for the project — includes version bumping, changelogs, etc.

- **Base:** `main`
- **Example:** `release/v1.0.0`

Release branches are created when the project is ready for a **new version release**, and they allow for **final adjustments and QA/Staging**.

The expected workflow for these branches is as follows:

1. Create the release branch from `main` and use it for final adjustments, such as version bumping and updating changelogs
2. Perform any necessary **testing and QA** on the release branch
3. After the release is ready, **tag** the latest commit on the release branch with the released version (e.g. `v1.0.0`)
4. Create a **GitHub Release** for the tagged commit, including release notes and changelog
5. Open a **Pull Request** from the release branch targeting `main`, and merge it while solving any conflicts that may arise
6. After the **PR** is merged into `main`, delete the release branch

#### Hotfix Branches

Used to quickly patch production code.

- **Base:** `release tag` (e.g. `v1.0.0`)
- **Example:** `hotfix/fix-login-crash`

Hotfix branches are created for **urgent fixes** that need to be applied to the production codebase immediately.

The expected workflow for these branches is as follows:

1. Create the hotfix branch from the `release tag` that matches the production environment (e.g. `v1.0.0`)
2. Make the necessary changes to fix the issue on the hotfix branch
3. After the hotfix is ready, **tag** the latest commit on the hotfix branch with the released patch (e.g. `v1.0.1`)
4. Create a **GitHub Release** for the tagged commit, including patch notes and fixes
5. Open a **Pull Request** from the hotfix branch targeting `main`, and merge it while solving any conflicts that may arise
6. If there is an active **release branch**, open a **Pull Request** from the hotfix branch targeting the **release branch**, and merge it while solving any conflicts that may arise
7. After the **PR** is merged into `main` (and into the **release branch** if the previous step applies), delete the hotfix branch

[📚 Back to Table of Contents](#-table-of-contents)

## 🏷️ Naming Conventions

The project follows specific naming conventions for **commit messages**, **supporting branch names**, and **pull request titles** to maintain clarity and consistency across the codebase.

### Commit Messages

For writing **commit messages**, use the following convention:

`<optional-emoji> <type>(optional scope): short description`

Here are the available values for `<type>` with some commit message examples:

| Type       | Purpose                                              | Commit Example                                                     |
| ---------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| `feat`     | Introduces a new feature                             | `✨ feat(api): add validator for user input`                        |
| `fix`      | Fixes a bug                                          | `🐛 fix: correct file not found error in document processing`       |
| `docs`     | Adds or improves documentation                       | `📝 docs(readme): improve usage section`                            |
| `style`    | Code style changes (formatting, whitespace, etc.)    | `🎨 style: improve order of functions in processing module`         |
| `refactor` | Code refactoring that doesn't change behavior        | `♻️ refactor(llm): simplify prompt generation logic`                |
| `perf`     | Improves performance                                 | `⚡️ perf(parser): optimize text parsing with regex pre-compilation` |
| `test`     | Adds or modifies tests                               | `✅ test(llm): add edge case tests for LLM output parser`           |
| `build`    | Changes that affect the build system or dependencies | `🔧 build(docker): restructure build process`                       |
| `ci`       | Changes to CI/CD pipelines or configs                | `👷 ci: add linting step to GitHub Actions`                         |
| `chore`    | Routine tasks like maintenance, dependency updates   | `⬆️ chore: update dependency versions`                              |
| `revert`   | Reverts a previous commit                            | `⏪ revert: revert "feat: add text deduplication"`                  |
| `merge`    | Merges changes from a Pull Request into `main`       | `🔀 merge(#77): feat/api-support`                                   |

The `<optional-emoji>` can be used to visually categorize the commit, but is not strictly required.
The project uses the emoji convention from [Gitmoji](https://gitmoji.dev/), which is also available in the [Gitmoji VS Code Extension](https://marketplace.visualstudio.com/items?itemName=seatonjiang.gitmoji-vscode).

### Supporting Branch Names

For naming **supporting branches**, use the following convention:

`<type>/<short-descriptive-name>`

Here are the available values for `<type>` with some branch name examples:

| Type       | Purpose                                              | Branch Example               |
| ---------- | ---------------------------------------------------- | ---------------------------- |
| `feat`     | New features or enhancements                         | `feat/api-support`           |
| `fix`      | Bug fixes                                            | `fix/login-error`            |
| `docs`     | Documentation-only changes                           | `docs/api-reference`         |
| `refactor` | Code restructuring without behavior change           | `refactor/simplify-pipeline` |
| `perf`     | Performance improvements                             | `perf/cache-optimization`    |
| `test`     | Experimental work or testing                         | `test/improve-config-tests`  |
| `build`    | Changes that affect the build system or dependencies | `build/migrate-to-poetry`    |
| `ci`       | Changes to CI/CD pipelines or configs                | `ci/setup-github-actions`    |
| `chore`    | Routine tasks like maintenance, dependency updates   | `chore/update-dependencies`  |
| `release`  | Preparing a new release                              | `release/v1.0.0`             |
| `hotfix`   | Urgent fixes to production code                      | `hotfix/fix-login-crash`     |

### Pull Request Titles

For naming **pull requests**, use the following convention:

`<type>(optional scope): short description`

Here, `<type>` can be any of the **supporting branch types** listed previously.

Example **PR** titles:

- `feat(core): add support for custom data models`
- `hotfix(parsing): resolve critical error with document parsing`

[📚 Back to Table of Contents](#-table-of-contents)

## 📦 Project Versioning

We follow [Semantic Versioning](https://semver.org/) **(MAJOR.MINOR.PATCH)** to manage project versions:

- **MAJOR**: Incompatible API changes or breaking changes
- **MINOR**: New features that are backwards compatible
- **PATCH**: Bug fixes or small improvements

> 🌿 The expected use of release/hotfix branches is shown in the [Branching Strategy](#-branching-strategy) section.
>
> 📝 All releases are documented in the [CHANGELOG](../CHANGELOG.md) file.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Tooling & Infrastructure

This project uses a set of foundational tools and automation to support development and delivery.

### Dependency Management

[Poetry](https://python-poetry.org/) is used for managing project dependencies and virtual environments.
The following files are key to this setup:

- **Dependencies/Packaging:** `pyproject.toml`
- **Poetry Lockfile:** `poetry.lock`
- **Pip-compatible Lockfile:** `requirements.txt`

### Containerization

[Docker](https://www.docker.com/) is used to provide a consistent environment for users to run the project, as well as to facilitate deployment.

The `Dockerfile` defines the **image/container setup**, and the `scripts/` directory contains utility shell scripts for **simplifying usage of the Docker container**.

### Continuous Integration/Deployment

Currently, the project **does not implement CI/CD** functionalities. The following ideas could be implemented in the future, using **GitHub Actions**:

- **CI**: Run **tests** and other checks on each **Pull Request**
- **CD**: Automatically deploy to **production** on **tagged releases/hotfixes**, and to **staging** on updates to **release branches**

[📚 Back to Table of Contents](#-table-of-contents)