"""Configuration dataclasses for Loom sessions."""

from dataclasses import dataclass, field
from typing import Optional

from loom.core.models import new_id


@dataclass
class BaseEngineConfig:
    """Configuration for the base text generation engine."""

    engine_type: str = "claude_cli_sim"  # v0 default; future: "vllm", "together"
    model_name: str = "claude-3-5-sonnet-latest"
    segment_tokens: int = 6
    branching_factor: int = 8
    temperature: float = 1.0
    top_p: float = 1.0
    max_logprobs: int = 0  # v0 default — CLI-sim has no logprobs


@dataclass
class SelectorConfig:
    """Configuration for the selector (human, stateless LLM, or agentic LLM)."""

    model_name: str = "claude-3-5-sonnet-latest"
    mode: str = "agentic"  # "agentic" | "stateless" | "human"
    show_logprobs: bool = True


@dataclass
class SessionConfig:
    """Configuration for a complete Loom session."""

    id: str = field(default_factory=new_id)
    base_engine: BaseEngineConfig = field(default_factory=BaseEngineConfig)
    selector: SelectorConfig = field(default_factory=SelectorConfig)
    max_tokens_total: int = 1500  # rough budget for the piece
    output_dir: str = "loom_sessions"
    manifest_path: Optional[str] = None
