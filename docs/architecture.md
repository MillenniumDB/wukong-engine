<!-- omit from toc -->
# 🏗️ Architecture Guidelines

This document defines the architectural practices for the project.
It is intended as a **living reference** for developers as the system evolves.

The architecture follows **Clean Architecture Principles**, adapted pragmatically for **Python**.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧭 General Overview](#-general-overview)
  - [Core Principles](#core-principles)
  - [Initial Architecture](#initial-architecture)
  - [Dependency Rules](#dependency-rules)
    - [Allowed Dependencies](#allowed-dependencies)
    - [Forbidden Dependencies](#forbidden-dependencies)
- [🧠 Domain Layer](#-domain-layer)
  - [Recommended Names](#recommended-names)
  - [Purpose](#purpose)
  - [Dependencies](#dependencies)
  - [Typical Structure](#typical-structure)
  - [Best Practices](#best-practices)
  - [Evolution](#evolution)
- [🧩 Application Layer](#-application-layer)
  - [Recommended Names](#recommended-names-1)
  - [Purpose](#purpose-1)
  - [Dependencies](#dependencies-1)
  - [Typical Structure](#typical-structure-1)
  - [Best Practices](#best-practices-1)
  - [Evolution](#evolution-1)
- [🛠️ Infrastructure Layer](#️-infrastructure-layer)
  - [Recommended Names](#recommended-names-2)
  - [Purpose](#purpose-2)
  - [Dependencies](#dependencies-2)
  - [Typical Structure](#typical-structure-2)
  - [Best Practices](#best-practices-2)
  - [Evolution](#evolution-2)
- [🖥️ Presentation Layer](#️-presentation-layer)
  - [Recommended Names](#recommended-names-3)
  - [Purpose](#purpose-3)
  - [Dependencies](#dependencies-3)
  - [Typical Structure](#typical-structure-3)
  - [Best Practices](#best-practices-3)
  - [Evolution](#evolution-3)

## 🧭 General Overview

### Core Principles

The architecture is based on the following core principles:

1. **Dependency direction always points inward**
2. **Policy is separated from mechanisms**
3. **Layers are promoted only when they earn responsibility**
4. **Clarity beats symmetry**
5. **Evolution is reactive, not speculative**

### Initial Architecture

When the project starts, the initial architectural layers should be:

```
domain/
application/
infrastructure/
presentation/
```

As the system grows, new layers may appear, but **only as justified** by emerging policy (very rare).

### Dependency Rules

Each layer has specific rules about what it may and must not depend on.

#### Allowed Dependencies

```
infrastructure → application → domain
presentation → application → domain
```

Here, the right arrow (`→`) means "may depend on".

#### Forbidden Dependencies

- `domain` must not import anything else
- `application` must not import `infrastructure` or `presentation`
- `infrastructure` must not import `presentation`
- `presentation` must not import `infrastructure` (except for technical concerns like logging)

> **Rule of Thumb**:
> Outer layers may depend on inner layers — never the reverse.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧠 Domain Layer

### Recommended Names

- `domain`
- `core`

### Purpose

Contains **pure business logic**.

It defines:

- Core concepts and invariants
- Business rules that must *always* hold
- Stable logic independent of frameworks, IO, or delivery

It answers:

> **“What exists in this system?”**

### Dependencies

**May Import**

- **Python** standard library

**Must NOT Import**

- Application
- Infrastructure
- Presentation
- External frameworks

### Typical Structure

The initial structure could look like:

```
domain/
├── model.py  # Core domain model
├── enums.py  # Domain enums
├── rules.py  # Business rules
└── exceptions.py  # Domain-specific exceptions
```

As the system grows, the structure may evolve to:

```
domain/
├── graph/  # Domain model for graph concepts
│   ├── graph.py
│   ├── entity.py
│   ├── relationship.py
│   ├── enums.py
│   ├── rules.py
│   └── exceptions.py
...
├── <concept>/  # e.g. schema, document
...
├── enums.py
├── rules.py
└── exceptions.py
```

### Best Practices

- Contains the core business concepts, rules, and invariants
- Models express meaning, not persistence or transport concerns
- Entities and value objects enforce consistency and validity
- Domain services exist only for cross-entity rules
- Prefer explicit types over primitives (value objects instead of native **Python** types)
- Domain exceptions express business failures
- Avoid frameworks, libraries, and side effects
- No orchestration, workflows, or use-case sequencing
- Stable over time; changes reflect business change only

### Evolution

- The domain **never gains new layers**
- Growth happens by *new concepts*, not technical roles
- Purity must be preserved indefinitely

[📚 Back to Table of Contents](#-table-of-contents)

## 🧩 Application Layer

### Recommended Names

- `application`
- `app`

### Purpose

Contains **application-specific policy**.

It:

- Orchestrates domain logic
- Defines system behavior (use cases)
- Encodes decision logic and strategies
- Defines **ports (interfaces)** for infrastructure

It answers:

> **“What does the system do?”**

### Dependencies

**May Import**

- Domain

**Must NOT Import**

- Infrastructure
- Presentation
- Frameworks or concrete adapters

### Typical Structure

The initial structure could look like:

```
application/
├── graph/  # Application logic for graph-related use cases
│   ├── use_cases/
│   |   └── build_graph.py
│   └── ports/
│       └── storage.py
...
├── <capability>/  # e.g. document_processing, extraction
...
├── workflow.py  # Orchestrates application workflows
└── exceptions.py  # Application-specific exceptions
```

As the system grows, the structure may evolve to:

```
application/
├── graph/
│   ├── use_cases/  # Use cases
│   │   ├── build_graph.py
│   │   └── export_graph.py
│   ├── services/  # Supporting services
│   │   └── deduplication.py
│   ├── ports/  # Interfaces for infrastructure
│   │   ├── storage.py
│   │   └── export.py
│   ├── policies/  # Decision logic
│   │   ├── build_strategy.py
│   │   └── export_format.py
│   └── exceptions.py
...
├── <capability>/  # e.g. document_processing, extraction
...
├── workflow.py
└── exceptions.py
```

### Best Practices

- Orchestrates use cases and application workflows
- Defines ports (interfaces) for required external behavior (`Protocol` or **ABCs**)
- Coordinates multiple domain operations in a single intent
- Contains no persistence, transport, or framework code
- Use cases are explicit, named after user intent (`process_document`, `build_graph`)
- Policy and strategy selection lives here
- Application DTOs express use-case intent
- Application exceptions express workflow failures
- Thin, readable, and highly testable

### Evolution

- This is the **main growth layer**
- Outbound/Inbound policy migrates here from `infrastructure`/`presentation`
- In very large systems, a dedicated top-level `policy` layer may be extracted from here (rare)

[📚 Back to Table of Contents](#-table-of-contents)

## 🛠️ Infrastructure Layer

### Recommended Names

- `infrastructure`
- `infra`

### Purpose

Contains **technical implementations** that interact with the external world.

It:

- Implements application ports (adapters)
- Handles communication with external tools and services
- Loads configuration

It manages:

- File system access
- Database repositories
- External API / SDK clients
- LLM providers
- Serialization / Deserialization
- Framework or vendor-specific code

It answers:

> **“How does the system interact with the external world?”**

### Dependencies

**May Import**

- Application
- Domain
- External libraries and frameworks

**Must NOT Import**

- Presentation

### Typical Structure

The initial structure could look like:

```
infrastructure/
├── adapters/  # Technical adapters
│   ├── persistence/
│   │   └── graph_repository.py
│   ├── llm/
│   │   └── openai_client.py
|   ...
│   └── <technical_concern>/  # e.g. external_api, telemetry, messaging
│       └── <adapter>.py  # e.g. logging
├── config/  # Configuration management
│   └── env.py
└── serialization/  # Data serialization/deserialization
    └── json.py
```

As the system grows, the structure may evolve to:

```
infrastructure/
├── adapters/
│   ├── persistence/  # Databases
│   │   ├── mdb_repository.py
│   │   ├── document_store.py
|   |   ...
│   │   ├── <persistence_adapter>.py  # e.g. neo4j_repository
|   |   ...
|   |   └── exceptions.py
│   ├── filesystem/  # File I/O
│   │   ├── json_loader.py
|   |   ...
│   │   ├── <filesystem_adapter>.py  # e.g. parquet_loader
|   |   ...
|   |   └── exceptions.py
│   ├── llm/  # LLM Providers
│   │   ├── openai_client.py
│   │   ├── local_llm_client.py
|   |   ...
│   │   ├── <llm_adapter>.py  # e.g. anthropic_client
|   |   ...
|   |   └── exceptions.py
|   ...
│   └── <technical_concern>/  # e.g. external_api, telemetry, messaging
│       ├── <adapter>.py  # e.g. logging
|       ...
|       └── exceptions.py
├── config/
│   ├── env.py
│   ...
│   ├── <config_module>.py  # e.g. defaults
│   ...
|   └── exceptions.py
└── serialization/
    ├── json.py
    ...
    ├── <serializer>.py  # e.g. parquet
    ...
    └── exceptions.py
```

### Best Practices

- No business or decision logic
- Contains all technical details and integrations
- Adapters must be thin, replaceable and implementation-focused
- Implements application-defined ports
- Translates infra data into domain/application models
- Prefer role-based names for adapters (`graph_repository.py`) (vendor/framework names are acceptable here)
- Outbound strategy logic moves to `application`
- Cross-cutting concerns (config, logging, serialization) live here
- Infrastructure exceptions represent technical failures

### Evolution

- New adapters are added
- Old adapters may be replaced
- General structure remains stable

[📚 Back to Table of Contents](#-table-of-contents)

## 🖥️ Presentation Layer

### Recommended Names

- `presentation`
- `interfaces`

### Purpose

Contains **inbound interaction** with the system.

It:

- Accepts input from external actors
- Invokes application use cases
- Translates results for external consumption

It manages:

- CLI commands
- API handlers / routes
- Request parsing
- Response formatting
- Error translation
- Input schemas / validation (without business logic)

It answers:

> **“How do external actors interact with the system?”**

### Dependencies

**May Import**

- Application
- Domain
- External libraries and frameworks

**Must NOT Import**

- Infrastructure (except for technical concerns like logging)

### Typical Structure

The initial structure could look like:

```
presentation/
├── cli/
│   └── main.py
...
├── <inbound_channel>/  # e.g. api
...
├── mappers.py  # Translation to internal app models
├── logging.py  # User-facing logging
└── errors.py  # User-facing error mapping
```

As the system grows, the structure may evolve to:

```
presentation/
├── cli/  # Command Line Interface
│   ├── app.py
│   ├── logging.py
│   ├── errors.py
│   ├── commands/
│   ├── handlers/
│   ...
│   └── <cli_package>/  # e.g. output
├── api/  # HTTP API
│   ├── app.py
│   ├── dependencies.py
│   ├── errors.py
│   ├── routers/
│   ├── handlers/
│   ...
│   └── <api_package>/  # e.g. schemas, middleware
...
├── <inbound_channel>/  # e.g. webhooks, jobs, messaging, gui
...
├── mappers/
│   ├── graph.py
│   ...
│   └── <mapper>.py  # e.g. documents
├── logging.py
└── errors.py
```

### Best Practices

- No business or decision logic
- Handlers must be thin and procedural
- Translates input into application commands / DTOs
- Translates application results and errors into channel-specific responses
- Prefer intent-based names (`run_engine_handler.py`)
- Validation is syntactic and structural, not semantic
- Error mapping belongs here, exception definitions belong in `application` and `domain`
- Logging is request-scoped and boundary-focused
- Strategy and orchestration logic moves to `application`

### Evolution

- New inbound channels appear
- Old channels may be deprecated
- General structure remains stable

[📚 Back to Table of Contents](#-table-of-contents)