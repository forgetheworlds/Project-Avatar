"""
End-to-End (E2E) Integration Test Package for Project Avatar.

WHAT IS __init__.py?
-------------------
This file marks the 'tests/e2e/' directory as a Python package, enabling
Python to import it as a module. It also provides comprehensive documentation
about the E2E testing philosophy and requirements.

WHY DOES THIS FILE EXIST?
-------------------------
1. **Package Marker**: Essential for Python to recognize 'e2e/' as an importable
   package for pytest discovery and test organization.

2. **Documentation Hub**: Contains detailed explanations of what E2E tests are,
   how to run them, and what prerequisites are required.

3. **Scope Definition**: Clearly delineates E2E tests from unit and property
tests by explaining they test complete workflows with real simulation.

4. **Configuration**: Defines package-level constants like __version__ that
   may be used by test reporting or CI/CD systems.

WHAT ARE E2E TESTS?
-------------------
End-to-End tests verify COMPLETE system behavior by:
- Starting PX4 SITL (Software In The Loop) simulation
- Connecting to the simulated drone via MAVSDK
- Executing full mission lifecycles
- Testing failsafe scenarios
- Measuring performance metrics

E2E vs OTHER TEST TYPES
------------------------
| Test Type    | Scope              | Speed      | Requires SITL |
|-------------|-------------------|------------|---------------|
| Unit        | Single function   | Fast       | No            |
| Integration | Component chain   | Medium     | Maybe         |
| Property    | Invariants        | Fast       | No            |
| E2E (this)  | Full system       | Slow       | Yes           |

WHAT BELONGS IN tests/e2e/?
----------------------------
This package contains comprehensive E2E tests for:
- Full mission lifecycle (connect -> arm -> takeoff -> navigate -> land)
- Failsafe triggers (RC loss, telemetry timeout, geofence breach)
- Emergency procedures (kill switch, RTL, land immediately)
- Performance benchmarks (latency, heartbeat precision, telemetry speed)
- Multi-agent coordination scenarios
- Vision-assisted navigation workflows
- Long-duration stability tests

PACKAGE STRUCTURE
-----------------
tests/e2e/
├── __init__.py              <- You are here (package documentation)
├── conftest.py              <- E2E fixtures (SITL lifecycle, drone instance)
├── test_mission_lifecycle.py <- Full mission workflow tests
├── test_failsafes.py        <- Failsafe trigger tests
├── test_performance.py      <- Performance benchmark tests
├── test_vision_missions.py  <- Vision-assisted navigation tests
└── test_stability.py        <- Long-duration stability tests

PREREQUISITES
-------------
Before running E2E tests, ensure:
1. PX4-Autopilot repository is cloned in project root
2. PX4 SITL can be built: cd PX4-Autopilot && make px4_sitl gz_x500
3. SITL is running OR auto-start is configured in conftest.py
4. MAVSDK connection available on udp://:14540

USAGE
-----
Run all E2E tests:
    pytest tests/e2e/ -v --run-sitl

Run specific E2E test:
    pytest tests/e2e/test_mission_lifecycle.py -v --run-sitl

Run with performance benchmarking:
    pytest tests/e2e/ --benchmark-only

SAFETY NOTE
-----------
E2E tests use SITL (Software In The Loop) simulation - NO REAL DRONE.
This is safe to run without hardware, but does require computational
resources to run the physics simulator.

BEGINNER NOTE
-------------
E2E tests are like a full dress rehearsal before opening night. They
test the entire system working together, not just individual parts. They
are slower but provide the highest confidence that everything works.

The '--run-sitl' flag is required to indicate you understand that these
tests need the simulator running (or will start it automatically).
"""

# Version identifier for E2E test package
# Used by CI/CD to track which test suite version is running
__version__ = "0.5.0"

# Note: Actual test implementations are in individual modules within this package.
# Shared E2E fixtures (SITL startup, drone connection) are defined in conftest.py.
