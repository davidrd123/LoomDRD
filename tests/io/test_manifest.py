"""Tests for loom.io.manifest: append_decision_manifest, read_manifest."""

import json
import pytest
from pathlib import Path

from loom.core.models import Loom, Node, DecisionEvent
from loom.io.manifest import append_decision_manifest, read_manifest


class TestAppendDecisionManifest:
    """Tests for append_decision_manifest."""

    def test_creates_file(self, tmp_path):
        event = DecisionEvent.create("parent_123", ["a", "b"])
        event.resolve_choose("a", "human", "preferred")
        path = tmp_path / "manifest.ndjson"

        append_decision_manifest(path, event, session_id="sess_001")

        assert path.exists()

    def test_creates_parent_directories(self, tmp_path):
        event = DecisionEvent.create("parent", ["a"])
        event.resolve_choose("a", "human", "ok")
        path = tmp_path / "nested" / "dir" / "manifest.ndjson"

        append_decision_manifest(path, event, session_id="sess")

        assert path.exists()

    def test_writes_valid_ndjson_line(self, tmp_path):
        event = DecisionEvent.create("parent_123", ["node_a", "node_b"])
        event.resolve_choose("node_a", "selector_llm", "better image")
        path = tmp_path / "manifest.ndjson"

        append_decision_manifest(path, event, session_id="sess_001")

        with path.open() as f:
            line = f.readline()
        record = json.loads(line)

        assert record["session_id"] == "sess_001"
        assert record["decision_id"] == event.id
        assert record["parent_node_id"] == "parent_123"
        assert record["candidate_node_ids"] == ["node_a", "node_b"]
        assert record["action"] == "choose"
        assert record["chosen_node_id"] == "node_a"
        assert record["chosen_by"] == "selector_llm"
        assert record["reason"] == "better image"

    def test_multiple_appends_create_multiple_lines(self, tmp_path):
        path = tmp_path / "manifest.ndjson"

        for i in range(3):
            event = DecisionEvent.create(f"parent_{i}", [f"node_{i}"])
            event.resolve_choose(f"node_{i}", "human", f"reason_{i}")
            append_decision_manifest(path, event, session_id="sess")

        with path.open() as f:
            lines = f.readlines()

        assert len(lines) == 3
        for i, line in enumerate(lines):
            record = json.loads(line)
            assert record["parent_node_id"] == f"parent_{i}"

    def test_logprob_fields_present(self, tmp_path):
        """Manifest should include logprob fields."""
        event = DecisionEvent.create("parent", ["a", "b"])
        event.resolve_choose("a", "human", "ok")
        # Manually set logprobs for testing
        event.max_logprob = -1.0
        event.chosen_logprob = -2.0
        event.logprob_gap = -1.0

        path = tmp_path / "manifest.ndjson"
        append_decision_manifest(path, event, session_id="sess")

        with path.open() as f:
            record = json.loads(f.readline())

        assert record["max_logprob"] == -1.0
        assert record["chosen_logprob"] == -2.0
        assert record["logprob_gap"] == -1.0

    def test_logprob_null_when_absent(self, tmp_path):
        """v0: logprob_gap should be null in JSON when not available."""
        event = DecisionEvent.create("parent", ["a"])
        event.resolve_choose("a", "human", "ok")
        # No logprobs set (v0 normal case)

        path = tmp_path / "manifest.ndjson"
        append_decision_manifest(path, event, session_id="sess")

        with path.open() as f:
            line = f.readline()

        # Check raw JSON contains null
        assert '"logprob_gap": null' in line or '"logprob_gap":null' in line

        record = json.loads(line)
        assert record["logprob_gap"] is None
        assert record["max_logprob"] is None
        assert record["chosen_logprob"] is None

    def test_timestamp_included(self, tmp_path):
        event = DecisionEvent.create("parent", ["a"])
        event.resolve_choose("a", "human", "ok")
        path = tmp_path / "manifest.ndjson"

        append_decision_manifest(path, event, session_id="sess")

        with path.open() as f:
            record = json.loads(f.readline())

        assert "timestamp" in record
        assert isinstance(record["timestamp"], float)


class TestReadManifest:
    """Tests for read_manifest."""

    def test_reads_all_records(self, tmp_path):
        path = tmp_path / "manifest.ndjson"

        for i in range(5):
            event = DecisionEvent.create(f"parent_{i}", [f"node_{i}"])
            event.resolve_choose(f"node_{i}", "human", f"reason_{i}")
            append_decision_manifest(path, event, session_id="sess")

        records = read_manifest(path)

        assert len(records) == 5
        for i, record in enumerate(records):
            assert record["parent_node_id"] == f"parent_{i}"

    def test_returns_empty_for_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.ndjson"

        records = read_manifest(path)

        assert records == []

    def test_handles_empty_file(self, tmp_path):
        path = tmp_path / "empty.ndjson"
        path.touch()

        records = read_manifest(path)

        assert records == []

    def test_skips_blank_lines(self, tmp_path):
        path = tmp_path / "manifest.ndjson"
        # Write with blank lines
        with path.open("w") as f:
            f.write('{"decision_id": "1"}\n')
            f.write("\n")
            f.write('{"decision_id": "2"}\n')
            f.write("   \n")
            f.write('{"decision_id": "3"}\n')

        records = read_manifest(path)

        assert len(records) == 3


class TestManifestIntegration:
    """Integration tests for manifest logging with Loom."""

    def test_log_decisions_from_loom(self, tmp_path):
        """Test logging decisions from actual Loom operations."""
        loom = Loom.create("The ", brief="test")
        path = tmp_path / "manifest.ndjson"

        # First decision
        root = loom.get_tip()
        candidates1 = [
            Node.from_candidate(root, "quick ", []),
            Node.from_candidate(root, "slow ", []),
        ]
        event1 = loom.add_candidates(root.id, candidates1)
        loom.commit_choice(event1.id, candidates1[0].id, "human", "first choice")
        append_decision_manifest(path, event1, loom.session_id)

        # Second decision
        tip = loom.get_tip()
        candidates2 = [
            Node.from_candidate(tip, "brown ", []),
            Node.from_candidate(tip, "red ", []),
        ]
        event2 = loom.add_candidates(tip.id, candidates2)
        loom.commit_choice(event2.id, candidates2[0].id, "selector_llm", "second choice")
        append_decision_manifest(path, event2, loom.session_id)

        # Read back and verify
        records = read_manifest(path)
        assert len(records) == 2

        assert records[0]["session_id"] == loom.session_id
        assert records[0]["action"] == "choose"
        assert records[0]["reason"] == "first choice"

        assert records[1]["session_id"] == loom.session_id
        assert records[1]["action"] == "choose"
        assert records[1]["reason"] == "second choice"
