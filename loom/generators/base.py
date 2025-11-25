"""Base generator protocol and candidate type."""

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass
class GeneratedCandidate:
    """Raw output from a generator. IDs are assigned when creating Nodes."""

    text: str
    token_ids: List[int]
    token_logprobs: Optional[List[float]]
    step_logprob: Optional[float]


class Generator(Protocol):
    """Interface for base text generators."""

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

