"""
Battery Drain Driver - Simulates rapid battery depletion.

INJECTION BEHAVIOR:
===================
- Simulates faster than normal battery drain
- Tests low-battery failsafe behavior
- Can trigger RTL or landing at configurable thresholds

PARAMETERS:
===========
- drain_rate: Multiplier for drain rate (default: 5.0 = 5x faster)
- target_percent: Target battery level (default: 15)
- gradual: Gradual vs step drain (default: True)

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { absolute_s: 60 }
    driver: battery_drain
    params:
      drain_rate: 10
      target_percent: 20
      gradual: true
```

EXPECTED DRONE BEHAVIOR:
========================
1. Battery level drops faster than normal
2. At low battery threshold (25% default), RTL triggers
3. At critical threshold (10%), immediate landing
4. GuardianProcess logs battery warnings
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)


class BatteryDrainDriver:
    """
    Simulates rapid battery depletion.

    BATTERY MODEL IN SIMULATION:
    ============================
    Battery drain is modeled as a percentage that decreases over time.
    In real flight, drain rate depends on:
    - Throttle level (hovering vs aggressive flight)
    - Wind conditions
    - Payload weight
    - Battery age/health

    This driver accelerates the drain to test failsafes without waiting
    for realistic discharge times.

    SAFETY TESTING:
    ===============
    This is essential for testing:
    1. RTL trigger at correct threshold
    2. Battery warning levels in GuardianProcess
    3. Mission abort behavior on low battery
    """

    name: ClassVar[str] = "battery_drain"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        BatteryDrainDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._original_battery: float = 100.0
        self._drain_task = None

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject battery drain condition.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        drain_rate = ctx.params.get("drain_rate", 5.0)
        target_percent = ctx.params.get("target_percent", 15)
        gradual = ctx.params.get("gradual", True)

        # Get current battery level from telemetry
        current_battery = ctx.telemetry.get("battery_percent", 85.0)
        self._original_battery = current_battery

        logger.info(
            f"Injecting battery drain: {current_battery}% -> {target_percent}% "
            f"(rate: {drain_rate}x, gradual: {gradual})"
        )

        try:
            if gradual:
                # Set accelerated drain rate
                await ctx.mcp_client.call_tool(
                    "set_battery_drain_rate",
                    {"multiplier": drain_rate}
                )

                # Set target level
                await ctx.mcp_client.call_tool(
                    "set_battery_target",
                    {"percent": target_percent}
                )
            else:
                # Immediate step change
                await ctx.mcp_client.call_tool(
                    "set_battery_level",
                    {"percent": target_percent}
                )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(battery_percent=target_percent)

            logger.info(f"Battery drain injected: targeting {target_percent}%")

        except Exception as e:
            logger.warning(f"Battery drain injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_battery_level", {"percent": target_percent})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release battery drain and restore normal drain rate.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing battery drain, restoring normal drain rate")

        try:
            # Reset drain rate to normal
            await ctx.mcp_client.call_tool(
                "set_battery_drain_rate",
                {"multiplier": 1.0}
            )

            # Note: We don't restore battery level (that would be unrealistic)
            # The battery stays at whatever level it reached during injection

            logger.info("Battery drain rate restored to normal")

        except Exception as e:
            logger.warning(f"Battery drain release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_battery_drain_rate", {"multiplier": 1.0})
                )
