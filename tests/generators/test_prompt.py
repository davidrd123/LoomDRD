"""Tests for prompt builder."""

from loom.brief import Brief
from loom.generators.prompt import build_base_prompt


def test_build_base_prompt_with_all_sections():
    brief = Brief(
        fewshot_examples="ex1\n---\nex2",
        section_intent="Explain the scene",
        rough_draft="Outline goes here",
    )
    full_text = "Current text"

    prompt = build_base_prompt(brief, full_text)

    assert "[FEW-SHOT TEXTURE EXAMPLES]" in prompt
    assert "ex1" in prompt
    assert "[SECTION INTENT]" in prompt
    assert "Explain the scene" in prompt
    assert "[ROUGH VERSION / OUTLINE]" in prompt
    assert "Outline goes here" in prompt
    assert "[CRAFTED TEXT SO FAR]" in prompt
    assert "Current text" in prompt
    assert prompt.strip().endswith("[CONTINUE]")


def test_build_base_prompt_skips_empty_sections():
    brief = Brief(section_intent="Intent only")
    prompt = build_base_prompt(brief, "Text so far")

    # Few-shot and rough should be absent if empty
    assert "[FEW-SHOT TEXTURE EXAMPLES]" not in prompt
    assert "[ROUGH VERSION / OUTLINE]" not in prompt
    assert "[SECTION INTENT]" in prompt
    assert "[CRAFTED TEXT SO FAR]" in prompt
    assert "[CONTINUE]" in prompt


def test_build_base_prompt_no_intent():
    brief = Brief(section_intent="")
    prompt = build_base_prompt(brief, "Some text")
    assert "[SECTION INTENT]" not in prompt
    assert "[CRAFTED TEXT SO FAR]" in prompt
