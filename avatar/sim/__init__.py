"""
Simulation scenario catalog for Project Avatar.

This module provides YAML-driven scenario orchestration with failure injection
for testing drone operations in simulation.

MAIN COMPONENTS:
================
- ScenarioLoader: Load scenario definitions from YAML
- Orchestrator: Execute scenarios with stage sequencing
- InjectionScheduler: Schedule failure injections
- AssertionEngine: Validate scenario outcomes
- ArtifactCollector: Collect test artifacts
- DriverRegistry: Registry for failure injection drivers

DRIVERS:
========
Drivers implement failure injection scenarios. See avatar.sim.drivers for:
- WindDriver: Simulates wind gusts
- GpsLossDriver: Simulates GPS signal loss
- VisionDropoutDriver: Simulates camera/vision failures
- OffboardFreezeDriver: Simulates offboard mode failures
- BatteryDrainDriver: Simulates rapid battery depletion
- RcLossDriver: Simulates RC link loss
- ObstacleProximityDriver: Simulates obstacle detection
- TargetMotionDriver: Simulates target movement
- NetworkPartitionDriver: Simulates network disconnection

USAGE:
======
    from avatar.sim import ScenarioLoader, Orchestrator

    loader = ScenarioLoader()
    scenario = loader.load("smoke_failsafe_rtl")

    orchestrator = Orchestrator(artifacts_dir=Path("./artifacts"), run_id="test_001")
    result = await orchestrator.run(scenario)

    if result.passed:
        print("SUCCESS")
"""

from avatar.sim.runner import (
    # Enums
    AssertionStatus,
    ScenarioKind,
    SimTier,
    # Data classes
    AssertionDefinition,
    AssertionResult,
    ArtifactCollector,
    DriverContext,
    InjectionDefinition,
    InjectionResult,
    InjectionTrigger,
    ScenarioDefinition,
    ScenarioResult,
    StageDefinition,
    StageResult,
    # Main classes
    AssertionEngine,
    DriverRegistry,
    MockMcpClient,
    Orchestrator,
    ScenarioLoader,
    InjectionScheduler,
    # Functions
    run_scenario,
)
from avatar.sim.drivers import (
    Driver,
    WindDriver,
    GpsLossDriver,
    OffboardFreezeDriver,
    VisionDropoutDriver,
    BatteryDrainDriver,
    RcLossDriver,
    ObstacleProximityDriver,
    TargetMotionDriver,
    NetworkPartitionDriver,
)
from avatar.sim.scenarios import SCENARIOS, SimulationScenario, get_scenario, list_scenarios

__all__ = [
    # Enums
    "AssertionStatus",
    "ScenarioKind",
    "SimTier",
    # Data classes
    "AssertionDefinition",
    "AssertionResult",
    "ArtifactCollector",
    "DriverContext",
    "InjectionDefinition",
    "InjectionResult",
    "InjectionTrigger",
    "ScenarioDefinition",
    "ScenarioResult",
    "StageDefinition",
    "StageResult",
    # Main classes
    "AssertionEngine",
    "DriverRegistry",
    "MockMcpClient",
    "Orchestrator",
    "ScenarioLoader",
    "InjectionScheduler",
    # Functions
    "run_scenario",
    # Driver protocol and implementations
    "Driver",
    "WindDriver",
    "GpsLossDriver",
    "OffboardFreezeDriver",
    "VisionDropoutDriver",
    "BatteryDrainDriver",
    "RcLossDriver",
    "ObstacleProximityDriver",
    "TargetMotionDriver",
    "NetworkPartitionDriver",
    # Legacy scenario support
    "SCENARIOS",
    "SimulationScenario",
    "get_scenario",
    "list_scenarios",
]
