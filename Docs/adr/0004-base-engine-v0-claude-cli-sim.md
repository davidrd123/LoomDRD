# ADR 004: Base Engine v0 – Claude CLI-Sim

Status: Proposed  
Date: 2025-11-25

## Context

- The Loom spec allows for multiple base engine implementations:
  - True base models via vLLM.
  - Hosted base models via providers like Together.
  - Claude in "CLI-sim" mode (no logprobs).
- Practical constraints right now:
  - Spinning up and operating vLLM infra requires extra time and ops work.
  - Together does not offer serverless base models and charges \$3–4/hr for a dedicated endpoint, which is overkill for early Loom prototyping.
  - We still want to start using Loom soon, and validate the phenomenology loop (segment size, branching factor, selector behavior).

## Decision

For **v0**, use **Claude in CLI-sim mode** as the default `Generator` implementation for the base engine.

- Implement a `ClaudeCLISimGenerator` that:
  - Wraps calls to Claude with a "CLI simulation" system prompt.
  - Treats each completion as an independent candidate segment.
  - Does **not** provide token-level logprobs (fields remain `None`).
- Keep the `Generator` abstraction unchanged so that a vLLM or Together-backed generator can be plugged in later without changing orchestrator or UI code.

## Implications for the Data Model

- `Node.token_logprobs` and `Node.step_logprob` will often be `None` in v0.
- `DecisionEvent.max_logprob`, `DecisionEvent.chosen_logprob`, and `DecisionEvent.logprob_gap` will also be `None` when using CLI-sim.
- Features that depend on logprobs (e.g. "find divergences by logprob_gap") should:
  - Be implemented defensively.
  - Gracefully degrade or no-op when logprobs are unavailable.

This matches the original spec's notion that logprobs are **optional** and primarily unlock later analysis rather than core functionality.

## Testing Strategy Impact

- All tests use **fake generators** or mocked LLM clients:
  - For core backend tests, use a pure-Python fake `Generator` with deterministic outputs.
  - For any tests that exercise `ClaudeCLISimGenerator`, mock the Anthropic client so tests never make network calls.
- We can still test logprob-dependent code paths by:
  - Injecting a synthetic generator that fills `step_logprob`.
  - Asserting that `DecisionEvent.logprob_gap` is computed correctly when data is present.

## Future Options

- When vLLM or another base engine becomes practical, we can:
  - Add `VLLMGenerator` / `TogetherGenerator` implementations.
  - Enable logprob-aware features (divergence queries, richer analysis).
  - Update configuration to select the generator at runtime (e.g. via config file or CLI flags).
- ADR 004 applies specifically to **v0**; future ADRs can revise the default base engine once infra and cost trade-offs change.

