"""
Project Avatar Test Suite Root Package.

WHAT IS __init__.py?
-------------------
This file marks the 'tests/' directory as a Python package, allowing Python
to recognize it as an importable module. Without this file, Python would treat
the directory as just a folder, not a code package.

WHY DOES AN EMPTY __init__.py EXIST?
------------------------------------
1. **Package Marker**: In Python, __init__.py is required (pre-3.3) to treat
   a directory as a package. Even in Python 3.3+ (which supports "namespace
   packages"), including an empty __init__.py is a best practice for clarity.

2. **pytest Discovery**: pytest uses this file to identify the test package
   root. It helps pytest understand the test structure and import paths.

3. **Import Organization**: Allows tests to import from each other using
   absolute imports like: from tests.core import some_fixture

4. **Future Expansion**: Provides a place to put package-level fixtures,
   conftest.py imports, or shared test utilities as the project grows.

PACKAGE STRUCTURE
-----------------
tests/
├── __init__.py          <- You are here (package root marker)
├── conftest.py          <- pytest fixtures and configuration
├── core/                <- Core utility tests
│   └── __init__.py
├── mav/                 <- MAV (Micro Air Vehicle) connection tests
│   └── __init__.py
├── mcp_server/          <- MCP server integration tests
│   └── __init__.py
├── tools/               <- Tool-specific unit tests
│   └── __init__.py
├── property/            <- Hypothesis property-based tests
│   └── __init__.py
└── e2e/                 <- End-to-end integration tests
    └── __init__.py

BEGINNER NOTE
-------------
When you run 'pytest tests/', Python first looks for __init__.py files to
understand the package hierarchy. Think of this file as a "signpost" that
says "this folder contains Python code that can be imported."

To run all tests:
    pytest tests/ -v

To run tests from a specific subpackage:
    pytest tests/core/ -v
    pytest tests/e2e/ -v
"""

# This file intentionally left minimal.
# Add package-level test utilities here if needed in the future.
# For now, it simply marks 'tests' as a Python package.
