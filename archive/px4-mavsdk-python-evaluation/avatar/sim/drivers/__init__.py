"""
Failure Injection Drivers for Scenario Testing.

This package contains drivers that simulate various failure conditions
during scenario execution. Each driver implements the Driver protocol
and can be triggered at specific times during scenario stages.

DRIVER PROTOCOL:
================
```python
class Driver(Protocol):
    name: str
    supported_tiers: set[SimTier]

    async def inject(self, ctx: DriverContext) -> None: ...
    async def release(self, ctx: DriverContext) -> None: ...
```

AVAILABLE DRIVERS:
==================
- WindDriver: Simulates wind gusts affecting flight stability
- GpsLossDriver: Simulates GPS signal loss
- VisionDropoutDriver: Simulates camera/vision system failures
- OffboardFreezeDriver: Simulates offboard mode command stream freeze
- BatteryDrainDriver: Simulates rapid battery depletion
- RcLossDriver: Simulates RC link loss
- ObstacleProximityDriver: Simulates obstacle detection events
- TargetMotionDriver: Simulates target movement patterns
- NetworkPartitionDriver: Simulates network disconnection

USAGE IN SCENARIOS:
===================
```yaml
injections:
  - at: { stage: orbit, t_offset_s: 5 }
    driver: gps_loss
    params: { duration_s: 10 }
```

The orchestrator will:
1. Wait for stage 'orbit' to start
2. Wait 5 seconds after stage start
3. Inject GPS loss for 10 seconds
4. Automatically release after duration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier


@runtime_checkable
class Driver(Protocol):
    """
    Protocol for failure injection drivers.

    Drivers implement specific failure scenarios that can be injected
    during scenario execution. Each driver must support:
    1. Injection: Apply the failure condition
    2. Release: Restore normal operation

    PROTOCOL REQUIREMENTS:
    ======================
    - name: Class attribute with driver identifier
    - supported_tiers: Class attribute listing compatible simulation tiers
    - inject(): Async method to apply failure
    - release(): Async method to restore normal state

    EXAMPLE IMPLEMENTATION:
    =======================
    ```python
    class GpsLossDriver:
        name = "gps_loss"
        supported_tiers = {SimTier.SIH, SimTier.GAZEBO}

        async def inject(self, ctx: DriverContext) -> None:
            # Set GPS timeout parameter to simulate loss
            await ctx.mcp_client.set_parameter("GPS_TIMEOUT", 0)
            logger.info("GPS signal lost")

        async def release(self, ctx: DriverContext) -> None:
            # Restore normal GPS timeout
            await ctx.mcp_client.set_parameter("GPS_TIMEOUT", 5)
            logger.info("GPS signal restored")
    ```
    """

    name: ClassVar[str]
    supported_tiers: ClassVar[set["SimTier"]]

    async def inject(self, ctx: "DriverContext") -> None:
        """Inject the failure condition.

        Args:
            ctx: Driver context with MCP client, telemetry, and params
        """
        ...

    async def release(self, ctx: "DriverContext") -> None:
        """Release the failure condition and restore normal operation.

        Args:
            ctx: Driver context with MCP client, telemetry, and params
        """
        ...


# =============================================================================
# DRIVER REGISTRATION
# =============================================================================

# Import drivers to register them
from avatar.sim.drivers.wind import WindDriver
from avatar.sim.drivers.gps_loss import GpsLossDriver
from avatar.sim.drivers.vision_dropout import VisionDropoutDriver
from avatar.sim.drivers.offboard_freeze import OffboardFreezeDriver
from avatar.sim.drivers.battery_drain import BatteryDrainDriver
from avatar.sim.drivers.rc_loss import RcLossDriver
from avatar.sim.drivers.obstacle_proximity import ObstacleProximityDriver
from avatar.sim.drivers.target_motion import TargetMotionDriver
from avatar.sim.drivers.network_partition import NetworkPartitionDriver

from avatar.sim.runner import DriverRegistry

# Register all drivers
DriverRegistry.register("wind", WindDriver)
DriverRegistry.register("gps_loss", GpsLossDriver)
DriverRegistry.register("vision_dropout", VisionDropoutDriver)
DriverRegistry.register("offboard_freeze", OffboardFreezeDriver)
DriverRegistry.register("battery_drain", BatteryDrainDriver)
DriverRegistry.register("rc_loss", RcLossDriver)
DriverRegistry.register("obstacle_proximity", ObstacleProximityDriver)
DriverRegistry.register("target_motion", TargetMotionDriver)
DriverRegistry.register("network_partition", NetworkPartitionDriver)


__all__ = [
    "Driver",
    "DriverRegistry",
    "WindDriver",
    "GpsLossDriver",
    "VisionDropoutDriver",
    "OffboardFreezeDriver",
    "BatteryDrainDriver",
    "RcLossDriver",
    "ObstacleProximityDriver",
    "TargetMotionDriver",
    "NetworkPartitionDriver",
]
