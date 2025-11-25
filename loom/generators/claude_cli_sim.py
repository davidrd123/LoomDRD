"""Claude CLI-sim generator implementation."""

from dataclasses import dataclass
from typing import Any, List, Optional, TYPE_CHECKING

from loom.brief import Brief
from loom.generators.base import GeneratedCandidate, Generator
from loom.generators.prompt import build_base_prompt


if TYPE_CHECKING:  # pragma: no cover
    import anthropic


@dataclass
class ClaudeCLISimGenerator(Generator):
    """
    Generate candidates using Claude in CLI-simulation mode.

    - No logprobs are available; token_ids/logprobs remain empty/None.
    - Each call returns `n` independent short continuations.
    """

    client: Any
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
        brief = Brief(
            fewshot_examples=fewshot_examples,
            section_intent=section_intent,
            rough_draft=rough_draft,
        )
        prompt = build_base_prompt(brief, full_text)

        candidates: List[GeneratedCandidate] = []
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
                        "content": f"<cmd>cat draft.txt</cmd>\n\n{prompt}",
                    }
                ],
            )
            text = response.content[0].text
            candidates.append(
                GeneratedCandidate(
                    text=text,
                    token_ids=[],
                    token_logprobs=None,
                    step_logprob=None,
                )
            )

        return candidates
