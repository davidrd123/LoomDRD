"""Rich CLI for human-in-the-loop Loom generation."""

import argparse
from pathlib import Path
from typing import Optional

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from loom.brief import Brief, load_brief
from loom.core.config import BaseEngineConfig, SessionConfig
from loom.core.models import Loom
from loom.generators import make_generator
from loom.io.manifest import append_decision_manifest
from loom.io.persistence import save_loom
from loom.orchestrator import Orchestrator


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loom CLI - human-in-the-loop text crafting")
    parser.add_argument("-s", "--seed", required=True, help="Seed text to start the loom")
    parser.add_argument("-b", "--brief-path", help="Path to brief file (TOML or markdown)")
    parser.add_argument("--brief-text", help="Inline brief text (used as notes if no file)")
    parser.add_argument("-o", "--output-dir", default="loom_sessions", help="Output directory")
    parser.add_argument("-n", "--branching-factor", type=int, default=8, help="Number of candidates per step")
    parser.add_argument("-t", "--segment-tokens", type=int, default=6, help="Max tokens per candidate segment")
    return parser.parse_args(argv)


def load_brief_from_args(args: argparse.Namespace) -> Brief:
    if args.brief_path and args.brief_text:
        raise SystemExit("Provide either --brief-path or --brief-text, not both.")
    if args.brief_path:
        return load_brief(Path(args.brief_path))
    if args.brief_text:
        return Brief(notes=args.brief_text)
    raise SystemExit("Brief is required (use --brief-path or --brief-text).")


def create_session_config(args: argparse.Namespace) -> SessionConfig:
    base_cfg = BaseEngineConfig(
        branching_factor=args.branching_factor,
        segment_tokens=args.segment_tokens,
    )
    return SessionConfig(base_engine=base_cfg)


def save_session(loom: Loom, manifest_path: Path, event_id: Optional[str] = None) -> None:
    output_dir = manifest_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    save_loom(loom, output_dir / "loom.json")
    if event_id:
        event = loom.decision_events[event_id]
        append_decision_manifest(manifest_path, event, session_id=loom.session_id)


def render_candidates(console: Console, loom: Loom, event_id: str) -> None:
    event = loom.decision_events[event_id]
    table = Table(title="Candidates", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Text")
    table.add_column("Logprob")

    for idx, node_id in enumerate(event.candidate_node_ids, start=1):
        node = loom.nodes[node_id]
        lp = "—" if node.step_logprob is None else f"{node.step_logprob:.2f}"
        table.add_row(str(idx), node.text, lp)

    console.print(table)


def main(argv: Optional[list[str]] = None) -> None:
    console = Console()
    args = parse_args(argv)
    brief = load_brief_from_args(args)
    session_cfg = create_session_config(args)

    loom = Loom.create(seed_text=args.seed, brief=brief.notes or brief.title or "")
    generator = make_generator(session_cfg.base_engine, anthropic.Anthropic())
    orchestrator = Orchestrator(loom=loom, generator=generator, brief=brief, config=session_cfg)

    manifest_path = Path(args.output_dir) / "manifest.ndjson"

    console.print(Panel(f"Session ID: {loom.session_id}\nSeed: {args.seed}", title="Loom Session"))

    running = True
    while running:
        event = orchestrator.generate_step()
        render_candidates(console, loom, event.id)

        choice = console.input("Choose [number], s=stop, q=quit: ").strip().lower()

        if choice == "q":
            console.print("Quit without saving.")
            return
        if choice == "s":
            orchestrator.commit_stop(event.id, "User stop")
            save_session(loom, manifest_path, event_id=event.id)
            console.print("Stopped.")
            break

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(event.candidate_node_ids):
                raise ValueError
        except ValueError:
            console.print("[red]Invalid choice[/red]")
            continue

        chosen_id = event.candidate_node_ids[idx]
        orchestrator.commit_choice(event.id, chosen_id, reason="human choice")
        save_session(loom, manifest_path, event_id=event.id)
        console.print(f"Chose candidate {idx+1}")

    console.print(f"Session saved to {args.output_dir}")


if __name__ == "__main__":
    main()

