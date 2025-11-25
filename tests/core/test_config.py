"""Tests for loom.core.config: BaseEngineConfig, SelectorConfig, SessionConfig."""

import pytest

from loom.core.config import BaseEngineConfig, SelectorConfig, SessionConfig


class TestBaseEngineConfig:
    """Tests for BaseEngineConfig."""

    def test_defaults_for_v0_cli_sim(self):
        """v0 defaults use Claude CLI-sim with no logprobs."""
        cfg = BaseEngineConfig()
        assert cfg.engine_type == "claude_cli_sim"
        assert cfg.model_name == "claude-3-5-sonnet-latest"
        assert cfg.segment_tokens == 6
        assert cfg.branching_factor == 8
        assert cfg.temperature == 1.0
        assert cfg.top_p == 1.0
        assert cfg.max_logprobs == 0  # v0: no logprobs

    def test_custom_values(self):
        cfg = BaseEngineConfig(
            engine_type="vllm",
            model_name="qwen-base",
            segment_tokens=8,
            branching_factor=4,
            temperature=0.85,
            top_p=0.92,
            max_logprobs=5,
        )
        assert cfg.engine_type == "vllm"
        assert cfg.model_name == "qwen-base"
        assert cfg.segment_tokens == 8
        assert cfg.branching_factor == 4
        assert cfg.temperature == 0.85
        assert cfg.top_p == 0.92
        assert cfg.max_logprobs == 5


class TestSelectorConfig:
    """Tests for SelectorConfig."""

    def test_defaults(self):
        cfg = SelectorConfig()
        assert cfg.model_name == "claude-3-5-sonnet-latest"
        assert cfg.mode == "agentic"
        assert cfg.show_logprobs is True

    def test_custom_values(self):
        cfg = SelectorConfig(
            model_name="claude-3-opus",
            mode="stateless",
            show_logprobs=False,
        )
        assert cfg.model_name == "claude-3-opus"
        assert cfg.mode == "stateless"
        assert cfg.show_logprobs is False


class TestSessionConfig:
    """Tests for SessionConfig."""

    def test_defaults(self):
        cfg = SessionConfig()
        assert isinstance(cfg.id, str)
        assert len(cfg.id) == 12
        assert isinstance(cfg.base_engine, BaseEngineConfig)
        assert isinstance(cfg.selector, SelectorConfig)
        assert cfg.max_tokens_total == 1500
        assert cfg.output_dir == "loom_sessions"
        assert cfg.manifest_path is None

    def test_nested_configs_are_independent(self):
        """Each SessionConfig gets its own base_engine and selector."""
        cfg1 = SessionConfig()
        cfg2 = SessionConfig()
        assert cfg1.id != cfg2.id
        # Modifying one doesn't affect the other
        cfg1.base_engine.segment_tokens = 10
        assert cfg2.base_engine.segment_tokens == 6

    def test_custom_values(self):
        custom_engine = BaseEngineConfig(engine_type="together")
        custom_selector = SelectorConfig(mode="human")
        cfg = SessionConfig(
            id="custom_id",
            base_engine=custom_engine,
            selector=custom_selector,
            max_tokens_total=3000,
            output_dir="/tmp/loom",
            manifest_path="/tmp/manifest.ndjson",
        )
        assert cfg.id == "custom_id"
        assert cfg.base_engine.engine_type == "together"
        assert cfg.selector.mode == "human"
        assert cfg.max_tokens_total == 3000
        assert cfg.output_dir == "/tmp/loom"
        assert cfg.manifest_path == "/tmp/manifest.ndjson"
