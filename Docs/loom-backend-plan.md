## Loom Backend Implementation Plan

This document refines the architecture in `Docs/loom_spec_v0.md` into concrete Python types, interfaces, and components for the Loom backend.

It covers:

- Dataclasses for `Node`, `DecisionEvent`, and `Loom`.
- Base engine (`Generator`) interface and v0 implementation.
- Selector structures (human, stateless LLM, agentic LLM).
- High-level backend layout and CLI / UI integration.

---

## Core Dataclasses

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import time
import uuid


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Node:
    """
    A segment of text in the loom. Every candidate becomes a Node,
    whether chosen or rejected. The loom is a true graph.
    """
    id: str
    parent_id: Optional[str]

    # Text & tokens
    text: str                          # segment text (just this node)
    full_text: str                     # cached: all ancestors + this node
    token_ids: List[int]
    
    # Logprobs (None if using CLI-sim mode without logprob access)
    token_logprobs: Optional[List[float]] = None
    step_logprob: Optional[float] = None

    # Decision metadata (filled when this node is part of a decision)
    decision_id: Optional[str] = None  # which DecisionEvent included this node
    was_chosen: bool = False           # True if this node is on a chosen path
    chosen_by: Optional[str] = None    # "selector_llm" | "human" | None if rejected
    selection_reason: Optional[str] = None
    scores: Dict[str, float] = field(default_factory=dict)

    # Timestamps
    created_at: float = field(default_factory=time.time)
    
    # Arbitrary extras
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_root(cls, seed_text: str) -> "Node":
        """Create the root node from seed text."""
        return cls(
            id=new_id(),
            parent_id=None,
            text=seed_text,
            full_text=seed_text,
            token_ids=[],  # seed text tokens not tracked
            was_chosen=True,
        )

    @classmethod
    def from_candidate(
        cls,
        parent: "Node",
        text: str,
        token_ids: List[int],
        token_logprobs: Optional[List[float]] = None,
        step_logprob: Optional[float] = None,
    ) -> "Node":
        """Create a candidate node from generation output."""
        return cls(
            id=new_id(),
            parent_id=parent.id,
            text=text,
            full_text=parent.full_text + text,
            token_ids=token_ids,
            token_logprobs=token_logprobs,
            step_logprob=step_logprob,
        )


@dataclass
class DecisionEvent:
    """
    Record of a single selection moment. Captures all candidates
    (as node IDs) and the outcome.
    
    action semantics:
    - "choose": chosen_node_id is set, that node extends current_path
    - "clarify": selector paused for human input, may resolve to choose later
    - "stop": no new node created, chosen_node_id is None, marks end of path
    """
    id: str
    parent_node_id: str

    # All candidates at this branch point (each is a Node in loom.nodes)
    candidate_node_ids: List[str]

    # Selection outcome
    action: str                              # "choose" | "clarify" | "stop"
    chosen_node_id: Optional[str] = None     # set if action == "choose"
    chosen_by: Optional[str] = None          # "selector_llm" | "human"
    reason: str = ""

    # For clarify actions
    clarification_question: Optional[str] = None
    candidates_in_tension: Optional[List[str]] = None
    what_hinges_on_it: Optional[str] = None
    human_response: Optional[str] = None

    # Scores per candidate (keyed by node_id)
    candidate_scores: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Logprob analysis (None if logprobs unavailable)
    max_logprob: Optional[float] = None
    chosen_logprob: Optional[float] = None
    logprob_gap: Optional[float] = None      # chosen - max (negative = override)

    timestamp: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        parent_node_id: str,
        candidate_node_ids: List[str],
    ) -> "DecisionEvent":
        """Create a new decision event (before selection is made)."""
        return cls(
            id=new_id(),
            parent_node_id=parent_node_id,
            candidate_node_ids=candidate_node_ids,
        )

    def resolve_choose(
        self,
        chosen_node_id: str,
        chosen_by: str,
        reason: str,
        candidate_scores: Optional[Dict[str, Dict[str, float]]] = None,
        nodes: Optional[Dict[str, "Node"]] = None,
    ) -> None:
        """Resolve this event as a choice."""
        self.action = "choose"
        self.chosen_node_id = chosen_node_id
        self.chosen_by = chosen_by
        self.reason = reason
        if candidate_scores:
            self.candidate_scores = candidate_scores
        
        # Compute logprob_gap if we have nodes with logprobs
        if nodes:
            logprobs = [
                nodes[nid].step_logprob 
                for nid in self.candidate_node_ids 
                if nodes[nid].step_logprob is not None
            ]
            if logprobs and nodes[chosen_node_id].step_logprob is not None:
                self.max_logprob = max(logprobs)
                self.chosen_logprob = nodes[chosen_node_id].step_logprob
                self.logprob_gap = self.chosen_logprob - self.max_logprob

    def resolve_clarify(
        self,
        question: str,
        candidates_in_tension: List[str],
        what_hinges_on_it: str,
    ) -> None:
        """Resolve this event as a clarification request."""
        self.action = "clarify"
        self.clarification_question = question
        self.candidates_in_tension = candidates_in_tension
        self.what_hinges_on_it = what_hinges_on_it

    def resolve_stop(self, reason: str) -> None:
        """Resolve this event as a stop."""
        self.action = "stop"
        self.chosen_node_id = None
        self.reason = reason


@dataclass
class Loom:
    """
    The complete branching text structure.
    
    nodes: All nodes (chosen and rejected)
    decision_events: All selection moments
    current_path: Node IDs along the active branch
    held_paths: Alternative paths being explored in parallel
    """
    nodes: Dict[str, Node] = field(default_factory=dict)
    decision_events: Dict[str, DecisionEvent] = field(default_factory=dict)
    
    root_id: Optional[str] = None
    current_path: List[str] = field(default_factory=list)
    held_paths: List[List[str]] = field(default_factory=list)

    # Session metadata
    session_id: str = field(default_factory=new_id)
    brief: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(cls, seed_text: str, brief: str, config: Optional[Dict] = None) -> "Loom":
        """Initialize a new loom with seed text."""
        root = Node.create_root(seed_text)
        loom = cls(
            root_id=root.id,
            current_path=[root.id],
            brief=brief,
            config=config or {},
        )
        loom.nodes[root.id] = root
        return loom

    def get_current_text(self) -> str:
        """Get the full text of the current path."""
        if not self.current_path:
            return ""
        tip_id = self.current_path[-1]
        return self.nodes[tip_id].full_text

    def get_tip(self) -> Optional[Node]:
        """Get the current tip node."""
        if not self.current_path:
            return None
        return self.nodes[self.current_path[-1]]

    def add_candidates(self, parent_id: str, candidates: List[Node]) -> DecisionEvent:
        """
        Add candidate nodes and create a decision event.
        Returns the event (unresolved, awaiting selection).
        """
        candidate_ids = []
        for node in candidates:
            node.parent_id = parent_id
            self.nodes[node.id] = node
            candidate_ids.append(node.id)
        
        event = DecisionEvent.create(parent_id, candidate_ids)
        self.decision_events[event.id] = event
        
        # Link nodes to this decision
        for node in candidates:
            node.decision_id = event.id
        
        return event

    def commit_choice(self, event_id: str, chosen_node_id: str, chosen_by: str, reason: str) -> None:
        """Commit a selection, extending current_path."""
        event = self.decision_events[event_id]
        event.resolve_choose(chosen_node_id, chosen_by, reason, nodes=self.nodes)
        
        # Mark the chosen node
        chosen_node = self.nodes[chosen_node_id]
        chosen_node.was_chosen = True
        chosen_node.chosen_by = chosen_by
        chosen_node.selection_reason = reason
        
        # Extend path
        self.current_path.append(chosen_node_id)

    def commit_stop(self, event_id: str, reason: str) -> None:
        """Commit a stop, ending the current path."""
        event = self.decision_events[event_id]
        event.resolve_stop(reason)

    # === Query methods ===

    def get_rejected_at(self, node_id: str) -> List[Node]:
        """Get all candidates that were rejected when this node was chosen."""
        node = self.nodes.get(node_id)
        if not node or not node.decision_id:
            return []
        event = self.decision_events[node.decision_id]
        return [
            self.nodes[nid] 
            for nid in event.candidate_node_ids 
            if nid != event.chosen_node_id
        ]

    def get_last_n_decisions(self, n: int) -> List[DecisionEvent]:
        """Get the most recent n decisions."""
        events = sorted(
            self.decision_events.values(),
            key=lambda e: e.timestamp,
            reverse=True
        )
        return events[:n]

    def find_divergences(self, threshold: float = -1.0) -> List[DecisionEvent]:
        """
        Find decisions where selector overrode base model preference.
        threshold: logprob_gap below this value (e.g., -1.0 means chosen was
                   at least 1.0 logprob worse than best candidate)
        Returns empty list if logprobs unavailable.
        """
        return [
            event for event in self.decision_events.values()
            if event.logprob_gap is not None and event.logprob_gap < threshold
        ]

    def find_clarifications(self) -> List[DecisionEvent]:
        """Get all clarify events."""
        return [
            event for event in self.decision_events.values()
            if event.action == "clarify"
        ]

    # === Serialization ===

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON export."""
        from dataclasses import asdict
        return {
            "session_id": self.session_id,
            "root_id": self.root_id,
            "current_path": self.current_path,
            "held_paths": self.held_paths,
            "brief": self.brief,
            "config": self.config,
            "created_at": self.created_at,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "decision_events": {k: asdict(v) for k, v in self.decision_events.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Loom":
        """Deserialize from dict."""
        loom = cls(
            session_id=data["session_id"],
            root_id=data["root_id"],
            current_path=data["current_path"],
            held_paths=data.get("held_paths", []),
            brief=data["brief"],
            config=data.get("config", {}),
            created_at=data.get("created_at", time.time()),
        )
        for k, v in data["nodes"].items():
            loom.nodes[k] = Node(**v)
        for k, v in data["decision_events"].items():
            loom.decision_events[k] = DecisionEvent(**v)
        return loom
```

---

## Base Engine v0: Generator Interface & Claude CLI-Sim

### GeneratedCandidate & Generator Protocol

At the base engine boundary we work with simple candidate records and a generator interface:

```python
from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class GeneratedCandidate:
    node_id: str
    text: str
    token_ids: List[int]
    token_logprobs: Optional[List[float]]
    step_logprob: Optional[float]


class Generator(Protocol):
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

The orchestrator is responsible for:

- Building the text prompt (few-shot examples, section intent, rough draft, full_text).
- Calling `Generator.generate_candidates(...)` and turning each `GeneratedCandidate` into a `Node` via `Node.from_candidate`.

### BaseEngineConfig & Generator Factory

We configure the base engine via a small config object and a factory:

```python
from dataclasses import dataclass


@dataclass
class BaseEngineConfig:
    engine_type: str = "claude_cli_sim"  # later: "vllm", "together", etc.
    model_name: str = "claude-3-5-sonnet-latest"
    segment_tokens: int = 6
    branching_factor: int = 8
    temperature: float = 1.0
    top_p: float = 1.0
    max_logprobs: int = 0  # 0 for CLI-sim (no logprobs)


def make_generator(cfg: BaseEngineConfig, client: "anthropic.Anthropic") -> Generator:
    if cfg.engine_type == "claude_cli_sim":
        return ClaudeCLISimGenerator(
            client=client,
            model=cfg.model_name,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
        )
    # Future:
    # if cfg.engine_type == "vllm": ...
    # if cfg.engine_type == "together": ...
    raise ValueError(f"Unknown engine_type: {cfg.engine_type}")
```

### ClaudeCLISimGenerator Sketch

The v0 base engine uses Claude in a CLI-simulation mode. It prioritizes simplicity and does not expose logprobs:

```python
import anthropic
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ClaudeCLISimGenerator:
    client: anthropic.Anthropic
    model: str = "claude-3-5-sonnet-latest"
    temperature: float = 1.0
    top_p: float = 1.0

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
        candidates: List[GeneratedCandidate] = []

        prompt = build_base_prompt(
            fewshot_examples=fewshot_examples,
            section_intent=section_intent,
            rough_draft=rough_draft,
            full_text=full_text,
        )

        for _ in range(n):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                system=(
                    "You are in CLI simulation mode. "
                    "Respond only with the output of the requested command."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": f\"\"\"<cmd>cat draft.txt</cmd>

{prompt}\"\"\",
                    }
                ],
            )
            text = response.content[0].text
            candidates.append(
                GeneratedCandidate(
                    node_id=new_id(),
                    text=text,
                    token_ids=[],
                    token_logprobs=None,
                    step_logprob=None,
                )
            )

        return candidates
```

Notes:

- `build_base_prompt(...)` is a helper (not shown) that implements the shape described in `Docs/loom_spec_v0.md` §5.1.
- For v0 we do **not** compute token IDs or logprobs; those fields are left empty/`None`.
- The orchestrator will pass each `GeneratedCandidate` to `Node.from_candidate`, which in turn populates the Loom.

This keeps the base engine plug-in point stable while making the v0 implementation trivial to mock and reason about.

---

## Implementation: What's Needed

### The Three Parts

1. **Backend (Python)** — Loom data structure, base model interface, selector orchestration
2. **Selector (Claude API)** — Agentic selection with tools
3. **UI** — Visualize tree, show candidates, enable human selection/override

---

### Part 1: Backend

**Language:** Python (vLLM, Together API, Anthropic SDK all have Python clients)

**Structure:**

```
loom/
├── core/
│   ├── dataclasses.py    # Node, DecisionEvent, Loom (above)
│   ├── generator.py      # Base model interface
│   └── orchestrator.py   # Main loop, tool implementations
├── selectors/
│   ├── base.py           # Selector interface
│   ├── human.py          # CLI human selector
│   ├── claude.py         # Claude agentic selector
│   └── hybrid.py         # LLM + human escalation
├── io/
│   ├── manifest.py       # NDJSON logging
│   └── serialize.py      # Loom save/load
└── cli.py                # Entry point
```

**Generator interface:**

```python
from abc import ABC, abstractmethod
from typing import List, Tuple

class Generator(ABC):
    @abstractmethod
    def generate_candidates(
        self,
        context: str,
        n: int = 8,
        max_tokens: int = 6,
    ) -> List[Tuple[str, List[int], List[float], float]]:
        """
        Returns list of (text, token_ids, token_logprobs, step_logprob)
        For CLI-sim mode, logprobs are None.
        """
        pass


class VLLMGenerator(Generator):
    """True base model via vLLM."""
    def __init__(self, model_name: str, temperature: float = 1.0, top_p: float = 1.0):
        # Initialize vLLM client
        pass

    def generate_candidates(self, context, n=8, max_tokens=6):
        # Call vLLM with n samples, return with logprobs
        pass


class TogetherGenerator(Generator):
    """Base model via Together API."""
    pass


class ClaudeCLISimGenerator(Generator):
    """
    Claude in CLI simulation mode.
    No logprobs available.
    """
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model

    def generate_candidates(self, context, n=8, max_tokens=6):
        candidates = []
        for _ in range(n):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=1.0,
                system="The assistant is in CLI simulation mode, and responds to the user's CLI commands only with the output of the command.",
                messages=[{
                    "role": "user",
                    "content": f"<cmd>cat draft.txt</cmd>\n\n{context}"
                }]
            )
            text = response.content[0].text
            candidates.append((text, [], None, None))  # No logprobs
        return candidates
```

---

### Part 2: Selector (Claude as Agent)

Using Claude's tool use:

```python
import anthropic
from typing import Optional

SELECTOR_SYSTEM_PROMPT = """
You are the selector for a collaborative text-crafting process...
[full prompt from spec §7]
"""

TOOLS = [
    {
        "name": "generate_candidates",
        "description": "Get N continuation options from the base model",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "default": 8},
                "max_tokens": {"type": "integer", "default": 6}
            }
        }
    },
    {
        "name": "commit_choice",
        "description": "Commit to a candidate and extend the piece",
        "input_schema": {
            "type": "object",
            "properties": {
                "candidate_id": {"type": "string"},
                "reason": {"type": "string"},
                "scores": {"type": "object"}
            },
            "required": ["candidate_id", "reason"]
        }
    },
    {
        "name": "request_human_input",
        "description": "Pause for human clarification when candidates diverge on meaning",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "candidates_in_tension": {"type": "array", "items": {"type": "string"}},
                "what_hinges_on_it": {"type": "string"}
            },
            "required": ["question", "candidates_in_tension", "what_hinges_on_it"]
        }
    },
    {
        "name": "stop_generation",
        "description": "End the piece when it reaches natural completion",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"}
            },
            "required": ["reason"]
        }
    },
    {
        "name": "query_loom",
        "description": "Inspect branching history",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["last_n_decisions", "rejected_at", "find_divergences"]
                },
                "params": {"type": "object"}
            },
            "required": ["query_type"]
        }
    }
]


class ClaudeSelector:
    def __init__(self, loom: Loom, generator: Generator):
        self.client = anthropic.Anthropic()
        self.loom = loom
        self.generator = generator
        self.current_candidates: Dict[str, Node] = {}

    def run(self):
        """Main agentic loop."""
        messages = [{
            "role": "user",
            "content": f"Begin crafting. The piece so far:\n\n{self.loom.get_current_text()}"
        }]

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SELECTOR_SYSTEM_PROMPT.format(brief=self.loom.brief),
                tools=TOOLS,
                messages=messages
            )

            # Handle tool calls
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self.handle_tool(block.name, block.input)
                        if result == "STOP":
                            return
                        if result == "HUMAN_INPUT_NEEDED":
                            # Handle human input flow
                            human_response = self.get_human_input()
                            result = {"human_response": human_response}
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })
                
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # No more tool calls, we're done
                break

    def handle_tool(self, name: str, input: dict):
        if name == "generate_candidates":
            return self.tool_generate_candidates(input)
        elif name == "commit_choice":
            return self.tool_commit_choice(input)
        elif name == "request_human_input":
            return "HUMAN_INPUT_NEEDED"
        elif name == "stop_generation":
            self.tool_stop(input)
            return "STOP"
        elif name == "query_loom":
            return self.tool_query_loom(input)

    def tool_generate_candidates(self, input: dict) -> dict:
        n = input.get("n", 8)
        max_tokens = input.get("max_tokens", 6)
        
        context = self.loom.get_current_text()
        raw_candidates = self.generator.generate_candidates(context, n, max_tokens)
        
        tip = self.loom.get_tip()
        candidates = []
        self.current_candidates = {}
        
        for text, token_ids, token_logprobs, step_logprob in raw_candidates:
            node = Node.from_candidate(
                parent=tip,
                text=text,
                token_ids=token_ids,
                token_logprobs=token_logprobs,
                step_logprob=step_logprob,
            )
            candidates.append(node)
            self.current_candidates[node.id] = node

        # Create decision event (unresolved)
        self.current_event = self.loom.add_candidates(
            tip.id,
            candidates
        )

        return {
            "candidates": [
                {
                    "id": node.id,
                    "text": node.text,
                    "logprob": node.step_logprob
                }
                for node in candidates
            ]
        }

    def tool_commit_choice(self, input: dict) -> dict:
        candidate_id = input["candidate_id"]
        reason = input["reason"]
        scores = input.get("scores", {})

        self.loom.commit_choice(
            self.current_event.id,
            candidate_id,
            chosen_by="selector_llm",
            reason=reason
        )

        return {
            "success": True,
            "new_text": self.loom.get_current_text()
        }

    def tool_stop(self, input: dict):
        self.loom.commit_stop(self.current_event.id, input["reason"])

    def tool_query_loom(self, input: dict) -> dict:
        query_type = input["query_type"]
        params = input.get("params", {})
        
        if query_type == "last_n_decisions":
            events = self.loom.get_last_n_decisions(params.get("n", 5))
            return {"decisions": [e.to_dict() for e in events]}
        elif query_type == "find_divergences":
            events = self.loom.find_divergences(params.get("threshold", -1.0))
            return {"divergences": [e.to_dict() for e in events]}
        # etc.
```

---

### Part 3: UI

**Options, from simplest to richest:**

#### Option A: CLI Only (v0)

```python
def human_select(candidates: List[Node], context: str) -> str:
    print("\n" + "="*50)
    print("CONTEXT (last 200 chars):")
    print(context[-200:])
    print("\n" + "-"*50)
    print("CANDIDATES:")
    for i, node in enumerate(candidates):
        logprob_str = f" (logprob: {node.step_logprob:.2f})" if node.step_logprob else ""
        print(f"  [{i+1}] \"{node.text}\"{logprob_str}")
    print("-"*50)
    
    while True:
        choice = input("Select (1-N), or 'q' to quit: ").strip()
        if choice == 'q':
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx].id
        except ValueError:
            pass
        print("Invalid choice, try again.")
```

Good enough to feel the system. Bad for seeing the tree structure.

#### Option B: TUI (Textual/Rich)

Python library [Textual](https://textual.textualize.io/) gives you a rich terminal UI:

- Tree view of loom on left
- Current text + candidates on right
- Keyboard navigation

More investment, but still pure Python.

#### Option C: Web UI

**Framework:** FastAPI backend + simple frontend

Frontend options:
- **React + react-flow**: Good for node graphs, lots of tree visualization examples
- **Svelte + d3**: Lighter weight, flexible
- **Obsidian plugin**: You already have Loomsidian—could potentially extend it

The tree visualization is the hard part. Something like:

```
        [root]
           │
        [node1]
           │
    ┌──────┼──────┐
    │      │      │
 [rej1] [node2] [rej2]
           │
    ┌──────┼──────┐
    │      │      │
 [rej3] [node3] [rej4]  ← current tip
```

#### Option D: Extend Loomsidian

From your screenshot, Loomsidian already does:
- Tree visualization
- Branching completions
- Node selection

If it's open source or you have access to the code, extending it might be the fastest path to a usable UI. It's TypeScript/Obsidian plugin architecture.

---

### Recommendation: Staged Approach

**Week 1: CLI prototype**
```
python -m loom.cli --seed "The attention was a hand, and it was holding" --brief brief.md
```
- Human selection only
- Feel the granularity
- Validate the data structures work

**Week 2: Add Claude selector**
- Wire up tool calls
- Run fully autonomous sessions
- Compare human vs LLM selections

**Week 3: Basic web UI**
- FastAPI serving the loom
- Simple tree view (even just nested HTML)
- Click to select, see candidates

**Week 4+: Rich visualization**
- Proper graph rendering
- Side-by-side path comparison
- Query interface for analysis

---

### Dependencies

```
# requirements.txt

# Core
anthropic>=0.18.0
pydantic>=2.0

# Base model options (pick one or more)
vllm>=0.3.0           # Self-hosted
together>=0.2.0       # Together API

# CLI/TUI
rich>=13.0            # Pretty terminal output
textual>=0.50         # Optional: rich TUI

# Web UI (if going that route)
fastapi>=0.100
uvicorn>=0.20
```

---

### Where to Start

What's your preference?

1. **CLI-first**: I can write a minimal `cli.py` that runs the full loop with human selection
2. **Claude selector first**: Wire up the agentic loop, watch it run
3. **UI-first**: Sketch the web UI structure if that's the blocker

And: are you planning to use Loomsidian as the UI, or build fresh?
