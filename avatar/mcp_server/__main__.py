#!/usr/bin/bin/env python3
"""
Entry point for running the Avatar MCP server as a Python module.

This module enables the MCP server to be started using Python's -m flag:
    python -m avatar.mcp_server

ARCHITECTURE ROLE:
------------------
This is the APPLICATION ENTRY POINT in the Avatar MCP server architecture.
It sits at the outermost layer and handles:

    1. Python Path Configuration: Ensures the project root is in sys.path
       so that avatar.* imports work correctly regardless of where the
       module is executed from.

    2. Module Execution: Delegates to the actual server implementation
       in avatar.mcp_server.server, which contains the FastMCP server
       setup and tool registration.

    3. Async Runtime: Creates the asyncio event loop that runs the
       asynchronous MCP server.

Layer Position in Architecture Stack:
    __main__.py (entry point)
        -> server.py (FastMCP server setup)
            -> tools/ (flight_tools, telemetry_tools, etc.)
                -> connection_manager.py (drone connection)
                    -> mavsdk (MAVLink communication)
                        -> PX4 autopilot (SITL or hardware)

USAGE:
------
Standard execution:
    python -m avatar.mcp_server

With environment variables for configuration:
    FIREWORKS_API_KEY=xxx python -m avatar.mcp_server

In Claude Code MCP configuration:
    {
        "drone": {
            "command": "python",
            "args": ["-m", "avatar.mcp_server"],
            "cwd": "/path/to/Project-Avatar"
        }
    }

The server will start and listen for MCP protocol messages on stdin/stdout.

DEPENDENCIES:
-------------
- avatar.mcp_server.server: Contains the main() function that configures
  and runs the FastMCP server with all drone tools registered.

- asyncio: Required for running the async MCP server.

- sys, os: Used for path manipulation to ensure imports work correctly.

IMPORTANT NOTES:
----------------
1. Path Configuration
   The module calculates the project root relative to this file's location:
       project_root = avatar/mcp_server/__main__.py -> ../../ (Project-Avatar/)
   It inserts this at the beginning of sys.path if not already present.

   This ensures that:
       from avatar.mav.connection_manager import ConnectionManager
   works regardless of the current working directory.

2. No Direct Server Logic
   This file intentionally contains NO server logic - it only handles
   bootstrapping. All server implementation is in server.py for:
       - Better code organization
       - Testability (server.py can be imported without __main__ side effects)
       - Clear separation of concerns

3. Error Handling
   Unhandled exceptions will propagate and print tracebacks to stderr.
   The MCP server in server.py includes its own error handling for
   operational errors (connection failures, command rejections, etc.).

4. Python Version
   Requires Python 3.10+ for the asyncio and type hint features used
   throughout the Avatar codebase.

5. Module vs Script Execution
   This file is ONLY executed when using `python -m avatar.mcp_server`.
   Direct execution (`python avatar/mcp_server/__main__.py`) would fail
   because the relative imports wouldn't resolve correctly.

EXAMPLES:
---------
Run from project root:
    cd /path/to/Project-Avatar
    python -m avatar.mcp_server

Run from any directory:
    # As long as Project-Avatar is accessible, this works due to path setup
    python -m avatar.mcp_server

Debug mode with verbose logging:
    PYTHONASYNCIODEBUG=1 python -m avatar.mcp_server

With custom logging level:
    LOG_LEVEL=DEBUG python -m avatar.mcp_server

MCP Protocol Mode:
    The server communicates via JSON-RPC over stdin/stdout when started.
    This is the standard MCP transport that Claude Code and other MCP
    clients use to communicate with the server.

Development Testing:
    To test without the full MCP protocol, use the tools directly:
        from avatar.mcp_server.tools.flight_tools import FlightTools
        tools = FlightTools()
        result = await tools.arm_and_takeoff(altitude_m=10)
"""

import asyncio
import sys
import os

# =============================================================================
# Python Path Setup
# =============================================================================
# Calculate the project root directory based on this file's location.
# File structure: avatar/mcp_server/__main__.py
# Project root:    ../../ from this file = Project-Avatar/

# Get the directory containing this file: .../avatar/mcp_server/
_current_file_dir = os.path.dirname(os.path.abspath(__file__))

# Go up two levels to reach project root: .../Project-Avatar/
project_root = os.path.dirname(os.path.dirname(_current_file_dir))

# Ensure project root is in Python path for avatar.* imports
# We insert at position 0 to prioritize it over other paths
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    # This allows imports like:
    #   from avatar.mav.connection_manager import ConnectionManager
    # to work regardless of the current working directory

# =============================================================================
# Server Import and Execution
# =============================================================================
# Import the main server entry point from server.py
# This deferred import (after path setup) ensures avatar module is findable

from avatar.mcp_server.server import main  # noqa: E402

# =============================================================================
# Module Execution Guard
# =============================================================================
# This block only executes when the file is run as a module (__name__ == "__main__")
# When imported, the code above runs (path setup) but this block does not

if __name__ == "__main__":
    # Run the async main function from server.py
    # This starts the FastMCP server and begins processing MCP requests

    # asyncio.run():
    #   - Creates a new event loop
    #   - Runs the main() coroutine
    #   - Closes the loop on completion
    #   - Handles KeyboardInterrupt (Ctrl+C) gracefully

    asyncio.run(main())

    # After main() completes (typically only on server shutdown):
    # - Cleanup code in server.py should have run
    # - Connection to drone (if any) should be closed
    # - Any pending tasks should be cancelled
