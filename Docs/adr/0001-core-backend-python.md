# ADR 001: Core Loom Backend in Python

Status: Proposed  
Date: 2025-11-25

## Context

- We already have detailed Python-oriented design docs in `Docs/loom_spec_v0.md` and `Docs/loom-backend-plan.md` (dataclasses, generator interfaces, orchestrator sketches).
- Loom’s core responsibilities are:
  - Data model: `Node`, `DecisionEvent`, `Loom`, `SessionConfig`.
  - Persistence and manifests (JSON + NDJSON).
  - Base-model integration via an abstract generator interface.
  - Selector loop orchestration (human, stateless LLM, agentic LLM).
- The broader LLM tooling ecosystem (Anthropic SDK, vLLM, Together, etc.) already has strong Python support, and the current mental models are expressed in Python.

## Decision

Implement the core Loom backend in **Python** as the single source of truth.

- Create a `loom/` package with:
  - `loom/core`: dataclasses, generator abstraction, orchestrator.
  - `loom/selectors`: human CLI selector, stateless selector, agentic selector.
  - `loom/io`: JSON/NDJSON persistence and manifest handling.
  - `loom/cli.py`: human-driven CLI entrypoint.
- Keep all authoritative Loom state (nodes, decisions, sessions) on the Python side; other components (CLI, FastHTML, React, etc.) talk to it via function calls or HTTP APIs.

## Alternatives Considered

- **Node/TypeScript backend**
  - Pros: strong static typing, good ecosystem for web backends.
  - Cons: diverges from existing Python-first design; duplicates work for LLM tooling; splits mental models across languages.

- **Polyglot backend (Python + Node)**
  - Pros: could use each language where it shines.
  - Cons: splits the data model and business logic; adds coordination overhead and serialization boundaries for core operations.

## Consequences

- Fast path from the current design docs to a working implementation.
- Python-first approach keeps base-model integration straightforward (vLLM, Together, Anthropic SDK).
- Frontends (CLI, FastHTML, React/TS) consume a simple Loom API and JSON structures; they do not own or duplicate core state.
- If we later add TypeScript/Node components, they remain thin clients over the Python Loom API rather than alternate sources of truth.
