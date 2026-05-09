"""
Obstacle Proximity Driver - Simulates obstacle detection events.

INJECTION BEHAVIOR:
===================
- Simulates obstacle appearing in drone's path
- Tests obstacle avoidance/abort behavior
- Can trigger emergency brake or path replanning

PARAMETERS:
===========
- distance_m: Distance to obstacle (default: 5)
- direction: Obstacle direction relative to drone (default: "front")
  - "front", "rear", "left", "right", "above", "below"
- speed_m_s: Obstacle approach speed if moving (default: 0)
- type: Obstacle type (default: "static")
  - "static", "moving", "temporary"

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: navigation, t_offset_s: 10 }
    driver: obstacle_proximity
    params:
      distance_m: 3
      direction: front
      type: moving
      speed_m_s: 2
```

EXPECTED DRONE BEHAVIOR:
========================
1. Obstacle detected by vision or proximity sensors
2. Drone may execute avoidance maneuver
3. Or trigger emergency brake/abort
4. GuardianProcess logs obstacle event
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)

ObstacleDirection = Literal["front", "rear", "left", "right", "above", "below"]
ObstacleType = Literal["static", "moving", "temporary"]


class ObstacleProximityDriver:
    """
    Simulates obstacle detection events.

    OBSTACLE AVOIDANCE IN PROJECT AVATAR:
    =====================================
    The obstacle system uses:
    - Vision-based detection (YOLO for obstacles)
    - Proximity sensors (simulated distance readings)
    - Path planning adjustments

    DETECTION THRESHOLDS:
    =====================
    - Warning distance: 10m (slow down)
    - Critical distance: 5m (stop/avoid)
    - Emergency distance: 2m (immediate action)

    SIMULATION METHOD:
    ==================
    We simulate by injecting:
    - Fake obstacle detection in vision feed
    - Simulated proximity sensor readings
    - Monitor GuardianProcess and flight response
    """

    name: ClassVar[str] = "obstacle_proximity"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        ObstacleProximityDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._obstacle_present: bool = False

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject obstacle proximity condition.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        distance_m = ctx.params.get("distance_m", 5.0)
        direction: ObstacleDirection = ctx.params.get("direction", "front")
        obstacle_type: ObstacleType = ctx.params.get("type", "static")
        speed_m_s = ctx.params.get("speed_m_s", 0.0)

        logger.info(
            f"Injecting obstacle: {distance_m}m {direction} "
            f"(type: {obstacle_type}, speed: {speed_m_s}m/s)"
        )

        try:
            # Add obstacle to detection system
            await ctx.mcp_client.call_tool(
                "add_obstacle",
                {
                    "distance_m": distance_m,
                    "direction": direction,
                    "type": obstacle_type,
                    "speed_m_s": speed_m_s,
                }
            )
            self._obstacle_present = True

            # Set proximity sensor reading
            await ctx.mcp_client.call_tool(
                "set_proximity_sensor",
                {
                    "direction": direction,
                    "distance_m": distance_m,
                }
            )

            # Trigger obstacle detection in vision
            # (fake detection object)
            await ctx.mcp_client.call_tool(
                "inject_vision_detection",
                {
                    "label": "obstacle",
                    "confidence": 0.95,
                    "distance_m": distance_m,
                    "direction": direction,
                }
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(
                    obstacle_detected=True,
                    obstacle_distance=distance_m,
                    obstacle_direction=direction,
                )

            logger.info(f"Obstacle injected: {distance_m}m {direction}")

        except Exception as e:
            logger.warning(f"Obstacle injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("add_obstacle", {"distance_m": distance_m, "direction": direction})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release obstacle condition.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing obstacle condition")

        try:
            # Remove obstacle
            await ctx.mcp_client.call_tool(
                "remove_obstacle",
                {"all": True}
            )
            self._obstacle_present = False

            # Clear proximity sensor
            await ctx.mcp_client.call_tool(
                "set_proximity_sensor",
                {
                    "direction": "all",
                    "distance_m": 999,  # No obstacle
                }
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(
                    obstacle_detected=False,
                    obstacle_distance=999,
                )

            logger.info("Obstacle removed: clear path")

        except Exception as e:
            logger.warning(f"Obstacle release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("remove_obstacle", {"all": True})
                )
