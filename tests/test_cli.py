"""Basic tests for the CLI using FakeGenerator and patched input."""

import builtins
import types
from pathlib import Path

import pytest

import loom.cli as cli
from loom.generators.fake import FakeGenerator
from loom.io.persistence import load_loom


class _StubConsole:
    """Minimal console stub capturing prompts; prints are no-ops."""

    def __init__(self, inputs):
        self.inputs = inputs
        self.output = []

    def print(self, *args, **kwargs):
        # capture but ignore
        self.output.append((args, kwargs))

    def input(self, prompt: str):
        if not self.inputs:
            raise EOFError("No more inputs")
        return self.inputs.pop(0)


def test_cli_happy_path(monkeypatch, tmp_path, capsys):
    # Prepare brief file
    brief_path = tmp_path / "brief.toml"
    brief_path.write_text('section_intent = "Test intent"\n', encoding="utf-8")

    # Patch generator factory to return FakeGenerator
    fake_gen = FakeGenerator(prefix="opt_", step_logprob=None)
    monkeypatch.setattr(cli, "make_generator", lambda cfg, client: fake_gen)

    # Patch Console to use stubbed inputs: choose first candidate, then stop
    stub_console = _StubConsole(inputs=["1", "s"])
    monkeypatch.setattr(cli, "Console", lambda: stub_console)

    # Patch anthropic client creation to avoid network
    monkeypatch.setattr(cli.anthropic, "Anthropic", lambda: types.SimpleNamespace())

    output_dir = tmp_path / "out"
    argv = [
        "--seed",
        "Hello ",
        "--brief-path",
        str(brief_path),
        "--output-dir",
        str(output_dir),
        "--branching-factor",
        "2",
        "--segment-tokens",
        "4",
    ]

    cli.main(argv)

    # Check files written
    loom_path = output_dir / "loom.json"
    manifest_path = output_dir / "manifest.ndjson"
    assert loom_path.exists()
    assert manifest_path.exists()

    loaded = load_loom(loom_path)
    # Path should include root + one chosen node
    assert len(loaded.current_path) == 2


def test_cli_requires_brief(monkeypatch, tmp_path):
    # Patch Console to prevent actual IO
    monkeypatch.setattr(cli, "Console", lambda: _StubConsole(inputs=[]))
    with pytest.raises(SystemExit):
        cli.main(["--seed", "Hi"])

