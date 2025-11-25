"""Structured brief loading for Loom."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import tomllib


@dataclass
class Brief:
    """Structured creative brief with optional free-form notes."""

    title: str = ""
    domain: str = ""
    voice: str = ""
    register: str = ""
    length_hint: Optional[str] = None

    # Selection guidance
    lean_into: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)

    # Free-form narrative (markdown-ish)
    notes: str = ""

    # Few-shot examples for texture
    fewshot_examples: str = ""

    # Section-specific intent
    section_intent: str = ""
    rough_draft: Optional[str] = None


def load_brief(path: Path) -> Brief:
    """
    Load a brief from a TOML file (preferred) or a plain text/markdown file (fallback).

    TOML files populate structured fields; other file types become Brief.notes.
    """
    path = Path(path)
    if path.suffix.lower() == ".toml":
        return _load_toml_brief(path)
    return Brief(notes=path.read_text(encoding="utf-8"))


def _load_toml_brief(path: Path) -> Brief:
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    return Brief(
        title=data.get("title", ""),
        domain=data.get("domain", ""),
        voice=data.get("voice", ""),
        register=data.get("register", ""),
        length_hint=data.get("length_hint"),
        lean_into=list(data.get("lean_into", [])),
        avoid=list(data.get("avoid", [])),
        notes=data.get("notes", ""),
        fewshot_examples=data.get("fewshot_examples", ""),
        section_intent=data.get("section_intent", ""),
        rough_draft=data.get("rough_draft"),
    )

