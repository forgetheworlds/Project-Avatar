"""Connection Configuration Module for Project Avatar.

This module provides the ConnectionConfig dataclass and MavsdkError alias
for MAVSDK drone connection management. It replaces the legacy
avatar.mav.connection module which has been removed.

Migration Guide:
    LEGACY (removed in v0.4.0):
        The avatar.mav.connection module has been removed.

    NEW (recommended):
        from avatar.mav.connection_config import ConnectionConfig
        from avatar.mav.connection_manager import ConnectionManager  # Preferred

    For backward compatibility (shim available until v0.4.0):
        from avatar.mcp_server.compat import DroneConnection, ConnectionConfig

Note:
    MAVSDK does not export a dedicated MavsdkError class. Errors from MAVSDK
    are raised as standard Python exceptions, hence MavsdkError is aliased to Exception.
"""

from dataclasses import dataclass, field
from typing import Optional


# Note: mavsdk doesn't export a dedicated MavsdkError class
# Errors from MAVSDK are raised as standard Python exceptions
MavsdkError = Exception


@dataclass
class ConnectionConfig:
    """Configuration parameters for MAVSDK drone connection.

    This dataclass encapsulates all connection-related settings including
    the MAVLink endpoint address, retry behavior, and timeout thresholds.

    Attributes:
        system_address: MAVLink connection string. Common formats:
            - "udp://:14540" - Listen on all interfaces, port 14540 (SITL default)
            - "udp://192.168.1.10:14550" - Connect to specific host
            - "serial:///dev/ttyUSB0:57600" - USB telemetry radio at 57600 baud
            - "serial:///dev/ttyACM0:921600" - Direct USB at 921600 baud
        max_retries: Maximum connection attempts before giving up
        retry_delay_s: Seconds to wait between connection attempts
        health_timeout_s: Maximum seconds to wait for health checks (GPS, gyro)

    Default values are tuned for SITL simulation where the simulator may take
    a few seconds to fully start up and begin accepting connections.

    Example:
        >>> config = ConnectionConfig(
        ...     system_address="udp://:14540",
        ...     max_retries=5,
        ...     retry_delay_s=2.0
        ... )
        >>> print(config.system_address)
        udp://:14540
    """
    system_address: str = "udp://:14540"      # Default SITL UDP endpoint
    max_retries: int = 3                        # Retry 3 times before failing
    retry_delay_s: float = 1.0                 # 1 second between retries
    health_timeout_s: float = 30.0             # 30s timeout for GPS/gyro lock


__all__ = ["ConnectionConfig", "MavsdkError"]
