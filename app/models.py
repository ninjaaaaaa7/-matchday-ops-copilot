"""Pydantic data models shared across the API and the decision logic.

These schemas define the request/response contract. Pydantic validates every
incoming payload automatically, which gives us safe input handling for free.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Allowed weather conditions. Restricting the set keeps inputs predictable.
WeatherType = Literal["clear", "rain", "extreme_heat", "storm"]


class Zone(BaseModel):
    """A single physical zone of the stadium (gate, concourse, stand, etc.)."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    capacity: int = Field(..., gt=0, description="Maximum safe occupancy.")
    occupancy: int = Field(..., ge=0, description="Current number of people.")
    inflow_per_min: int = Field(0, ge=0, description="People entering per minute.")
    stewards: int = Field(0, ge=0, description="Stewards currently assigned.")
    open_incidents: int = Field(0, ge=0, description="Active incidents in the zone.")
    step_free_access: bool = Field(
        True, description="Whether the zone offers step-free (accessible) routing."
    )


class MatchContext(BaseModel):
    """Match-level context that influences risk across every zone."""

    fixture: str = Field(..., min_length=1)
    minutes_to_kickoff: int = Field(
        ..., description="Minutes until kickoff; negative once the match is in play."
    )
    weather: WeatherType = "clear"
    expected_attendance: int = Field(0, ge=0)


class StadiumState(BaseModel):
    """A full snapshot of the stadium at a point in time."""

    stadium: str = Field(..., min_length=1)
    match: MatchContext
    zones: List[Zone] = Field(..., min_length=1)


class ZoneAssessment(BaseModel):
    """The computed risk assessment for a single zone."""

    id: str
    name: str
    density_pct: float  # occupancy as a percentage of capacity
    density_tier: str  # NORMAL | ELEVATED | HIGH | CRITICAL
    stewards_ratio: float  # fans per steward
    risk_score: float  # 0-100
    risk_level: str  # LOW | MODERATE | HIGH | CRITICAL
    recommended_actions: List[str]


class StadiumAssessment(BaseModel):
    """The full assessment returned by the context engine."""

    stadium: str
    fixture: str
    minutes_to_kickoff: int
    weather: str
    overall_risk_level: str
    highest_risk_zone: Optional[str]
    zones: List[ZoneAssessment]


class CopilotRequest(BaseModel):
    """A staff question plus the stadium snapshot it should be answered against."""

    state: StadiumState
    question: str = Field(..., min_length=1, max_length=500)
    language: str = Field("English", min_length=1, max_length=40)


class CopilotResponse(BaseModel):
    """The copilot's grounded answer alongside the raw assessment."""

    assessment: StadiumAssessment
    answer: str
    mode: str  # "live" (real model) or "demo" (deterministic fallback)
