"""Tests for loom.io.persistence: save_loom, load_loom."""

import json
import pytest
from pathlib import Path

from loom.core.models import Loom, Node
from loom.io.persistence import save_loom, load_loom


class TestSaveLoom:
    """Tests for save_loom."""

    def test_creates_file(self, tmp_path):
        loom = Loom.create("seed text", brief="test")
        path = tmp_path / "loom.json"

        save_loom(loom, path)

        assert path.exists()

    def test_creates_parent_directories(self, tmp_path):
        loom = Loom.create("seed", brief="")
        path = tmp_path / "nested" / "dir" / "loom.json"

        save_loom(loom, path)

        assert path.exists()

    def test_writes_valid_json(self, tmp_path):
        loom = Loom.create("seed", brief="test brief")
        path = tmp_path / "loom.json"

        save_loom(loom, path)

        with path.open() as f:
            data = json.load(f)
        assert data["brief"] == "test brief"
        assert "nodes" in data
        assert "decision_events" in data

    def test_accepts_string_path(self, tmp_path):
        loom = Loom.create("seed", brief="")
        path = str(tmp_path / "loom.json")

        save_loom(loom, path)

        assert Path(path).exists()


class TestLoadLoom:
    """Tests for load_loom."""

    def test_loads_saved_loom(self, tmp_path):
        loom = Loom.create("The beginning", brief="A test")
        path = tmp_path / "loom.json"
        save_loom(loom, path)

        loaded = load_loom(path)

        assert loaded.brief == "A test"
        assert loaded.get_current_text() == "The beginning"

    def test_accepts_string_path(self, tmp_path):
        loom = Loom.create("seed", brief="")
        path = str(tmp_path / "loom.json")
        save_loom(loom, path)

        loaded = load_loom(path)

        assert loaded.session_id == loom.session_id


class TestRoundTrip:
    """Tests for save/load round-trip integrity."""

    def test_simple_loom_roundtrip(self, tmp_path):
        loom = Loom.create("seed text", brief="test brief", config={"key": "value"})
        path = tmp_path / "loom.json"

        save_loom(loom, path)
        loaded = load_loom(path)

        assert loaded.session_id == loom.session_id
        assert loaded.root_id == loom.root_id
        assert loaded.current_path == loom.current_path
        assert loaded.brief == loom.brief
        assert loaded.config == loom.config

    def test_loom_with_decisions_roundtrip(self, tmp_path):
        loom = Loom.create("The ", brief="")
        root = loom.get_tip()

        # Add candidates and make a choice
        candidates = [
            Node.from_candidate(root, "quick", [1, 2]),
            Node.from_candidate(root, "slow", [3, 4]),
        ]
        event = loom.add_candidates(root.id, candidates)
        loom.commit_choice(event.id, candidates[0].id, "human", "better flow")

        path = tmp_path / "loom.json"
        save_loom(loom, path)
        loaded = load_loom(path)

        # Check structure
        assert len(loaded.nodes) == len(loom.nodes)
        assert len(loaded.decision_events) == len(loom.decision_events)
        assert loaded.current_path == loom.current_path
        assert loaded.get_current_text() == "The quick"

        # Check chosen node
        chosen = loaded.nodes[candidates[0].id]
        assert chosen.was_chosen is True
        assert chosen.chosen_by == "human"
        assert chosen.selection_reason == "better flow"

        # Check event
        loaded_event = loaded.decision_events[event.id]
        assert loaded_event.action == "choose"
        assert loaded_event.chosen_node_id == candidates[0].id

    def test_none_logprobs_preserved(self, tmp_path):
        """v0: None logprobs must serialize and deserialize correctly."""
        loom = Loom.create("seed", brief="")
        root = loom.get_tip()

        # Candidate without logprobs (v0 normal case)
        candidate = Node.from_candidate(root, " text", [])
        event = loom.add_candidates(root.id, [candidate])
        loom.commit_choice(event.id, candidate.id, "human", "ok")

        path = tmp_path / "loom.json"
        save_loom(loom, path)
        loaded = load_loom(path)

        # Node logprobs
        loaded_node = loaded.nodes[candidate.id]
        assert loaded_node.step_logprob is None
        assert loaded_node.token_logprobs is None

        # Event logprobs
        loaded_event = loaded.decision_events[event.id]
        assert loaded_event.logprob_gap is None
        assert loaded_event.max_logprob is None
        assert loaded_event.chosen_logprob is None

    def test_logprobs_preserved_when_present(self, tmp_path):
        loom = Loom.create("seed", brief="")
        root = loom.get_tip()

        # Candidate with logprobs
        candidate = Node.from_candidate(
            root, " text", [1, 2], token_logprobs=[-1.0, -2.0], step_logprob=-3.0
        )
        event = loom.add_candidates(root.id, [candidate])
        loom.commit_choice(event.id, candidate.id, "human", "ok")

        path = tmp_path / "loom.json"
        save_loom(loom, path)
        loaded = load_loom(path)

        loaded_node = loaded.nodes[candidate.id]
        assert loaded_node.step_logprob == -3.0
        assert loaded_node.token_logprobs == [-1.0, -2.0]

    def test_json_structure_matches_spec(self, tmp_path):
        """JSON output should have expected top-level keys."""
        loom = Loom.create("seed", brief="test", config={"k": "v"})
        path = tmp_path / "loom.json"
        save_loom(loom, path)

        with path.open() as f:
            data = json.load(f)

        # Required top-level keys per spec
        assert "session_id" in data
        assert "root_id" in data
        assert "current_path" in data
        assert "held_paths" in data
        assert "brief" in data
        assert "config" in data
        assert "created_at" in data
        assert "nodes" in data
        assert "decision_events" in data
