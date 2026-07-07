"""Deterministic stadium context engine.

This module holds the *rules-based* intelligence of the copilot. It turns a
raw snapshot of stadium conditions (:class:`StadiumState`) into a structured,
explainable risk assessment (:class:`StadiumAssessment`).

Keeping this logic separate from the generative-AI layer is deliberate:

* the core decision-making is fully deterministic and unit-testable, and
* the AI layer is *grounded* in these computed facts instead of guessing.
"""

import math

from .models import StadiumAssessment, StadiumState, Zone, ZoneAssessment

# --- Tunable thresholds -----------------------------------------------------

# Density is occupancy / capacity. These bands classify how full a zone is.
DENSITY_ELEVATED = 0.70
DENSITY_HIGH = 0.85
DENSITY_CRITICAL = 0.95

# Safe crowd-to-steward ratio. Above this a zone is considered understaffed.
SAFE_STEWARD_RATIO = 250

# Risk score (0-100) bands used to label a zone.
RISK_MODERATE = 30
RISK_HIGH = 55
RISK_CRITICAL = 80

# Extra risk points contributed by adverse weather.
WEATHER_PENALTY = {
    "clear": 0,
    "rain": 5,
    "extreme_heat": 8,
    "storm": 10,
}

# Ordering used to pick the single worst risk level across all zones.
RISK_LEVEL_ORDER = ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def _density_tier(density_pct: float) -> str:
    """Classify how full a zone is, given its density fraction (0.0-1.0+)."""
    if density_pct >= DENSITY_CRITICAL:
        return "CRITICAL"
    if density_pct >= DENSITY_HIGH:
        return "HIGH"
    if density_pct >= DENSITY_ELEVATED:
        return "ELEVATED"
    return "NORMAL"


def _risk_level(risk_score: float) -> str:
    """Map a numeric risk score (0-100) to a human-readable level."""
    if risk_score >= RISK_CRITICAL:
        return "CRITICAL"
    if risk_score >= RISK_HIGH:
        return "HIGH"
    if risk_score >= RISK_MODERATE:
        return "MODERATE"
    return "LOW"


def _score_zone(
    zone: Zone, weather: str, minutes_to_kickoff: int
) -> tuple[float, float, float]:
    """Compute (density fraction, fans-per-steward, risk score) for one zone.

    The risk score is a weighted sum of independent, explainable factors so
    that staff can always see *why* a zone is flagged.
    """
    # Density fraction. capacity > 0 is guaranteed by the Zone model.
    density_pct = zone.occupancy / zone.capacity

    # Fans per steward. With no stewards, every fan is effectively unmanaged.
    stewards_ratio = zone.occupancy / zone.stewards if zone.stewards else float(zone.occupancy)

    risk = 0.0

    # 1) Crowding pressure (up to ~60 points). Fullness dominates the score.
    risk += min(density_pct, 1.0) * 45
    if density_pct > 1.0:
        # Over-capacity is especially dangerous, so add a steep extra penalty.
        risk += min((density_pct - 1.0) * 100, 15)

    # 2) Understaffing (up to 20 points).
    if stewards_ratio > SAFE_STEWARD_RATIO:
        over = (stewards_ratio - SAFE_STEWARD_RATIO) / SAFE_STEWARD_RATIO
        risk += min(over * 20, 20)

    # 3) Inflow near kickoff (up to 15 points). Heavy arrivals with little
    #    time left and an already-busy zone signal a dangerous build-up.
    if 0 <= minutes_to_kickoff <= 45 and density_pct >= DENSITY_ELEVATED:
        time_factor = (45 - minutes_to_kickoff) / 45  # 0..1, higher near kickoff
        inflow_factor = min(zone.inflow_per_min / 100.0, 1.0)  # 0..1
        risk += inflow_factor * time_factor * 15

    # 4) Active incidents (up to 15 points).
    risk += min(zone.open_incidents * 8, 15)

    # 5) Weather modifier (up to 10 points).
    risk += WEATHER_PENALTY.get(weather, 0)

    # Clamp to the 0-100 range and round for readability.
    risk = round(min(risk, 100.0), 1)
    return density_pct, stewards_ratio, risk


def _recommend(
    zone: Zone,
    density_pct: float,
    density_tier: str,
    stewards_ratio: float,
    state: StadiumState,
) -> list[str]:
    """Produce concrete, prioritised actions for a single zone.

    Rules run from most to least urgent so the first action listed is the one
    staff should act on first.
    """
    actions = []
    weather = state.match.weather
    minutes = state.match.minutes_to_kickoff

    # Crowding response.
    if density_tier == "CRITICAL" or density_pct >= 1.0:
        actions.append(
            f"Pause new entry at {zone.name} and divert arrivals to lower-density zones."
        )
    elif density_tier == "HIGH":
        actions.append(
            f"Open additional entry lanes at {zone.name} and slow upstream flow."
        )

    # Arrivals surge close to kickoff.
    if 0 <= minutes <= 30 and zone.inflow_per_min >= 60 and density_pct >= DENSITY_ELEVATED:
        actions.append(
            f"Add express screening at {zone.name}: {zone.inflow_per_min} fans/min "
            f"still arriving with {minutes} min to kickoff."
        )

    # Staffing gap.
    if stewards_ratio > SAFE_STEWARD_RATIO:
        needed = math.ceil(zone.occupancy / SAFE_STEWARD_RATIO) - zone.stewards
        if needed > 0:
            actions.append(
                f"Dispatch {needed} more steward(s) to {zone.name} "
                f"(currently ~1 per {int(stewards_ratio)} fans)."
            )

    # Incident escalation.
    if zone.open_incidents > 0:
        actions.append(
            f"Escalate {zone.open_incidents} active incident(s) at {zone.name} "
            f"to the control room."
        )

    # Accessibility safeguard when a busy zone lacks step-free access.
    if not zone.step_free_access and density_tier in ("HIGH", "CRITICAL"):
        actions.append(
            f"Open a staffed step-free route near {zone.name} for wheelchair users "
            f"and reduced-mobility fans."
        )

    # Weather care for exposed queues.
    if weather == "extreme_heat" and density_tier != "NORMAL":
        actions.append(f"Deploy water and shaded waiting at {zone.name} (extreme heat).")
    elif weather in ("rain", "storm") and density_tier != "NORMAL":
        actions.append(
            f"Provide covered holding at {zone.name} and keep open-air queues moving ({weather})."
        )

    # Nothing urgent: keep watching.
    if not actions:
        actions.append(f"Maintain routine monitoring at {zone.name}.")

    return actions


def _highest_level(levels: list[str]) -> str:
    """Return the single worst risk level from a list (LOW if the list is empty)."""
    if not levels:
        return "LOW"
    return max(levels, key=lambda level: RISK_LEVEL_ORDER.index(level))


def assess_stadium(state: StadiumState) -> StadiumAssessment:
    """Assess every zone and return a ranked, explainable stadium assessment."""
    zone_assessments = []

    for zone in state.zones:
        density_pct, stewards_ratio, risk_score = _score_zone(
            zone, state.match.weather, state.match.minutes_to_kickoff
        )
        tier = _density_tier(density_pct)
        level = _risk_level(risk_score)
        actions = _recommend(zone, density_pct, tier, stewards_ratio, state)

        zone_assessments.append(
            ZoneAssessment(
                id=zone.id,
                name=zone.name,
                density_pct=round(density_pct * 100, 1),
                density_tier=tier,
                stewards_ratio=round(stewards_ratio, 1),
                risk_score=risk_score,
                risk_level=level,
                recommended_actions=actions,
            )
        )

    # Rank zones by risk, highest first, so staff see the priority order.
    zone_assessments.sort(key=lambda z: z.risk_score, reverse=True)

    overall = _highest_level([z.risk_level for z in zone_assessments])
    highest = zone_assessments[0].name if zone_assessments else None

    return StadiumAssessment(
        stadium=state.stadium,
        fixture=state.match.fixture,
        minutes_to_kickoff=state.match.minutes_to_kickoff,
        weather=state.match.weather,
        overall_risk_level=overall,
        highest_risk_zone=highest,
        zones=zone_assessments,
    )
