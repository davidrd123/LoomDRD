"""Tests for FakeGenerator."""

from loom.generators.fake import FakeGenerator


def test_fake_generator_returns_deterministic_candidates():
    gen = FakeGenerator(prefix="opt_", step_logprob=-1.0)

    candidates = gen.generate_candidates(
        full_text="text",
        fewshot_examples="",
        section_intent="",
        rough_draft=None,
        n=3,
        max_tokens=5,
    )

    texts = [c.text for c in candidates]
    assert texts == ["opt_0", "opt_1", "opt_2"]
    assert all(c.token_ids == [] for c in candidates)
    assert all(c.token_logprobs is None for c in candidates)
    assert all(c.step_logprob == -1.0 for c in candidates)

