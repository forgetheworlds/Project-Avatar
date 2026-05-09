"""Offboard setpoint streaming for PX4 velocity control."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from avatar.mav.offboard_owner import OffboardOwner

logger = logging.getLogger(__name__)


@dataclass
class OffboardVelocityStreamer:
    """Streams MAVSDK velocity setpoints at a fixed cadence for PX4 Offboard mode.

    This streamer handles the continuous setpoint stream required by PX4 to
    maintain offboard mode. It integrates with OffboardOwner for mutual exclusion.

    SAFETY NOTES:
    - PX4 requires setpoints at minimum 10Hz (ideally 20Hz)
    - If setpoints stop, PX4 triggers COM_OF_LOSS_T failsafe (default 0.5s)
    - OffboardOwner integration prevents conflicting control sources

    Example:
        streamer = OffboardVelocityStreamer(rate_hz=20.0)

        # With OffboardOwner for mutual exclusion
        owner = get_offboard_owner()
        count = await streamer.stream_for(
            drone, velocity_setpoint, duration_s=5.0,
            offboard_owner=owner, owner_id="my_mission"
        )

        # Without OffboardOwner (for simple use cases)
        count = await streamer.stream_for(drone, velocity_setpoint, duration_s=5.0)
    """

    rate_hz: float = 20.0

    @property
    def interval_s(self) -> float:
        return 1.0 / self.rate_hz

    async def stream_for(
        self,
        drone: Any,
        velocity_setpoint: Any,
        duration_s: float,
        offboard_owner: Optional[OffboardOwner] = None,
        owner_id: str = "offboard_velocity_streamer",
    ) -> int:
        """Send velocity setpoints, start offboard mode, stream, and stop.

        This method handles the complete offboard lifecycle:
        1. Acquire OffboardOwner (if provided) for mutual exclusion
        2. Set initial velocity setpoint
        3. Start offboard mode
        4. Stream setpoints at configured rate for duration
        5. Stop offboard mode
        6. Release OffboardOwner (if acquired)

        Args:
            drone: MAVSDK System instance
            velocity_setpoint: MAVSDK VelocityNedYaw setpoint
            duration_s: How long to stream setpoints (seconds)
            offboard_owner: Optional OffboardOwner for mutual exclusion
            owner_id: Identifier for this streamer when acquiring ownership

        Returns:
            Number of setpoints sent. Returns 0 if OffboardOwner acquisition fails.

        Example:
            streamer = OffboardVelocityStreamer(rate_hz=20.0)
            count = await streamer.stream_for(
                drone, VelocityNedYaw(1.0, 0.0, 0.0, 0.0), duration_s=5.0
            )
            print(f"Sent {count} setpoints")
        """
        setpoint_count = 0
        started = False
        acquired_owner = False

        try:
            # Attempt to acquire OffboardOwner if provided
            if offboard_owner is not None:
                acquired = await offboard_owner.acquire(owner_id)
                if not acquired:
                    current = offboard_owner.current_owner()
                    logger.warning(
                        f"Failed to acquire offboard ownership. "
                        f"Currently owned by: {current}"
                    )
                    return 0
                acquired_owner = True

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
            # Always stop offboard mode if started
            if started:
                try:
                    await drone.offboard.stop()
                except Exception as exc:
                    logger.warning("Failed to stop offboard mode: %s", exc)

            # Release OffboardOwner if we acquired it
            if acquired_owner and offboard_owner is not None:
                try:
                    await offboard_owner.release(owner_id)
                except Exception as exc:
                    logger.warning("Failed to release offboard ownership: %s", exc)
