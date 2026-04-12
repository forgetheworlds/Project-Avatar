#!/usr/bin/env python3
"""
Entry point for running the MCP server as a module.

Usage:
    python -m avatar.mcp_server

Or with Claude Code MCP configuration:
    {
        "drone": {
            "command": "python",
            "args": ["-m", "avatar.mcp_server"],
            "cwd": "/path/to/Project-Avatar"
        }
    }
"""

import asyncio
import sys
import os

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from avatar.mcp_server.server import main

if __name__ == "__main__":
    asyncio.run(main())
