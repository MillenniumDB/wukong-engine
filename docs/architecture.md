<!-- omit from toc -->
# 🏗️ Architecture Guidelines

This document defines the architectural practices for the project.
It is intended as a **living reference** for developers as the system evolves.

The architecture follows **Clean Architecture Principles**, adapted pragmatically for **Python**.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧭 General Overview](#-general-overview)
  - [Core Principles](#core-principles)
  - [Main Architecture](#main-architecture)
  - [Dependency Rules](#dependency-rules)
    - [Allowed Dependencies](#allowed-dependencies)
    - [Forbidden Dependencies](#forbidden-dependencies)
  - [Program Execution](#program-execution)
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

### Main Architecture

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
- `presentation` must not import `infrastructure` (except for user-dependent technical concerns like logging)

> **Rule of Thumb**:
> Outer layers may depend on inner layers — never the reverse.

### Program Execution

When executing the program, the entry point lives in one of the **inbound channels** from the `presentation` layer (e.g. `presentation/api/main.py`), and should be called directly or through a custom console script.

All relevant components from all layers are then instantiated and wired together inside the `bootstrap` package, which lives alongside the other layers at the top level. This package must contain modules that have access to all layers and act as **composition roots** for different execution contexts (e.g. **CLI, API**). These modules expose set-up functions that are imported in the `presentation` entry points to instantiate their respective compositions.

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
- External libraries and frameworks

### Typical Structure

The initial structure could look like:

```
domain/
├── model.py  # Core domain model
├── enums.py  # Domain enums
├── rules.py  # Business rules
└── exceptions.py  # Domain exceptions
```

As the system grows, the structure may evolve to:

```
domain/
├── graph/  # Domain definitions for a graph
│   ├── graph.py
│   ├── entity.py
│   ├── relationship.py
│   ├── enums.py  # Graph-related enums
│   ├── rules.py  # Graph-related business rules
│   └── exceptions.py  # Graph-related exceptions
...
├── <concept>/  # e.g. schema
...
└── shared/  # Shared across domain concepts
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
- Avoid frameworks, external libraries, and side effects
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
- Defines **ports** for infrastructure
- Defines **DTOs** for outer layers

It answers:

> **“What does the system do?”**

### Dependencies

**May Import**

- Domain

**Must NOT Import**

- Infrastructure
- Presentation
- External libraries and frameworks

### Typical Structure

The initial structure could look like:

```
application/
└── graph/  # Application logic for graph-related use cases
    ├── use_cases/  # Specific use cases
    |   └── build_graph.py
    └── ports/  # External interfaces
        └── storage.py
```

As the system grows, the structure may evolve to:

```
application/
├── graph/  # Application logic for graph-related use cases
│   ├── use_cases/  # Specific use cases
│   │   ├── build_graph/  # Complex use case
│   │   |   ├── use_case.py
│   │   |   ├── validators.py
│   │   |   └── steps.py
│   │   └── export_graph.py  # Simple use case
│   ├── services/  # Supporting services
│   │   └── deduplication.py
│   ├── ports/  # External interfaces
│   │   ├── storage.py
│   │   └── export.py
│   ├── policies/  # Shared decision logic
│   │   ├── build_strategy.py
│   │   └── export_format.py
│   ├── dto/  # Shared data transfer objects
│   │   └── graph_spec.py
│   ├── mappers/  # Shared App <-> Domain conversions
│   │   └── create_graph.py
│   └── exceptions.py  # Graph-related exceptions
...
├── <sub_domain>/  # e.g. extraction
...
├── workflows/  # Workflows that orchestrate multiple use cases
│   └── generate_graph.py  # Build and export a graph
└── shared/  # Shared across sub-domains
    ├── ports/
    │   └── file_loader.py
    └── exceptions.py
```

### Best Practices

- Orchestrates use cases and application workflows
- Defines **ports** (interfaces using `Protocol`) for required external behavior (`infrastructure`)
- Defines **DTOs** (static data classes) for data exchange with outer layers (`presentation`/`infrastructure`)
- Coordinates multiple domain operations in a single intent
- Use cases are explicit, named after user intent (`process_document`, `build_graph`)
- Use cases depend on ports and may consume/produce DTOs
- If needed, use cases can convert DTOs to/from domain models, using `domain` constructors/factories or `application` mappers
- Application exceptions express workflow failures
- Policy and strategy selection lives here

### Evolution

- This is the **main growth layer**, where new business capabilities appear
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
├── adapters/  # Outbound adapters
│   ├── persistence/  # Databases/Stores
│   │   └── graph_repository.py
│   └── llm/  # LLM Providers
│       └── openai_client.py
└── config/  # Configuration management
    └── env.py
```

As the system grows, the structure may evolve to:

```
infrastructure/
├── adapters/  # Outbound adapters
│   ├── persistence/  # Databases/Stores
│   │   ├── mdb_repository.py
│   │   ├── document_store.py
|   |   ...
│   │   ├── <persistence_adapter>.py  # e.g. neo4j_repository
|   |   ...
|   |   ├── mappers/  # Domain/App <-> Framework conversions
|   |   |   └── graph_mapper.py
|   |   └── exceptions.py
│   ├── filesystem/  # File I/O
│   │   ├── json_loader.py
|   |   ...
│   │   ├── <filesystem_adapter>.py  # e.g. parquet_loader
|   |   ...
|   |   └── exceptions.py
│   ├── llm/  # LLM Providers
│   │   ├── openai_client.py
│   │   ├── local_client.py
|   |   ...
│   │   ├── <llm_adapter>.py  # e.g. anthropic_client
|   |   ...
|   |   └── exceptions.py
|   ...
│   └── <application_concern>/  # e.g. api_clients, messaging
├── config/  # Configuration management
│   ├── env.py
│   ...
│   ├── <config_module>.py  # e.g. defaults
│   ...
|   └── exceptions.py
...
└── <infrastructure_concern>/  # e.g. logging, serialization, security, telemetry
```

### Best Practices

- No business or decision logic
- Contains all technical details and integrations
- Implements application-defined ports using adapters
- Adapters must be thin, replaceable and implementation-focused
- Prefer role-based names for adapters (`graph_repository.py`)
- Vendor/framework based names are acceptable for adapters
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

### Purpose

Contains **inbound interaction** with the system.

It:

- Accepts input from external actors
- Invokes application use cases
- Translates application results for external consumption

It manages:

- CLI commands
- API handlers / routes
- Request parsing
- Response formatting
- Error translation
- Input schemas / structural validation

It answers:

> **“How do external actors interact with the system?”**

### Dependencies

**May Import**

- Application
- Domain
- External libraries and frameworks
- Composition root modules from `bootstrap`
- Infrastructure (only for user-dependent technical concerns like logging)

**Must NOT Import**

- Infrastructure (in general)

### Typical Structure

The initial structure could look like:

```
presentation/
└── api/  # HTTP API
    ├── main.py  # Entry point
    ├── router.py  # Maps endpoints to handlers
    └── handlers.py  # Handlers for API endpoints
```

As the system grows, the structure may evolve to:

```
presentation/
├── api/  # HTTP API
│   ├── main.py
│   ├── graph/  # Graph-related component
│   │   ├── router.py
│   │   ├── handlers.py
│   │   ├── errors.py  # User-facing error mapping
│   │   └── mappers/  # Domain/App <-> Framework conversions
│   │       └── graph.py
│   ...
│   ├── <api_component>/  # e.g. documents
│   ...
│   └── shared/  # Shared across API components
│       └── errors.py
├── cli/  # Command Line Interface
│   ├── main.py
│   ├── errors.py
│   ├── commands.py  # Maps CLI commands to handlers
│   ├── handlers.py  # Handlers for CLI commands
│   ...
│   └── <cli_component>/  # e.g. output
...
├── <inbound_channel>/  # e.g. webhooks, jobs, messaging, gui
...
└── shared/  # Shared across inbound channels
    ├── schemas/  # Shared validation schemas
    │   ├── graph.py
    │   ├── entity.py
    │   └── relationship.py
    └── errors.py  # Shared user-facing error mapping
```

### Best Practices

- No business or decision logic
- Hosts entry points for inbound channels, which import composition roots from `bootstrap`
- Translates external input into application commands / DTOs using handlers (calls use cases directly)
- Translates application results, DTOs and errors into channel-specific responses using handlers (receives them directly)
- Handlers must be thin and procedural, prefer intent-based names (`create_graph`)
- Validation is syntactic and structural, not semantic
- Uses printing for user-facing output in CLI, logging for technical concerns
- Error mapping belongs here, exception definitions belong in `application` and `domain`
- Strategy and orchestration logic moves to `application`

### Evolution

- New inbound channels appear
- Old channels may be deprecated
- General structure remains stable

[📚 Back to Table of Contents](#-table-of-contents)