"""Tests for generator factory."""

import types

import pytest

from loom.generators import make_generator
from loom.generators.claude_cli_sim import ClaudeCLISimGenerator


class _StubCfg:
    def __init__(self, engine_type: str = "claude_cli_sim"):
        self.engine_type = engine_type
        self.model_name = "model-x"
        self.temperature = 0.9
        self.top_p = 0.8


def test_make_generator_returns_claude_cli_sim():
    cfg = _StubCfg(engine_type="claude_cli_sim")
    stub_client = types.SimpleNamespace()  # unused in Fake CLI-sim test path

    gen = make_generator(cfg, stub_client)
    assert isinstance(gen, ClaudeCLISimGenerator)
    assert gen.model == "model-x"
    assert gen.temperature == 0.9
    assert gen.top_p == 0.8


def test_make_generator_unknown_engine_type():
    cfg = _StubCfg(engine_type="unknown")
    with pytest.raises(ValueError):
        make_generator(cfg, types.SimpleNamespace())

