# AvatarMCPServer MCP Standards Audit

**Date:** 2026-04-12  
**Auditor:** Claude Code (MCP Standards Expert)  
**Scope:** AvatarMCPServer implementation against MCP best practices and standards  
**Files Analyzed:**
- `avatar/mcp_server/server.py`
- `avatar/mcp_server/tools/flight_tools.py`
- `avatar/mcp_server/tools/telemetry_tools.py`
- `avatar/mcp_server/tools/vision_tools.py`

---

## Executive Summary

The AvatarMCPServer implementation provides a solid foundation for drone control via MCP but has several gaps against official MCP standards, particularly in **tool annotations**, **error handling**, and **schema completeness**. The most critical issues relate to missing safety annotations (`destructiveHint`, `readOnlyHint`) that could lead to incorrect agent assumptions about tool behavior.

**Overall Grade:** B- (Good foundation, needs annotation and schema improvements)

---

## 1. Tool Inventory

### 1.1 Flight Control Tools

| Tool Name | File | Input Schema | Output Schema | Description |
|-----------|------|--------------|---------------|-------------|
| `arm_and_takeoff` | server.py, flight_tools.py | `{altitude_m: number}` | `{"success": bool, "message": string, "altitude_m": number}` | Arms and takes off to altitude |
| `land` | server.py, flight_tools.py | `{}` | `{"success": bool, "message": string}` | Lands at current position |
| `rtl` | server.py, flight_tools.py | `{}` | `{"success": bool, "message": string, "home_position": array}` | Return to launch |
| `abort_mission` | server.py, flight_tools.py | `{reason?: string}` | `{"success": bool, "message": string, "reason": string}` | Abort and hover |
| `goto_gps` | server.py, flight_tools.py | `{lat, lon, alt_m?, speed_ms?}` | `{"success": bool, "message": string, "target": object}` | Navigate to GPS |
| `fly_body_offset` | server.py, flight_tools.py | `{forward_m?, right_m?, up_m?, yaw_align?, speed_m_s?}` | `{"success": bool, "offset": object, "transform": object, "target": object}` | Body-relative movement |
| `set_velocity` | server.py, flight_tools.py | `{north_m_s?, east_m_s?, down_m_s?, yaw_deg?, duration_s?}` | `{"success": bool, "velocity_ned": array, "setpoints_sent": number}` | NED velocity control |
| `hold` | server.py, flight_tools.py | `{duration_s?, position_tolerance_m?, auto_rtl_on_drift?}` | `{"success": bool, "duration_s": number, "max_drift_m": number}` | Hold position |

### 1.2 Telemetry Tools

| Tool Name | File | Input Schema | Output Schema | Description |
|-----------|------|--------------|---------------|-------------|
| `get_telemetry` | server.py, telemetry_tools.py | `{}` | `{"success": bool, "position": object, "velocity": object, "attitude": object, "battery": object, ...}` | Comprehensive telemetry |
| `get_battery_status` | telemetry_tools.py | `{}` | `{"success": bool, "battery": object, "safety": object}` | Battery status |
| `get_health_status` | telemetry_tools.py | `{}` | `{"success": bool, "health": object, "ready_to_fly": bool, "issues": array}` | Health checks |
| `get_position_info` | telemetry_tools.py | `{}` | `{"success": bool, "position": object, "home": object, "distance_from_home_m": number}` | Position info |
| `get_status` | server.py, telemetry_tools.py | `{}` | Large unified status object | Unified system status |
| `get_status_tool` | telemetry_tools.py | `{}` | JSON status string | Status as MCP tool |

### 1.3 Vision Tools

| Tool Name | File | Input Schema | Output Schema | Description |
|-----------|------|--------------|---------------|-------------|
| `detect_objects` | server.py, vision_tools.py | `{confidence_threshold?: number}` | `{"success": bool, "detections": array, "total_detections": number}` | Run YOLO detection |
| `get_detected_objects` | server.py, vision_tools.py | `{target_labels?: string[], min_confidence?: number}` | `{"success": bool, "detections": array, "frame_captured": bool}` | Get cached detections |
| `capture_frame` | vision_tools.py | `{}` | `{"success": bool, "image_base64": string, "format": string, "width": number, "height": number}` | Capture camera frame |
| `capture_and_detect` | vision_tools.py | `{target_labels?, min_confidence?}` | Combined frame + detections | Capture and detect |

---

## 2. Standards Compliance Analysis

### 2.1 Tool Design Standards

#### Naming Convention (Partial Compliance)

**Current State:**
- ✓ Tool names are descriptive
- ✗ Missing consistent prefix for grouping (e.g., `drone_`, `vision_`, `telemetry_`)
- ✗ Mixed naming styles (`goto_gps` vs `fly_body_offset` vs `set_velocity`)

**Standards Reference:** MCP recommends action-oriented naming with consistent prefixes for discoverability.

**Issues:**
1. `arm_and_takeoff` should be `drone_arm_and_takeoff` or `flight_arm_and_takeoff`
2. `get_telemetry` should be `telemetry_get` or `drone_get_telemetry`
3. `detect_objects` should be `vision_detect_objects` or `camera_detect`

#### Input Schema Validation (Good Compliance)

**Strengths:**
- ✓ Comprehensive type definitions with `type`, `minimum`, `maximum`
- ✓ Default values specified
- ✓ Descriptions for all parameters
- ✓ `required` arrays defined

**Example Good Practice:**
```json
{
  "type": "object",
  "properties": {
    "altitude_m": {
      "type": "number",
      "description": "Target takeoff altitude in meters",
      "default": 10,
      "minimum": 1,
      "maximum": 120
    }
  },
  "required": []
}
```

**Issues:**
1. Some schemas lack `enum` where appropriate (e.g., `flight_mode` in telemetry)
2. No `pattern` validation for string inputs (e.g., GPS coordinate format)
3. Missing `dependencies` for conditional parameters

#### Output Schema (Weak Compliance)

**Current State:**
- ✗ No structured output schemas defined in tool registration
- ✗ All outputs are JSON strings wrapped in `TextContent`
- ✗ No use of `structuredContent` type for typed outputs

**MCP Standard:**
```json
{
  "outputSchema": {
    "type": "object",
    "properties": {...}
  }
}
```

---

### 2.2 Tool Annotations (Critical Gap)

**Status:** NO ANNOTATIONS IMPLEMENTED

MCP Standard annotations help agents understand tool semantics:

| Annotation | Purpose | Current Status |
|------------|---------|----------------|
| `readOnlyHint` | Does tool modify state? | ❌ NOT IMPLEMENTED |
| `destructiveHint` | Is action irreversible? | ❌ NOT IMPLEMENTED |
| `idempotentHint` | Can it be safely retried? | ❌ NOT IMPLEMENTED |
| `openWorldHint` | Can it return arbitrary data? | ❌ NOT IMPLEMENTED |

**Critical Missing Annotations by Tool:**

| Tool | readOnlyHint | destructiveHint | idempotentHint | Priority |
|------|--------------|-----------------|----------------|----------|
| `arm_and_takeoff` | `false` | `true` | `false` | **CRITICAL** |
| `land` | `false` | `false` | `false` | **CRITICAL** |
| `rtl` | `false` | `false` | `true` | **CRITICAL** |
| `abort_mission` | `false` | `false` | `true` | **CRITICAL** |
| `goto_gps` | `false` | `false` | `true` | **CRITICAL** |
| `set_velocity` | `false` | `false` | `false` | **CRITICAL** |
| `fly_body_offset` | `false` | `false` | `false` | **HIGH** |
| `hold` | `false` | `false` | `false` | **HIGH** |
| `get_telemetry` | `true` | `false` | `true` | **CRITICAL** |
| `get_status` | `true` | `false` | `true` | **CRITICAL** |
| `detect_objects` | `false` | `false` | `false` | **HIGH** |

**Why This Matters:**
Without `destructiveHint`, an agent might incorrectly assume `land` is a read-only query and call it during information gathering. Without `readOnlyHint`, agents can't optimize caching and parallelization.

---

### 2.3 Context Management

#### Description Quality (Good Compliance)

**Strengths:**
- ✓ Comprehensive descriptions with usage guidance
- ✓ Safety warnings embedded in descriptions (e.g., "CRITICAL: Must maintain 20Hz stream")
- ✓ State requirements documented

**Example:**
```python
description=(
    "Set velocity setpoint in NED frame (offboard mode). "
    "CRITICAL: Must maintain 20Hz stream or PX4 triggers failsafe. "
    "Max horizontal: 15 m/s. Max vertical: 3 m/s. "
    "Requires flying state. Transitions to VELOCITY_CONTROL."
)
```

**Issues:**
1. Descriptions could be more concise (MCP recommends <500 chars for optimal context window usage)
2. Some descriptions contain implementation details not relevant to agents

#### Pagination (Not Applicable)

Current tools don't return large datasets that would require pagination. Status: N/A

#### Response Format (Mixed Compliance)

**Current:** All responses are JSON strings in `TextContent`

**MCP Options:**
1. `TextContent` - Plain text (current)
2. `ImageContent` - Binary image data
3. `EmbeddedResource` - Reference to resource
4. `structuredContent` - Typed data with schema

**Gap:** `capture_frame` returns base64 in JSON instead of using `ImageContent` type.

---

### 2.4 Error Handling (Partial Compliance)

#### Error Format (Good)

**Consistent format used across tools:**
```json
{
  "success": false,
  "error": "Descriptive error message"
}
```

#### Actionable Error Messages (Mixed)

**Good Examples:**
- `"Failed to connect to drone. Ensure SITL or hardware is running."` - Actionable
- `"Health check failed - no GPS lock or home position"` - Actionable
- `"State precondition failed: Cannot move in {state} state. Must be in a flying state..."` - Actionable with context

**Weak Examples:**
- `"Failed to arm: {e}"` - Generic exception passthrough
- `"Takeoff failed: {e}"` - Generic exception passthrough
- `"Frame capture failed: {e}"` - Generic exception passthrough

**Missing:**
1. Error codes for programmatic handling
2. `recoverable` field to indicate if retry is safe
3. `suggested_action` field with next steps

**Standards Reference from tool_schema_design.md:**
```json
{
  "error": {
    "code": "GEOFENCE_VIOLATION",
    "message": "Target position exceeds geofence",
    "recoverable": true,
    "suggested_action": "Use goto_gps with coordinates within 100m of home"
  }
}
```

---

### 2.5 Infrastructure (Good Compliance)

#### Async/Await (Excellent)

- ✓ Proper async/await throughout
- ✓ `asyncio.to_thread()` used for blocking operations (vision)
- ✓ No blocking I/O in async paths

#### Connection Management (Good)

- ✓ Singleton ConnectionManager pattern
- ✓ Connection reuse across tools
- ✓ Health checks before operations

#### Cleanup (Good)

- ✓ Graceful shutdown sequence in `AvatarMCPServer.shutdown()`
- ✓ Task cancellation handling in `_maintain_offboard_streaming`
- ✗ Some tools create new `FlightTools()` instances per call (resource inefficiency)

**Issue:** Tool wrappers recreate `FlightTools` instances:
```python
async def land() -> str:
    tools = FlightTools()  # New instance each call
    result = await tools.land()
    return json.dumps(result)
```

#### Health Check (Partial)

- ✓ Server-level health via `get_status` tool
- ✗ No dedicated `health` or `ping` tool for liveness probes
- ✗ No connection health exposed as a tool

---

## 3. Gaps Identified

### 3.1 Critical Gaps (Must Fix)

| # | Gap | Impact | File |
|---|-----|--------|------|
| 1 | **No tool annotations** (`destructiveHint`, `readOnlyHint`, etc.) | Agents can't understand tool semantics; safety risk | server.py:249-524 |
| 2 | **No output schemas** | Agents can't parse responses predictably | server.py:249-524 |
| 3 | `capture_frame` doesn't use `ImageContent` | Inefficient base64 encoding | vision_tools.py:276-287 |
| 4 | `FlightTools` instance per call | Resource waste, no connection reuse | flight_tools.py:1016-1182 |
| 5 | Missing error codes | Can't handle errors programmatically | All tool files |

### 3.2 High Priority Gaps

| # | Gap | Impact | File |
|---|-----|--------|------|
| 6 | No `ping` or `health` tool | Can't verify liveness | server.py |
| 7 | Inconsistent naming convention | Poor discoverability | All tool files |
| 8 | Missing `TelemetryTools` in server | Battery, health tools not exposed | telemetry_tools.py |
| 9 | No pagination for large datasets | Future scalability issue | N/A currently |
| 10 | No resource exposure | Can't expose camera as resource | server.py |

### 3.3 Medium Priority Gaps

| # | Gap | Impact | File |
|---|-----|--------|------|
| 11 | Descriptions too verbose | Wastes context window | server.py |
| 12 | No `capture_and_detect` in server | Missed optimization opportunity | server.py |
| 13 | Missing enum constraints | Less precise validation | server.py |
| 14 | No `progress` notifications for long ops | Poor UX for long operations | flight_tools.py |

---

## 4. Recommendations

### 4.1 Add Tool Annotations (CRITICAL)

Update tool registration in `server.py` to include annotations:

```python
types.Tool(
    name="arm_and_takeoff",
    description="...",
    inputSchema={...},
    # ADD THESE:
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,  # Arms motors - safety critical
        "idempotentHint": False,   # Can't re-arm without landing first
        "openWorldHint": False,
    }
)
```

### 4.2 Add Output Schemas (CRITICAL)

Define output schemas for all tools:

```python
types.Tool(
    name="get_telemetry",
    description="...",
    inputSchema={...},
    outputSchema={  # ADD THIS
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "position": {
                "type": "object",
                "properties": {
                    "latitude_deg": {"type": "number"},
                    "longitude_deg": {"type": "number"},
                    "absolute_altitude_m": {"type": "number"},
                }
            },
            # ... more properties
        }
    }
)
```

### 4.3 Use ImageContent for Frame Capture (HIGH)

Update `capture_frame` to return binary content:

```python
# Instead of base64 in JSON:
return types.ImageContent(
    type="image",
    data=img_bytes,  # Binary data
    mimeType="image/png"
)
```

### 4.4 Add Missing Tools to Server (HIGH)

Register additional tools from `telemetry_tools.py`:

```python
# Add to handle_list_tools():
types.Tool(
    name="get_battery_status",
    description="Get detailed battery status...",
    inputSchema={...},
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
),
types.Tool(
    name="get_health_status",
    description="Get drone health and calibration status...",
    inputSchema={...},
    annotations={...}
),
```

### 4.5 Improve Error Messages (HIGH)

Standardize error format with codes and suggestions:

```python
return json.dumps({
    "success": False,
    "error": {
        "code": "CONNECTION_FAILED",
        "message": "Failed to connect to drone",
        "recoverable": True,
        "suggested_action": "Ensure SITL is running with: make px4_sitl gz_x500",
        "details": str(e)  # Original exception
    }
})
```

### 4.6 Add Health/Ping Tool (MEDIUM)

Add a lightweight health check tool:

```python
types.Tool(
    name="ping",
    description="Check server and drone connectivity",
    inputSchema={...},
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
```

### 4.7 Consider Tool Renaming (LOW)

For consistency, consider prefixes:
- `flight_` prefix for flight controls: `flight_arm_and_takeoff`, `flight_land`
- `telemetry_` prefix for data: `telemetry_get`, `telemetry_battery`
- `vision_` prefix for camera: `vision_detect`, `vision_capture`

---

## 5. Priority Ranking

### CRITICAL (Fix Immediately)

1. **Add tool annotations** - Safety-critical for agent understanding
2. **Add output schemas** - Required for reliable parsing
3. **Fix FlightTools instance recreation** - Performance issue
4. **Add error codes** - Required for programmatic error handling

### HIGH (Fix This Sprint)

5. **Use ImageContent for capture_frame** - Efficiency improvement
6. **Add missing telemetry tools** to server registration
7. **Add ping/health tool** - Operational necessity
8. **Standardize error format** with `recoverable` and `suggested_action`

### MEDIUM (Fix Next Sprint)

9. Shorten verbose descriptions
10. Add `capture_and_detect` to server
11. Add enum constraints where applicable
12. Add progress notifications for long operations

### LOW (Nice to Have)

13. Consider tool renaming with prefixes
14. Add resource exposure for camera stream
15. Add pagination support for future large datasets

---

## 6. Compliance Summary

| Standard Category | Score | Notes |
|-------------------|-------|-------|
| Tool Design (Naming) | C+ | Good names, inconsistent prefixes |
| Input Schemas | A- | Comprehensive, minor gaps |
| Output Schemas | F | Not implemented |
| Tool Annotations | F | Not implemented |
| Error Handling | B | Good format, needs codes |
| Context Management | B+ | Good descriptions, verbose |
| Infrastructure | A- | Good async, minor resource issue |
| **OVERALL** | **B-** | Solid foundation, annotations critical |

---

## 7. References

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- Tool Schema Design Doc: `research/03-software-architecture/tool_schema_design.md`
- MCP SDK API Fix: `docs/solutions/integration-issues/mcp-sdk-api-compatibility.md`

---

## Appendix: Annotation Recommendations by Tool

```python
ANNOTATIONS = {
    "arm_and_takeoff": {
        "readOnlyHint": False,
        "destructiveHint": True,   # Arms motors
        "idempotentHint": False,     # Can't arm twice
        "openWorldHint": False,
    },
    "land": {
        "readOnlyHint": False,
        "destructiveHint": False,    # Can RTL after
        "idempotentHint": True,      # Safe to call multiple times
        "openWorldHint": False,
    },
    "rtl": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,      # Safe to call multiple times
        "openWorldHint": False,
    },
    "abort_mission": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "goto_gps": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,      # Re-sending same target is safe
        "openWorldHint": False,
    },
    "fly_body_offset": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,     # Relative to current position
        "openWorldHint": False,
    },
    "set_velocity": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,     # Time-based, not idempotent
        "openWorldHint": False,
    },
    "hold": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "get_telemetry": {
        "readOnlyHint": True,        # Pure read
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "get_status": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "detect_objects": {
        "readOnlyHint": False,       # Uses compute resources
        "destructiveHint": False,
        "idempotentHint": True,      # Same frame = same result
        "openWorldHint": False,
    },
    "get_detected_objects": {
        "readOnlyHint": True,        # Cache read
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
}
```
