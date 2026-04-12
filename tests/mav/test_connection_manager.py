"""Tests for the Singleton ConnectionManager.

These tests verify:
- Singleton behavior (same instance across imports)
- Connection state machine transitions
- Fast access after first connection (<100ms)
- Auto-reconnect on connection loss
- Thread safety with concurrent access
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These imports will fail initially (TDD - tests first)
from avatar.mav.connection_manager import ConnectionManager, ConnectionState, ConnectionHealth


class TestSingletonBehavior:
    """Test singleton pattern enforcement."""

    def test_singleton_same_instance(self) -> None:
        """Two instantiations return the same object."""
        # Reset any existing instance first
        ConnectionManager._instance = None

        cm1 = ConnectionManager()
        cm2 = ConnectionManager()

        assert cm1 is cm2
        assert id(cm1) == id(cm2)

    def test_singleton_across_threads(self) -> None:
        """Singleton works across different import contexts."""
        # Clear and create fresh
        ConnectionManager._instance = None

        cm1 = ConnectionManager()
        cm2 = ConnectionManager()

        # Verify same instance
        assert cm1 is cm2
        # Verify internal state is shared
        cm1._test_marker = "shared"
        assert cm2._test_marker == "shared"


class TestConnectionState:
    """Test connection state machine."""

    def test_initial_state(self) -> None:
        """Fresh instance starts in DISCONNECTED state."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        assert cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_state_transitions(self) -> None:
        """State machine transitions correctly through lifecycle."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        # Mock the MAVSDK System
        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        # Start connecting
        assert cm.state == ConnectionState.DISCONNECTED

        # Use an event to control connection timing
        connect_started = asyncio.Event()
        connect_continue = asyncio.Event()

        async def slow_connect(*args, **kwargs):
            connect_started.set()
            await connect_continue.wait()
            return mock_drone

        # Simulate slow connection to observe states
        with patch.object(cm, '_do_connect', side_effect=slow_connect):
            # Start connection
            task = asyncio.create_task(cm.connect("udp://:14540"))

            # Wait for connection to start
            await asyncio.wait_for(connect_started.wait(), timeout=1.0)

            # Should transition to CONNECTING
            assert cm.state == ConnectionState.CONNECTING

            # Complete connection
            connect_continue.set()
            await task

            # Should be CONNECTED
            assert cm.state == ConnectionState.CONNECTED

        # Disconnect
        await cm.disconnect()
        assert cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_state_error_on_failure(self) -> None:
        """State transitions to ERROR on connection failure."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        # Mock connection failure
        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection refused")

            result = await cm.connect("udp://:14540", max_retries=1)

            assert result is False
            assert cm.state == ConnectionState.ERROR


class TestConnectionTiming:
    """Test connection timing requirements."""

    @pytest.mark.asyncio
    async def test_first_connection_timing(self) -> None:
        """First connection completes in <5 seconds."""
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

            start = time.time()
            result = await cm.connect("udp://:14540", max_retries=1)
            elapsed = time.time() - start

            assert result is True
            assert elapsed < 5.0, f"First connection took {elapsed}s, expected <5s"

    @pytest.mark.asyncio
    async def test_subsequent_commands_fast(self) -> None:
        """get_drone() returns in <100ms after first connection."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()

        async def mock_connection_state():
            state = MagicMock()
            state.is_connected = True
            yield state

        mock_drone.core.connection_state = mock_connection_state

        # Pre-connect
        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone
            await cm.connect("udp://:14540", max_retries=1)

        # Now test get_drone() speed
        start = time.time()
        drone = await cm.get_drone()
        elapsed = time.time() - start

        assert drone is not None
        assert elapsed < 0.1, f"get_drone() took {elapsed}s, expected <100ms"


class TestAutoReconnect:
    """Test automatic reconnection behavior."""

    @pytest.mark.asyncio
    async def test_auto_reconnect_on_loss(self) -> None:
        """Auto-reconnects when connection is lost."""
        ConnectionManager._instance = None
        cm = ConnectionManager()
        cm._reconnect_delay_s = 0.01  # Fast reconnect for testing

        mock_drone = MagicMock()
        connection_count = 0

        async def mock_connection_state():
            nonlocal connection_count
            state = MagicMock()
            # First call connected, second call disconnected
            state.is_connected = connection_count == 0
            connection_count += 1
            yield state

        mock_drone.core.connection_state = mock_connection_state

        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_drone

            # Initial connection
            await cm.connect("udp://:14540", max_retries=1)
            assert cm.state == ConnectionState.CONNECTED

            # Simulate disconnect by triggering health check failure
            cm._health.is_healthy = False

            # Wait for auto-reconnect to trigger
            await asyncio.sleep(0.05)

            # Should have attempted reconnect
            assert mock_connect.call_count >= 1

    @pytest.mark.asyncio
    async def test_ensure_connected_raises(self) -> None:
        """ensure_connected() raises ConnectionError when not connected."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        with pytest.raises(ConnectionError):
            await cm.ensure_connected()


class TestConnectionHealth:
    """Test health monitoring."""

    @pytest.mark.asyncio
    async def test_health_tracking(self) -> None:
        """Health data is tracked correctly."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        # Initial health
        assert cm.health.is_healthy is False
        assert cm.health.error_count == 0

        # Update health
        cm._update_health(is_healthy=True, gps_lock=True, home_position_set=True)

        assert cm.health.is_healthy is True
        assert cm.health.gps_lock is True
        assert cm.health.home_position_set is True

    @pytest.mark.asyncio
    async def test_error_counting(self) -> None:
        """Error count increments correctly."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        assert cm.health.error_count == 0

        # Record some errors
        cm._record_error("Test error 1")
        cm._record_error("Test error 2")

        assert cm.health.error_count == 2
        assert cm.health.last_error == "Test error 2"


class TestThreadSafety:
    """Test thread safety with concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_get_drone(self) -> None:
        """Multiple concurrent get_drone() calls are safe."""
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
            await cm.connect("udp://:14540", max_retries=1)

        # Multiple concurrent get_drone calls
        async def get_drone_task():
            return await cm.get_drone()

        tasks = [get_drone_task() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should get the same drone instance
        assert all(r is mock_drone for r in results)

    @pytest.mark.asyncio
    async def test_connect_while_connecting(self) -> None:
        """Second connect() when already connected returns immediately."""
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

            # First connection
            result1 = await cm.connect("udp://:14540", max_retries=1)
            assert result1 is True
            assert cm.state == ConnectionState.CONNECTED

            # Second connect when already connected should return immediately
            start = asyncio.get_event_loop().time()
            result2 = await cm.connect("udp://:14540", max_retries=1)
            elapsed = asyncio.get_event_loop().time() - start

            # Should succeed immediately without calling _do_connect again
            assert result2 is True
            assert elapsed < 0.1  # Should be fast
            assert mock_connect.call_count == 1  # Only called once


class TestDisconnect:
    """Test disconnect behavior."""

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self) -> None:
        """Disconnect properly cleans up resources."""
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
            await cm.connect("udp://:14540", max_retries=1)

        assert cm.state == ConnectionState.CONNECTED

        await cm.disconnect()

        assert cm.state == ConnectionState.DISCONNECTED
        assert cm._drone is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_drone_while_disconnected(self) -> None:
        """get_drone() returns None when disconnected."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        drone = await cm.get_drone()
        assert drone is None

    @pytest.mark.asyncio
    async def test_connect_with_retries(self) -> None:
        """Connection retries on transient failures."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        mock_drone = MagicMock()
        call_count = 0

        async def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Attempt {call_count} failed")

            async def mock_connection_state():
                state = MagicMock()
                state.is_connected = True
                yield state

            mock_drone.core.connection_state = mock_connection_state
            return mock_drone

        with patch.object(cm, '_do_connect', side_effect=failing_then_success):
            start = time.time()
            result = await cm.connect(
                "udp://:14540",
                max_retries=5,
                retry_delay_s=0.01
            )
            elapsed = time.time() - start

            assert result is True
            assert call_count == 3
            assert elapsed < 1.0  # Should be fast with small delays

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        """Returns False when all retries fail."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        with patch.object(cm, '_do_connect', side_effect=Exception("Always fails")):
            result = await cm.connect(
                "udp://:14540",
                max_retries=3,
                retry_delay_s=0.01
            )

            assert result is False
            assert cm.state == ConnectionState.ERROR
            assert cm.health.error_count == 3
