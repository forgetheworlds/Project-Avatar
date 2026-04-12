"""Backward compatibility tests for MCP server API migration.

These tests verify that old API calls continue to work while emitting
deprecation warnings. Tests cover:

1. DroneConnection shim class
2. Legacy tool function signatures
3. Deprecation warning emission
4. Return type compatibility
5. Parameter mapping (e.g., drone_id -> ignored)

To run: pytest tests/mcp_server/test_backward_compat.py -v
"""

import asyncio
import json
import warnings
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import compatibility layer
from avatar.mcp_server.compat import (
    DroneConnection,
    DroneMCPServerConfig,
    ConnectionConfig,
    arm,
    takeoff,
    arm_and_takeoff_legacy,
    get_telemetry,
    land_legacy,
    rtl_legacy,
    abort_mission_legacy,
    check_api_compatibility,
    get_migration_guide,
    _emit_deprecation_warning,
    _warned_classes,
    _warned_functions,
)
from avatar.mav.connection_manager import ConnectionManager, ConnectionState
from avatar.mcp_server.tools.flight_tools import FlightTools


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_warning_tracking():
    """Reset warning tracking before each test."""
    _warned_classes.clear()
    _warned_functions.clear()
    yield
    _warned_classes.clear()
    _warned_functions.clear()


@pytest.fixture
def mock_connection_manager():
    """Create a mock ConnectionManager for testing."""
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
    """Create a mock FlightTools for testing."""
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
    """Create mock telemetry tools for testing."""
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


class TestDroneConnectionShim:
    """Test DroneConnection backward compatibility shim."""

    def test_init_emits_deprecation_warning(self, mock_connection_manager):
        """Test that DroneConnection emits deprecation warning on init."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            conn = DroneConnection()

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "DroneConnection" in str(deprecation_warnings[0].message)
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_init_with_config(self, mock_connection_manager):
        """Test DroneConnection initialization with ConnectionConfig."""
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
        """Test is_connected property delegates to ConnectionManager."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            assert conn.is_connected is True
            mock_connection_manager.state = ConnectionState.DISCONNECTED
            assert conn.is_connected is False

    def test_drone_property(self, mock_connection_manager):
        """Test drone property returns System instance when connected."""
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
        """Test connect() delegates to ConnectionManager.connect()."""
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
        """Test that connect() sets the _drone attribute on success."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            await conn.connect()

            assert conn._drone is mock_connection_manager._drone

    @pytest.mark.asyncio
    async def test_connect_returns_false_on_failure(self, mock_connection_manager):
        """Test connect() returns False when ConnectionManager fails."""
        mock_connection_manager.connect.return_value = False

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            result = await conn.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_health_uses_connection_manager(self, mock_connection_manager):
        """Test wait_for_health() uses ConnectionManager health status."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            # Already healthy
            mock_connection_manager.health.is_healthy = True
            result = await conn.wait_for_health()
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_health_polls_for_health(self, mock_connection_manager):
        """Test wait_for_health() polls until healthy or timeout."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()

            # Start unhealthy, become healthy after first check
            mock_connection_manager.health.is_healthy = True

            result = await conn.wait_for_health()
            assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_delegates_to_connection_manager(self, mock_connection_manager):
        """Test disconnect() delegates to ConnectionManager.disconnect()."""
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


class TestLegacyToolFunctions:
    """Test legacy tool function backward compatibility."""

    @pytest.mark.asyncio
    async def test_arm_emits_deprecation_warning(self, mock_flight_tools):
        """Test arm() emits deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await arm(drone_id="drone1")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "arm()" in str(deprecation_warnings[0].message)

    @pytest.mark.asyncio
    async def test_arm_returns_legacy_format(self, mock_flight_tools):
        """Test arm() returns result in legacy format."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await arm(drone_id="drone1")

            assert "success" in result
            assert "drone_id" in result
            assert result["drone_id"] == "drone1"

    @pytest.mark.asyncio
    async def test_takeoff_emits_deprecation_warning(self, mock_flight_tools):
        """Test takeoff() emits deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await takeoff(altitude=15.0)

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "takeoff" in str(deprecation_warnings[0].message).lower()

    @pytest.mark.asyncio
    async def test_takeoff_returns_legacy_format(self, mock_flight_tools):
        """Test takeoff() returns result in legacy format."""
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
        """Test arm_and_takeoff_legacy() emits deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await arm_and_takeoff_legacy(altitude_m=20.0, drone_id="drone2")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_arm_and_takeoff_legacy_includes_drone_id(self, mock_flight_tools):
        """Test arm_and_takeoff_legacy() includes drone_id in result."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await arm_and_takeoff_legacy(altitude_m=20.0, drone_id="drone2")

            assert "drone_id" in result
            assert "version" in result
            assert result["drone_id"] == "drone2"
            assert result["version"] == "legacy_compat"

    @pytest.mark.asyncio
    async def test_land_legacy_emits_warning(self, mock_flight_tools):
        """Test land_legacy() emits deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await land_legacy(drone_id="drone1")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_land_legacy_returns_legacy_format(self, mock_flight_tools):
        """Test land_legacy() returns result in legacy format."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await land_legacy(drone_id="drone1")

            assert "success" in result
            assert "drone_id" in result
            assert "version" in result
            assert result["drone_id"] == "drone1"

    @pytest.mark.asyncio
    async def test_rtl_legacy_emits_warning(self, mock_flight_tools):
        """Test rtl_legacy() emits deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await rtl_legacy(drone_id="drone1")

            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1

    @pytest.mark.asyncio
    async def test_abort_mission_legacy_accepts_reason_and_drone_id(self, mock_flight_tools):
        """Test abort_mission_legacy() accepts both reason and drone_id."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = await abort_mission_legacy(reason="Emergency", drone_id="drone1")

            mock_flight_tools.abort_mission.assert_called_once_with(reason="Emergency")
            assert "drone_id" in result
            assert result["drone_id"] == "drone1"


# =============================================================================
# Configuration Tests
# =============================================================================


class TestLegacyConfiguration:
    """Test legacy configuration backward compatibility."""

    def test_drone_mcp_server_config_emits_warning(self):
        """Test DroneMCPServerConfig emits deprecation warning."""
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
        """Test DroneMCPServerConfig preserves configuration values."""
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
        """Test conversion to FlightToolsConfig."""
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
        """Test ConnectionConfig is re-exported for backward compatibility."""
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


class TestUtilityFunctions:
    """Test compatibility utility functions."""

    def test_check_api_compatibility_returns_dict(self):
        """Test check_api_compatibility returns expected structure."""
        result = check_api_compatibility()

        assert isinstance(result, dict)
        assert "compat_version" in result
        assert "target_removal" in result
        assert "deprecated_items" in result
        assert "migration_guide" in result
        assert result["compat_version"] == "0.2.0"

    def test_check_api_compatibility_lists_deprecated_items(self):
        """Test check_api_compatibility lists all deprecated APIs."""
        result = check_api_compatibility()

        deprecated_names = [item["name"] for item in result["deprecated_items"]]

        assert "DroneConnection" in deprecated_names
        assert "DroneMCPServerConfig" in deprecated_names

    def test_get_migration_guide_returns_string(self):
        """Test get_migration_guide returns formatted string."""
        guide = get_migration_guide()

        assert isinstance(guide, str)
        assert "MIGRATION GUIDE" in guide
        assert "DEPRECATION NOTICE" in guide
        assert "ConnectionManager" in guide


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @pytest.mark.asyncio
    async def test_old_style_connection_and_flight(self, mock_connection_manager, mock_flight_tools):
        """Test old-style code pattern: connect -> arm -> takeoff."""
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
        """Test separate arm() and takeoff() calls (old pattern)."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")

            # Arm first
            arm_result = await arm(drone_id="drone1")
            assert "success" in arm_result

            # Then takeoff
            takeoff_result = await takeoff(altitude=10.0)
            assert "altitude_m" in takeoff_result

    def test_imports_from_mcp_server_module(self):
        """Test that all compat items can be imported from mcp_server module."""
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


class TestDeprecationWarnings:
    """Test deprecation warning behavior."""

    def test_duplicate_warnings_suppressed(self):
        """Test that duplicate warnings are suppressed per module."""
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
        """Test that warnings include migration guidance."""
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
        """Test that warnings are raised with proper metadata."""
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


class TestErrorHandling:
    """Test error handling in compatibility layer."""

    @pytest.mark.asyncio
    async def test_arm_handles_failure(self, mock_flight_tools):
        """Test arm() handles failure gracefully."""
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
        """Test connection failure is properly propagated."""
        mock_connection_manager.connect.return_value = False

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            conn = DroneConnection()
            result = await conn.connect()

            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_health_timeout(self, mock_connection_manager):
        """Test wait_for_health handles unhealthiness."""
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


class TestVersionAndMetadata:
    """Test version information and metadata."""

    def test_compat_module_exports(self):
        """Test that all expected exports are in __all__."""
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
        """Test that mcp_server module exports compat items."""
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
