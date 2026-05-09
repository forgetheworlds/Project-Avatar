# MCP Standards Compliance Fixes

**Date:** 2026-04-12  
**Status:** IN PROGRESS  
**Priority:** CRITICAL (blocks production deployment)  
**Source:** MCP Standards Audit (docs/analysis/mcp_standards_audit.md)

---

## Executive Summary

The AvatarMCPServer has critical gaps in MCP protocol compliance that prevent safe use by external AI agents. This plan addresses the **4 most critical issues** that must be fixed before production deployment.

| Issue | Severity | Impact | Effort |
|-------|----------|--------|--------|
| Missing Tool Annotations | CRITICAL | Agents can't understand tool semantics; safety risk | 6-8 hours |
| No Output Schemas | CRITICAL | Agents can't parse responses predictably | 8-10 hours |
| Missing Error Codes | HIGH | Can't handle errors programmatically | 4-6 hours |
| Resource Inefficiency | MEDIUM | FlightTools recreated per call | 2-3 hours |

**Total Effort:** 20-27 hours

---

## Critical Issues

### Issue 1: Missing Tool Annotations (CRITICAL)

**Problem:** Zero tools have MCP annotations. Agents cannot distinguish:
- Read-only queries (`get_telemetry`) from state-changing actions (`arm_and_takeoff`)
- Destructive operations (`land` - can't un-land) from safe operations
- Idempotent calls (safe to retry) from non-idempotent calls

**Required Annotations by Tool:**

| Tool | readOnlyHint | destructiveHint | idempotentHint | Priority |
|------|--------------|-----------------|----------------|----------|
| `arm_and_takeoff` | false | **true** | false | CRITICAL |
| `land` | false | false | false | CRITICAL |
| `rtl` | false | false | **true** | CRITICAL |
| `abort_mission` | false | false | **true** | CRITICAL |
| `goto_gps` | false | false | **true** | CRITICAL |
| `fly_body_offset` | false | false | false | HIGH |
| `set_velocity` | false | false | false | HIGH |
| `hold` | false | false | false | HIGH |
| `get_telemetry` | **true** | false | **true** | CRITICAL |
| `get_status` | **true** | false | **true** | CRITICAL |
| `detect_objects` | false | false | false | HIGH |
| `capture_frame` | **true** | false | **true** | HIGH |

**Implementation:**
```python
types.Tool(
    name="arm_and_takeoff",
    description="...",
    inputSchema={...},
    annotations=types.ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,   # Arms motors - irreversible without land
        idempotentHint=False,   # Can't re-arm without landing first
        openWorldHint=False,
    )
)
```

---

### Issue 2: No Output Schemas (CRITICAL)

**Problem:** All tools return plain JSON strings. Agents cannot predict response structure or validate outputs.

**Required Output Schemas:**

**For `get_telemetry`:**
```json
{
  "type": "object",
  "properties": {
    "success": {"type": "boolean"},
    "position": {
      "type": "object",
      "properties": {
        "latitude_deg": {"type": "number"},
        "longitude_deg": {"type": "number"},
        "absolute_altitude_m": {"type": "number"},
        "relative_altitude_m": {"type": "number"}
      }
    },
    "velocity": {
      "type": "object",
      "properties": {
        "north_m_s": {"type": "number"},
        "east_m_s": {"type": "number"},
        "down_m_s": {"type": "number"},
        "speed_m_s": {"type": "number"}
      }
    },
    "attitude": {
      "type": "object",
      "properties": {
        "roll_deg": {"type": "number"},
        "pitch_deg": {"type": "number"},
        "yaw_deg": {"type": "number"}
      }
    },
    "battery": {
      "type": "object",
      "properties": {
        "remaining_percent": {"type": "number"},
        "voltage_v": {"type": "number"}
      }
    },
    "error": {"type": "string"}
  },
  "required": ["success"]
}
```

**For `arm_and_takeoff`:**
```json
{
  "type": "object",
  "properties": {
    "success": {"type": "boolean"},
    "message": {"type": "string"},
    "altitude_m": {"type": "number"},
    "state": {"type": "string", "enum": ["HOVER", "ERROR"]},
    "error": {"type": "string"}
  },
  "required": ["success"]
}
```

---

### Issue 3: Missing Error Codes (HIGH)

**Problem:** Error responses lack programmatic error codes, recoverable flags, and suggested actions.

**Current Error Format:**
```json
{
  "success": false,
  "error": "Failed to connect to drone. Ensure SITL or hardware is running."
}
```

**Required Error Format:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Error: Drone not connected. Ensure SITL is running."
    }
  ],
  "isError": true,
  "structuredContent": {
    "error": {
      "code": "CONNECTION_FAILED",
      "message": "Failed to connect to drone",
      "recoverable": true,
      "suggested_action": "Start SITL with: make px4_sitl gz_x500",
      "details": "Connection timeout after 30s"
    }
  }
}
```

**Standard Error Codes to Implement:**
- `CONNECTION_FAILED` - Drone not reachable
- `STATE_PRECONDITION_FAILED` - Wrong flight state for command
- `GEOFENCE_VIOLATION` - Target exceeds safety boundaries  
- `BATTERY_TOO_LOW` - Insufficient battery for operation
- `OFFBOARD_MODE_FAILED` - Could not enter offboard mode
- `TIMEOUT` - Operation exceeded time limit
- `SAFETY_GUARDIAN_BLOCKED` - Guardian prevented unsafe operation

---

### Issue 4: Resource Inefficiency (MEDIUM)

**Problem:** Tool wrappers create new `FlightTools()` instances on each call instead of reusing singleton.

**Current (inefficient):**
```python
async def land() -> str:
    tools = FlightTools()  # New instance every call
    result = await tools.land()
    return json.dumps(result)
```

**Required (efficient):**
```python
# Use singleton from server
_flight_tools: Optional[FlightTools] = None

async def land() -> str:
    global _flight_tools
    if _flight_tools is None:
        _flight_tools = FlightTools()
    result = await _flight_tools.land()
    return json.dumps(result)
```

---

## Bonus: ImageContent for Frame Capture

**Current:** Base64-encoded JSON (inefficient)
```python
return json.dumps({
    "success": True,
    "image_base64": "iVBORw0KGgoAAAANS...",  # ❌ Inefficient
    "format": "PNG"
})
```

**Required:** Use MCP ImageContent type
```python
from mcp.types import ImageContent

return ImageContent(
    type="image",
    data=img_bytes,  # Binary data
    mimeType="image/png"
)
```

---

## Implementation Tasks

### Task 1: Add Tool Annotations (6-8 hours)
- [ ] Define annotations dict for each of 17 tools
- [ ] Update `list_tools()` in server.py to include annotations
- [ ] Add tests to verify annotations present

### Task 2: Define Output Schemas (8-10 hours)
- [ ] Create output schema for `arm_and_takeoff`
- [ ] Create output schema for `land`
- [ ] Create output schema for `rtl`
- [ ] Create output schema for `abort_mission`
- [ ] Create output schema for `goto_gps`
- [ ] Create output schema for `fly_body_offset`
- [ ] Create output schema for `set_velocity`
- [ ] Create output schema for `hold`
- [ ] Create output schema for `get_telemetry`
- [ ] Create output schema for `get_status`
- [ ] Create output schema for `detect_objects`
- [ ] Create output schema for `capture_frame`

### Task 3: Implement Error Codes (4-6 hours)
- [ ] Define error code enum/class
- [ ] Update all error responses to use new format
- [ ] Add `isError: true` flag to error responses
- [ ] Add `recoverable` and `suggested_action` fields

### Task 4: Fix Resource Efficiency (2-3 hours)
- [ ] Create global FlightTools singleton
- [ ] Update all tool wrappers to use singleton
- [ ] Add tests for singleton reuse

### Task 5: Use ImageContent (2-3 hours)
- [ ] Update `capture_frame` to return ImageContent
- [ ] Update `detect_objects` to handle ImageContent
- [ ] Test with MCP Inspector

---

## Testing Strategy

1. **Unit Tests:** Verify each tool has annotations, output schema, proper error format
2. **Integration Tests:** Test with MCP Inspector tool
3. **Validation:** Use mypy to verify type safety
4. **Manual Testing:** Test with Claude Code to verify tools appear correctly

---

## Success Criteria

- [ ] All 17 tools have annotations with correct hints
- [ ] All 17 tools have output schemas defined
- [ ] All error responses include `isError: true` and error codes
- [ ] `capture_frame` returns ImageContent (not base64 JSON)
- [ ] FlightTools singleton reused across calls
- [ ] All tests passing (target: 500+)
- [ ] MCP Inspector validates schema compliance

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking changes to existing clients | Maintain backward compatibility during transition |
| Schema validation failures | Test all schemas with JSON Schema validator |
| ImageContent not supported by all clients | Provide fallback to base64 JSON |

---

## Post-Implementation

After these fixes, the server will be **MCP Standards Compliant** and ready for:
- External AI agent usage
- Production deployment
- Multi-client scenarios
- Public release

---

*Plan created based on MCP Standards Audit (docs/analysis/mcp_standards_audit.md)*
