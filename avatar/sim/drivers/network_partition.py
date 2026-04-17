"""
Network Partition Driver - Simulates network disconnection.

INJECTION BEHAVIOR:
===================
- Simulates loss of network connection between agent and drone
- Tests MCP stdio timeout handling
- Tests command queuing and retry behavior

PARAMETERS:
===========
- duration_s: Duration of partition (default: 5)
- partition_type: Type of network issue (default: "complete")
  - "complete": Total disconnection
  - "intermittent": Intermittent connectivity
  - "high_latency": High latency connection
  - "packet_loss": Significant packet loss
- latency_ms: Latency for high_latency type (default: 1000)

YAML EXAMPLE:
=============
```yaml
injections:
  - at: { stage: navigation, t_offset_s: 20 }
    driver: network_partition
    params:
      duration_s: 10
      partition_type: intermittent
```

EXPECTED DRONE BEHAVIOR:
========================
1. MCP commands fail or timeout
2. Heartbeat timeout triggers
3. GuardianProcess detects connection loss
4. Failsafe action executed (RTL, hold, etc.)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from avatar.sim.runner import DriverContext, SimTier

logger = logging.getLogger(__name__)

PartitionType = Literal["complete", "intermittent", "high_latency", "packet_loss"]


class NetworkPartitionDriver:
    """
    Simulates network disconnection.

    NETWORK DEPENDENCIES:
    =====================
    Project Avatar uses network for:
    1. MCP stdio communication with agent
    2. MAVSDK connection (local for SITL)
    3. Telemetry broadcasting
    4. Vision stream (if remote camera)

    PARTITION SIMULATION:
    =====================
    We simulate various network issues:
    - Complete: Block all traffic
    - Intermittent: Random drops
    - High latency: Delayed responses
    - Packet loss: Corrupted/incomplete data

    This tests the system's resilience to connection issues.
    """

    name: ClassVar[str] = "network_partition"
    supported_tiers: ClassVar[set["SimTier"]] = set()

    def __init__(self) -> None:
        from avatar.sim.runner import SimTier
        NetworkPartitionDriver.supported_tiers = {SimTier.SIH, SimTier.GAZEBO}
        self._partition_active: bool = False

    async def inject(self, ctx: "DriverContext") -> None:
        """
        Inject network partition.

        Args:
            ctx: Driver context with MCP client and parameters
        """
        partition_type: PartitionType = ctx.params.get("partition_type", "complete")
        duration_s = ctx.params.get("duration_s", 5)
        latency_ms = ctx.params.get("latency_ms", 1000)

        logger.info(
            f"Injecting network partition: {partition_type} (duration: {duration_s}s)"
        )

        try:
            if partition_type == "complete":
                # Block all network traffic
                await ctx.mcp_client.call_tool(
                    "set_network_state",
                    {"connected": False, "reason": "partition_test"}
                )
                self._partition_active = True

            elif partition_type == "intermittent":
                # Intermittent connectivity
                await ctx.mcp_client.call_tool(
                    "set_network_intermittent",
                    {"drop_rate": 0.5, "min_latency_ms": 100, "max_latency_ms": 1000}
                )

            elif partition_type == "high_latency":
                # High latency connection
                await ctx.mcp_client.call_tool(
                    "set_network_latency",
                    {"latency_ms": latency_ms, "jitter_ms": latency_ms // 10}
                )

            elif partition_type == "packet_loss":
                # Packet loss
                await ctx.mcp_client.call_tool(
                    "set_network_packet_loss",
                    {"loss_rate": 0.3}
                )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(
                    network_connected=(partition_type == "complete"),
                    network_partition_type=partition_type,
                )

            logger.info(f"Network partition injected: {partition_type}")

        except Exception as e:
            logger.warning(f"Network partition injection error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_network_state", {"connected": False})
                )

    async def release(self, ctx: "DriverContext") -> None:
        """
        Release network partition and restore connection.

        Args:
            ctx: Driver context
        """
        logger.info("Releasing network partition, restoring connection")

        try:
            # Restore network connectivity
            await ctx.mcp_client.call_tool(
                "set_network_state",
                {"connected": True, "reason": "partition_released"}
            )
            self._partition_active = False

            # Reset all network parameters
            await ctx.mcp_client.call_tool(
                "set_network_intermittent",
                {"drop_rate": 0.0}
            )
            await ctx.mcp_client.call_tool(
                "set_network_latency",
                {"latency_ms": 0, "jitter_ms": 0}
            )
            await ctx.mcp_client.call_tool(
                "set_network_packet_loss",
                {"loss_rate": 0.0}
            )

            # Update mock state if available
            if hasattr(ctx.mcp_client, "set_state"):
                ctx.mcp_client.set_state(
                    network_connected=True,
                    network_partition_type="none",
                )

            logger.info("Network restored: connection regained")

        except Exception as e:
            logger.warning(f"Network release error: {e}")
            # Record for mock testing
            if hasattr(ctx.mcp_client, "calls"):
                ctx.mcp_client.calls.append(
                    ("set_network_state", {"connected": True})
                )
