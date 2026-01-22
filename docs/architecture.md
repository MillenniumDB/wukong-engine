<!-- omit from toc -->
# 🏗️ Architecture Guidelines

This document defines the architectural practices for the project.
It is intended as a **living reference** for developers as the system evolves.

The architecture follows **Clean Architecture Principles**, adapted pragmatically for **Python**.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧭 General Overview](#-general-overview)
  - [Core Principles](#core-principles)
  - [Layered Architecture](#layered-architecture)
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

### Layered Architecture

When the project starts, the initial architectural layers should be:

```
domain/
application/
infrastructure/
presentation/
```

As the system grows, new layers may appear, but **only as justified** by emerging policy (extremely rare).

### Dependency Rules

Each layer has specific rules about what it may and must not depend on.

#### Allowed Dependencies

```
infrastructure → application → domain
presentation → application
```

Here, the right arrow (`→`) means "may depend on".

#### Forbidden Dependencies

- `domain` must not import anything else
- `application` must not import `infrastructure` or `presentation`
- `infrastructure` must not import `presentation`
- `presentation` must not import `domain` or `infrastructure` (except for user-defined infra concerns like `logging`)

### Program Execution

When executing the program, the entry point lives in one of the **inbound channels** from the `presentation` layer (e.g. `presentation/api/main.py`), and should be called directly or through a custom console script.

All *long-lived and stateless components* from all layers are then instantiated and wired together inside the `bootstrap` package, which lives alongside the other layers at the top level. This package must contain modules that have access to all layers and act as **composition roots** for different execution contexts (e.g. **CLI, API**). These modules expose context objects that are imported in the `presentation` entry points to provide access to the required `application` **use cases, services, and workflows.**

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
└── graph/  # Domain definitions for a graph
    ├── entities.py  # Mutable objects with a unique identity (e.g. Graph, Node, Edge)
    └── values.py  # IDs, types, enums and other immutable objects (e.g. GraphID, NodeID, EdgeID)
```

As the system grows, the structure may evolve to:

```
domain/
├── graph/  # Domain definitions for a graph
│   ├── entities/  # Mutable objects with a unique identity
│   │   ├── graph.py
│   │   ├── node.py
│   │   └── edge.py
│   ├── values/  # IDs, types, enums and other immutable objects
│   │   ├── graph_id.py
│   │   ├── node_id.py
│   │   └── edge_id.py
│   ├── services/  # Complex stateless operations
│   │   └── graph_merger.py
│   ├── events/  # Specific domain occurrences
│   │   └── node_added.py
│   └── exceptions.py  # Graph-related exceptions
...
└── <concept>/  # e.g. user, project
```

### Best Practices

- Contains the core business concepts, rules, and invariants
- Models express meaning and are grouped by concept/subdomain (e.g. `graph`, `user`)
- **Entities** are mutable objects with a unique identity (e.g. `User`, `Graph`), which can be aggregated if needed (e.g. `Graph` contains `Node` and `Edge`)
- **Value objects** are immutable objects defined by their attributes (e.g. `Email`, `GraphID`)
- Domain **services** are stateless operations that model complex behavior between multiple entities/values (e.g. `GraphMerger`)
- Domain **events** represent significant occurrences in the domain (e.g. `NodeAdded`)
- Prefer explicit types over primitives (value objects instead of native **Python** types)
- Domain exceptions express business failures and propagate to `application`
- Avoid frameworks, external libraries, and side effects
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

- Orchestrates `domain` logic
- Defines system capabilities (use cases, services, workflows)
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
└── graph_building/  # Application logic for building graphs
    ├── use_cases/  # Application use cases (atomic actions)
    │   └── build_graph.py
    └── ports/  # External abstract interfaces
        └── graph_repository.py
```

As the system grows, the structure may evolve to:

```
application/
├── graph_building/  # Application logic for building graphs
│   ├── use_cases/  # Application use cases (atomic actions)
│   │   ├── build_graph.py
│   │   └── export_graph.py
│   ├── services/  # Application services (coordinators/helpers)
│   │   └── graph_manager.py
│   ├── workflows/  # Application workflows (orchestrators)
│   │   └── graph_construction.py
│   ├── ports/  # External abstract interfaces
│   │   ├── graph_repository.py
│   │   └── graph_exporter.py
│   ├── dtos/  # Data Transfer Objects (DTOs)
│   │   ├── build_graph.py
│   │   └── export_graph.py
│   ├── policies/  # Decision logic
│   │   ├── build_strategy.py
│   │   └── export_format.py
│   └── exceptions.py  # Graph-related exceptions
...
├── <sub_domain>/  # e.g. project_execution, document_processing
...
└── exceptions.py  # Application-wide exceptions
```

### Best Practices

- Orchestrates `domain` operations and implements `application` use cases, services, and workflows inside subdomains (e.g. `graph_building`)
- Defines **ports** *(abstract protocols)* for required external behavior to be implemented in `infrastructure` (e.g. `GraphRepository`)
- Defines **DTOs** *(static data classes)* for data exchange with `presentation` *(commands, queries, results)* (e.g. `ExportGraphCommand`)
- Use cases are atomic, explicit and user-facing, named after user intent (e.g. `ExportGraph`, `BuildGraph`)
- Use cases depend on ports and should consume/produce DTOs to interact with `presentation`
- Services encapsulate supporting application logic and are named after their role (e.g. `GraphManager`)
- Workflows orchestrate multiple use cases/services and are named in a process-oriented manner (e.g. `GraphConstruction`)
- Business-driven policy and strategy selection lives here, making use of factory ports implemented in `infrastructure` when needed (e.g. `LLMProvider` port used to obtain an `LLMClient` adapter)
- May catch `domain` and `application` exceptions, handling them or translating to `application` exceptions
- Application exceptions express workflow failures and propagate to `presentation`

### Evolution

- This is the **main growth layer**, where new business capabilities appear
- New subdomains, use cases, services, workflows, ports, and DTOs are added
- Outbound/Inbound policy migrates here from `infrastructure`/`presentation`

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
│   └── client.py
├── config/  # Configuration management
│   └── settings.py
└── logging/  # Logging configuration
    └── config.py
```

As the system grows, the structure may evolve to:

```
infrastructure/
├── persistence/  # Databases/Stores
│   ├── neo4j/
│   │   ├── graph_repository.py  # Adapter
│   │   ├── models.py  # Neo4j models
│   │   └── mappers.py  # Map domain objects to/from Neo4j models
│   ├── sqlalchemy/
│   │   ├── user_repository.py
│   │   ├── models.py
│   │   └── mappers.py
│   └── exceptions.py
├── llm/  # LLM Providers
│   ├── openai_client.py
│   ├── anthropic_client.py
│   └── exceptions.py
...
├── <application_concern>/  # e.g. filesystem, external_services, messaging, search
...
├── config/  # Configuration management
│   ├── settings.py
│   └── environments.py
├── logging/  # Logging configuration
│   └── config.py
...
└── <infrastructure_concern>/  # e.g. security, telemetry
```

### Best Practices

- Contains all technical details and integrations
- Implements `application` ports using adapters, which work with `domain`/`application` objects and basic types
- Adapters must be thin, replaceable and implementation-focused
- Adapters may apply syntactic and structural validation (not semantic) if needed
- Prefer role-based names for adapters (e.g. `neo4j/graph_repository.py` implements `Neo4jGraphRepository`)
- Cross-cutting infrastructure concerns (e.g. `config`, `logging`, `security`, `telemetry`) live here
- Business-driven strategy logic moves to `application`, which can then obtain the concrete adapter through a factory port (e.g. `LLMProvider` returns `OpenAILLMClient`)
- Technical strategy logic is managed here, including dynamic selection of adapters based on *configuration/environment/availability*
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

It answers:

> **“How do external actors interact with the system?”**

### Dependencies

**May Import**

- Application
- External libraries and frameworks
- Composition root modules from `bootstrap`

**Must NOT Import**

- Domain
- Infrastructure (except for user-defined infra concerns like `logging`)

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
│   ├── graph/  # Graph-related API component
│   │   ├── schemas/  # API schemas for input/output
│   │   │   └── graph.py
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
└── errors.py  # Shared user-facing error mapping
```

### Best Practices

- Hosts entry points for inbound channels, which import composition roots from `bootstrap` to instantiate presentation context
- Translates external input into `application` use cases, services and workflows using handlers (converts input schemas into `application` DTOs)
- Translates `application` results, DTOs and errors into channel-specific responses using handlers (converts them into output schemas/errors)
- Handlers must be thin and procedural, prefer intent-based names (e.g. `build_graph`)
- Handlers may apply syntactic and structural validation (not semantic) if needed
- Strategy logic moves to `application`/`infrastructure`, including dynamic management of technical concerns based on user input
- Uses printing for user-facing output in CLI, logging for technical concerns
- May catch `application` exceptions, handling them and exiting the program (or raising a framework-required exception)
- Presentation does not define or raise exceptions, it only maps them to user-facing error behavior (except for framework-required exceptions)

### Evolution

- New inbound channels appear
- Old channels may be deprecated
- General structure remains stable

[📚 Back to Table of Contents](#-table-of-contents)