"""Tests for generator base types."""

from loom.generators.base import GeneratedCandidate


def test_generated_candidate_fields():
    cand = GeneratedCandidate(
        text="hello",
        token_ids=[1, 2],
        token_logprobs=[-1.0, -0.5],
        step_logprob=-1.5,
    )
    assert cand.text == "hello"
    assert cand.token_ids == [1, 2]
    assert cand.token_logprobs == [-1.0, -0.5]
    assert cand.step_logprob == -1.5

