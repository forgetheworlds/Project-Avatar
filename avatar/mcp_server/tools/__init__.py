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

from avatar.mcp_server.tools.acrobatics import (
    front_flip,
    back_flip,
    barrel_roll,
    yaw_spin,
    loop_maneuver,
    corkscrew,
    acrobatic_sequence,
)

from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal,
    point_camera_at,
    orbit_target,
    track_target,
    spiral_search,
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
    # Acrobatic tools
    "front_flip",
    "back_flip",
    "barrel_roll",
    "yaw_spin",
    "loop_maneuver",
    "corkscrew",
    "acrobatic_sequence",
    # Tracking tools
    "set_gimbal",
    "point_camera_at",
    "orbit_target",
    "track_target",
    "spiral_search",
]
