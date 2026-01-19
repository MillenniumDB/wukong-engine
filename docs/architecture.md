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
- `presentation` must not import `infrastructure` (except for user-defined technical concerns like logging)

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
├── graph.py  # Domain entity
├── node.py  # Domain entity
├── edge.py  # Domain entity
└── values.py  # e.g. GraphID, NodeID, EdgeID
```

As the system grows, the structure may evolve to:

```
domain/
├── graph/  # Domain definitions for a graph
│   ├── graph.py  # Domain entity
│   ├── node.py  # Domain entity
│   ├── edge.py  # Domain entity
│   ├── values/  # IDs, types, enums and other immutables
│   │   ├── graph_id.py
│   │   ├── node_id.py
│   │   └── edge_id.py
│   ├── services/  # Stateless operations
│   │   └── graph_merge.py
│   ├── events/  # Facts that happened
│   │   └── node_added.py
│   └── exceptions.py  # Graph-related exceptions
...
└── <concept>/  # e.g. schema
```

### Best Practices

- Contains the core business concepts, rules, and invariants
- Models express meaning, not persistence or transport concerns
- Entities (mutable) and value objects (immutable) enforce consistency and validity
- Domain services (stateless operations) exist for complex behavior between entities/values
- Prefer explicit types over primitives (value objects instead of native **Python** types)
- Avoid frameworks, external libraries, and side effects
- No orchestration, workflows, or use-case sequencing
- Stable over time; changes reflect business change only
- Domain exceptions express business failures and propagate to `application`

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

- Orchestrates `domain` logic
- Defines system behavior (use cases)
- Encodes decision logic and strategies
- Defines abstract **ports** for `infrastructure`
- Defines **DTOs** for data exchange with `presentation`

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
    └── ports/  # External interfaces specific to graphs
        └── persistence.py  # GraphRepository
```

As the system grows, the structure may evolve to:

```
application/
├── graph/  # Application logic for graph-related use cases
│   ├── use_cases/  # Specific use cases
│   │   ├── build_graph.py
│   │   └── export_graph.py
│   ├── services/  # Supporting services
│   │   └── deduplication.py
│   ├── ports/  # External interfaces specific to graphs
│   │   ├── persistence.py  # GraphRepository
│   │   └── export.py
│   ├── policies/  # Decision logic
│   │   ├── build_strategy.py
│   │   └── export_format.py
│   ├── schemas/  # DTOs
│   │   ├── create_graph.py  # CreateGraphCommand, CreateGraphResult
│   │   └── update_graph.py
│   └── exceptions.py  # Graph-related exceptions
...
├── <sub_domain>/  # e.g. extraction
...
├── ports/  # General external interfaces
│   ├── persistence.py  # UserRepository
│   └── auth.py
├── workflows/  # Workflows that orchestrate multiple use cases
│   └── graph_construction.py  # Build and export a graph
└── exceptions.py  # Application-wide exceptions
```

### Best Practices

- Orchestrates `domain` operations, use cases and workflows
- Defines **ports** (abstract interfaces) for required external behavior to be implemented in `infrastructure`
- Defines **DTOs** (static data classes) for data exchange with `presentation` (commands, queries, results)
- Policy and strategy selection lives here
- Use cases are explicit, named after user intent (`process_document`, `build_graph`)
- Use cases depend on ports and may consume/produce DTOs
- If needed, use cases can convert DTOs to/from `domain` models, using `domain` constructors/factories or `application` mappers
- May catch `domain` and `application` exceptions, handling them or translating to `application` exceptions
- Application exceptions express workflow failures and propagate to `presentation`

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

- Implements `application` ports (adapters)
- Handles communication with external tools and services
- Manages configuration and cross-cutting concerns

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
├── persistence/  # Databases/Stores
│   └── graph_repository.py
├── llm/  # LLM Providers
│   └── llm_client.py
└── config/  # Configuration management
    └── settings.py
```

As the system grows, the structure may evolve to:

```
infrastructure/
├── persistence/  # Databases/Stores
│   ├── mdb/
│   │   ├── graph_repository.py
│   │   └── graph_query_executor.py
│   ├── neo4j/
│   │   ├── graph_repository.py
│   │   └── graph_query_executor.py
|   └── exceptions.py
├── llm/  # LLM Providers
│   ├── openai/
│   │   └── llm_client.py
│   ├── local/
│   │   └── llm_client.py
|   └── exceptions.py
...
├── <application_concern>/  # e.g. cache, messaging, search
...
├── config/  # Configuration management
│   ├── settings.py
|   └── environments.py
...
└── <infrastructure_concern>/  # e.g. logging, serialization, security, telemetry
```

### Best Practices

- Contains all technical details and integrations
- Implements `application` ports using adapters
- Adapters must be thin, replaceable and implementation-focused
- Prefer role-based names for adapters (`graph_repository.py`)
- May implement validation that enforces syntactic/structural correctness (not semantic)
- Cross-cutting concerns (config, logging, serialization) live here
- Outbound strategy logic moves to `application`
- May catch external framework exceptions, handling them or translating to `application` or `infrastructure` exceptions
- Infrastructure exceptions represent generalized technical failures and are converted to `application` exceptions before propagation

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
- Invokes `application` use cases
- Translates `application` results for external consumption

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
- External libraries and frameworks
- Composition root modules from `bootstrap`

**Must NOT Import**

- Infrastructure (except for user-defined technical concerns like logging)

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
│   │   ├── mappers.py  # Maps app DTOs to/from API schemas
│   │   └── errors.py
│   └── errors.py  # General API error mapping
├── cli/  # Command Line Interface
│   ├── main.py
│   ├── commands.py  # Maps CLI commands to handlers
│   ├── handlers.py  # Handlers for CLI commands
│   └── errors.py
...
├── <inbound_channel>/  # e.g. webhooks, jobs, messaging, gui
...
├── schemas/  # Shared schemas for input/output
│   ├── graph.py
│   ├── entity.py
│   └── relationship.py
└── errors.py  # Shared user-facing error mapping
```

### Best Practices

- Hosts entry points for inbound channels, which import composition roots from `bootstrap`
- Translates external input into `application` use cases using handlers (converts input schemas into DTOs)
- Translates `application` results, DTOs and errors into channel-specific responses using handlers (converts DTOs into output schemas)
- Handlers must be thin and procedural, prefer intent-based names (`create_graph`)
- Validation is syntactic and structural, not semantic
- Uses printing for user-facing output in CLI, logging for technical concerns
- Strategy and orchestration logic moves to `application`
- May catch `application` exceptions, handling them and exiting the program (or raising a framework-required exception)
- Presentation does not define or raise exceptions, it only maps them to user-facing error behavior (except for framework-required exceptions)

### Evolution

- New inbound channels appear
- Old channels may be deprecated
- General structure remains stable

[📚 Back to Table of Contents](#-table-of-contents)