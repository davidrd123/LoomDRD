"""Orchestrator tying Loom, Brief, and Generator together."""

from typing import Optional

from loom.brief import Brief
from loom.core.config import SessionConfig
from loom.core.models import DecisionEvent, Loom, Node
from loom.generators.base import Generator


class Orchestrator:
    """
    Minimal orchestrator for human-in-the-loop generation.

    Responsibilities:
    - Call the generator with prompt components (brief + current text).
    - Create candidate Nodes and DecisionEvents on the Loom.
    - Commit human choices or stops.
    """

    def __init__(self, loom: Loom, generator: Generator, brief: Brief, config: SessionConfig):
        self.loom = loom
        self.generator = generator
        self.brief = brief
        self.config = config

    def generate_step(self) -> DecisionEvent:
        """
        Generate candidates from the current tip and return an unresolved DecisionEvent.
        """
        tip = self.loom.get_tip()
        if tip is None:
            raise ValueError("Loom has no tip to generate from.")

        n = self.config.base_engine.branching_factor
        max_tokens = self.config.base_engine.segment_tokens

        raw_candidates = self.generator.generate_candidates(
            full_text=tip.full_text,
            fewshot_examples=self.brief.fewshot_examples,
            section_intent=self.brief.section_intent,
            rough_draft=self.brief.rough_draft,
            n=n,
            max_tokens=max_tokens,
        )

        nodes = [
            Node.from_candidate(
                parent=tip,
                text=cand.text,
                token_ids=cand.token_ids,
                token_logprobs=cand.token_logprobs,
                step_logprob=cand.step_logprob,
            )
            for cand in raw_candidates
        ]

        event = self.loom.add_candidates(tip.id, nodes)
        return event

    def commit_choice(self, event_id: str, node_id: str, reason: str) -> None:
        """
        Commit a human choice and extend the current path.
        """
        self.loom.commit_choice(event_id, node_id, chosen_by="human", reason=reason)

    def commit_stop(self, event_id: str, reason: str) -> None:
        """
        Commit a stop action without extending the path.
        """
        self.loom.commit_stop(event_id, reason)

