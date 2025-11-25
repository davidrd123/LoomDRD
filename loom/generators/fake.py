"""Deterministic fake generator for tests."""

from typing import List, Optional

from loom.generators.base import GeneratedCandidate, Generator


class FakeGenerator(Generator):
    """
    Simple deterministic generator for testing orchestrator/CLI flows.

    Returns candidates like:
        candidate_0, candidate_1, ...
    with empty token_ids and no logprobs (v0 normal case).
    """

    def __init__(self, prefix: str = "candidate_", step_logprob: Optional[float] = None):
        self.prefix = prefix
        self.step_logprob = step_logprob

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
        return [
            GeneratedCandidate(
                text=f"{self.prefix}{i}",
                token_ids=[],
                token_logprobs=None,
                step_logprob=self.step_logprob,
            )
            for i in range(n)
        ]

