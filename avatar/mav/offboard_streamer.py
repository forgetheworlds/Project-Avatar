"""Offboard setpoint streaming for PX4 velocity control."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OffboardVelocityStreamer:
    """Streams MAVSDK velocity setpoints at a fixed cadence for PX4 Offboard mode."""

    rate_hz: float = 20.0

    @property
    def interval_s(self) -> float:
        return 1.0 / self.rate_hz

    async def stream_for(self, drone: Any, velocity_setpoint: Any, duration_s: float) -> int:
        """Send velocity setpoints, start offboard mode, stream, and stop."""
        setpoint_count = 0
        started = False

        try:
            await drone.offboard.set_velocity_ned(velocity_setpoint)
            await drone.offboard.start()
            started = True

            start_time = time.monotonic()
            next_send_time = start_time

            while time.monotonic() - start_time < duration_s:
                await drone.offboard.set_velocity_ned(velocity_setpoint)
                setpoint_count += 1

                next_send_time += self.interval_s
                sleep_s = next_send_time - time.monotonic()
                if sleep_s > 0:
                    await asyncio.sleep(sleep_s)

            return setpoint_count

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Offboard velocity streaming failed: %s", exc)
            return setpoint_count
        finally:
            if started:
                try:
                    await drone.offboard.stop()
                except Exception as exc:
                    logger.warning("Failed to stop offboard mode: %s", exc)
