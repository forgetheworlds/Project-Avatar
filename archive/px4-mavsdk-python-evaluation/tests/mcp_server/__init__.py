"""
MCP Server Test Package.

WHAT IS __init__.py?
-------------------
This file marks the 'tests/mcp_server/' directory as a Python package.
It serves as the entry point when Python imports the test module, allowing
organization of MCP-related tests as a cohesive unit.

WHY DOES AN EMPTY __init__.py EXIST?
------------------------------------
1. **Package Marker**: Essential for Python to recognize 'mcp_server/' as
   an importable package rather than a plain directory.

2. **Test Hierarchy**: Creates a clear boundary for pytest to identify and
   run MCP server tests independently from other test categories.

3. **Import Path**: Enables imports like 'from tests.mcp_server import fixtures'
   for sharing test utilities across MCP test modules.

4. **Future Growth**: Reserves the package namespace for upcoming test modules
   as the MCP server implementation expands.

WHAT BELONGS IN tests/mcp_server/?
----------------------------------
This package contains tests for:
- MCP server initialization and lifecycle
- Tool registration and discovery
- JSON-RPC protocol handling
- Request/response message formatting
- Server configuration and options
- Connection handling between agents and server
- Error handling and malformed request responses
- Server state management

PACKAGE STRUCTURE
-----------------
tests/mcp_server/
├── __init__.py          <- You are here (package marker)
├── conftest.py          <- MCP server fixtures and mocks
├── test_server_init.py  <- Server initialization tests
├── test_tool_registry.py <- Tool registration tests
├── test_protocol.py     <- JSON-RPC protocol tests
└── test_integration.py  <- Server integration tests

WHAT IS MCP?
------------
MCP (Model Context Protocol) is the communication protocol that allows AI
agents (like Claude) to interact with the drone system. The MCP Server
acts as a bridge between natural language commands and drone operations.

This test package verifies that the server correctly:
- Exposes tools to agents
- Handles protocol messages
- Manages connections

BEGINNER NOTE
-------------
Think of this package as testing "the receptionist" that connects AI agents
to the drone system. It tests that requests are received, understood, and
routed correctly - but not necessarily that the drone actions work (that's
tested in tests/tools/ and tests/e2e/).

Example running MCP server tests:
    pytest tests/mcp_server/ -v
"""

# This file marks 'tests/mcp_server' as a Python package.
# The actual tests are in individual modules within this directory.
# Add package-level fixtures or imports here as the test suite grows.
