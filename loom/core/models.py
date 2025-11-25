"""Core data model for Loom: Node, DecisionEvent, Loom."""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import time
import uuid


def new_id() -> str:
    """Generate a short unique ID."""
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
    text: str  # segment text (just this node)
    full_text: str  # cached: all ancestors + this node
    token_ids: List[int]

    # Logprobs (None if using CLI-sim mode without logprob access)
    token_logprobs: Optional[List[float]] = None
    step_logprob: Optional[float] = None

    # Decision metadata (filled when this node is part of a decision)
    decision_id: Optional[str] = None  # which DecisionEvent included this node
    was_chosen: bool = False  # True if this node is on a chosen path
    chosen_by: Optional[str] = None  # "selector_llm" | "human" | None if rejected
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
    action: str = ""  # "choose" | "clarify" | "stop" (empty until resolved)
    chosen_node_id: Optional[str] = None  # set if action == "choose"
    chosen_by: Optional[str] = None  # "selector_llm" | "human"
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
    logprob_gap: Optional[float] = None  # chosen - max (negative = override)

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
    def create(
        cls, seed_text: str, brief: str, config: Optional[Dict[str, Any]] = None
    ) -> "Loom":
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

    def add_candidates(
        self, parent_id: str, candidates: List[Node]
    ) -> DecisionEvent:
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

    def commit_choice(
        self, event_id: str, chosen_node_id: str, chosen_by: str, reason: str
    ) -> None:
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
            reverse=True,
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
            event
            for event in self.decision_events.values()
            if event.logprob_gap is not None and event.logprob_gap < threshold
        ]

    def find_clarifications(self) -> List[DecisionEvent]:
        """Get all clarify events."""
        return [
            event
            for event in self.decision_events.values()
            if event.action == "clarify"
        ]

    # === Serialization ===

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON export."""
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
