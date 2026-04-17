# Safety-Critical Drone Code Testing Strategies

## Executive Summary

This document provides comprehensive testing methodologies for safety-critical drone software, covering industry-standard approaches used by PX4, ArduPilot, and aerospace-grade systems. Testing is organized into four pillars: simulation-based testing (HITL/SITL), unit/integration testing, quality gates, and safety validation patterns.

---

## 1. Testing Methodologies

### 1.1 Hardware-in-the-Loop (HITL) Testing

HITL simulation uses actual flight controller hardware connected to a simulator, replacing the physical vehicle and environment with high-fidelity models.

#### Supported Simulators

| Simulator | Support Level | Protocol | Notes |
|-----------|--------------|----------|-------|
| **jMAVSim** | Full | MAVLink | Lightweight Java-based simulator, ideal for CI/CD |
| **Gazebo** | Full | MAVLink/ROS | Physics-based, supports complex environments |
| **X-Plane** | Partial (Plane only) | UDP | High-fidelity aircraft dynamics |
| **FlightGear** | Partial (Plane only) | UDP | Open-source flight simulator |
| **RealFlight** | Community | - | RC flight simulator |
| **AirSim** | Community | RPC | Unreal Engine-based, photorealistic |

#### HITL Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Simulator     │◄────►│   MAVLink    │◄────►│  Flight Controller│
│ (jMAVSim/Gazebo)│      │   Bridge     │      │   (Pixhawk)     │
└─────────────────┘      └──────────────┘      └─────────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │  Test Runner │
                        │   (pytest)   │
                        └──────────────┘
```

#### PX4 HITL Setup

```bash
# 1. Configure airframe for HITL
# In QGroundControl: Airframe → HILT star category
# For Quadcopter: HILT Quadcopter X

# 2. Disable preflight checks in Simulation tab
# This allows HITL without GPS lock

# 3. Connect via USB and start simulation
make px4_sitl_default none_iris  # SITL equivalent
# For HITL, use QGroundControl to connect
```

#### HITL Test Categories

```python
# Example: HITL test structure
class HITLTestBase:
    """Base class for HITL tests with safety timeouts"""

    def setup_method(self):
        self.fc = FlightController()
        self.sim = Simulator()
        self.timeout = 30  # Safety timeout seconds

    def teardown_method(self):
        self.sim.stop()
        self.fc.disconnect()

    def test_arm_disarm(self):
        """Test basic arming with hardware safety checks"""
        # Verify preflight checks
        assert self.fc.health.all_ok(), "Pre-arm checks failed"

        # Arm with timeout
        with timeout(self.timeout):
            self.fc.arm()
            assert self.fc.armed

        # Disarm
        self.fc.disarm()
        assert not self.fc.armed
```

#### HITL Safety Requirements

- **Watchdog**: Test fails if no heartbeat within timeout
- **Geofence**: Automatic failsafe if drone exceeds boundaries
- **RC Override**: Physical transmitter can always take control
- **Kill Switch**: Emergency stop capability

---

### 1.2 Software-in-the-Loop (SITL) Testing

SITL runs the actual flight control software on host hardware, simulating the flight controller without physical hardware.

#### SITL Modes

| Mode | Use Case | Command |
|------|----------|---------|
| **jMAVSim** | Quick testing | `make px4_sitl jmavsim` |
| **Gazebo** | Vision/realism | `make px4_sitl gazebo` |
| **Gazebo Classic** | ROS integration | `make px4_sitl gazebo-classic` |
| **JSBSim** | Fixed-wing focus | `make px4_sitl jsbsim` |

#### PX4 SITL Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Host Computer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  PX4 Firmware│  │  Simulator  │  │  Test Runner │        │
│  │  (SITL build)│  │  (jMAVSim)  │  │  (MAVSDK/py) │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                 │               │
│         └────────────────┴─────────────────┘               │
│                    UDP/MAVLink                             │
└─────────────────────────────────────────────────────────────┘
```

#### ArduPilot SITL Commands

```bash
# Copter simulation
sim_vehicle.py -v ArduCopter

# Plane with specific location
sim_vehicle.py -v ArduPlane --location=KSFO

# Rover with gdb debugging
sim_vehicle.py -v APMrover2 --debug --gdb

# Custom parameters
sim_vehicle.py -v ArduCopter --add-param-file=my_params.parm
```

#### SITL Testing Patterns

```python
# test_sitl_mission.py
import pytest
import asyncio
from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan

@pytest.fixture(scope="module")
async def drone():
    """SITL drone fixture with automatic cleanup"""
    drone = System()
    await drone.connect(system_address="udp://:14540")

    # Wait for connection
    async for state in drone.core.connection_state():
        if state.is_connected:
            break

    yield drone

    # Cleanup
    try:
        await drone.action.disarm()
    except:
        pass

@pytest.mark.sitl
@pytest.mark.asyncio
async def test_takeoff_and_land(drone):
    """SITL test: Takeoff to 10m and land"""
    # Health check
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            break

    # Arm and takeoff
    await drone.action.arm()
    await drone.action.takeoff()

    # Wait for altitude
    async for position in drone.telemetry.position():
        if position.relative_altitude_m > 9:
            break

    # Land
    await drone.action.land()

    # Verify disarmed
    async for is_armed in drone.telemetry.armed():
        if not is_armed:
            break
```

#### SITL Integration with CI

```yaml
# .github/workflows/sitl-test.yml
name: SITL Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup PX4 SITL
        run: |
          git clone https://github.com/PX4/PX4-Autopilot.git
          cd PX4-Autopilot
          make px4_sitl

      - name: Run Integration Tests
        run: |
          docker run -v $(pwd):/src px4io/px4-dev-simulation bash -c "
            cd /src
            pytest tests/sitl/ -v --timeout=300
          "
```

---

### 1.3 Unit Testing for Async Drone Code

#### Testing Frameworks

| Framework | Purpose | When to Use |
|-----------|---------|-------------|
| **pytest** | Unit/integration | All Python drone code |
| **pytest-asyncio** | Async support | MAVSDK, asyncio-based |
| **hypothesis** | Property-based | Command validation |
| **GoogleTest** | C++ unit tests | PX4/ArduPilot core |
| **GMock** | Mocking C++ | PX4 unit tests |

#### Async Test Patterns

```python
# test_drone_controller.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from drone_controller import DroneController

@pytest.fixture
def mock_mavsdk():
    """Mock MAVSDK system for unit tests"""
    system = Mock()
    system.connect = AsyncMock()
    system.action.arm = AsyncMock()
    system.action.disarm = AsyncMock()
    system.action.takeoff = AsyncMock()
    system.action.land = AsyncMock()

    # Mock telemetry streams
    system.telemetry.position = Mock()
    system.telemetry.position.__aiter__ = Mock(
        return_value=iter([Mock(relative_altitude_m=10)])
    )

    return system

@pytest.fixture
def controller(mock_mavsdk):
    """Drone controller fixture with mocked MAVSDK"""
    return DroneController(mock_mavsdk)

@pytest.mark.asyncio
async def test_safe_arm_success(controller, mock_mavsdk):
    """Test successful arming with all checks passing"""
    # Setup
    mock_mavsdk.telemetry.health.__aiter__ = Mock(
        return_value=iter([Mock(
            is_gyrometer_calibration_ok=True,
            is_accelerometer_calibration_ok=True,
            is_magnetometer_calibration_ok=True,
            is_level_calibration_ok=True,
            is_local_position_ok=True,
            is_global_position_ok=True,
            is_home_position_ok=True,
            is_armable=True
        )])
    )

    # Execute
    result = await controller.safe_arm()

    # Verify
    assert result is True
    mock_mavsdk.action.arm.assert_called_once()

@pytest.mark.asyncio
async def test_safe_arm_fails_uncalibrated(controller, mock_mavsdk):
    """Test arming failure when not calibrated"""
    # Setup: magnetometer not calibrated
    mock_mavsdk.telemetry.health.__aiter__ = Mock(
        return_value=iter([Mock(
            is_gyrometer_calibration_ok=True,
            is_accelerometer_calibration_ok=True,
            is_magnetometer_calibration_ok=False,  # FAIL
            is_armable=False
        )])
    )

    # Execute
    with pytest.raises(SafetyException, match="not calibrated"):
        await controller.safe_arm()

    # Verify arm was never called
    mock_mavsdk.action.arm.assert_not_called()
```

#### Running ArduPilot Unit Tests

```bash
# Configure for testing
./waf configure --board=linux --debug

# Build tests
./waf tests

# Run specific test
./build/linux/tests/test_vector2

# Run with GDB
./gdb --quiet --args ./build/linux/tests/test_vector2

# Run with Valgrind for memory checking
valgrind --soname-synonyms=somalloc=nouserintercepts \
    ./build/linux/tests/test_vector2
```

#### Sample Unit Test (ArduPilot C++)

```cpp
// libraries/AP_Math/tests/test_vector2.cpp
#include <AP_gtest.h>
#include <AP_Math/AP_Math.h>

TEST(Vector2Test, IsEqual) {
    Vector2f a(1.0f, 2.0f);
    Vector2f b(1.0f, 2.0f);
    Vector2f c(1.1f, 2.0f);

    EXPECT_TRUE(a == b);
    EXPECT_FALSE(a == c);
}

TEST(Vector2Test, angle) {
    EXPECT_FLOAT_EQ(M_PI/2, Vector2f(0, 1).angle());
    EXPECT_FLOAT_EQ(0, Vector2f(1, 0).angle());
    EXPECT_FLOAT_EQ(-M_PI/2, Vector2f(0, -1).angle());
}

TEST(Vector2Test, normalized) {
    Vector2f v(3.0f, 4.0f);
    Vector2f n = v.normalized();

    EXPECT_FLOAT_EQ(1.0f, n.length());
    EXPECT_FLOAT_EQ(0.6f, n.x);  // 3/5
    EXPECT_FLOAT_EQ(0.8f, n.y);  // 4/5
}
```

---

### 1.4 Property-Based Testing

Property-based testing generates random inputs to find edge cases in command validation.

#### Using Hypothesis for Drone Commands

```python
# test_command_validation.py
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from dataclasses import dataclass
from typing import Optional
import math

@dataclass
class GotoCommand:
    """Go-to-location command"""
    lat: float  # -90 to 90
    lon: float  # -180 to 180
    alt: float  # meters AMSL
    speed: float  # m/s
    yaw: Optional[float] = None  # degrees, None for unchanged

class CommandValidator:
    """Validates drone commands for safety"""

    MAX_SPEED = 20.0  # m/s
    MAX_ALTITUDE = 120.0  # meters (400ft)
    MIN_ALTITUDE = -500.0  # Dead Sea area

    @staticmethod
    def validate_goto(cmd: GotoCommand) -> tuple[bool, str]:
        """Validate goto command"""
        if not -90 <= cmd.lat <= 90:
            return False, f"Invalid latitude: {cmd.lat}"

        if not -180 <= cmd.lon <= 180:
            return False, f"Invalid longitude: {cmd.lon}"

        if cmd.alt > CommandValidator.MAX_ALTITUDE:
            return False, f"Altitude exceeds limit: {cmd.alt}m"

        if cmd.alt < CommandValidator.MIN_ALTITUDE:
            return False, f"Altitude below minimum: {cmd.alt}m"

        if cmd.speed <= 0 or cmd.speed > CommandValidator.MAX_SPEED:
            return False, f"Speed out of range: {cmd.speed}"

        if cmd.yaw is not None and not 0 <= cmd.yaw < 360:
            return False, f"Invalid yaw: {cmd.yaw}"

        return True, "Valid"

# Property-based tests
@given(
    lat=st.floats(min_value=-90, max_value=90),
    lon=st.floats(min_value=-180, max_value=180),
    alt=st.floats(min_value=-500, max_value=120),
    speed=st.floats(min_value=0.1, max_value=20),
    yaw=st.one_of(st.none(), st.floats(min_value=0, max_value=359.999))
)
def test_valid_commands_pass(lat, lon, alt, speed, yaw):
    """All valid commands should validate successfully"""
    cmd = GotoCommand(lat, lon, alt, speed, yaw)
    valid, msg = CommandValidator.validate_goto(cmd)
    assert valid, f"Should be valid but got: {msg}"

@given(
    lat=st.floats().filter(lambda x: x < -90 or x > 90),
    lon=st.floats(min_value=-180, max_value=180),
    alt=st.floats(min_value=-500, max_value=120),
    speed=st.floats(min_value=0.1, max_value=20)
)
def test_invalid_lat_fails(lat, lon, alt, speed):
    """Invalid latitude should be rejected"""
    cmd = GotoCommand(lat, lon, alt, speed)
    valid, _ = CommandValidator.validate_goto(cmd)
    assert not valid

@given(
    alt=st.floats().filter(lambda x: x > 120 or x < -500)
)
def test_altitude_limits(alt):
    """Altitude outside safe range should be rejected"""
    cmd = GotoCommand(0, 0, alt, 5)
    valid, _ = CommandValidator.validate_goto(cmd)
    assert not valid

# Stateful testing for command sequences
class DroneStateMachine(RuleBasedStateMachine):
    """State machine for testing drone command sequences"""

    def __init__(self):
        super().__init__()
        self.position = (0.0, 0.0, 0.0)  # lat, lon, alt
        self.armed = False
        self.commands_executed = []

    @rule(lat=st.floats(-90, 90), lon=st.floats(-180, 180),
          alt=st.floats(0, 120), speed=st.floats(0.1, 20))
    def goto(self, lat, lon, alt, speed):
        """Execute goto command"""
        if not self.armed:
            return  # Can't move if not armed

        # Distance check
        distance = self._distance(self.position[0], self.position[1], lat, lon)
        max_distance = speed * 10  # Assume 10s max travel

        if distance > max_distance:
            raise ValueError("Impossible movement speed")

        self.position = (lat, lon, alt)
        self.commands_executed.append(('goto', lat, lon, alt))

    @rule()
    def arm(self):
        """Arm the drone"""
        if self.position[2] > 0.1:  # Already in air
            return
        self.armed = True
        self.commands_executed.append('arm')

    @rule()
    def disarm(self):
        """Disarm the drone"""
        self.armed = False
        self.commands_executed.append('disarm')

    @invariant()
    def altitude_safe(self):
        """Altitude must always be safe"""
        assert 0 <= self.position[2] <= 120

    @invariant()
    def speed_reasonable(self):
        """Speed must be reasonable between commands"""
        if len(self.commands_executed) < 2:
            return

    def _distance(self, lat1, lon1, lat2, lon2):
        """Haversine distance in meters"""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

TestDroneCommands = DroneStateMachine.TestCase
TestDroneCommands.settings = settings(max_examples=1000)
```

---

## 2. Code Quality Gates

### 2.1 Required Coverage Percentages

#### Aerospace Standards

| Standard | Coverage Requirement | Context |
|----------|---------------------|---------|
| **DO-178C** | 100% MC/DC | Level A (catastrophic) |
| **DO-330** | Tool qualification | Testing tools used |
| **ISO 26262** | ASIL-D: High coverage | Automotive parallel |
| **IEC 61508** | SIL 4: 100% coverage | Generic safety |

#### Recommended Coverage Targets

```python
# pyproject.toml coverage configuration
[tool.coverage.run]
source = ["src"]
branch = true
concurrency = ["thread", "greenlet"]
# For async drone code

[tool.coverage.report]
# Minimum coverage thresholds
fail_under = 95

# Files that require 100% coverage
[tool.coverage.report.paths]
strict = [
    "src/drone/safety/*.py",
    "src/drone/failsafe/*.py",
    "src/drone/commands/validators.py"
]

# Files with relaxed coverage
[tool.coverage.report.exclude_lines]
exclude_also = [
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:"
]
```

#### Running Coverage Reports

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Check against threshold
pytest --cov=src --cov-fail-under=95

# Generate detailed report
coverage html
coverage report --fail-under=95

# For safety-critical files
pytest tests/safety/ --cov=src/safety --cov-fail-under=100
```

### 2.2 Static Analysis Tools

#### Python Stack

```ini
# .pylintrc - Pylint configuration for drone code
[MASTER]
jobs=4
persistent=yes

disable=
    C0103,  # Invalid name (for MAVLink fields)
    C0111,  # Missing docstring (handled by pydocstyle)
    R0903,  # Too few public methods (for dataclasses)
    R0913,  # Too many arguments (common in drone commands)

[TYPECHECK]
generated-members=numpy.*,torch.*,pymavlink.*

[DESIGN]
max-args=10  # Drone commands need many parameters
max-attributes=15
max-branches=20

[SIMILARITIES]
min-similarity-lines=10
ignore-imports=yes

[BASIC]
good-names=i,j,k,ex,Run,_,x,y,z,lat,lon,alt,yaw,pitch,roll
```

```toml
# mypy.ini - Type checking configuration
[mypy]
python_version = 3.11
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

# MAVLink libraries (external, limited typing)
[mypy-pymavlink.*]
ignore_missing_imports = true

[mypy-mavsdk.*]
ignore_missing_imports = true

[mypy-dronekit.*]
ignore_missing_imports = true
```

```toml
# pyproject.toml - Bandit security scanner
[tool.bandit]
exclude_dirs = ["tests", "docs"]
skips = ["B101"]  # Skip assert warnings (used in tests)

# Severity filter
severity = "medium"
confidence = "medium"
```

#### Pre-commit Hook Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/pylint-dev/pylint
    rev: v3.0.3
    hooks:
      - id: pylint
        args: [--rcfile=.pylintrc]
        additional_dependencies:
          - pytest-asyncio
          - mavsdk

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        args: [--strict]
        additional_dependencies:
          - types-PyYAML
          - pytest-asyncio

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]
        additional_dependencies:
          - toml

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/PyCQA/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile, black]
```

#### C++ Static Analysis (PX4/ArduPilot)

```cmake
# CMakeLists.txt static analysis targets
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    # cppcheck
    find_program(CPPCHECK cppcheck)
    if(CPPCHECK)
        add_custom_target(cppcheck
            COMMAND ${CPPCHECK}
                --enable=all
                --std=c++17
                --suppress=missingIncludeSystem
                --suppress=unmatchedSuppression
                --error-exitcode=1
                -I ${CMAKE_SOURCE_DIR}/src
                ${CMAKE_SOURCE_DIR}/src
            COMMENT "Running cppcheck"
        )
    endif()

    # clang-tidy
    find_program(CLANG_TIDY clang-tidy)
    if(CLANG_TIDY)
        set(CMAKE_CXX_CLANG_TIDY
            ${CLANG_TIDY}
            -checks=bugprone-*,cppcoreguidelines-*,performance-*,portability-*,-cppcoreguidelines-pro-bounds-pointer-arithmetic
            -warnings-as-errors=*
        )
    endif()
endif()
```

### 2.3 Runtime Assertions and Invariants

#### Safety-Critical Assertions

```python
# safety_assertions.py
import functools
import logging
from typing import Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class SafetyViolation(Exception):
    """Exception raised when safety invariant is violated"""
    pass

@dataclass(frozen=True)
class StateInvariant:
    """Defines an invariant to check"""
    name: str
    check: Callable[[], bool]
    critical: bool = True

class SafetyMonitor:
    """Runtime safety monitor for drone operations"""

    def __init__(self):
        self.invariants: list[StateInvariant] = []
        self.violations: list[tuple[str, float]] = []

    def register(self, invariant: StateInvariant):
        """Register an invariant to monitor"""
        self.invariants.append(invariant)

    def check_all(self) -> bool:
        """Check all invariants, return True if all pass"""
        for inv in self.invariants:
            if not inv.check():
                msg = f"Invariant violated: {inv.name}"
                logger.critical(msg)
                self.violations.append((inv.name, time.time()))

                if inv.critical:
                    raise SafetyViolation(msg)
                return False
        return True

    def assert_invariant(self, name: str, condition: bool, critical: bool = True):
        """Assert a single invariant"""
        if not condition:
            msg = f"Invariant violated: {name}"
            logger.critical(msg)

            if critical:
                raise SafetyViolation(msg)
            return False
        return True

# Pre/post condition decorators
def pre_condition(check: Callable[..., bool]):
    """Decorator to check precondition"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not check(*args, **kwargs):
                raise SafetyViolation(f"Precondition failed for {func.__name__}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def post_condition(check: Callable[..., bool]):
    """Decorator to check postcondition"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not check(result, *args, **kwargs):
                raise SafetyViolation(f"Postcondition failed for {func.__name__}")
            return result
        return wrapper
    return decorator

# Example usage in drone code
class FlightController:
    def __init__(self):
        self.monitor = SafetyMonitor()
        self._setup_invariants()

    def _setup_invariants(self):
        """Register critical invariants"""
        self.monitor.register(StateInvariant(
            name="altitude_positive",
            check=lambda: self.current_altitude >= 0,
            critical=True
        ))
        self.monitor.register(StateInvariant(
            name="airspeed_valid",
            check=lambda: 0 <= self.airspeed < 100,  # m/s
            critical=True
        ))
        self.monitor.register(StateInvariant(
            name="battery_above_emergency",
            check=lambda: self.battery_remaining > 10,  # %
            critical=True
        ))

    @pre_condition(lambda self, alt: 0 <= alt <= 120)
    @post_condition(lambda _, result, *args, **kwargs: result is True)
    def set_target_altitude(self, altitude: float) -> bool:
        """Set target altitude with safety checks"""
        self._target_altitude = altitude
        return True

    async def _flight_loop(self):
        """Main flight loop with invariant checking"""
        while self._armed:
            self.monitor.check_all()
            await self._control_step()
            await asyncio.sleep(0.01)  # 100Hz
```

#### Compile-Time Assertions (C++)

```cpp
// safety_assertions.hpp
#pragma once
#include <type_traits>
#include <limits>

// Static assertions for compile-time checking
static_assert(sizeof(float) == 4, "Float must be 32-bit for MAVLink");
static_assert(std::numeric_limits<float>::is_iec559, "IEEE 754 required");

// Runtime assertions that can be disabled in production
#ifdef SAFETY_ASSERTIONS_ENABLED
    #define SAFETY_ASSERT(condition, message) \
        do { \
            if (!(condition)) { \
                safety_violation(__FILE__, __LINE__, message); \
            } \
        } while(0)
#else
    #define SAFETY_ASSERT(condition, message) ((void)0)
#endif

// Invariant checks
template<typename T>
class BoundedValue {
    T value;
    T min, max;

public:
    BoundedValue(T v, T minimum, T maximum) : min(minimum), max(maximum) {
        SAFETY_ASSERT(v >= min && v <= max, "Value out of bounds");
        value = v;
    }

    void set(T v) {
        SAFETY_ASSERT(v >= min && v <= max, "Value out of bounds");
        value = v;
    }

    T get() const { return value; }
};

// Type-safe altitude
using Altitude = BoundedValue<float>;
```

### 2.4 Fuzzing Command Inputs

```python
# fuzz_command_inputs.py
import atheris
import sys
import json
from dataclasses import dataclass
from typing import Any

@dataclass
class CommandFuzzResult:
    input_data: bytes
    exception: Exception
    crash: bool = False

class CommandFuzzer:
    """Fuzz test drone command inputs"""

    def __init__(self, validator):
        self.validator = validator
        self.results: list[CommandFuzzResult] = []

    def fuzz_mavlink_packet(self, data: bytes):
        """Fuzz raw MAVLink packet parsing"""
        try:
            # Try to parse as MAVLink message
            msg = self._parse_mavlink(data)
            if msg:
                self.validator.validate(msg)
        except Exception as e:
            self.results.append(CommandFuzzResult(data, e))

    def fuzz_json_command(self, data: bytes):
        """Fuzz JSON-formatted commands"""
        try:
            cmd = json.loads(data.decode('utf-8', errors='ignore'))
            self._execute_command(cmd)
        except json.JSONDecodeError:
            pass  # Invalid JSON is expected
        except Exception as e:
            self.results.append(CommandFuzzResult(data, e))

    def _parse_mavlink(self, data: bytes) -> Any:
        """Attempt to parse MAVLink packet"""
        # Implementation would use pymavlink
        pass

    def _execute_command(self, cmd: dict):
        """Execute command with safety checks"""
        cmd_type = cmd.get('type')

        if cmd_type == 'goto':
            self._validate_goto(cmd)
        elif cmd_type == 'arm':
            self._validate_arm(cmd)
        elif cmd_type == 'takeoff':
            self._validate_takeoff(cmd)

    def _validate_goto(self, cmd: dict):
        """Validate goto command parameters"""
        lat = cmd.get('lat')
        lon = cmd.get('lon')
        alt = cmd.get('alt')

        # These should not crash - should be rejected gracefully
        assert isinstance(lat, (int, float)), "Latitude must be numeric"
        assert isinstance(lon, (int, float)), "Longitude must be numeric"
        assert isinstance(alt, (int, float)), "Altitude must be numeric"

        assert -90 <= lat <= 90, "Latitude out of range"
        assert -180 <= lon <= 180, "Longitude out of range"
        assert 0 <= alt <= 120, "Altitude out of range"

def main():
    """Atheris fuzzing entry point"""

    fuzzer = CommandFuzzer(validator=None)

    def test_one_input(data: bytes):
        """Test input - called by atheris"""
        # Split data to test multiple parsers
        if len(data) > 0:
            if data[0] < 128:
                fuzzer.fuzz_mavlink_packet(data)
            else:
                fuzzer.fuzz_json_command(data[1:])

    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()

if __name__ == "__main__":
    main()
```

#### Running Fuzz Tests

```bash
# Install atheris
pip install atheris

# Run fuzzer with corpus
python fuzz_command_inputs.py corpus/ -max_total_time=300

# Run with specific input
python fuzz_command_inputs.py -max_len=1024 -runs=1000000

# Minimize crash cases
python fuzz_command_inputs.py -minimize_crash=1 crash-*
```

---

## 3. Safety Validation Patterns

### 3.1 Test for Every Failure Mode

#### Failure Mode Analysis

```python
# test_failure_modes.py
import pytest
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

class FailureMode(Enum):
    """Drone failure modes to test"""
    SENSOR_GPS_LOSS = auto()
    SENSOR_GYRO_FAILURE = auto()
    SENSOR_ACCEL_FAILURE = auto()
    SENSOR_MAG_FAILURE = auto()
    SENSOR_BARO_FAILURE = auto()
    COMMS_LINK_LOSS = auto()
    COMMS_GCS_TIMEOUT = auto()
    POWER_BATTERY_LOW = auto()
    POWER_BATTERY_CRITICAL = auto()
    MOTOR_FAILURE_SINGLE = auto()
    MOTOR_FAILURE_MULTI = auto()
    NAVIGATION_WAYPOINT_ERROR = auto()
    GEO_FENCE_BREACH = auto()
    RC_SIGNAL_LOSS = auto()
    RC_SIGNAL_INTERFERENCE = auto()

@dataclass
class FailureScenario:
    """Failure mode test scenario"""
    mode: FailureMode
    trigger: Callable
    expected_failsafe: str
    expected_action: str
    timeout_seconds: float

class FailureModeTester:
    """Test harness for failure modes"""

    SCENARIOS = [
        FailureScenario(
            mode=FailureMode.SENSOR_GPS_LOSS,
            trigger=lambda sim: sim.gps.disable(),
            expected_failsafe="LAND",
            expected_action="Switch to dead reckoning",
            timeout_seconds=30
        ),
        FailureScenario(
            mode=FailureMode.POWER_BATTERY_CRITICAL,
            trigger=lambda sim: sim.battery.set_level(5),
            expected_failsafe="RTL",
            expected_action="Return to launch immediately",
            timeout_seconds=10
        ),
        FailureScenario(
            mode=FailureMode.COMMS_LINK_LOSS,
            trigger=lambda sim: sim.mavlink.disconnect(),
            expected_failsafe="CONTINUE_MISSION",  # Or RTL based on config
            expected_action="Execute failsafe action",
            timeout_seconds=60
        ),
        FailureScenario(
            mode=FailureMode.MOTOR_FAILURE_SINGLE,
            trigger=lambda sim: sim.motors.fail(0),
            expected_failsafe="LAND",
            expected_action="Emergency landing",
            timeout_seconds=5
        ),
    ]

    async def run_scenario(self, scenario: FailureScenario, drone):
        """Execute a single failure scenario"""
        # Pre-condition: drone flying normally
        assert drone.state.is_flying
        assert drone.state.armed

        # Inject failure
        scenario.trigger(drone.simulator)

        # Wait for failsafe activation
        start_time = time.time()
        while time.time() - start_time < scenario.timeout_seconds:
            current_failsafe = drone.state.failsafe_mode

            if current_failsafe == scenario.expected_failsafe:
                return True, "Failsafe activated correctly"

            await asyncio.sleep(0.1)

        return False, f"Expected {scenario.expected_failsafe}, got {drone.state.failsafe_mode}"

@pytest.mark.parametrize("scenario", FailureModeTester.SCENARIOS, ids=lambda s: s.mode.name)
@pytest.mark.sitl
@pytest.mark.asyncio
async def test_failure_mode(scenario, sitl_drone):
    """Test each failure mode activates correct failsafe"""
    tester = FailureModeTester()
    success, msg = await tester.run_scenario(scenario, sitl_drone)
    assert success, msg
```

### 3.2 Heartbeat Loss Simulation

```python
# test_heartbeat_loss.py
import pytest
import asyncio
from mavsdk import System
from datetime import datetime, timedelta

class HeartbeatMonitor:
    """Monitor and simulate heartbeat conditions"""

    HEARTBEAT_TIMEOUT = 5.0  # seconds before failsafe
    HEARTBEAT_HZ = 1  # Expected heartbeat frequency

    def __init__(self, drone: System):
        self.drone = drone
        self.last_heartbeat = datetime.now()
        self.heartbeat_count = 0
        self._monitor_task = None

    async def start_monitoring(self):
        """Start heartbeat monitoring"""
        async for health in self.drone.telemetry.health():
            self.last_heartbeat = datetime.now()
            self.heartbeat_count += 1

    def is_heartbeat_alive(self) -> bool:
        """Check if heartbeat is within timeout"""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        return elapsed < self.HEARTBEAT_TIMEOUT

class HeartbeatLossSimulator:
    """Simulate various heartbeat loss scenarios"""

    async def simulate_complete_loss(self, duration: float):
        """Complete GCS disconnection"""
        # Simulate by blocking MAVLink traffic
        pass

    async def simulate_intermittent_loss(self, loss_duration: float, interval: float, count: int):
        """Intermittent connection drops"""
        for i in range(count):
            await self.simulate_complete_loss(loss_duration)
            await asyncio.sleep(interval)

    async def simulate_delayed_heartbeat(self, delay: float):
        """Heartbeat arrives but delayed"""
        pass

@pytest.mark.sitl
@pytest.mark.asyncio
class TestHeartbeatLoss:
    """Test suite for heartbeat loss scenarios"""

    async def test_heartbeat_timeout_triggers_failsafe(self, sitl_drone):
        """Verify heartbeat loss triggers configured failsafe"""
        # Setup: Arm and takeoff
        await sitl_drone.action.arm()
        await sitl_drone.action.takeoff()

        # Wait for stable flight
        await asyncio.sleep(2)

        # Simulate heartbeat loss
        monitor = HeartbeatMonitor(sitl_drone)
        await monitor.start_monitoring()

        # Stop sending heartbeats (simulated)
        await sitl_drone.simulator.disconnect_gcs()

        # Wait for timeout + margin
        await asyncio.sleep(HeartbeatMonitor.HEARTBEAT_TIMEOUT + 2)

        # Verify failsafe activated
        async for status in sitl_drone.telemetry.status_text():
            if "failsafe" in status.text.lower():
                break

    async def test_heartbeat_recovery(self, sitl_drone):
        """Verify system recovers when heartbeat resumes"""
        # Trigger temporary loss
        await sitl_drone.simulator.disconnect_gcs()
        await asyncio.sleep(2)

        # Reconnect before timeout
        await sitl_drone.simulator.connect_gcs()

        # Verify normal operation continues
        async for armed in sitl_drone.telemetry.armed():
            assert armed, "Drone disarmed unexpectedly"
            break

    @pytest.mark.parametrize("delay", [0.5, 1.0, 2.0, 4.0])
    async def test_delayed_heartbeat_tolerance(self, sitl_drone, delay):
        """Test system tolerates heartbeat delays up to threshold"""
        # System should handle delays < timeout
        if delay < HeartbeatMonitor.HEARTBEAT_TIMEOUT:
            # Should not trigger failsafe
            pass
        else:
            # Should trigger failsafe
            pass
```

### 3.3 Network Partition Testing

```python
# test_network_partition.py
import pytest
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class PartitionScenario:
    """Network partition test scenario"""
    name: str
    partition_type: str  # ' gcs', 'companion', 'external'
    duration: float
    recovery_time: float
    expected_behavior: str

class NetworkPartitionSimulator:
    """Simulate network partitions for testing"""

    SCENARIOS = [
        PartitionScenario(
            name="GCS partition during mission",
            partition_type="gcs",
            duration=30,
            recovery_time=10,
            expected_behavior="continue_mission"
        ),
        PartitionScenario(
            name="Companion computer partition",
            partition_type="companion",
            duration=15,
            recovery_time=5,
            expected_behavior="fallback_to_autopilot"
        ),
        PartitionScenario(
            name="External API partition",
            partition_type="external",
            duration=60,
            recovery_time=0,
            expected_behavior="degraded_mode"
        ),
    ]

    async def partition_gcs(self, duration: float):
        """Simulate GCS connection loss"""
        # Implement iptables rules or network namespace
        pass

    async def partition_companion(self, duration: float):
        """Simulate companion computer disconnection"""
        pass

    async def throttle_connection(self, bandwidth: int, latency: int):
        """Simulate degraded network conditions"""
        pass

@pytest.mark.sitl
@pytest.mark.asyncio
class TestNetworkPartition:
    """Network partition resilience tests"""

    @pytest.mark.parametrize("scenario", NetworkPartitionSimulator.SCENARIOS)
    async def test_partition_recovery(self, sitl_drone, scenario):
        """Test drone behavior during and after network partitions"""
        simulator = NetworkPartitionSimulator()

        # Start mission
        await self._start_mission(sitl_drone)

        # Apply partition
        if scenario.partition_type == "gcs":
            await simulator.partition_gcs(scenario.duration)
        elif scenario.partition_type == "companion":
            await simulator.partition_companion(scenario.duration)

        # Monitor behavior during partition
        await asyncio.sleep(scenario.duration / 2)

        # Verify expected behavior
        status = await sitl_drone.telemetry.flight_mode()
        assert self._verify_behavior(status, scenario.expected_behavior)

        # Recover connection
        await asyncio.sleep(scenario.recovery_time)

        # Verify full recovery
        assert await self._is_fully_recovered(sitl_drone)

    async def test_partition_during_landing(self, sitl_drone):
        """Critical: Partition during landing phase"""
        # Start landing
        await sitl_drone.action.land()

        # Simulate partition mid-landing
        await sitl_drone.simulator.partition_gcs(10)

        # Verify landing continues safely (autonomous)
        async for in_air in sitl_drone.telemetry.in_air():
            if not in_air:
                break

        # Verify safe on ground
        assert not await sitl_drone.telemetry.armed()

    async def test_multiple_simultaneous_partitions(self, sitl_drone):
        """Worst case: Multiple simultaneous connection losses"""
        pass
```

### 3.4 RC Override Testing

```python
# test_rc_override.py
import pytest
import asyncio
from enum import Enum

class RCMode(Enum):
    """RC control modes"""
    PASS_THROUGH = "passthrough"
    ACRO = "acro"
    STABILIZE = "stabilize"
    LOITER = "loiter"
    RTL = "rtl"
    LAND = "land"

class RCOverrideTester:
    """Test RC override functionality"""

    RC_CHANNELS = {
        'throttle': 3,
        'aileron': 1,
        'elevator': 2,
        'rudder': 4,
        'mode': 5,
        'aux1': 6,
        'aux2': 7,
    }

    async def simulate_rc_input(self, drone, channels: dict):
        """Simulate RC transmitter input"""
        for name, value in channels.items():
            ch_num = self.RC_CHANNELS[name]
            await drone.simulator.set_rc_channel(ch_num, value)

    async def test_rc_failsafe(self, drone):
        """Test RC loss failsafe activation"""
        # Normal RC input
        await self.simulate_rc_input(drone, {
            'throttle': 1500,
            'aileron': 1500,
            'elevator': 1500,
            'rudder': 1500,
        })

        # Simulate RC loss (values go to failsafe positions)
        await drone.simulator.rc_loss()

        # Verify failsafe action taken
        async for status in drone.telemetry.status_text():
            if "rc failsafe" in status.text.lower():
                break

@pytest.mark.sitl
@pytest.mark.asyncio
class TestRCOverride:
    """RC override and failsafe tests"""

    async def test_mode_switch_via_rc(self, sitl_drone):
        """Test RC mode channel switches flight modes"""
        tester = RCOverrideTester()

        # Switch to STABILIZE
        await tester.simulate_rc_input(sitl_drone, {'mode': 1200})
        await asyncio.sleep(0.5)

        mode = await sitl_drone.telemetry.flight_mode()
        assert mode == "Stabilize"

        # Switch to LOITER
        await tester.simulate_rc_input(sitl_drone, {'mode': 1500})
        await asyncio.sleep(0.5)

        mode = await sitl_drone.telemetry.flight_mode()
        assert mode == "Loiter"

    async def test_rc_override_during_mission(self, sitl_drone):
        """RC can take control during auto mission"""
        # Start auto mission
        await self._start_mission(sitl_drone)

        # Verify in auto mode
        mode = await sitl_drone.telemetry.flight_mode()
        assert "Auto" in mode

        # RC takes control (mode switch)
        tester = RCOverrideTester()
        await tester.simulate_rc_input(sitl_drone, {'mode': 1200})  # Stabilize

        await asyncio.sleep(0.5)

        # Verify switched to manual mode
        mode = await sitl_drone.telemetry.flight_mode()
        assert "Stabilize" in mode

    async def test_rc_emergency_stop(self, sitl_drone):
        """Emergency stop via RC"""
        # Arm and takeoff
        await sitl_drone.action.arm()
        await sitl_drone.action.takeoff()

        # Trigger emergency stop (throttle low + yaw full)
        tester = RCOverrideTester()
        await tester.simulate_rc_input(sitl_drone, {
            'throttle': 1000,  # Minimum
            'rudder': 2000,    # Full right
        })

        # Hold for 2 seconds (typical emergency stop timeout)
        await asyncio.sleep(2.1)

        # Verify disarmed
        async for armed in sitl_drone.telemetry.armed():
            assert not armed, "Emergency stop failed"
            break
```

---

## 4. Pytest Patterns for Drone Testing

### 4.1 Complete Test Structure

```python
# tests/conftest.py
import pytest
import asyncio
from typing import AsyncGenerator
from mavsdk import System

# Test categorization markers
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "sitl: Software-in-the-loop tests")
    config.addinivalue_line("markers", "hitl: Hardware-in-the-loop tests")
    config.addinivalue_line("markers", "safety: Safety-critical tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "fuzz: Fuzzing tests")

# Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def mock_drone():
    """Mock drone for unit tests"""
    from unittest.mock import AsyncMock, Mock

    drone = Mock(spec=System)
    drone.connect = AsyncMock()
    drone.action.arm = AsyncMock()
    drone.action.disarm = AsyncMock()
    drone.action.takeoff = AsyncMock()
    drone.action.land = AsyncMock()

    return drone

@pytest.fixture(scope="module")
async def sitl_drone() -> AsyncGenerator[System, None]:
    """Real SITL drone for integration tests"""
    drone = System()

    # Connect to SITL instance
    await drone.connect(system_address="udp://:14540")

    # Wait for connection
    async for state in drone.core.connection_state():
        if state.is_connected:
            break

    yield drone

    # Cleanup
    try:
        await drone.action.disarm()
    except:
        pass

@pytest.fixture(scope="module")
def hitl_drone():
    """HITL drone - requires physical hardware"""
    pytest.skip("HITL tests require hardware")

@pytest.fixture
def safety_monitor():
    """Safety monitor for test safety"""
    from safety_assertions import SafetyMonitor
    return SafetyMonitor()
```

### 4.2 Test Organization

```
tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── test_commands.py      # Command validation
│   ├── test_safety.py        # Safety logic
│   ├── test_navigation.py    # Navigation algorithms
│   └── test_mavlink.py       # MAVLink parsing
├── integration/
│   ├── test_mavsdk.py        # MAVSDK integration
│   ├── test_simulator.py     # Simulator interface
│   └── test_mission.py       # Mission execution
├── sitl/
│   ├── test_takeoff_land.py
│   ├── test_mission.py
│   ├── test_failsafe.py
│   └── test_geofence.py
├── hitl/
│   ├── test_sensors.py
│   ├── test_rc.py
│   └── test_esc.py
├── fuzz/
│   └── test_command_fuzz.py
└── safety/
    ├── test_failure_modes.py
    ├── test_heartbeat_loss.py
    ├── test_network_partition.py
    └── test_rc_override.py
```

### 4.3 Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run SITL tests (requires simulator)
pytest -m sitl --timeout=300

# Run safety-critical tests with 100% coverage requirement
pytest -m safety --cov=src/safety --cov-fail-under=100

# Run HITL tests (requires hardware)
pytest -m hitl --hardware-port=/dev/ttyACM0

# Run with parallel execution
pytest -n auto

# Run with detailed reporting
pytest -v --tb=short --durations=10

# Run fuzzing tests
pytest -m fuzz --fuzz-time=300

# Skip slow tests for quick feedback
pytest -m "not slow"

# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=xml
```

### 4.4 Advanced Pytest Patterns

```python
# tests/test_parametrize_patterns.py
import pytest
from hypothesis import given, strategies as st

# Parametrized fixtures
@pytest.fixture(params=["udp://:14540", "tcp://localhost:5760", "serial:///dev/ttyACM0"])
def connection_string(request):
    return request.param

# Cartesian product parametrize
@pytest.mark.parametrize("speed", [5, 10, 15])
@pytest.mark.parametrize("altitude", [10, 50, 100])
@pytest.mark.sitl
@pytest.mark.asyncio
async def test_climb_rates(sitl_drone, speed, altitude):
    """Test various speed/altitude combinations"""
    pass

# Conditional skipping
@pytest.mark.skipif(
    not os.environ.get("HITL_HARDWARE"),
    reason="No HITL hardware configured"
)
@pytest.mark.hitl
async def test_esc_calibration(hitl_drone):
    pass

# Expected failures
@pytest.mark.xfail(reason="Known issue with GPS simulation")
async def test_gps_precision(sitl_drone):
    pass

# Custom test collection
@pytest.mark.safety
@pytest.mark.critical  # Custom marker for critical safety tests
async def test_failsafe_battery_critical(sitl_drone):
    pass

# Timeout decorator
@pytest.mark.timeout(60)
async def test_long_mission(sitl_drone):
    pass

# Hypothesis property-based with pytest
@pytest.mark.hypothesis
@given(
    lat=st.floats(min_value=-90, max_value=90),
    lon=st.floats(min_value=-180, max_value=180)
)
def test_coordinate_parsing(lat, lon):
    coord = Coordinate(lat, lon)
    assert coord.is_valid()
```

### 4.5 Test Reporting and CI Integration

```yaml
# .github/workflows/drone-tests.yml
name: Drone Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e ".[test]"

      - name: Run unit tests
        run: |
          pytest -m unit --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  sitl-tests:
    runs-on: ubuntu-latest
    services:
      px4-sitl:
        image: px4io/px4-dev-simulation:latest
        ports:
          - 14540:14540/udp
    steps:
      - uses: actions/checkout@v4

      - name: Run SITL tests
        run: |
          pytest -m sitl --timeout=600 --reruns=2

  static-analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run pylint
        run: |
          pylint src/ --rcfile=.pylintrc

      - name: Run mypy
        run: |
          mypy src/ --strict

      - name: Run bandit
        run: |
          bandit -r src/ -c pyproject.toml

      - name: Check coverage threshold
        run: |
          pytest --cov=src --cov-fail-under=95
```

---

## 5. Best Practices Summary

### Testing Pyramid for Drone Software

```
         /\
        /  \
       /E2E \      <- HITL tests (few, slow, expensive)
      /------\
     /        \
    / Integration\   <- SITL tests (moderate, mission scenarios)
   /--------------\
  /                \
 /     Unit Tests    \  <- Fast, many, safety logic
/----------------------\
```

### Key Metrics

| Metric | Target | Safety-Critical |
|--------|--------|----------------|
| Unit test coverage | >80% | 100% |
| SITL scenario coverage | >90% | All missions |
| HITL regression tests | Core functions | All flight modes |
| Static analysis issues | 0 high/critical | 0 all |
| Test execution time | <10 min unit | <2 hours full |

### Pre-Flight Checklist (for tests)

- [ ] All unit tests pass
- [ ] Static analysis clean
- [ ] SITL tests pass in simulator
- [ ] HITL tests pass on hardware
- [ ] Failure mode tests verify failsafe behavior
- [ ] RC override tested
- [ ] Heartbeat loss scenarios tested
- [ ] Network partition scenarios tested
- [ ] Property-based tests pass (fuzzing)
- [ ] Coverage meets threshold

---

## References

1. PX4 Documentation: https://docs.px4.io/main/en/
2. ArduPilot Testing: https://ardupilot.org/dev/docs/
3. MAVSDK Python: https://github.com/mavlink/MAVSDK-Python
4. DO-178C Software Considerations in Airborne Systems
5. IEC 61508 Functional Safety of Electrical/Electronic/Programmable Electronic Safety-related Systems
6. Gazebo Simulator: https://gazebosim.org/
7. jMAVSim: https://github.com/PX4/jMAVSim
8. pytest-asyncio: https://pytest-asyncio.readthedocs.io/
9. Hypothesis testing: https://hypothesis.readthedocs.io/
10. Atheris fuzzing: https://github.com/google/atheris

---

*Document version: 1.0*
*Generated for safety-critical drone software development*
