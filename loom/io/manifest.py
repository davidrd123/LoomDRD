"""NDJSON manifest logging for decision events."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Union

from loom.core.models import DecisionEvent


def append_decision_manifest(
    path: Union[str, Path],
    event: DecisionEvent,
    session_id: str,
) -> None:
    """
    Append a decision event to an NDJSON manifest file.

    Each call appends one line containing the event data plus session metadata.
    The manifest format matches §9 of loom_spec_v0.md.

    Args:
        path: Path to the NDJSON manifest file.
        event: The DecisionEvent to log.
        session_id: The session ID to include in the record.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build the manifest record
    record = {
        "session_id": session_id,
        "decision_id": event.id,
        "parent_node_id": event.parent_node_id,
        "candidate_node_ids": event.candidate_node_ids,
        "action": event.action,
        "chosen_node_id": event.chosen_node_id,
        "chosen_by": event.chosen_by,
        "reason": event.reason,
        "max_logprob": event.max_logprob,
        "chosen_logprob": event.chosen_logprob,
        "logprob_gap": event.logprob_gap,
        "timestamp": event.timestamp,
    }

    # Append as NDJSON (one JSON object per line)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def read_manifest(path: Union[str, Path]) -> list[dict]:
    """
    Read all records from an NDJSON manifest file.

    Args:
        path: Path to the NDJSON manifest file.

    Returns:
        List of decision records as dicts.
    """
    path = Path(path)
    if not path.exists():
        return []

    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
