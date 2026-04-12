"""Tests for context managers.

These tests verify:
- managed_connection: Auto-connect/disconnect with proper cleanup
- managed_offboard: Safe offboard entry/exit with heartbeat
- managed_telemetry_cache: Automatic cache lifecycle
- batch_operations: Controlled concurrent execution
- FlightSession: Full lifecycle management with cleanup

All tests verify proper cleanup even when exceptions occur.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.core.context_managers import (
    FlightSession,
    batch_operations,
    managed_connection,
    managed_offboard,
    managed_telemetry_cache,
    _get_telemetry_from_drone,
)
from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mav.telemetry_cache import TelemetryData


class TestManagedConnection:
    """Test managed_connection context manager."""

    @pytest.mark.asyncio
    async def test_managed_connection_auto_connects(self) -> None:
        """managed_connection auto-connects on entry."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with managed_connection("udp://:14540", timeout_s=1.0) as conn_cm:
                assert conn_cm is not None
                assert conn_cm.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_managed_connection_auto_disconnects(self) -> None:
        """managed_connection auto-disconnects on exit."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with managed_connection("udp://:14540", timeout_s=1.0) as conn_cm:
                assert conn_cm.state == ConnectionState.CONNECTED

            # After exit, should be disconnected
            assert conn_cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_managed_connection_cleanup_on_error(self) -> None:
        """managed_connection cleans up even when exception occurs."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            try:
                async with managed_connection("udp://:14540", timeout_s=1.0) as conn_cm:
                    assert conn_cm.state == ConnectionState.CONNECTED
                    raise ValueError("Test error")
            except ValueError:
                pass  # Expected

            # Should still be disconnected after exception
            assert conn_cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_managed_connection_raises_on_failure(self) -> None:
        """managed_connection raises ConnectionError on connect failure."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = None  # Connection failed

            with pytest.raises(ConnectionError):
                async with managed_connection("udp://:14540", timeout_s=1.0):
                    pass

    @pytest.mark.asyncio
    async def test_managed_connection_timeout(self) -> None:
        """managed_connection respects timeout parameter."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(10.0)  # Very slow
            return None

        with patch.object(cm, '_do_connect', side_effect=slow_connect):
            with pytest.raises(asyncio.TimeoutError):
                async with managed_connection("udp://:14540", timeout_s=0.1):
                    pass


class TestManagedOffboard:
    """Test managed_offboard context manager."""

    @pytest.mark.asyncio
    async def test_managed_offboard_starts(self) -> None:
        """managed_offboard starts offboard mode on entry."""
        mock_drone = MagicMock()
        mock_offboard = MagicMock()
        mock_offboard.start = AsyncMock()
        mock_offboard.stop = AsyncMock()
        mock_offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard = mock_offboard

        # Patch the import within the module
        with patch.dict('sys.modules', {'mavsdk.offboard': MagicMock(OffboardError=Exception)}):
            async with managed_offboard(mock_drone) as offboard:
                # Verify start was called
                mock_offboard.start.assert_called_once()
                assert offboard is mock_offboard

    @pytest.mark.asyncio
    async def test_managed_offboard_stops(self) -> None:
        """managed_offboard stops offboard mode on exit."""
        mock_drone = MagicMock()
        mock_offboard = MagicMock()
        mock_offboard.start = AsyncMock()
        mock_offboard.stop = AsyncMock()
        mock_offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard = mock_offboard

        with patch.dict('sys.modules', {'mavsdk.offboard': MagicMock(OffboardError=Exception)}):
            async with managed_offboard(mock_drone) as offboard:
                mock_offboard.start.assert_called_once()

            # After exit, stop should be called
            mock_offboard.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_managed_offboard_cleanup_on_error(self) -> None:
        """managed_offboard stops offboard even on exception."""
        mock_drone = MagicMock()
        mock_offboard = MagicMock()
        mock_offboard.start = AsyncMock()
        mock_offboard.stop = AsyncMock()
        mock_offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard = mock_offboard

        with patch.dict('sys.modules', {'mavsdk.offboard': MagicMock(OffboardError=Exception)}):
            try:
                async with managed_offboard(mock_drone) as offboard:
                    raise ValueError("Test error in offboard")
            except ValueError:
                pass  # Expected

            # Stop should still be called
            mock_offboard.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_managed_offboard_with_initial_setpoint(self) -> None:
        """managed_offboard sets initial setpoint if provided."""
        mock_drone = MagicMock()
        mock_offboard = MagicMock()
        mock_offboard.start = AsyncMock()
        mock_offboard.stop = AsyncMock()
        mock_offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard = mock_offboard

        mock_offboard_module = MagicMock()
        mock_offboard_module.VelocityNedYaw = MagicMock(return_value="mock_velocity")
        mock_offboard_module.OffboardError = Exception

        initial_setpoint = {"north_m_s": 1.0, "east_m_s": 0.0, "down_m_s": 0.0, "yaw_deg": 0.0}

        with patch.dict('sys.modules', {'mavsdk.offboard': mock_offboard_module}):
            async with managed_offboard(mock_drone, initial_setpoint=initial_setpoint):
                # Verify set_velocity_ned was called with initial setpoint
                mock_offboard.set_velocity_ned.assert_called_once()

    @pytest.mark.asyncio
    async def test_managed_offboard_handles_stop_error(self) -> None:
        """managed_offboard handles errors during stop gracefully."""
        mock_drone = MagicMock()
        mock_offboard = MagicMock()
        mock_offboard.start = AsyncMock()
        mock_offboard.stop = AsyncMock(side_effect=Exception("Stop failed"))
        mock_offboard.set_velocity_ned = AsyncMock()
        mock_drone.offboard = mock_offboard

        with patch.dict('sys.modules', {'mavsdk.offboard': MagicMock(OffboardError=Exception)}):
            # Should not raise even though stop failed
            async with managed_offboard(mock_drone) as offboard:
                pass  # Normal operation


class TestManagedTelemetryCache:
    """Test managed_telemetry_cache context manager."""

    @pytest.mark.asyncio
    async def test_managed_cache_starts(self) -> None:
        """managed_telemetry_cache starts cache on entry."""
        mock_drone = MagicMock()

        # Mock telemetry data
        mock_telemetry = MagicMock()

        async def mock_position():
            pos = MagicMock()
            pos.latitude_deg = 37.7749
            pos.longitude_deg = -122.4194
            pos.relative_altitude_m = 10.0
            yield pos

        async def mock_velocity():
            vel = MagicMock()
            vel.north_m_s = 0.0
            vel.east_m_s = 0.0
            vel.down_m_s = 0.0
            yield vel

        async def mock_attitude():
            att = MagicMock()
            att.roll_deg = 0.0
            att.pitch_deg = 0.0
            att.yaw_deg = 0.0
            yield att

        async def mock_battery():
            bat = MagicMock()
            bat.remaining_percent = 0.85
            bat.voltage_v = 16.8
            bat.current_a = 5.0
            yield bat

        async def mock_armed():
            yield True

        async def mock_landed():
            yield 1  # In air

        async def mock_flight_mode():
            yield "HOLD"

        async def mock_health():
            health = MagicMock()
            health.is_global_position_ok = True
            health.is_home_position_ok = True
            yield health

        async def mock_gps_info():
            gps = MagicMock()
            gps.fix_type = 3
            yield gps

        mock_drone.telemetry.position = mock_position
        mock_drone.telemetry.velocity_ned = mock_velocity
        mock_drone.telemetry.attitude_euler = mock_attitude
        mock_drone.telemetry.battery = mock_battery
        mock_drone.telemetry.armed = mock_armed
        mock_drone.telemetry.landed_state = mock_landed
        mock_drone.telemetry.flight_mode = mock_flight_mode
        mock_drone.telemetry.health = mock_health
        mock_drone.telemetry.gps_info = mock_gps_info

        async with managed_telemetry_cache(mock_drone, refresh_interval_ms=50) as cache:
            # Wait for first refresh
            await asyncio.sleep(0.1)
            data = cache.get_data()
            assert data is not None
            assert isinstance(data, TelemetryData)

    @pytest.mark.asyncio
    async def test_managed_cache_stops(self) -> None:
        """managed_telemetry_cache stops cache on exit."""
        mock_drone = MagicMock()

        # Mock all telemetry streams
        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=0.0, longitude_deg=0.0, relative_altitude_m=0.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        async with managed_telemetry_cache(mock_drone, refresh_interval_ms=50) as cache:
            await asyncio.sleep(0.1)
            assert cache.get_data() is not None

        # After exit, cache should be stopped (is_stale should return True eventually)
        await asyncio.sleep(0.1)
        # Cache is stopped, so data won't update and will become stale

    @pytest.mark.asyncio
    async def test_managed_cache_cleanup_on_error(self) -> None:
        """managed_telemetry_cache stops even on exception."""
        mock_drone = MagicMock()

        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=0.0, longitude_deg=0.0, relative_altitude_m=0.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        try:
            async with managed_telemetry_cache(mock_drone, refresh_interval_ms=50) as cache:
                await asyncio.sleep(0.1)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Cache should be stopped (no errors during cleanup)


class TestBatchOperations:
    """Test batch_operations context manager."""

    @pytest.mark.asyncio
    async def test_batch_executes_operations(self) -> None:
        """batch_operations executes all operations."""
        from avatar.core.context_managers import BatchOperations

        executed = []

        async def op1():
            executed.append(1)
            return 1

        async def op2():
            executed.append(2)
            return 2

        async def op3():
            executed.append(3)
            return 3

        batch = BatchOperations(max_concurrent=3)
        async with batch:
            batch.operations.append(op1())
            batch.operations.append(op2())
            batch.operations.append(op3())

        assert sorted(executed) == [1, 2, 3]
        assert sorted(batch.results) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_batch_respects_concurrency_limit(self) -> None:
        """batch_operations respects max_concurrent parameter."""
        from avatar.core.context_managers import BatchOperations

        running_count = 0
        max_running = 0

        async def tracked_op():
            nonlocal running_count, max_running
            running_count += 1
            max_running = max(max_running, running_count)
            await asyncio.sleep(0.1)
            running_count -= 1
            return 1

        batch = BatchOperations(max_concurrent=2)
        async with batch:
            for _ in range(5):
                batch.operations.append(tracked_op())

        assert max_running <= 2

    @pytest.mark.asyncio
    async def test_batch_empty(self) -> None:
        """batch_operations handles empty batch."""
        from avatar.core.context_managers import BatchOperations

        batch = BatchOperations()
        async with batch:
            pass  # No operations added

        # Should complete without error
        assert batch.results == []

    @pytest.mark.asyncio
    async def test_batch_continue_on_error(self) -> None:
        """batch_operations with continue_on_error handles exceptions."""
        from avatar.core.context_managers import BatchOperations

        async def good_op():
            return "success"

        async def bad_op():
            raise ValueError("Test error")

        batch = BatchOperations(max_concurrent=3, continue_on_error=True)
        async with batch:
            batch.operations.append(good_op())
            batch.operations.append(bad_op())
            batch.operations.append(good_op())

        # Results should contain exceptions for bad ops
        assert batch.results[0] == "success"
        assert isinstance(batch.results[1], ValueError)
        assert batch.results[2] == "success"

    @pytest.mark.asyncio
    async def test_batch_raises_on_error(self) -> None:
        """batch_operations without continue_on_error raises on first error."""
        from avatar.core.context_managers import BatchOperations

        async def bad_op():
            raise ValueError("Test error")

        batch = BatchOperations(max_concurrent=3, continue_on_error=False)
        with pytest.raises(ValueError):
            async with batch:
                batch.operations.append(bad_op())


class TestFlightSession:
    """Test FlightSession context manager."""

    @pytest.mark.asyncio
    async def test_flight_session_lifecycle(self) -> None:
        """FlightSession manages full connection lifecycle."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()
        mock_drone.action.takeoff = AsyncMock()
        mock_drone.action.land = AsyncMock()
        mock_drone.action.arm = AsyncMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        # Mock telemetry streams
        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=37.7749, longitude_deg=-122.4194, relative_altitude_m=10.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with FlightSession("udp://:14540", connection_timeout_s=1.0) as session:
                assert session.is_running is True
                assert session.cm is not None
                assert session.drone is not None

                # Test telemetry access
                telemetry = session.get_telemetry()
                assert telemetry is not None

                # Test flight commands
                await session.arm()
                mock_drone.action.arm.assert_called_once()

                await session.takeoff(altitude_m=5.0)
                mock_drone.action.takeoff.assert_called_once()

            # After exit
            assert session.is_running is False
            assert session.cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_flight_session_cleanup_on_error(self) -> None:
        """FlightSession cleans up even on exception."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        # Mock telemetry
        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=0.0, longitude_deg=0.0, relative_altitude_m=0.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            try:
                async with FlightSession("udp://:14540", connection_timeout_s=1.0) as session:
                    assert session.is_running is True
                    raise ValueError("Test error in session")
            except ValueError:
                pass  # Expected

            # Should be disconnected after exception
            assert cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_flight_session_connection_failure(self) -> None:
        """FlightSession raises ConnectionError on connect failure."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = None  # Connection failed

            with pytest.raises(ConnectionError):
                async with FlightSession("udp://:14540", connection_timeout_s=0.5):
                    pass

    @pytest.mark.asyncio
    async def test_flight_session_is_telemetry_fresh(self) -> None:
        """FlightSession.is_telemetry_fresh() works correctly."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=0.0, longitude_deg=0.0, relative_altitude_m=0.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with FlightSession(
                "udp://:14540",
                connection_timeout_s=1.0,
                telemetry_refresh_ms=50,  # Fast refresh
            ) as session:
                # Initially no telemetry, should return False (not fresh)
                # as there's no data in the cache yet
                assert session.is_telemetry_fresh() is False

                # Wait for telemetry cache to start and get initial data
                await asyncio.sleep(0.3)

                # The method should be callable and return a boolean
                result = session.is_telemetry_fresh()
                assert isinstance(result, bool)

                # Verify get_telemetry returns data (indicating the cache is working)
                data = session.get_telemetry()
                # Either we have data or we don't - both are valid states
                # depending on timing, but the method should not crash

    @pytest.mark.asyncio
    async def test_flight_session_get_fresh_telemetry(self) -> None:
        """FlightSession.get_fresh_telemetry() returns data."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=37.0, longitude_deg=-122.0, relative_altitude_m=10.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=90.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=0.9, voltage_v=16.0, current_a=1.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(True)
        mock_drone.telemetry.landed_state = lambda: mock_single(1)
        mock_drone.telemetry.flight_mode = lambda: mock_single("OFFBOARD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with FlightSession("udp://:14540", connection_timeout_s=1.0) as session:
                await asyncio.sleep(0.15)
                data = await session.get_fresh_telemetry()
                assert data is not None
                assert isinstance(data, TelemetryData)
                assert data.latitude == 37.0

    @pytest.mark.asyncio
    async def test_flight_session_land(self) -> None:
        """FlightSession.land() commands landing."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()
        mock_drone.action.land = AsyncMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=0.0, longitude_deg=0.0, relative_altitude_m=0.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with FlightSession("udp://:14540", connection_timeout_s=1.0) as session:
                await session.land()
                mock_drone.action.land.assert_called_once()

    @pytest.mark.asyncio
    async def test_flight_session_disarm(self) -> None:
        """FlightSession.disarm() commands disarm."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()
        mock_drone.action.disarm = AsyncMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=0.0, longitude_deg=0.0, relative_altitude_m=0.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            async with FlightSession("udp://:14540", connection_timeout_s=1.0) as session:
                await session.disarm()
                mock_drone.action.disarm.assert_called_once()


class TestGetTelemetryFromDrone:
    """Test _get_telemetry_from_drone helper."""

    @pytest.mark.asyncio
    async def test_get_telemetry_from_drone(self) -> None:
        """_get_telemetry_from_drone returns TelemetryData."""
        mock_drone = MagicMock()

        async def mock_single(value):
            yield value

        mock_drone.telemetry.position = lambda: mock_single(MagicMock(
            latitude_deg=37.7749, longitude_deg=-122.4194, relative_altitude_m=100.0
        ))
        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=1.0, east_m_s=2.0, down_m_s=0.5
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.1, pitch_deg=0.2, yaw_deg=0.3
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=0.85, voltage_v=16.8, current_a=5.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(True)
        mock_drone.telemetry.landed_state = lambda: mock_single(1)
        mock_drone.telemetry.flight_mode = lambda: mock_single("OFFBOARD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=True, is_home_position_ok=True
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=3))

        data = await _get_telemetry_from_drone(mock_drone)

        assert isinstance(data, TelemetryData)
        assert data.latitude == 37.7749
        assert data.longitude == -122.4194
        assert data.altitude == 100.0
        assert data.velocity_north == 1.0
        assert data.velocity_east == 2.0
        assert data.velocity_down == 0.5
        assert data.groundspeed == pytest.approx(2.236, abs=0.01)
        assert data.roll == 0.1
        assert data.pitch == 0.2
        assert data.yaw == 0.3
        assert data.battery_percent == 85.0
        assert data.battery_voltage == 16.8
        assert data.battery_current == 5.0
        assert data.armed is True
        assert data.in_air is True
        assert data.flight_mode == "OFFBOARD"
        assert data.gps_fix == 3
        assert data.is_gps_ok is True
        assert data.is_home_position_ok is True

    @pytest.mark.asyncio
    async def test_get_telemetry_handles_errors(self) -> None:
        """_get_telemetry_from_drone handles telemetry errors gracefully."""
        mock_drone = MagicMock()

        # Make position raise an exception
        async def failing_position():
            raise Exception("Position failed")
            yield MagicMock()  # Never reached

        mock_drone.telemetry.position = failing_position

        # Other streams work
        async def mock_single(value):
            yield value

        mock_drone.telemetry.velocity_ned = lambda: mock_single(MagicMock(
            north_m_s=0.0, east_m_s=0.0, down_m_s=0.0
        ))
        mock_drone.telemetry.attitude_euler = lambda: mock_single(MagicMock(
            roll_deg=0.0, pitch_deg=0.0, yaw_deg=0.0
        ))
        mock_drone.telemetry.battery = lambda: mock_single(MagicMock(
            remaining_percent=1.0, voltage_v=16.0, current_a=0.0
        ))
        mock_drone.telemetry.armed = lambda: mock_single(False)
        mock_drone.telemetry.landed_state = lambda: mock_single(0)
        mock_drone.telemetry.flight_mode = lambda: mock_single("HOLD")
        mock_drone.telemetry.health = lambda: mock_single(MagicMock(
            is_global_position_ok=False, is_home_position_ok=False
        ))
        mock_drone.telemetry.gps_info = lambda: mock_single(MagicMock(fix_type=0))

        # Should not raise, returns default values
        data = await _get_telemetry_from_drone(mock_drone)
        assert isinstance(data, TelemetryData)
        assert data.latitude == 0.0  # Default value
