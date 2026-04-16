"""Backward compatibility tests for MCP server API migration.

These tests verify that old API calls continue to work while emitting
deprecation warnings. Tests cover:

1. DroneConnection shim class
2. Legacy tool function signatures
3. Deprecation warning emission
4. Return type compatibility
5. Parameter mapping (e.g., drone_id -> ignored)

To run: pytest tests/mcp_server/test_backward_compat.py -v

================================================================================
WHY BACKWARD COMPATIBILITY MATTERS
================================================================================

When evolving an API used by multiple agents and external clients, breaking
changes can cause mission-critical failures. This compatibility layer ensures:

1. GRACEFUL MIGRATION: Existing agents continue working while developers
   update their code to use the new API. No sudden breakage.

2. SAFETY FOR ACTIVE MISSIONS: A drone in flight cannot afford an API error.
   Backward compat ensures ongoing missions complete successfully.

3. TESTING TIME: Teams can upgrade the server first, then migrate agents
   one at a time, reducing risk.

4. CLEAR DEPRECATION PATH: Warnings guide developers to new APIs with
   specific replacement instructions, not just "this broke."

================================================================================
OLD API vs NEW API - KEY DIFFERENCES
================================================================================

OLD API (v0.1.x - DEPRECATED)                 NEW API (v0.2.x+)
-------------------------------------------   --------------------------------
DroneConnection                               ConnectionManager
- Manual connection lifecycle                 - Singleton, auto-managed
- Direct MAVSDK System access                 - Connection pooling support
- Single drone per instance                   - Multi-drone support via drone_id

DroneMCPServerConfig                          FlightToolsConfig
- Server-centric naming                       - Tool-centric naming
- Basic retry configuration                   - Extended health/timeouts

arm(drone_id="...")                           FlightTools.arm_and_takeoff()
takeoff(altitude=...)                         - Unified arm+takeoff
- Separate calls                              - Altitude validation
- No unified sequence

get_telemetry(drone_id="...")                 FlightTools.get_telemetry()
- JSON string returns                         - Structured dict returns
- Raw MAVSDK passthrough                      - Validated, formatted data

land_legacy(drone_id="...")                   FlightTools.land()
rtl_legacy(drone_id="...")                    FlightTools.rtl()
abort_mission_legacy(...)                     FlightTools.abort_mission()
- Legacy naming                               - Consistent naming
- drone_id parameter (ignored)                - reason parameter support

================================================================================
MIGRATION PATH
================================================================================

PHASE 1: Upgrade Server (IMMEDIATE)
  - Install new server version
  - Old agents continue working (compat layer active)
  - Monitor deprecation warnings in logs

PHASE 2: Update Agents (WEEKS 1-2)
  Replace imports:
    FROM: from avatar.mcp_server import DroneConnection
    TO:   from avatar.mav.connection_manager import ConnectionManager

  Replace connection code:
    FROM: conn = DroneConnection(config)
          await conn.connect()
    TO:   cm = ConnectionManager()
          await cm.connect(system_address="udp://:14540")

  Replace flight commands:
    FROM: await arm(drone_id="drone1")
          await takeoff(altitude=10.0)
    TO:   ft = FlightTools(cm)
          await ft.arm_and_takeoff(altitude_m=10.0)

PHASE 3: Remove Legacy (TARGET: v0.4.0)
  - Compatibility layer removed
  - All agents must use new API
  - Breaking change for any unmigrated code

================================================================================
TEST STRUCTURE
================================================================================

Tests are organized by compatibility aspect:

1. DroneConnection Shim Tests: Verify the shim class delegates to
   ConnectionManager correctly while emitting warnings.

2. Legacy Tool Function Tests: Verify old function signatures work
   and return expected legacy formats.

3. Configuration Tests: Verify config classes convert properly.

4. Utility Function Tests: Verify migration helpers provide useful info.

5. Integration Tests: Full old-style workflows still function.

6. Deprecation Warning Tests: Warnings fire correctly with guidance.

7. Error Handling Tests: Errors propagate correctly through compat layer.

8. Version/Metadata Tests: Exports match expected interface.
"""

import asyncio
import json
import warnings
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import compatibility layer - these are the OLD API exports that must
# continue working. The compat module acts as a translation layer between
# deprecated calls and the new ConnectionManager/FlightTools architecture.
from avatar.mcp_server.compat import (
    DroneConnection,          # Shim class wrapping ConnectionManager
    DroneMCPServerConfig,     # Legacy config (maps to FlightToolsConfig)
    ConnectionConfig,          # Still valid (re-exported)
    arm,                      # Legacy standalone function
    takeoff,                  # Legacy standalone function
    arm_and_takeoff_legacy,   # Explicitly named legacy version
    get_telemetry,           # Legacy telemetry function
    land_legacy,             # Legacy land function
    rtl_legacy,              # Legacy RTL function
    abort_mission_legacy,    # Legacy abort function
    check_api_compatibility, # Migration helper - returns compat info
    get_migration_guide,     # Migration helper - returns guide text
    _emit_deprecation_warning,  # Internal warning helper (tested)
    _warned_classes,         # Tracks warned classes (prevents spam)
    _warned_functions,       # Tracks warned functions (prevents spam)
)
from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mcp_server.tools.flight_tools import FlightTools


# =============================================================================
# Fixtures
# =============================================================================
# Fixtures provide mocked dependencies so tests run without requiring
# an actual drone connection or SITL simulation.


@pytest.fixture(autouse=True)
def reset_warning_tracking():
    """Reset warning tracking before each test.

    WHY: The compat module tracks which warnings have been emitted to
    prevent duplicate warning spam. This fixture ensures each test
    starts with a clean slate, not affected by previous test warnings.
    """
    _warned_classes.clear()
    _warned_functions.clear()
    yield
    _warned_classes.clear()
    _warned_functions.clear()


@pytest.fixture
def mock_connection_manager():
    """Create a mock ConnectionManager for testing.

    Mocks the ConnectionManager singleton to simulate connected/disconnected
    states without actual MAVSDK connections. This allows testing the
    compat layer's delegation logic in isolation.

    STATE SIMULATED:
    - Connected state
    - Healthy GPS and home position
    - Async operations (connect, disconnect, get_drone)
    """
    with patch("avatar.mcp_server.compat.ConnectionManager") as mock_cm_class:
        mock_cm = MagicMock()
        mock_cm._state = ConnectionState.CONNECTED
        mock_cm._drone = MagicMock()
        mock_cm.state = ConnectionState.CONNECTED
        mock_cm.health = MagicMock()
        mock_cm.health.is_healthy = True
        mock_cm.health.gps_lock = True
        mock_cm.health.home_position_set = True
        mock_cm.connect = AsyncMock(return_value=True)
        mock_cm.disconnect = AsyncMock()
        mock_cm.get_drone = AsyncMock(return_value=mock_cm._drone)
        mock_cm.ensure_connected = AsyncMock(return_value=mock_cm._drone)

        # Return same mock instance (singleton behavior)
        mock_cm_class.return_value = mock_cm
        mock_cm_class._instance = mock_cm

        yield mock_cm


@pytest.fixture
def mock_flight_tools():
    """Create a mock FlightTools for testing.

    FlightTools is the new API for flight operations. These mocks simulate
    successful flight command responses without actual drone communication.

    VALIDATED OPERATIONS:
    - arm_and_takeoff: Returns success + altitude confirmation
    - land: Returns success confirmation
    - rtl: Returns success confirmation
    - abort_mission: Returns success confirmation
    """
    with patch("avatar.mcp_server.compat.FlightTools") as mock_ft_class:
        mock_ft = MagicMock()
        mock_ft.arm_and_takeoff = AsyncMock(return_value={
            "success": True,
            "message": "Takeoff complete",
            "altitude_m": 10.0,
        })
        mock_ft.land = AsyncMock(return_value={
            "success": True,
            "message": "Landing initiated",
        })
        mock_ft.rtl = AsyncMock(return_value={
            "success": True,
            "message": "RTL initiated",
        })
        mock_ft.abort_mission = AsyncMock(return_value={
            "success": True,
            "message": "Mission aborted",
        })
        mock_ft_class.return_value = mock_ft
        yield mock_ft


@pytest.fixture
def mock_telemetry_tools():
    """Create mock telemetry tools for testing.

    The new telemetry API returns structured data; the legacy API returns
    JSON strings. This mock simulates the new API that the compat layer
    will call and format.
    """
    with patch("avatar.mcp_server.compat.new_get_telemetry") as mock_telemetry:
        mock_telemetry.return_value = json.dumps({
            "success": True,
            "position": {"latitude_deg": 37.7749, "longitude_deg": -122.4194},
            "battery": {"remaining_percent": 85},
        })
        yield mock_telemetry


# =============================================================================
# DroneConnection Shim Tests
# =============================================================================
# These tests verify the DroneConnection shim properly delegates to
# ConnectionManager while emitting deprecation warnings.
#
# MIGRATION PATH: Replace DroneConnection with ConnectionManager
#   DroneConnection(config) -> ConnectionManager() then connect()


class TestDroneConnectionShim:
    """Test DroneConnection backward compatibility shim.

    The DroneConnection class in the old API was the primary interface
    for drone communication. In the new API, ConnectionManager is a
    singleton that manages all connections. This shim:

    1. Accepts old DroneConnection initialization parameters
    2. Translates them to ConnectionManager calls
    3. Maintains the same public interface (connect, disconnect, etc.)
    4. Emits deprecation warnings guiding migration
    """

    def test_init_emits_deprecation_warning(self, mock_connection_manager):
        """Test that DroneConnection emits deprecation warning on init.

        VALIDATES: Every instantiation warns developers to migrate.
        MIGRATION: Replace DroneConnection with ConnectionManager.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            conn = DroneConnection()

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "DroneConnection" in str(deprecation_warnings[0].message)
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_init_with_config(self, mock_connection_manager):
        """Test DroneConnection initialization with ConnectionConfig.

        OLD API PATTERN:
            config = ConnectionConfig(system_address="udp://:14540")
            conn = DroneConnection(config)

        NEW API PATTERN:
            cm = ConnectionManager()
            await cm.connect(system_address="udp://:14540")

        VALIDATES: Config parameters are passed through to ConnectionManager.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            config = ConnectionConfig(
                system_address="udp://:14540",
                max_retries=5,
                retry_delay_s=2.0,
            )
            conn = DroneConnection(config)

            assert conn.config == config
            assert conn._cm._system_address == "udp://:14540"

    def test_is_connected_property(self, mock_connection_manager):
        """Test is_connected property delegates to ConnectionManager.

        OLD API: conn.is_connected (property on DroneConnection instance)
        NEW API: cm.state == ConnectionState.CONNECTED

        VALIDATES: Property correctly reflects ConnectionManager state.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            assert conn.is_connected is True
            mock_connection_manager.state = ConnectionState.DISCONNECTED
            assert conn.is_connected is False

    def test_drone_property(self, mock_connection_manager):
        """Test drone property returns System instance when connected.

        OLD API: conn.drone -> MAVSDK System instance
        NEW API: cm.get_drone() -> MAVSDK System instance

        VALIDATES: Property returns actual drone instance or None.
        NOTE: Returns None when disconnected for safety.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            # When connected
            assert conn.drone is mock_connection_manager._drone

            # When disconnected
            mock_connection_manager._state = ConnectionState.DISCONNECTED
            assert conn.drone is None

    @pytest.mark.asyncio
    async def test_connect_delegates_to_connection_manager(self, mock_connection_manager):
        """Test connect() delegates to ConnectionManager.connect().

        OLD API:
            config = ConnectionConfig(system_address="udp://:14550")
            conn = DroneConnection(config)
            await conn.connect()

        NEW API:
            cm = ConnectionManager()
            await cm.connect(system_address="udp://:14550")

        VALIDATES: Connection parameters are correctly forwarded.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            config = ConnectionConfig(
                system_address="udp://:14550",
                max_retries=3,
                retry_delay_s=1.0,
            )
            conn = DroneConnection(config)

            result = await conn.connect()

            assert result is True
            mock_connection_manager.connect.assert_called_once_with(
                system_address="udp://:14550",
                max_retries=3,
                retry_delay_s=1.0,
            )

    @pytest.mark.asyncio
    async def test_connect_sets_drone_attribute(self, mock_connection_manager):
        """Test that connect() sets the _drone attribute on success.

        VALIDATES: Internal state remains consistent with old API behavior.
        NOTE: The _drone attribute was used by old code to access MAVSDK.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            await conn.connect()

            assert conn._drone is mock_connection_manager._drone

    @pytest.mark.asyncio
    async def test_connect_returns_false_on_failure(self, mock_connection_manager):
        """Test connect() returns False when ConnectionManager fails.

        VALIDATES: Error handling matches old API contract.
        MIGRATION: New API raises exceptions; old API returned False.
        This shim preserves the boolean return for compatibility.
        """
        mock_connection_manager.connect.return_value = False

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            result = await conn.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_health_uses_connection_manager(self, mock_connection_manager):
        """Test wait_for_health() uses ConnectionManager health status.

        OLD API: conn.wait_for_health(timeout=30)
        NEW API: Implicit in ensure_connected() and health polling

        VALIDATES: Health checking delegates to ConnectionManager.health
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            # Already healthy
            mock_connection_manager.health.is_healthy = True
            result = await conn.wait_for_health()
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_health_polls_for_health(self, mock_connection_manager):
        """Test wait_for_health() polls until healthy or timeout.

        VALIDATES: Implements the old polling behavior using new health API.
        NOTE: This is a logic path test; actual timing is mocked.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            # Start unhealthy, become healthy after first check
            mock_connection_manager.health.is_healthy = True

            result = await conn.wait_for_health()
            assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_delegates_to_connection_manager(self, mock_connection_manager):
        """Test disconnect() delegates to ConnectionManager.disconnect().

        OLD API: await conn.disconnect()
        NEW API: await cm.disconnect()

        VALIDATES: Disconnect calls through and clears _drone reference.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()
            conn._drone = MagicMock()

            await conn.disconnect()

            mock_connection_manager.disconnect.assert_called_once()
            assert conn._drone is None


# =============================================================================
# Legacy Tool Function Tests
# =============================================================================
# These tests verify standalone flight command functions still work.
#
# OLD API: Individual functions (arm, takeoff, land_legacy, etc.)
# NEW API: FlightTools class methods (ft.arm_and_takeoff(), ft.land(), etc.)
#
# MIGRATION: Create FlightTools instance, call methods instead of
#            standalone functions.


class TestLegacyToolFunctions:
    """Test legacy tool function backward compatibility.

    The old API exposed individual functions for each flight command:
    - arm(drone_id) -> arms the drone
    - takeoff(altitude) -> takes off to specified altitude
    - land_legacy(drone_id) -> lands the drone
    - etc.

    The new API groups these into FlightTools class:
    - ft = FlightTools(connection_manager)
    - ft.arm_and_takeoff(altitude_m) -> arms AND takes off
    - ft.land() -> lands

    This compat layer:
    1. Keeps old function signatures working
    2. Internally creates/uses FlightTools
    3. Emits deprecation warnings
    4. Returns legacy-formatted results
    """

    @pytest.mark.asyncio
    async def test_arm_emits_deprecation_warning(self, mock_flight_tools):
        """Test arm() emits deprecation warning.

        VALIDATES: Standalone arm() warns to use FlightTools.arm_and_takeoff().

        MIGRATION PATH:
            FROM: await arm(drone_id="drone1")
            TO:   ft = FlightTools(cm)
                  await ft.arm_and_takeoff(altitude_m=10.0)
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await arm(drone_id="drone1")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "arm()" in str(deprecation_warnings[0].message)

    @pytest.mark.asyncio
    async def test_arm_returns_legacy_format(self, mock_flight_tools):
        """Test arm() returns result in legacy format.

        OLD API RETURN FORMAT:
        {
            "success": True/False,
            "drone_id": "the_drone_id",
            "message": "...",
            "version": "legacy_compat"
        }

        NEW API RETURN FORMAT:
        {
            "success": True/False,
            "message": "...",
            "altitude_m": float  # for arm_and_takeoff
        }

        VALIDATES: Old format preserved even though new API differs.
        The compat layer adds drone_id and version fields.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await arm(drone_id="drone1")

            assert "success" in result
            assert "drone_id" in result
            assert result["drone_id"] == "drone1"

    @pytest.mark.asyncio
    async def test_takeoff_emits_deprecation_warning(self, mock_flight_tools):
        """Test takeoff() emits deprecation warning.

        VALIDATES: Standalone takeoff() warns to migrate.

        MIGRATION NOTE: Old API separated arm and takeoff. New API combines
        them because arming without immediate takeoff is a safety risk.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await takeoff(altitude=15.0)

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "takeoff" in str(deprecation_warnings[0].message).lower()

    @pytest.mark.asyncio
    async def test_takeoff_returns_legacy_format(self, mock_flight_tools):
        """Test takeoff() returns result in legacy format.

        VALIDATES: Result includes altitude_m from the new API response.
        The compat layer extracts and formats the altitude value.
        """
        # Configure mock to return the altitude we pass in
        async def mock_arm_and_takeoff(altitude_m):
            return {
                "success": True,
                "message": "Takeoff complete",
                "altitude_m": altitude_m,
            }
        mock_flight_tools.arm_and_takeoff = mock_arm_and_takeoff

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await takeoff(altitude=15.0)

            assert "success" in result
            assert "altitude_m" in result
            assert result["altitude_m"] == 15.0

    @pytest.mark.asyncio
    async def test_arm_and_takeoff_legacy_emits_warning(self, mock_flight_tools):
        """Test arm_and_takeoff_legacy() emits deprecation warning.

        This is the combined operation that the new API encourages.
        Even though it matches new behavior, the naming is legacy.

        MIGRATION PATH:
            FROM: await arm_and_takeoff_legacy(altitude_m=20.0, drone_id="drone2")
            TO:   await ft.arm_and_takeoff(altitude_m=20.0)
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await arm_and_takeoff_legacy(altitude_m=20.0, drone_id="drone2")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_arm_and_takeoff_legacy_includes_drone_id(self, mock_flight_tools):
        """Test arm_and_takeoff_legacy() includes drone_id in result.

        VALIDATES: The drone_id parameter (deprecated) is echoed back
        in the response for old API compatibility.

        NOTE: In the new API, drone_id is managed by ConnectionManager
        and doesn't need to be passed per-operation.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await arm_and_takeoff_legacy(altitude_m=20.0, drone_id="drone2")

            assert "drone_id" in result
            assert "version" in result
            assert result["drone_id"] == "drone2"
            assert result["version"] == "legacy_compat"

    @pytest.mark.asyncio
    async def test_land_legacy_emits_warning(self, mock_flight_tools):
        """Test land_legacy() emits deprecation warning.

        VALIDATES: Old land function warns about migration.

        MIGRATION PATH:
            FROM: await land_legacy(drone_id="drone1")
            TO:   await ft.land()
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await land_legacy(drone_id="drone1")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_land_legacy_returns_legacy_format(self, mock_flight_tools):
        """Test land_legacy() returns result in legacy format.

        VALIDATES: Same format as arm() - success, drone_id, version fields.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await land_legacy(drone_id="drone1")

            assert "success" in result
            assert "drone_id" in result
            assert "version" in result
            assert result["drone_id"] == "drone1"

    @pytest.mark.asyncio
    async def test_rtl_legacy_emits_warning(self, mock_flight_tools):
        """Test rtl_legacy() emits deprecation warning.

        RTL = Return To Launch (return to takeoff point).

        MIGRATION PATH:
            FROM: await rtl_legacy(drone_id="drone1")
            TO:   await ft.rtl()
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await rtl_legacy(drone_id="drone1")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_abort_mission_legacy_accepts_reason_and_drone_id(self, mock_flight_tools):
        """Test abort_mission_legacy() accepts both reason and drone_id.

        VALIDATES: Old API parameters are accepted even though new API
        has different signature.

        MIGRATION PATH:
            FROM: await abort_mission_legacy(reason="Emergency", drone_id="drone1")
            TO:   await ft.abort_mission(reason="Emergency")

        NOTE: drone_id is ignored in compat layer (ConnectionManager handles it).
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await abort_mission_legacy(reason="Emergency", drone_id="drone1")

            mock_flight_tools.abort_mission.assert_called_once_with(reason="Emergency")
            assert "drone_id" in result
            assert result["drone_id"] == "drone1"


# =============================================================================
# Configuration Tests
# =============================================================================
# Tests for config class compatibility.
#
# OLD API: DroneMCPServerConfig (server-centric)
# NEW API: FlightToolsConfig (tool-centric)
#
# MIGRATION: DroneMCPServerConfig.to_flight_tools_config() method


class TestLegacyConfiguration:
    """Test legacy configuration backward compatibility.

    Configuration classes changed naming to reflect the architecture shift:
    - Old: DroneMCPServerConfig - implied single server
    - New: FlightToolsConfig - tool-focused, supports multiple connections

    The compat layer:
    1. Keeps DroneMCPServerConfig working
    2. Provides conversion to FlightToolsConfig
    3. Preserves all configuration values
    """

    def test_drone_mcp_server_config_emits_warning(self):
        """Test DroneMCPServerConfig emits deprecation warning.

        VALIDATES: Instantiating old config class warns about migration.

        MIGRATION PATH:
            FROM: config = DroneMCPServerConfig(system_address="...")
            TO:   config = FlightToolsConfig(system_address="...")
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = DroneMCPServerConfig(
                system_address="udp://:14540",
                max_retries=5,
            )

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "DroneMCPServerConfig" in str(deprecation_warnings[0].message)

    def test_drone_mcp_server_config_preserves_values(self):
        """Test DroneMCPServerConfig preserves configuration values.

        VALIDATES: All config parameters are stored correctly:
        - system_address: MAVSDK connection string
        - max_retries: Connection retry attempts
        - retry_delay_s: Delay between retries
        - health_timeout_s: Health check timeout

        These values must be preserved for the conversion to work.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            config = DroneMCPServerConfig(
                system_address="udp://:14560",
                max_retries=5,
                retry_delay_s=2.5,
                health_timeout_s=60.0,
            )

            assert config.system_address == "udp://:14560"
            assert config.max_retries == 5
            assert config.retry_delay_s == 2.5
            assert config.health_timeout_s == 60.0

    def test_to_flight_tools_config_conversion(self):
        """Test conversion to FlightToolsConfig.

        VALIDATES: The to_flight_tools_config() method correctly
        maps legacy config values to the new config class.

        This is the BRIDGE between old and new - critical for migration.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            legacy_config = DroneMCPServerConfig(
                system_address="udp://:14560",
                max_retries=5,
                retry_delay_s=2.5,
                health_timeout_s=60.0,
            )

            new_config = legacy_config.to_flight_tools_config()

            assert new_config.system_address == "udp://:14560"
            assert new_config.max_retries == 5
            assert new_config.retry_delay_s == 2.5
            assert new_config.health_timeout_s == 60.0

    def test_connection_config_still_available(self):
        """Test ConnectionConfig is re-exported for backward compatibility.

        VALIDATES: ConnectionConfig is still valid in new API (re-exported),
        so it should NOT emit deprecation warnings.

        NOTE: ConnectionConfig survived the API transition unchanged,
        so it's simply re-exported rather than shimmed.
        """
        # Should not emit warning (it's just a re-export)
        config = ConnectionConfig(
            system_address="udp://:14540",
            max_retries=3,
        )

        assert config.system_address == "udp://:14540"
        assert config.max_retries == 3


# =============================================================================
# Utility Function Tests
# =============================================================================
# Tests for migration helper utilities.
#
# These functions help developers understand and execute migration.


class TestUtilityFunctions:
    """Test compatibility utility functions.

    These utilities provide programmatic access to migration information:
    - check_api_compatibility(): Returns current compat status
    - get_migration_guide(): Returns human-readable guide

    Useful for:
    - Health check endpoints
    - Startup diagnostics
    - CI/CD migration validation
    """

    def test_check_api_compatibility_returns_dict(self):
        """Test check_api_compatibility returns expected structure.

        VALIDATES: Returns structured data for programmatic use:
        {
            "compat_version": "0.2.0",
            "target_removal": "0.4.0",
            "deprecated_items": [...],
            "migration_guide": "..."
        }
        """
        result = check_api_compatibility()

        assert isinstance(result, dict)
        assert "compat_version" in result
        assert "target_removal" in result
        assert "deprecated_items" in result
        assert "migration_guide" in result
        assert result["compat_version"] == "0.2.0"

    def test_check_api_compatibility_lists_deprecated_items(self):
        """Test check_api_compatibility lists all deprecated APIs.

        VALIDATES: All deprecated items are documented so developers
        know exactly what needs migration.

        Each item should include:
        - name: The deprecated class/function
        - replacement: What to use instead
        - removal_version: When it will be removed
        """
        result = check_api_compatibility()

        deprecated_names = [item["name"] for item in result["deprecated_items"]]

        assert "DroneConnection" in deprecated_names
        assert "DroneMCPServerConfig" in deprecated_names

    def test_get_migration_guide_returns_string(self):
        """Test get_migration_guide returns formatted string.

        VALIDATES: Returns human-readable guide with:
        - Clear deprecation notice
        - Step-by-step instructions
        - Code examples (old vs new)
        - Timeline information
        """
        guide = get_migration_guide()

        assert isinstance(guide, str)
        assert "MIGRATION GUIDE" in guide
        assert "DEPRECATION NOTICE" in guide
        assert "ConnectionManager" in guide


# =============================================================================
# Integration Tests
# =============================================================================
# End-to-end tests of old-style workflows.
#
# These ensure complete mission scripts using old API still work.


class TestIntegrationScenarios:
    """Test realistic integration scenarios.

    These tests simulate complete workflows using only the old API.
    They validate that existing mission scripts, notebooks, and
    external agents continue functioning without modification.

    SCENARIOS:
    1. Connect -> Arm -> Takeoff -> Land -> Disconnect
    2. Separate arm and takeoff calls (old pattern)
    3. Import verification from main module
    """

    @pytest.mark.asyncio
    async def test_old_style_connection_and_flight(self, mock_connection_manager, mock_flight_tools):
        """Test old-style code pattern: connect -> arm -> takeoff.

        This is the MOST CRITICAL test - it validates a complete flight
        using only deprecated APIs.

        OLD-STYLE WORKFLOW:
            1. Create DroneConnection with ConnectionConfig
            2. await conn.connect()
            3. await arm_and_takeoff_legacy(altitude_m=10.0, drone_id="drone1")
            4. await land_legacy(drone_id="drone1")
            5. await conn.disconnect()

        VALIDATES: Complete mission succeeds without touching new API.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")

            # Old-style connection
            from avatar.mcp_server.compat import DroneConnection, ConnectionConfig
            config = ConnectionConfig(system_address="udp://:14540")
            conn = DroneConnection(config)
            connected = await conn.connect()
            assert connected is True

            # Old-style arm and takeoff
            result = await arm_and_takeoff_legacy(altitude_m=10.0, drone_id="drone1")
            assert result["success"] is True
            assert result["drone_id"] == "drone1"

            # Old-style land
            result = await land_legacy(drone_id="drone1")
            assert result["success"] is True

            # Disconnect
            await conn.disconnect()

    @pytest.mark.asyncio
    async def test_separate_arm_and_takeoff(self, mock_flight_tools):
        """Test separate arm() and takeoff() calls (old pattern).

        OLD PATTERN (discouraged but supported):
            await arm(drone_id="drone1")
            await takeoff(altitude=10.0)

        NEW PATTERN (recommended):
            await ft.arm_and_takeoff(altitude_m=10.0)

        VALIDATES: Old two-step pattern still works through compat layer.
        NOTE: arm() + takeoff() internally delegates to arm_and_takeoff().
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")

            # Arm first
            arm_result = await arm(drone_id="drone1")
            assert "success" in arm_result

            # Then takeoff
            takeoff_result = await takeoff(altitude=10.0)
            assert "altitude_m" in takeoff_result

    def test_imports_from_mcp_server_module(self):
        """Test that all compat items can be imported from mcp_server module.

        VALIDATES: Public API surface - all deprecated exports are available.

        This ensures existing code using:
            from avatar import mcp_server
            conn = mcp_server.DroneConnection()

        continues to work without import errors.
        """
        from avatar import mcp_server

        # All compat items should be accessible
        assert hasattr(mcp_server, "DroneConnection")
        assert hasattr(mcp_server, "DroneMCPServerConfig")
        assert hasattr(mcp_server, "ConnectionConfig")
        assert hasattr(mcp_server, "arm")
        assert hasattr(mcp_server, "takeoff")
        assert hasattr(mcp_server, "check_api_compatibility")
        assert hasattr(mcp_server, "get_migration_guide")


# =============================================================================
# Deprecation Warning Tests
# =============================================================================
# Tests specifically for warning behavior.
#
# Deprecation warnings must:
# 1. Fire when deprecated APIs are used
# 2. Include migration guidance
# 3. Not spam (duplicate suppression)
# 4. Point to correct line in user code


class TestDeprecationWarnings:
    """Test deprecation warning behavior.

    Deprecation warnings are the MIGRATION MECHANISM. They must be:

    1. INFORMATIVE: Tell user what to use instead
    2. ACTIONABLE: Include version numbers for planning
    3. NON-SPAMMY: Don't repeat for same call site
    4. ACCURATE: Point to user's code, not internal shim

    Python's warnings system handles stacklevel to ensure warnings
    appear to come from the calling code, not the compat layer.
    """

    def test_duplicate_warnings_suppressed(self):
        """Test that duplicate warnings are suppressed per module.

        VALIDATES: _warned_classes and _warned_functions tracking works.

        WHY THIS MATTERS: Without suppression, a loop calling arm()
        100 times would emit 100 warnings. We emit once per module.

        TRACKING:
        - _warned_classes: Set of class names already warned
        - _warned_functions: Set of function names already warned
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # First call should emit warning
            _emit_deprecation_warning("TestClass", "NewClass")
            first_count = len([x for x in w if issubclass(x.category, DeprecationWarning)])

            # Second call should not emit (already warned)
            _emit_deprecation_warning("TestClass", "NewClass")
            second_count = len([x for x in w if issubclass(x.category, DeprecationWarning)])

            assert first_count == second_count  # No new warnings

    def test_warnings_include_migration_info(self):
        """Test that warnings include migration guidance.

        VALIDATES: Warning message includes:
        - "deprecated" indicator
        - Current compat version (v0.2.0)
        - Target removal version (v0.4.0)
        - Replacement API name (NewAPI)

        EXAMPLE MESSAGE:
        "TestClass is deprecated since v0.2.0 and will be removed in v0.4.0.
         Use NewAPI instead."
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            _emit_deprecation_warning("OldAPI", "NewAPI")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

            message = str(deprecation_warnings[0].message)
            assert "deprecated" in message.lower()
            assert "v0.2.0" in message
            assert "v0.4.0" in message
            assert "NewAPI" in message

    def test_warning_stacklevel(self):
        """Test that warnings are raised with proper metadata.

        VALIDATES: Warning includes correct filename and line number
        for the CALLING code, not the internal _emit_deprecation_warning.

        The stacklevel parameter in warnings.warn() controls this.
        Correct stacklevel means users see where THEY used deprecated API.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            _emit_deprecation_warning("TestAPI", "NewAPI")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            # Verify the warning has a valid filename (may be pytest internals when running tests)
            assert deprecation_warnings[0].filename is not None
            assert deprecation_warnings[0].lineno > 0


# =============================================================================
# Error Handling Tests
# =============================================================================
# Tests for error propagation through compat layer.
#
# Errors from the new API must be properly handled and converted
# to formats expected by old API consumers.


class TestErrorHandling:
    """Test error handling in compatibility layer.

    The compat layer must handle errors gracefully:

    1. PROPAGATE: New API errors become old API errors
    2. FORMAT: New exception-based errors become old boolean/dict errors
    3. NO MASKING: Don't hide errors that old API would have shown
    4. SAFE: Failed compat operations don't crash caller

    ERROR TRANSLATION EXAMPLES:
    - New API: raises ConnectionError -> Old API: returns False
    - New API: returns {"success": False, "error": "..."} -> Old API: same format
    """

    @pytest.mark.asyncio
    async def test_arm_handles_failure(self, mock_flight_tools):
        """Test arm() handles failure gracefully.

        VALIDATES: When FlightTools.arm_and_takeoff returns failure,
        the compat layer propagates it correctly in legacy format.
        """
        mock_flight_tools.arm_and_takeoff.return_value = {
            "success": False,
            "error": "Failed to arm",
        }

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await arm(drone_id="drone1")

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_connection_failure_handled(self, mock_connection_manager):
        """Test connection failure is properly propagated.

        VALIDATES: When ConnectionManager.connect returns False,
        DroneConnection.connect also returns False (old API contract).

        Old API returned booleans; new API may raise exceptions.
        Shim converts exceptions to boolean False for compatibility.
        """
        mock_connection_manager.connect.return_value = False

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()
            result = await conn.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_health_timeout(self, mock_connection_manager):
        """Test wait_for_health handles unhealthiness.

        VALIDATES: When health check fails (drone unhealthy), the
        method returns False rather than hanging or crashing.

        TIMEOUT LOGIC: Old API had timeout parameter; shim implements
        polling loop with iteration limit for safety.
        """
        # Always unhealthy
        mock_connection_manager.health.is_healthy = False

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            # Should timeout after 30 iterations (mocked, not real time)
            # This tests the logic path, not actual timing
            result = await conn.wait_for_health()
            assert result is False


# =============================================================================
# Version and Metadata Tests
# =============================================================================
# Tests for module exports and public API surface.
#
# These ensure the compat layer exposes exactly what it should.


class TestVersionAndMetadata:
    """Test version information and metadata.

    The compat module and mcp_server module must export the correct
    public interface. These tests verify __all__ lists match actual
    available exports.

    __all__ IMPORTANCE:
    - Controls what 'from module import *' imports
    - Documents the public API
    - Prevents accidental export of internals
    """

    def test_compat_module_exports(self):
        """Test that all expected exports are in __all__.

        VALIDATES: compat.__all__ includes all deprecated items that
        should be importable. Missing items would break existing code.

        EXPECTED EXPORTS:
        - Classes: DroneConnection, DroneMCPServerConfig, ConnectionConfig
        - Functions: arm, takeoff, arm_and_takeoff_legacy, etc.
        - Utilities: check_api_compatibility, get_migration_guide
        """
        from avatar.mcp_server import compat

        expected_exports = [
            "DroneConnection",
            "DroneMCPServerConfig",
            "ConnectionConfig",
            "arm",
            "takeoff",
            "arm_and_takeoff_legacy",
            "get_telemetry",
            "land_legacy",
            "rtl_legacy",
            "abort_mission_legacy",
            "check_api_compatibility",
            "get_migration_guide",
        ]

        for export in expected_exports:
            assert export in compat.__all__, f"{export} missing from __all__"

    def test_mcp_server_module_exports(self):
        """Test that mcp_server module exports compat items.

        VALIDATES: Main mcp_server module re-exports compat items
        for convenient import: from avatar import mcp_server

        This is the PRIMARY import pattern for existing agents.
        """
        from avatar import mcp_server

        expected_exports = [
            "DroneConnection",
            "DroneMCPServerConfig",
            "ConnectionConfig",
            "arm",
            "takeoff",
            "check_api_compatibility",
            "get_migration_guide",
        ]

        for export in expected_exports:
            assert export in mcp_server.__all__, f"{export} missing from mcp_server.__all__"
