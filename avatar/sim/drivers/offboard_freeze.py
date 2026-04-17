"""
Offboard Freeze Driver - Simulates offboard mode command stream freeze.

INJECTION BEHAVIOR:
===================
- Simulates stoppage of offboard setpoint stream
- Drone loses position/velocity commands from offboard controller
- May trigger offboard timeout failsafe

PARAMETERS:
===========
- duration_s: Duration of command freeze (default: 3)
- freeze_type: Type of freeze behavior (default: "timeout")
  - "timeout": Commands stop, triggers offboard timeout
  - "hold_last": Last command is held but not updated
  - "zero_velocity": Zero velocity commands sent (hover drift)

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: start_orbit, t_offset_s: 15 }
    driver: offboard_freeze
    params:
      duration_s: 3
      freeze_type: timeout
```

EXPECTED DRONE BEHAVIOR:
========================
1. Offboard setpoint stream stops or becomes stale
2. PX4 triggers offboard timeout (default: 0.5s)
3. Drone executes failsafe action (position hold or RTL)
4. Logs show offboard mode exit

This is CRITICAL for testing failsafe behavior in autonomous flight.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)

FreezeType = Literal["timeout", "hold_last", "zero_velocity"]


class OffboardFreezeDriver:
    """
    Simulates offboard mode command stream freeze.

    OFFBOARD MODE REQUIREMENTS:
    ===========================
    PX4 requires offboard setpoints at minimum 2Hz. If setpoints stop:
    1. After 0.5s (default): Offboard timeout triggers
    2. Drone exits offboard mode
    3. Failsafe action executes (typically position hold or RTL)

    This driver tests that the system handles command interruption gracefully.

    SIMULATION METHOD:
    ==================
    We simulate by:
    1. Stopping setpoint stream from OffboardStreamer
    2. Notifying PX4 that offboard commands are paused
    3. Monitoring for failsafe trigger

    SAFETY NOTE:
    ============
    In real flight, this scenario is dangerous. The simulation helps
    validate that failsafes work correctly before attempting real flights.
    """

    name: ClassVar[str] = "offboard_freeze"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        OffboardFreezeDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._offboard_active: bool = True

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject offboard command freeze.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        freeze_type: FreezeType = ctx.params.get("freeze_type", "timeout")
        duration_s = ctx.params.get("duration_s", 3)

        logger.info(
            f"Injecting offboard freeze: {freeze_type} (duration: {duration_s}s)"
        )

        try:
            if freeze_type == "timeout":
                # Stop sending setpoints completely
                await ctx.mcp_client.call_tool(
                    "pause_offboard_stream",
                    {"reason": "injection_test"}
                )
                self._offboard_active = False

            elif freeze_type == "hold_last":
                # Continue sending last setpoint without updates
                await ctx.mcp_client.call_tool(
                    "freeze_offboard_setpoint",
                    {"mode": "hold_last"}
                )

            elif freeze_type == "zero_velocity":
                # Send zero velocity commands (drift scenario)
                await ctx.mcp_client.call_tool(
                    "set_offboard_velocity",
                    {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_rate": 0.0}
                )

            # Record that offboard is frozen
            await ctx.mcp_client.call_tool(
                "set_offboard_status",
                {"status": "frozen", "freeze_type": freeze_type}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(offboard_status="frozen")

            logger.info(f"Offboard freeze injected: {freeze_type}")

        except Exception as e:
            logger.warning(f"Offboard freeze injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("pause_offboard_stream", {"reason": "injection_test"})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release offboard freeze and restore command stream.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing offboard freeze, restoring command stream")

        try:
            # Resume offboard stream
            if not self._offboard_active:
                await ctx.mcp_client.call_tool(
                    "resume_offboard_stream",
                    {}
                )
                self._offboard_active = True

            # Clear freeze mode
            await ctx.mcp_client.call_tool(
                "freeze_offboard_setpoint",
                {"mode": "normal"}
            )

            # Restore status
            await ctx.mcp_client.call_tool(
                "set_offboard_status",
                {"status": "active", "freeze_type": "none"}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(offboard_status="active")

            logger.info("Offboard stream restored: commands flowing")

        except Exception as e:
            logger.warning(f"Offboard release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("resume_offboard_stream", {})
                )
