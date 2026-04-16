import asyncio

import pytest

from tests.e2e.mcp_sitl_helpers import (
    ClientSession,
    call_tool_json,
    mcp_server_params,
    require_mcp_sitl,
    stdio_client,
)


async def wait_for_hovering(session, timeout_s: float = 12.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_s
    last_status = {}

    while asyncio.get_running_loop().time() < deadline:
        last_status = await call_tool_json(session, "get_status")
        state = last_status["state_machine"]["current_state"]
        if state in {"HOVERING", "FLYING"}:
            return last_status
        await asyncio.sleep(0.25)

    pytest.fail(f"Drone did not reach hovering/flying state: {last_status}")


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.sitl_required
async def test_mcp_can_run_basic_sitl_flight_smoke(request):
    require_mcp_sitl(request)
    params = mcp_server_params()

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            status = await call_tool_json(session, "get_status")
            telemetry = await call_tool_json(session, "get_telemetry")
            takeoff = await call_tool_json(session, "arm_and_takeoff", {"altitude_m": 5.0})
            airborne_status = await wait_for_hovering(session)
            hold = await call_tool_json(session, "hold", {"duration_s": 2.0})
            land = await call_tool_json(session, "land")

    assert status["initialized"] is True
    assert telemetry["success"] is True
    assert takeoff["success"] is True
    assert airborne_status["state_machine"]["current_state"] in {"HOVERING", "FLYING"}
    assert hold["success"] is True
    assert land["success"] is True
