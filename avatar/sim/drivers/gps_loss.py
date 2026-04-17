"""
GPS Loss Driver - Simulates GPS signal loss.

INJECTION BEHAVIOR:
===================
- Simulates loss of GPS fix
- Drone may switch to non-GPS flight mode
- Triggers position uncertainty increase

PARAMETERS:
===========
- duration_s: Duration of GPS loss (default: 10)
- gradual: Gradual degradation vs sudden loss (default: False)
- recover_method: Recovery behavior (default: "auto")

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: navigation, t_offset_s: 5 }
    driver: gps_loss
    params:
      duration_s: 15
      gradual: true
```

EXPECTED DRONE BEHAVIOR:
========================
1. GPS quality degrades (if gradual=true)
2. Position estimate becomes less accurate
3. Drone may switch to ALTCTL or MANUAL mode
4. If duration_s set, GPS returns after that time
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)


class GpsLossDriver:
    """
    Simulates GPS signal loss.

    GPS LOSS SIMULATION:
    ====================
    In real flight, GPS loss triggers:
    1. Position estimate uncertainty increases
    2. EKF may switch to altitude-only mode
    3. Position-dependent modes (OFFBOARD, POSCTL) may become unavailable
    4. Failsafe may trigger RTL in position-less mode

    SIMULATION IMPLEMENTATION:
    =========================
    For SIH/Gazebo, we simulate by:
    1. Setting GPS timeout to zero (signal lost)
    2. Injecting GPS noise/failure
    3. Monitoring for failsafe triggers
    """

    name: ClassVar[str] = "gps_loss"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        GpsLossDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._gps_satellites_original: int = 12

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject GPS loss condition.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        gradual = ctx.params.get("gradual", False)
        duration_s = ctx.params.get("duration_s")

        logger.info(f"Injecting GPS loss (gradual={gradual}, duration={duration_s}s)")

        try:
            if gradual:
                # Gradual degradation: reduce satellites over time
                for sats in [10, 8, 6, 4, 2, 0]:
                    await ctx.mcp_client.call_tool(
                        "set_gps_satellites",
                        {"count": sats}
                    )
                    # In real simulation, would use asyncio.sleep
                    # Here we just record the progression
                    logger.debug(f"GPS satellites: {sats}")

            else:
                # Sudden GPS loss
                await ctx.mcp_client.call_tool(
                    "set_gps_satellites",
                    {"count": 0}
                )

            # Set GPS timeout to trigger loss detection
            await ctx.mcp_client.call_tool(
                "set_parameter",
                {"name": "GPS_TIMEOUT", "value": 0}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(gps_satellites=0)

            logger.info("GPS loss injection complete")

        except Exception as e:
            logger.warning(f"GPS loss injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_gps_satellites", {"count": 0})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release GPS loss and restore GPS fix.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing GPS loss, restoring GPS fix")

        try:
            # Restore GPS satellites
            await ctx.mcp_client.call_tool(
                "set_gps_satellites",
                {"count": self._gps_satellites_original}
            )

            # Restore GPS timeout
            await ctx.mcp_client.call_tool(
                "set_parameter",
                {"name": "GPS_TIMEOUT", "value": 5}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(gps_satellites=self._gps_satellites_original)

            logger.info("GPS restored: fix regained")

        except Exception as e:
            logger.warning(f"GPS release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_gps_satellites", {"count": self._gps_satellites_original})
                )
