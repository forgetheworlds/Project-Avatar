import pytest

from avatar.sim.scenarios import get_scenario
from tests.e2e.mcp_sitl_helpers import require_mcp_sitl, run_mcp_sitl_sequence


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_nature_cinematic_scenario_gate(request):
    require_mcp_sitl(request)

    scenario = get_scenario("nature_orbit_reveal")
    assert scenario.kind == "nature_cinematic"

    responses = await run_mcp_sitl_sequence([
        ("preview_cinematic_shot", {
            "template_name": "orbit_close",
            "target_lat": 47.39798,
            "target_lon": 8.54618,
        }),
        ("arm_and_takeoff", {"altitude_m": 6.0}),
        ("__sleep__", {"seconds": 9.0}),
        ("set_velocity", {"north_m_s": 0.4, "east_m_s": 0.8, "duration_s": 3.0}),
        ("set_velocity", {"north_m_s": -0.3, "east_m_s": 0.6, "duration_s": 3.0}),
        ("land", {}),
    ])

    assert responses[0]["success"] is True
    assert responses[1]["success"] is True
    assert responses[2]["success"] is True
    assert responses[3]["success"] is True
    assert responses[4]["success"] is True
