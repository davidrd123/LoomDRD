# Loom Testing Strategy

Status: Draft  
Date: 2025-11-25

## Goals

- Maintain **high-confidence, high-coverage tests** for the Loom codebase.
- Treat the Loom backend and data model as **infrastructure**, not just app code.
- Keep tests **fast, deterministic, and hermetic** (no network, no real LLM calls).
- Use tests as an executable form of the **specs in** `Docs/loom_spec_v0.md` and `Docs/claude_plan.md`.

## Tooling & Structure

### Python (Backend, Orchestrator, FastHTML)

- Test runner: `pytest`
- Coverage: `coverage.py` (or `pytest --cov`)
- Optional: property-based tests with `hypothesis` for invariants

Suggested layout:

- `tests/`
  - `tests/core/` – `Node`, `DecisionEvent`, `Loom`, `SessionConfig`
  - `tests/io/` – serialization, manifests, file formats
  - `tests/selectors/` – human, stateless, agentic selector flows (with mocks)
  - `tests/cli/` – CLI entry points and user flows (rich CLI)
  - `tests/web/` – FastHTML handlers and HTTP-level behavior

### Frontend (React + TypeScript Tree Viewer, Phase 3)

- Unit/Component tests: `vitest` or `jest` + `@testing-library/react`
- E2E/smoke tests: `playwright` or `cypress` (minimal, focused)

Suggested layout (when the UI exists):

- `ui/`
  - `src/` – React/TS source
  - `tests/` – unit/component tests
  - `e2e/` – optional browser-level tests

## Test Levels

### 1. Unit Tests (Core)

Focus on small pieces with no I/O:

- `Node`, `DecisionEvent`, `Loom` behaviors:
  - Creation helpers (`create_root`, `from_candidate`, `DecisionEvent.create`, `resolve_*`).
  - Invariants: parent links, `current_path` consistency, `root_id` rules.
  - Query helpers: `get_rejected_at`, `get_last_n_decisions`, `find_divergences`, `find_clarifications`.
- Serialization:
  - `Loom.to_dict` / `Loom.from_dict` round-trips.
  - Stable JSON shapes for nodes/decisions.
- IO helpers:
  - Manifest log functions append correctly formatted NDJSON lines.

Where appropriate, add **property-based tests** for:

- Tree invariants (e.g. all nodes reachable from `root_id`).
- Simple graph properties (no cycles, path consistency).

### 2. Integration Tests (Python)

Compose multiple components with **stubbed dependencies**:

- Orchestrator + `Generator`:
  - Use a fake `Generator` that returns deterministic candidates.
  - Run the decision loop for several steps; assert Loom structure and manifest output.
- Human/CLI flow:
  - Simulate user input (e.g. `1`, `stop`) and assert:
    - Correct nodes are chosen.
    - `current_path` matches choices.
- FastHTML web endpoints:
  - Use a test client to hit routes (start session, fetch state, commit choice).
  - Assert JSON responses and Loom updates.

All integration tests must **not** hit real network services or LLM APIs. Use:

- Fake `Generator` implementations.
- Mock Anthropics/Together/vLLM clients at the boundary.

### 3. Selector Tests (Stateless + Agentic)

#### Stateless Selector

- Given fixed inputs (brief, context, candidates), test:
  - JSON schema validation.
  - Correct mapping from selector output to `DecisionEvent` and Loom updates.
- Use **frozen “golden” outputs** from a real run (checked into `tests/data/`) for regression when helpful, but do not require live calls in tests.

#### Agentic Selector

- Mock the LLM client so that:
  - Tool calls (`generate_candidates`, `commit_choice`, `request_human_input`, `query_loom`) are exercised.
  - The selector loop can be stepped deterministically.
- Assert:
  - Correct tool inputs are generated.
  - Loom and manifest state changes match expectations.

### 4. UI Tests

#### FastHTML (Phase 1)

- Request-level tests:
  - Starting a session creates a Loom with correct root node.
  - Choosing a candidate updates `current_path` and the rendered view.
- No browser automation required; rely on HTML/JSON assertions.

#### React + TypeScript Tree Viewer (Phase 3)

- Component tests:
  - Graph component renders nodes/edges from a Loom JSON snapshot.
  - Current path is highlighted, rejected branches styled differently.
- Contract tests:
  - Type-safe Loom JSON types (e.g. `zod` or TypeScript interfaces) aligned with backend schema.
- Optional E2E:
  - Minimal flows (load session, pan/zoom, click-to-focus).

## LLM-Specific Guidelines

- **No test should depend on live LLM behavior.**
  - All LLM-facing clients must be mocked in tests.
  - Use deterministic fake responses for both candidate generation and selector decisions.
- Where we want to guard against regressions in prompts or tool schemas:
  - Store **frozen transcripts** or JSON examples under `tests/data/`.
  - Assert that we still produce/accept the same wire-level schema.

## Coverage Expectations

- **Core backend (core + io):** target ≥ 90% line coverage and good branch coverage on critical methods.
- **Selectors & orchestrators:** target ≥ 80% coverage, with key paths exercised (choose/clarify/stop, logprob_gap handling).
- **CLI & FastHTML:** target ≥ 70% coverage; focus on main flows rather than every edge case of presentation.
- **React/TS UI:** aim for component-level tests for key views; exact coverage can be looser but should still protect the main interactions.

Coverage is a **tool**, not a goal by itself:

- Prioritize tests that enforce invariants and catch regressions in Loom structure, not just line execution.
- Prefer a smaller number of **high-value tests** over superficial micro-tests.

## CI Expectations

- On every push and PR:
  - Run Python tests: `pytest` with coverage.
  - (When present) run UI tests: `npm test` or equivalent.
  - Fail the build if coverage drops below agreed thresholds.
- Keep CI fast:
  - Heavy or long-running experiments belong in separate scripts, not in the test suite.

## Phase Alignment

- **Phase 0:** focus on unit tests for data model and serialization + manifest IO.
- **Phase 1:** add integration tests for CLI and FastHTML flows with fake generators.
- **Phase 2:** add selector tests (stateless + agentic) with mocked LLM clients.
- **Phase 3:** add JSON contract tests and UI tests for the tree viewer.

This document should be updated as the codebase grows, especially when:

- We add new selector modes or generators.
- We introduce new public APIs or JSON schemas.
- We refine coverage targets or CI workflows.

