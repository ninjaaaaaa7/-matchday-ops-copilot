// Front-end logic for MatchDay Ops Copilot.
// Vanilla JS keeps the bundle tiny and dependency-free. It talks to the same
// FastAPI backend that serves this page.

"use strict";

// The current stadium snapshot, loaded from the API and reused for questions.
let currentState = null;

// Small helper to escape text before inserting it into the DOM (avoids XSS
// even though our data is trusted here - safe by default).
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Fetch helper with basic error handling.
async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error("Request failed: " + response.status);
  }
  return response.json();
}

// Show whether the backend is running live AI or demo mode.
async function loadStatus() {
  const badge = document.getElementById("mode-badge");
  try {
    const health = await api("/api/health");
    if (health.ai_enabled) {
      badge.textContent = "Live AI (" + health.model + ")";
    } else {
      badge.textContent = "Demo mode - no API key set";
    }
  } catch (err) {
    badge.textContent = "Backend unavailable";
  }
}

// Render the match summary and the ranked zone assessment.
function renderAssessment(assessment) {
  document.getElementById("s-stadium").textContent = assessment.stadium;
  document.getElementById("s-fixture").textContent = assessment.fixture;
  document.getElementById("s-kickoff").textContent =
    assessment.minutes_to_kickoff + " min";
  document.getElementById("s-weather").textContent = assessment.weather;
  document.getElementById("s-risk").textContent = assessment.overall_risk_level;

  const container = document.getElementById("zones");
  container.innerHTML = "";

  assessment.zones.forEach(function (zone) {
    const card = document.createElement("article");
    card.className = "zone-card risk-" + zone.risk_level;

    const actions = zone.recommended_actions
      .map(function (a) {
        return "<li>" + escapeHtml(a) + "</li>";
      })
      .join("");

    card.innerHTML =
      '<h4><span>' +
      escapeHtml(zone.name) +
      '</span><span class="pill risk-' +
      zone.risk_level +
      '">' +
      zone.risk_level +
      "</span></h4>" +
      '<p class="zone-meta">Density ' +
      zone.density_pct +
      "% (" +
      zone.density_tier +
      ") - risk " +
      zone.risk_score +
      "/100 - ~1 steward per " +
      Math.round(zone.stewards_ratio) +
      " fans</p>" +
      "<ul>" +
      actions +
      "</ul>";

    container.appendChild(card);
  });
}

// Load the sample stadium and show its assessment on first paint.
async function loadSample() {
  currentState = await api("/api/sample");
  const assessment = await api("/api/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentState),
  });
  renderAssessment(assessment);
}

// Handle the "Ask copilot" form submission.
async function onAsk(event) {
  event.preventDefault();
  if (!currentState) {
    return;
  }

  const button = document.getElementById("ask-btn");
  const answerBox = document.getElementById("answer");
  const question = document.getElementById("question").value.trim();
  const language = document.getElementById("language").value;

  if (!question) {
    answerBox.textContent = "Please type a question first.";
    return;
  }

  button.disabled = true;
  button.textContent = "Thinking…";
  answerBox.textContent = "Contacting copilot…";

  try {
    const result = await api("/api/copilot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        state: currentState,
        question: question,
        language: language,
      }),
    });
    answerBox.textContent = result.answer;
    // Refresh the assessment panel in case anything changed.
    renderAssessment(result.assessment);
  } catch (err) {
    answerBox.textContent = "Sorry, the copilot could not be reached.";
  } finally {
    button.disabled = false;
    button.textContent = "Ask copilot";
  }
}

// Wire everything up once the DOM is ready.
document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("copilot-form").addEventListener("submit", onAsk);
  loadStatus();
  loadSample().catch(function () {
    document.getElementById("zones").textContent =
      "Could not load the sample stadium. Is the backend running?";
  });
});
