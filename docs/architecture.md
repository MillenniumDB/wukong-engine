<!-- omit from toc -->
# 🏗️ Architecture Guidelines

This document defines the architectural practices for the project.
It is intended as a **living reference** for developers as the system evolves.

The architecture follows **Clean Architecture principles**, adapted pragmatically for **Python**.

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
  - [Best practices](#best-practices-1)
  - [Evolution](#evolution-1)
- [🛠️ Infrastructure Layer](#️-infrastructure-layer)
  - [Recommended Names](#recommended-names-2)
  - [Purpose](#purpose-2)
  - [Dependencies](#dependencies-2)
  - [Initial recommended structure](#initial-recommended-structure)
  - [Best practices](#best-practices-2)
  - [Inbound vs Outbound](#inbound-vs-outbound)
  - [Inbound](#inbound)
  - [Outbound](#outbound)
  - [Adapters Namespace (Optional, Mature Systems)](#adapters-namespace-optional-mature-systems)
    - [Purpose](#purpose-3)
    - [Mature structure example](#mature-structure-example)
- [🖥️ Presentation Layer](#️-presentation-layer)
  - [Recommended Names](#recommended-names-3)
  - [Purpose](#purpose-4)
  - [Dependencies](#dependencies-3)
  - [Structure](#structure)
  - [Promotion rule](#promotion-rule)
- [📌 Architecture Summary](#-architecture-summary)
  - [Import Rules](#import-rules)
  - [Evolution Summary](#evolution-summary)
  - [One-Sentence Mental Model](#one-sentence-mental-model)

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

As the system grows, new layers may appear, but **only as justified** by emerging policy.

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
- `presentation` must not import `infrastructure`

> **Rule of Thumb**:
> Outer layers may depend on inner layers — never the reverse.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧠 Domain Layer

### Recommended Names

- `domain`
- `core`
- `model`

### Purpose

Contains **pure business logic**.

It defines:

- Core concepts and invariants
- Business rules that must *always* hold
- Stable logic independent of frameworks, IO, or delivery

It answers:

> **“What exists in this problem space?”**

### Dependencies

**May Import**

- **Python** standard library

**Must NOT Import**

- Application
- Infrastructure
- Presentation
- Frameworks, SDKs, databases, HTTP, LLM clients

### Typical Structure

The initial structure could look like:

```
domain/
├── model.py
├── enums.py
├── rules.py
└── exceptions.py
```

As the system grows, the structure may evolve to:

```
domain/
├── graph/
│   ├── graph.py
│   ├── entity.py
│   ├── relationship.py
│   ├── enums.py
│   ├── rules.py
│   └── exceptions.py
...
├── <concept>/  # e.g. schema, document
...
├── value_objects.py  # e.g. ConfidenceScore, Identifier
├── enums.py
├── rules.py
└── exceptions.py
```

### Best Practices

- Rich domain models over anemic data
- No persistence or transport concerns
- Avoid generic `utils/`
- Fully testable without mocks

### Evolution

- The domain **never gains new layers**
- Growth happens by *new concepts*, not technical roles
- Purity must be preserved indefinitely

[📚 Back to Table of Contents](#-table-of-contents)

## 🧩 Application Layer

### Recommended Names

- `application`
- `app`
- `services`

### Purpose

Contains **application-specific policy**.

It:

- Orchestrates domain logic
- Defines system behavior (use cases)
- Encodes decision logic and strategies
- Defines **ports (interfaces)** for infrastructure

It answers:

> **“What should the system do?”**

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
├── graph/
│   ├── use_cases.py
│   └── ports.py
...
├── <capability>/  # e.g. document_processing, extraction
...
├── workflow.py
└── exceptions.py
```

As the system grows, the structure may evolve to:

```
application/
├── graph/
│   ├── use_cases/
│   │   ├── build_graph.py
│   │   └── export_graph.py
│   ├── ports/
│   │   ├── storage.py
│   │   └── export.py
│   ├── policies/
│   │   ├── build_strategy.py
│   │   └── export_format.py
│   ├── dto/
│   │   ├── build.py
│   │   └── export.py
│   └── exceptions.py
...
├── <capability>/  # e.g. document_processing, extraction
...
├── workflow.py
└── exceptions.py
```

### Best practices

- Use verbs for use cases (`process_document`, `build_graph`)
- Keep use cases small and explicit
- Move outbound strategy logic here when it appears
- Use `Protocol` or **ABCs** for ports
- No IO, SDKs, HTTP, DB, or filesystem code

### Evolution

- This is the **main growth layer**
- Outbound policy migrates here from `infrastructure`
- In very large systems, a dedicated top-level `policy` layer may be extracted from here (rare)

[📚 Back to Table of Contents](#-table-of-contents)

## 🛠️ Infrastructure Layer

### Recommended Names

- `infrastructure`
- `infra`

### Purpose

Infrastructure contains **mechanisms, not policy**.

It:
- Implements Application ports
- Handles IO (databases, APIs, FS, LLM SDKs)
- Hosts entry points initially
- Wires dependencies

The Infrastructure answers:

> **“How is this executed?”**

### Dependencies

**May import**
- Application
- Domain
- External libraries and frameworks

**Must NOT import**
- Presentation

### Initial recommended structure

```
infrastructure/
├── inbound/
│   ├── api/
│   ├── cli/
│   └── batch/
├── outbound/
│   ├── persistence/
│   ├── llm/
│   └── filesystem/
└── wiring/
```

### Best practices

- Adapters must be thin
- No business or decision logic
- Translate infra data into domain/application models
- Centralize dependency wiring

### Inbound vs Outbound

### Inbound

- Entry into the system
- API, CLI, batch jobs, consumers
- Initially thin adapters
- Promoted when policy appears

### Outbound

- External dependencies
- Databases, APIs, LLMs, queues
- Strategy logic moves to Application
- Infrastructure remains mechanical

Separating inbound/outbound **from the start**:
- Makes direction explicit
- Prevents erosion
- Enables clean promotion later

### Adapters Namespace (Optional, Mature Systems)

#### Purpose

`adapters/` is introduced when Infrastructure becomes mixed.

It separates:
- Boundary-crossing code (adapters)
- Plumbing (wiring, config, telemetry)

#### Mature structure example

```
infrastructure/
├── adapters/
│   └── outbound/
│       ├── persistence/
│       ├── llm/
│       └── messaging/
├── wiring/
├── config/
└── telemetry/
```

It is **normal and desirable** for `adapters/` to contain **only outbound adapters**.

[📚 Back to Table of Contents](#-table-of-contents)

## 🖥️ Presentation Layer

### Recommended Names

- `presentation`
- `interfaces`

### Purpose

Presentation contains **inbound policy**.

It exists **only when inbound logic becomes decision-heavy**.

It handles:
- Authentication / authorization mapping
- Tenant and plan enforcement
- API versioning
- Request orchestration
- Response shaping

The Presentation answers:

> **“How is system behavior exposed and controlled?”**

### Dependencies

**May import**
- Application
- Domain (value objects, enums, exceptions)

**Must NOT import**
- Infrastructure

### Structure

```
presentation/
├── api/
├── cli/
└── batch/
```

### Promotion rule

Inbound code moves **directly** from Infrastructure → Presentation
(it does *not* pass through Application).

[📚 Back to Table of Contents](#-table-of-contents)

## 📌 Architecture Summary

### Import Rules

| Layer          | May Import                | Must NOT Import              |
| -------------- | ------------------------- | ---------------------------- |
| Domain         | stdlib                    | anything else                |
| Application    | Domain                    | Infrastructure, Presentation |
| Presentation   | Application, Domain       | Infrastructure               |
| Infrastructure | Application, Domain, libs | Presentation                 |

### Evolution Summary

| Concern         | Promotion Path                |
| --------------- | ----------------------------- |
| Inbound policy  | Infrastructure → Presentation |
| Outbound policy | Infrastructure → Application  |
| Domain logic    | Never promoted                |
| New layers      | Only when policy demands it   |

### One-Sentence Mental Model

> **Domain defines truth.
Application defines behavior.
Infrastructure executes.
Presentation exposes.**

[📚 Back to Table of Contents](#-table-of-contents)