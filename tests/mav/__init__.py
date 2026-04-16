"""
MAV (Micro Air Vehicle) Connection Test Package.

WHAT IS __init__.py?
-------------------
This file marks the 'tests/mav/' directory as a Python package. When Python
sees __init__.py in a directory, it treats that directory as a module that
can be imported (e.g., 'import tests.mav').

WHY DOES THIS FILE EXIST?
-------------------------
1. **Package Declaration**: Required (pre-Python 3.3) to make 'mav/' importable.
   Still recommended in modern Python for explicit package definition.

2. **Scope Definition**: The docstring clarifies this package tests the MAV
   communication layer between the code and the drone flight controller.

3. **Test Organization**: Helps pytest categorize and discover MAV-specific
tests separately from other test categories.

4. **Import Safety**: Prevents Python from accidentally treating 'mav/' as
   part of a different package due to path confusion.

WHAT BELONGS IN tests/mav/?
---------------------------
This package contains tests for:
- MAVSDK connection establishment and teardown
- MAVLink protocol message handling
- Connection manager lifecycle (connect, disconnect, reconnect)
- UDP/TCP connection endpoints
- Heartbeat monitoring and timeout detection
- Mission protocol communication
- Parameter protocol handling
- Command protocol (arming, mode changes)

PACKAGE STRUCTURE
-----------------
tests/mav/
├── __init__.py              <- You are here (package marker)
├── conftest.py              <- MAV-specific fixtures (mock connections, etc.)
├── test_connection.py       <- Connection establishment tests
├── test_mavlink_messages.py <- MAVLink message parsing tests
├── test_heartbeat.py        <- Heartbeat monitoring tests
├── test_mission_protocol.py <- Mission upload/download tests
└── test_connection_manager.py <- Connection manager unit tests

WHAT IS MAV/MAVLINK/MAVSDK?
---------------------------
- **MAV**: Micro Air Vehicle - the generic term for small drones
- **MAVLink**: The communication protocol drones use to talk to ground stations
- **MAVSDK**: The Python library we use to communicate with PX4/ArduPilot

This test package focuses on the communication layer, NOT the business logic.
Higher-level flight operations are tested in tests/tools/ and tests/e2e/.

BEGINNER NOTE
-------------
Think of this package as testing "the phone line" between our code and the
drone. It ensures messages can be sent and received reliably, but doesn't
test what we say during the conversation (that's in other test packages).

Example running just MAV tests:
    pytest tests/mav/ -v

Example importing MAV test utilities:
    from tests.mav.conftest import mock_mavlink_connection
"""

# Package marker for MAV connection tests.
# Add MAV-specific test utilities or shared mock fixtures here if needed.
