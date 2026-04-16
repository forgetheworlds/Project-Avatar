"""Tests for OffboardVelocityStreamer with OffboardOwner integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.mav.offboard_streamer import OffboardVelocityStreamer
from avatar.mav.offboard_owner import OffboardOwner


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


@pytest.mark.asyncio
async def test_streamer_acquires_offboard_owner():
    """Streamer acquires OffboardOwner before starting offboard mode."""
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    owner = OffboardOwner()
    await owner.acquire("test_owner")  # Pre-acquire

    streamer = OffboardVelocityStreamer(rate_hz=20.0)
    count = await streamer.stream_for(
        drone, setpoint, duration_s=0.1,
        offboard_owner=owner, owner_id="streamer_test"
    )

    # Should have failed to acquire (already owned by test_owner)
    assert count == 0
    drone.offboard.start.assert_not_awaited()


@pytest.mark.asyncio
async def test_streamer_releases_offboard_owner_on_success():
    """Streamer releases OffboardOwner after successful streaming."""
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    owner = OffboardOwner()
    assert owner.current_owner() is None

    streamer = OffboardVelocityStreamer(rate_hz=20.0)
    count = await streamer.stream_for(
        drone, setpoint, duration_s=0.1,
        offboard_owner=owner, owner_id="streamer_test"
    )

    # Should have streamed successfully
    assert count >= 2

    # Owner should be released after streaming
    assert owner.current_owner() is None
    drone.offboard.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_streamer_releases_offboard_owner_on_error():
    """Streamer releases OffboardOwner even when error occurs."""
    drone = MagicMock()
    # First call succeeds (before offboard.start), second succeeds, third fails
    drone.offboard.set_velocity_ned = AsyncMock(
        side_effect=[None, None, RuntimeError("streaming error")]
    )
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    owner = OffboardOwner()
    assert owner.current_owner() is None

    streamer = OffboardVelocityStreamer(rate_hz=20.0)
    count = await streamer.stream_for(
        drone, setpoint, duration_s=0.2,
        offboard_owner=owner, owner_id="streamer_test"
    )

    # Should have streamed at least 1 setpoint before error
    # (1st is before start, 2nd increments count, 3rd fails)
    assert count >= 1

    # Owner should be released even after error
    assert owner.current_owner() is None
    drone.offboard.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_streamer_without_offboard_owner():
    """Streamer works without OffboardOwner for simple use cases."""
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    streamer = OffboardVelocityStreamer(rate_hz=20.0)
    count = await streamer.stream_for(
        drone, setpoint, duration_s=0.1,
        offboard_owner=None,  # No OffboardOwner
    )

    assert count >= 2
    drone.offboard.start.assert_awaited_once()
    drone.offboard.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_streamer_custom_owner_id():
    """Streamer uses custom owner_id for OffboardOwner."""
    drone = MagicMock()
    drone.offboard.set_velocity_ned = AsyncMock()
    drone.offboard.start = AsyncMock()
    drone.offboard.stop = AsyncMock()
    setpoint = MagicMock()

    owner = OffboardOwner()
    streamer = OffboardVelocityStreamer(rate_hz=20.0)

    # Start streaming (will acquire owner)
    count = await streamer.stream_for(
        drone, setpoint, duration_s=0.05,
        offboard_owner=owner, owner_id="my_custom_id"
    )

    assert count >= 1

    # After streaming, owner should be released
    assert owner.current_owner() is None
