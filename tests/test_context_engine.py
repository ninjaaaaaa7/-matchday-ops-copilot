"""Unit tests for the deterministic context engine."""

from app.context_engine import (
    _density_tier,
    _highest_level,
    _risk_level,
    assess_stadium,
)
from app.models import MatchContext, StadiumState, Zone


def _state(zones, minutes=25, weather="clear"):
    """Build a StadiumState with the given zones for testing."""
    return StadiumState(
        stadium="Test Stadium",
        match=MatchContext(
            fixture="Test Fixture", minutes_to_kickoff=minutes, weather=weather
        ),
        zones=zones,
    )


def test_density_tier_boundaries():
    # Values are classified into the correct band, boundaries included.
    assert _density_tier(0.50) == "NORMAL"
    assert _density_tier(0.70) == "ELEVATED"
    assert _density_tier(0.85) == "HIGH"
    assert _density_tier(0.95) == "CRITICAL"
    assert _density_tier(1.20) == "CRITICAL"


def test_risk_level_boundaries():
    assert _risk_level(0) == "LOW"
    assert _risk_level(30) == "MODERATE"
    assert _risk_level(55) == "HIGH"
    assert _risk_level(80) == "CRITICAL"


def test_highest_level_picks_worst():
    assert _highest_level(["LOW", "HIGH", "MODERATE"]) == "HIGH"
    assert _highest_level([]) == "LOW"


def test_calm_zone_is_low_risk():
    zone = Zone(id="z1", name="Calm", capacity=1000, occupancy=300, stewards=10)
    result = assess_stadium(_state([zone]))
    assessed = result.zones[0]
    assert assessed.risk_level == "LOW"
    assert assessed.density_tier == "NORMAL"
    # A calm zone still receives a monitoring instruction, never an empty list.
    assert assessed.recommended_actions


def test_overcrowded_zone_is_critical():
    zone = Zone(
        id="z1",
        name="Packed Gate",
        capacity=1000,
        occupancy=1000,
        inflow_per_min=100,
        stewards=1,
        open_incidents=2,
    )
    result = assess_stadium(_state([zone], minutes=5))
    assessed = result.zones[0]
    assert assessed.risk_level == "CRITICAL"
    assert result.overall_risk_level == "CRITICAL"
    # The most urgent action (pause entry) should be first.
    assert "Pause new entry" in assessed.recommended_actions[0]


def test_zones_are_ranked_by_risk():
    calm = Zone(id="c", name="Calm", capacity=1000, occupancy=200, stewards=10)
    busy = Zone(id="b", name="Busy", capacity=1000, occupancy=990, stewards=1)
    result = assess_stadium(_state([calm, busy]))
    # Highest risk must come first regardless of input order.
    assert result.zones[0].name == "Busy"
    assert result.zones[0].risk_score >= result.zones[1].risk_score
    assert result.highest_risk_zone == "Busy"


def test_zero_stewards_does_not_crash():
    # No stewards must not raise a division error; the fan count is used instead.
    zone = Zone(id="z", name="Unmanaged", capacity=1000, occupancy=500, stewards=0)
    result = assess_stadium(_state([zone]))
    assert result.zones[0].stewards_ratio == 500.0


def test_understaffed_zone_recommends_more_stewards():
    zone = Zone(id="z", name="Thin", capacity=2000, occupancy=1600, stewards=2)
    result = assess_stadium(_state([zone]))
    actions = " ".join(result.zones[0].recommended_actions)
    assert "steward" in actions.lower()


def test_inaccessible_busy_zone_flags_step_free_route():
    zone = Zone(
        id="z",
        name="Old Stand",
        capacity=1000,
        occupancy=950,
        stewards=10,
        step_free_access=False,
    )
    result = assess_stadium(_state([zone]))
    actions = " ".join(result.zones[0].recommended_actions).lower()
    assert "step-free" in actions
