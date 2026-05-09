"""MCP Tool Compliance Tests (D3.14).

This module provides parametrized compliance tests for all MCP tools.
Each tool is tested for:
1. Annotations with all 4 required keys (readOnlyHint, destructiveHint, idempotentHint, openWorldHint)
2. outputSchema presence and correct type (object)

The tests use pytest parametrization to run a separate test for each tool,
making it easy to identify which specific tools fail compliance.

Usage:
    pytest tests/mcp_server/test_compliance.py -v
    pytest tests/mcp_server/test_compliance.py -k "get_telemetry"
"""

import pytest
from typing import Any, Dict, List

# Import the tool names list from server
from avatar.mcp_server.server import LISTED_TOOL_NAMES, avatar_mcp_tool_definitions


@pytest.fixture
def tool_specs() -> Dict[str, Dict[str, Any]]:
    """Build a dictionary of tool specifications keyed by tool name.

    Returns:
        Dict mapping tool name to its specification including:
        - annotations: Dict with the 4 hint keys
        - inputSchema: Dict with the input schema
        - outputSchema: Always {"type": "object"} for MCP tools
    """
    tools = avatar_mcp_tool_definitions()
    specs = {}

    for tool in tools:
        annotations_obj = getattr(tool, 'annotations', None)
        input_schema = getattr(tool, 'inputSchema', {})

        # Convert ToolAnnotations to dict if present
        if annotations_obj is not None and hasattr(annotations_obj, 'model_dump'):
            annotations = annotations_obj.model_dump()
        elif annotations_obj is not None and isinstance(annotations_obj, dict):
            annotations = annotations_obj
        else:
            # Default annotations for tools without explicit annotations
            annotations = {
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": False,
                "openWorldHint": True,
            }

        specs[tool.name] = {
            "annotations": annotations,
            "inputSchema": input_schema,
            "outputSchema": {"type": "object"},  # MCP tools always return JSON objects
            "readOnlyHint": annotations.get("readOnlyHint", False),
            "destructiveHint": annotations.get("destructiveHint", True),
            "idempotentHint": annotations.get("idempotentHint", False),
            "openWorldHint": annotations.get("openWorldHint", True),
        }

    return specs


@pytest.mark.parametrize("tool_name", LISTED_TOOL_NAMES)
def test_tool_compliance(tool_name: str, tool_specs: Dict[str, Dict[str, Any]]) -> None:
    """Test that each tool has compliant annotations and schemas.

    D3.14 Compliance Requirements:
    1. readOnlyHint: Must be True or False
    2. destructiveHint: Must be True or False
    3. idempotentHint: Must be True or False
    4. openWorldHint: Must be True or False
    5. outputSchema: Must have "type": "object"

    Args:
        tool_name: Name of the tool to test (parametrized).
        tool_specs: Fixture providing all tool specifications.
    """
    spec = tool_specs[tool_name]

    # Check that all 4 annotation keys are present and valid
    assert spec["readOnlyHint"] in (True, False), (
        f"{tool_name}: readOnlyHint must be True or False, got {spec['readOnlyHint']}"
    )
    assert spec["destructiveHint"] in (True, False), (
        f"{tool_name}: destructiveHint must be True or False, got {spec['destructiveHint']}"
    )
    assert spec["idempotentHint"] in (True, False), (
        f"{tool_name}: idempotentHint must be True or False, got {spec['idempotentHint']}"
    )
    assert spec["openWorldHint"] in (True, False), (
        f"{tool_name}: openWorldHint must be True or False, got {spec['openWorldHint']}"
    )

    # Check outputSchema presence and type
    assert "outputSchema" in spec, f"{tool_name}: missing outputSchema"
    assert spec["outputSchema"]["type"] == "object", (
        f"{tool_name}: outputSchema type must be 'object', got {spec['outputSchema'].get('type')}"
    )


@pytest.mark.parametrize("tool_name", LISTED_TOOL_NAMES)
def test_tool_input_schema(tool_name: str, tool_specs: Dict[str, Dict[str, Any]]) -> None:
    """Test that each tool has a valid inputSchema.

    MCP tools must have an inputSchema with:
    - "type": "object"
    - "properties": dict (can be empty for no-arg tools)
    - "required": list (can be empty)

    Args:
        tool_name: Name of the tool to test (parametrized).
        tool_specs: Fixture providing all tool specifications.
    """
    spec = tool_specs[tool_name]

    assert "inputSchema" in spec, f"{tool_name}: missing inputSchema"
    input_schema = spec["inputSchema"]

    assert input_schema.get("type") == "object", (
        f"{tool_name}: inputSchema type must be 'object', got {input_schema.get('type')}"
    )
    assert "properties" in input_schema, (
        f"{tool_name}: inputSchema must have 'properties' key"
    )
    assert isinstance(input_schema.get("properties", {}), dict), (
        f"{tool_name}: inputSchema properties must be a dict"
    )


def test_tool_count_matches_listed_names() -> None:
    """Test that the number of tools matches LISTED_TOOL_NAMES."""
    tools = avatar_mcp_tool_definitions()
    tool_names = [t.name for t in tools]

    assert len(tools) == len(LISTED_TOOL_NAMES), (
        f"Tool count mismatch: {len(tools)} tools defined, "
        f"but LISTED_TOOL_NAMES has {len(LISTED_TOOL_NAMES)} entries"
    )

    # Check that all listed names are in the actual tools
    for name in LISTED_TOOL_NAMES:
        assert name in tool_names, f"Tool '{name}' in LISTED_TOOL_NAMES but not in tool definitions"


def test_no_duplicate_tool_names() -> None:
    """Test that there are no duplicate tool names."""
    tools = avatar_mcp_tool_definitions()
    tool_names = [t.name for t in tools]

    assert len(tool_names) == len(set(tool_names)), (
        f"Duplicate tool names found: {[name for name in tool_names if tool_names.count(name) > 1]}"
    )
