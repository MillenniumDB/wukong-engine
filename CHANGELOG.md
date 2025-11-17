<!-- omit from toc -->
# 📝 Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

<!-- omit from toc -->
## 📚 Table of Contents
- [\[Unreleased\]](#unreleased)
  - [✨ Added](#-added)
  - [♻️ Changed](#️-changed)
- [\[0.2.0\] - 2025-10-23](#020---2025-10-23)
  - [✨ Added](#-added-1)
  - [♻️ Changed](#️-changed-1)
  - [🐛 Fixed](#-fixed)
  - [⚡ Performance](#-performance)
  - [📝 Documentation](#-documentation)
- [\[0.1.0\] - 2025-07-25](#010---2025-07-25)
  - [✨ Added](#-added-2)
  - [🛠️ Build](#️-build)
  - [📝 Documentation](#-documentation-1)

## [Unreleased]

### ✨ Added

- Simplified way for defining source and target entities in relations.

### ♻️ Changed

- Example data directory to use real estate legal data.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.2.0] - 2025-10-23

### ✨ Added

- Document set logic for processing different types of documents.
- Support for **Hybrid Entities**, which act as both core and local entities.
- Support for extracting property values from available metadata files associated with the documents.
- Support for placeholder and default property values.
- Support for regex matching when extracting property values.
- General statistics file for the knowledge graph after exporting.
- String representation method for the data model.

### ♻️ Changed

- Data directory structure to support document set logic.

### 🐛 Fixed

- Frozen thread issue where the LLM API never responds.

### ⚡ Performance

- Trim large documents for **Core Entity** extraction.

### 📝 Documentation

- Updated data model docs with new fields.
- Updated data directory structure in docs.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.1.0] - 2025-07-25

### ✨ Added

- Initial release of the **WUKONG** engine.
- Data model schema for representing knowledge graphs.
- Configuration file for engine settings.
- Support for a custom configuration file provided by the user.
- Support for processing plain text documents.
- Support for **GPT 4.1-mini** as the default **LLM** for extracting information from documents.
- Support for exporting knowledge graphs in **MDB**, **Neo4j** and **JSON** format.
- Basic command-line interface **(CLI)** for running the engine.
- Example data directory structure for testing purposes.
- Basic error handling and logging functionality.
- Support for loading environment variables via a `.env` file.
- **WUKONG** engine logos.

### 🛠️ Build

- **Docker** support for containerization on **Linux/MacOS/Windows**.
- **Poetry** configuration for dependency management.
- Linting and formatting setup with **Ruff** and **Pyright**.

### 📝 Documentation

- Initial documentation and basic license for the project.

[📚 Back to Table of Contents](#-table-of-contents)