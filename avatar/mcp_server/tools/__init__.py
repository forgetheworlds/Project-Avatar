# MCP tools for drone control

from avatar.mcp_server.tools.flight_tools import (
    FlightTools,
    FlightToolsConfig,
    arm_and_takeoff,
    goto_gps,
    land,
    rtl,
    abort_mission,
    hold,
    haversine_distance,
    set_state_machine,
    set_telemetry_cache,
    get_state_machine,
    get_telemetry_cache,
    set_velocity,
)

from avatar.mcp_server.tools.vision_tools import (
    VisionTools,
    VisionToolsConfig,
    capture_frame,
    get_detected_objects,
)

from avatar.mcp_server.tools.telemetry_tools import (
    TelemetryTools,
    TelemetryToolsConfig,
    get_telemetry,
    get_battery_status,
    get_status,
    get_status_tool,
    get_connection_manager,
    get_guardian,
    set_guardian,
)

__all__ = [
    # Flight tools
    "FlightTools",
    "FlightToolsConfig",
    "arm_and_takeoff",
    "goto_gps",
    "land",
    "rtl",
    "abort_mission",
    "hold",
    "haversine_distance",
    "set_state_machine",
    "set_telemetry_cache",
    "get_state_machine",
    "get_telemetry_cache",
    "set_velocity",
    # Vision tools
    "VisionTools",
    "VisionToolsConfig",
    "capture_frame",
    "get_detected_objects",
    # Telemetry tools
    "TelemetryTools",
    "TelemetryToolsConfig",
    "get_telemetry",
    "get_battery_status",
    "get_status",
    "get_status_tool",
    "get_connection_manager",
    "get_guardian",
    "set_guardian",
]
