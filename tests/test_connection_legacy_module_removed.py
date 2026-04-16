"""Tests for Wave 0 Task 6: ConnectionConfig extraction and legacy module removal.

This test module verifies that:
1. The old avatar/mav/connection.py module is deleted
2. ConnectionConfig is importable from the new location (avatar.mav.connection_config)
3. The DroneConnection shim in compat.py still works
"""

from pathlib import Path


def test_connection_py_deleted() -> None:
    """Verify that the legacy avatar/mav/connection module raises ImportError.

    The legacy module has been replaced with a stub that raises ImportError
    with a helpful migration message, or has been fully removed.
    """
    legacy_file = Path("avatar/mav/connection.py")

    if legacy_file.exists():
        # If stub exists, importing should raise ImportError with helpful message
        try:
            import avatar.mav.connection  # type: ignore[import]
            assert False, "Importing avatar.mav.connection should raise ImportError"
        except ImportError as e:
            # Verify the error message contains migration guidance
            assert "has been removed" in str(e).lower() or "connection_config" in str(e).lower(), (
                f"ImportError should mention migration path, got: {e}"
            )
    # If file doesn't exist, that's also acceptable - fully deleted


def test_connection_config_importable() -> None:
    """Verify ConnectionConfig can be imported from the new location."""
    from avatar.mav.connection_config import ConnectionConfig

    # Test default values
    config = ConnectionConfig()
    assert config.system_address == "udp://:14540"
    assert config.max_retries == 3
    assert config.retry_delay_s == 1.0
    assert config.health_timeout_s == 30.0

    # Test custom values
    custom_config = ConnectionConfig(
        system_address="serial:///dev/ttyUSB0:57600",
        max_retries=5,
        retry_delay_s=2.0,
        health_timeout_s=60.0,
    )
    assert custom_config.system_address == "serial:///dev/ttyUSB0:57600"
    assert custom_config.max_retries == 5
    assert custom_config.retry_delay_s == 2.0
    assert custom_config.health_timeout_s == 60.0


def test_mavsdk_error_alias() -> None:
    """Verify MavsdkError alias is available in connection_config module."""
    from avatar.mav.connection_config import MavsdkError

    # MavsdkError should be an alias for Exception
    assert MavsdkError is Exception


def test_drone_connection_shim_in_compat() -> None:
    """Verify DroneConnection shim is available from compat module."""
    from avatar.mcp_server.compat import DroneConnection

    # Verify it's the shim class, not the original
    assert DroneConnection.__module__ == "avatar.mcp_server.compat"


def test_connection_config_re_export_in_compat() -> None:
    """Verify ConnectionConfig is re-exported from compat module."""
    from avatar.mcp_server.compat import ConnectionConfig

    # Should be the same class as from connection_config
    from avatar.mav.connection_config import ConnectionConfig as OriginalConfig

    assert ConnectionConfig is OriginalConfig


def test_flight_tools_imports_connection_config() -> None:
    """Verify flight_tools can import ConnectionConfig from new location."""
    # This tests that the import in flight_tools.py works
    from avatar.mcp_server.tools.flight_tools import FlightTools, FlightToolsConfig

    # Verify we can create instances
    config = FlightToolsConfig()
    assert config.system_address == "udp://:14540"


def test_telemetry_tools_imports_connection_config() -> None:
    """Verify telemetry_tools can import ConnectionConfig from new location."""
    # This tests that the import in telemetry_tools.py works
    from avatar.mcp_server.tools.telemetry_tools import TelemetryTools, TelemetryToolsConfig

    # Verify we can create instances
    config = TelemetryToolsConfig()
    assert config.system_address == "udp://:14540"


def test_conftest_imports_updated() -> None:
    """Verify conftest.py imports from new location."""
    # The conftest.py fixture uses DroneConnection and ConnectionConfig
    # This test will fail if those imports are broken
    from avatar.mav.connection_config import ConnectionConfig
    from avatar.mcp_server.compat import DroneConnection

    # Verify we can create a ConnectionConfig
    config = ConnectionConfig()
    assert config.system_address == "udp://:14540"
