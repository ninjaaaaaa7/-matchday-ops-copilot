"""Tests for the generative-AI layer, including a mocked live call."""

import asyncio

from app import ai_assistant
from app.ai_assistant import build_prompt, run_copilot
from app.config import settings
from app.context_engine import assess_stadium
from app.sample_data import sample_state


def test_build_prompt_contains_key_facts():
    assessment = assess_stadium(sample_state())
    prompt = build_prompt(assessment, "Where is the biggest risk?", "Spanish")
    # The prompt must ground the model in the real data and honour the language.
    assert assessment.stadium in prompt
    assert "Where is the biggest risk?" in prompt
    assert "Respond in Spanish" in prompt


def test_demo_mode_returns_grounded_answer(monkeypatch):
    # Force demo mode (no key) so the test is deterministic regardless of any
    # GEMINI_API_KEY in the local environment.
    monkeypatch.setattr(settings, "gemini_api_key", "")
    result = asyncio.run(run_copilot(sample_state(), "What now?", "English"))
    assert result.mode == "demo"
    assert result.assessment.fixture in result.answer
    assert len(result.answer) > 0


def test_live_mode_parses_model_response(monkeypatch):
    """Simulate a successful Gemini call without touching the network."""

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "Prioritise the transit hub."}]}}
                ]
            }

    async def fake_post(url, params=None, json=None):
        return FakeResponse()

    # Enable live mode and swap the async client's request method for our fake.
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(ai_assistant._client, "post", fake_post)

    result = asyncio.run(run_copilot(sample_state(), "What now?", "English"))
    assert result.mode == "live"
    assert result.answer == "Prioritise the transit hub."


def test_live_mode_falls_back_on_error(monkeypatch):
    """If the model call raises, the request still succeeds in demo mode."""

    async def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(ai_assistant._client, "post", boom)

    result = asyncio.run(run_copilot(sample_state(), "What now?", "English"))
    assert result.mode == "demo"
    assert len(result.answer) > 0
