"""
Tools Test Package.

WHAT IS __init__.py?
-------------------
This file identifies the 'tests/tools/' directory as a Python package.
When Python encounters a directory containing __init__.py, it treats that
directory as a module that can be imported and organized.

WHY DOES AN EMPTY __init__.py EXIST?
------------------------------------
1. **Package Boundary**: Required for Python to treat 'tools/' as a module
   namespace, enabling imports like 'from tests.tools import helpers'.

2. **pytest Organization**: Helps pytest discover and categorize tool-specific
   unit tests separately from integration or end-to-end tests.

3. **Clean Imports**: Prevents namespace pollution by clearly scoping all
tool test utilities within this package.

4. **Scalability**: Provides a foundation for adding package-level test
   configurations, fixtures, or shared utilities as the codebase grows.

WHAT BELONGS IN tests/tools/?
-----------------------------
This package contains UNIT tests for individual tool implementations:
- Flight tools (arm_and_takeoff, goto_gps, land, rtl, etc.)
- Vision tools (capture_frame, get_detected_objects)
- Telemetry tools (get_telemetry, get_battery_status)
- Tracking tools (set_gimbal, orbit_target, track_target)
- Cinematic shot tools (execute_cinematic_shot)
- Acrobatic tools (front_flip, barrel_roll, etc.)

UNIT TESTS vs OTHER TEST TYPES
------------------------------
- **Unit tests (this package)**: Test individual functions in isolation,
  often with mocked dependencies. Fast, focused, many tests.

- **Integration tests (tests/mcp_server/)**: Test how components work together.

- **E2E tests (tests/e2e/)**: Test complete workflows with real SITL simulation.

- **Property tests (tests/property/)**: Test invariants with random data.

PACKAGE STRUCTURE
-----------------
tests/tools/
├── __init__.py              <- You are here (package marker)
├── conftest.py              <- Tool-specific test fixtures
├── test_flight_tools.py     <- Flight operation unit tests
├── test_vision_tools.py     <- Vision/detection unit tests
├── test_telemetry_tools.py  <- Telemetry function unit tests
├── test_tracking_tools.py   <- Tracking function unit tests
├── test_cinematic_shots.py  <- Cinematic shot unit tests
└── test_acrobatics.py       <- Acrobatic maneuver unit tests

BEGINNER NOTE
-------------
Unit tests are like testing each ingredient before cooking a meal. They ensure
each function works correctly on its own before testing the whole system.

These tests typically use mocks to simulate the drone, so they don't require
PX4 SITL to be running. This makes them fast to execute during development.

Example running tool unit tests:
    pytest tests/tools/ -v

Example running a specific tool test file:
    pytest tests/tools/test_flight_tools.py -v
"""

# Package marker for tool unit tests.
# Tool-specific fixtures (mock drones, fake telemetry) should go in conftest.py.
# This file remains minimal to avoid import side effects.
