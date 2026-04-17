"""
Scenario Orchestration Framework for Project Avatar.

This module implements YAML-driven scenario runner with failure injection
for testing drone operations in simulation.

COMPONENTS:
===========
1. ScenarioLoader - Loads YAML scenario definitions
2. Orchestrator - Executes scenarios with stage sequencing
3. InjectionScheduler - Schedules failure injections at specified times
4. AssertionEngine - Validates scenario outcomes
5. ArtifactCollector - Collects test artifacts for analysis

YAML SCENARIO FORMAT:
====================
```yaml
id: scenario_name
kind: nature_cinematic | runner_follow | ...
description: "..."
backends: [mcp_stdio, mavsdk, ...]
sim:
  tier: sih | gazebo
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: {...} }
injections:
  - at: { stage: start_orbit, t_offset_s: 15 }
    driver: offboard_freeze
    params: { duration_s: 3 }
assertions:
  - within_s: 8
    expect: { state: [HOLD, RTL] }
```

DRIVER INTERFACE:
================
Drivers implement failure injection scenarios:
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
    from avatar.sim.runner import Orchestrator, ScenarioLoader

    loader = ScenarioLoader()
    scenario = loader.load("smoke_failsafe_rtl")

    orchestrator = Orchestrator(artifacts_dir="/tmp/artifacts")
    result = await orchestrator.run(scenario)

    if result.passed:
        print("Scenario passed!")
    else:
        print(f"Failed: {result.failures}")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND TYPE DEFINITIONS
# =============================================================================


class SimTier(str, Enum):
    """Simulation tier levels."""

    SIH = "sih"  # Software-In-Hardware (lightweight)
    GAZEBO = "gazebo"  # Full physics simulation


class ScenarioKind(str, Enum):
    """Scenario categories."""

    NATURE_CINEMATIC = "nature_cinematic"
    RUNNER_FOLLOW = "runner_follow"
    SAILBOAT_FOLLOW = "sailboat_follow"
    INDOOR_OBSTACLE = "indoor_obstacle"
    SMOKE_TEST = "smoke_test"
    ACROBATICS = "acrobatics"
    FAILSAFE = "failsafe"


class AssertionStatus(str, Enum):
    """Assertion result status."""

    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    ERROR = "error"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class StageDefinition:
    """A single stage in a scenario."""

    id: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    timeout_s: Optional[float] = None
    on_failure: str = "abort"  # abort | continue | skip


@dataclass
class InjectionTrigger:
    """When to trigger a failure injection."""

    stage: Optional[str] = None  # Trigger at start of this stage
    t_offset_s: float = 0.0  # Offset from stage start
    absolute_s: Optional[float] = None  # Absolute time from scenario start


@dataclass
class InjectionDefinition:
    """Failure injection configuration."""

    at: InjectionTrigger
    driver: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssertionDefinition:
    """Assertion to validate scenario outcome."""

    within_s: float = 10.0
    expect: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class ScenarioDefinition:
    """Complete scenario definition loaded from YAML."""

    id: str
    kind: ScenarioKind
    description: str
    backends: list[str] = field(default_factory=lambda: ["mcp_stdio", "mavsdk"])
    sim_tier: SimTier = SimTier.SIH
    stages: list[StageDefinition] = field(default_factory=list)
    injections: list[InjectionDefinition] = field(default_factory=list)
    assertions: list[AssertionDefinition] = field(default_factory=list)
    timeout_s: float = 300.0  # Total scenario timeout
    setup: list[dict[str, Any]] = field(default_factory=list)
    teardown: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StageResult:
    """Result of executing a single stage."""

    stage_id: str
    tool: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_s: float = 0.0


@dataclass
class InjectionResult:
    """Result of a failure injection."""

    driver: str
    success: bool
    params: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    inject_time_s: float = 0.0
    release_time_s: Optional[float] = None


@dataclass
class AssertionResult:
    """Result of an assertion check."""

    status: AssertionStatus
    expected: dict[str, Any]
    actual: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    elapsed_s: float = 0.0


@dataclass
class ScenarioResult:
    """Complete result of running a scenario."""

    scenario_id: str
    passed: bool
    stages: list[StageResult] = field(default_factory=list)
    injections: list[InjectionResult] = field(default_factory=list)
    assertions: list[AssertionResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    artifacts: list[str] = field(default_factory=list)


# =============================================================================
# SCENARIO LOADER
# =============================================================================


class ScenarioLoader:
    """
    Load scenario definitions from YAML files.

    SCENARIO SEARCH PATHS:
    1. Absolute path (if provided)
    2. avatar/sim/scenarios/<id>.yaml
    3. ./scenarios/<id>.yaml (relative to cwd)

    YAML SCHEMA:
    ```yaml
    id: scenario_name  # Required
    kind: smoke_test   # Required
    description: "..."  # Required

    backends: [mcp_stdio, mavsdk]  # Optional
    sim:
      tier: sih  # sih | gazebo

    stages:
      - id: takeoff
        tool: arm_and_takeoff
        args: { altitude: 10.0 }
        timeout_s: 30.0
        on_failure: abort

    injections:
      - at: { stage: orbit, t_offset_s: 5 }
        driver: gps_loss
        params: { duration_s: 10 }

    assertions:
      - within_s: 8
        expect: { state: [HOLD, RTL] }
        message: "Should enter failsafe"
    ```
    """

    SCENARIO_DIRS = [
        Path(__file__).parent / "scenarios",
        Path.cwd() / "scenarios",
    ]

    def __init__(self, scenario_dirs: Optional[list[Path]] = None):
        """
        Initialize loader with optional custom scenario directories.

        Args:
            scenario_dirs: Custom search paths for scenario files
        """
        self.scenario_dirs = scenario_dirs or self.SCENARIO_DIRS

    def load(self, scenario_id: str) -> ScenarioDefinition:
        """
        Load a scenario by ID.

        Args:
            scenario_id: Scenario identifier (matches filename without .yaml)

        Returns:
            ScenarioDefinition object

        Raises:
            FileNotFoundError: If scenario file not found
            ValueError: If scenario has invalid structure
        """
        yaml_path = self._find_scenario_file(scenario_id)
        logger.info(f"Loading scenario from: {yaml_path}")

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        return self._parse_scenario(data, yaml_path)

    def load_path(self, path: Union[str, Path]) -> ScenarioDefinition:
        """
        Load a scenario from an explicit path.

        Args:
            path: Path to YAML scenario file

        Returns:
            ScenarioDefinition object
        """
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        return self._parse_scenario(data, yaml_path)

    def list_scenarios(self) -> list[str]:
        """
        List all available scenario IDs.

        Returns:
            List of scenario IDs found in search paths
        """
        scenario_ids = set()

        for dir_path in self.scenario_dirs:
            if not dir_path.exists():
                continue
            for yaml_file in dir_path.glob("*.yaml"):
                scenario_ids.add(yaml_file.stem)
            for yaml_file in dir_path.glob("*.yml"):
                scenario_ids.add(yaml_file.stem)

        return sorted(scenario_ids)

    def _find_scenario_file(self, scenario_id: str) -> Path:
        """Find scenario file in search paths."""
        for dir_path in self.scenario_dirs:
            for ext in (".yaml", ".yml"):
                candidate = dir_path / f"{scenario_id}{ext}"
                if candidate.exists():
                    return candidate

        raise FileNotFoundError(
            f"Scenario '{scenario_id}' not found in: {[str(d) for d in self.scenario_dirs]}"
        )

    def _parse_scenario(
        self, data: dict[str, Any], source_path: Path
    ) -> ScenarioDefinition:
        """Parse YAML data into ScenarioDefinition."""
        # Required fields
        if "id" not in data:
            raise ValueError(f"Scenario missing 'id' field: {source_path}")
        if "kind" not in data:
            raise ValueError(f"Scenario missing 'kind' field: {source_path}")
        if "description" not in data:
            raise ValueError(f"Scenario missing 'description' field: {source_path}")

        # Parse kind
        try:
            kind = ScenarioKind(data["kind"])
        except ValueError:
            valid_kinds = [k.value for k in ScenarioKind]
            raise ValueError(
                f"Invalid kind '{data['kind']}'. Valid: {valid_kinds}"
            )

        # Parse simulation tier
        sim_data = data.get("sim", {})
        tier_str = sim_data.get("tier", "sih")
        try:
            sim_tier = SimTier(tier_str)
        except ValueError:
            valid_tiers = [t.value for t in SimTier]
            raise ValueError(f"Invalid tier '{tier_str}'. Valid: {valid_tiers}")

        # Parse stages
        stages = []
        for stage_data in data.get("stages", []):
            stages.append(self._parse_stage(stage_data))

        # Parse injections
        injections = []
        for inj_data in data.get("injections", []):
            injections.append(self._parse_injection(inj_data))

        # Parse assertions
        assertions = []
        for assert_data in data.get("assertions", []):
            assertions.append(self._parse_assertion(assert_data))

        return ScenarioDefinition(
            id=data["id"],
            kind=kind,
            description=data["description"],
            backends=data.get("backends", ["mcp_stdio", "mavsdk"]),
            sim_tier=sim_tier,
            stages=stages,
            injections=injections,
            assertions=assertions,
            timeout_s=float(data.get("timeout_s", 300.0)),
            setup=data.get("setup", []),
            teardown=data.get("teardown", []),
        )

    def _parse_stage(self, data: dict[str, Any]) -> StageDefinition:
        """Parse stage definition."""
        if "id" not in data:
            raise ValueError("Stage missing 'id' field")
        if "tool" not in data:
            raise ValueError(f"Stage '{data['id']}' missing 'tool' field")

        return StageDefinition(
            id=data["id"],
            tool=data["tool"],
            args=data.get("args", {}),
            timeout_s=data.get("timeout_s"),
            on_failure=data.get("on_failure", "abort"),
        )

    def _parse_injection(self, data: dict[str, Any]) -> InjectionDefinition:
        """Parse injection definition."""
        if "at" not in data:
            raise ValueError("Injection missing 'at' trigger")
        if "driver" not in data:
            raise ValueError("Injection missing 'driver' field")

        at_data = data["at"]
        trigger = InjectionTrigger(
            stage=at_data.get("stage"),
            t_offset_s=float(at_data.get("t_offset_s", 0.0)),
            absolute_s=at_data.get("absolute_s"),
        )

        return InjectionDefinition(
            at=trigger,
            driver=data["driver"],
            params=data.get("params", {}),
        )

    def _parse_assertion(self, data: dict[str, Any]) -> AssertionDefinition:
        """Parse assertion definition."""
        return AssertionDefinition(
            within_s=float(data.get("within_s", 10.0)),
            expect=data.get("expect", {}),
            message=data.get("message", ""),
        )


# =============================================================================
# DRIVER CONTEXT
# =============================================================================


@dataclass
class DriverContext:
    """
    Context passed to drivers during injection.

    Provides access to simulation state and MCP stdio interface.
    """

    scenario_id: str
    stage_id: Optional[str]
    sim_tier: SimTier
    start_time_s: float
    current_time_s: float
    mcp_client: Any  # MCP stdio client (mocked in unit tests)
    telemetry: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# DRIVER PROTOCOL AND REGISTRY
# =============================================================================


class DriverRegistry:
    """
    Registry for failure injection drivers.

    Drivers register themselves by name and can be looked up at runtime.
    """

    _drivers: dict[str, Any] = {}  # type: ignore

    @classmethod
    def register(cls, name: str, driver_class: Any) -> None:
        """Register a driver class by name."""
        cls._drivers[name] = driver_class
        logger.debug(f"Registered driver: {name}")

    @classmethod
    def get(cls, name: str) -> Any:
        """Get a driver class by name."""
        if name not in cls._drivers:
            raise ValueError(f"Unknown driver: {name}. Available: {list(cls._drivers.keys())}")
        return cls._drivers[name]

    @classmethod
    def list_drivers(cls) -> list[str]:
        """List registered driver names."""
        return sorted(cls._drivers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered drivers (for testing)."""
        cls._drivers.clear()


# =============================================================================
# MOCK MCP CLIENT FOR TESTING
# =============================================================================


class MockMcpClient:
    """
    Mock MCP stdio client for unit testing drivers.

    Provides a simplified interface that records commands for inspection
    in tests without requiring actual MCP transport.

    USAGE IN TESTS:
    ===============
    ```python
    mock_mcp = MockMcpClient()

    # Configure responses
    mock_mcp.set_response("get_telemetry", {"battery": 85.0})

    # Use in driver context
    ctx = DriverContext(..., mcp_client=mock_mcp)

    # Inspect calls after injection
    assert mock_mcp.calls[0] == ("set_parameter", {"name": "GPS_TIMEOUT", "value": 0})
    ```
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.responses: dict[str, dict[str, Any]] = {}
        self._state: dict[str, Any] = {
            "flight_mode": "OFFBOARD",
            "armed": True,
            "in_air": True,
            "battery_percent": 85.0,
            "gps_satellites": 12,
            "home_lat": 37.7749,
            "home_lon": -122.4194,
            "latitude": 37.7750,
            "longitude": -122.4195,
            "altitude_amsl_m": 50.0,
            "speed_m_s": 5.0,
            "vx_m_s": 2.0,
            "vy_m_s": 0.0,
            "vz_m_s": 0.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": 90.0,
        }

    def set_response(self, tool: str, response: dict[str, Any]) -> None:
        """Set a canned response for a tool call."""
        self.responses[tool] = response

    def set_state(self, **kwargs: Any) -> None:
        """Update simulated drone state."""
        self._state.update(kwargs)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Mock tool call - records call and returns canned response."""
        self.calls.append((name, arguments.copy()))

        # Check for canned response
        if name in self.responses:
            return self.responses[name]

        # Handle state queries
        if name == "get_telemetry":
            return {"status": "success", "data": self._state.copy()}
        if name == "get_status":
            return {"status": "success", "state": self._state.copy()}

        # Default success response
        return {"status": "success"}

    async def set_parameter(self, param_name: str, value: Any) -> dict[str, Any]:
        """Mock parameter set via PX4 param tool."""
        return await self.call_tool("set_parameter", {"name": param_name, "value": value})

    async def inject_failure(self, failure_type: str, **params: Any) -> dict[str, Any]:
        """Mock failure injection."""
        return await self.call_tool(f"inject_{failure_type}", params)

    async def release_failure(self, failure_type: str) -> dict[str, Any]:
        """Mock failure release."""
        return await self.call_tool(f"release_{failure_type}", {})

    def get_state(self) -> dict[str, Any]:
        """Get current simulated state."""
        return self._state.copy()

    def clear_calls(self) -> None:
        """Clear recorded calls."""
        self.calls.clear()


# =============================================================================
# INJECTION SCHEDULER
# =============================================================================


class InjectionScheduler:
    """
    Schedule and execute failure injections during scenarios.

    SCHEDULING MODES:
    =================
    1. Stage-relative: Trigger at offset from stage start
       ```yaml
       injections:
         - at: { stage: orbit, t_offset_s: 5 }
           driver: gps_loss
       ```

    2. Absolute time: Trigger at specific time from scenario start
       ```yaml
       injections:
         - at: { absolute_s: 30 }
           driver: wind
       ```

    EXECUTION FLOW:
    ===============
    1. Schedule all injections at scenario start
    2. Monitor stage transitions and time elapsed
    3. Execute injection when trigger condition met
    4. Track active injections for cleanup
    """

    def __init__(self) -> None:
        self._scheduled: list[tuple[InjectionDefinition, asyncio.Task[None]]] = []
        self._active: dict[str, Any] = {}  # driver_name -> driver instance
        self._scenario_start_s: float = 0.0
        self._stage_starts: dict[str, float] = {}
        self._current_stage: Optional[str] = None

    def reset(self) -> None:
        """Reset scheduler state."""
        # Cancel all pending tasks
        for _, task in self._scheduled:
            task.cancel()
        self._scheduled.clear()
        self._active.clear()
        self._stage_starts.clear()
        self._current_stage = None

    def schedule(
        self,
        injections: list[InjectionDefinition],
        mcp_client: Any,
        sim_tier: SimTier,
        scenario_start_s: float,
    ) -> None:
        """
        Schedule all injections for a scenario.

        Args:
            injections: List of injection definitions
            mcp_client: MCP stdio client (real or mock)
            sim_tier: Simulation tier (for driver compatibility check)
            scenario_start_s: Scenario start timestamp
        """
        self.reset()
        self._scenario_start_s = scenario_start_s

        for inj in injections:
            # Create async task for each injection
            task = asyncio.create_task(
                self._schedule_injection(inj, mcp_client, sim_tier)
            )
            self._scheduled.append((inj, task))

    def notify_stage_start(self, stage_id: str, timestamp_s: float) -> None:
        """Notify scheduler that a stage has started."""
        self._stage_starts[stage_id] = timestamp_s
        self._current_stage = stage_id

    async def _schedule_injection(
        self,
        inj: InjectionDefinition,
        mcp_client: Any,
        sim_tier: SimTier,
    ) -> None:
        """Execute a single injection at scheduled time."""
        # Calculate delay
        if inj.at.absolute_s is not None:
            # Absolute time from scenario start
            delay_s = inj.at.absolute_s - (time.time() - self._scenario_start_s)
        elif inj.at.stage is not None:
            # Wait for stage to start, then apply offset
            while inj.at.stage not in self._stage_starts:
                await asyncio.sleep(0.1)
                if time.time() - self._scenario_start_s > 600:  # Safety timeout
                    logger.error(f"Timeout waiting for stage: {inj.at.stage}")
                    return

            stage_start = self._stage_starts[inj.at.stage]
            target_time = stage_start + inj.at.t_offset_s
            delay_s = target_time - time.time()
        else:
            # Immediate injection
            delay_s = inj.at.t_offset_s

        # Wait for trigger time
        if delay_s > 0:
            logger.debug(f"Waiting {delay_s:.1f}s for injection: {inj.driver}")
            await asyncio.sleep(delay_s)

        # Get driver and check compatibility
        driver_class = DriverRegistry.get(inj.driver)
        driver = driver_class()

        # Check tier compatibility
        if sim_tier not in driver.supported_tiers:
            logger.warning(
                f"Driver {inj.driver} not compatible with tier {sim_tier}, skipping"
            )
            return

        # Create context
        ctx = DriverContext(
            scenario_id="",
            stage_id=self._current_stage,
            sim_tier=sim_tier,
            start_time_s=self._scenario_start_s,
            current_time_s=time.time(),
            mcp_client=mcp_client,
            params=inj.params,
        )

        # Inject
        logger.info(f"Injecting failure: {inj.driver}")
        self._active[inj.driver] = driver

        try:
            await driver.inject(ctx)
        except Exception as e:
            logger.error(f"Injection failed: {inj.driver}: {e}")

        # Wait for duration if specified
        duration_s = inj.params.get("duration_s")
        if duration_s:
            await asyncio.sleep(duration_s)
            await driver.release(ctx)

        # Remove from active
        self._active.pop(inj.driver, None)

    async def release_all(self) -> None:
        """Release all active injections."""
        for driver_name, driver in list(self._active.items()):
            logger.info(f"Releasing injection: {driver_name}")
            try:
                ctx = DriverContext(
                    scenario_id="",
                    stage_id=self._current_stage,
                    sim_tier=SimTier.SIH,
                    start_time_s=self._scenario_start_s,
                    current_time_s=time.time(),
                    mcp_client=MockMcpClient(),
                    params={},
                )
                await driver.release(ctx)
            except Exception as e:
                logger.error(f"Release failed: {driver_name}: {e}")

        self._active.clear()


# =============================================================================
# ASSERTION ENGINE
# =============================================================================


class AssertionEngine:
    """
    Validate scenario outcomes against assertions.

    ASSERTION TYPES:
    ================
    1. State assertions: Check flight mode, armed state, etc.
       ```yaml
       assertions:
         - expect: { state: [HOLD, RTL] }
       ```

    2. Telemetry assertions: Check altitude, speed, battery
       ```yaml
       assertions:
         - expect: { battery_percent: { min: 20 } }
       ```

    3. Sequence assertions: Check stage completion order
       ```yaml
       assertions:
         - expect: { stages_completed: [takeoff, orbit, land] }
       ```

    VALIDATION FLOW:
    ================
    1. Monitor telemetry/state continuously
    2. Check each assertion within specified timeout
    3. Report pass/fail with actual vs expected values
    """

    def __init__(self) -> None:
        self._telemetry: dict[str, Any] = {}
        self._flight_state: dict[str, Any] = {}
        self._completed_stages: list[str] = []

    def update_telemetry(self, telemetry: dict[str, Any]) -> None:
        """Update current telemetry snapshot."""
        self._telemetry.update(telemetry)

    def update_flight_state(self, state: dict[str, Any]) -> None:
        """Update current flight state."""
        self._flight_state.update(state)

    def notify_stage_complete(self, stage_id: str) -> None:
        """Record completed stage."""
        self._completed_stages.append(stage_id)

    async def check_assertion(
        self,
        assertion: AssertionDefinition,
        mcp_client: Any,
        start_time_s: float,
    ) -> AssertionResult:
        """
        Check a single assertion within timeout.

        Args:
            assertion: Assertion definition to check
            mcp_client: MCP client for querying state
            start_time_s: When assertion checking started

        Returns:
            AssertionResult with pass/fail status
        """
        deadline = start_time_s + assertion.within_s

        while time.time() < deadline:
            # Get current state
            try:
                result = await mcp_client.call_tool("get_status", {})
                current_state = result.get("state", {})
            except Exception as e:
                logger.debug(f"Failed to get state: {e}")
                await asyncio.sleep(0.5)
                continue

            # Check each expectation
            all_match = True
            for key, expected in assertion.expect.items():
                actual = current_state.get(key)

                if isinstance(expected, list):
                    # Expected is a list of acceptable values
                    if actual not in expected:
                        all_match = False
                        break
                elif isinstance(expected, dict):
                    # Expected is a constraint dict (min, max, etc.)
                    if not self._check_constraint(actual, expected):
                        all_match = False
                        break
                else:
                    # Expected is an exact value
                    if actual != expected:
                        all_match = False
                        break

            if all_match:
                return AssertionResult(
                    status=AssertionStatus.PASS,
                    expected=assertion.expect,
                    actual=current_state,
                    message=assertion.message,
                    elapsed_s=time.time() - start_time_s,
                )

            await asyncio.sleep(0.5)

        # Timeout - assertion failed
        try:
            result = await mcp_client.call_tool("get_status", {})
            actual = result.get("state", {})
        except Exception:
            actual = {}

        return AssertionResult(
            status=AssertionStatus.TIMEOUT,
            expected=assertion.expect,
            actual=actual,
            message=f"Assertion timed out after {assertion.within_s}s: {assertion.message}",
            elapsed_s=time.time() - start_time_s,
        )

    def _check_constraint(self, value: Any, constraint: dict[str, Any]) -> bool:
        """Check if value satisfies constraint dict."""
        if value is None:
            return False

        if "min" in constraint and value < constraint["min"]:
            return False
        if "max" in constraint and value > constraint["max"]:
            return False
        if "equals" in constraint and value != constraint["equals"]:
            return False

        return True


# =============================================================================
# ARTIFACT COLLECTOR
# =============================================================================


class ArtifactCollector:
    """
    Collect and store test artifacts during scenario execution.

    ARTIFACT TYPES:
    ================
    1. Telemetry logs: JSON files with telemetry snapshots
    2. Result files: Scenario pass/fail status
    3. Debug logs: Detailed execution traces
    4. Screenshots: Camera frames (if vision active)

    OUTPUT STRUCTURE:
    =================
    artifacts/
    └── <run_id>/
        ├── result.json          # Scenario result summary
        ├── telemetry.jsonl      # Telemetry log (JSON Lines)
        ├── stages.json          # Stage execution log
        ├── injections.json      # Injection log
        └── assertions.json      # Assertion results
    """

    def __init__(self, artifacts_dir: Path, run_id: str) -> None:
        """
        Initialize collector with output directory.

        Args:
            artifacts_dir: Base artifacts directory
            run_id: Unique run identifier
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.run_dir = artifacts_dir / run_id
        self._telemetry_log: list[dict[str, Any]] = []
        self._start_time: float = time.time()

    def setup(self) -> None:
        """Create artifact directories."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Artifacts directory: {self.run_dir}")

    def record_telemetry(self, telemetry: dict[str, Any]) -> None:
        """Record a telemetry snapshot."""
        entry = {
            "timestamp_s": time.time() - self._start_time,
            "data": telemetry,
        }
        self._telemetry_log.append(entry)

    def save_result(self, result: ScenarioResult) -> None:
        """Save scenario result to JSON."""
        result_path = self.run_dir / "result.json"

        output = {
            "scenario_id": result.scenario_id,
            "passed": result.passed,
            "failures": result.failures,
            "duration_s": result.duration_s,
            "stages": [
                {
                    "stage_id": sr.stage_id,
                    "tool": sr.tool,
                    "success": sr.success,
                    "error": sr.error,
                    "duration_s": sr.duration_s,
                }
                for sr in result.stages
            ],
            "injections": [
                {
                    "driver": ir.driver,
                    "success": ir.success,
                    "error": ir.error,
                }
                for ir in result.injections
            ],
            "assertions": [
                {
                    "status": ar.status.value,
                    "expected": ar.expected,
                    "actual": ar.actual,
                    "message": ar.message,
                }
                for ar in result.assertions
            ],
        }

        with open(result_path, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Result saved: {result_path}")

    def save_telemetry_log(self) -> None:
        """Save telemetry log to JSONL file."""
        if not self._telemetry_log:
            return

        log_path = self.run_dir / "telemetry.jsonl"

        with open(log_path, "w") as f:
            for entry in self._telemetry_log:
                f.write(json.dumps(entry) + "\n")

        logger.info(f"Telemetry log saved: {log_path} ({len(self._telemetry_log)} entries)")

    def save_artifact(self, name: str, content: str | bytes) -> Path:
        """
        Save a custom artifact file.

        Args:
            name: Artifact filename
            content: File content (string or bytes)

        Returns:
            Path to saved artifact
        """
        artifact_path = self.run_dir / name

        if isinstance(content, bytes):
            with open(artifact_path, "wb") as f:
                f.write(content)
        else:
            with open(artifact_path, "w") as f:
                f.write(content)

        logger.info(f"Artifact saved: {artifact_path}")
        return artifact_path

    def list_artifacts(self) -> list[str]:
        """List collected artifact filenames."""
        if not self.run_dir.exists():
            return []
        return [f.name for f in self.run_dir.iterdir() if f.is_file()]

    def teardown(self) -> None:
        """Finalize and close artifact collection."""
        self.save_telemetry_log()


# =============================================================================
# ORCHESTRATOR
# =============================================================================


class Orchestrator:
    """
    Execute scenarios with stage sequencing, failure injection, and validation.

    ORCHESTRATION FLOW:
    ===================
    1. Load scenario definition
    2. Setup artifact collection
    3. Execute stages in order
    4. Schedule failure injections
    5. Validate assertions
    6. Collect and report results

    USAGE:
    ======
    ```python
    loader = ScenarioLoader()
    scenario = loader.load("smoke_failsafe_rtl")

    orchestrator = Orchestrator(
        artifacts_dir=Path("/tmp/artifacts"),
        run_id="test_001",
    )

    result = await orchestrator.run(scenario)

    if result.passed:
        print("SUCCESS")
    else:
        print(f"FAILED: {result.failures}")
    ```
    """

    def __init__(
        self,
        artifacts_dir: Path,
        run_id: str,
        mcp_client: Optional[Any] = None,
    ) -> None:
        """
        Initialize orchestrator.

        Args:
            artifacts_dir: Directory for test artifacts
            run_id: Unique run identifier
            mcp_client: MCP stdio client (uses mock if not provided)
        """
        self.artifacts_dir = Path(artifacts_dir)
        self.run_id = run_id
        self.mcp_client = mcp_client or MockMcpClient()

        self.loader = ScenarioLoader()
        self.scheduler = InjectionScheduler()
        self.assertion_engine = AssertionEngine()
        self.collector: Optional[ArtifactCollector] = None

    async def run(self, scenario: ScenarioDefinition) -> ScenarioResult:
        """
        Execute a scenario.

        Args:
            scenario: Scenario definition to execute

        Returns:
            ScenarioResult with pass/fail status and details
        """
        start_time = time.time()

        # Setup artifact collection
        self.collector = ArtifactCollector(self.artifacts_dir, self.run_id)
        self.collector.setup()

        # Initialize result
        result = ScenarioResult(
            scenario_id=scenario.id,
            passed=False,
            failures=[],
        )

        logger.info(f"Starting scenario: {scenario.id}")
        logger.info(f"Description: {scenario.description}")

        try:
            # Run with overall timeout
            async with asyncio.timeout(scenario.timeout_s):
                await self._execute_scenario(scenario, result)

        except asyncio.TimeoutError:
            result.failures.append(f"Scenario timeout after {scenario.timeout_s}s")

        except Exception as e:
            result.failures.append(f"Scenario error: {e}")
            logger.exception(f"Scenario failed: {e}")

        finally:
            # Calculate duration
            result.duration_s = time.time() - start_time

            # Release any active injections
            await self.scheduler.release_all()

            # Save artifacts
            if self.collector:
                self.collector.save_result(result)
                self.collector.teardown()
                result.artifacts = self.collector.list_artifacts()

        # Determine pass/fail
        result.passed = len(result.failures) == 0 and all(
            ar.status == AssertionStatus.PASS for ar in result.assertions
        )

        logger.info(f"Scenario {scenario.id} {'PASSED' if result.passed else 'FAILED'}")
        return result

    async def _execute_scenario(
        self,
        scenario: ScenarioDefinition,
        result: ScenarioResult,
    ) -> None:
        """Execute scenario stages, injections, and assertions."""
        start_time = time.time()

        # Schedule injections
        self.scheduler.schedule(
            scenario.injections,
            self.mcp_client,
            scenario.sim_tier,
            start_time,
        )

        # Execute stages
        for stage in scenario.stages:
            stage_start = time.time()

            # Notify scheduler of stage start
            self.scheduler.notify_stage_start(stage.id, stage_start)

            logger.info(f"Stage: {stage.id} - {stage.tool}")

            try:
                # Execute stage tool
                stage_result = await self._execute_stage(stage)
                result.stages.append(stage_result)

                # Notify assertion engine
                self.assertion_engine.notify_stage_complete(stage.id)

                # Handle stage failure
                if not stage_result.success:
                    if stage.on_failure == "abort":
                        result.failures.append(
                            f"Stage '{stage.id}' failed: {stage_result.error}"
                        )
                        break
                    elif stage.on_failure == "continue":
                        logger.warning(
                            f"Stage '{stage.id}' failed, continuing: {stage_result.error}"
                        )

            except asyncio.TimeoutError:
                error_msg = f"Stage '{stage.id}' timed out"
                result.failures.append(error_msg)
                result.stages.append(
                    StageResult(
                        stage_id=stage.id,
                        tool=stage.tool,
                        success=False,
                        error=error_msg,
                    )
                )
                if stage.on_failure == "abort":
                    break

        # Check assertions
        for assertion in scenario.assertions:
            assertion_result = await self.assertion_engine.check_assertion(
                assertion,
                self.mcp_client,
                start_time,
            )
            result.assertions.append(assertion_result)

            if assertion_result.status != AssertionStatus.PASS:
                result.failures.append(assertion_result.message)

    async def _execute_stage(self, stage: StageDefinition) -> StageResult:
        """Execute a single stage."""
        start_time = time.time()

        try:
            # Call MCP tool
            output = await self.mcp_client.call_tool(stage.tool, stage.args)

            duration_s = time.time() - start_time

            return StageResult(
                stage_id=stage.id,
                tool=stage.tool,
                success=output.get("status") != "error",
                output=output,
                duration_s=duration_s,
            )

        except Exception as e:
            return StageResult(
                stage_id=stage.id,
                tool=stage.tool,
                success=False,
                error=str(e),
                duration_s=time.time() - start_time,
            )


# =============================================================================
# MAIN ENTRY POINT (CLI)
# =============================================================================


async def run_scenario(
    scenario_id: str,
    artifacts_dir: str,
    mcp_client: Optional[Any] = None,
) -> ScenarioResult:
    """
    Run a scenario by ID.

    Args:
        scenario_id: Scenario to run
        artifacts_dir: Directory for artifacts
        mcp_client: Optional MCP client (uses mock if not provided)

    Returns:
        ScenarioResult
    """
    loader = ScenarioLoader()
    scenario = loader.load(scenario_id)

    run_id = f"{scenario_id}_{int(time.time())}"

    orchestrator = Orchestrator(
        artifacts_dir=Path(artifacts_dir),
        run_id=run_id,
        mcp_client=mcp_client,
    )

    return await orchestrator.run(scenario)


def main() -> int:
    """CLI entry point for scenario runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Run simulation scenarios")
    parser.add_argument(
        "--scenario",
        "-s",
        required=True,
        help="Scenario ID to run",
    )
    parser.add_argument(
        "--artifacts",
        "-a",
        default="./artifacts",
        help="Artifacts output directory",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available scenarios",
    )

    args = parser.parse_args()

    if args.list:
        loader = ScenarioLoader()
        scenarios = loader.list_scenarios()
        print("Available scenarios:")
        for s in scenarios:
            print(f"  - {s}")
        return 0

    # Run scenario
    result = asyncio.run(run_scenario(args.scenario, args.artifacts))

    print(f"\nScenario: {result.scenario_id}")
    print(f"Status: {'PASSED' if result.passed else 'FAILED'}")
    print(f"Duration: {result.duration_s:.1f}s")

    if result.failures:
        print("\nFailures:")
        for f in result.failures:
            print(f"  - {f}")

    if result.artifacts:
        print(f"\nArtifacts: {result.artifacts}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    exit(main())
