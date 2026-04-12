"""End-to-End Integration Tests for Project Avatar.

This package contains comprehensive E2E tests that verify the complete
system integration including:
- Full mission lifecycle (connect -> arm -> takeoff -> navigate -> land)
- Failsafe triggers (RC loss, telemetry timeout, geofence breach)
- Performance benchmarks (latency, heartbeat precision, telemetry speed)

All tests use SITL (Software In The Loop) simulation with PX4.
No real hardware is required.

Usage:
    pytest tests/e2e/ -v --run-sitl

Prerequisites:
    - PX4 SITL running: `make px4_sitl gz_x500` (in PX4-Autopilot directory)
    - MAVSDK connection available on udp://:14540
"""

__version__ = "0.5.0"
