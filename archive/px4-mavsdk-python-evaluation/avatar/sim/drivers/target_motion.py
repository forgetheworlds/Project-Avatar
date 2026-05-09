"""
Target Motion Driver - Simulates target movement patterns.

INJECTION BEHAVIOR:
===================
- Simulates target object movement during tracking
- Tests tracking algorithm robustness
- Can simulate various motion patterns

PARAMETERS:
===========
- pattern: Motion pattern (default: "linear")
  - "static": No movement
  - "linear": Linear motion
  - "circular": Circular path
  - "random": Random walk
  - "evading": Evasive maneuvers
- speed_m_s: Target speed (default: 2)
- direction_deg: Movement direction for linear (default: 0)
- radius_m: Radius for circular pattern (default: 10)

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: track, t_offset_s: 0 }
    driver: target_motion
    params:
      pattern: evading
      speed_m_s: 5
```

EXPECTED DRONE BEHAVIOR:
========================
1. Target state is updated with new position/velocity
2. Tracking algorithm adjusts pursuit
3. Drone follows target within constraints
4. Kalman filter updates predictions
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)

MotionPattern = Literal["static", "linear", "circular", "random", "evading"]


class TargetMotionDriver:
    """
    Simulates target movement patterns.

    TARGET TRACKING IN PROJECT AVATAR:
    ===================================
    The tracking system uses:
    - Vision detection to locate target
    - Kalman filter to predict target motion
    - Offboard commands to follow target

    MOTION PATTERNS:
    ================
    - Static: Target stationary (baseline)
    - Linear: Constant velocity in one direction
    - Circular: Orbit around a point
    - Random: Unpredictable random walk
    - Evading: Simulates person/vehicle trying to escape

    This tests tracking algorithm robustness.
    """

    name: ClassVar[str] = "target_motion"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        TargetMotionDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._motion_active: bool = False

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject target motion pattern.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        pattern: MotionPattern = ctx.params.get("pattern", "linear")
        speed_m_s = ctx.params.get("speed_m_s", 2.0)
        direction_deg = ctx.params.get("direction_deg", 0.0)
        radius_m = ctx.params.get("radius_m", 10.0)

        logger.info(
            f"Injecting target motion: {pattern} at {speed_m_s} m/s "
            f"(direction: {direction_deg} deg, radius: {radius_m}m)"
        )

        try:
            # Set target motion parameters
            await ctx.mcp_client.call_tool(
                "set_target_motion",
                {
                    "pattern": pattern,
                    "speed_m_s": speed_m_s,
                    "direction_deg": direction_deg,
                    "radius_m": radius_m,
                }
            )
            self._motion_active = True

            # For Gazebo, update the simulated target entity
            await ctx.mcp_client.call_tool(
                "set_simulation_target",
                {
                    "motion_pattern": pattern,
                    "speed_m_s": speed_m_s,
                }
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(
                    target_motion=pattern,
                    target_speed=speed_m_s,
                )

            logger.info(f"Target motion injected: {pattern}")

        except Exception as e:
            logger.warning(f"Target motion injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_target_motion", {
                        "pattern": pattern,
                        "speed_m_s": speed_m_s,
                    })
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release target motion and return to static.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing target motion, returning to static")

        try:
            # Reset to static target
            await ctx.mcp_client.call_tool(
                "set_target_motion",
                {
                    "pattern": "static",
                    "speed_m_s": 0.0,
                }
            )
            self._motion_active = False

            # Update simulation target
            await ctx.mcp_client.call_tool(
                "set_simulation_target",
                {
                    "motion_pattern": "static",
                    "speed_m_s": 0.0,
                }
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(
                    target_motion="static",
                    target_speed=0.0,
                )

            logger.info("Target motion reset: static target")

        except Exception as e:
            logger.warning(f"Target motion release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_target_motion", {"pattern": "static"})
                )
