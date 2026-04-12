"""
PX4/SITL connection management.

Manages MAVSDK connection to drone (SITL or hardware).
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock

try:
    from mavsdk import System
except ImportError:
    # Fallback for testing without mavsdk installed
    class System:  # type: ignore
        """Mock MAVSDK System for testing."""

        def __init__(self) -> None:
            self.core = MagicMock()
            self.telemetry = MagicMock()
            self.action = MagicMock()
            self.offboard = MagicMock()

        async def connect(self, system_address: str) -> None:
            pass

# Note: mavsdk doesn't export a dedicated MavsdkError class
# Errors from MAVSDK are raised as standard Python exceptions
MavsdkError = Exception

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Connection configuration."""
    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0


class DroneConnection:
    """
    Manages MAVSDK connection to drone (SITL or hardware).

    Responsibilities:
    - Establish connection (UDP for SITL, serial for hardware)
    - Retry logic (3 attempts with 1s delay)
    - Health check wait (GPS, gyro, home position)
    - Graceful disconnect

    Usage:
        conn = DroneConnection("udp://:14540")
        await conn.connect()
        # ... use conn.drone for MAVSDK operations ...
        await conn.disconnect()
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        self.config = config or ConnectionConfig()
        self.drone: Optional[System] = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to drone with retry logic."""
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(f"Connection attempt {attempt}/{self.config.max_retries}")

                self.drone = System()
                await self.drone.connect(system_address=self.config.system_address)

                # Wait for connection
                async for state in self.drone.core.connection_state():
                    if state.is_connected:
                        logger.info("Drone connected!")
                        self._connected = True
                        return True
                    break

            except MavsdkError as e:
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay_s)

        logger.error("Failed to connect after all retries")
        return False

    async def wait_for_health(self) -> bool:
        """Wait for GPS/gyro calibration and home position."""
        if not self.drone:
            return False

        try:
            logger.info("Waiting for GPS lock and home position...")

            async for health in self.drone.telemetry.health():
                if health.is_global_position_ok and health.is_home_position_ok:
                    logger.info("GPS and home position OK!")
                    return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

        return False

    async def disconnect(self) -> None:
        """Graceful disconnect."""
        if self.drone:
            # MAVSDK doesn't have explicit disconnect, just stop using it
            logger.info("Disconnected from drone")
        self._connected = False
        self.drone = None

    @property
    def is_connected(self) -> bool:
        return self._connected
