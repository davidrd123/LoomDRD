# Loom v0 – Agentic Selection Architecture

Status: **design complete, implementation pending**
Scope: **text‑only loom**, single active path, optional parallel paths later

---

## 1. Purpose (Short)

Normal LLM generation hides all the interesting stuff:

* Base model samples one path through token space.
* All the other “could‑have‑been” tokens disappear.
* Any story about “why this word” is retrospective.

Loom externalizes that process:

1. **Base model** generates *multiple* short continuations at each step.
2. **Selector agent (Claude)** sees them *plus* the brief and full text.
3. Selector chooses:

   * `choose` → commit a branch
   * `clarify` → ask human a conceptual question
   * `stop` → end the piece
4. **Loom store** keeps:

   * every candidate as a node
   * every decision as a DecisionEvent
   * logprobs, reasons, divergences vs base distribution

This gives you a **phenomenology substrate**: a graph of text + decisions you can query later. 

You already have a precedent for this style of manifest + logging in the Comfy automation system (NDJSON manifest, job markers, etc.); Loom follows the same spirit. 

---

## 2. Core Actors

### 2.1. Base Engine

* Stateless generator of candidate segments.
* Knows:

  * Few‑shot example texts (texture)
  * Section intent / rough draft
  * Crafted text so far
* Does *not* know selection criteria (no “aliveness” rules).

Possible implementations:

* true base model (e.g. Qwen base via Together / vLLM)
* Claude in CLI‑sim mode (`cat untitled.txt`, `temperature=1`, `top_p=1`)

### 2.2. Loom Store

* Persistent text tree + decision log.
* Knows:

  * All nodes (chosen + rejected)
  * All decision events
  * Current active path
* No aesthetic judgment.

### 2.3. Selector Agent (Claude with tools)

* Runs as an **agent** with tools:

  * `generate_candidates`
  * `commit_choice`
  * `request_human_input`
  * `query_loom`
* Has:

  * full creative brief
  * full text so far (active path)
  * explicit selection criteria.

### 2.4. Human

* Writes / edits brief.
* Answers clarification questions.
* Can override choices or stop.

### 2.5. Thin Orchestrator / Harness

* Plain Python, no opinions.
* Exposes tools to the selector.
* Owns:

  * Base model calls
  * Loom mutations
  * Session manifests and persistence.

---

## 3. Data Model

You’ll likely want a `loom/` module with `dataclasses`. This is the minimal v0 set.

### 3.1. Node

Every candidate becomes a Node, even if rejected.

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time

@dataclass
class Node:
    id: str
    parent_id: Optional[str]

    # Text span for this step
    text: str                   # this segment only
    full_text: str              # parent.full_text + text (cached)

    # Tokenization (optional but recommended)
    start_token_idx: int
    end_token_idx: int          # exclusive
    token_ids: List[int]
    token_logprobs: List[float] # may be empty if base has no logprobs
    step_logprob: Optional[float]  # aggregate for this segment

    # Selection provenance (for nodes on chosen paths)
    chosen_by: Optional[str] = None        # "selector_llm" | "human" | "auto"
    selection_reason: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)

    # Back‑link to the decision that produced this node
    decision_id: Optional[str] = None

    meta: Dict[str, Any] = field(default_factory=dict)
```

Notes:

* For rejected candidates, `chosen_by` stays `None`; they still have `decision_id`.
* `step_logprob` can be `None` in CLI‑sim mode (no logprobs).

### 3.2. DecisionEvent

A single “branch moment” with all options and the outcome.

```python
@dataclass
class DecisionEvent:
    id: str
    parent_node_id: str

    # All nodes that were offered at this decision point
    candidate_node_ids: List[str]

    # Outcome
    action: str                           # "choose" | "clarify" | "stop"
    chosen_node_id: Optional[str]         # if action=="choose"
    chosen_by: str                        # "selector_llm" | "human"
    reason: str

    # Clarification metadata (if action=="clarify")
    clarification_question: Optional[str] = None
    candidates_in_tension: Optional[List[str]] = None
    what_hinges_on_it: Optional[str] = None
    human_response: Optional[str] = None

    # Metrics
    scores: Dict[str, Any] = field(default_factory=dict)
    logprob_gap: Optional[float] = None   # chosen_logprob - max_logprob across candidates
    timestamp: float = field(default_factory=time.time)
```

Conventions:

* `action == "choose"`:

  * `chosen_node_id` **must** be set.
  * `logprob_gap` computed as `chosen.step_logprob - max(step_logprob)` where available.
* `action == "clarify"`:

  * `chosen_node_id` may be `None` initially; you can:

    * either create a subsequent `"choose"` event that references this one, or
    * reuse the same event and fill `chosen_node_id` + `human_response` after clarification.
* `action == "stop"`:

  * `chosen_node_id` must be `None`.
  * No new Node is created; this marks the end of `current_path`.

### 3.3. Loom

Single loom per session.

```python
@dataclass
class Loom:
    nodes: Dict[str, Node]
    decision_events: Dict[str, DecisionEvent]

    root_id: str
    current_path: List[str]              # node ids along active branch

    # Optional: alternate branches to keep exploring later
    held_paths: List[List[str]] = field(default_factory=list)

    # Optional session metadata
    meta: Dict[str, Any] = field(default_factory=dict)
```

Invariants:

* `nodes[root_id].parent_id is None`.
* `current_path[0] == root_id`.
* For any `node_id` in `current_path[1:]`, `nodes[node_id].parent_id` is the previous node in path.

---

## 4. Config & Session Objects

Useful to standardize this so your harness has something simple to pass around.

```python
@dataclass
class BaseEngineConfig:
    model_name: str
    segment_tokens: int = 6
    branching_factor: int = 8
    temperature: float = 1.0
    top_p: float = 1.0
    max_logprobs: int = 5         # 0 if not available

@dataclass
class SelectorConfig:
    model_name: str
    mode: str = "agentic"         # "agentic" | "stateless"
    show_logprobs: bool = True

@dataclass
class SessionConfig:
    id: str
    base_engine: BaseEngineConfig
    selector: SelectorConfig
    max_tokens_total: int = 1500  # rough budget for the piece (optional)

    # Paths for persistence / manifests
    output_dir: str = "loom_sessions"
    manifest_path: Optional[str] = None
```

---

## 5. Base Engine Interface

A simple interface to hide Together/vLLM/CLI details.

```python
from typing import Protocol

@dataclass
class GeneratedCandidate:
    node_id: str
    text: str
    token_ids: List[int]
    token_logprobs: List[float]
    step_logprob: Optional[float]

class BaseEngine(Protocol):
    def generate_candidates(
        self,
        *,
        full_text: str,
        fewshot_examples: str,
        section_intent: str,
        rough_draft: Optional[str],
        n: int,
        max_tokens: int,
    ) -> List[GeneratedCandidate]:
        ...
```

### 5.1. Base Prompt Shape

Inside `generate_candidates`, the orchestrator constructs something like:

```text
[FEW-SHOT TEXTURE EXAMPLES]
<example 1>
---
<example 2>
---

[SECTION INTENT]
<one or a few lines about what this section does>

[ROUGH VERSION / OUTLINE] (optional)
<rough content for this section>

[CRAFTED TEXT SO FAR]
<full_text from loom>

[CONTINUE]
```

**Important distinction:**

* **Intent / rough** are **descriptive**, not prescriptive.
  They say “what this part is about,” not “use style X, avoid Y.”
* Normative criteria (what counts as “good”) live in the selector’s brief.

---

## 6. Selector Side

### 6.1. Selection Criteria (Falsifiable)

**Select FOR:**

* **Syntactic pull** – makes you want to read the next word.
* **Image density** – concrete, specific, sensory over vague abstraction.
* **Surprise‑that‑fits** – unexpected but retrospectively inevitable.
* **Load‑bearing phrasing** – minimal filler; every word does work.
* **Register match** – fits the voice/texture described in the brief. 

**Select AGAINST:**

* Assistant‑mode hedging:

  * “As an AI…”, “It is important to note…”, “This suggests that…”
* Premature resolution:

  * Closing tension or over‑explaining metaphors too early.
* Generic mysticism:

  * Vague cosmic/energy talk not grounded in the piece’s own imagery.
* Filler & throat‑clearing:

  * “kind of”, “really”, “in a sense”, “actually”.
* Register breaks:

  * Sudden corporate, academic, or chatty tone unless brief allows.

These are the “aliveness” heuristics, stated so you can actually check them.

### 6.2. Attention Scopes

Prompt the selector to use multiple scopes:

* **Micro** – candidate span (2–8 tokens): rhythm, exact words.
* **Local** – last 1–2 sentences: does it land well right here?
* **Paragraph** – recent ~200 words: is this the right move for the section?
* **Global** – full piece: voice and thematic coherence.

Implementation hint: orchestrator can feed the agent both:

* `full_text` (global)
* `recent_context` (e.g. last two sentences) for local focus.

---

## 7. Tools API (Agentic Mode)

These are the tools you expose to the selector agent. Their Python signatures are “real”; you’ll also mirror them in your model’s tool schema.

### 7.1. `generate_candidates`

```python
def tool_generate_candidates(
    parent_node_id: str,
    n: int = 8,
    max_tokens: int = 6
) -> dict:
    """
    Called by selector to get N short candidate continuations from base engine.

    Returns JSON:
    {
      "parent_node_id": "...",
      "candidates": [
        {
          "node_id": "node_123",
          "text": "...",
          "step_logprob": -3.8    # optional
        },
        ...
      ]
    }
    """
```

Orchestrator steps:

1. Look up `parent_node = loom.nodes[parent_node_id]`.
2. Build base prompt with:

   * few‑shot examples
   * section intent / rough draft
   * `parent_node.full_text` (or full current_path text).
3. Call `BaseEngine.generate_candidates(...)`.
4. For each candidate:

   * Create a `Node` with:

     * `parent_id=parent_node_id`
     * `full_text = parent.full_text + candidate.text`
     * `decision_id=None` for now.
   * Add to `loom.nodes`.
5. Return candidate list (ids + text + step_logprob if available).

### 7.2. `commit_choice`

```python
def tool_commit_choice(
    parent_node_id: str,
    candidate_node_ids: List[str],
    payload: dict
) -> dict:
    """
    Commit a selection decision to the loom.

    payload:
      - action: "choose" | "clarify" | "stop"
      - chosen_node_id: str | null
      - chosen_by: "selector_llm" | "human"
      - reason: str
      - scores: dict (optional)
      - clarification_question: str (optional)
      - candidates_in_tension: [node_id, ...] (optional)
      - what_hinges_on_it: str (optional)
      - human_response: str (optional)

    Returns:
      {
        "decision_id": "...",
        "current_path": [...],
        "full_text": "...",   # new full_text for active path
      }
    """
```

Orchestrator:

1. Compute `max_logprob`/`chosen_logprob` if available → `logprob_gap`.
2. Create a `DecisionEvent` with:

   * `candidate_node_ids`
   * `action`, `chosen_node_id`, `chosen_by`, `reason`, etc.
3. Attach `decision_id` to each `Node` in `candidate_node_ids`.
4. If `action=="choose"`:

   * Extend `loom.current_path` with `chosen_node_id`.
   * Update chosen Node’s `chosen_by`, `selection_reason`, `scores`.
5. If `action=="stop"`:

   * Don’t extend path.
6. Append a manifest record (see §9).

### 7.3. `request_human_input`

You can model this as a separate tool, or just let `commit_choice(action="clarify")` trigger it internally.

Conceptually:

```python
def tool_request_human_input(
    question: str,
    candidates_in_tension: List[str],
    what_hinges_on_it: str
) -> dict:
    """
    Escalate to human; block until response.

    Returns:
      {
        "human_response": "...",
        "chosen_node_id": "node_XXX" | null
      }
    """
```

The harness shows a prompt/CLI to the human, then returns their answer. You then either:

* call `tool_commit_choice` again with `chosen_by="human"`, or
* fill `human_response` into the existing DecisionEvent and set `chosen_node_id`.

### 7.4. `query_loom`

Minimal v0 query surface:

```python
def tool_query_loom(query_type: str, **params) -> dict:
    """
    query_type:
      - "last_n_decisions": {n}
      - "rejected_at": {parent_node_id}
      - "find_divergences": {threshold}
      - "find_clarifications": {}

    Returns shape depends on query_type.
    """
```

Useful queries:

* `last_n_decisions(n)` → quick recap.
* `rejected_at(node)` → show roads not taken.
* `find_divergences(threshold)` → where selector fought base model (logprob_gap < –threshold).
* `find_clarifications()` → all conceptual fork points.

---

## 8. Stateless Selector Contract (Fallback)

When not running Claude as a full agent (e.g. experiments with a small model), you can fall back to a single “decide” call where orchestrator:

1. Generates candidates itself.
2. Calls selector with brief, context, candidates.
3. Gets back a JSON decision, then applies it via `commit_choice`.

### 8.1. Input shape

```json
{
  "brief": "...creative brief...",
  "full_text": "...complete piece so far...",
  "recent_context": "...last 1-2 sentences...",
  "candidates": [
    {"id": "node_1", "text": "candidate text 1", "logprob": -3.2},
    {"id": "node_2", "text": "candidate text 2", "logprob": -2.8},
    {"id": "node_3", "text": "candidate text 3", "logprob": -4.1}
  ]
}
```

### 8.2. Output shape

**Choose:**

```json
{
  "action": "choose",
  "choice": "node_2",
  "ranking": ["node_2", "node_1", "node_3"],
  "scores": {
    "node_1": {"pull": 0.4, "density": 0.6},
    "node_2": {"pull": 0.9, "density": 0.8},
    "node_3": {"pull": 0.5, "density": 0.4}
  },
  "reason": "node_2 continues the image concretely and increases tension without closing it."
}
```

**Clarify:**

```json
{
  "action": "clarify",
  "question": "A and C treat the process as continuous flow; B and D introduce rupture. Which frame are we in?",
  "candidates_in_tension": ["node_1", "node_3"],
  "what_hinges_on_it": "Continuous → phenomenology of flow; ruptured → phenomenology of discrete jumps."
}
```

**Stop:**

```json
{
  "action": "stop",
  "reason": "The last image completes the movement; further continuation would dilute it."
}
```

The **same JSON schema** is what your tools use internally in agentic mode, just split across calls.

---

## 9. Logging & Manifest

Mirroring your Comfy automation, use an **NDJSON manifest**: one line per DecisionEvent. 

Example line:

```json
{
  "session_id": "sess_2025-11-25T01",
  "decision_id": "dec_0042",
  "parent_node_id": "node_0041",
  "candidate_node_ids": ["node_0042a", "node_0042b", "node_0042c"],
  "chosen_node_id": "node_0042b",
  "action": "choose",
  "chosen_by": "selector_llm",
  "reason": "Concrete image, strong syntactic pull.",
  "max_logprob": -2.1,
  "chosen_logprob": -3.8,
  "logprob_gap": -1.7,
  "timestamp": 1700000000.0
}
```

Key field for later analysis:

* `logprob_gap`:

  * Negative → selector pushed *against* base model preference.
  * Zeroish → selector followed base distribution.
  * You can query “where is the selector doing real aesthetic work?”

You can also add a lighter session‑level manifest (like Comfy’s batch manifest) but the DecisionEvent log is the core.

---

## 10. Hyperparameters (v0 defaults)

For the “Loom / phenomenology” mode:

```python
SEGMENT_TOKENS   = 6       # 4–8 segment size, tune by feel
BRANCHING_FACTOR = 8
TEMPERATURE      = 1.0
TOP_P            = 1.0
LOGPROBS         = 5       # if base supports it
```

Fallback “stable” profile if needed:

```python
SEGMENT_TOKENS   = 8
BRANCHING_FACTOR = 4
TEMPERATURE      = 0.85
TOP_P            = 0.92
```

Selector context:

* Real setup: **full text** for Claude (200k window).
* Only use sliding windows if you’re forced onto a smaller model.

---

## 11. v0 Implementation Plan

You can treat this as a mini roadmap for the first code pass.

### Stage 0 – Core Types & Persistence

* Implement:

  * `Node`, `DecisionEvent`, `Loom`
  * `SessionConfig`
* Add:

  * `load_loom(path)`, `save_loom(path)` as JSON.
  * `append_decision_manifest(path, DecisionEvent)` → NDJSON line.

### Stage 1 – Human‑only Prototype

* Implement a simple `BaseEngine` wrapper (call OpenAI/Together/whatever).
* CLI:

  * Load brief, intent, examples from files.
  * Initialize `Loom` with root node (seed text).
  * Loop:

    * generate N candidates
    * print them with numbers
    * human picks or types `stop`
    * commit Node + DecisionEvent
  * Save loom + manifest at end.

This lets you tune:

* `SEGMENT_TOKENS`
* `BRANCHING_FACTOR`
* whether candidates feel overwhelming.

### Stage 2 – Stateless Selector

* Implement “selector as function”:

  * Build JSON input (brief, full_text, recent_context, candidates).
  * Call Claude/GPT as normal chat completion.
  * Parse JSON output and call `commit_choice`.

No tools yet; still orchestrator‑driven loop.

### Stage 3 – Agentic Selector (Tools)

* Wrap Stage 2 logic in tools:

  * `tool_generate_candidates`
  * `tool_commit_choice`
  * `tool_query_loom`
  * `tool_request_human_input`
* Run Claude as an agent with those tools available and the system prompt that:

  * describes brief
  * lists selection criteria
  * explains attention scopes
  * tells it to select / clarify / stop.

### Stage 4 – Analysis Helpers

* Scripts to answer questions like:

  * “List all decisions with `logprob_gap < -1.0`.”
  * “Show all clarify events and their questions.”
  * “Print chosen vs rejected text for decision X.”

---

## 12. Open Design Knobs (for later)

Not blockers for v0, but worth keeping in mind:

1. **Human direction mid‑piece (unprompted):**

   * v0: Human edits brief; selector re‑reads full brief each decision.
   * Later: add a `update_brief` tool / command.

2. **Multi‑path exploration:**

   * v0: stay linear (one `current_path`).
   * Later:

     * keep multiple `held_paths`,
     * run multiple selectors in parallel on different tips.

3. **Logprobs visibility to selector:**

   * v0: show aggregate `step_logprob` for each candidate, but remind it “lower logprob ≠ worse.”
   * Later: experiment with hiding logprobs to test selection bias.

4. **Base engine choice:**

   * Qwen base vs CLI‑sim Claude as pseudo‑base.
   * With CLI‑sim you lose logprobs → `logprob_gap` and divergence queries become unavailable or approximate.

