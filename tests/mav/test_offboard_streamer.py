from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mav.offboard_streamer import OffboardVelocityStreamer


@pytest.mark.asyncio
async def test_streamer_sends_initial_setpoint_before_starting_offboard():
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    count = await OffboardVelocityStreamer(rate_hz=20.0).stream_for(
        drone, setpoint, duration_s=0.12
    )

    assert count >= 2
    assert drone.offboard.set_velocity_ned.await_count >= 3
    assert drone.offboard.set_velocity_ned.await_args_list[0].args == (setpoint,)
    drone.offboard.start.assert_awaited_once()
    drone.offboard.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_streamer_stops_offboard_when_streaming_raises():
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock(
        side_effect=[None, None, RuntimeError("link lost")]
    )
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    count = await OffboardVelocityStreamer(rate_hz=20.0).stream_for(
        drone, setpoint, duration_s=0.2
    )

    assert count == 1
    drone.offboard.stop.assert_awaited_once()
