# LLM Drone Control - JSON Tool Schema Design

## Overview

This document defines the JSON tool schema for LLM-based drone control systems. The schema provides a structured interface between LLM reasoning agents and flight control systems, with comprehensive safety constraints and error handling.

---

## Architecture

```
┌─────────────────┐     JSON Tool Schema      ┌──────────────────┐
│   LLM Agent     │ ◄────────────────────────► │  Flight Control  │
│  (Reasoning)    │    Request/Response       │    System        │
└─────────────────┘                           └──────────────────┘
         │                                              │
         │                                              │
         ▼                                              ▼
┌─────────────────┐                           ┌──────────────────┐
│  Tool Validator │                           │  Safety Monitor  │
│   & Router      │                           │  (Independent)   │
└─────────────────┘                           └──────────────────┘
```

---

## Stage 1: Flight Control Tools

### 1.1 arm_and_takeoff

**Purpose:** Arms the drone and initiates takeoff to specified altitude.

```json
{
  "name": "arm_and_takeoff",
  "description": "Arm the drone motors and takeoff to specified altitude. Verifies pre-flight checks before arming.",
  "parameters": {
    "type": "object",
    "required": ["altitude_m"],
    "properties": {
      "altitude_m": {
        "type": "number",
        "description": "Target altitude in meters above takeoff point",
        "minimum": 1.0,
        "maximum": 120.0,
        "default": 5.0
      },
      "verify_sensors": {
        "type": "boolean",
        "description": "Require all sensor checks to pass before arming",
        "default": true
      },
      "takeoff_speed_m_s": {
        "type": "number",
        "description": "Vertical speed during takeoff",
        "minimum": 0.5,
        "maximum": 5.0,
        "default": 2.0
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": { "type": "string", "enum": ["armed", "taking_off", "hovering", "failed"] },
      "current_altitude_m": { "type": "number" },
      "execution_id": { "type": "string", "format": "uuid" },
      "estimated_completion_s": { "type": "number" },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": "DISARMED",
    "battery_min_percent": 20,
    "gps_fix_required": true,
    "geofence_check": true,
    "no_fly_zone_check": true
  },
  "idempotent": false,
  "estimated_duration_s": "altitude_m / takeoff_speed_m_s + 5"
}
```

---

### 1.2 goto_gps

**Purpose:** Navigate to specified GPS coordinates at given altitude and speed.

```json
{
  "name": "goto_gps",
  "description": "Navigate to specified GPS coordinates. Supports curved or straight-line paths with obstacle avoidance.",
  "parameters": {
    "type": "object",
    "required": ["lat", "lon", "alt_m"],
    "properties": {
      "lat": {
        "type": "number",
        "description": "Target latitude in decimal degrees (WGS84)",
        "minimum": -90.0,
        "maximum": 90.0
      },
      "lon": {
        "type": "number",
        "description": "Target longitude in decimal degrees (WGS84)",
        "minimum": -180.0,
        "maximum": 180.0
      },
      "alt_m": {
        "type": "number",
        "description": "Target altitude in meters above takeoff point (AGL)",
        "minimum": 2.0,
        "maximum": 120.0
      },
      "speed_m_s": {
        "type": "number",
        "description": "Cruise speed during navigation",
        "minimum": 1.0,
        "maximum": 20.0,
        "default": 10.0
      },
      "heading_mode": {
        "type": "string",
        "enum": ["course_aligned", "locked", "custom"],
        "default": "course_aligned",
        "description": "Heading behavior during flight"
      },
      "heading_deg": {
        "type": "number",
        "description": "Custom heading in degrees (0-360, required if heading_mode=custom)",
        "minimum": 0.0,
        "maximum": 360.0
      },
      "path_type": {
        "type": "string",
        "enum": ["direct", "curved", "obstacle_avoidance"],
        "default": "obstacle_avoidance"
      },
      "acceptance_radius_m": {
        "type": "number",
        "description": "Radius for waypoint acceptance",
        "minimum": 0.5,
        "maximum": 10.0,
        "default": 2.0
      }
    },
    "dependencies": {
      "heading_mode": {
        "oneOf": [
          {
            "properties": { "heading_mode": { "enum": ["course_aligned", "locked"] } }
          },
          {
            "properties": {
              "heading_mode": { "enum": ["custom"] },
              "heading_deg": { "type": "number" }
            },
            "required": ["heading_deg"]
          }
        ]
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": {
        "type": "string",
        "enum": ["navigating", "arrived", "avoiding_obstacle", "failed", "geofence_violation"]
      },
      "progress_percent": { "type": "number", "minimum": 0, "maximum": 100 },
      "distance_remaining_m": { "type": "number" },
      "estimated_arrival_s": { "type": "number" },
      "current_position": {
        "type": "object",
        "properties": {
          "lat": { "type": "number" },
          "lon": { "type": "number" },
          "alt_m": { "type": "number" }
        }
      },
      "execution_id": { "type": "string", "format": "uuid" },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" },
          "suggested_action": { "type": "string" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING"],
    "mutex": ["hold", "land", "rtl"],
    "geofence_destination_check": true,
    "path_clearance_check": true
  },
  "idempotent": true,
  "estimated_duration_s": "distance_m / speed_m_s"
}
```

---

### 1.3 fly_body_offset

**Purpose:** Move relative to current body frame position.

```json
{
  "name": "fly_body_offset",
  "description": "Fly to a position relative to current body frame (forward, right, up from current orientation).",
  "parameters": {
    "type": "object",
    "required": ["forward_m", "right_m", "up_m"],
    "properties": {
      "forward_m": {
        "type": "number",
        "description": "Distance forward (positive) or backward (negative) in meters",
        "minimum": -100.0,
        "maximum": 100.0
      },
      "right_m": {
        "type": "number",
        "description": "Distance right (positive) or left (negative) in meters",
        "minimum": -100.0,
        "maximum": 100.0
      },
      "up_m": {
        "type": "number",
        "description": "Distance up (positive) or down (negative) in meters",
        "minimum": -50.0,
        "maximum": 50.0
      },
      "speed_m_s": {
        "type": "number",
        "description": "Maximum speed during maneuver",
        "minimum": 0.5,
        "maximum": 15.0,
        "default": 5.0
      },
      "yaw_behavior": {
        "type": "string",
        "enum": ["maintain", "align_with_direction", "custom"],
        "default": "maintain"
      },
      "custom_yaw_deg": {
        "type": "number",
        "description": "Custom yaw angle (required if yaw_behavior=custom)",
        "minimum": 0.0,
        "maximum": 360.0
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": {
        "type": "string",
        "enum": ["moving", "complete", "failed", "geofence_violation"]
      },
      "target_global": {
        "type": "object",
        "properties": {
          "lat": { "type": "number" },
          "lon": { "type": "number" },
          "alt_m": { "type": "number" }
        }
      },
      "distance_remaining_m": { "type": "number" },
      "execution_id": { "type": "string", "format": "uuid" },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL"],
    "mutex": ["goto_gps", "land", "rtl"],
    "geofence_destination_check": true,
    "altitude_bounds_check": true
  },
  "idempotent": false,
  "estimated_duration_s": "sqrt(forward_m^2 + right_m^2 + up_m^2) / speed_m_s"
}
```

---

### 1.4 set_velocity

**Purpose:** Control drone using velocity setpoints in NED frame.

```json
{
  "name": "set_velocity",
  "description": "Set velocity setpoints in North-East-Down (NED) coordinate frame. Drone maintains velocity until new command or mode change.",
  "parameters": {
    "type": "object",
    "required": ["north_m_s", "east_m_s", "down_m_s"],
    "properties": {
      "north_m_s": {
        "type": "number",
        "description": "Velocity north (positive) or south (negative) in m/s",
        "minimum": -25.0,
        "maximum": 25.0
      },
      "east_m_s": {
        "type": "number",
        "description": "Velocity east (positive) or west (negative) in m/s",
        "minimum": -25.0,
        "maximum": 25.0
      },
      "down_m_s": {
        "type": "number",
        "description": "Velocity down (positive) or up (negative) in m/s",
        "minimum": -10.0,
        "maximum": 10.0
      },
      "yaw_rate_deg_s": {
        "type": "number",
        "description": "Yaw rotation rate in degrees per second",
        "minimum": -90.0,
        "maximum": 90.0,
        "default": 0.0
      },
      "yaw_heading_deg": {
        "type": "number",
        "description": "Desired yaw heading (0-360). If provided, yaw_rate is ignored",
        "minimum": 0.0,
        "maximum": 360.0
      },
      "duration_s": {
        "type": "number",
        "description": "Duration to maintain velocity (0=indefinite until next command)",
        "minimum": 0.0,
        "maximum": 300.0,
        "default": 0.0
      },
      "coordinate_frame": {
        "type": "string",
        "enum": ["ned", "body"],
        "default": "ned",
        "description": "Coordinate frame for velocity commands"
      },
      "acceleration_limit_m_s2": {
        "type": "number",
        "description": "Maximum acceleration during velocity change",
        "minimum": 0.5,
        "maximum": 10.0,
        "default": 2.0
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": {
        "type": "string",
        "enum": ["velocity_control_active", "duration_complete", "failed", "geofence_violation"]
      },
      "actual_velocity": {
        "type": "object",
        "properties": {
          "north_m_s": { "type": "number" },
          "east_m_s": { "type": "number" },
          "down_m_s": { "type": "number" },
          "groundspeed_m_s": { "type": "number" }
        }
      },
      "time_remaining_s": { "type": "number" },
      "execution_id": { "type": "string", "format": "uuid" },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL"],
    "mutex": ["goto_gps", "fly_body_offset", "land", "rtl"],
    "velocity_magnitude_check": true,
    "geofence_projection_check": true
  },
  "idempotent": true,
  "estimated_duration_s": "duration_s or indefinite"
}
```

---

### 1.5 hold

**Purpose:** Hold position for specified duration.

```json
{
  "name": "hold",
  "description": "Hold current position and altitude for specified duration. Drone maintains position using GPS and barometer.",
  "parameters": {
    "type": "object",
    "required": ["duration_s"],
    "properties": {
      "duration_s": {
        "type": "number",
        "description": "Duration to hold position in seconds",
        "minimum": 1.0,
        "maximum": 3600.0
      },
      "position_tolerance_m": {
        "type": "number",
        "description": "Maximum position drift tolerance",
        "minimum": 0.1,
        "maximum": 5.0,
        "default": 1.0
      },
      "yaw_behavior": {
        "type": "string",
        "enum": ["maintain", "face_north", "rotate_continuous", "follow_gimbal"],
        "default": "maintain"
      },
      "accept_external_commands": {
        "type": "boolean",
        "description": "Allow new commands to interrupt hold",
        "default": true
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": {
        "type": "string",
        "enum": ["holding", "complete", "interrupted", "failed"]
      },
      "time_elapsed_s": { "type": "number" },
      "time_remaining_s": { "type": "number" },
      "position_accuracy_m": { "type": "number" },
      "execution_id": { "type": "string", "format": "uuid" },
      "interrupted_by": {
        "type": "string",
        "description": "Command that interrupted hold, if applicable"
      },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL"],
    "mutex_lock": true,
    "blocks": ["goto_gps", "fly_body_offset", "set_velocity"]
  },
  "idempotent": false,
  "estimated_duration_s": "duration_s"
}
```

---

### 1.6 land

**Purpose:** Initiate landing sequence at current position.

```json
{
  "name": "land",
  "description": "Land at current horizontal position. Descends at controlled rate until touchdown detected.",
  "parameters": {
    "type": "object",
    "required": [],
    "properties": {
      "descent_rate_m_s": {
        "type": "number",
        "description": "Vertical descent speed",
        "minimum": 0.3,
        "maximum": 3.0,
        "default": 1.0
      },
      "land_at_lat": {
        "type": "number",
        "description": "Optional: Land at specific latitude instead of current position",
        "minimum": -90.0,
        "maximum": 90.0
      },
      "land_at_lon": {
        "type": "number",
        "description": "Optional: Land at specific longitude instead of current position",
        "minimum": -180.0,
        "maximum": 180.0
      },
      "touchdown_threshold_m_s": {
        "type": "number",
        "description": "Vertical velocity threshold to detect touchdown",
        "minimum": 0.1,
        "maximum": 1.0,
        "default": 0.3
      },
      "disarm_after_land": {
        "type": "boolean",
        "description": "Automatically disarm after touchdown",
        "default": true
      },
      "timeout_s": {
        "type": "number",
        "description": "Maximum time allowed for landing",
        "minimum": 30.0,
        "maximum": 600.0,
        "default": 120.0
      }
    },
    "dependencies": {
      "land_at_lat": ["land_at_lon"],
      "land_at_lon": ["land_at_lat"]
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": {
        "type": "string",
        "enum": ["descending", "touchdown_detected", "landed_disarmed", "failed", "timeout"]
      },
      "current_altitude_m": { "type": "number" },
      "descent_rate_m_s": { "type": "number" },
      "estimated_landing_s": { "type": "number" },
      "touchdown_confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "execution_id": { "type": "string", "format": "uuid" },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" },
          "suggested_action": { "type": "string" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL", "HOLD"],
    "mutex_priority": "high",
    "preempts": ["goto_gps", "fly_body_offset", "set_velocity", "hold"],
    "terrain_check": true
  },
  "idempotent": false,
  "estimated_duration_s": "current_altitude_m / descent_rate_m_s + 10"
}
```

---

### 1.7 rtl (Return to Launch)

**Purpose:** Return to takeoff location and land.

```json
{
  "name": "rtl",
  "description": "Return to launch (takeoff) position, maintaining RTL altitude if specified, then land.",
  "parameters": {
    "type": "object",
    "required": [],
    "properties": {
      "rtl_altitude_m": {
        "type": "number",
        "description": "Altitude to maintain during RTL (0=use parameter system default)",
        "minimum": 0.0,
        "maximum": 120.0,
        "default": 0.0
      },
      "cruise_speed_m_s": {
        "type": "number",
        "description": "Speed during RTL navigation",
        "minimum": 1.0,
        "maximum": 20.0,
        "default": 10.0
      },
      "land_after_rtl": {
        "type": "boolean",
        "description": "Land after reaching home point",
        "default": true
      },
      " RTL_path_type": {
        "type": "string",
        "enum": ["direct", "waypoint", "safe_corridor"],
        "default": "direct"
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "status": {
        "type": "string",
        "enum": ["climbing_to_rtl_alt", "returning", "descending", "landed", "failed"]
      },
      "home_position": {
        "type": "object",
        "properties": {
          "lat": { "type": "number" },
          "lon": { "type": "number" },
          "alt_m": { "type": "number" }
        }
      },
      "distance_to_home_m": { "type": "number" },
      "estimated_arrival_s": { "type": "number" },
      "execution_id": { "type": "string", "format": "uuid" },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": ["HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL", "HOLD"],
    "mutex_priority": "critical",
    "preempts_all": true,
    "home_position_recorded": true,
    "geofence_path_check": true
  },
  "idempotent": true,
  "estimated_duration_s": "(distance_to_home + altitude_changes) / cruise_speed_m_s + landing_time"
}
```

---

### 1.8 get_status

**Purpose:** Retrieve complete drone state.

```json
{
  "name": "get_status",
  "description": "Retrieve comprehensive drone status including position, battery, flight mode, and system health.",
  "parameters": {
    "type": "object",
    "required": [],
    "properties": {
      "include_telemetry": {
        "type": "boolean",
        "description": "Include live telemetry data",
        "default": true
      },
      "include_mission_status": {
        "type": "boolean",
        "description": "Include current mission/waypoint status",
        "default": true
      },
      "include_sensor_health": {
        "type": "boolean",
        "description": "Include sensor diagnostic information",
        "default": false
      }
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "timestamp": { "type": "string", "format": "date-time" },
      "state_string": {
        "type": "string",
        "description": "Human-readable state summary",
        "example": "HOVERING at 15m AGL, 73% battery, GPS 12 sats"
      },
      "flight_state": {
        "type": "string",
        "enum": ["DISARMED", "ARMED", "TAKING_OFF", "HOVERING", "FLYING", "VELOCITY_CONTROL", "POSITION_CONTROL", "HOLD", "LANDING", "LANDED", "RTL", "EMERGENCY", "CRITICAL"]
      },
      "armed": { "type": "boolean" },
      "position": {
        "type": "object",
        "properties": {
          "lat": { "type": "number" },
          "lon": { "type": "number" },
          "alt_m": { "type": "number" },
          "relative_alt_m": { "type": "number" },
          "heading_deg": { "type": "number" }
        }
      },
      "home_position": {
        "type": "object",
        "properties": {
          "lat": { "type": "number" },
          "lon": { "type": "number" },
          "alt_m": { "type": "number" }
        }
      },
      "velocity": {
        "type": "object",
        "properties": {
          "north_m_s": { "type": "number" },
          "east_m_s": { "type": "number" },
          "down_m_s": { "type": "number" },
          "groundspeed_m_s": { "type": "number" }
        }
      },
      "attitude": {
        "type": "object",
        "properties": {
          "roll_deg": { "type": "number" },
          "pitch_deg": { "type": "number" },
          "yaw_deg": { "type": "number" }
        }
      },
      "battery": {
        "type": "object",
        "properties": {
          "percent": { "type": "number", "minimum": 0, "maximum": 100 },
          "voltage_v": { "type": "number" },
          "current_a": { "type": "number" },
          "remaining_mah": { "type": "number" },
          "time_remaining_s": { "type": "number" },
          "warning_level": { "type": "string", "enum": ["none", "low", "critical", "emergency"] }
        }
      },
      "gps": {
        "type": "object",
        "properties": {
          "fix_type": { "type": "string", "enum": ["none", "2d", "3d", "3d_dgps", "3d_rtk"] },
          "satellites": { "type": "number" },
          "hdop": { "type": "number" },
          "vdop": { "type": "number" }
        }
      },
      "active_command": {
        "type": "object",
        "properties": {
          "command": { "type": "string" },
          "execution_id": { "type": "string" },
          "progress_percent": { "type": "number" }
        }
      },
      "geofence_status": {
        "type": "object",
        "properties": {
          "enabled": { "type": "boolean" },
          "violation_imminent": { "type": "boolean" },
          "distance_to_boundary_m": { "type": "number" }
        }
      },
      "system_health": {
        "type": "object",
        "properties": {
          "overall": { "type": "string", "enum": ["healthy", "degraded", "unhealthy", "critical"] },
          "sensors": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "name": { "type": "string" },
                "status": { "type": "string", "enum": ["healthy", "degraded", "failed", "unknown"] }
              }
            }
          }
        }
      },
      "error": {
        "type": "object",
        "properties": {
          "code": { "type": "string" },
          "message": { "type": "string" }
        }
      }
    }
  },
  "preconditions": {
    "required_state": "any",
    "no_mutex": true
  },
  "idempotent": true,
  "estimated_duration_s": 0
}
```

---

## 2. Safety Constraints Schema

### 2.1 Parameter Bounds Validation

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ParameterBoundsConfig",
  "type": "object",
  "properties": {
    "global_constraints": {
      "type": "object",
      "properties": {
        "max_altitude_m": { "type": "number", "default": 120 },
        "max_speed_m_s": { "type": "number", "default": 20 },
        "max_horizontal_distance_m": { "type": "number", "default": 1000 },
        "max_flight_time_s": { "type": "number", "default": 1800 },
        "min_battery_takeoff_percent": { "type": "number", "default": 20 },
        "min_battery_rtl_percent": { "type": "number", "default": 15 },
        "min_battery_emergency_percent": { "type": "number", "default": 10 }
      }
    },
    "tool_specific": {
      "type": "object",
      "patternProperties": {
        "^[a-z_]+$": {
          "type": "object",
          "properties": {
            "parameters": {
              "type": "object",
              "patternProperties": {
                "^[a-z_]+$": {
                  "type": "object",
                  "properties": {
                    "min": { "type": "number" },
                    "max": { "type": "number" },
                    "step": { "type": "number" },
                    "required": { "type": "boolean" },
                    "validator": { "type": "string", "description": "Custom validation expression" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### 2.2 Geofence Configuration

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GeofenceConfig",
  "type": "object",
  "properties": {
    "version": { "type": "string", "default": "1.0" },
    "geofences": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "type": {
            "type": "string",
            "enum": ["cylinder", "polygon", "altitude", "keep_in", "keep_out"]
          },
          "enabled": { "type": "boolean", "default": true },
          "priority": { "type": "number", "minimum": 0, "maximum": 100 },
          "action_on_breach": {
            "type": "string",
            "enum": ["report", "hold", "rtl", "land", "emergency_stop"],
            "default": "hold"
          },
          "buffer_m": { "type": "number", "default": 5 },
          "cylinder_params": {
            "type": "object",
            "properties": {
              "center_lat": { "type": "number" },
              "center_lon": { "type": "number" },
              "radius_m": { "type": "number", "minimum": 10 },
              "min_alt_m": { "type": "number" },
              "max_alt_m": { "type": "number" }
            },
            "required": ["center_lat", "center_lon", "radius_m"]
          },
          "polygon_params": {
            "type": "object",
            "properties": {
              "vertices": {
                "type": "array",
                "minItems": 3,
                "items": {
                  "type": "object",
                  "properties": {
                    "lat": { "type": "number" },
                    "lon": { "type": "number" }
                  },
                  "required": ["lat", "lon"]
                }
              },
              "min_alt_m": { "type": "number" },
              "max_alt_m": { "type": "number" }
            },
            "required": ["vertices"]
          },
          "altitude_params": {
            "type": "object",
            "properties": {
              "min_alt_m": { "type": "number", "default": 2 },
              "max_alt_m": { "type": "number", "default": 120 }
            }
          }
        },
        "required": ["id", "type"]
      }
    },
    "validation_checks": {
      "type": "object",
      "properties": {
        "pre_flight": { "type": "boolean", "default": true },
        "pre_command": { "type": "boolean", "default": true },
        "continuous": { "type": "boolean", "default": true },
        "destination_projection": { "type": "boolean", "default": true }
      }
    }
  }
}
```

### 2.3 Mutual Exclusion Matrix

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MutexConfig",
  "type": "object",
  "properties": {
    "version": { "type": "string", "default": "1.0" },
    "default_policy": {
      "type": "string",
      "enum": ["reject", "queue", "preempt"],
      "default": "reject"
    },
    "mutex_groups": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "group_id": { "type": "string" },
          "tools": {
            "type": "array",
            "items": { "type": "string" }
          },
          "policy": {
            "type": "string",
            "enum": ["exclusive", "priority_based"]
          },
          "priorities": {
            "type": "object",
            "description": "Tool priority for priority_based policy (higher = more priority)",
            "additionalProperties": { "type": "number" }
          }
        }
      }
    },
    "state_transitions": {
      "type": "object",
      "description": "Valid state transitions for each tool",
      "patternProperties": {
        "^[A-Z_]+$": {
          "type": "object",
          "properties": {
            "allowed_tools": {
              "type": "array",
              "items": { "type": "string" }
            },
            "blocked_tools": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

**Example Mutex Group:**

```json
{
  "group_id": "navigation",
  "tools": ["goto_gps", "fly_body_offset", "set_velocity", "hold"],
  "policy": "priority_based",
  "priorities": {
    "hold": 100,
    "goto_gps": 80,
    "fly_body_offset": 70,
    "set_velocity": 60
  }
}
```

### 2.4 Emergency Stop (Independent Channel)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EmergencyStopConfig",
  "type": "object",
  "properties": {
    "channels": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": {
            "type": "string",
            "enum": ["rc_switch", "mavlink_command", "hardware_button", "gcs_button", "failsafe_trigger"]
          },
          "priority": { "type": "number", "minimum": 0, "maximum": 1000 },
          "enabled": { "type": "boolean", "default": true },
          "latency_requirement_ms": { "type": "number", "default": 100 }
        }
      }
    },
    "stop_actions": {
      "type": "array",
      "description": "Sequence of actions on emergency stop",
      "items": {
        "type": "object",
        "properties": {
          "action": {
            "type": "string",
            "enum": ["cut_motors", "land_immediate", "rtl", "hover", "notify_gcs"]
          },
          "delay_ms": { "type": "number", "default": 0 },
          "condition": { "type": "string", "description": "Condition to execute this action" }
        }
      },
      "default": [
        { "action": "hover", "delay_ms": 0 },
        { "action": "land_immediate", "delay_ms": 500 },
        { "action": "notify_gcs", "delay_ms": 0 }
      ]
    },
    "recovery": {
      "type": "object",
      "properties": {
        "require_manual_reset": { "type": "boolean", "default": true },
        "require_gcs_authorization": { "type": "boolean", "default": true },
        "reset_timeout_s": { "type": "number", "default": 30 }
      }
    },
    "llm_bypass": {
      "type": "object",
      "description": "Configuration for LLM-independent emergency stop",
      "properties": {
        "hardware_priority": { "type": "boolean", "default": true },
        "direct_fc_connection": { "type": "boolean", "default": true },
        "llm_can_override": { "type": "boolean", "default": false },
        "max_llm_command_delay_ms": { "type": "number", "default": 500 }
      }
    }
  }
}
```

---

## 3. Error Handling Schema

### 3.1 Error Response Standard

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ErrorResponse",
  "type": "object",
  "properties": {
    "success": { "type": "boolean", "const": false },
    "error": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "INVALID_PARAMETERS",
            "OUT_OF_BOUNDS",
            "GEOFENCE_VIOLATION",
            "INVALID_STATE",
            "MUTEX_CONFLICT",
            "PRECONDITION_FAILED",
            "EXECUTION_FAILED",
            "TIMEOUT",
            "PARTIAL_EXECUTION",
            "SENSOR_FAILURE",
            "BATTERY_LOW",
            "GPS_DEGRADED",
            "COMMUNICATION_LOST",
            "EMERGENCY_STOPPED",
            "RETRY_EXHAUSTED",
            "UNKNOWN"
          ]
        },
        "severity": {
          "type": "string",
          "enum": ["info", "warning", "error", "critical"],
          "default": "error"
        },
        "message": { "type": "string" },
        "details": { "type": "object" },
        "recoverable": { "type": "boolean" },
        "suggested_action": { "type": "string" },
        "alternative_commands": {
          "type": "array",
          "items": { "type": "string" }
        }
      },
      "required": ["code", "message", "recoverable"]
    },
    "context": {
      "type": "object",
      "properties": {
        "command": { "type": "string" },
        "execution_id": { "type": "string" },
        "timestamp": { "type": "string", "format": "date-time" },
        "flight_state": { "type": "string" },
        "partial_completion": { "type": "number", "minimum": 0, "maximum": 100 }
      }
    }
  }
}
```

### 3.2 Partial Execution Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PartialExecutionResult",
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "status": { "type": "string", "const": "partial" },
    "completed_steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step": { "type": "number" },
          "action": { "type": "string" },
          "completed": { "type": "boolean" },
          "timestamp": { "type": "string", "format": "date-time" }
        }
      }
    },
    "current_state": {
      "type": "object",
      "properties": {
        "position": {
          "type": "object",
          "properties": {
            "lat": { "type": "number" },
            "lon": { "type": "number" },
            "alt_m": { "type": "number" }
          }
        },
        "flight_mode": { "type": "string" },
        "velocity": {
          "type": "object",
          "properties": {
            "north_m_s": { "type": "number" },
            "east_m_s": { "type": "number" },
            "down_m_s": { "type": "number" }
          }
        }
      }
    },
    "failure_point": {
      "type": "object",
      "properties": {
        "step": { "type": "number" },
        "reason": { "type": "string" },
        "error_code": { "type": "string" }
      }
    },
    "resumable": { "type": "boolean" },
    "resume_point": {
      "type": "object",
      "properties": {
        "step": { "type": "number" },
        "from_position": {
          "type": "object",
          "properties": {
            "lat": { "type": "number" },
            "lon": { "type": "number" },
            "alt_m": { "type": "number" }
          }
        }
      }
    },
    "rollback_available": { "type": "boolean" },
    "rollback_actions": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

### 3.3 Retry Configuration

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RetryConfig",
  "type": "object",
  "properties": {
    "default_policy": {
      "type": "object",
      "properties": {
        "max_attempts": { "type": "number", "default": 3 },
        "backoff_type": {
          "type": "string",
          "enum": ["fixed", "linear", "exponential"],
          "default": "exponential"
        },
        "base_delay_ms": { "type": "number", "default": 1000 },
        "max_delay_ms": { "type": "number", "default": 10000 },
        "jitter": { "type": "boolean", "default": true }
      }
    },
    "tool_specific": {
      "type": "object",
      "patternProperties": {
        "^[a-z_]+$": {
          "type": "object",
          "properties": {
            "max_attempts": { "type": "number" },
            "retryable_errors": {
              "type": "array",
              "items": { "type": "string" }
            },
            "non_retryable_errors": {
              "type": "array",
              "items": { "type": "string" }
            },
            "idempotent": { "type": "boolean" }
          }
        }
      }
    },
    "retry_hooks": {
      "type": "object",
      "properties": {
        "on_retry": { "type": "string", "description": "Hook to execute before retry" },
        "on_exhausted": { "type": "string", "description": "Hook when retries exhausted" }
      }
    }
  }
}
```

### 3.4 State Recovery Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StateRecoveryConfig",
  "type": "object",
  "properties": {
    "recovery_modes": {
      "type": "object",
      "properties": {
        "automatic": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": false },
            "allowed_transitions": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "from": { "type": "string" },
                  "to": { "type": "string" },
                  "condition": { "type": "string" }
                }
              }
            }
          }
        },
        "gcs_assisted": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean", "default": true },
            "timeout_s": { "type": "number", "default": 60 }
          }
        },
        "manual": {
          "type": "object",
          "properties": {
            "requires_operator_present": { "type": "boolean", "default": true },
            "recovery_checklist": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        }
      }
    },
    "state_snapshots": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean", "default": true },
        "interval_s": { "type": "number", "default": 5 },
        "retention_count": { "type": "number", "default": 10 },
        "snapshot_contents": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["position", "mission_state", "battery", "parameters", "sensor_health"]
          }
        }
      }
    },
    "recovery_procedures": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "trigger": {
            "type": "string",
            "enum": ["communication_loss", "gps_loss", "sensor_failure", "low_battery", "geofence_breach"]
          },
          "priority": { "type": "number" },
          "steps": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "action": { "type": "string" },
                "condition": { "type": "string" },
                "timeout_s": { "type": "number" },
                "on_success": { "type": "string" },
                "on_failure": { "type": "string" }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 4. Tool Request/Response Envelope

### 4.1 Request Envelope

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ToolRequest",
  "type": "object",
  "required": ["tool", "request_id", "parameters"],
  "properties": {
    "version": { "type": "string", "default": "1.0" },
    "request_id": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" },
    "tool": { "type": "string" },
    "parameters": { "type": "object" },
    "options": {
      "type": "object",
      "properties": {
        "async": { "type": "boolean", "default": false },
        "timeout_s": { "type": "number" },
        "retry_policy": { "type": "string" },
        "priority": { "type": "number", "minimum": 0, "maximum": 100 },
        "blocking": { "type": "boolean", "default": true },
        "validation_only": { "type": "boolean", "default": false }
      }
    },
    "context": {
      "type": "object",
      "properties": {
        "session_id": { "type": "string" },
        "llm_model": { "type": "string" },
        "operator_present": { "type": "boolean" }
      }
    }
  }
}
```

### 4.2 Response Envelope

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ToolResponse",
  "type": "object",
  "required": ["request_id", "success"],
  "properties": {
    "version": { "type": "string", "default": "1.0" },
    "request_id": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" },
    "tool": { "type": "string" },
    "success": { "type": "boolean" },
    "status": {
      "type": "string",
      "enum": ["pending", "validating", "executing", "completed", "failed", "cancelled", "timeout"]
    },
    "result": { "type": "object" },
    "error": {
      "type": "object",
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "severity": { "type": "string" },
        "recoverable": { "type": "boolean" }
      }
    },
    "execution": {
      "type": "object",
      "properties": {
        "execution_id": { "type": "string", "format": "uuid" },
        "start_time": { "type": "string", "format": "date-time" },
        "end_time": { "type": "string", "format": "date-time" },
        "duration_ms": { "type": "number" },
        "attempts": { "type": "number" }
      }
    },
    "validation": {
      "type": "object",
      "properties": {
        "passed": { "type": "boolean" },
        "checks": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "check": { "type": "string" },
              "passed": { "type": "boolean" },
              "message": { "type": "string" }
            }
          }
        }
      }
    },
    "next_steps": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

---

## 5. Complete Example Tool Call

### Request

```json
{
  "version": "1.0",
  "request_id": "req-550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "tool": "goto_gps",
  "parameters": {
    "lat": 37.7749,
    "lon": -122.4194,
    "alt_m": 50,
    "speed_m_s": 12,
    "path_type": "obstacle_avoidance",
    "acceptance_radius_m": 3
  },
  "options": {
    "async": false,
    "timeout_s": 300,
    "blocking": true,
    "validation_only": false
  },
  "context": {
    "session_id": "sess-1234",
    "operator_present": true
  }
}
```

### Success Response

```json
{
  "version": "1.0",
  "request_id": "req-550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:45Z",
  "tool": "goto_gps",
  "success": true,
  "status": "completed",
  "result": {
    "status": "arrived",
    "progress_percent": 100,
    "distance_remaining_m": 0,
    "current_position": {
      "lat": 37.7749,
      "lon": -122.4194,
      "alt_m": 50.2
    },
    "execution_id": "exec-660e8400-e29b-41d4-a716-446655440001"
  },
  "execution": {
    "execution_id": "exec-660e8400-e29b-41d4-a716-446655440001",
    "start_time": "2024-01-15T10:30:02Z",
    "end_time": "2024-01-15T10:30:45Z",
    "duration_ms": 43000,
    "attempts": 1
  },
  "validation": {
    "passed": true,
    "checks": [
      { "check": "parameter_bounds", "passed": true },
      { "check": "geofence_destination", "passed": true },
      { "check": "path_clearance", "passed": true },
      { "check": "battery_sufficient", "passed": true }
    ]
  }
}
```

### Error Response (Geofence Violation)

```json
{
  "version": "1.0",
  "request_id": "req-550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:05Z",
  "tool": "goto_gps",
  "success": false,
  "status": "failed",
  "error": {
    "code": "GEOFENCE_VIOLATION",
    "severity": "error",
    "message": "Destination point (37.7749, -122.4194) violates geofence 'downtown_restricted_zone'",
    "recoverable": true,
    "suggested_action": "Select alternative destination outside restricted zone",
    "alternative_commands": ["fly_body_offset", "rtl", "get_status"],
    "details": {
      "geofence_id": "downtown_restricted_zone",
      "geofence_name": "Downtown No-Fly Zone",
      "distance_to_boundary_m": 150,
      "nearest_valid_point": {
        "lat": 37.7850,
        "lon": -122.4300
      }
    }
  },
  "validation": {
    "passed": false,
    "checks": [
      { "check": "parameter_bounds", "passed": true },
      { "check": "geofence_destination", "passed": false, "message": "Destination in no-fly zone" }
    ]
  },
  "context": {
    "flight_state": "HOVERING",
    "partial_completion": 0
  }
}
```

---

## 6. Idempotency Keys

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "IdempotencyConfig",
  "type": "object",
  "properties": {
    "enabled": { "type": "boolean", "default": true },
    "key_generation": {
      "type": "string",
      "enum": ["client_provided", "deterministic_hash"],
      "default": "deterministic_hash"
    },
    "ttl_s": { "type": "number", "default": 3600 },
    "storage": {
      "type": "object",
      "properties": {
        "type": { "type": "string", "enum": ["memory", "redis", "persistent"] },
        "retention_count": { "type": "number", "default": 1000 }
      }
    },
    "tool_support": {
      "type": "object",
      "properties": {
        "goto_gps": { "type": "boolean", "default": true },
        "set_velocity": { "type": "boolean", "default": true },
        "rtl": { "type": "boolean", "default": true },
        "arm_and_takeoff": { "type": "boolean", "default": false },
        "fly_body_offset": { "type": "boolean", "default": false },
        "hold": { "type": "boolean", "default": false },
        "land": { "type": "boolean", "default": false }
      }
    }
  }
}
```

---

## 7. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-15 | Initial Stage 1 tool schema |
| 1.1 | TBD | Add Stage 2 advanced tools (orbit, mission upload, camera control) |

---

## Appendix A: State Machine Diagram

```
                    ┌─────────────┐
         ┌─────────►│  DISARMED   │◄────────┐
         │          └──────┬──────┘         │
         │                 │ arm_and_takeoff│
         │                 ▼                │
         │          ┌─────────────┐         │
         │    ┌────►│   ARMED     │────┐    │
         │    │     └─────────────┘    │    │
         │    │            │           │    │
         │    │            ▼           │    │
         │    │     ┌─────────────┐    │    │
         │    └─────│ TAKING_OFF  │────┘    │
         │          └──────┬──────┘         │
         │                 │                 │
         │                 ▼                 │
         │          ┌─────────────┐          │
    land()│◄────────│  HOVERING   │────────►│rtl()
         │          └──────┬──────┘          │
         │     ┌───────────┼───────────┐     │
         │     │           │           │     │
         │     ▼           ▼           ▼     │
         │┌────────┐ ┌──────────┐ ┌──────────┐│
         ││FLYING  │ │ VELOCITY │ │POSITION  ││
         ││(goto)  │ │ CONTROL  │ │CONTROL   ││
         │└────┬───┘ └────┬─────┘ └────┬───┘│
         │     │          │            │     │
         │     └──────────┴────────────┘     │
         │                 │                 │
         │     ┌───────────┴───────────┐     │
         │     │                       │     │
         │     ▼                       ▼     │
         │┌────────┐              ┌────────┐ │
         ││  HOLD  │              │ LANDING│ │
         │└───┬────┘              └───┬────┘ │
         │    │                        │     │
         │    └──────────┬─────────────┘     │
         │               │                   │
         │               ▼                   │
         │          ┌─────────────┐         │
         └─────────►│   LANDED    │─────────┘
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
         ┌─────────►│    RTL      │
         │          └─────────────┘
         │
         │     ┌─────────────────────────┐
         └────►│      EMERGENCY          │
               │ (Independent hardware   │
               │  stop from any state)   │
               └─────────────────────────┘
```
