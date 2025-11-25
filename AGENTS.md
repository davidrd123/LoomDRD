# LoomDRD – Agent & Contributor Guidelines

This file is for both human contributors and AI agents working in this repo.  
It describes how the project is organized, how to run things, and the expectations for code, tests, and docs.

Scope: applies to the entire repository unless superseded by a more specific `AGENTS.md` in a subdirectory.

---

## Project Structure & Docs

- Core design and behavior:
  - `Docs/loom_spec_v0.md` — conceptual spec and data model for Loom v0.
  - `Docs/loom-backend-plan.md` — concrete Python backend plan (dataclasses, interfaces, layout).
- Architecture decisions and process:
  - `Docs/adr/` — ADRs; read or update these when changing boundaries or making non-trivial tradeoffs.
  - `Docs/testing-strategy.md` — testing philosophy, structure, and coverage expectations.
  - `Docs/README.md` — overview of the docs and how they fit together.
- Examples:
  - `Docs/examples/` — sample briefs/sessions/manifests (when present).

As implementation proceeds, the Python package layout should follow `Docs/loom-backend-plan.md` (e.g. `loom/core`, `loom/io`, `loom/selectors`, `loom/cli.py`), and tests should mirror modules under `tests/`.

---

## Environment, Build & Test Commands

- **Python version:** target Python 3.11+.
- **Environment manager:** use [`uv`](https://github.com/astral-sh/uv) as the default tool.
  - Create/sync environment:
    - `uv sync`
  - Run tests:
    - `uv run pytest`
  - Add dependencies:
    - Runtime: `uv add <package>`
    - Dev-only (tests, tooling): `uv add --group dev <package>`
- Phase 0 dependencies are minimal (stdlib + `pytest`, `pytest-cov`, optional `hypothesis`), defined in `pyproject.toml`.
- When adding new commands or workflows, document them briefly in the relevant doc (e.g. `Docs/README.md` or a feature-specific doc) rather than only in commit messages.

---

## Coding Style & Conventions

- **Language:** Python for backend/orchestrator; TypeScript/React for future tree viewer UI.
- **Python style:**
  - PEP 8, 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes.
  - Prefer type hints on public functions and dataclasses.
  - Keep modules cohesive; avoid large “god modules.”
  - Avoid unnecessary global state; favor pure functions where practical.
- **Data model & config:**
  - Treat `Node`, `DecisionEvent`, `Loom`, and config types as core infrastructure.
  - Maintain invariants described in `Docs/loom_spec_v0.md` and `Docs/loom-backend-plan.md`.
  - Logprob fields are **optional**; v0 (Claude CLI-sim) should treat `None` as the normal case.
- **Dependencies:**
  - Keep runtime deps lean; add only what’s needed and document why in the relevant doc or ADR.

---

## Testing Guidelines

- **Framework:** `pytest`.
  - Tests should live under `tests/`, mirroring the package layout (e.g. `loom/core/models.py` → `tests/core/test_models.py`).
  - Aim for:
    - ≥90% line coverage on core models and IO (per `Docs/testing-strategy.md`).
    - Strong coverage of invariants and failure modes, not just happy paths.
- **LLM & network usage in tests:**
  - Tests must not depend on live network calls or real LLMs.
  - Use fakes/mocks for generators and Anthropic clients.
  - For logprob-related code paths, use synthetic generators that populate `step_logprob` rather than calling real models.
- **Kinds of tests:**
  - Unit tests for dataclasses and helpers: creation, invariants, serialization round-trips, query methods.
  - Integration tests for orchestrator/CLI/FastHTML endpoints once they exist.
  - Future: component tests for the React/TS tree viewer and minimal E2E checks.
- Before merging changes that affect core behavior, add or update tests so they encode the new expectations.

---

## Docs, ADRs, and Sync

- Treat docs and ADRs as **first-class artifacts**, not afterthoughts.
  - When you change core behavior, update:
    - The spec (`Docs/loom_spec_v0.md`) if the conceptual model changes.
    - The backend plan (`Docs/loom-backend-plan.md`) if types/interfaces/layout change.
    - Relevant ADRs or add a new ADR under `Docs/adr/` for significant architectural decisions.
    - `Docs/testing-strategy.md` if testing approach or coverage expectations change.
- Keep `Docs/README.md` roughly in sync with new docs so newcomers know where to look.

---

## Commit & PR Guidelines

- Prefer small, focused commits with clear messages (e.g., `feat: add Loom dataclasses`, `test: cover manifest logging`, `docs: clarify base engine choice`).
- When a commit implements or changes an ADR, reference the ADR ID in the commit message or PR description.
- Describe how you verified changes:
  - Which tests you ran (`uv run pytest`, specific modules).
  - Any manual flows you exercised (once CLI/UI exist).

---

## Agent Guidance (for AI assistants)

- Before making changes:
  - Read `Docs/README.md` to understand the doc layout.
  - Skim `Docs/loom_spec_v0.md`, `Docs/loom-backend-plan.md`, the relevant ADRs, and `Docs/testing-strategy.md`.
- When modifying code:
  - Follow the coding style and testing guidelines above.
  - Prefer modifying or adding tests in line with `Docs/testing-strategy.md` rather than leaving behavior untested.
  - Avoid introducing new external dependencies without updating `pyproject.toml` and briefly explaining why in a doc or ADR.
- When updating behavior or interfaces:
  - Ensure docs and ADRs remain consistent with the new behavior.
  - Call out any intentional divergences from the existing spec and, if appropriate, propose an ADR.

