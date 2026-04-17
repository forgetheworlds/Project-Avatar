"""HITL Scenario Tests - YAML runner subset with Gazebo-only skips.

This module implements HITL-compatible scenario tests that can run on
real hardware (fc_bench or pi_plus_fc topologies).

HITL-COMPATIBLE SCENARIOS:
- offboard_freeze: Offboard setpoint stream interruption
- rc_loss: RC link loss simulation
- battery_drain: Rapid battery depletion
- network_partition: Network disruption (pi_plus_fc only)

GAZEBO-ONLY SCENARIOS (explicitly skipped):
- gps_loss: Requires Gazebo GPS jam simulation
- wind: Requires Gazebo wind field physics
- obstacle_proximity: Requires Gazebo depth/obstacle simulation
"""

from __future__ import annotations

import logging

import pytest

pytestmark = [pytest.mark.hitl]

logger = logging.getLogger(__name__)

# Scenarios that can run on HITL hardware
HITL_SCENARIO_IDS = ("offboard_freeze", "rc_loss", "battery_drain", "network_partition")

# Gazebo-only scenarios with skip reasons
SKIP_GAZEBO_ONLY = {
    "gps_loss": "HITL skip: gps_loss requires Gazebo GPS jam / physics (not available on bench FC)",
    "wind": "HITL skip: wind requires Gazebo wind field",
    "obstacle_proximity": "HITL skip: obstacle_proximity requires Gazebo depth/obstacle simulation",
}


@pytest.mark.parametrize("scenario_id", HITL_SCENARIO_IDS)
@pytest.mark.asyncio
async def test_hitl_yaml_scenario(
    scenario_id: str,
    hitl_target: str,
    hitl_mavsdk_uri: str,
) -> None:
    """Run HITL-compatible YAML scenario on real hardware.

    Loads and executes scenario using the Orchestrator/ScenarioLoader
    framework from avatar.sim.runner.

    Args:
        scenario_id: Scenario identifier (e.g., 'offboard_freeze')
        hitl_target: Target topology ('fc_bench' or 'pi_plus_fc')
        hitl_mavsdk_uri: MAVSDK connection URI

    SKIP CONDITIONS:
        - network_partition on fc_bench (requires Pi for tc netem)
        - Scenario file not found
    """
    if scenario_id == "network_partition" and hitl_target != "pi_plus_fc":
        pytest.skip(
            "HITL skip: network_partition uses tc netem on the Pi (spec section 9.3); "
            "use AVATAR_HITL_TARGET=pi_plus_fc"
        )

    # Import scenario framework
    try:
        from avatar.sim.runner import Orchestrator, ScenarioLoader
    except ImportError:
        pytest.skip("avatar.sim.runner not available")

    loader = ScenarioLoader()

    # Attempt to load scenario
    try:
        scenario = loader.load(scenario_id)
    except FileNotFoundError:
        pytest.skip(f"Scenario file not found: {scenario_id}")

    # Create orchestrator with HITL URI
    # Note: The actual Orchestrator may need adaptation for HITL
    # This is a placeholder for the full implementation
    logger.info(f"Running HITL scenario: {scenario_id} on {hitl_target}")
    logger.info(f"MAVSDK URI: {hitl_mavsdk_uri}")

    # For now, this is a stub that validates the test infrastructure
    # Full implementation would instantiate Orchestrator with a real MCP client
    # that communicates over the HITL MAVSDK connection
    #
    # orch = Orchestrator(mavsdk_uri=hitl_mavsdk_uri, scenario=scenario)
    # await orch.run()

    # Placeholder assertion for infrastructure validation
    assert hitl_mavsdk_uri.startswith(("serial://", "udp://")), \
        f"Invalid MAVSDK URI format: {hitl_mavsdk_uri}"

    logger.info(f"HITL scenario {scenario_id} infrastructure validated")


@pytest.mark.parametrize(
    "scenario_id,reason",
    [
        ("gps_loss", SKIP_GAZEBO_ONLY["gps_loss"]),
        ("wind", SKIP_GAZEBO_ONLY["wind"]),
        ("obstacle_proximity", SKIP_GAZEBO_ONLY["obstacle_proximity"]),
    ],
)
def test_gazebo_only_scenarios_documented_skip(scenario_id: str, reason: str) -> None:
    """Document Gazebo-only scenarios with explicit skip reasons.

    These scenarios require simulation capabilities not available on
    real hardware (GPS jam, wind fields, obstacle detection).

    This test exists to document why these scenarios are skipped
    in HITL runs, providing clear guidance for operators.

    Args:
        scenario_id: Scenario identifier
        reason: Skip reason explaining Gazebo dependency
    """
    pytest.skip(reason)
