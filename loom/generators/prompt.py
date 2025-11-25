"""Prompt construction helpers for base generation."""

from loom.brief import Brief


def build_base_prompt(
    brief: Brief,
    full_text: str,
) -> str:
    """
    Build the base prompt for candidate generation (spec §5.1).

    Sections:
    - FEW-SHOT TEXTURE EXAMPLES
    - SECTION INTENT
    - ROUGH VERSION / OUTLINE (optional)
    - CRAFTED TEXT SO FAR
    - CONTINUE
    """

    parts: list[str] = []

    if brief.fewshot_examples.strip():
        parts.append(_section("FEW-SHOT TEXTURE EXAMPLES", brief.fewshot_examples.strip()))

    if brief.section_intent.strip():
        parts.append(_section("SECTION INTENT", brief.section_intent.strip()))

    if brief.rough_draft and brief.rough_draft.strip():
        parts.append(_section("ROUGH VERSION / OUTLINE", brief.rough_draft.strip()))

    parts.append(_section("CRAFTED TEXT SO FAR", full_text))

    parts.append("[CONTINUE]")

    return "\n\n".join(parts)


def _section(title: str, body: str) -> str:
    return f"[{title}]\n{body}"
