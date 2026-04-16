import pytest

from avatar.sim.scenarios import get_scenario
from tests.e2e.mcp_sitl_helpers import require_mcp_sitl, run_mcp_sitl_sequence


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_indoor_obstacle_room_scenario_gate(request):
    require_mcp_sitl(request)

    scenario = get_scenario("indoor_obstacle_room_depth")
    assert scenario.kind == "indoor_obstacle_room"

    responses = await run_mcp_sitl_sequence([
        ("get_status", {}),
        ("arm_and_takeoff", {"altitude_m": 3.0}),
        ("__sleep__", {"seconds": 6.0}),
        ("set_velocity", {"north_m_s": 0.4, "east_m_s": 0.0, "duration_s": 2.0}),
        ("set_velocity", {"north_m_s": 0.0, "east_m_s": 0.4, "duration_s": 2.0}),
        ("abort_mission", {"reason": "indoor obstacle drill complete"}),
        ("land", {}),
    ])

    assert responses[1]["success"] is True
    assert responses[2]["success"] is True
    assert responses[3]["success"] is True
    assert responses[4]["success"] is True
    assert responses[5]["success"] is True
