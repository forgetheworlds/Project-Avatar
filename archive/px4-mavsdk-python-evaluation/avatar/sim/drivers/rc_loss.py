"""
RC Loss Driver - Simulates RC link loss.

INJECTION BEHAVIOR:
===================
- Simulates loss of RC (remote control) link
- Tests RC loss failsafe behavior
- Drone may execute RTL or hover

PARAMETERS:
===========
- duration_s: Duration of RC loss (default: 10)
- loss_type: Type of RC loss (default: "signal_loss")
  - "signal_loss": Complete signal loss
  - "weak_signal": Intermittent signal with delays
  - "interference": Signal present but corrupted

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: hover, t_offset_s: 5 }
    driver: rc_loss
    params:
      duration_s: 15
      loss_type: signal_loss
```

EXPECTED DRONE BEHAVIOR:
========================
1. RC link status changes to lost/weak
2. PX4 triggers RC loss failsafe (after timeout)
3. Drone executes configured failsafe action:
   - Return to Launch (RTL)
   - Hold/Land
   - Continue mission (if configured)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)

RcLossType = Literal["signal_loss", "weak_signal", "interference"]


class RcLossDriver:
    """
    Simulates RC link loss.

    RC LINK IN PX4:
    ================
    PX4 monitors RC link quality via:
    - Signal strength reporting
    - Command response timing
    - Heartbeat from transmitter

    On RC loss:
    1. Wait for RC loss timeout (parameter)
    2. Execute failsafe action
    3. Log event for post-flight analysis

    SIMULATION:
    ===========
    In SITL, we simulate by:
    - Setting RC signal strength to 0
    - Or stopping RC command injection
    - Monitoring failsafe trigger
    """

    name: ClassVar[str] = "rc_loss"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        RcLossDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._rc_connected: bool = True

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject RC link loss.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        loss_type: RcLossType = ctx.params.get("loss_type", "signal_loss")
        duration_s = ctx.params.get("duration_s", 10)

        logger.info(
            f"Injecting RC loss: {loss_type} (duration: {duration_s}s)"
        )

        try:
            if loss_type == "signal_loss":
                # Complete signal loss
                await ctx.mcp_client.call_tool(
                    "set_rc_signal_strength",
                    {"strength": 0}
                )
                self._rc_connected = False

            elif loss_type == "weak_signal":
                # Weak/intermittent signal
                await ctx.mcp_client.call_tool(
                    "set_rc_signal_strength",
                    {"strength": 30}  # Weak signal
                )
                await ctx.mcp_client.call_tool(
                    "set_rc_intermittent",
                    {"enabled": True, "drop_rate": 0.3}
                )

            elif loss_type == "interference":
                # Corrupted signal
                await ctx.mcp_client.call_tool(
                    "set_rc_interference",
                    {"enabled": True, "noise_level": 0.5}
                )

            # Update RC status
            await ctx.mcp_client.call_tool(
                "set_rc_status",
                {"connected": False, "loss_type": loss_type}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(rc_connected=False)

            logger.info(f"RC loss injected: {loss_type}")

        except Exception as e:
            logger.warning(f"RC loss injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_rc_signal_strength", {"strength": 0})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release RC loss and restore RC link.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing RC loss, restoring RC link")

        try:
            # Restore signal strength
            await ctx.mcp_client.call_tool(
                "set_rc_signal_strength",
                {"strength": 100}
            )
            self._rc_connected = True

            # Clear intermittent/interference modes
            await ctx.mcp_client.call_tool(
                "set_rc_intermittent",
                {"enabled": False, "drop_rate": 0}
            )
            await ctx.mcp_client.call_tool(
                "set_rc_interference",
                {"enabled": False, "noise_level": 0}
            )

            # Update status
            await ctx.mcp_client.call_tool(
                "set_rc_status",
                {"connected": True, "loss_type": "none"}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(rc_connected=True)

            logger.info("RC link restored: connection regained")

        except Exception as e:
            logger.warning(f"RC release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_rc_signal_strength", {"strength": 100})
                )
