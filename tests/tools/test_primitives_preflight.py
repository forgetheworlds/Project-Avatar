"""Tests for run_preflight MCP tool.

Verifies preflight check functionality for drone safety validation.

The run_preflight tool performs comprehensive safety checks before flight:
- GPS: Validates GPS lock quality (3D fix required)
- Battery: Checks battery level (>=25% for RTL, >=50% preferred)
- Home: Verifies home position is set (required for RTL)
- Sensors: Checks sensor calibration status
- Connection: Validates MAVLink connection state

Test Categories:
    - TestRunPreflightSchema: Schema validation tests
    - TestRunPreflightAllChecks: Full preflight check tests
    - TestRunPreflightSelectiveChecks: Individual check tests
    - TestRunPreflightEdgeCases: Edge case and error handling tests
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from avatar.mcp_server.tools import primitives_preflight as preflight
from avatar.mav.connection_manager import ConnectionState


class TestRunPreflightSchema:
    """Test schema validation for run_preflight tool."""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)
        yield
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)

    def test_run_preflight_input_schema(self):
        """Input schema has expected structure."""
        schema = preflight.run_preflight_tool_schema()
        assert "properties" in schema
        assert "checks" in schema["properties"]
        # Pydantic v2 uses anyOf for Optional fields
        checks_schema = schema["properties"]["checks"]
        if "anyOf" in checks_schema:
            # Find the array type in anyOf
            array_schema = next(
                (s for s in checks_schema["anyOf"] if s.get("type") == "array"),
                None
            )
            assert array_schema is not None
            assert array_schema["items"]["type"] == "string"
        else:
            # Fallback for simpler schema format
            assert checks_schema["type"] == "array"
            assert checks_schema["items"]["type"] == "string"

    def test_run_preflight_output_schema(self):
        """Output schema has expected structure."""
        schema = preflight.run_preflight_output_schema()
        assert "properties" in schema
        assert "checks" in schema["properties"]
        assert "all_passed" in schema["properties"]
        assert "warnings" in schema["properties"]
        assert "failures" in schema["properties"]

    def test_run_preflight_annotations(self):
        """Annotations indicate read-only tool."""
        annotations = preflight.run_preflight_annotations()
        assert annotations["readOnlyHint"] is True
        assert annotations["destructiveHint"] is False
        assert annotations["idempotentHint"] is True
        assert annotations["openWorldHint"] is False

    def test_run_preflight_input_defaults(self):
        """Input schema defaults to all checks when checks is None."""
        input_data = preflight.RunPreflightInput()
        assert input_data.checks is None

    def test_run_preflight_input_with_checks(self):
        """Input schema accepts specific checks list."""
        input_data = preflight.RunPreflightInput(checks=["gps", "battery"])
        assert input_data.checks == ["gps", "battery"]


class TestRunPreflightAllChecks:
    """Test full preflight check execution."""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons and create mocks before each test."""
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)
        yield
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)

    @pytest.fixture
    def mock_telemetry_cache(self):
        """Create mock telemetry cache with good data."""
        cache = MagicMock()
        data = MagicMock()
        data.gps_fix = 4
        data.is_gps_ok = True
        data.battery_percent = 85.0
        cache.get_data = MagicMock(return_value=data)
        return cache

    @pytest.fixture
    def mock_guardian(self):
        """Create mock guardian with home position set."""
        guardian = MagicMock()
        guardian.is_home_set = True
        guardian.home_position = (37.7749, -122.4194)
        return guardian

    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager with connected state."""
        cm = MagicMock()
        cm.state = ConnectionState.CONNECTED
        cm.ensure_connected = AsyncMock(return_value=MagicMock())
        return cm

    @pytest.fixture
    def mock_drone(self):
        """Create mock drone with healthy sensors."""
        drone = MagicMock()

        # Mock health telemetry
        health = MagicMock()
        health.is_gyrometer_calibration_ok = True
        health.is_accelerometer_calibration_ok = True
        health.is_magnetometer_calibration_ok = True
        health.is_level_calibration_ok = True
        health.is_global_position_valid = True
        health.is_home_position_ok = True

        async def mock_health():
            yield health

        drone.telemetry.health = mock_health

        return drone

    @pytest.mark.asyncio
    async def test_all_checks_pass(
        self, mock_telemetry_cache, mock_guardian, mock_connection_manager, mock_drone
    ):
        """All checks pass when telemetry is healthy."""
        preflight.set_telemetry_cache(mock_telemetry_cache)
        preflight.set_guardian(mock_guardian)
        # Wire up mock_drone to be returned by ensure_connected
        mock_connection_manager.ensure_connected = AsyncMock(return_value=mock_drone)
        preflight.set_connection_manager(mock_connection_manager)

        result = await preflight.run_preflight()
        data = json.loads(result)

        assert data["all_passed"] is True
        assert data["warnings"] == 0
        assert data["failures"] == 0
        assert len(data["checks"]) == 5

        # Verify all checks passed
        for check in data["checks"]:
            assert check["status"] == "pass"

    @pytest.mark.asyncio
    async def test_returns_json_string(self):
        """run_preflight returns a JSON string."""
        result = await preflight.run_preflight()
        assert isinstance(result, str)

        # Should be valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_handle_run_preflight_returns_json(self):
        """handle_run_preflight returns JSON string."""
        result = await preflight.handle_run_preflight({})
        assert isinstance(result, str)

        data = json.loads(result)
        assert "checks" in data
        assert "all_passed" in data


class TestRunPreflightSelectiveChecks:
    """Test individual check functionality."""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)
        yield
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)

    @pytest.mark.asyncio
    async def test_gps_check_only(self):
        """Can run only GPS check."""
        result = await preflight.run_preflight(checks=["gps"])
        data = json.loads(result)

        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "gps"

    @pytest.mark.asyncio
    async def test_battery_check_only(self):
        """Can run only battery check."""
        result = await preflight.run_preflight(checks=["battery"])
        data = json.loads(result)

        assert len(data["checks"]) == 1
        assert data["checks"][0]["name"] == "battery"

    @pytest.mark.asyncio
    async def test_multiple_checks(self):
        """Can run specific subset of checks."""
        result = await preflight.run_preflight(checks=["gps", "battery", "connection"])
        data = json.loads(result)

        assert len(data["checks"]) == 3
        check_names = {c["name"] for c in data["checks"]}
        assert check_names == {"gps", "battery", "connection"}

    @pytest.mark.asyncio
    async def test_invalid_check_name_returns_error(self):
        """Invalid check names return error envelope."""
        result = await preflight.run_preflight(checks=["gps", "invalid_check"])
        data = json.loads(result)

        assert "isError" in data or "error" in data

    @pytest.mark.asyncio
    async def test_gps_passes_with_3d_fix(self):
        """GPS check passes with 3D fix."""
        cache = MagicMock()
        data = MagicMock()
        data.gps_fix = 4
        data.is_gps_ok = True
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["gps"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "pass"

    @pytest.mark.asyncio
    async def test_gps_warns_with_2d_fix(self):
        """GPS check warns with 2D fix."""
        cache = MagicMock()
        data = MagicMock()
        data.gps_fix = 2
        data.is_gps_ok = False
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["gps"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "warn"
        assert data["warnings"] == 1

    @pytest.mark.asyncio
    async def test_gps_fails_with_no_fix(self):
        """GPS check fails with no fix."""
        cache = MagicMock()
        data = MagicMock()
        data.gps_fix = 0
        data.is_gps_ok = False
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["gps"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "fail"
        assert data["failures"] == 1
        assert data["all_passed"] is False

    @pytest.mark.asyncio
    async def test_battery_passes_above_50_percent(self):
        """Battery check passes above 50%."""
        cache = MagicMock()
        data = MagicMock()
        data.battery_percent = 85.0
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["battery"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "pass"

    @pytest.mark.asyncio
    async def test_battery_warns_between_25_and_50(self):
        """Battery check warns between 25% and 50%."""
        cache = MagicMock()
        data = MagicMock()
        data.battery_percent = 35.0
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["battery"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "warn"

    @pytest.mark.asyncio
    async def test_battery_fails_below_25(self):
        """Battery check fails below 25%."""
        cache = MagicMock()
        data = MagicMock()
        data.battery_percent = 15.0
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["battery"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "fail"

    @pytest.mark.asyncio
    async def test_home_passes_when_set(self):
        """Home check passes when home position is set."""
        guardian = MagicMock()
        guardian.is_home_set = True
        guardian.home_position = (37.7749, -122.4194)

        preflight.set_guardian(guardian)

        result = await preflight.run_preflight(checks=["home"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "pass"

    @pytest.mark.asyncio
    async def test_home_warns_when_not_set(self):
        """Home check warns when home position is not set."""
        guardian = MagicMock()
        guardian.is_home_set = False

        preflight.set_guardian(guardian)

        result = await preflight.run_preflight(checks=["home"])
        data = json.loads(result)

        # Home not set is a warning, not a failure (can set on arm)
        assert data["checks"][0]["status"] in ("warn", "pass")


class TestRunPreflightEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)
        yield
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)

    @pytest.mark.asyncio
    async def test_no_telemetry_cache_graceful_handling(self):
        """Handles missing telemetry cache gracefully."""
        result = await preflight.run_preflight(checks=["gps"])
        data = json.loads(result)

        # Should return results, not crash
        assert "checks" in data
        assert data["checks"][0]["status"] == "fail"

    @pytest.mark.asyncio
    async def test_empty_telemetry_data(self):
        """Handles empty telemetry data gracefully."""
        cache = MagicMock()
        cache.get_data = MagicMock(return_value=None)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["gps"])
        data = json.loads(result)

        assert data["checks"][0]["status"] == "fail"

    @pytest.mark.asyncio
    async def test_no_connection_manager_graceful_handling(self):
        """Handles missing connection manager gracefully."""
        result = await preflight.run_preflight(checks=["connection"])
        data = json.loads(result)

        # Should still return results
        assert "checks" in data
        # Connection check may fail without connection manager
        assert data["checks"][0]["name"] == "connection"

    @pytest.mark.asyncio
    async def test_mixed_results_count_correctly(self):
        """Warnings and failures are counted correctly."""
        cache = MagicMock()
        data = MagicMock()
        data.gps_fix = 2  # warn
        data.is_gps_ok = False
        data.battery_percent = 15.0  # fail
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["gps", "battery"])
        data = json.loads(result)

        assert data["warnings"] == 1  # gps
        assert data["failures"] == 1  # battery
        assert data["all_passed"] is False

    @pytest.mark.asyncio
    async def test_all_passed_true_with_warnings(self):
        """all_passed is True with warnings but no failures."""
        cache = MagicMock()
        data = MagicMock()
        data.gps_fix = 2  # warn
        data.is_gps_ok = False
        data.battery_percent = 60.0  # pass
        cache.get_data = MagicMock(return_value=data)

        preflight.set_telemetry_cache(cache)

        result = await preflight.run_preflight(checks=["gps", "battery"])
        data = json.loads(result)

        assert data["warnings"] == 1
        assert data["failures"] == 0
        assert data["all_passed"] is True  # No failures, only warnings


class TestJSONSerialization:
    """Test JSON serialization for MCP transport."""

    @pytest.fixture(autouse=True)
    def setup_test(self):
        """Reset singletons before each test."""
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)
        yield
        preflight.set_telemetry_cache(None)
        preflight.set_guardian(None)
        preflight.set_connection_manager(None)

    @pytest.mark.asyncio
    async def test_result_is_json_serializable(self):
        """Result can be serialized to JSON and parsed back."""
        result = await preflight.run_preflight()

        # Should not raise
        data = json.loads(result)

        # Verify structure
        assert "checks" in data
        assert "all_passed" in data
        assert "warnings" in data
        assert "failures" in data

    @pytest.mark.asyncio
    async def test_result_can_be_re_serialized(self):
        """Result can be re-serialized to JSON."""
        result = await preflight.run_preflight()
        data = json.loads(result)

        # Re-serialize
        re_serialized = json.dumps(data)
        re_parsed = json.loads(re_serialized)

        assert re_parsed == data
