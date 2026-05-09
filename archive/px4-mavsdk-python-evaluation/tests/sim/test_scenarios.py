"""
Tests for scenario orchestration framework.

Tests cover:
1. ScenarioLoader - YAML parsing and validation
2. Orchestrator - Scenario execution
3. Drivers - Failure injection (mocked MCP)
4. AssertionEngine - Outcome validation
5. ArtifactCollector - Artifact collection
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from avatar.sim import (
    AssertionDefinition,
    AssertionEngine,
    AssertionStatus,
    AssertionResult,
    ArtifactCollector,
    DriverContext,
    DriverRegistry,
    InjectionDefinition,
    InjectionScheduler,
    InjectionTrigger,
    MockMcpClient,
    Orchestrator,
    ScenarioDefinition,
    ScenarioKind,
    ScenarioLoader,
    ScenarioResult,
    SimTier,
    StageDefinition,
    StageResult,
    run_scenario,
    # Drivers
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
from avatar.sim.scenarios import SCENARIOS, get_scenario, list_scenarios


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_mcp_client() -> MockMcpClient:
    """Create a mock MCP client for testing."""
    return MockMcpClient()


@pytest.fixture
def sample_scenario_yaml(tmp_path: Path) -> Path:
    """Create a sample scenario YAML file."""
    yaml_content = """
id: test_scenario
kind: smoke_test
description: "Test scenario for unit testing"

backends:
  - mcp_stdio
  - mavsdk

sim:
  tier: sih

timeout_s: 60

stages:
  - id: takeoff
    tool: arm_and_takeoff
    args:
      altitude: 10.0
    timeout_s: 30
    on_failure: abort

injections:
  - at:
      stage: takeoff
      t_offset_s: 5
    driver: gps_loss
    params:
      duration_s: 10

assertions:
  - within_s: 8
    expect:
      flight_mode: [HOLD, RTL]
    message: "Should enter safe mode"
"""
    yaml_path = tmp_path / "test_scenario.yaml"
    yaml_path.write_text(yaml_content)
    return yaml_path


@pytest.fixture
def sample_scenario_def() -> ScenarioDefinition:
    """Create a sample scenario definition for testing."""
    return ScenarioDefinition(
        id="test_scenario",
        kind=ScenarioKind.SMOKE_TEST,
        description="Test scenario for unit testing",
        stages=[
            StageDefinition(
                id="takeoff",
                tool="arm_and_takeoff",
                args={"altitude": 10.0},
                timeout_s=30,
            ),
            StageDefinition(
                id="hover",
                tool="hold",
                args={},
            ),
        ],
        injections=[
            InjectionDefinition(
                at=InjectionTrigger(stage="hover", t_offset_s=5.0),
                driver="gps_loss",
                params={"duration_s": 10},
            ),
        ],
        assertions=[
            AssertionDefinition(
                within_s=8.0,
                expect={"flight_mode": ["HOLD", "RTL"]},
                message="Should enter safe mode",
            ),
        ],
    )


# =============================================================================
# LEGACY TESTS (preserved from original file)
# =============================================================================


def test_scenario_catalog_contains_real_use_cases():
    """Test that legacy scenario catalog has expected scenarios."""
    assert "runner_follow_basic" in SCENARIOS
    assert "sailboat_follow_wide" in SCENARIOS
    assert "nature_orbit_reveal" in SCENARIOS
    assert "indoor_obstacle_room_depth" in SCENARIOS


def test_each_scenario_has_acceptance_command():
    """Test that each legacy scenario has valid acceptance test."""
    for scenario in list_scenarios():
        assert scenario.acceptance_test.startswith("python3 -m pytest ")
        assert scenario.px4_command.startswith("cd PX4-Autopilot && make ")
        assert "mcp_stdio" in scenario.required_backends


def test_get_scenario_returns_named_scenario():
    """Test that get_scenario returns the correct scenario."""
    scenario = get_scenario("sailboat_follow_wide")

    assert scenario.kind == "sailboat_follow"
    assert "boat" in scenario.description.lower()


# =============================================================================
# SCENARIO LOADER TESTS
# =============================================================================


class TestScenarioLoader:
    """Tests for ScenarioLoader."""

    def test_load_from_path(self, sample_scenario_yaml: Path) -> None:
        """Test loading scenario from explicit path."""
        loader = ScenarioLoader()
        scenario = loader.load_path(sample_scenario_yaml)

        assert scenario.id == "test_scenario"
        assert scenario.kind == ScenarioKind.SMOKE_TEST
        assert "Test scenario" in scenario.description
        assert len(scenario.stages) == 1
        assert len(scenario.injections) == 1
        assert len(scenario.assertions) == 1

    def test_parse_stage(self) -> None:
        """Test parsing stage definition."""
        loader = ScenarioLoader()
        stage_data = {
            "id": "takeoff",
            "tool": "arm_and_takeoff",
            "args": {"altitude": 10.0},
            "timeout_s": 30,
            "on_failure": "abort",
        }
        stage = loader._parse_stage(stage_data)

        assert stage.id == "takeoff"
        assert stage.tool == "arm_and_takeoff"
        assert stage.args == {"altitude": 10.0}
        assert stage.timeout_s == 30
        assert stage.on_failure == "abort"

    def test_parse_injection(self) -> None:
        """Test parsing injection definition."""
        loader = ScenarioLoader()
        inj_data = {
            "at": {"stage": "hover", "t_offset_s": 5.0},
            "driver": "gps_loss",
            "params": {"duration_s": 10},
        }
        inj = loader._parse_injection(inj_data)

        assert inj.driver == "gps_loss"
        assert inj.at.stage == "hover"
        assert inj.at.t_offset_s == 5.0
        assert inj.params == {"duration_s": 10}

    def test_parse_assertion(self) -> None:
        """Test parsing assertion definition."""
        loader = ScenarioLoader()
        assert_data = {
            "within_s": 8.0,
            "expect": {"flight_mode": ["HOLD", "RTL"]},
            "message": "Should enter safe mode",
        }
        assertion = loader._parse_assertion(assert_data)

        assert assertion.within_s == 8.0
        assert assertion.expect == {"flight_mode": ["HOLD", "RTL"]}
        assert assertion.message == "Should enter safe mode"

    def test_list_scenarios(self) -> None:
        """Test listing available scenarios."""
        loader = ScenarioLoader()
        scenarios = loader.list_scenarios()

        # Should include the scenarios we created
        assert "smoke_failsafe_rtl" in scenarios
        assert "orbit_offboard_freeze" in scenarios
        assert "analyze_area_offline" in scenarios

    def test_invalid_kind_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid kind raises ValueError."""
        yaml_content = """
id: bad_scenario
kind: invalid_kind
description: "Bad scenario"
"""
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text(yaml_content)

        loader = ScenarioLoader()
        with pytest.raises(ValueError, match="Invalid kind"):
            loader.load_path(yaml_path)

    def test_missing_id_raises_error(self, tmp_path: Path) -> None:
        """Test that missing ID raises ValueError."""
        yaml_content = """
kind: smoke_test
description: "No ID"
"""
        yaml_path = tmp_path / "no_id.yaml"
        yaml_path.write_text(yaml_content)

        loader = ScenarioLoader()
        with pytest.raises(ValueError, match="missing 'id'"):
            loader.load_path(yaml_path)


# =============================================================================
# DRIVER TESTS
# =============================================================================


class TestDrivers:
    """Tests for failure injection drivers."""

    def test_driver_registry(self) -> None:
        """Test driver registration and lookup."""
        # Check all expected drivers are registered
        drivers = DriverRegistry.list_drivers()

        assert "wind" in drivers
        assert "gps_loss" in drivers
        assert "vision_dropout" in drivers
        assert "offboard_freeze" in drivers
        assert "battery_drain" in drivers
        assert "rc_loss" in drivers
        assert "obstacle_proximity" in drivers
        assert "target_motion" in drivers
        assert "network_partition" in drivers

    def test_get_unknown_driver_raises_error(self) -> None:
        """Test that unknown driver raises ValueError."""
        with pytest.raises(ValueError, match="Unknown driver"):
            DriverRegistry.get("nonexistent_driver")

    @pytest.mark.asyncio
    async def test_wind_driver_inject(self, mock_mcp_client: MockMcpClient) -> None:
        """Test WindDriver injection."""
        driver = WindDriver()

        ctx = DriverContext(
            scenario_id="test",
            stage_id="hover",
            sim_tier=SimTier.SIH,
            start_time_s=0.0,
            current_time_s=1.0,
            mcp_client=mock_mcp_client,
            params={"speed_m_s": 5.0, "direction_deg": 45},
        )

        await driver.inject(ctx)

        # Check that calls were made
        assert len(mock_mcp_client.calls) > 0
        call_names = [c[0] for c in mock_mcp_client.calls]
        assert "set_simulation_wind" in call_names

    @pytest.mark.asyncio
    async def test_gps_loss_driver(self, mock_mcp_client: MockMcpClient) -> None:
        """Test GpsLossDriver injection and release."""
        driver = GpsLossDriver()

        ctx = DriverContext(
            scenario_id="test",
            stage_id="nav",
            sim_tier=SimTier.SIH,
            start_time_s=0.0,
            current_time_s=1.0,
            mcp_client=mock_mcp_client,
            params={"duration_s": 10, "gradual": False},
        )

        await driver.inject(ctx)
        assert len(mock_mcp_client.calls) > 0

        # Clear calls and test release
        mock_mcp_client.clear_calls()
        await driver.release(ctx)
        assert len(mock_mcp_client.calls) > 0

    @pytest.mark.asyncio
    async def test_offboard_freeze_driver(self, mock_mcp_client: MockMcpClient) -> None:
        """Test OffboardFreezeDriver injection."""
        driver = OffboardFreezeDriver()

        ctx = DriverContext(
            scenario_id="test",
            stage_id="orbit",
            sim_tier=SimTier.GAZEBO,
            start_time_s=0.0,
            current_time_s=15.0,
            mcp_client=mock_mcp_client,
            params={"duration_s": 3, "freeze_type": "timeout"},
        )

        await driver.inject(ctx)

        call_names = [c[0] for c in mock_mcp_client.calls]
        assert "pause_offboard_stream" in call_names

    @pytest.mark.asyncio
    async def test_vision_dropout_driver(self, mock_mcp_client: MockMcpClient) -> None:
        """Test VisionDropoutDriver with different dropout types."""
        driver = VisionDropoutDriver()

        # Test camera_off type
        ctx = DriverContext(
            scenario_id="test",
            stage_id="track",
            sim_tier=SimTier.GAZEBO,
            start_time_s=0.0,
            current_time_s=10.0,
            mcp_client=mock_mcp_client,
            params={"dropout_type": "camera_off", "duration_s": 5},
        )

        await driver.inject(ctx)
        call_names = [c[0] for c in mock_mcp_client.calls]
        assert "set_camera_enabled" in call_names

    @pytest.mark.asyncio
    async def test_battery_drain_driver(self, mock_mcp_client: MockMcpClient) -> None:
        """Test BatteryDrainDriver injection."""
        driver = BatteryDrainDriver()

        ctx = DriverContext(
            scenario_id="test",
            stage_id="hover",
            sim_tier=SimTier.SIH,
            start_time_s=0.0,
            current_time_s=60.0,
            mcp_client=mock_mcp_client,
            telemetry={"battery_percent": 85.0},
            params={"drain_rate": 10, "target_percent": 20, "gradual": True},
        )

        await driver.inject(ctx)

        call_names = [c[0] for c in mock_mcp_client.calls]
        assert "set_battery_drain_rate" in call_names or "set_battery_level" in call_names


# =============================================================================
# INJECTION SCHEDULER TESTS
# =============================================================================


class TestInjectionScheduler:
    """Tests for InjectionScheduler."""

    @pytest.mark.asyncio
    async def test_schedule_injection(self) -> None:
        """Test scheduling injections."""
        scheduler = InjectionScheduler()

        injections = [
            InjectionDefinition(
                at=InjectionTrigger(stage="hover", t_offset_s=5.0),
                driver="gps_loss",
                params={"duration_s": 10},
            ),
        ]

        mock_mcp = MockMcpClient()
        scheduler.schedule(injections, mock_mcp, SimTier.SIH, 0.0)

        # Verify tasks were created
        assert len(scheduler._scheduled) == 1

        scheduler.reset()

    def test_notify_stage_start(self) -> None:
        """Test stage start notification."""
        scheduler = InjectionScheduler()

        scheduler.notify_stage_start("hover", 10.0)

        assert scheduler._stage_starts["hover"] == 10.0
        assert scheduler._current_stage == "hover"

    @pytest.mark.asyncio
    async def test_release_all(self) -> None:
        """Test releasing all active injections."""
        scheduler = InjectionScheduler()

        # Add a fake active injection
        scheduler._active["test_driver"] = MagicMock()
        scheduler._active["test_driver"].release = AsyncMock()

        await scheduler.release_all()

        assert len(scheduler._active) == 0


# =============================================================================
# ASSERTION ENGINE TESTS
# =============================================================================


class TestAssertionEngine:
    """Tests for AssertionEngine."""

    @pytest.mark.asyncio
    async def test_check_assertion_pass(self, mock_mcp_client: MockMcpClient) -> None:
        """Test assertion that passes."""
        engine = AssertionEngine()

        # Set up mock to return expected state
        mock_mcp_client.set_response(
            "get_status",
            {"state": {"flight_mode": "HOLD", "armed": True}},
        )

        assertion = AssertionDefinition(
            within_s=5.0,
            expect={"flight_mode": ["HOLD", "RTL"]},
            message="Should be in safe mode",
        )

        result = await engine.check_assertion(assertion, mock_mcp_client, time.time())

        assert result.status == AssertionStatus.PASS

    @pytest.mark.asyncio
    async def test_check_assertion_timeout(self, mock_mcp_client: MockMcpClient) -> None:
        """Test assertion that times out."""
        engine = AssertionEngine()

        # Set up mock to return wrong state
        mock_mcp_client.set_response(
            "get_status",
            {"state": {"flight_mode": "OFFBOARD"}},
        )

        assertion = AssertionDefinition(
            within_s=0.5,  # Very short timeout
            expect={"flight_mode": ["HOLD", "RTL"]},
            message="Should be in safe mode",
        )

        result = await engine.check_assertion(assertion, mock_mcp_client, 0.0)

        assert result.status == AssertionStatus.TIMEOUT

    def test_notify_stage_complete(self) -> None:
        """Test recording completed stages."""
        engine = AssertionEngine()

        engine.notify_stage_complete("takeoff")
        engine.notify_stage_complete("hover")

        assert engine._completed_stages == ["takeoff", "hover"]


# =============================================================================
# ARTIFACT COLLECTOR TESTS
# =============================================================================


class TestArtifactCollector:
    """Tests for ArtifactCollector."""

    def test_setup_creates_directory(self, tmp_path: Path) -> None:
        """Test that setup creates artifact directory."""
        collector = ArtifactCollector(tmp_path, "test_run")
        collector.setup()

        assert collector.run_dir.exists()
        assert collector.run_dir.name == "test_run"

    def test_record_telemetry(self, tmp_path: Path) -> None:
        """Test recording telemetry snapshots."""
        collector = ArtifactCollector(tmp_path, "test_run")
        collector.setup()

        collector.record_telemetry({"battery": 85.0, "altitude": 10.0})
        collector.record_telemetry({"battery": 80.0, "altitude": 15.0})

        assert len(collector._telemetry_log) == 2

    def test_save_result(self, tmp_path: Path) -> None:
        """Test saving scenario result."""
        collector = ArtifactCollector(tmp_path, "test_run")
        collector.setup()

        result = ScenarioResult(
            scenario_id="test",
            passed=True,
            stages=[StageResult(stage_id="takeoff", tool="arm_and_takeoff", success=True)],
        )

        collector.save_result(result)

        result_path = collector.run_dir / "result.json"
        assert result_path.exists()

    def test_save_artifact(self, tmp_path: Path) -> None:
        """Test saving custom artifact."""
        collector = ArtifactCollector(tmp_path, "test_run")
        collector.setup()

        artifact_path = collector.save_artifact("debug.log", "Debug output here")

        assert artifact_path.exists()
        assert artifact_path.read_text() == "Debug output here"

    def test_list_artifacts(self, tmp_path: Path) -> None:
        """Test listing collected artifacts."""
        collector = ArtifactCollector(tmp_path, "test_run")
        collector.setup()

        collector.save_artifact("test1.txt", "content1")
        collector.save_artifact("test2.txt", "content2")

        artifacts = collector.list_artifacts()

        assert "test1.txt" in artifacts
        assert "test2.txt" in artifacts


# =============================================================================
# ORCHESTRATOR TESTS
# =============================================================================


class TestOrchestrator:
    """Tests for Orchestrator."""

    @pytest.mark.asyncio
    async def test_run_simple_scenario(
        self,
        sample_scenario_def: ScenarioDefinition,
        tmp_path: Path,
    ) -> None:
        """Test running a simple scenario with mock MCP."""
        mock_mcp = MockMcpClient()

        # Configure mock responses
        mock_mcp.set_response("run_preflight", {"status": "success"})
        mock_mcp.set_response("arm_and_takeoff", {"status": "success"})
        mock_mcp.set_response("hold", {"status": "success"})
        mock_mcp.set_response(
            "get_status",
            {"state": {"flight_mode": "HOLD", "armed": True}},
        )

        orchestrator = Orchestrator(
            artifacts_dir=tmp_path,
            run_id="test_run",
            mcp_client=mock_mcp,
        )

        result = await orchestrator.run(sample_scenario_def)

        assert result.scenario_id == "test_scenario"
        assert len(result.stages) >= 1  # At least takeoff stage
        assert result.duration_s > 0
        assert len(result.artifacts) > 0

    @pytest.mark.asyncio
    async def test_scenario_failure_recording(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that scenario failures are recorded correctly."""
        mock_mcp = MockMcpClient()

        # Configure mock to return failure
        mock_mcp.set_response("arm_and_takeoff", {"status": "error", "error": "GPS not ready"})

        scenario = ScenarioDefinition(
            id="fail_test",
            kind=ScenarioKind.SMOKE_TEST,
            description="Test that fails",
            stages=[
                StageDefinition(
                    id="takeoff",
                    tool="arm_and_takeoff",
                    args={"altitude": 10.0},
                    on_failure="abort",
                ),
            ],
        )

        orchestrator = Orchestrator(
            artifacts_dir=tmp_path,
            run_id="fail_run",
            mcp_client=mock_mcp,
        )

        result = await orchestrator.run(scenario)

        # The scenario should have recorded the stage attempt
        assert len(result.stages) == 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for scenario runner."""

    @pytest.mark.asyncio
    async def test_load_and_run_yaml_scenario(self, tmp_path: Path) -> None:
        """Test loading and running a YAML scenario."""
        # Create a minimal scenario
        yaml_path = tmp_path / "minimal.yaml"
        yaml_path.write_text("""
id: minimal_test
kind: smoke_test
description: "Minimal test scenario"

stages:
  - id: noop
    tool: ping
    args: {}
""")

        loader = ScenarioLoader([tmp_path])
        scenario = loader.load_path(yaml_path)

        assert scenario.id == "minimal_test"
        assert len(scenario.stages) == 1

    @pytest.mark.asyncio
    async def test_run_scenario_function(self, tmp_path: Path) -> None:
        """Test the run_scenario convenience function."""
        mock_mcp = MockMcpClient()
        mock_mcp.set_response("ping", {"status": "success"})
        mock_mcp.set_response("get_status", {"state": {}})

        # Create a minimal scenario file
        yaml_path = tmp_path / "simple.yaml"
        yaml_path.write_text("""
id: simple
kind: smoke_test
description: "Simple test"

stages:
  - id: ping_test
    tool: ping
    args: {}
""")

        loader = ScenarioLoader([tmp_path])
        scenario = loader.load_path(yaml_path)

        orchestrator = Orchestrator(
            artifacts_dir=tmp_path,
            run_id="simple_run",
            mcp_client=mock_mcp,
        )

        result = await orchestrator.run(scenario)

        assert result.scenario_id == "simple"


# =============================================================================
# DRIVER PROTOCOL TESTS
# =============================================================================


class TestDriverProtocol:
    """Tests for driver protocol compliance."""

    def test_all_drivers_have_name(self) -> None:
        """Test that all drivers have a name attribute."""
        drivers = [
            WindDriver(),
            GpsLossDriver(),
            OffboardFreezeDriver(),
            VisionDropoutDriver(),
            BatteryDrainDriver(),
            RcLossDriver(),
            ObstacleProximityDriver(),
            TargetMotionDriver(),
            NetworkPartitionDriver(),
        ]

        for driver in drivers:
            assert hasattr(driver, "name")
            assert isinstance(driver.name, str)
            assert len(driver.name) > 0

    def test_all_drivers_have_supported_tiers(self) -> None:
        """Test that all drivers define supported tiers."""
        drivers = [
            WindDriver(),
            GpsLossDriver(),
            OffboardFreezeDriver(),
            VisionDropoutDriver(),
            BatteryDrainDriver(),
            RcLossDriver(),
            ObstacleProximityDriver(),
            TargetMotionDriver(),
            NetworkPartitionDriver(),
        ]

        for driver in drivers:
            assert hasattr(driver, "supported_tiers")
            # After __init__, supported_tiers should be a set
            assert isinstance(driver.supported_tiers, set)

    @pytest.mark.asyncio
    async def test_drivers_are_callable(self, mock_mcp_client: MockMcpClient) -> None:
        """Test that all drivers implement inject and release."""
        drivers = [
            (WindDriver(), {"speed_m_s": 5.0}),
            (GpsLossDriver(), {}),
            (OffboardFreezeDriver(), {}),
            (VisionDropoutDriver(), {}),
            (BatteryDrainDriver(), {}),
            (RcLossDriver(), {}),
            (ObstacleProximityDriver(), {}),
            (TargetMotionDriver(), {}),
            (NetworkPartitionDriver(), {}),
        ]

        for driver, params in drivers:
            ctx = DriverContext(
                scenario_id="test",
                stage_id="test_stage",
                sim_tier=SimTier.SIH,
                start_time_s=0.0,
                current_time_s=1.0,
                mcp_client=mock_mcp_client,
                params=params,
            )

            # Both inject and release should be callable
            await driver.inject(ctx)
            await driver.release(ctx)

            # Clear calls for next driver
            mock_mcp_client.clear_calls()
