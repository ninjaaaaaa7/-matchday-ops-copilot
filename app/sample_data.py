"""A realistic sample stadium snapshot used for demos and the default UI.

The numbers are chosen to show a range of situations: calm zones, a busy gate,
an understaffed transit link with active incidents, and extreme-heat weather.
"""

from .models import MatchContext, StadiumState, Zone


def sample_state() -> StadiumState:
    """Return a representative FIFA World Cup 2026 matchday snapshot."""
    return StadiumState(
        stadium="MetLife Stadium, New York/New Jersey",
        match=MatchContext(
            fixture="Group Stage - Argentina vs Mexico",
            minutes_to_kickoff=25,
            weather="extreme_heat",
            expected_attendance=82500,
        ),
        zones=[
            Zone(
                id="gate-a",
                name="Gate A (North)",
                capacity=6000,
                occupancy=5850,
                inflow_per_min=95,
                stewards=18,
                open_incidents=1,
                step_free_access=True,
            ),
            Zone(
                id="gate-c",
                name="Gate C (East)",
                capacity=5000,
                occupancy=4100,
                inflow_per_min=70,
                stewards=12,
                open_incidents=0,
                step_free_access=False,
            ),
            Zone(
                id="concourse-2",
                name="Concourse 2",
                capacity=8000,
                occupancy=5200,
                inflow_per_min=40,
                stewards=20,
                open_incidents=0,
                step_free_access=True,
            ),
            Zone(
                id="fan-zone",
                name="South Fan Zone",
                capacity=12000,
                occupancy=6000,
                inflow_per_min=30,
                stewards=15,
                open_incidents=0,
                step_free_access=True,
            ),
            Zone(
                id="transit-hub",
                name="Transit Hub Link",
                capacity=4000,
                occupancy=3950,
                inflow_per_min=110,
                stewards=8,
                open_incidents=2,
                step_free_access=False,
            ),
        ],
    )
