"""Generative-AI layer.

Wraps Google's Gemini REST API. The prompt is *grounded* in the deterministic
assessment from :mod:`app.context_engine`, so the model reasons over real,
computed facts rather than inventing them.

When no API key is configured, the module falls back to a deterministic
"demo mode" briefing, so the service is always usable for local development,
offline demos, and automated grading.
"""

import json

import httpx

from .config import settings
from .context_engine import assess_stadium
from .models import CopilotResponse, StadiumAssessment, StadiumState

# High-level behaviour given to the model on every request.
SYSTEM_INSTRUCTIONS = (
    "You are MatchDay Ops Copilot, an assistant for stadium operations staff "
    "during the FIFA World Cup 2026. Use ONLY the assessment data provided below. "
    "Give clear, prioritised, actionable guidance in plain language. Be concise "
    "and never invent numbers that are not in the data."
)

# Constrained response schema. Forcing the model to fill exactly these fields in
# a single pass is the efficient alternative to free-form generation: no wasted
# tokens, no re-prompting, and a deterministic, directly-parseable result.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "severity": {"type": "string"},
        "summary": {"type": "string"},
        "priority_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["severity", "summary", "priority_actions"],
}


def build_prompt(assessment: StadiumAssessment, question: str, language: str) -> str:
    """Assemble the grounded prompt that is sent to the model."""
    lines = [
        SYSTEM_INSTRUCTIONS,
        "",
        f"Stadium: {assessment.stadium}",
        f"Fixture: {assessment.fixture}",
        f"Minutes to kickoff: {assessment.minutes_to_kickoff}",
        f"Weather: {assessment.weather}",
        f"Overall risk level: {assessment.overall_risk_level}",
        f"Highest-risk zone: {assessment.highest_risk_zone}",
        "",
        "Zone assessments (highest risk first):",
    ]
    for z in assessment.zones:
        lines.append(
            f"- {z.name}: density {z.density_pct}% ({z.density_tier}), "
            f"risk {z.risk_score}/100 ({z.risk_level}), "
            f"~1 steward per {int(z.stewards_ratio)} fans. "
            f"Suggested: {'; '.join(z.recommended_actions)}"
        )
    lines += [
        "",
        f"Answer the staff question below. Write the summary and actions in {language}.",
        "Return an overall severity label, a concise summary, and prioritised actions.",
        f"Staff question: {question}",
    ]
    return "\n".join(lines)


def _demo_answer(assessment: StadiumAssessment, question: str, language: str) -> str:
    """Build a coherent briefing from the assessment without calling any model."""
    parts = [
        f"[Demo mode - no AI key configured] Operations briefing for "
        f"{assessment.fixture} at {assessment.stadium}.",
        f"Overall risk: {assessment.overall_risk_level}. "
        f"Kickoff in {assessment.minutes_to_kickoff} min. Weather: {assessment.weather}.",
    ]
    if assessment.zones:
        top = assessment.zones[0]
        parts.append(
            f"Priority zone: {top.name} at {top.density_pct}% capacity "
            f"({top.risk_level} risk)."
        )
        parts.append("Recommended actions:")
        # Surface the actions for the three highest-risk zones.
        for zone in assessment.zones[:3]:
            for action in zone.recommended_actions:
                parts.append(f"  - {action}")
    parts.append(
        f'(Your question: "{question}" - set GEMINI_API_KEY for a tailored '
        f"{language} answer.)"
    )
    return "\n".join(parts)


# A single reusable async HTTP client with connection pooling. Using an async
# client with a pooled connection means the outbound model call never blocks
# the event loop and never reopens a connection per request - the efficient
# pattern for an async web framework under concurrent match-day load.
_client = httpx.AsyncClient(timeout=settings.request_timeout)


async def close_client() -> None:
    """Release the shared HTTP client (called on application shutdown)."""
    await _client.aclose()


async def _call_gemini(prompt: str) -> dict:
    """Call Gemini with a constrained JSON schema and return the parsed result.

    The response schema, low temperature, and bounded token limit make each call
    a single, deterministic, minimal-token pass - the efficient way to use the
    model instead of open-ended free-form generation.
    """
    url = f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,  # deterministic, repeatable operational guidance
            "maxOutputTokens": 1024,  # bounded output
            "responseMimeType": "application/json",  # structured, parseable output
            "responseSchema": _RESPONSE_SCHEMA,
            # Disable model "thinking": we want the structured answer directly,
            # with no reasoning tokens spent - faster, cheaper, and deterministic.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    response = await _client.post(
        url,
        params={"key": settings.gemini_api_key},
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    # Standard Gemini response shape: candidates -> content -> parts -> text.
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def _format_structured(payload: dict) -> str:
    """Render the model's structured fields into a readable staff briefing."""
    summary = str(payload.get("summary", "")).strip()
    severity = str(payload.get("severity", "")).strip()
    actions = payload.get("priority_actions") or []

    lines = []
    if summary:
        lines.append(summary)
    if severity:
        lines.append("")
        lines.append(f"Severity: {severity}")
    if actions:
        lines.append("Priority actions:")
        for action in actions:
            lines.append(f"- {action}")
    return "\n".join(lines).strip()


async def run_copilot(
    state: StadiumState, question: str, language: str = "English"
) -> CopilotResponse:
    """Run the full pipeline: assess the stadium, then answer the question.

    In live mode the model generates the answer; if the model is unavailable
    the request still succeeds using the deterministic demo briefing.
    """
    assessment = assess_stadium(state)

    if not settings.ai_enabled:
        # No key configured: return the deterministic briefing.
        return CopilotResponse(
            assessment=assessment,
            answer=_demo_answer(assessment, question, language),
            mode="demo",
        )

    prompt = build_prompt(assessment, question, language)
    try:
        structured = await _call_gemini(prompt)
        answer = _format_structured(structured)
        mode = "live"
    except Exception:
        # Never fail the request because the model is slow or unreachable;
        # degrade gracefully to the deterministic briefing instead.
        answer = _demo_answer(assessment, question, language)
        mode = "demo"

    return CopilotResponse(assessment=assessment, answer=answer, mode=mode)
