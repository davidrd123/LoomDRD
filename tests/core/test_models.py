"""Tests for loom.core.models: Node, DecisionEvent, Loom."""

import pytest

from loom.core.models import Node, DecisionEvent, Loom, new_id


class TestNewId:
    """Tests for the new_id helper."""

    def test_returns_string(self):
        assert isinstance(new_id(), str)

    def test_length_is_12(self):
        assert len(new_id()) == 12

    def test_unique(self):
        ids = [new_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestNode:
    """Tests for the Node dataclass."""

    def test_create_root_sets_defaults(self):
        node = Node.create_root("Hello")
        assert node.text == "Hello"
        assert node.full_text == "Hello"
        assert node.parent_id is None
        assert node.was_chosen is True
        assert node.token_ids == []
        assert node.token_logprobs is None
        assert node.step_logprob is None
        assert node.decision_id is None
        assert node.chosen_by is None
        assert node.selection_reason is None
        assert node.scores == {}
        assert node.meta == {}
        assert isinstance(node.id, str)
        assert len(node.id) == 12

    def test_from_candidate_links_to_parent(self):
        root = Node.create_root("The ")
        child = Node.from_candidate(
            parent=root,
            text="quick",
            token_ids=[1, 2, 3],
        )
        assert child.parent_id == root.id
        assert child.text == "quick"
        assert child.full_text == "The quick"
        assert child.token_ids == [1, 2, 3]
        assert child.was_chosen is False
        assert child.token_logprobs is None
        assert child.step_logprob is None

    def test_from_candidate_with_logprobs(self):
        root = Node.create_root("The ")
        child = Node.from_candidate(
            parent=root,
            text="fox",
            token_ids=[10, 20],
            token_logprobs=[-1.5, -2.0],
            step_logprob=-3.5,
        )
        assert child.token_logprobs == [-1.5, -2.0]
        assert child.step_logprob == -3.5

    def test_logprob_fields_default_to_none(self):
        """v0 normal case: logprobs are None."""
        root = Node.create_root("seed")
        assert root.token_logprobs is None
        assert root.step_logprob is None

        child = Node.from_candidate(root, "text", [])
        assert child.token_logprobs is None
        assert child.step_logprob is None


class TestDecisionEvent:
    """Tests for the DecisionEvent dataclass."""

    def test_create_initializes_pending_state(self):
        event = DecisionEvent.create("parent_123", ["node_a", "node_b", "node_c"])
        assert event.parent_node_id == "parent_123"
        assert event.candidate_node_ids == ["node_a", "node_b", "node_c"]
        assert event.action == ""  # unresolved
        assert event.chosen_node_id is None
        assert event.chosen_by is None
        assert event.reason == ""
        assert event.logprob_gap is None
        assert event.max_logprob is None
        assert event.chosen_logprob is None
        assert isinstance(event.id, str)

    def test_resolve_choose_without_logprobs(self):
        """v0 normal case: no logprobs, logprob_gap stays None."""
        event = DecisionEvent.create("parent", ["a", "b"])
        # Create nodes without logprobs
        nodes = {
            "a": Node.create_root("a"),
            "b": Node.create_root("b"),
        }
        event.resolve_choose(
            chosen_node_id="a",
            chosen_by="human",
            reason="preferred",
            nodes=nodes,
        )
        assert event.action == "choose"
        assert event.chosen_node_id == "a"
        assert event.chosen_by == "human"
        assert event.reason == "preferred"
        assert event.logprob_gap is None
        assert event.max_logprob is None
        assert event.chosen_logprob is None

    def test_resolve_choose_with_logprobs(self):
        """When logprobs are present, compute logprob_gap."""
        event = DecisionEvent.create("parent", ["a", "b", "c"])
        # Create nodes with logprobs
        node_a = Node.create_root("a")
        node_a.step_logprob = -2.0
        node_b = Node.create_root("b")
        node_b.step_logprob = -1.0  # best logprob
        node_c = Node.create_root("c")
        node_c.step_logprob = -3.0
        nodes = {"a": node_a, "b": node_b, "c": node_c}

        # Choose node_a which is NOT the best logprob
        event.resolve_choose(
            chosen_node_id="a",
            chosen_by="selector_llm",
            reason="better image",
            nodes=nodes,
        )
        assert event.action == "choose"
        assert event.max_logprob == -1.0  # best was node_b
        assert event.chosen_logprob == -2.0  # node_a
        assert event.logprob_gap == -1.0  # -2.0 - (-1.0) = -1.0 (override)

    def test_resolve_choose_with_candidate_scores(self):
        event = DecisionEvent.create("parent", ["a", "b"])
        scores = {
            "a": {"pull": 0.8, "density": 0.6},
            "b": {"pull": 0.4, "density": 0.9},
        }
        event.resolve_choose(
            chosen_node_id="a",
            chosen_by="selector_llm",
            reason="better pull",
            candidate_scores=scores,
        )
        assert event.candidate_scores == scores

    def test_resolve_clarify(self):
        event = DecisionEvent.create("parent", ["a", "b"])
        event.resolve_clarify(
            question="Should this be literal or metaphorical?",
            candidates_in_tension=["a", "b"],
            what_hinges_on_it="Tone of the entire section",
        )
        assert event.action == "clarify"
        assert event.clarification_question == "Should this be literal or metaphorical?"
        assert event.candidates_in_tension == ["a", "b"]
        assert event.what_hinges_on_it == "Tone of the entire section"
        assert event.chosen_node_id is None

    def test_resolve_stop(self):
        event = DecisionEvent.create("parent", ["a", "b"])
        event.resolve_stop("Natural ending reached")
        assert event.action == "stop"
        assert event.chosen_node_id is None
        assert event.reason == "Natural ending reached"


class TestLoom:
    """Tests for the Loom dataclass."""

    def test_create_initializes_with_root(self):
        loom = Loom.create("The beginning", brief="Test brief")
        assert loom.brief == "Test brief"
        assert loom.root_id is not None
        assert loom.current_path == [loom.root_id]
        assert len(loom.nodes) == 1
        root = loom.nodes[loom.root_id]
        assert root.text == "The beginning"
        assert root.full_text == "The beginning"
        assert root.was_chosen is True
        assert root.parent_id is None

    def test_create_with_config(self):
        config = {"segment_tokens": 8, "branching_factor": 4}
        loom = Loom.create("seed", brief="brief", config=config)
        assert loom.config == config

    def test_get_current_text(self):
        loom = Loom.create("Hello", brief="")
        assert loom.get_current_text() == "Hello"

    def test_get_tip(self):
        loom = Loom.create("Hello", brief="")
        tip = loom.get_tip()
        assert tip is not None
        assert tip.text == "Hello"

    def test_get_tip_empty_path(self):
        loom = Loom()
        assert loom.get_tip() is None

    def test_get_current_text_empty_path(self):
        loom = Loom()
        assert loom.get_current_text() == ""

    def test_add_candidates_creates_nodes_and_event(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, "quick", [1]),
            Node.from_candidate(root, "slow", [2]),
            Node.from_candidate(root, "fast", [3]),
        ]
        event = loom.add_candidates(root.id, candidates)

        # All candidates added to nodes
        assert len(loom.nodes) == 4  # root + 3 candidates
        for c in candidates:
            assert c.id in loom.nodes
            assert loom.nodes[c.id].decision_id == event.id
            assert loom.nodes[c.id].parent_id == root.id

        # Event created and linked
        assert event.id in loom.decision_events
        assert event.parent_node_id == root.id
        assert len(event.candidate_node_ids) == 3

    def test_commit_choice_extends_path(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, "quick", []),
            Node.from_candidate(root, "slow", []),
        ]
        event = loom.add_candidates(root.id, candidates)

        chosen_id = candidates[0].id
        loom.commit_choice(event.id, chosen_id, "human", "better rhythm")

        # Path extended
        assert loom.current_path == [root.id, chosen_id]
        assert loom.get_current_text() == "The quick"

        # Node marked
        chosen = loom.nodes[chosen_id]
        assert chosen.was_chosen is True
        assert chosen.chosen_by == "human"
        assert chosen.selection_reason == "better rhythm"

        # Event resolved
        assert event.action == "choose"
        assert event.chosen_node_id == chosen_id

    def test_commit_stop_does_not_extend_path(self):
        loom = Loom.create("The end", brief="")
        root = loom.get_tip()

        candidates = [Node.from_candidate(root, ".", [])]
        event = loom.add_candidates(root.id, candidates)

        loom.commit_stop(event.id, "Natural conclusion")

        # Path not extended
        assert loom.current_path == [root.id]
        assert event.action == "stop"
        assert event.chosen_node_id is None

    def test_get_rejected_at(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, "quick", []),
            Node.from_candidate(root, "slow", []),
            Node.from_candidate(root, "fast", []),
        ]
        event = loom.add_candidates(root.id, candidates)
        loom.commit_choice(event.id, candidates[0].id, "human", "chosen")

        rejected = loom.get_rejected_at(candidates[0].id)
        assert len(rejected) == 2
        rejected_ids = {r.id for r in rejected}
        assert candidates[1].id in rejected_ids
        assert candidates[2].id in rejected_ids

    def test_get_rejected_at_root_returns_empty(self):
        loom = Loom.create("root", brief="")
        rejected = loom.get_rejected_at(loom.root_id)
        assert rejected == []

    def test_get_last_n_decisions(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        # Create multiple decisions
        for word in ["quick ", "brown ", "fox"]:
            tip = loom.get_tip()
            candidates = [Node.from_candidate(tip, word, [])]
            event = loom.add_candidates(tip.id, candidates)
            loom.commit_choice(event.id, candidates[0].id, "human", "ok")

        assert len(loom.decision_events) == 3
        last_2 = loom.get_last_n_decisions(2)
        assert len(last_2) == 2
        # Most recent first
        assert last_2[0].timestamp >= last_2[1].timestamp

    def test_find_divergences_empty_when_no_logprobs(self):
        """v0 normal case: no logprobs means no divergences found."""
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, "quick", []),
            Node.from_candidate(root, "slow", []),
        ]
        event = loom.add_candidates(root.id, candidates)
        loom.commit_choice(event.id, candidates[0].id, "human", "ok")

        divergences = loom.find_divergences(threshold=-1.0)
        assert divergences == []

    def test_find_divergences_with_logprobs(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        # Create candidates with logprobs
        c1 = Node.from_candidate(root, "quick", [], step_logprob=-3.0)
        c2 = Node.from_candidate(root, "slow", [], step_logprob=-1.0)  # best
        event = loom.add_candidates(root.id, [c1, c2])
        # Choose c1 which has worse logprob (divergence of -2.0)
        loom.commit_choice(event.id, c1.id, "selector_llm", "override")

        # Should find divergence with gap < -1.0
        divergences = loom.find_divergences(threshold=-1.0)
        assert len(divergences) == 1
        assert divergences[0].logprob_gap == -2.0

        # Threshold of -2.5 should not match
        divergences = loom.find_divergences(threshold=-2.5)
        assert divergences == []

    def test_find_clarifications(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, "quick", []),
            Node.from_candidate(root, "slow", []),
        ]
        event = loom.add_candidates(root.id, candidates)
        event.resolve_clarify("Which?", ["a", "b"], "tone")

        clarifications = loom.find_clarifications()
        assert len(clarifications) == 1
        assert clarifications[0].action == "clarify"

    def test_to_dict_from_dict_roundtrip(self):
        loom = Loom.create("The quick", brief="Test brief", config={"k": "v"})
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, " brown", [1, 2]),
            Node.from_candidate(root, " red", [3, 4]),
        ]
        event = loom.add_candidates(root.id, candidates)
        loom.commit_choice(event.id, candidates[0].id, "human", "chosen")

        # Round-trip
        data = loom.to_dict()
        restored = Loom.from_dict(data)

        # Check all fields preserved
        assert restored.session_id == loom.session_id
        assert restored.root_id == loom.root_id
        assert restored.current_path == loom.current_path
        assert restored.brief == loom.brief
        assert restored.config == loom.config
        assert len(restored.nodes) == len(loom.nodes)
        assert len(restored.decision_events) == len(loom.decision_events)

        # Check node content
        for node_id, node in loom.nodes.items():
            restored_node = restored.nodes[node_id]
            assert restored_node.text == node.text
            assert restored_node.full_text == node.full_text
            assert restored_node.parent_id == node.parent_id
            assert restored_node.was_chosen == node.was_chosen

        # Check event content
        for event_id, event in loom.decision_events.items():
            restored_event = restored.decision_events[event_id]
            assert restored_event.action == event.action
            assert restored_event.chosen_node_id == event.chosen_node_id

    def test_to_dict_from_dict_preserves_none_logprobs(self):
        """v0: None logprobs must serialize/deserialize correctly."""
        loom = Loom.create("seed", brief="")
        root = loom.get_tip()

        # Candidate without logprobs (v0 normal)
        candidate = Node.from_candidate(root, " text", [])
        assert candidate.step_logprob is None
        assert candidate.token_logprobs is None

        event = loom.add_candidates(root.id, [candidate])
        loom.commit_choice(event.id, candidate.id, "human", "ok")

        data = loom.to_dict()
        restored = Loom.from_dict(data)

        # Logprob fields should still be None
        restored_node = restored.nodes[candidate.id]
        assert restored_node.step_logprob is None
        assert restored_node.token_logprobs is None

        restored_event = restored.decision_events[event.id]
        assert restored_event.logprob_gap is None
        assert restored_event.max_logprob is None
        assert restored_event.chosen_logprob is None


class TestLoomInvariants:
    """Tests for Loom invariants."""

    def test_root_has_no_parent(self):
        loom = Loom.create("root", brief="")
        root = loom.nodes[loom.root_id]
        assert root.parent_id is None

    def test_current_path_starts_with_root(self):
        loom = Loom.create("root", brief="")
        assert loom.current_path[0] == loom.root_id

    def test_path_nodes_chain_correctly(self):
        loom = Loom.create("The ", brief="")

        for word in ["quick ", "brown ", "fox"]:
            tip = loom.get_tip()
            candidates = [Node.from_candidate(tip, word, [])]
            event = loom.add_candidates(tip.id, candidates)
            loom.commit_choice(event.id, candidates[0].id, "human", "ok")

        # Verify chain
        for i in range(1, len(loom.current_path)):
            node = loom.nodes[loom.current_path[i]]
            expected_parent = loom.current_path[i - 1]
            assert node.parent_id == expected_parent

    def test_all_candidates_in_decision_exist_in_nodes(self):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        candidates = [
            Node.from_candidate(root, "a", []),
            Node.from_candidate(root, "b", []),
        ]
        event = loom.add_candidates(root.id, candidates)

        for node_id in event.candidate_node_ids:
            assert node_id in loom.nodes
