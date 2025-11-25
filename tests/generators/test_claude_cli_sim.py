"""Tests for ClaudeCLISimGenerator (mocked Anthropic client)."""

from loom.generators.claude_cli_sim import ClaudeCLISimGenerator


class _StubContent:
    def __init__(self, text: str):
        self.text = text


class _StubResponse:
    def __init__(self, text: str):
        self.content = [_StubContent(text)]


class _StubMessages:
    def __init__(self, calls: list):
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _StubResponse(text="stubbed output")


class _StubClient:
    def __init__(self):
        self.calls = []
        self.messages = _StubMessages(self.calls)


def test_claude_cli_sim_calls_anthropic_and_returns_candidates():
    client = _StubClient()
    gen = ClaudeCLISimGenerator(client=client, model="model-x", temperature=0.9, top_p=0.8)

    candidates = gen.generate_candidates(
        full_text="Existing text.",
        fewshot_examples="ex1\n---\nex2",
        section_intent="Explain",
        rough_draft=None,
        n=2,
        max_tokens=6,
    )

    # Two calls made
    assert len(client.calls) == 2
    for call in client.calls:
        assert call["model"] == "model-x"
        assert call["max_tokens"] == 6
        assert call["temperature"] == 0.9
        assert call["top_p"] == 0.8
        # Prompt should include CONTINUE and SECTION INTENT
        prompt = call["messages"][0]["content"]
        assert "[SECTION INTENT]" in prompt
        assert "[CONTINUE]" in prompt

    # Returned candidates mapped from stubbed output
    assert len(candidates) == 2
    assert all(c.text == "stubbed output" for c in candidates)
    assert all(c.token_ids == [] for c in candidates)
    assert all(c.token_logprobs is None for c in candidates)
    assert all(c.step_logprob is None for c in candidates)

