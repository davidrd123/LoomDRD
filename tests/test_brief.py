"""Tests for loom.brief."""

from pathlib import Path

from loom.brief import Brief, load_brief


def test_load_toml_full_fields(tmp_path: Path):
    toml_content = """
title = "Worldspider"
domain = "Phenomenology"
voice = "Compressed"
register = "technical"
length_hint = "short"

lean_into = ["aliveness", "surprise"]
avoid = ["hedging"]

notes = "freeform notes"
fewshot_examples = "<ex1>..."
section_intent = "Describe the process"
rough_draft = "Outline text"
"""
    path = tmp_path / "brief.toml"
    path.write_text(toml_content, encoding="utf-8")

    brief = load_brief(path)
    assert brief.title == "Worldspider"
    assert brief.domain == "Phenomenology"
    assert brief.voice == "Compressed"
    assert brief.register == "technical"
    assert brief.length_hint == "short"
    assert brief.lean_into == ["aliveness", "surprise"]
    assert brief.avoid == ["hedging"]
    assert brief.notes == "freeform notes"
    assert brief.fewshot_examples == "<ex1>..."
    assert brief.section_intent == "Describe the process"
    assert brief.rough_draft == "Outline text"


def test_load_toml_missing_optionals(tmp_path: Path):
    toml_content = """
title = "Minimal"
section_intent = "Intent"
"""
    path = tmp_path / "brief.toml"
    path.write_text(toml_content, encoding="utf-8")

    brief = load_brief(path)
    assert brief.title == "Minimal"
    assert brief.section_intent == "Intent"
    # Optional fields fall back to defaults
    assert brief.voice == ""
    assert brief.lean_into == []
    assert brief.rough_draft is None


def test_load_markdown_fallback(tmp_path: Path):
    md_content = "# Brief\nSome notes here."
    path = tmp_path / "brief.md"
    path.write_text(md_content, encoding="utf-8")

    brief = load_brief(path)
    assert isinstance(brief, Brief)
    assert brief.notes == md_content
    # Structured fields should be defaults
    assert brief.title == ""
    assert brief.section_intent == ""

