"""
Core Utilities Test Package.

WHAT IS __init__.py?
-------------------
This file marks the 'tests/core/' directory as a Python package, making it
importable as 'tests.core'. Python executes this file when the package is
first imported, before loading any modules inside.

WHY DOES THIS FILE EXIST?
-------------------------
1. **Package Marker**: Declares that 'core/' is a Python package, not just
   a regular folder. This is essential for test discovery and imports.

2. **Documentation**: The docstring explains what tests belong in this package.

3. **Namespace Control**: Prevents accidental imports from parent directories
   and keeps the test namespace clean.

4. **pytest Integration**: Helps pytest understand test hierarchy and provides
   a location for package-specific conftest.py configurations.

WHAT BELONGS IN tests/core/?
----------------------------
This package contains tests for:
- Core utility functions (config loading, data structures)
- State machine logic and transitions
- Guardian safety system components
- Connection manager utilities
- Helper functions used across the codebase
- Telemetry cache and data structures

PACKAGE STRUCTURE
-----------------
tests/core/
├── __init__.py          <- You are here (package marker)
├── conftest.py          <- Core-specific pytest fixtures
├── test_config.py       <- Configuration loading tests
├── test_state_machine.py <- Flight state machine tests
├── test_guardian.py     <- Safety guardian tests
├── test_telemetry_cache.py <- Telemetry data cache tests
└── test_utils.py        <- General utility function tests

RELATIONSHIP TO OTHER PACKAGES
------------------------------
- tests/mav/          -> Tests MAVSDK connection layer
- tests/mcp_server/   -> Tests MCP server integration
- tests/tools/        -> Tests individual tool implementations
- tests/property/     -> Property-based tests for invariants
- tests/e2e/          -> End-to-end integration tests

BEGINNER NOTE
-------------
Each test subpackage has its own __init__.py. This creates a clear hierarchy
that pytest can navigate. When you run 'pytest tests/core/', pytest uses
this __init__.py to identify where the core test package begins.

Example test discovery:
    pytest tests/core/ -v

Example importing from this package:
    from tests.core.conftest import some_fixture
"""

# This file primarily serves as a package marker.
# Add core-package test utilities or shared fixtures here if needed.
