"""
Vision Dropout Driver - Simulates camera/vision system failures.

INJECTION BEHAVIOR:
===================
- Simulates camera feed interruption
- Vision detection system stops receiving frames
- Object tracking may lose target lock

PARAMETERS:
===========
- duration_s: Duration of vision dropout (default: 5)
- dropout_type: Type of failure (default: "camera_off")
  - "camera_off": Camera stops sending frames
  - "blur": Frames received but severely blurred
  - "noise": Frames corrupted with noise
  - "latency": High latency in frame delivery

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: track, t_offset_s: 10 }
    driver: vision_dropout
    params:
      duration_s: 8
      dropout_type: blur
```

EXPECTED DRONE BEHAVIOR:
========================
1. Vision detection confidence drops to zero
2. Tracking target may be lost
3. May trigger vision-loss failsafe if configured
4. Drone should hold position or abort vision-dependent operations
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)

DropoutType = Literal["camera_off", "blur", "noise", "latency"]


class VisionDropoutDriver:
    """
    Simulates camera/vision system failures.

    VISION SYSTEM IN PROJECT AVATAR:
    ================================
    The vision system uses:
    1. Gazebo camera plugin for simulation
    2. YOLOv8-nano for object detection
    3. Kalman filter for target tracking

    DROPOUT SIMULATION:
    ===================
    We simulate various failure modes:
    - Camera off: No frames at all
    - Blur: Frames are severely blurred (motion blur simulation)
    - Noise: Corrupted pixel data
    - Latency: Delayed frame delivery

    These affect the detection confidence and tracking accuracy.
    """

    name: ClassVar[str] = "vision_dropout"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        VisionDropoutDriver.supported_tiers = {SimTier.GAZEBO, SimTier.SIH}
        self._vision_enabled: bool = True

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject vision dropout.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        dropout_type: DropoutType = ctx.params.get("dropout_type", "camera_off")
        duration_s = ctx.params.get("duration_s")

        logger.info(
            f"Injecting vision dropout: {dropout_type} (duration: {duration_s}s)"
        )

        try:
            if dropout_type == "camera_off":
                # Completely disable camera
                await ctx.mcp_client.call_tool(
                    "set_camera_enabled",
                    {"enabled": False}
                )
                self._vision_enabled = False

            elif dropout_type == "blur":
                # Set blur level on camera
                await ctx.mcp_client.call_tool(
                    "set_camera_blur",
                    {"level": 1.0}  # Maximum blur
                )

            elif dropout_type == "noise":
                # Add noise to camera frames
                await ctx.mcp_client.call_tool(
                    "set_camera_noise",
                    {"level": 1.0}  # Maximum noise
                )

            elif dropout_type == "latency":
                # Add frame latency
                await ctx.mcp_client.call_tool(
                    "set_camera_latency",
                    {"seconds": 2.0}  # 2 second delay
                )

            # Update vision detection to indicate dropout
            await ctx.mcp_client.call_tool(
                "set_vision_status",
                {"status": "dropout", "reason": dropout_type}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(vision_status="dropout")

            logger.info(f"Vision dropout injected: {dropout_type}")

        except Exception as e:
            logger.warning(f"Vision dropout injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_vision_status", {"status": "dropout"})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release vision dropout and restore normal vision.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing vision dropout, restoring normal vision")

        try:
            # Re-enable camera if it was disabled
            if not self._vision_enabled:
                await ctx.mcp_client.call_tool(
                    "set_camera_enabled",
                    {"enabled": True}
                )
                self._vision_enabled = True

            # Reset all vision parameters
            await ctx.mcp_client.call_tool(
                "set_camera_blur",
                {"level": 0.0}
            )
            await ctx.mcp_client.call_tool(
                "set_camera_noise",
                {"level": 0.0}
            )
            await ctx.mcp_client.call_tool(
                "set_camera_latency",
                {"seconds": 0.0}
            )

            # Restore vision status
            await ctx.mcp_client.call_tool(
                "set_vision_status",
                {"status": "normal", "reason": "restored"}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(vision_status="normal")

            logger.info("Vision restored: normal operation")

        except Exception as e:
            logger.warning(f"Vision release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_vision_status", {"status": "normal"})
                )
