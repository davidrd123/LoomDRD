"""Tests for the Orchestrator."""

from loom.brief import Brief
from loom.core.config import SessionConfig, BaseEngineConfig
from loom.core.models import Loom
from loom.generators.fake import FakeGenerator
from loom.orchestrator import Orchestrator


def make_session_config(branching: int = 2, segment_tokens: int = 6) -> SessionConfig:
    base_cfg = BaseEngineConfig(
        branching_factor=branching,
        segment_tokens=segment_tokens,
    )
    return SessionConfig(base_engine=base_cfg)


def test_generate_step_creates_decision_and_nodes():
    loom = Loom.create("Seed ", brief="brief")
    brief = Brief(section_intent="Intent")
    cfg = make_session_config(branching=3, segment_tokens=5)
    gen = FakeGenerator(prefix="opt_", step_logprob=None)

    orch = Orchestrator(loom=loom, generator=gen, brief=brief, config=cfg)
    event = orch.generate_step()

    assert event.id in loom.decision_events
    assert len(event.candidate_node_ids) == 3  # branching_factor
    # Nodes should be present and linked
    for node_id in event.candidate_node_ids:
        node = loom.nodes[node_id]
        assert node.parent_id == loom.current_path[-1]
        assert node.text.startswith("opt_")


def test_commit_choice_extends_path():
    loom = Loom.create("Seed ", brief="")
    brief = Brief(section_intent="Intent")
    cfg = make_session_config(branching=2)
    gen = FakeGenerator(prefix="c", step_logprob=None)
    orch = Orchestrator(loom, gen, brief, cfg)

    event = orch.generate_step()
    chosen = event.candidate_node_ids[0]
    orch.commit_choice(event.id, chosen, reason="pick")

    assert loom.current_path[-1] == chosen
    assert loom.nodes[chosen].was_chosen is True


def test_commit_stop_does_not_extend_path():
    loom = Loom.create("Seed ", brief="")
    brief = Brief(section_intent="Intent")
    cfg = make_session_config(branching=1)
    gen = FakeGenerator(prefix="c", step_logprob=None)
    orch = Orchestrator(loom, gen, brief, cfg)

    event = orch.generate_step()
    orch.commit_stop(event.id, "done")

    assert loom.current_path == [loom.root_id]
    assert event.action == "stop"
