import pytest

from avatar.sim.scenarios import get_scenario
from tests.e2e.mcp_sitl_helpers import require_mcp_sitl, run_mcp_sitl_sequence


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_runner_follow_scenario_gate(request):
    require_mcp_sitl(request)

    scenario = get_scenario("runner_follow_basic")
    assert scenario.kind == "runner_follow"

    responses = await run_mcp_sitl_sequence([
        ("get_status", {}),
        ("arm_and_takeoff", {"altitude_m": 5.0}),
        ("__sleep__", {"seconds": 8.0}),
        ("set_velocity", {"north_m_s": 1.5, "east_m_s": 0.4, "duration_s": 3.0}),
        ("set_velocity", {"north_m_s": 1.0, "east_m_s": -0.3, "duration_s": 3.0}),
        ("land", {}),
    ])

    assert responses[1]["success"] is True
    assert responses[2]["success"] is True
    assert responses[3]["success"] is True
    assert responses[4]["success"] is True
