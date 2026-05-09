"""
Property-Based Test Package for Project Avatar.

WHAT IS __init__.py?
-------------------
This file marks the 'tests/property/' directory as a Python package.
It enables Python to import this directory as a module and provides a
location for package-level documentation and configuration.

WHY DOES THIS FILE EXIST?
-------------------------
1. **Package Marker**: Declares 'property/' as an importable Python package,
   essential for pytest discovery and module imports.

2. **Documentation**: Explains what property-based testing is and why we use it.

3. **Scope Definition**: Clarifies that this package contains Hypothesis-based
   tests that verify invariants rather than specific examples.

4. **Test Organization**: Separates property tests from unit tests, making it
clear which tests use random data generation vs. hardcoded test cases.

WHAT IS PROPERTY-BASED TESTING?
-------------------------------
Unlike traditional unit tests that check specific examples:
    def test_add(): assert add(2, 2) == 4

Property-based tests verify INVARIANTS using random data:
    @given(st.integers(), st.integers())
    def test_add_commutative(a, b): assert add(a, b) == add(b, a)

Benefits:
- Finds edge cases you didn't think of
- Tests with hundreds of random inputs automatically
- Documents behavior properties, not just examples

WHAT BELONGS IN tests/property/?
--------------------------------
This package contains Hypothesis-based property tests for:
- GPS coordinate calculations (haversine distance, coordinate transforms)
- State machine transitions (valid states, no invalid transitions)
- Telemetry data invariants (battery never negative, altitudes in valid range)
- Mission waypoint validation (coordinates within bounds, valid sequences)
- Guardian safety checks (kill switch logic, geofence calculations)
- Velocity/acceleration constraints (physical limits respected)

PACKAGE STRUCTURE
-----------------
tests/property/
├── __init__.py                  <- You are here (package marker)
├── conftest.py                  <- Hypothesis configuration and strategies
├── test_gps_properties.py       <- GPS calculation property tests
├── test_state_machine_properties.py <- State transition property tests
├── test_telemetry_properties.py  <- Telemetry invariant tests
├── test_guardian_properties.py   <- Safety logic property tests
└── test_mission_properties.py    <- Mission validation property tests

REQUIRED DEPENDENCIES
---------------------
These tests require the 'hypothesis' package:
    pip install hypothesis

Or install with dev dependencies:
    pip install -e ".[dev]"

BEGINNER NOTE
-------------
Property tests are like having a tireless tester who tries thousands of
random inputs to break your code. They complement (not replace) unit tests.

Example running property tests:
    pytest tests/property/ -v

Example running with more examples (slower but more thorough):
    pytest tests/property/ --hypothesis-profile=thorough

Learn more: https://hypothesis.readthedocs.io/
"""

# Package marker for property-based tests.
# Hypothesis configuration (deadlines, example counts) should go in conftest.py.
"""
Property-based tests for the drone control system.

This package contains Hypothesis-based property tests that verify
critical invariants and find edge cases through fuzzing.
"""
