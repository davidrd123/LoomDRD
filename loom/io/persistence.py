"""JSON persistence for Loom sessions."""

import json
from pathlib import Path
from typing import Union

from loom.core.models import Loom


def save_loom(loom: Loom, path: Union[str, Path]) -> None:
    """
    Save a Loom to a JSON file.

    Args:
        loom: The Loom instance to save.
        path: Path to the output JSON file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(loom.to_dict(), f, indent=2)


def load_loom(path: Union[str, Path]) -> Loom:
    """
    Load a Loom from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        The deserialized Loom instance.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Loom.from_dict(data)
