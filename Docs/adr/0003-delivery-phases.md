# ADR 003: Delivery Phases

Status: Proposed  
Date: 2025-11-25

## Context

- `Docs/loom_spec_v0.md` already outlines a v0 implementation plan:
  - Core types and persistence.
  - Human-only CLI prototype.
  - Stateless selector.
  - Agentic selector with tools.
  - Analysis helpers and queries.
- We have now also decided on:
  - A Python-first backend (ADR 001).
  - A staged UI strategy using CLI + FastHTML first, then React/TS for tree visualization (ADR 002).
- We want a consolidated, phased roadmap that integrates these decisions and is easy to track.

## Decision

Adopt a phased delivery plan that layers capabilities on top of a stable data model and APIs:

### Phase 0 – Core Types & Persistence

- Implement in Python:
  - `Node`, `DecisionEvent`, `Loom`, `SessionConfig`.
  - JSON save/load for Loom (`load_loom(path)`, `save_loom(path)`).
  - NDJSON manifest logging (`append_decision_manifest(path, DecisionEvent)`).
- Enforce Loom invariants (root, current_path consistency, etc.).

### Phase 1 – Human-First Operation (No Tree)

- Implement a `Generator` abstraction and at least one concrete generator
  (e.g. CLI-sim Claude or a base model via vLLM/Together).
- Implement `loom/cli.py`:
  - Load brief/intent/examples from files.
  - Initialize a Loom session from seed text.
  - Run a loop: generate N candidates → display → accept numeric choice/stop.
  - Persist Loom and NDJSON manifest per session.
- Implement a **FastHTML** UI:
  - Start sessions from seed + brief.
  - Show current text, candidates, and linear history of chosen nodes.
  - Allow clicking to choose or stop.

### Phase 2 – Selector Automation

- Add a **stateless selector**:
  - Orchestrator generates candidates.
  - Calls an LLM once with brief + context + candidates.
  - Receives JSON decision (`choose` / `clarify` / `stop`) and applies it via `commit_choice`.
- Add an **agentic selector**:
  - Expose tools: `generate_candidates`, `commit_choice`, `request_human_input`, `query_loom`.
  - Run Claude (or similar) as a tool-using agent that drives the loom loop.
  - Reuse the same underlying Loom API and manifest logging.

### Phase 3 – Tree Visualization & Analysis

- Optional intermediate: generate **static SVG** tree views (e.g. Graphviz) embedded in FastHTML for quick visual inspection.
- Build a dedicated **React + TypeScript** tree viewer:
  - Consume Loom JSON from the Python API.
  - Render the branching structure with `react-flow`, `cytoscape.js`, or similar.
  - Highlight current path, rejected branches, and clarify events.
- Add analysis helpers on top of the manifest and Loom:
  - Queries like “last N decisions”, “find divergences by logprob_gap”, “list all clarify events”.

## Consequences

- Each phase is independently shippable and usable:
  - Phase 0–1 already give a human-in-the-loop phenomenology substrate.
  - Phase 2 adds LLM-driven selection without changing core structures.
  - Phase 3 adds richer visualization and analysis on top of stable APIs.
- The plan reduces risk by:
  - Validating the core loop (human + CLI/FastHTML) before investing in complex UIs.
  - Reusing the same Loom and manifest structures across human, stateless, and agentic selectors.

