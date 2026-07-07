---
title: MatchDay Ops Copilot
emoji: 🏟️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# MatchDay Ops Copilot

**A GenAI-enabled decision-support assistant for stadium operations staff during the FIFA World Cup 2026.**

Hack2skill Prompt Wars - **Challenge 4: Smart Stadiums & Tournament Operations**.

**🔗 Live demo:** https://ninjaaaaaaa7-matchday-ops-copilot.hf.space (Hugging Face Space)

MatchDay Ops Copilot watches a live snapshot of a stadium (gate crowding, staffing,
arrivals, incidents, weather, match clock), computes an **explainable risk assessment**
for every zone, and lets operations staff ask questions in plain language - in any
language - to get **prioritised, actionable guidance** grounded in that assessment.

---

## 1. Chosen vertical

**Vertical:** Smart Stadiums & Tournament Operations
**Persona:** **Venue operations staff** (control-room and gate supervisors)
**Focus areas:** real-time decision support + crowd management, with multilingual
assistance and accessibility built in.

Operations staff on a World Cup matchday are flooded with signals from dozens of
zones and have seconds to decide where to act. This assistant turns that raw state
into a ranked priority list and answers natural-language questions about it.

**How this maps to the challenge's named focus areas:**

| Challenge focus area | How MatchDay Ops Copilot addresses it |
|----------------------|----------------------------------------|
| Real-time decision support | Ranked, per-zone risk with prioritised actions the moment a snapshot arrives |
| Crowd management | Density tiers, over-capacity penalties, and arrivals-surge detection near kickoff |
| Operational intelligence | A single explainable risk score per zone from five weighted factors |
| Accessibility | Flags busy zones lacking step-free access; the UI itself meets WCAG AA |
| Multilingual assistance | Staff can ask in any language and choose the reply language |

## 2. Approach and logic

The system is built in **two deliberately separated layers**:

### a) A deterministic context engine (the "logic")
`app/context_engine.py` contains rules-based intelligence with **no AI dependency**.
For each zone it computes:

- **Density tier** - occupancy / capacity, banded into `NORMAL / ELEVATED / HIGH / CRITICAL`.
- **A 0-100 risk score** from independent, explainable factors:
  1. crowding pressure (dominant factor, with a steep penalty above capacity),
  2. understaffing (fans-per-steward above a safe ratio),
  3. arrivals surge close to kickoff,
  4. active incidents,
  5. adverse-weather modifier.
- **A risk level** (`LOW / MODERATE / HIGH / CRITICAL`) and **prioritised recommended actions**
  (e.g. *pause entry and divert*, *dispatch N more stewards*, *open a step-free route*,
  *deploy water and shade in extreme heat*).

Zones are then **ranked by risk** so the worst zone is always first.

### b) A generative-AI layer (the "assistant")
`app/ai_assistant.py` builds a prompt **grounded in the computed assessment** and sends
it to **Google Gemini**. Because the model reasons over real, pre-computed facts, it
gives stable operational guidance instead of inventing numbers. Staff can ask in any
language and choose the reply language (multilingual assistance).

**Why this split matters:** the decision logic is fully deterministic and unit-tested,
and the AI is a natural-language layer *on top of* verified facts - not the source of
truth. This is the "logical decision making based on user context" the challenge asks for.

## 3. How the solution works

```
Browser UI  ──►  FastAPI backend  ──►  Context engine (deterministic assessment)
                                   └─►  Gemini (grounded natural-language answer)
```

**API endpoints**

| Method | Path           | Purpose                                             |
|--------|----------------|-----------------------------------------------------|
| GET    | `/`            | Accessible single-page operations dashboard         |
| GET    | `/api/health`  | Status + whether live AI is enabled                 |
| GET    | `/api/sample`  | A realistic sample stadium snapshot                 |
| POST   | `/api/assess`  | Deterministic risk assessment for a snapshot        |
| POST   | `/api/copilot` | Grounded natural-language answer to a staff question|

**Graceful demo mode:** if no `GEMINI_API_KEY` is set, `/api/copilot` returns a
deterministic briefing built from the assessment, so the app **always works** - for
local development, offline demos, and automated grading. With a key set, it returns a
live Gemini answer, and it **falls back to the briefing** if the model is unreachable.

### Run it locally

```bash
# 1. Create a virtual environment and install dependencies
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt

# 2. (Optional) enable live AI
cp .env.example .env      # then paste your Gemini API key into .env

# 3. Start the server
uvicorn app.main:app --reload

# 4. Open the dashboard
#    http://127.0.0.1:8000
```

### Run the tests

```bash
pytest
```

19 tests cover the context-engine rules, the API endpoints, input validation, demo
mode, and a **mocked** live Gemini call (no network needed).

## 4. Assumptions made

- **Input is a snapshot.** The app assesses a stadium state supplied per request. In a
  real deployment this snapshot would come from ticketing turnstiles, CCTV crowd
  analytics, and staff radios; here the shape is defined by `app/models.py` and a
  realistic sample is provided by `app/sample_data.py`.
- **Thresholds are configurable defaults.** Density bands and the safe steward ratio
  (constants in `context_engine.py`) are sensible defaults, not venue-certified figures;
  each venue would calibrate them.
- **Gemini is the GenAI provider.** The model name is configurable via `GEMINI_MODEL`
  and defaults to `gemini-2.0-flash`. No provider SDK is required - the app calls the
  REST API directly to keep dependencies minimal.
- **Trusted internal users.** The tool is for accredited operations staff; it has no
  auth layer, which a production deployment would add behind the venue network.

## Evaluation notes

- **Code quality** - small, single-responsibility modules; type hints, docstrings, and
  inline comments throughout; deterministic logic isolated from I/O.
- **Security** - the API key is read from the environment only and never committed
  (`.env` is git-ignored); all request bodies are validated by Pydantic; user text is
  HTML-escaped before rendering in the UI.
- **Efficiency** - no heavy dependencies or vector stores; a single grounded model call
  per question with a low temperature and bounded output.
- **Testing** - 19 `pytest` tests, including a mocked live-AI path, all passing.
- **Accessibility** - semantic HTML landmarks, a skip link, labelled form controls,
  visible focus outlines, `aria-live` result regions, AA-contrast colours, and risk
  communicated by **text labels, not colour alone**.

## Project structure

```
matchday-ops-copilot/
├── app/
│   ├── main.py            # FastAPI app + routes
│   ├── config.py          # environment-driven settings
│   ├── models.py          # Pydantic request/response schemas
│   ├── context_engine.py  # deterministic risk logic (unit-tested)
│   ├── ai_assistant.py    # Gemini layer + graceful demo fallback
│   └── sample_data.py     # realistic sample stadium snapshot
├── static/                # accessible single-page dashboard (HTML/CSS/JS)
├── tests/                 # pytest suite
├── requirements.txt
├── .env.example
└── README.md
```

## License

Released under the [MIT License](LICENSE).
