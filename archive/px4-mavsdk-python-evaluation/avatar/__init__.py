"""
Project Avatar - Safety-critical drone control system.

This package provides autonomous drone navigation capabilities with
safety-first design principles for PX4-based UAV systems.

================================================================================
WHAT IS __init__.py? (For Beginners)
================================================================================

An __init__.py file is what turns a regular directory into a Python "package".
Think of it like a folder's business card - it tells Python:

1. "This directory is a module you can import"
2. "Here's what we want to expose when someone imports us"
3. "Run any setup code needed before using this package"

Without this file, Python would treat 'avatar/' as just a folder with Python
files, not as an importable package.

================================================================================
PACKAGE STRUCTURE
================================================================================

avatar/                          <- Root package (this file)
├── __init__.py                  <- You're reading it! Package entry point
├── mav/                         <- MAVSDK drone communication layer
│   ├── __init__.py              <- Exports safety, protocols, PX4 params
│   └── ... (implementation files)
├── mcp_server/                  <- MCP server for AI agent control
│   ├── __init__.py              <- Exports server components
│   └── ... (server implementation)
├── core/                        <- Shared utilities & helpers
│   ├── __init__.py              <- Exports decorators, context managers
│   └── ... (utility modules)
└── vision/                      <- Computer vision (if present)

================================================================================
HOW PACKAGE IMPORTS WORK IN PYTHON
================================================================================

When you write:        Python actually looks for:
--------------------    ------------------------
import avatar           avatar/__init__.py (this file)
from avatar import X     X defined in this file's __all__ or directly
from avatar.mav import Y avatar/mav/__init__.py, then Y from that

The __version__ and __author__ below are standard metadata that tools
like pip, setuptools, and IDEs can read to show package information.

================================================================================
WHY THIS __init__.py IS MINIMAL
================================================================================

This root __init__.py only defines metadata. We DON'T bulk-export everything
here because:

1. Explicit is better than implicit - users should import specific submodules
2. Heavy imports here would slow down EVERY import of the package
3. Safety-critical code benefits from clear import paths
4. Each submodule has its own focused __init__.py for organization

Recommended imports:
    from avatar.mav import AsyncGuardian          # Safety system
    from avatar.mcp_server import AvatarMCPServer  # MCP interface
    from avatar.core import timeout, retry         # Utilities
"""

# Package metadata - these are standard Python conventions
# Tools like pip, poetry, and IDEs read these to show version info
__version__ = "1.0.0"
__author__ = "Drone Safety Team"

# We intentionally do NOT define __all__ here because we want users to
# import from specific submodules. This encourages:
#   - Clear understanding of dependencies
#   - Minimal import overhead
#   - Explicit code that shows where things come from
#
# If you want to see what's available in each submodule:
#   avatar/mav/__init__.py       - Drone communication & safety
#   avatar/mcp_server/__init__.py - MCP server components
#   avatar/core/__init__.py      - Utilities & decorators
