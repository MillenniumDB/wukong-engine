<!-- omit from toc -->
# 🤝 Contributing to the Project

Thanks for your interest in contributing! Here's how you can help and what to know before you start.

<!-- omit from toc -->
## 📚 Table of Contents
- [🚀 Getting Started](#-getting-started)
- [🐛 Reporting Bugs / ✨ Suggesting Features](#-reporting-bugs---suggesting-features)
- [✅ Submitting Changes](#-submitting-changes)
- [🏷️ Naming Conventions](#️-naming-conventions)
  - [Commit Messages](#commit-messages)
  - [Branch Names](#branch-names)
  - [Pull Request Titles](#pull-request-titles)
- [📜 Code of Conduct](#-code-of-conduct)

## 🚀 Getting Started

To set up the project as an external contributor, follow these steps:

1. Fork this repository to your own **GitHub** account.

2. Clone your fork locally and navigate to the project directory:

```sh
git clone https://github.com/your-username/wukong-engine.git
cd wukong-engine
```

3. Switch to the development branch and create a new feature branch for your changes:

```sh
git checkout dev  # Make sure you're on the dev branch
git checkout -b my-feature-branch
```

4. Take a look at the [Development Guide](../docs/development.md) and follow the setup instructions and development practices for the project.

[📚 Back to Table of Contents](#-table-of-contents)

## 🐛 Reporting Bugs / ✨ Suggesting Features

Before making changes or submitting a pull request, please open an **Issue**:

- To **report a bug**, include steps to reproduce it and the expected behavior
- To **suggest a new feature or improvement**, briefly describe the problem it solves
- Use the available **issue templates** provided in **GitHub** to help structure your submission

This helps us track ideas, avoid duplicates, and prioritize development.

[📚 Back to Table of Contents](#-table-of-contents)

## ✅ Submitting Changes

Before submitting a contribution, please make sure to:

- ✅ **Pull the latest changes** from the `dev` branch and resolve any merge conflicts
- ✅ **Follow the code style guidelines**
- ✅ **Add or update tests** for new features or bug fixes
- ✅ **Ensure all tests pass**
- ✅ **Run the tool locally** to confirm it works as expected
- ✅ **Include clear and descriptive commit messages**
- ✅ **Do not commit secrets or credentials** (e.g. from `.env`, config files)

Once ready, open a **Pull Request** from your **feature branch** to the `dev` branch with:

- A clear title and summary of the changes
- Reference to any **relevant issue numbers** (e.g. Closes #42)
- Screenshots or output if useful for understanding the change
- Use the available **PR template** provided in **GitHub** to help structure your submission

Your **PR** will be reviewed by a maintainer. Please be patient and open to feedback!

[📚 Back to Table of Contents](#-table-of-contents)

## 🏷️ Naming Conventions

### Commit Messages

For writing **commit messages**, use the following convention:

`<optional-emoji> <type>: short description`

Here are the available values for `<type>` with some commit message examples:

| Type       | Purpose                                              | Commit Example                                             |
| ---------- | ---------------------------------------------------- | ---------------------------------------------------------- |
| `feat`     | Introduces a new feature                             | `feat: add validator for user input`                       |
| `fix`      | Fixes a bug                                          | `fix: correct file not found error in document processing` |
| `docs`     | Adds or improves documentation                       | `docs: update usage section in README`                     |
| `style`    | Code style changes (formatting, whitespace, etc.)    | `style: improve order of functions in processing module`   |
| `refactor` | Code refactoring that doesn't change behavior        | `refactor: simplify prompt generation logic`               |
| `perf`     | Improves performance                                 | `perf: optimize text parsing with regex pre-compilation`   |
| `test`     | Adds or modifies tests                               | `test: add edge case tests for LLM output parser`          |
| `chore`    | Routine tasks like maintenance, dependency updates   | `chore: update dependencies in pyproject.toml`             |
| `build`    | Changes that affect the build system or dependencies | `build: switch to poetry for package management`           |
| `ci`       | Changes to CI/CD pipelines or configs                | `ci: add GitHub Actions workflow for testing`              |
| `revert`   | Reverts a previous commit                            | `revert: revert "feat: add text deduplication"`            |

The `<optional-emoji>` can be used to visually categorize the commit, but is not strictly required. The project uses the emoji convention from [Gitmoji](https://gitmoji.dev/).

### Branch Names

For naming **feature branches**, use the following convention:

`<type>/<short-descriptive-name>`

Here are the available values for `<type>` with some branch name examples:

| Type       | Purpose                                    | Branch Example               |
| ---------- | ------------------------------------------ | ---------------------------- |
| `feature`  | New features or enhancements               | `feature/add-api-support`    |
| `fix`      | Bug fixes                                  | `fix/handle-null-values`     |
| `docs`     | Documentation-only changes                 | `docs/update-readme`         |
| `test`     | Adding or modifying tests                  | `test/improve-config-tests`  |
| `refactor` | Code restructuring without behavior change | `refactor/simplify-pipeline` |
| `chore`    | Maintenance tasks (e.g. tooling, deps)     | `chore/update-dependencies`  |
| `ci`       | Continuous integration config changes      | `ci/setup-github-actions`    |
| `build`    | Build system updates                       | `build/add-docker-support`   |
| `hotfix`   | Urgent fixes to production code            | `hotfix/fix-login-crash`     |
| `release`  | Preparing a new release                    | `release/1.0.0`              |

### Pull Request Titles

For naming **pull requests**, use the following convention:

`<type>: short description`

Here, `<type>` can be any of the **commit message types** listed previously.

Example **PR** titles:

- `feat: add support for custom data models`
- `fix: resolve issue with document parsing`

[📚 Back to Table of Contents](#-table-of-contents)

## 📜 Code of Conduct

All contributors are expected to adhere to the project's [Code of Conduct](./CODE_OF_CONDUCT.md). This includes treating others with respect, being inclusive, and fostering a positive environment for collaboration.

[📚 Back to Table of Contents](#-table-of-contents)