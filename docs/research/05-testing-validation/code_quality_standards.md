# Code Quality Standards for Safety-Critical Drone Software

**Version:** 1.1.0  
**Classification:** Safety-Critical (SIL-2 equivalent)  
**Applicable Standards:** DO-178C, ISO/IEC 61508, ASTM F3269, F3322-22  

---

## Table of Contents

1. [Python Coding Standards](#1-python-coding-standards)
   - [1.1 Type Hints (mypy strict mode)](#11-type-hints-mypy-strict-mode)
   - [1.2 Docstring Format (Google style)](#12-docstring-format-google-style)
   - [1.3 Import Organization (isort)](#13-import-organization-isort)
   - [1.4 Error Handling Patterns for Async Code](#14-error-handling-patterns-for-async-code)
2. [Static Analysis Setup](#2-static-analysis-setup)
   - [2.1 mypy Configuration](#21-mypy-configuration)
   - [2.2 pylint Safety-Focused Rules](#22-pylint-safety-focused-rules)
   - [2.3 bandit Security Scanning](#23-bandit-security-scanning)
   - [2.4 pre-commit Hooks](#24-pre-commit-hooks)
   - [2.5 Running Static Analysis](#25-running-static-analysis)
   - [2.6 CI Integration](#26-ci-integration)
3. [Runtime Safety Patterns](#3-runtime-safety-patterns)
   - [3.1 Assert vs Exception vs Log](#31-assert-vs-exception-vs-log)
   - [3.2 Input Validation Layers](#32-input-validation-layers)
   - [3.3 Timeout Decorators for Async Operations](#33-timeout-decorators-for-async-operations)
   - [3.4 Resource Cleanup (Context Managers)](#34-resource-cleanup-context-managers)
4. [Testing Requirements](#4-testing-requirements)
   - [4.1 pytest Structure](#41-pytest-structure)
   - [4.2 Coverage Thresholds](#42-coverage-thresholds)
   - [4.3 Property-Based Testing with Hypothesis](#43-property-based-testing-with-hypothesis)
5. [Documentation Standards](#5-documentation-standards)
   - [5.1 Architecture Decision Records (ADR)](#51-architecture-decision-records-adr)
   - [5.2 API Documentation](#52-api-documentation)
   - [5.3 Safety Rationale Comments](#53-safety-rationale-comments)
6. [Appendix: Configuration Files](#6-appendix-configuration-files)

---

## 1. Python Coding Standards

### 1.1 Type Hints (mypy strict mode)

All Python code must include comprehensive type hints. The project uses mypy in strict mode.

#### Basic Type Hints

```python
from typing import Optional, Union, List, Dict, Any, Protocol, TypeVar, Generic, Final
from collections.abc import Callable, Iterable, Iterator, AsyncIterator
from decimal import Decimal

# Function signatures must be fully typed
def calculate_hover_power(
    mass_kg: float,
    rotor_count: int,
    air_density: float = 1.225,
) -> float:
    """Calculate hover power required for given mass and configuration."""
    ...

# Return type must be explicit, even for None
def initialize_flight_controller(config: FlightConfig) -> None:
    """Initialize the flight controller with given configuration."""
    ...

# Complex types
def process_waypoints(
    waypoints: List[Waypoint],
    validator: Callable[[Waypoint], bool],
) -> Dict[str, List[Waypoint]]:
    """Process waypoints through validator and categorize."""
    ...
```

#### Generic Types

```python
from typing import TypeVar, Generic, Final

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class SafetyBuffer(Generic[T]):
    """Thread-safe circular buffer for safety-critical data."""

    def __init__(self, capacity: int) -> None:
        self._capacity: Final[int] = capacity
        self._buffer: List[T] = []

    def push(self, item: T) -> None:
        """Add item to buffer, removing oldest if at capacity."""
        ...

    def get_all(self) -> tuple[T, ...]:
        """Return all items as immutable tuple."""
        ...
```

#### Protocol Classes (Structural Subtyping)

```python
from typing import Protocol, runtime_checkable
from decimal import Decimal

@runtime_checkable
class Navigable(Protocol):
    """Protocol for objects that can provide navigation data."""

    @property
    def latitude(self) -> Decimal:
        """Latitude in decimal degrees."""
        ...

    @property
    def longitude(self) -> Decimal:
        """Longitude in decimal degrees."""
        ...

    @property
    def altitude_msl(self) -> float:
        """Altitude above mean sea level in meters."""
        ...

def validate_position(obj: Navigable) -> bool:
    """Validate that a navigable object has valid coordinates."""
    ...
```

#### Optional and Union Types

```python
from typing import Optional, Union

def find_landing_zone(
    current_position: Position,
    emergency: bool = False,
) -> Optional[LandingZone]:
    """Find suitable landing zone, returning None if none available."""
    ...

# Use Union for multiple distinct types with different handling
def parse_altitude(value: Union[str, float, int]) -> float:
    """Parse altitude from various input formats."""
    if isinstance(value, str):
        return float(value)
    return float(value)

# Python 3.10+ syntax (preferred when available)
def parse_altitude_modern(value: str | float | int) -> float:
    """Parse altitude using modern union syntax."""
    ...
```

#### Async Type Hints

```python
from typing import AsyncIterator, Awaitable
import asyncio

async def stream_telemetry(
    drone_id: str,
    frequency_hz: float,
) -> AsyncIterator[TelemetryFrame]:
    """Stream telemetry data at specified frequency."""
    ...

async def fetch_mission_status(mission_id: str) -> MissionStatus:
    """Fetch current mission status."""
    ...

# Callbacks with async support
async def execute_with_retry(
    operation: Callable[[], Awaitable[T]],
    max_attempts: int = 3,
) -> T:
    """Execute async operation with retry logic."""
    ...
```

#### Type Annotation Requirements

| Element | Requirement | Example |
|---------|-------------|---------|
| Function parameters | Always | `def foo(x: int) -> None` |
| Return values | Always | `-> Result[T, E]` |
| Class attributes | Always | `_value: Final[float]` |
| Variables (ambiguous) | Required | `data: list[int] = []` |
| Generic types | Use full form | `dict[str, int]` not `{}` |
| None-able | Use Optional | `Optional[str]` or `\| None` |
| Literals | Use Literal | `Literal["ARMED", "DISARMED"]` |

### 1.2 Docstring Format (Google style)

All public modules, classes, methods, and functions must have Google-style docstrings.

#### Module Docstrings

```python
"""Flight controller safety monitoring module.

This module implements real-time safety monitoring for the flight controller,
including battery checks, geofence enforcement, and emergency landing triggers.

Example:
    >>> from drone.safety import SafetyMonitor
    >>> monitor = SafetyMonitor(battery_threshold=20.0)
    >>> monitor.enable()

Attributes:
    DEFAULT_BATTERY_THRESHOLD: Default minimum battery percentage for safe operation.
    MAX_GEOFENCE_VIOLATIONS: Maximum allowed geofence violations before emergency.

Note:
    Safety monitor runs in a separate thread and must be properly
    initialized before flight operations begin.
"""
```

#### Class Docstrings

```python
class GeofenceValidator:
    """Validates drone position against defined geofence boundaries.

    Enforces both altitude and lateral boundaries to prevent
    unauthorized airspace entry and altitude violations.

    Args:
        boundaries: List of geofence boundary polygons.
        max_altitude_msl: Maximum allowed altitude in meters MSL.
        min_altitude_agl: Minimum safe altitude above ground in meters.

    Attributes:
        violation_count: Number of geofence violations since initialization.
        last_violation: Timestamp of most recent violation.

    Raises:
        ValueError: If boundaries list is empty or altitudes are invalid.
        GeofenceInitializationError: If validator fails to load boundary data.

    Example:
        >>> boundaries = load_boundaries_from_kml("airspace.kml")
        >>> validator = GeofenceValidator(
        ...     boundaries=boundaries,
        ...     max_altitude_msl=120.0,
        ...     min_altitude_agl=10.0,
        ... )
        >>> validator.validate_position(current_pos)
    """

    def __init__(
        self,
        boundaries: list[Polygon],
        max_altitude_msl: float,
        min_altitude_agl: float,
    ) -> None:
        """Initialize geofence validator."""
        ...
```

#### Function/Method Docstrings

```python
def calculate_failsafe_landing_zone(
    current_position: Position,
    battery_remaining: float,
    wind_speed: float,
    available_sites: list[LandingZone],
) -> LandingZone:
    """Calculate optimal landing zone for failsafe landing.

    Selects the safest landing zone considering battery endurance,
    wind conditions, and landing site characteristics.

    Args:
        current_position: Current drone position in WGS84 coordinates.
        battery_remaining: Estimated remaining flight time in seconds.
        wind_speed: Current wind speed in m/s at landing altitude.
        available_sites: List of pre-surveyed landing zones.

    Returns:
        Selected landing zone with highest safety score.

    Raises:
        InsufficientBatteryError: If no reachable landing zone exists.
        NoValidLandingZoneError: If no suitable landing zone available.

    Note:
        Algorithm prioritizes safety over proximity. May select a
        farther landing zone if it offers better wind protection.

    Safety Note:
        This method must complete within 500ms to ensure timely
        failsafe activation. Complex terrain may require fallback.
    """
    ...
```

### 1.3 Import Organization (isort)

Imports must be organized following isort configuration with safety-critical grouping.

#### Import Order

```python
"""Example module showing proper import organization."""

# 1. Future imports (must be first)
from __future__ import annotations

# 2. Standard library imports (alphabetical)
import asyncio
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

# 3. Third-party imports (alphabetical)
import numpy as np
from pydantic import BaseModel, Field, validator
from scipy.spatial import distance

# 4. First-party project imports (alphabetical)
from drone.config import SafetyThresholds
from drone.exceptions import FlightSafetyError, NavigationError
from drone.models.position import Position, Waypoint
from drone.utils.coordinates import wgs84_to_enu

# 5. Local application imports (when applicable)

# 6. TYPE_CHECKING imports (only for type checking, not runtime)
if TYPE_CHECKING:
    from drone.flight_controller import FlightController
    from drone.telemetry import TelemetryClient
```

#### Import Style Guidelines

```python
# Preferred: Explicit imports
from drone.models.position import Position, Waypoint
from drone.utils.coordinates import wgs84_to_enu

# Avoid: Wildcard imports (except in __init__.py for public API)
# from drone.models import *  # DON'T DO THIS

# Preferred: Import modules for heavy use
import numpy as np

# Preferred: Use relative imports within packages
from .exceptions import FlightSafetyError
from ..config import Settings

# Avoid: Circular imports via TYPE_CHECKING
if TYPE_CHECKING:
    from .flight_controller import FlightController  # Only imported for type hints
```

#### Import Rules

| Rule | Rationale |
|------|-----------|
| No `import *` | Explicit dependencies only |
| No circular imports | System must be analyzable |
| Prefer absolute imports | Clear dependency graph |
| Group by safety level | Standard < Third-party < Internal |
| Use `typing.TYPE_CHECKING` | Break circular type dependencies |

### 1.4 Error Handling Patterns for Async Code

#### Structured Exception Hierarchy

```python
"""Safety-critical exception hierarchy for drone operations."""
import time

class DroneError(Exception):
    """Base exception for all drone-related errors."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.timestamp = time.time()


class FlightSafetyError(DroneError):
    """Base for all flight safety violations."""

    def __init__(self, message: str, severity: SafetySeverity) -> None:
        super().__init__(message, error_code="SAFETY_VIOLATION")
        self.severity = severity


class GeofenceViolation(FlightSafetyError):
    """Raised when drone exits authorized flight area."""

    def __init__(
        self,
        position: Position,
        boundary: str,
        exceeded_by: float,
    ) -> None:
        message = f"Geofence violation at {position}: exceeded {boundary} by {exceeded_by}m"
        super().__init__(message, SafetySeverity.CRITICAL)
        self.position = position
        self.boundary = boundary
        self.exceeded_by = exceeded_by


class BatteryCritical(FlightSafetyError):
    """Raised when battery level drops below critical threshold."""

    def __init__(self, current_level: float, threshold: float) -> None:
        message = f"Battery critical: {current_level:.1f}% (threshold: {threshold}%)"
        super().__init__(message, SafetySeverity.EMERGENCY)
        self.current_level = current_level
        self.threshold = threshold
```

#### Async Error Handling Patterns

```python
import asyncio
from contextlib import asynccontextmanager
from typing import TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')

class AsyncSafetyManager:
    """Manages async safety operations with proper error handling."""

    async def execute_safety_critical(
        self,
        operation: Callable[[], Awaitable[T]],
        timeout_seconds: float = 5.0,
        retries: int = 2,
    ) -> T:
        """Execute safety-critical operation with timeout and retry.

        Args:
            operation: Async operation to execute.
            timeout_seconds: Maximum time to wait for operation.
            retries: Number of retry attempts on transient failure.

        Returns:
            Operation result.

        Raises:
            SafetyOperationError: If operation fails after all retries.
            asyncio.TimeoutError: If operation exceeds timeout.
        """
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                return await asyncio.wait_for(
                    operation(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Safety operation timeout (attempt {attempt + 1})")
            except TransientError as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
            except SafetyCriticalError:
                # Never retry safety-critical failures
                raise

        raise SafetyOperationError(
            f"Failed after {retries + 1} attempts"
        ) from last_error

    @asynccontextmanager
    async def monitored_operation(self, name: str):
        """Context manager for monitored async operations."""
        start_time = asyncio.get_event_loop().time()
        try:
            yield self
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            await self._log_failure(name, elapsed, e)
            raise
        else:
            elapsed = asyncio.get_event_loop().time() - start_time
            await self._log_success(name, elapsed)
```

#### Exception Chaining

```python
def load_mission_file(path: Path) -> Mission:
    """Load mission from file with proper exception handling."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise MissionLoadError(f"Mission file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise MissionLoadError(f"Invalid JSON in mission file: {e}") from e
    except PermissionError as e:
        raise MissionLoadError(f"Cannot read mission file: {path}") from e

    try:
        return Mission.from_dict(data)
    except KeyError as e:
        raise MissionValidationError(f"Missing required field: {e}") from e
    except ValueError as e:
        raise MissionValidationError(f"Invalid mission data: {e}") from e
```

---

## 2. Static Analysis Setup

### 2.1 mypy Configuration

See `pyproject.toml` for complete configuration. Key settings:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
extra_checks = true
```

### 2.2 pylint Safety-Focused Rules

```toml
[tool.pylint.main]
py-version = "3.11"
ignore-patterns = ["^\\."]
load-plugins = [
    "pylint.extensions.check_elif",
    "pylint.extensions.comparetozero",
    "pylint.extensions.comparison_placement",
    "pylint.extensions.confusing_elif",
    "pylint.extensions.for_any_all",
    "pylint.extensions.mccabe",
    "pylint.extensions.overlapping_exceptions",
    "pylint.extensions.redefined_loop_name",
    "pylint.extensions.typing",
]

[tool.pylint.messages_control]
disable = [
    "missing-module-docstring",
    "missing-class-docstring",
    "too-few-public-methods",
    "too-many-arguments",
    "too-many-instance-attributes",
    "too-many-lines",
    "too-many-locals",
    "too-many-branches",
    "too-many-return-statements",
    "protected-access",
]

[tool.pylint.design]
max-args = 10
max-attributes = 15
max-bool-expr = 5
max-branches = 15
max-locals = 20
max-parents = 7
max-public-methods = 25
max-returns = 11
max-statements = 60
```

### 2.3 bandit Security Scanning

See `.bandit.yaml` for complete configuration.

Key tests enabled:
- B102: exec_used
- B105-B107: hardcoded_password
- B301-B324: Blacklisted function calls
- B401-B413: Import of unsafe modules
- B501-B507: SSL/TLS configuration issues
- B602-B607: Subprocess security

### 2.4 pre-commit Hooks

See `.pre-commit-config.yaml` for complete configuration.

Key hooks:
- Black code formatter
- isort import sorting
- mypy type checking
- pylint static analysis
- bandit security scanning
- Safety dependency checking
- pytest unit tests
- Coverage threshold checking

### 2.5 Running Static Analysis

```bash
# Run all checks
./scripts/quality-check.sh

# Individual tools
mypy src/drone --strict
pylint src/drone --rcfile=pyproject.toml
bandit -r src/drone -c .bandit.yaml
pytest --cov=drone --cov-report=term-missing --cov-fail-under=90

# Pre-commit on all files
pre-commit run --all-files

# Pre-commit on staged files only
pre-commit run
```

### 2.6 CI Integration

```yaml
# .github/workflows/quality.yml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt

      - name: Run mypy
        run: mypy src/drone --strict

      - name: Run pylint
        run: pylint src/drone

      - name: Run bandit
        run: bandit -r src/drone -c .bandit.yaml

      - name: Run tests with coverage
        run: pytest --cov=drone --cov-report=xml --cov-fail-under=90

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 3. Runtime Safety Patterns

### 3.1 Assert vs Exception vs Log

| Situation | Use | Example |
|-----------|-----|---------|
| Internal invariant | `assert` | Precondition that should never fail in production |
| External input validation | `Exception` | Invalid user input, sensor reading out of range |
| Safety-critical condition | `Exception` | Battery critical, geofence violation |
| Recoverable degradation | `Log` | Minor sensor drift, non-critical timeout |
| Debugging aid | `assert` | Development-only checks, disabled in release |

#### Assert Usage (Internal Invariants Only)

```python
def process_waypoints(waypoints: list[Waypoint]) -> None:
    """Process waypoint list."""
    # Internal invariant: list should be sorted by sequence
    # This is a programming error if violated, not a runtime condition
    assert all(
        waypoints[i].sequence < waypoints[i + 1].sequence
        for i in range(len(waypoints) - 1)
    ), "Waypoints must be pre-sorted by sequence number"

    for wp in waypoints:
        process_waypoint(wp)
```

#### Exception Usage (External/Runtime Conditions)

```python
def validate_sensor_reading(reading: SensorReading) -> None:
    """Validate incoming sensor reading."""
    # External input: must raise exception
    if reading.timestamp > time.time():
        raise SensorValidationError("Timestamp from future")

    if reading.value < reading.sensor.min_value:
        raise SensorValidationError(
            f"Value {reading.value} below minimum {reading.sensor.min_value}"
        )

    # Safety-critical: must raise exception
    if reading.sensor.type == SensorType.BATTERY and reading.value < 10.0:
        raise BatteryCritical(reading.value, 10.0)
```

#### Logging Usage (Non-Critical Events)

```python
async def telemetry_loop(self) -> None:
    """Main telemetry collection loop."""
    while self._running:
        try:
            frame = await self._collect_frame()
            await self._process_frame(frame)
        except asyncio.TimeoutError:
            # Log but continue - telemetry is important but not safety-critical
            logger.warning("Telemetry collection timeout, retrying...")
            await asyncio.sleep(0.1)
        except SensorTemporarilyUnavailable:
            # Degraded but not fatal
            logger.info("Sensor temporarily unavailable, using cached data")
            self._use_cached_telemetry()
```

### 3.2 Input Validation Layers

#### Defense in Depth Pattern

```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class PositionInput(BaseModel):
    """Validated position input with multiple validation layers."""

    # Layer 1: Pydantic type validation
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    altitude_msl: float = Field(..., ge=-500, le=20000)

    # Layer 2: Custom validators
    @validator('latitude', 'longitude')
    def validate_precision(cls, v: Decimal) -> Decimal:
        """Ensure coordinate precision is sufficient."""
        if v.as_tuple().exponent < -8:
            raise ValueError("Coordinate precision exceeds 8 decimal places")
        return v

    @validator('altitude_msl')
    def validate_altitude_realistic(cls, v: float) -> float:
        """Ensure altitude is physically realistic for drone operations."""
        if v > 400:  # Standard US altitude limit
            raise ValueError("Altitude exceeds typical drone operating limits")
        return v


class SafetyValidator:
    """Layer 3: Business logic validation."""

    def validate_position_for_flight(
        self,
        position: Position,
        mission_context: MissionContext,
    ) -> ValidatedPosition:
        """Apply business rules and safety constraints."""
        # Check against geofence
        if not self._geofence.contains(position):
            raise GeofenceViolation(position, self._geofence.name)

        # Check against mission bounds
        if not mission_context.boundary.contains(position):
            raise PositionOutsideMissionArea(position)

        # Check for no-fly zones
        for nfz in self._no_fly_zones:
            if nfz.contains(position):
                raise NoFlyZoneViolation(position, nfz)

        return ValidatedPosition(
            position=position,
            validation_time=time.time(),
            validator_version=self._version,
        )
```

#### Sanitization Pattern

```python
class CommandSanitizer:
    """Sanitizes and validates incoming drone commands."""

    MAX_VELOCITY = 30.0  # m/s
    MAX_ACCELERATION = 15.0  # m/s^2
    MAX_ALTITUDE_CHANGE = 100.0  # m per command

    def sanitize_velocity_command(
        self,
        cmd: VelocityCommand,
        current_state: FlightState,
    ) -> SafeVelocityCommand:
        """Sanitize velocity command to safe limits."""
        # Clamp values
        vx = max(-self.MAX_VELOCITY, min(cmd.vx, self.MAX_VELOCITY))
        vy = max(-self.MAX_VELOCITY, min(cmd.vy, self.MAX_VELOCITY))
        vz = max(-self.MAX_VELOCITY, min(cmd.vz, self.MAX_VELOCITY))

        # Calculate resulting acceleration
        dt = cmd.timestamp - current_state.timestamp
        if dt > 0:
            ax = (vx - current_state.vx) / dt
            ay = (vy - current_state.vy) / dt
            az = (vz - current_state.vz) / dt

            # Limit acceleration
            if abs(ax) > self.MAX_ACCELERATION:
                vx = current_state.vx + copysign(self.MAX_ACCELERATION * dt, ax)
            if abs(ay) > self.MAX_ACCELERATION:
                vy = current_state.vy + copysign(self.MAX_ACCELERATION * dt, ay)
            if abs(az) > self.MAX_ACCELERATION:
                vz = current_state.vz + copysign(self.MAX_ACCELERATION * dt, az)

        return SafeVelocityCommand(vx=vx, vy=vy, vz=vz, original=cmd)
```

### 3.3 Timeout Decorators for Async Operations

```python
import asyncio
import functools
from typing import TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')

def timeout(
    seconds: float,
    *,
    raise_on_timeout: bool = True,
    safety_critical: bool = False,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to add timeout to async functions.

    Args:
        seconds: Maximum time to wait.
        raise_on_timeout: If True, raises TimeoutError; if False, returns None.
        safety_critical: If True, logs emergency on timeout.
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds,
                )
            except asyncio.TimeoutError as e:
                if safety_critical:
                    logger.critical(
                        f"SAFETY-CRITICAL TIMEOUT in {func.__name__} after {seconds}s"
                    )
                    # Trigger emergency protocol
                    await emergency_protocol.activate()

                if raise_on_timeout:
                    raise TimeoutError(
                        f"{func.__name__} timed out after {seconds}s"
                    ) from e
                return None  # type: ignore[return-value]

        return wrapper
    return decorator


# Usage examples
class FlightController:

    @timeout(0.5, safety_critical=True)
    async def get_attitude(self) -> Attitude:
        """Get current attitude - must be fast for control loop."""
        return await self._imu.read_attitude()

    @timeout(5.0, raise_on_timeout=False)
    async def fetch_weather(self) -> WeatherData | None:
        """Fetch weather - non-critical, can fail gracefully."""
        return await self._weather_api.get_current()

    @timeout(1.0, safety_critical=True)
    async def send_rtl_command(self) -> None:
        """Send return-to-land command - critical, must succeed."""
        await self._command_link.send_rtl()
```

### 3.4 Resource Cleanup (Context Managers)

#### Async Context Managers

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

class TelemetrySession:
    """Manages telemetry session with guaranteed cleanup."""

    @asynccontextmanager
    async def acquire(
        self,
        drone_id: str,
        priority: SessionPriority = SessionPriority.NORMAL,
    ) -> AsyncIterator[TelemetrySession]:
        """Acquire telemetry session with automatic cleanup."""
        session = TelemetrySession(drone_id, priority)
        try:
            await session._connect()
            await session._start_streaming()
            yield session
        finally:
            # Guaranteed cleanup even on exception
            await session._stop_streaming()
            await session._disconnect()
            await session._release_resources()


# Usage
async def collect_flight_data(drone_id: str) -> None:
    """Collect flight data with proper resource management."""
    async with TelemetrySession.acquire(drone_id, priority=SessionPriority.HIGH):
        # Session automatically cleaned up on exit
        data = await TelemetrySession.get_flight_data()
        process_data(data)
```

#### Multiple Resource Management

```python
@asynccontextmanager
async def flight_operation_resources(
    drone: Drone,
) -> AsyncIterator[tuple[TelemetryClient, CameraController, Logger]]:
    """Manage all resources needed for flight operation."""
    telemetry = TelemetryClient(drone)
    camera = CameraController(drone)
    logger = FlightLogger(drone)

    try:
        # Acquire in order
        await telemetry.connect()
        await camera.initialize()
        await logger.start()

        yield telemetry, camera, logger

    finally:
        # Release in reverse order, with individual error handling
        try:
            await logger.stop()
        except Exception as e:
            logger.error(f"Failed to stop logger: {e}")

        try:
            await camera.shutdown()
        except Exception as e:
            logger.error(f"Failed to shutdown camera: {e}")

        try:
            await telemetry.disconnect()
        except Exception as e:
            logger.error(f"Failed to disconnect telemetry: {e}")
```

---

## 4. Testing Requirements

### 4.1 pytest Structure

#### Test Organization

```
tests/
├── unit/                      # Unit tests (no external dependencies)
│   ├── test_models/
│   │   ├── test_position.py
│   │   └── test_waypoint.py
│   ├── test_utils/
│   │   └── test_coordinates.py
│   └── test_safety/
│       └── test_geofence.py
├── integration/               # Integration tests (with real dependencies)
│   ├── test_flight_controller/
│   ├── test_telemetry/
│   └── test_mission_planning/
├── e2e/                       # End-to-end tests
│   └── test_flight_scenarios/
├── property/                  # Property-based tests
│   └── test_invariants.py
├── fixtures/                  # Shared test fixtures
│   ├── __init__.py
│   ├── drones.py
│   ├── missions.py
│   └── positions.py
└── conftest.py               # Global pytest configuration
```

#### Test File Structure

```python
"""Tests for geofence validation."""

import pytest
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st

from drone.safety.geofence import GeofenceValidator
from drone.models.position import Position
from drone.exceptions import GeofenceViolation


class TestGeofenceValidator:
    """Test suite for geofence validator."""

    @pytest.fixture
    def validator(self) -> GeofenceValidator:
        """Create geofence validator with test boundaries."""
        boundaries = create_test_boundaries()
        return GeofenceValidator(
            boundaries=boundaries,
            max_altitude_msl=120.0,
            min_altitude_agl=10.0,
        )

    @pytest.fixture
    def valid_position(self) -> Position:
        """Create valid position within test geofence."""
        return Position(latitude=37.7749, longitude=-122.4194, altitude_msl=50.0)

    def test_valid_position_passes(self, validator, valid_position) -> None:
        """Test that valid position passes validation."""
        result = validator.validate(valid_position)
        assert result.is_valid
        assert result.violations == []

    def test_position_outside_boundary_fails(self, validator) -> None:
        """Test that position outside lateral boundary fails."""
        outside_pos = Position(latitude=0.0, longitude=0.0, altitude_msl=50.0)

        with pytest.raises(GeofenceViolation) as exc_info:
            validator.validate(outside_pos)

        assert "outside boundary" in str(exc_info.value)

    @pytest.mark.parametrize("altitude,expected_valid", [
        (5.0, False),   # Below minimum AGL
        (15.0, True),   # Just above minimum
        (115.0, True),  # Just below maximum
        (125.0, False), # Above maximum MSL
    ])
    def test_altitude_limits(
        self,
        validator,
        valid_position,
        altitude: float,
        expected_valid: bool,
    ) -> None:
        """Test altitude limit enforcement."""
        position = valid_position.with_altitude(altitude)

        if expected_valid:
            result = validator.validate(position)
            assert result.is_valid
        else:
            with pytest.raises(GeofenceViolation):
                validator.validate(position)

    @pytest.mark.asyncio
    async def test_async_validation(self, validator) -> None:
        """Test async validation with timeout."""
        position = Position(latitude=37.7749, longitude=-122.4194, altitude_msl=50.0)

        result = await validator.validate_async(position, timeout=1.0)

        assert result.is_valid

    @pytest.mark.slow
    def test_performance_many_positions(self, validator) -> None:
        """Test validation performance with many positions."""
        positions = generate_random_positions(count=10000)

        start_time = time.time()
        for pos in positions:
            validator.validate(pos)
        elapsed = time.time() - start_time

        # Must validate 10k positions in under 100ms
        assert elapsed < 0.1


class TestGeofenceEdgeCases:
    """Edge case tests for geofence validation."""

    def test_exactly_on_boundary(self, validator) -> None:
        """Test position exactly on boundary is valid."""
        # Implementation detail: boundary inclusive
        ...

    def test_nan_coordinates(self, validator) -> None:
        """Test handling of NaN coordinates."""
        pos = Position(latitude=float('nan'), longitude=0.0, altitude_msl=50.0)

        with pytest.raises(ValueError, match="Invalid coordinates"):
            validator.validate(pos)

    def test_infinite_altitude(self, validator) -> None:
        """Test handling of infinite altitude."""
        pos = Position(latitude=37.7749, longitude=-122.4194, altitude_msl=float('inf'))

        with pytest.raises(ValueError, match="Invalid altitude"):
            validator.validate(pos)
```

### 4.2 Coverage Thresholds

#### Coverage Configuration (pyproject.toml)

```toml
[tool.coverage.run]
source = ["src/drone"]
branch = true
parallel = true
concurrency = ["thread", "multiprocessing"]
omit = [
    "*/tests/*",
    "*/test_*",
    "*/__pycache__/*",
    "*/conftest.py",
    "*/migrations/*",
    "*/venv/*",
    "*/.venv/*",
]

[tool.coverage.report]
# Safety-critical modules require 95% coverage
fail_under = 90
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
    "@overload",
    "except ImportError:",
    "pass  # coverage: ignore",
]
show_missing = true
skip_covered = false
```

#### Per-Module Coverage Requirements

| Module Category | Minimum Coverage | Notes |
|-----------------|------------------|-------|
| Safety-critical (safety/, control/) | 95% | Geofence, failsafe, emergency |
| Navigation (navigation/) | 90% | Path planning, obstacle avoidance |
| Core models (models/) | 90% | Data structures, validation |
| Telemetry (telemetry/) | 85% | Data collection, logging |
| Utils (utils/) | 80% | Helper functions |
| Tests themselves | 100% | All test code must execute |

### 4.3 Property-Based Testing with Hypothesis

```python
"""Property-based tests for safety-critical invariants."""

from hypothesis import given, settings, strategies as st, assume, example
from hypothesis.stateful import RuleBasedStateMachine, rule, precondition

from drone.models.position import Position
from drone.safety.geofence import GeofenceValidator
from drone.navigation.path_planner import PathPlanner


class TestPositionInvariants:
    """Property-based tests for position validation invariants."""

    @given(
        lat=st.decimals(min_value=-90, max_value=90).filter(lambda x: not x.is_nan()),
        lon=st.decimals(min_value=-180, max_value=180).filter(lambda x: not x.is_nan()),
        alt=st.floats(min_value=-1000, max_value=50000),
    )
    @settings(max_examples=1000, deadline=None)
    def test_position_creation_preserves_values(
        self,
        lat: float,
        lon: float,
        alt: float,
    ) -> None:
        """Position creation preserves all coordinate values."""
        pos = Position(latitude=lat, longitude=lon, altitude_msl=alt)

        assert pos.latitude == lat
        assert pos.longitude == lon
        assert pos.altitude_msl == alt

    @given(
        pos1=st.builds(
            Position,
            latitude=st.decimals(min_value=-90, max_value=90),
            longitude=st.decimals(min_value=-180, max_value=180),
            altitude_msl=st.floats(min_value=0, max_value=1000),
        ),
        pos2=st.builds(
            Position,
            latitude=st.decimals(min_value=-90, max_value=90),
            longitude=st.decimals(min_value=-180, max_value=180),
            altitude_msl=st.floats(min_value=0, max_value=1000),
        ),
    )
    @settings(max_examples=500)
    def test_distance_is_symmetric(self, pos1: Position, pos2: Position) -> None:
        """Distance calculation is symmetric: d(a,b) == d(b,a)."""
        d1 = pos1.distance_to(pos2)
        d2 = pos2.distance_to(pos1)

        assert abs(d1 - d2) < 0.0001

    @given(
        pos=st.builds(Position),
        delta_lat=st.floats(min_value=-1, max_value=1),
        delta_lon=st.floats(min_value=-1, max_value=1),
    )
    @settings(max_examples=500)
    def test_small_movements_result_in_small_distances(
        self,
        pos: Position,
        delta_lat: float,
        delta_lon: float,
    ) -> None:
        """Small coordinate changes result in small distances."""
        # Only test with valid resulting positions
        new_lat = float(pos.latitude) + delta_lat
        new_lon = float(pos.longitude) + delta_lon

        assume(-90 <= new_lat <= 90)
        assume(-180 <= new_lon <= 180)

        new_pos = pos.with_offset(delta_lat, delta_lon)
        distance = pos.distance_to(new_pos)

        # Distance should be bounded (rough upper bound for small changes)
        assert distance < 200000  # 200km max for 1 degree change


class GeofenceStateMachine(RuleBasedStateMachine):
    """Stateful property-based test for geofence consistency."""

    def __init__(self) -> None:
        super().__init__()
        self.validator = GeofenceValidator.create_test_instance()
        self.positions: list[Position] = []
        self.violations: list[Position] = []

    @rule(
        lat=st.decimals(min_value=-90, max_value=90),
        lon=st.decimals(min_value=-180, max_value=180),
        alt=st.floats(min_value=0, max_value=500),
    )
    def add_position(self, lat: float, lon: float, alt: float) -> None:
        """Add a position and track validation."""
        pos = Position(lat, lon, alt)
        self.positions.append(pos)

        try:
            self.validator.validate(pos)
        except GeofenceViolation:
            self.violations.append(pos)

    @rule()
    def check_violations_consistent(self) -> None:
        """Check that violations remain consistent on re-validation."""
        for pos in self.violations:
            with pytest.raises(GeofenceViolation):
                self.validator.validate(pos)

    @precondition(lambda self: len(self.positions) > 0)
    @rule()
    def check_valid_positions_stay_valid(self) -> None:
        """Valid positions should remain valid."""
        valid_positions = [p for p in self.positions if p not in self.violations]

        for pos in valid_positions:
            result = self.validator.validate(pos)
            assert result.is_valid


TestGeofenceStateful = GeofenceStateMachine.TestCase


# Safety-critical invariant: battery never increases without charging
class BatteryInvariantTests(RuleBasedStateMachine):
    """Stateful test for battery level monotonicity."""

    def __init__(self) -> None:
        super().__init__()
        self.battery = 100.0
        self.charging = False
        self.history: list[float] = [self.battery]

    @rule(consumption=st.floats(min_value=0.1, max_value=5.0))
    def discharge(self, consumption: float) -> None:
        """Simulate battery discharge."""
        assume(not self.charging)
        assume(self.battery > 0)

        self.battery = max(0.0, self.battery - consumption)
        self.history.append(self.battery)

        # INVARIANT: Battery never increases when discharging
        assert self.battery <= self.history[-2]

    @rule()
    def start_charging(self) -> None:
        """Start charging the battery."""
        self.charging = True

    @rule(charge=st.floats(min_value=0.1, max_value=5.0))
    def charge(self, charge: float) -> None:
        """Charge the battery."""
        assume(self.charging)
        self.battery = min(100.0, self.battery + charge)
        self.history.append(self.battery)

    @rule()
    def stop_charging(self) -> None:
        """Stop charging."""
        self.charging = False


TestBatteryMonotonicity = BatteryInvariantTests.TestCase
```

---

## 5. Documentation Standards

### 5.1 Architecture Decision Records (ADR)

#### ADR Template

```markdown
# ADR-XXX: [Title]

## Status
- Proposed / Accepted / Deprecated / Superseded by ADR-YYY

## Context
[Description of the problem or requirement that prompted this decision.]

## Decision
[The decision that was made. Be explicit and specific.]

## Consequences

### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Trade-off 1]
- [Trade-off 2]

### Safety Impact
- [Impact on safety-critical operations]
- [Risk assessment]

## Alternatives Considered

### Alternative 1: [Name]
- **Pros**: ...
- **Cons**: ...
- **Why rejected**: ...

## Related Decisions
- [Links to related ADRs]

## References
- [Links to relevant standards, papers, etc.]
```

#### Example ADR

```markdown
# ADR-001: Use of Python 3.11+ for Type Safety

## Status
Accepted

## Context
The drone control software requires strong type safety guarantees to prevent
runtime errors in safety-critical flight operations. We needed to select a
Python version and type checking strategy.

## Decision
We will use Python 3.11+ with mypy in strict mode for all production code.

Key points:
- Type hints are mandatory for all function signatures
- mypy --strict is run in CI on every commit
- Runtime type checking with Pydantic for external inputs
- Union operator syntax (|) preferred over Union[]

## Consequences

### Positive
- Compile-time detection of type errors
- Better IDE support and autocomplete
- Self-documenting function signatures
- Refactoring confidence with type checker

### Negative
- Slightly slower development velocity
- Team training required on type system
- Some third-party libraries lack type stubs

### Safety Impact
- **Risk reduction**: Type errors caught before runtime prevent potential
  flight control faults
- **Audit trail**: Type signatures serve as documentation for safety reviews
- **Testing**: Reduces need for type-related defensive tests

## Alternatives Considered

### Alternative: Python 3.10 with limited typing
- **Pros**: Broader library compatibility
- **Cons**: Missing modern typing features (Union syntax, better generics)
- **Why rejected**: Safety benefits of 3.11+ outweigh compatibility concerns

### Alternative: Rust for safety-critical components
- **Pros**: Memory safety, compile-time guarantees
- **Cons**: Team expertise, ecosystem, development velocity
- **Why rejected**: Phase 2 consideration; Python with strict typing
  sufficient for current requirements

## Related Decisions
- ADR-002: Pydantic for Data Validation
- ADR-003: AsyncIO for Concurrency

## References
- PEP 484: Type Hints
- PEP 604: Union Types with X | Y syntax
- DO-178C Software Considerations in Airborne Systems
```

### 5.2 API Documentation

#### OpenAPI/Swagger Integration

```python
"""API documentation using OpenAPI/Swagger."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Drone Control API",
    description="Safety-critical API for drone flight operations",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


class MissionUploadRequest(BaseModel):
    """Request model for mission upload."""

    name: str = Field(
        ...,
        description="Unique mission name",
        min_length=1,
        max_length=100,
        example="survey_site_alpha",
    )
    waypoints: list[Waypoint] = Field(
        ...,
        description="Ordered list of mission waypoints",
        min_items=2,
        max_items=1000,
    )
    safety_parameters: SafetyParameters = Field(
        ...,
        description="Mission-specific safety configuration",
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "site_survey_v1",
                "waypoints": [
                    {"lat": 37.7749, "lon": -122.4194, "alt": 50},
                    {"lat": 37.7750, "lon": -122.4195, "alt": 50},
                ],
                "safety_parameters": {
                    "max_altitude_msl": 120,
                    "geofence_id": "site_alpha",
                },
            }
        }


@app.post(
    "/missions",
    response_model=MissionCreatedResponse,
    status_code=201,
    responses={
        400: {"model": ValidationErrorResponse, "description": "Invalid mission data"},
        409: {"model": ConflictErrorResponse, "description": "Mission name already exists"},
        422: {"model": SafetyErrorResponse, "description": "Safety validation failed"},
    },
    summary="Upload new mission",
    description="""
    Upload a new flight mission for validation and storage.

    The mission undergoes the following validation:
    - Geofence compatibility check
    - Waypoint accessibility verification
    - Battery endurance calculation
    - No-fly zone intersection detection

    **Safety-critical**: This endpoint performs full safety validation.
    Missions that fail safety checks return 422 and are not stored.
    """,
    tags=["missions"],
)
async def upload_mission(
    request: MissionUploadRequest,
    current_user: User = Depends(get_current_user),
) -> MissionCreatedResponse:
    """Upload and validate new flight mission."""
    ...
```

### 5.3 Safety Rationale Comments

#### Safety Comment Format

```python
# SAFETY: [Safety level] - [One-line rationale]
# [Detailed explanation if needed]
# VERIFIED: [How this is tested/verified]
# RISK: [What could go wrong if violated]
# REF: [Reference to standard/requirement]

# Example:
# SAFETY: CRITICAL - Prevent uncontrolled descent
# The failsafe timeout must be shorter than the minimum time
# to ground from maximum altitude at maximum descent rate.
# VERIFIED: Unit test test_failsafe_timeout_sufficient()
# RISK: Late failsafe activation leads to crash
# REF: ASTM F3322-22, Section 4.3
FAILSAFE_TIMEOUT_SEC = 2.0
```

#### Safety-Critical Code Documentation

```python
class EmergencyLandingController:
    """Controller for emergency landing procedures.

    Implements failsafe landing when primary flight control
    is compromised or safety violations are detected.

    Safety Classification: CRITICAL
    Failure Mode: Uncontrolled descent
    Mitigation: Redundant sensors, conservative control limits
    """

    # SAFETY: CRITICAL - Prevent landing site overrun
    # Minimum descent rate ensures landing site is reachable
    # but prevents excessive ground speed.
    # CALCULATED: Based on 30m landing zone, 5m/s max ground speed
    # VERIFIED: Hardware-in-loop simulation scenarios 1.1-1.5
    MAX_DESCENT_RATE_MPS = 3.0

    # SAFETY: HIGH - Prevent ground collision
    # Altitude threshold for final approach phase.
    # Below this altitude, forward speed is reduced to minimum.
    # VERIFIED: Flight test log #2024-03-15
    FINAL_APPROACH_ALTITUDE_M = 10.0

    async def execute_emergency_landing(
        self,
        trigger: EmergencyTrigger,
        landing_zone: Optional[LandingZone] = None,
    ) -> LandingResult:
        """Execute emergency landing procedure.

        This is a safety-critical operation that cannot be aborted
        once initiated without operator override at control station.

        SAFETY PROTOCOLS:
        1. Immediate motor power reduction to idle
        2. Maximum descent rate limiting (see MAX_DESCENT_RATE_MPS)
        3. Landing zone approach at minimum safe airspeed
        4. Flare maneuver at FINAL_APPROACH_ALTITUDE_M
        5. Motor cutoff at ground contact detection

        VERIFICATION:
        - Unit tests: test_emergency_landing_*.py
        - HIL simulation: scenarios 2.1-2.8
        - Flight test: Log #2024-03-15 through #2024-03-22

        FAILURE MODES:
        - Sensor failure: Use redundant IMU, GPS
        - Landing zone occupied: Execute go-around to alternate
        - Ground contact failure: Timeout-based motor cutoff

        Args:
            trigger: Emergency condition that activated landing
            landing_zone: Optional pre-selected landing zone.
                          If None, selects nearest safe zone.

        Returns:
            LandingResult with touchdown data and outcome.

        Raises:
            EmergencyLandingError: If landing cannot be completed safely.
                                   Caller must attempt alternate procedure.

        Safety Reference: ASTM F3322-22, Section 5.2
        """
        # SAFETY: Log all emergency landings for post-flight analysis
        await self._log_emergency_start(trigger)

        try:
            # SAFETY: CRITICAL - Must have valid landing zone
            # Flying without valid landing zone violates operational envelope
            zone = landing_zone or await self._select_landing_zone()
            if not zone or not zone.is_valid:
                raise EmergencyLandingError("No valid landing zone available")

            # SAFETY: Descent rate limiting prevents structural damage
            # and maintains control authority
            await self._execute_controlled_descent(
                target=zone,
                max_descent_rate=self.MAX_DESCENT_RATE_MPS,
            )

            return await self._complete_landing(zone)

        except Exception as e:
            # SAFETY: Any failure during emergency landing is logged
            # at CRITICAL level for immediate investigation
            logger.critical(f"Emergency landing failure: {e}")
            await self._activate_ultimate_failsafe()
            raise
```

---

## 6. Appendix: Configuration Files

### pyproject.toml

Complete configuration file is located at `/Users/muadhsambul/Downloads/Project-Avatar/pyproject.toml`

Key sections:
- `[build-system]`: Build requirements
- `[project]`: Package metadata and dependencies
- `[tool.mypy]`: Strict type checking configuration
- `[tool.pylint.*]`: Safety-focused linting rules
- `[tool.bandit]`: Security scanning configuration
- `[tool.pytest.ini_options]`: Test framework settings
- `[tool.coverage.*]`: Coverage thresholds and reporting
- `[tool.isort]`: Import organization
- `[tool.black]`: Code formatting
- `[tool.ruff]`: Fast Python linter
- `[tool.hypothesis]`: Property-based testing settings

### .pre-commit-config.yaml

Complete configuration file is located at `/Users/muadhsambul/Downloads/Project-Avatar/.pre-commit-config.yaml`

Includes hooks for:
- File validation (trailing whitespace, JSON/YAML/TOML syntax)
- Security checks (private keys, large files)
- Python formatting (Black)
- Import sorting (isort)
- Type checking (mypy)
- Linting (pylint)
- Security scanning (bandit)
- Testing (pytest with coverage)

### .bandit.yaml

Complete configuration file is located at `/Users/muadhsambul/Downloads/Project-Avatar/.bandit.yaml`

Configures security tests for:
- Injection vulnerabilities (B301-B324)
- Cryptographic issues (B401-B413)
- Runtime execution (B102, B104-B107)
- Information leakage (B501-B507)
- Input validation (B103, B108)

### mypy.ini (Alternative)

For projects not using pyproject.toml:

```ini
# mypy.ini - Safety-Critical Python Type Checking
# Compliance: DO-178C Level B, ISO/IEC 61508 SIL-2

[mypy]
# Strictness
strict = True
implicit_reexport = False
warn_return_any = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True

# Disallow dynamic behavior
disallow_untyped_defs = True
disallow_incomplete_defs = True
disallow_untyped_decorators = True
disallow_subclassing_any = True
disallow_any_generics = True
disallow_any_explicit = False
disallow_any_decorated = False

# None handling
strict_optional = True
implicit_optional = False

# Error reporting
show_error_codes = True
show_column_numbers = True
show_error_context = True
pretty = True

# Import handling
ignore_missing_imports = False
follow_imports = normal
no_implicit_optional = True

# Performance and safety
strict_equality = True
extra_checks = True
warn_unused_configs = True

# Python version
python_version = 3.11

# Cache
cache_dir = .mypy_cache

[mypy.plugins.numpy]
init_return = True

[mypy-result.*]
ignore_missing_imports = True

[mypy-numpy.*]
ignore_missing_imports = True
```

### pytest.ini (Alternative)

For projects not using pyproject.toml:

```ini
[pytest]
minversion = 7.0
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --strict-config
    --tb=short
    --capture=no
    -v
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    e2e: marks tests as end-to-end tests
    property: marks tests as property-based tests
    safety_critical: marks safety-critical tests
    hardware_in_loop: marks tests requiring hardware
asyncio_mode = auto
timeout = 300
filterwarnings =
    error::DeprecationWarning
    error::PendingDeprecationWarning
    ignore::pytest.PytestUnraisableExceptionWarning
```

### conftest.py (Global pytest fixtures)

```python
"""Global pytest configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator

from drone.config import TestConfig
from drone.models.position import Position


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_position() -> Position:
    """Create a valid test position."""
    return Position(
        latitude=37.7749,
        longitude=-122.4194,
        altitude_msl=50.0,
    )


@pytest.fixture
def safety_config():
    """Create safety configuration for tests."""
    return TestConfig(
        max_altitude=120.0,
        geofence_radius=1000.0,
        battery_threshold=20.0,
    )


@pytest.fixture
async def flight_controller(safety_config) -> AsyncGenerator:
    """Create flight controller fixture with automatic cleanup."""
    from drone.flight_controller import FlightController

    controller = FlightController(config=safety_config)
    await controller.initialize()
    yield controller
    await controller.shutdown()


def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "safety_critical: marks safety-critical tests")
```

---

## Checklists

### Pre-Commit Checklist

- [ ] mypy passes with `--strict`
- [ ] pylint score >= 9.0/10
- [ ] bandit shows no high/critical issues
- [ ] All tests pass (unit, integration)
- [ ] Coverage >= 90% for modified safety-critical code
- [ ] Docstrings follow Google style
- [ ] Type hints complete for all public APIs
- [ ] Safety rationale comments added for critical changes

### Safety Review Checklist

- [ ] All safety-critical paths have timeout handling
- [ ] Resource cleanup implemented (context managers)
- [ ] Input validation at all entry points
- [ ] Exception hierarchy appropriate for error type
- [ ] Logging at appropriate levels for all error paths
- [ ] Property-based tests for invariants
- [ ] ADR created for architectural changes
- [ ] Hardware-in-loop testing completed

---

## References

### Standards
- DO-178C: Software Considerations in Airborne Systems
- ASTM F3322-22: Standard Practice for Unmanned Aircraft Systems
- ISO 21384-3:2023: UAS Operational Procedures
- RTCA DO-331: Model-Based Development

### Python Guidelines
- PEP 8: Style Guide for Python Code
- PEP 257: Docstring Conventions
- PEP 484: Type Hints
- PEP 285: Abstract Base Classes

### Tools
- mypy: Static Type Checking
- pylint: Python Code Analysis
- bandit: Security Linter
- hypothesis: Property-Based Testing
- pytest: Testing Framework

---

*Document Version: 1.1.0*  
*Last Updated: 2024*  
*Owner: Drone Software Safety Team*
