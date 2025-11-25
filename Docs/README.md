# Loom Docs Overview

This directory contains the core design and process documentation for Loom.

The goal is that a fresh reader (human or LLM) can quickly understand:

- What Loom is and how it works conceptually.
- How the backend is structured in Python.
- How architectural decisions are recorded.
- How we approach testing and quality.

## Documents

- `loom_spec_v0.md`
  - **What it is:** The primary architecture and behavior spec for Loom v0.
  - **Covers:**
    - Purpose and core actors (base engine, loom store, selector, human).
    - Data model (`Node`, `DecisionEvent`, `Loom`).
    - Config and session objects.
    - Base engine interface and prompt shape.
    - Selector criteria, attention scopes, and tools API.
    - Logging, manifests, and high-level implementation stages.
  - **Use this when:** You want the conceptual model or need to check “what Loom is supposed to do.”

- `loom-backend-plan.md`
  - **What it is:** Concrete backend implementation plan for the Python Loom backend.
  - **Covers:**
    - Dataclasses for `Node`, `DecisionEvent`, and `Loom`.
    - Serialization helpers and query methods.
    - Base engine (`Generator`) interface and v0 implementation (`ClaudeCLISimGenerator`).
    - Backend layout (`loom/core`, `loom/selectors`, `loom/io`, `cli.py`).
    - Selector skeletons (human/CLI, stateless LLM, agentic selector).
  - **Use this when:** You are implementing or modifying backend code and want concrete types, interfaces, and module structure.

- `testing-strategy.md`
  - **What it is:** The testing philosophy and concrete testing plan.
  - **Covers:**
    - Goals and principles (high coverage, deterministic, no live LLMs in tests).
    - Python test layout and tooling (`pytest`, coverage, optional `hypothesis`).
    - Integration tests for orchestrator, CLI, and FastHTML endpoints.
    - Selector tests (stateless and agentic) with mocked LLM clients.
    - Future UI tests for the React/TypeScript tree viewer.
  - **Use this when:** You are adding or modifying tests, or deciding how to validate new features.

- `adr/`
  - **What it is:** Architecture Decision Records (ADRs) capturing key choices and their rationale.
  - **Currently includes:**
    - `0001-core-backend-python.md` — Python as the single source of truth for Loom backend.
    - `0002-ui-strategy-and-tech-stack.md` — UI strategy: rich CLI + FastHTML first, React/TS tree viewer later.
    - `0003-delivery-phases.md` — Phased delivery plan from core types to automation and visualization.
    - `0004-base-engine-v0-claude-cli-sim.md` — v0 base engine choice: Claude CLI-sim.
  - **Use this when:** You are questioning “why did we choose X?” or considering changing a foundational decision.

- `examples/`
  - **What it is:** Example briefs, sessions, or manifests (when present).
  - **Use this when:** You want concrete sample inputs/outputs or to sanity-check behavior.
  - Includes `brief.toml` as a canonical structured brief example.

## Environment & Tooling

- **Python management:** Use [`uv`](https://github.com/astral-sh/uv) as the default way to manage the Python environment and run commands.
  - Create/sync environment (from `pyproject.toml`):
    - `uv sync`
  - Run tests:
    - `uv run pytest`
  - Add dependencies (runtime or dev):
    - `uv add <package>`
    - `uv add --group dev <package>`  # for test/dev-only deps
- The Phase 0 scope only requires the standard library plus the dev dependencies listed under the `dev` group in `pyproject.toml` (pytest, pytest-cov, hypothesis). Later phases will add runtime deps (e.g. Anthropic SDK, FastHTML, React tooling).

## How to Read This Repo as a New Contributor

1. Start with `loom_spec_v0.md` to get the conceptual model.
2. Read `loom-backend-plan.md` to see how that model becomes concrete Python code.
3. Skim the ADRs in `Docs/adr/` to understand major decisions and constraints.
4. Check `testing-strategy.md` before adding or changing behavior, so new code fits the testing philosophy.

This structure is intended to be stable; if new docs are added, please update this `README` with a short description and intended use. 
