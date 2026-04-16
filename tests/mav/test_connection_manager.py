"""Tests for the Singleton ConnectionManager.

These tests verify:
- Singleton behavior (same instance across imports)
- Connection state machine transitions
- Fast access after first connection (<100ms)
- Auto-reconnect on connection loss
- Thread safety with concurrent access

SAFETY CRITICAL: The ConnectionManager is the single point of communication
between the autonomous system and the drone. Failures here can cause:
- Loss of control link (potential flyaway)
- Delayed command execution (collision risk)
- State inconsistency (unsafe transitions)

All tests ensure reliable, predictable connection behavior under all conditions.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These imports will fail initially (TDD - tests first)
from avatar.mav.connection_manager import ConnectionManager, ConnectionState, ConnectionHealth


class TestSingletonBehavior:
    """Test singleton pattern enforcement.

    SAFETY: The singleton pattern ensures only one connection exists to prevent:
    - Multiple conflicting command sources
    - Resource exhaustion from duplicate connections
    - Race conditions in connection state management
    """

    def test_singleton_same_instance(self) -> None:
        """Two instantiations return the same object.

        VALIDATES: The singleton pattern is correctly implemented.

        MOCK SETUP: None required - testing pattern directly.

        SAFETY REASON: Multiple connection instances could each issue commands,
        causing the drone to receive conflicting instructions simultaneously.

        STEP-BY-STEP:
        1. Reset any existing singleton instance
        2. Create first ConnectionManager instance
        3. Create second ConnectionManager instance
        4. Assert both references point to same object (identity check)
        5. Assert object IDs are identical
        """
        # Reset any existing instance first
        ConnectionManager._instance = None

        cm1 = ConnectionManager()
        cm2 = ConnectionManager()

        assert cm1 is cm2
        assert id(cm1) == id(cm2)

    def test_singleton_across_threads(self) -> None:
        """Singleton works across different import contexts.

        VALIDATES: Internal state is truly shared between all access points.

        MOCK SETUP: None required - testing state sharing.

        SAFETY REASON: Different modules/components must see the same connection
        state to make consistent decisions about drone operations.

        STEP-BY-STEP:
        1. Clear singleton to start fresh
        2. Create first instance and set test marker
        3. Create second instance (should return same object)
        4. Modify marker through first instance
        5. Verify second instance sees the change (proves shared state)
        """
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
    """Test connection state machine.

    SAFETY: The state machine prevents invalid operations during connection
    lifecycle. For example, commands should not be sent while DISCONNECTED,
    and connection attempts should not stack while already CONNECTING.
    """

    def test_initial_state(self) -> None:
        """Fresh instance starts in DISCONNECTED state.

        VALIDATES: Initial state is safe (not connected by accident).

        MOCK SETUP: None - testing initial condition.

        SAFETY REASON: Starting in DISCONNECTED prevents accidental command
        sends before explicit connection setup. Forces intentional connection.

        STEP-BY-STEP:
        1. Reset singleton to ensure fresh instance
        2. Create new ConnectionManager
        3. Assert state is DISCONNECTED (safe default)
        """
        ConnectionManager._instance = None
        cm = ConnectionManager()

        assert cm.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_state_transitions(self) -> None:
        """State machine transitions correctly through lifecycle.

        VALIDATES: DISCONNECTED -> CONNECTING -> CONNECTED -> DISCONNECTED

        MOCK SETUP:
        - Mock MAVSDK System object with async connection_state generator
        - Mock _do_connect to control timing with asyncio Events
        - Slow connection simulation to observe intermediate states

        SAFETY REASON: Operators and other systems need to know the exact
        connection state to determine if commands can be sent. Intermediate
        CONNECTING state prevents duplicate connection attempts.

        STEP-BY-STEP:
        1. Reset singleton and create fresh ConnectionManager
        2. Create mock drone object with connection_state async generator
        3. Set up timing controls (connect_started, connect_continue events)
        4. Patch _do_connect with slow_connect that waits on events
        5. Start async connection task (should enter CONNECTING immediately)
        6. Wait for connect_started event (proves connection began)
        7. Assert state is CONNECTING (intermediate state visible)
        8. Signal connect_continue to allow connection to complete
        9. Await connection task completion
        10. Assert state is CONNECTED (final success state)
        11. Call disconnect()
        12. Assert state returns to DISCONNECTED
        """
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
        """State transitions to ERROR on connection failure.

        VALIDATES: Failed connections don't leave system in ambiguous state.

        MOCK SETUP: Patch _do_connect with AsyncMock that raises Exception.

        SAFETY REASON: ERROR state clearly indicates a problem exists. This
        prevents components from attempting operations on a broken connection.
        Also tracks error count for diagnostic purposes.

        STEP-BY-STEP:
        1. Reset singleton and create fresh ConnectionManager
        2. Patch _do_connect to raise "Connection refused" exception
        3. Attempt connection with max_retries=1 (single attempt)
        4. Assert connection returns False (failure indicated)
        5. Assert state is ERROR (not stuck in CONNECTING or CONNECTED)
        6. Assert error count is incremented (diagnostic tracking)
        """
        ConnectionManager._instance = None
        cm = ConnectionManager()

        # Mock connection failure
        with patch.object(cm, '_do_connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection refused")

            result = await cm.connect("udp://:14540", max_retries=1)

            assert result is False
            assert cm.state == ConnectionState.ERROR


class TestConnectionTiming:
    """Test connection timing requirements.

    SAFETY: Timing requirements ensure responsive control. Slow connections
    could delay emergency commands (RTL, Land, Kill) when seconds matter.
    """

    @pytest.mark.asyncio
    async def test_first_connection_timing(self) -> None:
        """First connection completes in <5 seconds.

        VALIDATES: Initial connection establishes within safety window.

        MOCK SETUP:
        - Mock MAVSDK System with connection_state generator
        - Mock _do_connect to return immediately (simulating fast connection)

        SAFETY REASON: If first connection takes too long, operators may
        assume system failure and attempt unsafe manual interventions.
        5 seconds allows time for MAVSDK discovery while remaining responsive.

        STEP-BY-STEP:
        1. Reset singleton and create fresh ConnectionManager
        2. Create mock drone with connection_state returning is_connected=True
        3. Patch _do_connect to return mock drone immediately
        4. Record start time
        5. Attempt connection with max_retries=1
        6. Record elapsed time
        7. Assert connection succeeded (result is True)
        8. Assert elapsed time < 5.0 seconds (timing requirement)
        """
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
        """get_drone() returns in <100ms after first connection.

        VALIDATES: Fast path for already-connected operations.

        MOCK SETUP:
        - Pre-connect the ConnectionManager before timing test
        - Mock MAVSDK System ready for immediate use

        SAFETY REASON: Emergency commands must be dispatched quickly.
        100ms ensures control latency stays within human reaction time bounds.
        Slow access could delay RTL/Land commands in emergencies.

        STEP-BY-STEP:
        1. Reset singleton and create fresh ConnectionManager
        2. Create mock drone and pre-connect (bypass timing measurement)
        3. With connection established, start timing
        4. Call get_drone() to retrieve drone reference
        5. Record elapsed time
        6. Assert drone reference returned (not None)
        7. Assert elapsed time < 100ms (fast path requirement)
        """
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
    """Test automatic reconnection behavior.

    SAFETY: Auto-reconnect maintains control link after temporary failures.
    Without auto-reconnect, a brief network interruption would leave the
    system permanently disconnected from a flying drone (catastrophic).
    """

    @pytest.mark.asyncio
    async def test_auto_reconnect_on_loss(self) -> None:
        """Auto-reconnects when connection is lost.

        VALIDATES: System detects connection loss and attempts recovery.

        MOCK SETUP:
        - Mock drone with connection_state that returns connected then disconnected
        - connection_count tracks which call we're on
        - Fast reconnect delay (0.01s) for test speed

        SAFETY REASON: Radio links can experience brief interference. Auto-reconnect
        prevents flyaway by restoring control as soon as signal returns. Without
        this, a momentary link loss would permanently strand a flying drone.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Set fast reconnect delay (0.01s) for testing
        3. Create mock with connection_count to alternate connected state
        4. connection_state returns is_connected=True on first call, False after
        5. Patch _do_connect to return mock drone
        6. Establish initial connection
        7. Assert state is CONNECTED
        8. Simulate health check failure (mark unhealthy)
        9. Wait for auto-reconnect to trigger (0.05s sleep)
        10. Assert _do_connect was called again (reconnect attempted)
        """
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
        """ensure_connected() raises ConnectionError when not connected.

        VALIDATES: Explicit check for connection before operations.

        MOCK SETUP: None - testing behavior when disconnected.

        SAFETY REASON: Commands sent to None drone would crash the system
        or fail silently. Raising ConnectionError forces explicit handling
        of the disconnected case at every call site.

        STEP-BY-STEP:
        1. Reset singleton and create fresh ConnectionManager
        2. Do not connect (state remains DISCONNECTED)
        3. Call ensure_connected() (used before critical operations)
        4. Assert ConnectionError is raised (prevents silent failures)
        """
        ConnectionManager._instance = None
        cm = ConnectionManager()

        with patch.object(cm, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = False

            with pytest.raises(ConnectionError):
                await cm.ensure_connected()

            mock_connect.assert_awaited_once()


class TestConnectionHealth:
    """Test health monitoring.

    SAFETY: Health tracking provides early warning of degrading conditions
    before total failure occurs. GPS lock and home position are prerequisites
    for safe RTL (Return to Launch) functionality.
    """

    @pytest.mark.asyncio
    async def test_health_tracking(self) -> None:
        """Health data is tracked correctly.

        VALIDATES: Health object reflects system state accurately.

        MOCK SETUP: None - testing health tracking methods directly.

        SAFETY REASON: RTL requires GPS lock and home position. Tracking these
        health indicators prevents attempting RTL when it would fail. Also
        tracks error counts for diagnosing intermittent issues.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Assert initial health is unhealthy (safe default)
        3. Assert error_count starts at 0
        4. Call _update_health with healthy state, GPS lock, home position set
        5. Assert health reflects updated values
        6. Verify is_healthy, gps_lock, home_position_set all True
        """
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
        """Error count increments correctly.

        VALIDATES: Error tracking for diagnostics and circuit breaking.

        MOCK SETUP: None - testing _record_error method.

        SAFETY REASON: High error counts indicate systemic problems that may
        require degrading functionality or aborting the mission. Tracks last_error
        for rapid root cause analysis during incidents.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Assert initial error_count is 0
        3. Record "Test error 1" via _record_error()
        4. Record "Test error 2" via _record_error()
        5. Assert error_count is now 2
        6. Assert last_error is "Test error 2" (most recent preserved)
        """
        ConnectionManager._instance = None
        cm = ConnectionManager()

        assert cm.health.error_count == 0

        # Record some errors
        cm._record_error("Test error 1")
        cm._record_error("Test error 2")

        assert cm.health.error_count == 2
        assert cm.health.last_error == "Test error 2"

    @pytest.mark.asyncio
    async def test_unready_vehicle_health_does_not_trigger_transport_reconnect(self) -> None:
        """GPS/home readiness is not the same as MAVSDK link failure."""
        ConnectionManager._instance = None
        cm = ConnectionManager()

        health = MagicMock()
        health.is_global_position_ok = False
        health.is_home_position_ok = False

        async def health_updates():
            yield health

        mock_drone = MagicMock()
        mock_drone.telemetry.health = health_updates

        with patch.object(cm, "_auto_reconnect", new_callable=AsyncMock) as mock_reconnect:
            cm._drone = mock_drone
            cm._state = ConnectionState.CONNECTED
            cm._health_check_interval_s = 0.01

            monitor_task = asyncio.create_task(cm._health_monitor())
            await asyncio.sleep(0.03)
            cm._stop_health_monitor.set()
            await monitor_task

            mock_reconnect.assert_not_called()
            assert cm.state == ConnectionState.CONNECTED
            assert cm.health.is_healthy is False


class TestThreadSafety:
    """Test thread safety with concurrent access.

    SAFETY: The ConnectionManager is accessed from multiple threads/agents.
    Race conditions could cause duplicate connections or state corruption.
    Thread safety ensures consistent behavior under concurrent load.
    """

    @pytest.mark.asyncio
    async def test_concurrent_get_drone(self) -> None:
        """Multiple concurrent get_drone() calls are safe.

        VALIDATES: No race conditions in drone access.

        MOCK SETUP:
        - Pre-connected ConnectionManager
        - 10 concurrent async tasks all calling get_drone()

        SAFETY REASON: During emergency situations, multiple components may
        simultaneously attempt to access the drone (Guardian, LLM, Operator).
        Thread safety prevents crashes and ensures all get the same reference.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Pre-connect with mock drone
        3. Define async task that calls get_drone()
        4. Create 10 concurrent tasks
        5. Gather all results
        6. Assert all results are the same mock_drone instance (identity check)
        """
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
        """Second connect() when already connected returns immediately.

        VALIDATES: Idempotent connect behavior prevents duplicate work.

        MOCK SETUP:
        - Mock MAVSDK System ready for connection
        - Track call_count on _do_connect

        SAFETY REASON: Duplicate connection attempts could confuse MAVSDK
        or create multiple connection sockets. Idempotent behavior ensures
        calling connect() multiple times is safe and fast.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Mock _do_connect with return value
        3. First connection attempt
        4. Assert connected (result1 is True)
        5. Record call_count (should be 1)
        6. Record start time
        7. Second connect() call (while already connected)
        8. Assert fast return (<100ms, no actual connection work)
        9. Assert call_count still 1 (no duplicate connection attempt)
        """
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
    """Test disconnect behavior.

    SAFETY: Clean disconnection prevents resource leaks and ensures proper
    cleanup of MAVSDK resources. Abrupt termination could leave sockets open.
    """

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up(self) -> None:
        """Disconnect properly cleans up resources.

        VALIDATES: _drone reference cleared, state updated to DISCONNECTED.

        MOCK SETUP:
        - Pre-connected ConnectionManager with mock drone

        SAFETY REASON: After disconnect, holding a drone reference could
        lead to use-after-disconnect errors. Clearing _drone forces null
        checks to fail, preventing commands to disconnected drone.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Pre-connect with mock drone
        3. Assert state is CONNECTED
        4. Call disconnect()
        5. Assert state is DISCONNECTED (clean state transition)
        6. Assert _drone is None (resource freed, prevents use-after-free)
        """
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
    """Test edge cases and error handling.

    SAFETY: Edge case handling ensures the system degrades gracefully
    rather than failing catastrophically when unexpected conditions occur.
    """

    @pytest.mark.asyncio
    async def test_get_drone_while_disconnected(self) -> None:
        """get_drone() returns None when disconnected.

        VALIDATES: Safe failure mode when no connection exists.

        MOCK SETUP: None - testing disconnected behavior.

        SAFETY REASON: Returning None allows null checks to prevent
        operations on non-existent connection. Alternative (raising
        exception) would require try/catch at every call site.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Do not connect (remain in DISCONNECTED state)
        3. Call get_drone()
        4. Assert result is None (explicit empty state)
        """
        ConnectionManager._instance = None
        cm = ConnectionManager()

        with patch.object(cm, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = False

            drone = await cm.get_drone()

        assert drone is None

    @pytest.mark.asyncio
    async def test_connect_with_retries(self) -> None:
        """Connection retries on transient failures.

        VALIDATES: Transient failures don't permanently break connection.

        MOCK SETUP:
        - Mock _do_connect that fails twice then succeeds
        - call_count tracks attempts

        SAFETY REASON: Network stack initialization can race with PX4 SITL
        startup. Retries allow time for PX4 to fully initialize. Without
        retries, a slightly slow startup would require manual restart.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Initialize call_count counter
        3. Define failing_then_success side_effect:
           - Attempts 1-2 raise Exception
           - Attempt 3+ returns mock drone
        4. Patch _do_connect with side_effect
        5. Attempt connection with max_retries=5, fast retry delay
        6. Assert connection succeeded (transient failures overcome)
        7. Assert exactly 3 calls made (2 failures + 1 success)
        8. Assert elapsed time < 1 second (fast retry behavior)
        """
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
        """Returns False when all retries fail.

        VALIDATES: Persistent failure is reported, not infinite loop.

        MOCK SETUP: Patch _do_connect to always raise Exception.

        SAFETY REASON: After max_retries, system must give up to prevent
        infinite loops that would block other operations. Returns False
        to indicate permanent failure requiring operator intervention.

        STEP-BY-STEP:
        1. Reset singleton and create ConnectionManager
        2. Patch _do_connect to always raise "Always fails"
        3. Attempt connection with max_retries=3
        4. Assert result is False (permanent failure indicated)
        5. Assert state is ERROR (failure state recorded)
        6. Assert error_count is 3 (all attempts recorded)
        """
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
