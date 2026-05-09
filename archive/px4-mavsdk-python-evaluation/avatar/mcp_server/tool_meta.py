"""Typed metadata helpers for MCP tools.

Task 21: D3.1 - Add tool_meta.py for typed metadata helpers

This module provides ToolMeta, a dataclass for defining MCP tool metadata
with type-safe hints that map to MCP SDK's ToolAnnotations.

Usage:
    from avatar.mcp_server.tool_meta import ToolMeta

    meta = ToolMeta(
        name="arm_motors",
        description="Arm the drone motors",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        read_only_hint=False,
        destructive_hint=True,
    )

    tool = meta.to_mcp_tool()  # Returns mcp.types.Tool
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp import types


@dataclass
class ToolMeta:
    """Typed metadata container for MCP tool definitions.

    This dataclass standardizes tool metadata across the codebase,
    providing type-safe hints that map directly to MCP SDK's ToolAnnotations.

    Attributes:
        name: Programmatic tool name (e.g., "arm_motors").
        description: Human-readable description for LLM context.
        input_schema: JSON Schema for input parameters.
        output_schema: JSON Schema for output structure.
        read_only_hint: True if tool does not modify its environment.
            Default: False.
        destructive_hint: True if tool may perform destructive updates.
            Only meaningful when read_only_hint is False.
            Default: False.
        idempotent_hint: True if repeated calls with same args have no
            additional effect. Only meaningful when read_only_hint is False.
            Default: False.
        open_world_hint: True if tool interacts with external entities.
            Default: True (per MCP spec).

    Example:
        >>> meta = ToolMeta(
        ...     name="get_telemetry",
        ...     description="Get current drone telemetry",
        ...     input_schema={"type": "object"},
        ...     output_schema={"type": "object"},
        ...     read_only_hint=True,
        ... )
        >>> tool = meta.to_mcp_tool()
        >>> tool.name
        'get_telemetry'
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    read_only_hint: bool = False
    destructive_hint: bool = False
    idempotent_hint: bool = False
    open_world_hint: bool = True  # Default per MCP spec

    def to_mcp_tool(self) -> types.Tool:
        """Convert ToolMeta to an mcp.types.Tool instance.

        Creates a Tool with all four hint annotations populated
        from the ToolMeta fields.

        Returns:
            types.Tool: MCP SDK Tool instance ready for registration.

        Example:
            >>> meta = ToolMeta(
            ...     name="emergency_stop",
            ...     description="Emergency stop",
            ...     input_schema={},
            ...     output_schema={},
            ...     destructive_hint=True,
            ... )
            >>> tool = meta.to_mcp_tool()
            >>> tool.annotations.destructiveHint
            True
        """
        annotations = types.ToolAnnotations(
            readOnlyHint=self.read_only_hint,
            destructiveHint=self.destructive_hint,
            idempotentHint=self.idempotent_hint,
            openWorldHint=self.open_world_hint,
        )

        return types.Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
            outputSchema=self.output_schema,
            annotations=annotations,
        )


__all__ = ["ToolMeta"]
