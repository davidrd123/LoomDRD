# ADR 002: UI Strategy and Tech Stack

Status: Proposed  
Date: 2025-11-25

## Context

- We want three UI levels:
  - Basic: current text + candidate choices (no tree).
  - Medium: web UI with linear history of the chosen path.
  - Advanced: interactive tree visualization of the full loom.
- We are comfortable with Python, JavaScript, and TypeScript, and want an excuse to explore FastHTML.
- The backend will be Python (ADR 001), exposing Loom state and operations via functions and/or HTTP APIs.

## Decision

Adopt a staged, multi-layer UI strategy:

- **Phase 1 UI (Python-only)**
  - Implement a **rich CLI** (using `rich`) for human selection and inspection:
    - Show current context and candidates.
    - Accept numeric choice / stop input.
  - Implement a **FastHTML** web UI that:
    - Displays current text.
    - Shows candidates as clickable buttons.
    - Shows linear history of chosen segments along the active path.

- **Phase 2 UI (Tree Viewer with React + TypeScript)**
  - Expose a read-only JSON API from Python, e.g. `GET /loom/{session_id}` returning `nodes`, `decision_events`, and `current_path`.
  - Build a small **React + TypeScript** SPA focused on visualization:
    - Render the Loom as a graph (e.g. via `react-flow` or `cytoscape.js`).
    - Highlight current path vs rejected branches.
    - Support pan/zoom and basic node interactions (hover, click-to-focus).
  - Keep React/TS client thin: no core business logic; Loom state lives in the Python backend.

## Alternatives Considered

- **All-in FastHTML (including tree visualization via embedded JS/D3)**
  - Pros: single Python stack; simple deployment story.
  - Cons: more manual wiring for graph ergonomics; less leverage from existing graph UI ecosystems; harder to strongly type client-side Loom structures.

- **All-in React/TypeScript from day one**
  - Pros: strong typing and mature tooling for rich UIs.
  - Cons: higher upfront investment before the core phenomenology loop is fun; distracts from validating segment sizes, branching factor, and selector behavior.

- **Server-side only Graphviz SVG**
  - Pros: minimal JS; quick to generate static tree views.
  - Cons: limited interactivity; not ideal as the primary UX once the system matures.

## Consequences

- Early iterations (Phase 1) stay Python-centric and close to the backend, making it easy to iterate on Loom behavior without JS/TS overhead.
- When richer visualization becomes important (Phase 2), React + TypeScript provide strong typing for Loom structures on the client and a good ecosystem for graph UIs.
- The separation of concerns is clear:
  - FastHTML: operational control (start sessions, choose candidates, basic history).
  - React/TS: analysis and visualization (exploring the branching tree).

