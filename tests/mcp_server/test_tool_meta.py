"""Tests for avatar.mcp_server.tool_meta - typed tool metadata helpers.

Task 21: D3.1 - Add tool_meta.py for typed metadata helpers
"""

from dataclasses import fields, is_dataclass

import pytest

from mcp import types


class TestToolMetaDataclass:
    """Tests for ToolMeta dataclass structure."""

    def test_tool_meta_is_dataclass(self) -> None:
        """ToolMeta must be a dataclass."""
        from avatar.mcp_server.tool_meta import ToolMeta

        assert is_dataclass(ToolMeta)

    def test_tool_meta_has_required_fields(self) -> None:
        """ToolMeta must have name, description, input_schema, output_schema fields."""
        from avatar.mcp_server.tool_meta import ToolMeta

        field_names = {f.name for f in fields(ToolMeta)}
        required = {"name", "description", "input_schema", "output_schema"}
        assert required.issubset(field_names), f"Missing fields: {required - field_names}"

    def test_tool_meta_has_hint_fields(self) -> None:
        """ToolMeta must have the four hint fields with default values."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        # Default values per MCP spec
        assert meta.read_only_hint is False
        assert meta.destructive_hint is False
        assert meta.idempotent_hint is False
        assert meta.open_world_hint is True  # Default is True per MCP spec


class TestToolMetaToMcpTool:
    """Tests for ToolMeta.to_mcp_tool() method."""

    def test_to_mcp_tool_returns_tool(self) -> None:
        """to_mcp_tool must return an mcp.types.Tool instance."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="arm_motors",
            description="Arm the drone motors",
            input_schema={"type": "object", "properties": {"force": {"type": "boolean"}}},
            output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
        )

        tool = meta.to_mcp_tool()
        assert isinstance(tool, types.Tool)

    def test_to_mcp_tool_has_correct_name_and_description(self) -> None:
        """to_mcp_tool must preserve name and description."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="arm_motors",
            description="Arm the drone motors",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        tool = meta.to_mcp_tool()
        assert tool.name == "arm_motors"
        assert tool.description == "Arm the drone motors"

    def test_to_mcp_tool_has_input_schema(self) -> None:
        """to_mcp_tool must include inputSchema."""
        from avatar.mcp_server.tool_meta import ToolMeta

        input_schema = {
            "type": "object",
            "properties": {"altitude": {"type": "number", "minimum": 0}},
            "required": ["altitude"],
        }

        meta = ToolMeta(
            name="takeoff",
            description="Take off to specified altitude",
            input_schema=input_schema,
            output_schema={"type": "object"},
        )

        tool = meta.to_mcp_tool()
        assert tool.inputSchema == input_schema

    def test_to_mcp_tool_has_output_schema(self) -> None:
        """to_mcp_tool must include outputSchema."""
        from avatar.mcp_server.tool_meta import ToolMeta

        output_schema = {
            "type": "object",
            "properties": {"success": {"type": "boolean"}, "message": {"type": "string"}},
        }

        meta = ToolMeta(
            name="land",
            description="Land the drone",
            input_schema={"type": "object"},
            output_schema=output_schema,
        )

        tool = meta.to_mcp_tool()
        assert tool.outputSchema == output_schema

    def test_to_mcp_tool_has_annotations_with_all_hints(self) -> None:
        """to_mcp_tool must create ToolAnnotations with all four hints."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="rtl",
            description="Return to launch",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            read_only_hint=False,
            destructive_hint=True,  # RTL can cancel missions
            idempotent_hint=True,  # RTL is idempotent
            open_world_hint=False,  # Closed world (drone only)
        )

        tool = meta.to_mcp_tool()
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is False
        assert tool.annotations.destructiveHint is True
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is False

    def test_to_mcp_tool_with_read_only_tool(self) -> None:
        """Read-only tools should have readOnlyHint=True and destructiveHint=False."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="get_telemetry",
            description="Get current telemetry",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            read_only_hint=True,
        )

        tool = meta.to_mcp_tool()
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False

    def test_to_mcp_tool_annotations_dict(self) -> None:
        """Tool annotations should serialize correctly with all hints."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="emergency_stop",
            description="Emergency stop - immediately halt all operations",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=True,
            open_world_hint=False,
        )

        tool = meta.to_mcp_tool()
        assert tool.annotations is not None

        # Verify model_dump includes all hints
        annotations_dict = tool.annotations.model_dump(exclude_none=True)
        assert "readOnlyHint" in annotations_dict
        assert "destructiveHint" in annotations_dict
        assert "idempotentHint" in annotations_dict
        assert "openWorldHint" in annotations_dict


class TestToolMetaFieldTypes:
    """Tests for ToolMeta field type annotations."""

    def test_name_is_str(self) -> None:
        """name field must be str."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="test",
            description="desc",
            input_schema={},
            output_schema={},
        )
        assert isinstance(meta.name, str)

    def test_description_is_str(self) -> None:
        """description field must be str."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="test",
            description="desc",
            input_schema={},
            output_schema={},
        )
        assert isinstance(meta.description, str)

    def test_input_schema_is_dict(self) -> None:
        """input_schema field must be dict."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="test",
            description="desc",
            input_schema={"type": "object"},
            output_schema={},
        )
        assert isinstance(meta.input_schema, dict)

    def test_output_schema_is_dict(self) -> None:
        """output_schema field must be dict."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="test",
            description="desc",
            input_schema={},
            output_schema={"type": "object"},
        )
        assert isinstance(meta.output_schema, dict)

    def test_hints_are_bool(self) -> None:
        """All hint fields must be bool."""
        from avatar.mcp_server.tool_meta import ToolMeta

        meta = ToolMeta(
            name="test",
            description="desc",
            input_schema={},
            output_schema={},
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )

        assert isinstance(meta.read_only_hint, bool)
        assert isinstance(meta.destructive_hint, bool)
        assert isinstance(meta.idempotent_hint, bool)
        assert isinstance(meta.open_world_hint, bool)
