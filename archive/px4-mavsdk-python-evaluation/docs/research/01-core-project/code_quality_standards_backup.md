# Python Code Quality Standards for Safety-Critical Drone Software

**Version:** 1.0  
**Classification:** Safety-Critical (SIL-2 equivalent)  
**Applicable Standards:** DO-178C, ISO/IEC 61508, ASTM F3269  

---

## Table of Contents

1. [Python Coding Standards](#1-python-coding-standards)
2. [Static Analysis Configuration](#2-static-analysis-configuration)
3. [Runtime Safety Patterns](#3-runtime-safety-patterns)
4. [Documentation Requirements](#4-documentation-requirements)
5. [Configuration Files](#5-configuration-files)

---

## 1. Python Coding Standards

### 1.1 Type Hints Throughout (mypy strict)

All code must use complete type annotations. No exceptions for safety-critical components.

```python
from typing import Optional, Union, Final, Literal, Protocol

# CORRECT: Complete type annotations
class FlightController:
    def __init__(self, drone_id: str, max_altitude: float) -> None:
        self._drone_id: Final[str] = drone_id
        self._max_altitude: Final[float] = max_altitude
        self._current_altitude: float = 0.0
        self._armed: bool = False

    def set_altitude(self, target: float) -> Result[None, AltitudeError]:
        """Set target altitude with validation."""
        if not self._armed:
            return Err(AltitudeError("Cannot set altitude: drone not armed"))
        if target > self._max_altitude:
            return Err(AltitudeError(f"Altitude {target} exceeds maximum {self._max_altitude}"))
        self._current_altitude = target
        return Ok(None)

# INCORRECT: Missing or incomplete type hints
class BadController:
    def __init__(self, drone_id, max_altitude):  # Missing types
        self.drone_id = drone_id  # No Final for immutable
        self.max = max_altitude  # Ambiguous name

    def set_altitude(self, target):  # Missing return type
        self.current = target  # Implicit attribute creation
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

#### Generic Patterns for Drone Systems

```python
from typing import TypeVar, Generic, NewType
from dataclasses import dataclass
from result import Result, Ok, Err

# NewTypes for domain-specific primitives
DroneId = NewType("DroneId", str)
AltitudeMeters = NewType("AltitudeMeters", float)
VelocityMPS = NewType("VelocityMPS", float)
TimestampNS = NewType("TimestampNS", int)

T = TypeVar("T")
E = TypeVar("E", bound=Exception)

@dataclass(frozen=True)
class TelemetryDatum(Generic[T]):
    """Immutable telemetry data point."""
    timestamp: TimestampNS
    value: T
    quality: Literal["VALID", "SUSPECT", "INVALID"]

# Usage
altitude_reading: TelemetryDatum[AltitudeMeters] = TelemetryDatum(
    timestamp=TimestampNS(1234567890),
    value=AltitudeMeters(100.5),
    quality="VALID"
)
```

### 1.2 Docstring Format (Google Style)

All public modules, classes, methods, and functions must have Google-style docstrings.

```python
def calculate_landing_trajectory(
    current_position: Position3D,
    landing_zone: Position3D,
    current_velocity: Velocity3D,
    max_deceleration: float,
    safety_margin: float = 1.5
) -> Result[Trajectory, PlanningError]:
    """Calculate a safe landing trajectory.

    Computes the optimal descent path from current position to landing
    zone while respecting deceleration limits and maintaining safety
    margins per ASTM F3269-21.

    Args:
        current_position: Current 3D position in meters (NED frame).
        landing_zone: Target landing position in meters (NED frame).
        current_velocity: Current velocity vector in m/s.
        max_deceleration: Maximum allowed deceleration in m/s^2.
        safety_margin: Multiplier for safety buffer (default: 1.5).

    Returns:
        Result containing either:
            - Ok: Computed Trajectory with waypoints and timestamps
            - Err: PlanningError describing why trajectory is impossible

    Raises:
        ValueError: If safety_margin is less than 1.0 or max_deceleration <= 0.

    Safety Notes:
        - Trajectory is validated against geofence before return
        - Minimum altitude check enforced at each waypoint
        - Emergency abort waypoint always included

    Example:
        >>> pos = Position3D(x=100.0, y=200.0, z=50.0)
        >>> lz = Position3D(x=0.0, y=0.0, z=0.0)
        >>> vel = Velocity3D(vx=5.0, vy=5.0, vz=-1.0)
        >>> result = calculate_landing_trajectory(pos, lz, vel, 2.0)
        >>> if result.is_ok():
        ...     trajectory = result.unwrap()
    """
```

#### Docstring Template

```python
"""One-line summary.

Extended description explaining what/why. Include references to
standards (DO-178C, ASTM, etc.) where applicable.

Args:
    param1: Description (units if applicable).
    param2: Description including valid ranges.

Returns:
    Description of return value including error conditions.

Raises:
    ExceptionType: When this exception is raised and why.

Safety Notes:
    - Critical safety consideration 1
    - Critical safety consideration 2

Example:
    >>> example_code_here()
"""
```

### 1.3 Import Organization

Imports must be grouped and ordered following PEP 8 with safety-critical additions.

```python
"""Module docstring here."""

# Group 1: Future imports (if needed)
from __future__ import annotations

# Group 2: Standard library (alphabetical)
import logging
import struct
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Literal, Optional, Protocol

# Group 3: Third-party packages (alphabetical)
import numpy as np
from result import Err, Ok, Result

# Group 4: Internal modules (most specific last)
from drone_safety.core.types import AltitudeMeters, DroneId
from drone_safety.flight.state import FlightState
from drone_safety.hardware.motor_controller import MotorController

# Group 5: Relative imports (avoid in safety-critical; use absolute)
# from .utils import helper  # AVOID
```

#### Import Rules

| Rule | Rationale |
|------|-----------|
| No `import *` | Explicit dependencies only |
| No circular imports | System must be analyzable |
| Prefer absolute imports | Clear dependency graph |
| Group by safety level | Standard < Third-party < Internal |
| Use `typing.TYPE_CHECKING` | Break circular type dependencies |

### 1.4 Naming Conventions

| Element | Convention | Example | Rationale |
|---------|------------|---------|-----------|
| Modules | `snake_case` | `flight_controller.py` | PEP 8 |
| Packages | `snake_case` | `drone_safety` | PEP 8 |
| Classes | `PascalCase` | `FlightController` | PEP 8 |
| Exceptions | `PascalCase` + `Error` | `AltitudeError` | Clarity |
| Functions | `snake_case` | `set_altitude()` | PEP 8 |
| Constants | `SCREAMING_SNAKE` | `MAX_ALTITUDE_M` | Clarity |
| Private | `_leading_underscore` | `_internal_state` | Encapsulation |
| Protected | `_single_underscore` | `_validate()` | Inheritance hint |
| Type variables | `PascalCase` or `T`, `K`, `V` | `T`, `DroneT` | Convention |
| Protocols | `PascalCase` + `able` or `Protocol` | `Flyable`, `Controllable` | Semantics |
| NewTypes | `PascalCase` descriptive | `AltitudeMeters` | Units in name |
| Enums | `PascalCase` class, members | `State.ARMED` | Clarity |

#### Safety-Critical Naming Additions

```python
# Units must be in name when not obvious
MAX_ALTITUDE_M: Final[float] = 120.0  # meters
TIMEOUT_MS: Final[int] = 5000  # milliseconds
BATTERY_CAPACITY_MAH: Final[int] = 5000  # milliamp-hours

# Boolean predicates must be clear
is_armed: bool  # State check
has_valid_gps: bool  # Capability check
should_abort: bool  # Decision flag
_can_fly: bool  # Private capability (computed)

# Result types must be explicit
current_altitude_result: Result[AltitudeMeters, SensorError]
```

---

## 2. Static Analysis Configuration

### 2.1 mypy.ini - Strict Mode

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
disallow_any_explicit = False  # Allow explicit Any with justification
disallow_any_decorated = False  # Allow decorated functions

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

### 2.2 pyproject.toml - Pylint Safety-Focused

```toml
[tool.pylint.main]
# Safety-critical: fail on any issue
fail-on = "I"
fail-under = 10.0

# Jobs
jobs = 0

# Files to check
recursive = true
ignore-patterns = ["^\\."]

[tool.pylint.messages_control]
# Disable non-critical warnings
disable = [
    "C0103",  # naming-convention (covered by black/mypy)
    "C0114",  # missing-module-docstring (redundant with pydocstyle)
    "C0115",  # missing-class-docstring
    "C0116",  # missing-function-docstring
    "R0903",  # too-few-public-methods (dataclasses/protocols)
    "R0913",  # too-many-arguments (safety APIs need parameters)
    "W0212",  # protected-access (internal modules)
]

# Enable all safety checks
enable = [
    "E",  # Errors
    "W",  # Warnings
    "F",  # Fatal
    "I",  # Informational
    "R",  # Refactoring
    "C",  # Convention
]

[tool.pylint.basic]
# Naming conventions (enforced separately, but validated here)
argument-naming-style = "snake_case"
attr-naming-style = "snake_case"
class-naming-style = "PascalCase"
const-naming-style = "UPPER_CASE"
function-naming-style = "snake_case"
method-naming-style = "snake_case"
module-naming-style = "snake_case"
variable-naming-style = "snake_case"

# Good names that override patterns
good-names = [
    "i", "j", "k", "ex", "Run", "T", "E", "K", "V",
    "ok", "err", "rx", "tx", "id", "x", "y", "z",
    "dt", "dx", "dy", "dz", "vx", "vy", "vz"
]

[tool.pylint.format]
max-line-length = 88  # Match black
max-module-lines = 1000

[tool.pylint.exceptions]
# Overridden methods check arguments
overridden-method-check-arg = true

[tool.pylint.classes]
defining-attr-methods = ["__init__", "__new__", "setUp", "asyncSetUp"]

[tool.pylint.design]
# Limit complexity for safety verification
max-args = 8
max-attributes = 15
max-bool-expr = 5
max-branches = 15
max-locals = 20
max-parents = 7
max-public-methods = 25
max-returns = 10
max-statements = 60
min-public-methods = 0

[tool.pylint.similarities]
# Code duplication detection
min-similarity-lines = 4
ignore-comments = true
ignore-docstrings = true
ignore-imports = true
ignore-signatures = true

[tool.pylint.variables]
# Strict variable checking
dummy-variables-rgx = "_$|dummy|unused"
init-import = false
redefining-builtins-modules = ["six", "future", "builtins"]

[tool.pylint.logging]
# Logging format validation
logging-format-style = "new"
logging-modules = ["logging"]

[tool.pylint.miscellaneous]
# Note format for code notes
notes = ["FIXME", "TODO", "SAFETY", "XXX", "HACK"]
notes-rgx = "(?i)\\s*(#\\s*)?(FIXME|TODO|SAFETY|XXX|HACK)(\\s*[:]\\s*|$)"

[tool.pylint.typecheck]
# Runtime type checking
generated-members = ["numpy.*", "torch.*"]
ignore-mixin-members = true
ignore-none = true
ignore-on-opaque-inference = true
ignored-checks-for-mixins = ["no-member"]
ignored-classes = ["optparse.Values", "thread._local", "threading.local"]
```

### 2.3 Bandit Security Scanner

```yaml
# bandit.yaml - Security scanning for drone software
# Targets: Command injection, deserialization, crypto, subprocess

skips:
  # Only skip checks with documented justification
  # B101:assert_used - We use asserts only for internal invariants
  # All others must be addressed, not skipped

assert_used:
  skips: []  # We use asserts appropriately; bandit warns by default

test_patterns:
  include:
    - "**/*.py"
  exclude:
    - "**/test_*.py"
    - "**/tests/**/*.py"
    - "**/_version.py"
    - "**/conftest.py"

severity_filter: LOW  # Report everything
confidence_filter: LOW  # Report everything

# Severity overrides for drone-specific concerns
severity_overrides:
  B102: HIGH  # exec_used - Critical for flight safety
  B105: HIGH  # hardcoded_password_string
  B307: HIGH  # eval - Never acceptable
  B602: HIGH  # subprocess_popen_with_shell
  B603: HIGH  # subprocess_without_shell_equals_true
  B604: HIGH  # any_other_function_with_shell_equals_true
  B605: HIGH  # start_process_with_a_shell
  B606: HIGH  # start_process_with_no_shell
  B607: HIGH  # start_process_with_partial_path

profiles:
  - all

# Exclude paths from scanning
exclude_dirs:
  - ".git"
  - ".venv"
  - "venv"
  - "__pycache__"
  - ".pytest_cache"
  - ".mypy_cache"
  - "build"
  - "dist"
  - ".tox"
  - "node_modules"

# HTML output for CI integration
format: screen  # Use 'html' for CI reports
output_file: bandit-report.txt

# Number of processes
parallel: 4

# Show line numbers
show_lineno: true

# Progress
quiet: false
```

### 2.4 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
# Safety-critical drone software hooks
# Version: 1.0

repos:
  # Basic file checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
        exclude: ".md$"
      - id: end-of-file-fixer
      - id: check-added-large-files
        args: ["--maxkb=1000"]
      - id: check-case-conflict
      - id: check-executables-have-shebangs
      - id: check-json
      - id: check-merge-conflict
      - id: check-symlinks
      - id: check-toml
      - id: check-xml
      - id: check-yaml
      - id: detect-private-key
      - id: mixed-line-ending
        args: ["--fix=lf"]
      - id: forbid-new-submodules

  # Python code formatting
  - repo: https://github.com/psf/black
    rev: 24.2.0
    hooks:
      - id: black
        language_version: python3.11
        args: ["--line-length=88", "--target-version=py311"]

  # Import sorting
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile=black", "--line-length=88"]

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-python-dateutil
          - pydantic>=2.0
          - result>=0.14.0
        args: ["--config-file=mypy.ini"]

  # Linting
  - repo: https://github.com/pycqa/pylint
    rev: v3.0.3
    hooks:
      - id: pylint
        args: ["--rcfile=pyproject.toml"]
        additional_dependencies:
          - result>=0.14.0
          - pydantic>=2.0

  # Security scanning
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.7
    hooks:
      - id: bandit
        args: ["-c", "bandit.yaml"]

  # Docstring conventions
  - repo: https://github.com/pycqa/pydocstyle
    rev: 6.3.0
    hooks:
      - id: pydocstyle
        args: ["--convention=google"]

  # Additional safety checks
  - repo: https://github.com/pre-commit/pygrep-hooks
    rev: v1.10.0
    hooks:
      - id: python-no-eval
      - id: python-no-log-warn
      - id: python-use-type-annotations
      - id: rst-backticks
      - id: rst-directive-colons
      - id: rst-inline-touching-normal

  # Custom safety hooks
  - repo: local
    hooks:
      - id: no-assert-in-production
        name: Check for assert in non-test files
        entry: bash -c 'grep -rn "assert " --include="*.py" src/ || exit 0'
        language: system
        types: [python]
        pass_filenames: false

      - id: check-safety-comments
        name: Verify SAFETY comments present
        entry: bash -c '
          for file in $(find src -name "*.py" -type f); do
            if grep -q "def.*flight\|def.*control\|def.*arm\|def.*motor" "$file" 2>/dev/null; then
              if ! grep -q "Safety Notes:" "$file"; then
                echo "ERROR: $file missing Safety Notes section"
                exit 1
              fi
            fi
          done
        '
        language: system
        pass_filenames: false
        always_run: true

  # Spell checking (for comments and docs)
  - repo: https://github.com/codespell-project/codespell
    rev: v2.2.6
    hooks:
      - id: codespell
        args: ["--ignore-words=.codespell-ignore"]
```

---

## 3. Runtime Safety Patterns

### 3.1 Assert vs Exception Usage

| Use Case | Mechanism | Example |
|----------|-----------|---------|
| Internal invariants (developer errors) | `assert` | `assert pointer is not None` |
| External input validation | Exception | `raise ValueError("Invalid altitude")` |
| Preconditions | Exception | `raise StateError("Drone not armed")` |
| Postconditions | `assert` (debug) / Exception (release) | `assert result > 0` |
| Safety-critical checks | Always Exception | `raise SafetyError("Geofence breached")` |

```python
from typing import Final

# Assert usage - internal invariants only
def _process_sensor_data(raw: bytes) -> SensorReading:
    """Internal processing with invariant checks."""
    # Invariant: raw data must be 16 bytes per spec
    assert len(raw) == 16, f"Expected 16 bytes, got {len(raw)}"

    # Processing...
    return SensorReading(...)

# Exception usage - all external boundaries
class FlightController:
    def set_altitude(self, target: float) -> None:
        """Set target altitude with full validation."""
        # Precondition check - always exception
        if target < 0:
            raise ValueError(f"Altitude must be non-negative, got {target}")

        if target > self._max_altitude:
            raise SafetyError(
                f"Altitude {target}m exceeds maximum {self._max_altitude}m. "
                "Geofence enforcement triggered."
            )

        # State validation - always exception
        if not self._armed:
            raise StateError("Cannot set altitude: drone not armed")

        # Apply with postcondition check
        self._altitude_target = target

        # Debug-only invariant check
        assert self._altitude_target >= 0, "Altitude became negative"
```

#### Assert Policy for Drone Software

```python
# pytest.ini configuration
# [pytest]
# filterwarnings =
#     error::AssertionError
#     ignore::DeprecationWarning

# Runtime configuration
import sys

if sys.flags.optimize >= 1:
    # Running with -O, asserts are stripped
    # All safety checks must use explicit exceptions
    SAFETY_RUNTIME_MODE = "PRODUCTION"
else:
    SAFETY_RUNTIME_MODE = "DEBUG"
    # Asserts available for internal invariants
```

### 3.2 Input Validation Layers

```python
from dataclasses import dataclass
from functools import wraps
from typing import Callable, TypeVar, ParamSpec
import re

P = ParamSpec("P")
T = TypeVar("T")

class ValidationError(ValueError):
    """Input validation failure."""
    pass

class Range:
    """Range validator for numeric inputs."""

    def __init__(self, min_val: float, max_val: float, inclusive: bool = True):
        self.min = min_val
        self.max = max_val
        self.inclusive = inclusive

    def __call__(self, value: float) -> float:
        op = (lambda x, y: x >= y) if self.inclusive else (lambda x, y: x > y)

        if not op(value, self.min):
            raise ValidationError(
                f"Value {value} below {'inclusive' if self.inclusive else 'exclusive'} "
                f"minimum {self.min}"
            )
        if not op(self.max, value):
            raise ValidationError(
                f"Value {value} above {'inclusive' if self.inclusive else 'exclusive'} "
                f"maximum {self.max}"
            )
        return value

class Pattern:
    """Regex pattern validator."""

    def __init__(self, pattern: str, description: str):
        self._pattern = re.compile(pattern)
        self._description = description

    def __call__(self, value: str) -> str:
        if not self._pattern.match(value):
            raise ValidationError(
                f"Value '{value}' does not match pattern {self._description}"
            )
        return value

# Predefined validators for drone domain
altitude_range = Range(0.0, 120.0)  # meters, per regulations
velocity_range = Range(-50.0, 50.0)  # m/s
battery_range = Range(0.0, 100.0)  # percent
drone_id_pattern = Pattern(r"^[A-Z]{2}-\d{4}-[A-F0-9]{8}$", "XX-XXXX-XXXXXXXX")

# Validation decorator
def validate(**validators: Callable[[any], any]) -> Callable:
    """Decorator for input validation."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Bind arguments to validate
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    try:
                        bound.arguments[param_name] = validator(
                            bound.arguments[param_name]
                        )
                    except ValidationError as e:
                        raise ValidationError(
                            f"Parameter '{param_name}' validation failed: {e}"
                        ) from e

            return func(*bound.args, **bound.kwargs)
        return wrapper
    return decorator

# Usage example
class MotorController:
    """Motor controller with validated inputs."""

    @validate(
        speed=Range(-1000.0, 1000.0),
        motor_id=Pattern(r"^M[1-4]$", "M1-M4")
    )
    def set_motor_speed(self, motor_id: str, speed: float) -> None:
        """Set motor speed with validation.

        Args:
            motor_id: Motor identifier (M1-M4).
            speed: Target speed in RPM (-1000 to 1000).

        Safety Notes:
            - Speed changes are rate-limited internally
            - Emergency stop overrides all speed commands
            - Validation occurs before hardware access
        """
        # Implementation - inputs guaranteed valid
        self._hardware.set_pwm(motor_id, self._rpm_to_pwm(speed))
```

### 3.3 Timeout Decorators

```python
import signal
import functools
from typing import TypeVar, Callable, Optional
from concurrent.futures import TimeoutError as FutureTimeoutError
import threading

T = TypeVar("T")

class TimeoutError(Exception):
    """Operation exceeded time limit."""
    pass

class SafetyTimeout:
    """Timeout decorator for safety-critical operations.

    Provides both signal-based (Unix) and threading-based timeouts.
    Signal-based preferred for main thread; threading for subthreads.
    """

    def __init__(
        self,
        seconds: float,
        use_signals: bool = True,
        exception: type[Exception] = TimeoutError
    ):
        self.seconds = seconds
        self.use_signals = use_signals and threading.current_thread() is threading.main_thread()
        self.exception = exception

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if self.use_signals:
                return self._with_signals(func, *args, **kwargs)
            else:
                return self._with_threading(func, *args, **kwargs)
        return wrapper

    def _with_signals(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Unix signal-based timeout."""
        def handler(signum, frame):
            raise self.exception(
                f"Operation {func.__name__} timed out after {self.seconds}s"
            )

        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(int(self.seconds))
        try:
            return func(*args, **kwargs)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def _with_threading(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Threading-based timeout for non-main threads."""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=self.seconds)
            except FutureTimeoutError:
                raise self.exception(
                    f"Operation {func.__name__} timed out after {self.seconds}s"
                )

# Context manager variant
class TimeoutContext:
    """Context manager for timeout control."""

    def __init__(self, seconds: float, exception: type[Exception] = TimeoutError):
        self.seconds = seconds
        self.exception = exception
        self._old_handler: Optional[Callable] = None

    def __enter__(self):
        if threading.current_thread() is threading.main_thread():
            self._old_handler = signal.signal(
                signal.SIGALRM,
                lambda s, f: self._raise_timeout()
            )
            signal.alarm(int(self.seconds))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._old_handler is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self._old_handler)
        return False

    def _raise_timeout(self):
        raise self.exception(f"Timeout after {self.seconds}s")

# Usage in drone software
class GPSReceiver:
    """GPS receiver with timeout handling."""

    SAFETY_TIMEOUT_S: float = 2.0  # Max time to wait for GPS fix

    @SafetyTimeout(seconds=SAFETY_TIMEOUT_S, exception=NavigationError)
    def get_position_fix(self) -> GPSPosition:
        """Get GPS position with safety timeout.

        Returns:
            GPSPosition: Validated position fix.

        Raises:
            NavigationError: If timeout or invalid fix.

        Safety Notes:
            - Timeout triggers RTL (Return to Launch) in flight mode
            - Last known position preserved in black box
            - Signal degradation logged for analysis
        """
        # Blocking call with hardware
        raw = self._serial.read_until(b"\n")
        return self._parse_nmea(raw)

    def emergency_land_if_no_fix(self) -> None:
        """Emergency procedure when GPS times out."""
        with TimeoutContext(seconds=5.0, exception=SafetyError):
            try:
                position = self.get_position_fix()
                self._last_known_position = position
            except NavigationError:
                # Trigger emergency landing procedure
                self._flight_controller.emergency_land()
```

### 3.4 Resource Cleanup Patterns

```python
from typing import ContextManager, TypeVar, Optional
from contextlib import contextmanager
import weakref

T = TypeVar("T")

class MotorResource:
    """Resource with guaranteed cleanup."""

    def __init__(self, motor_id: str):
        self._motor_id = motor_id
        self._armed: bool = False
        self._pwm_value: int = 0
        self._cleanup_done: bool = False

    def __enter__(self) -> "MotorResource":
        """Arm motor on entry."""
        self._arm()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Emergency stop and disarm on exit."""
        self._emergency_stop()
        self._disarm()
        return False  # Don't suppress exceptions

    def _arm(self) -> None:
        if self._armed:
            raise StateError("Motor already armed")
        self._armed = True
        self._hardware_arm()

    def _disarm(self) -> None:
        if not self._cleanup_done:
            self._hardware_disarm()
            self._cleanup_done = True
        self._armed = False

    def _emergency_stop(self) -> None:
        """Immediate motor shutdown."""
        self._set_pwm(0)

    def _set_pwm(self, value: int) -> None:
        self._pwm_value = value
        # Hardware write...

    def _hardware_arm(self) -> None: ...
    def _hardware_disarm(self) -> None: ...

# Context manager factory
@contextmanager
def safe_motor_operation(motor_id: str) -> ContextManager[MotorResource]:
    """Context manager for safe motor operations.

    Yields:
        MotorResource: Armed motor resource.

    Safety Notes:
        - Motor automatically disarmed on exit
        - Emergency stop triggered on any exception
        - PWM reset to zero before disarm
    """
    resource = MotorResource(motor_id)
    try:
        resource._arm()
        yield resource
    except Exception:
        resource._emergency_stop()
        raise
    finally:
        resource._emergency_stop()
        resource._disarm()

# Weakref cleanup pattern
class HardwareResource:
    """Resource with automatic cleanup via weakref."""

    _active_resources: weakref.WeakSet["HardwareResource"] = weakref.WeakSet()

    def __init__(self, device_path: str):
        self._device_path = device_path
        self._fd: Optional[int] = None
        self._open()
        HardwareResource._active_resources.add(self)

    def _open(self) -> None:
        # Open hardware device
        pass

    def close(self) -> None:
        """Explicit cleanup."""
        if self._fd is not None:
            # Close device
            self._fd = None

    def __del__(self):
        """Finalizer - last resort cleanup."""
        if self._fd is not None:
            # Log warning about resource leak
            logging.warning(f"Resource {self._device_path} not closed properly")
            self.close()

    @classmethod
    def cleanup_all(cls) -> None:
        """Cleanup all active resources - for emergency shutdown."""
        for resource in list(cls._active_resources):
            resource.close()

# Usage pattern
class FlightController:
    def execute_maneuver(self, trajectory: Trajectory) -> Result[None, FlightError]:
        """Execute flight maneuver with resource safety.

        All motors are automatically disarmed on exit, even if
        an exception occurs during execution.

        Safety Notes:
            - Motors armed only for duration of maneuver
            - Emergency stop on any exception
            - All motors disarmed before return
        """
        with safe_motor_operation("M1") as m1, \
             safe_motor_operation("M2") as m2, \
             safe_motor_operation("M3") as m3, \
             safe_motor_operation("M4") as m4:

            motors = [m1, m2, m3, m4]

            for waypoint in trajectory.waypoints:
                speeds = self._calculate_motor_speeds(waypoint)
                for motor, speed in zip(motors, speeds):
                    motor._set_pwm(self._rpm_to_pwm(speed))

                # Check for emergency conditions
                if self._should_abort():
                    return Err(FlightError("Maneuver aborted - emergency condition"))

        # Motors automatically disarmed here
        return Ok(None)
```

---

## 4. Documentation Requirements

### 4.1 Architecture Decision Records (ADRs)

Each significant architectural decision must be recorded.

```markdown
# ADR-001: Flight Control Loop Architecture

## Status
Accepted

## Context
The flight control system requires real-time processing of sensor data
at 400Hz while maintaining safety guarantees. We need to select an
architecture that balances:
- Deterministic timing
- Fault isolation
- Verification complexity
- Hardware resource constraints

## Decision
We will implement a dual-loop architecture:
1. **Hard Real-Time Loop** (400Hz): Runs on isolated CPU core,
   handles IMU fusion and motor control. Written in C for
determinism.
2. **Soft Real-Time Loop** (50Hz): Runs in Python on main core,
   handles GPS, telemetry, and high-level planning.

Communication via lock-free ring buffer (pre-allocated, no malloc in RT loop).

## Consequences

### Positive
- Deterministic timing for critical controls
- Python available for complex planning algorithms
- Clear separation of concerns
- Can verify RT loop independently

### Negative
- Added complexity of two languages
- Communication overhead between loops
- Need careful buffer sizing
- Python GC must not pause main loop

## Safety Impact
- **SIL Level**: SIL-2 for Python components, SIL-3 for C components
- **Verification**: Python loop tested with property-based testing
- **Monitoring**: Watchdog resets if either loop fails

## References
- DO-178C Section 6.4 (Partitioning)
- ISO 26262-6 Annex B (Safety mechanisms)
```

### 4.2 Safety Rationale Comments

All safety-critical code must include safety rationale comments.

```python
def calculate_emergency_descent(
    current_altitude: AltitudeMeters,
    battery_voltage: float,
    ground_speed: VelocityMPS
) -> DescentProfile:
    """Calculate emergency descent profile for RTL.

    SAFETY RATIONALE:
    This function is called when battery reaches critical threshold
    or when communication is lost for >30s. The descent profile must
    ensure the drone reaches ground before battery depletion while
    maintaining safe airspeed.

    Safety Properties:
    1. Time to ground <= Battery remaining / Power consumption
    2. Descent rate <= 3 m/s (regulatory limit per 14 CFR 107.51)
    3. Horizontal speed <= 15 m/s during descent
    4. Landing zone must be within glide range

    Verification:
    - Property tested: test_descent_reaches_ground
    - Bounds tested: test_descent_rate_limits
    - Integration: test_rtl_end_to_end

    Failure Modes:
    - If battery too low for calculated descent: trigger immediate
      landing at current position (emergency_landing_immediate)
    - If landing zone unreachable: select nearest safe zone from
      precomputed emergency_sites database

    Standard Ref: ASTM F3269-21 Section 5.4.2
    """
    # SAFETY: Clamp to valid range - sensor may return erratic values
    # during power fluctuation. Verified by test_sensor_fault_injection.
    safe_voltage = max(0.0, min(battery_voltage, MAX_BATTERY_VOLTAGE))

    # SAFETY: Conservative power estimate - use 120% of measured
    # to account for aging batteries and temperature effects
    power_consumption = estimate_power(ground_speed) * 1.2

    # SAFETY: Minimum 30s reserve for final landing approach
    usable_flight_time = (safe_voltage - MIN_LANDING_VOLTAGE) / power_consumption
    usable_flight_time = max(0, usable_flight_time - 30)

    # ... implementation continues
```

### 4.3 API Documentation

```python
"""Flight Control API - Drone Safety System.

This module provides the primary interface for autonomous flight control.
All functions enforce safety constraints per ASTM F3269-21 and maintain
invariants required for SIL-2 certification.

## API Stability

This API follows semantic versioning. Breaking changes will only occur
in major version updates with 6-month deprecation period.

## Thread Safety

All functions in this module are thread-safe unless explicitly marked
`NOT THREAD-SAFE` in their docstrings. Thread-safe functions use
internal locking - do not hold locks when calling these functions.

## Error Handling

All functions return `Result[T, Error]` where Error types are:
- ValidationError: Input validation failure (caller error)
- StateError: Invalid system state (caller should check state)
- SafetyError: Safety constraint violation (requires immediate action)
- HardwareError: Hardware communication failure (may retry)

## Usage Example

```python
from drone_safety.api import FlightController, SafetyError

controller = FlightController(drone_id="AC-0001-DEADBEEF")

# Arm and takeoff with safety checks
result = controller.arm()
if result.is_err():
    handle_error(result.unwrap_err())

result = controller.takeoff(target_altitude=50.0)
if result.is_err():
    controller.disarm()  # Emergency disarm
    handle_error(result.unwrap_err())

# Execute flight plan
for waypoint in flight_plan.waypoints:
    result = controller.goto(waypoint)
    if result.is_err():
        # SafetyError triggers automatic RTL
        if isinstance(result.unwrap_err(), SafetyError):
            return  # RTL in progress
```

## Safety Guarantees

1. Geofence enforcement at all times during flight
2. Automatic Return-to-Launch on:
   - Communication loss >30s
   - Battery critical threshold
   - GPS loss with insufficient backup
3. Emergency landing on:
   - Motor failure detected
   - IMU fault detected
   - Geofence breach imminent

## See Also
- Architecture: docs/architecture/flight-control.md
- Safety Analysis: docs/safety/FHA-001.md
- Verification Report: docs/verification/v-report-2024.md
"""

from result import Result, Ok, Err

class FlightController:
    """Primary interface for drone flight control.

    Thread-safe. All methods return Result types. Safe for use
    from multiple threads - internal state is protected by reentrant lock.

    Lifecycle:
        1. Instantiate (checks hardware connectivity)
        2. calibrate() - Required before first flight
        3. arm() - Prepare for flight
        4. takeoff() / goto() / land() - Flight operations
        5. disarm() - End flight session

    Safety State Machine:
    ```
    [INIT] --calibrate()--> [CALIBRATED] --arm()--> [ARMED]
                                   |
                                   v
                            [DISARMED] <--disarm()-- [FLYING]
                                   ^                    |
                                   |                    v
                                   +------land()-------+
    ```
    """

    def arm(self) -> Result[None, StateError | HardwareError]:
        """Arm the flight controller for flight.

        Arms all motor controllers and enables flight control outputs.
        Must be called before takeoff().

        Pre-conditions:
            - System state must be CALIBRATED
            - Battery level > 20%
            - GPS fix valid
            - No hardware faults detected

        Post-conditions:
            - Motor controllers armed
            - Control outputs enabled
            - State = ARMED

        Returns:
            Ok(None): Successfully armed
            Err(StateError): Pre-condition not met (check details)
            Err(HardwareError): Hardware communication failure

        Safety Notes:
            - Motors remain stopped - only controller armed
            - Emergency stop switch remains active
            - Props may spin on takeoff() - clear area before arming

        Example:
            >>> result = controller.arm()
            >>> if result.is_err():
            ...     print(f"Cannot arm: {result.unwrap_err()}")

        Raises:
            Never raises exceptions. All errors in Result.
        """
        ...
```

---

## 5. Configuration Files

### 5.1 Complete pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "drone-safety-system"
version = "1.0.0"
description = "Safety-critical drone flight control system"
readme = "README.md"
license = {file = "LICENSE"}
requires-python = ">=3.11"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Aerospace Industry",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "numpy>=1.26.0",
    "pydantic>=2.5.0",
    "result>=0.14.0",
    "typing-extensions>=4.8.0",
]

[project.optional-dependencies]
dev = [
    "black>=24.1.0",
    "mypy>=1.8.0",
    "pylint>=3.0.0",
    "bandit[toml]>=1.7.7",
    "isort>=5.13.0",
    "pre-commit>=3.6.0",
    "pydocstyle>=6.3.0",
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "hypothesis>=6.98.0",
]

[project.scripts]
drone-safety = "drone_safety.cli:main"

# Black configuration
[tool.black]
line-length = 88
target-version = ["py311"]
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

# isort configuration
[tool.isort]
profile = "black"
line_length = 88
known_first_party = ["drone_safety"]
known_third_party = ["numpy", "pydantic", "result"]
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]

# Coverage configuration
[tool.coverage.run]
branch = true
source = ["src/drone_safety"]
omit = [
    "*/tests/*",
    "*/test_*.py",
]

[tool.coverage.report]
precision = 2
fail_under = 90.0
skip_covered = true
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]

# Pylint configuration (see section 2.2 for full pylint section)
[tool.pylint.main]
fail-under = 10.0
recursive = true

[tool.pylint.messages_control]
disable = [
    "C0103",
    "C0114",
    "C0115",
    "C0116",
    "R0903",
    "R0913",
    "W0212",
]

# pytest configuration
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=src/drone_safety",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-report=xml:coverage.xml",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "hardware: marks tests requiring hardware (deselect with '-m \"not hardware\"')",
    "safety: marks safety-critical tests",
    "property: marks property-based tests",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
]

# Pydantic v2 settings
[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
warn_untyped_fields = true
```

### 5.2 Setup Script

```bash
#!/bin/bash
# setup-safety-environment.sh
# Initialize safety-critical Python development environment

set -euo pipefail

echo "=== Drone Safety System - Development Environment Setup ==="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python $REQUIRED_VERSION or higher required (found $PYTHON_VERSION)"
    exit 1
fi

echo "Python version OK: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev]"

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Verify installation
echo ""
echo "=== Verification ==="
echo ""
echo "mypy version:"
mypy --version

echo ""
echo "pylint version:"
pylint --version

echo ""
echo "bandit version:"
bandit --version

echo ""
echo "pre-commit hooks:"
pre-commit --version

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Activate environment: source .venv/bin/activate"
echo "Run type check: mypy src/"
echo "Run lint: pylint src/"
echo "Run security scan: bandit -c bandit.yaml -r src/"
echo "Run pre-commit: pre-commit run --all-files"
```

### 5.3 CI/CD Configuration (GitHub Actions)

```yaml
# .github/workflows/safety-ci.yml
name: Safety-Critical CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  static-analysis:
    name: Static Analysis
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml') }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run Black (format check)
        run: black --check --diff src/ tests/

      - name: Run isort (import order check)
        run: isort --check-only --diff src/ tests/

      - name: Run mypy (type check)
        run: mypy --config-file mypy.ini src/

      - name: Run pylint (lint)
        run: pylint src/ --rcfile=pyproject.toml

      - name: Run bandit (security scan)
        run: bandit -c bandit.yaml -r src/ -f json -o bandit-report.json || true

      - name: Upload bandit report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bandit-report
          path: bandit-report.json

  tests:
    name: Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest -v \
            --cov=src/drone_safety \
            --cov-report=xml \
            --cov-report=term \
            --strict-markers \
            -m "not hardware and not slow"

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  safety-checks:
    name: Safety Checks
    runs-on: ubuntu-latest
    needs: [static-analysis, tests]
    steps:
      - uses: actions/checkout@v4

      - name: Check for safety comment presence
        run: |
          missing=0
          for file in $(find src -name "*.py" -type f); do
            if grep -q "def.*flight\|def.*control\|def.*arm\|def.*motor" "$file" 2>/dev/null; then
              if ! grep -q "Safety Notes:" "$file"; then
                echo "MISSING: $file"
                missing=$((missing + 1))
              fi
            fi
          done
          if [ $missing -gt 0 ]; then
            echo "ERROR: $missing files missing Safety Notes"
            exit 1
          fi

      - name: Check for assert in non-test code
        run: |
          if grep -rn "assert " --include="*.py" src/ 2>/dev/null | grep -v "test_"; then
            echo "ERROR: assert statements found in production code"
            exit 1
          fi

      - name: Check ADR references
        run: |
          if ! ls docs/adr/*.md 2>/dev/null; then
            echo "WARNING: No Architecture Decision Records found"
          fi
```

---

## Appendix: Quick Reference

### Pre-commit Commands
```bash
# Install hooks
pre-commit install

# Run all checks
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
```

### Type Check Commands
```bash
# Basic type check
mypy src/

# With strict config
mypy --config-file mypy.ini src/

# Show error codes
mypy --show-error-codes src/
```

### Security Scan Commands
```bash
# Basic scan
bandit -r src/

# With config
bandit -c bandit.yaml -r src/ -f json

# Skip tests
bandit -r src/ -x tests/
```

### Safety Review Checklist

Before any code is merged:

- [ ] All functions have type annotations
- [ ] All public APIs have Google-style docstrings
- [ ] Safety Notes section present for safety-critical functions
- [ ] No `assert` statements in production code (use exceptions)
- [ ] Input validation at all public boundaries
- [ ] Timeout handling for external operations
- [ ] Resource cleanup in all exit paths
- [ ] mypy strict mode passes
- [ ] pylint score >= 9.0
- [ ] bandit finds no HIGH severity issues
- [ ] Test coverage >= 90%
- [ ] ADR updated if architectural decision made

---

**End of Document**

*This document establishes Python coding standards for safety-critical drone software following DO-178C Level B and ISO/IEC 61508 SIL-2 guidelines.*
