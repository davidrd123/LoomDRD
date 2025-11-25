"""Generator factory and exports."""

from typing import TYPE_CHECKING

from loom.generators.base import GeneratedCandidate, Generator
from loom.generators.prompt import build_base_prompt

if TYPE_CHECKING:  # pragma: no cover
    import anthropic
    from loom.core.config import BaseEngineConfig


def make_generator(cfg: "BaseEngineConfig", client: "anthropic.Anthropic") -> Generator:
    """
    Factory to create a generator based on BaseEngineConfig.

    Only Claude CLI-sim is supported in v0; others can be added later.
    """
    from loom.generators.claude_cli_sim import ClaudeCLISimGenerator

    if cfg.engine_type == "claude_cli_sim":
        return ClaudeCLISimGenerator(
            client=client,
            model=cfg.model_name,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
        )
    raise ValueError(f"Unknown engine_type: {cfg.engine_type}")


__all__ = [
    "GeneratedCandidate",
    "Generator",
    "build_base_prompt",
    "make_generator",
]
