# Flight Operations Mission Planning Patterns

## Overview

This document defines standardized mission templates for autonomous flight operations, safety envelopes, LLM-based mission understanding, and dynamic replanning capabilities.

---

## 1. Template Patterns

### 1.1 Search Pattern (Lawnmower)

Systematic area coverage using parallel track lines.

```json
{
  "template_id": "search_lawnmower",
  "name": "Lawnmower Search Pattern",
  "description": "Systematic area coverage with parallel track lines",
  "parameters": {
    "boundary": {
      "type": "polygon",
      "coordinates": [[lat, lon], [lat, lon], [lat, lon], [lat, lon]],
      "required": true
    },
    "track_spacing": {
      "type": "float",
      "unit": "meters",
      "default": 50,
      "min": 10,
      "max": 500,
      "description": "Distance between parallel tracks"
    },
    "direction": {
      "type": "float",
      "unit": "degrees",
      "default": 0,
      "min": 0,
      "max": 360,
      "description": "Bearing of search lines (0 = North)"
    },
    "altitude": {
      "type": "float",
      "unit": "meters AGL",
      "default": 100,
      "min": 20,
      "max": 400
    },
    "speed": {
      "type": "float",
      "unit": "m/s",
      "default": 15,
      "min": 5,
      "max": 30
    },
    "overlap": {
      "type": "float",
      "unit": "percent",
      "default": 20,
      "min": 0,
      "max": 50,
      "description": "Sensor footprint overlap between tracks"
    },
    "turn_type": {
      "type": "enum",
      "options": ["stop_and_turn", "banked_turn", "continuous"],
      "default": "banked_turn"
    },
    "entry_point": {
      "type": "enum",
      "options": ["nearest_corner", "specific", "center"],
      "default": "nearest_corner"
    },
    "specific_entry": {
      "type": "coordinate",
      "required_if": "entry_point == specific"
    }
  },
  "waypoint_generation": {
    "algorithm": "lawnmower_generator",
    "steps": [
      "Calculate bounding box of boundary polygon",
      "Rotate coordinate system by direction angle",
      "Generate parallel lines at track_spacing intervals",
      "Clip lines to boundary polygon",
      "Rotate back to original coordinate system",
      "Add turn waypoints between track ends",
      "Optimize entry/exit points"
    ]
  },
  "estimated_metrics": {
    "coverage_area": "calculated",
    "flight_time": "calculated",
    "waypoint_count": "calculated",
    "turn_count": "calculated"
  }
}
```

### 1.2 Search Pattern (Spiral)

Expanding spiral search from center point outward.

```json
{
  "template_id": "search_spiral",
  "name": "Spiral Search Pattern",
  "description": "Expanding spiral search from center point",
  "parameters": {
    "center": {
      "type": "coordinate",
      "required": true,
      "description": "Starting point of spiral"
    },
    "max_radius": {
      "type": "float",
      "unit": "meters",
      "required": true,
      "min": 50,
      "max": 5000
    },
    "spacing": {
      "type": "float",
      "unit": "meters",
      "default": 50,
      "min": 10,
      "max": 200,
      "description": "Radial distance between spiral loops"
    },
    "direction": {
      "type": "enum",
      "options": ["outward", "inward"],
      "default": "outward"
    },
    "rotation": {
      "type": "enum",
      "options": ["clockwise", "counter_clockwise"],
      "default": "clockwise"
    },
    "altitude": {
      "type": "float",
      "unit": "meters AGL",
      "default": 100,
      "min": 20,
      "max": 400
    },
    "speed": {
      "type": "float",
      "unit": "m/s",
      "default": 15,
      "min": 5,
      "max": 30
    },
    "pitch": {
      "type": "float",
      "unit": "degrees",
      "default": 15,
      "description": "Camera pitch angle for downward-looking sensors"
    }
  },
  "waypoint_generation": {
    "algorithm": "archimedean_spiral",
    "formula": "r = a + b * theta",
    "steps": [
      "Initialize at center point",
      "Generate spiral points at spacing intervals",
      "Limit to max_radius",
      "Interpolate for smooth trajectory",
      "Add altitude waypoints if terrain following"
    ]
  }
}
```

### 1.3 Orbit Pattern

Circular orbit around a center point.

```json
{
  "template_id": "orbit_circle",
  "name": "Circular Orbit Pattern",
  "description": "Continuous circular orbit around target",
  "parameters": {
    "center": {
      "type": "coordinate",
      "required": true,
      "description": "Orbit center point"
    },
    "radius": {
      "type": "float",
      "unit": "meters",
      "default": 100,
      "min": 30,
      "max": 1000
    },
    "altitude": {
      "type": "float",
      "unit": "meters AGL",
      "default": 100,
      "min": 20,
      "max": 400
    },
    "speed": {
      "type": "float",
      "unit": "m/s",
      "default": 15,
      "min": 5,
      "max": 25
    },
    "direction": {
      "type": "enum",
      "options": ["clockwise", "counter_clockwise"],
      "default": "clockwise"
    },
    "loops": {
      "type": "integer",
      "default": 1,
      "min": 1,
      "max": 100
    },
    "entry_angle": {
      "type": "float",
      "unit": "degrees",
      "default": 0,
      "min": 0,
      "max": 360,
      "description": "Approach angle to enter orbit"
    },
    "camera_target": {
      "type": "enum",
      "options": ["center", "forward", "custom"],
      "default": "center"
    },
    "custom_target": {
      "type": "coordinate",
      "required_if": "camera_target == custom"
    }
  },
  "waypoint_generation": {
    "algorithm": "circle_generator",
    "steps": [
      "Calculate entry point based on entry_angle",
      "Generate circle waypoints at 10-degree intervals",
      "Set camera gimbal to target center",
      "Repeat for specified number of loops"
    ],
    "min_segment_length": 10
  }
}
```

### 1.4 Perimeter Scan (Waypoint Sequence)

Sequential waypoint navigation for perimeter monitoring.

```json
{
  "template_id": "perimeter_scan",
  "name": "Perimeter Scan Pattern",
  "description": "Sequential waypoint navigation for perimeter monitoring",
  "parameters": {
    "waypoints": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "position": {
            "type": "coordinate",
            "required": true
          },
          "altitude": {
            "type": "float",
            "unit": "meters AGL"
          },
          "speed": {
            "type": "float",
            "unit": "m/s"
          },
          "hover_time": {
            "type": "float",
            "unit": "seconds",
            "default": 0
          },
          "camera_action": {
            "type": "enum",
            "options": ["none", "capture", "pan_scan", "record_start", "record_stop", "zoom_in", "zoom_out"],
            "default": "none"
          },
          "sensor_trigger": {
            "type": "array",
            "items": "string",
            "description": "Activate specific sensors at waypoint"
          },
          "action_radius": {
            "type": "float",
            "unit": "meters",
            "default": 5,
            "description": "Acceptance radius for waypoint completion"
          }
        }
      },
      "min_items": 2,
      "max_items": 100
    },
    "loop": {
      "type": "boolean",
      "default": false,
      "description": "Return to first waypoint after last"
    },
    "loop_count": {
      "type": "integer",
      "default": 1,
      "min": 1,
      "max": 100,
      "required_if": "loop == true"
    },
    "path_type": {
      "type": "enum",
      "options": ["direct", "curved", "terrain_follow"],
      "default": "curved"
    },
    "transition_speed": {
      "type": "float",
      "unit": "m/s",
      "description": "Speed during waypoint transitions"
    }
  },
  "validation_rules": {
    "max_total_distance": 50000,
    "max_altitude_variance": 200,
    "min_waypoint_spacing": 10,
    "self_intersection_check": true
  }
}
```

### 1.5 Moving Target Follow

Dynamic tracking of moving ground targets.

```json
{
  "template_id": "moving_target_follow",
  "name": "Moving Target Follow",
  "description": "Dynamic tracking and following of moving ground targets",
  "parameters": {
    "target": {
      "type": "object",
      "properties": {
        "target_id": {
          "type": "string",
          "required": true
        },
        "target_type": {
          "type": "enum",
          "options": ["vehicle", "person", "vessel", "aircraft", "unknown"],
          "default": "unknown"
        },
        "initial_position": {
          "type": "coordinate",
          "required": true
        },
        "position_source": {
          "type": "enum",
          "options": [["visual_tracking", "gps_beacon", "adsb", "manual_input", "predicted"]],
          "default": "visual_tracking"
        }
      }
    },
    "follow_mode": {
      "type": "enum",
      "options": ["trail", "lead", "parallel", "orbit", "hover"],
      "default": "trail"
    },
    "follow_distance": {
      "type": "float",
      "unit": "meters",
      "default": 100,
      "min": 30,
      "max": 1000
    },
    "follow_altitude": {
      "type": "float",
      "unit": "meters AGL",
      "default": 100,
      "min": 20,
      "max": 400
    },
    "follow_bearing": {
      "type": "float",
      "unit": "degrees",
      "default": 180,
      "min": 0,
      "max": 360,
      "description": "Relative bearing to maintain (0 = in front, 180 = behind)"
    },
    "speed_matching": {
      "type": "boolean",
      "default": true,
      "description": "Match target ground speed plus buffer"
    },
    "speed_buffer": {
      "type": "float",
      "unit": "m/s",
      "default": 5,
      "min": 0,
      "max": 15,
      "required_if": "speed_matching == true"
    },
    "max_speed": {
      "type": "float",
      "unit": "m/s",
      "default": 25,
      "min": 5,
      "max": 35
    },
    "altitude_mode": {
      "type": "enum",
      "options": ["fixed", "relative_to_target", "terrain_follow"],
      "default": "fixed"
    },
    "prediction_horizon": {
      "type": "float",
      "unit": "seconds",
      "default": 5,
      "min": 0,
      "max": 30,
      "description": "Time to predict target position ahead"
    },
    "lost_target_action": {
      "type": "enum",
      "options": ["hover", "search_pattern", "return_last_known", "abort"],
      "default": "search_pattern"
    },
    "lost_target_timeout": {
      "type": "float",
      "unit": "seconds",
      "default": 30,
      "min": 5,
      "max": 300
    }
  },
  "dynamic_behavior": {
    "update_frequency": 5,
    "position_prediction": "linear_extrapolation",
    "collision_avoidance": true,
    "terrain_clearance_min": 30
  }
}
```

---

## 2. Safety Envelopes

### 2.1 Geofencing - Max Distance from Home

```json
{
  "safety_envelope": {
    "type": "geofence",
    "envelope_id": "max_distance_from_home",
    "description": "Maximum distance aircraft can travel from home point",
    "parameters": {
      "home_position": {
        "type": "coordinate",
        "auto_set": "takeoff_location",
        "manual_override": true
      },
      "max_distance": {
        "type": "float",
        "unit": "meters",
        "default": 1000,
        "min": 100,
        "max": 10000,
        "phase_overrides": {
          "takeoff": 100,
          "climb": 500,
          "mission": 5000,
          "return": 10000,
          "landing": 100
        }
      },
      "warning_distance": {
        "type": "float",
        "unit": "meters",
        "default": 80,
        "description": "Percentage of max distance for warning"
      },
      "boundary_action": {
        "type": "enum",
        "options": ["hover", "return_home", "land_in_place", "continue_with_warning"],
        "default": "return_home"
      },
      "shape": {
        "type": "enum",
        "options": ["circle", "ellipse", "polygon"],
        "default": "circle"
      }
    }
  }
}
```

### 2.2 Altitude Bands per Phase

```json
{
  "safety_envelope": {
    "type": "altitude_constraints",
    "envelope_id": "altitude_bands",
    "description": "Altitude restrictions per flight phase",
    "phases": {
      "takeoff": {
        "min_altitude_agl": 0,
        "max_altitude_agl": 30,
        "max_ascent_rate": 3,
        "duration_limit_seconds": 60,
        "transitions_to": ["climb", "abort_landing"]
      },
      "climb": {
        "min_altitude_agl": 20,
        "max_altitude_agl": 120,
        "max_ascent_rate": 5,
        "duration_limit_seconds": 120,
        "transitions_to": ["mission", "return_home"]
      },
      "mission": {
        "min_altitude_agl": 30,
        "max_altitude_agl": 400,
        "max_ascent_rate": 3,
        "max_descent_rate": 3,
        "terrain_clearance_min": 20,
        "duration_limit_seconds": 1800,
        "transitions_to": ["return_home", "emergency_land"]
      },
      "return_home": {
        "min_altitude_agl": 30,
        "max_altitude_agl": 120,
        "preferred_altitude_agl": 60,
        "max_descent_rate": 3,
        "duration_limit_seconds": 600,
        "transitions_to": ["landing", "hold"]
      },
      "landing": {
        "min_altitude_agl": 0,
        "max_altitude_agl": 30,
        "max_descent_rate": 2,
        "duration_limit_seconds": 120,
        "final_approach_altitude": 10,
        "touchdown_zone_radius": 5,
        "transitions_to": ["landed", "go_around"]
      },
      "hover": {
        "min_altitude_agl": 10,
        "max_altitude_agl": 100,
        "hold_duration_limit": 300,
        "transitions_to": ["mission", "return_home", "landing"]
      },
      "emergency_land": {
        "min_altitude_agl": 0,
        "max_descent_rate": 5,
        "find_safe_zone": true,
        "priority": "immediate"
      }
    },
    "absolute_ceiling": {
      "max_altitude_amsl": 120,
      "unit": "meters",
      "jurisdiction": "faa_part_107"
    }
  }
}
```

### 2.3 Timeout per Mission Phase

```json
{
  "safety_envelope": {
    "type": "phase_timeouts",
    "envelope_id": "mission_phase_timeouts",
    "description": "Maximum duration limits for each mission phase",
    "timeout_policy": {
      "default_action": "return_home",
      "escalation_delay_seconds": 30,
      "pilot_override": true
    },
    "phases": {
      "preflight_check": {
        "timeout_seconds": 300,
        "timeout_action": "abort_mission",
        "warning_at": 240
      },
      "takeoff": {
        "timeout_seconds": 120,
        "timeout_action": "abort_and_land",
        "warning_at": 90
      },
      "transit_to_mission": {
        "timeout_seconds": 600,
        "timeout_action": "return_home",
        "warning_at": 480
      },
      "mission_execution": {
        "timeout_seconds": 3600,
        "timeout_action": "return_home",
        "warning_at": 3000,
        "extendable": true,
        "max_extension": 1800
      },
      "target_acquisition": {
        "timeout_seconds": 300,
        "timeout_action": "return_home",
        "warning_at": 240
      },
      "target_tracking": {
        "timeout_seconds": 1800,
        "timeout_action": "return_home",
        "warning_at": 1500,
        "extendable": true
      },
      "return_home": {
        "timeout_seconds": 900,
        "timeout_action": "emergency_land",
        "warning_at": 720
      },
      "landing_approach": {
        "timeout_seconds": 180,
        "timeout_action": "go_around",
        "warning_at": 120
      },
      "final_landing": {
        "timeout_seconds": 60,
        "timeout_action": "emergency_land",
        "warning_at": 45
      }
    },
    "cumulative_limits": {
      "max_mission_duration": 3600,
      "max_total_flight_time": 5400,
      "battery_reserve_threshold": 20
    }
  }
}
```

### 2.4 Abort Conditions

```json
{
  "safety_envelope": {
    "type": "abort_conditions",
    "envelope_id": "mission_abort_triggers",
    "description": "Conditions that trigger automatic mission abort",
    "abort_levels": {
      "immediate": {
        "priority": 1,
        "action": "emergency_land",
        "notify_operator": true
      },
      "critical": {
        "priority": 2,
        "action": "return_home",
        "notify_operator": true
      },
      "caution": {
        "priority": 3,
        "action": "hover_and_await_instruction",
        "notify_operator": true
      }
    },
    "conditions": {
      "immediate": [
        {
          "id": "battery_critical",
          "trigger": "battery_level < 10%",
          "description": "Battery critically low"
        },
        {
          "id": "engine_failure",
          "trigger": "engine_status == failure OR rpm < minimum",
          "description": "Engine or motor failure detected"
        },
        {
          "id": "flight_control_failure",
          "trigger": "control_surface_fault OR imu_failure",
          "description": "Primary flight control system failure"
        },
        {
          "id": "gps_loss_critical",
          "trigger": "gps_satellites < 4 AND duration > 10s",
          "description": "GPS position lost for critical duration"
        },
        {
          "id": "collision_imminent",
          "trigger": "obstacle_distance < 5m AND closing",
          "description": "Imminent collision detected"
        },
        {
          "id": "geofence_breach",
          "trigger": "position outside authorized_boundary",
          "description": "Unauthorized airspace entry"
        },
        {
          "id": "link_loss_extended",
          "trigger": "command_link_lost AND duration > 60s",
          "description": "Command link lost beyond failsafe threshold"
        },
        {
          "id": "structural_fault",
          "trigger": "vibration_anomaly OR structural_sensor_alert",
          "description": "Structural integrity concern"
        }
      ],
      "critical": [
        {
          "id": "battery_low",
          "trigger": "battery_level < 25%",
          "description": "Battery below return threshold"
        },
        {
          "id": "weather_deterioration",
          "trigger": "wind_speed > max_operational OR visibility < minimum",
          "description": "Weather conditions exceeded limits"
        },
        {
          "id": "communication_degraded",
          "trigger": "telemetry_link_quality < 30%",
          "description": "Communication link degraded"
        },
        {
          "id": "navigation_uncertainty",
          "trigger": "position_accuracy > 50m",
          "description": "Navigation accuracy degraded"
        },
        {
          "id": "payload_failure",
          "trigger": "primary_payload_offline",
          "description": "Mission-critical payload failure"
        },
        {
          "id": "temperature_extreme",
          "trigger": "internal_temp > 70C OR internal_temp < -20C",
          "description": "Temperature limits exceeded"
        }
      ],
      "caution": [
        {
          "id": "battery_warning",
          "trigger": "battery_level < 40%",
          "description": "Battery below extended mission threshold"
        },
        {
          "id": "wind_increasing",
          "trigger": "wind_speed > 0.8 * max_operational",
          "description": "Wind approaching operational limits"
        },
        {
          "id": "gps_degraded",
          "trigger": "gps_accuracy > 10m",
          "description": "GPS accuracy degraded"
        },
        {
          "id": "payload_anomaly",
          "trigger": "payload_status == degraded",
          "description": "Payload performance degraded"
        },
        {
          "id": "proximity_warning",
          "trigger": "aircraft_proximity < 500m",
          "description": "Manned aircraft in vicinity"
        }
      ]
    },
    "operator_override": {
      "enabled": true,
      "authentication": "required",
      "level_override": ["caution", "critical"],
      "immediate_level": false
    }
  }
}
```

---

## 3. LLM Mission Understanding

### 3.1 Natural Language to Template Matching

```json
{
  "llm_mission_understanding": {
    "component": "template_matching",
    "description": "Map natural language requests to mission templates",
    "intent_classification": {
      "categories": [
        {
          "intent": "area_search",
          "templates": ["search_lawnmower", "search_spiral"],
          "keywords": ["search", "scan", "survey", "inspect", "look for", "find in area", "cover area"],
          "confidence_threshold": 0.7
        },
        {
          "intent": "point_observation",
          "templates": ["orbit_circle"],
          "keywords": ["orbit", "circle", "watch", "monitor", "observe", "loiter", "stay near"],
          "confidence_threshold": 0.7
        },
        {
          "intent": "perimeter_patrol",
          "templates": ["perimeter_scan"],
          "keywords": ["patrol", "perimeter", "border", "fence line", "boundary", "check points"],
          "confidence_threshold": 0.7
        },
        {
          "intent": "target_tracking",
          "templates": ["moving_target_follow"],
          "keywords": ["follow", "track", "pursue", "chase", "keep eyes on", "stay with"],
          "confidence_threshold": 0.7
        },
        {
          "intent": "transit",
          "templates": ["perimeter_scan"],
          "keywords": ["go to", "fly to", "move to", "transit", "travel to", "proceed to"],
          "parameters": {
            "waypoint_count": 2
          }
        }
      ]
    },
    "matching_algorithm": {
      "primary": "semantic_similarity",
      "embedding_model": "mission_intent_v2",
      "fallback": "keyword_matching",
      "multi_intent_resolution": "highest_confidence_with_confirmation"
    }
  }
}
```

### 3.2 Parameter Extraction

```json
{
  "llm_mission_understanding": {
    "component": "parameter_extraction",
    "description": "Extract mission parameters from natural language",
    "extraction_rules": {
      "location": {
        "entity_types": ["GPE", "LOC", "FACILITY"],
        "patterns": [
          "at {location}",
          "near {location}",
          "around {location}",
          "in {location}",
          "by {location}"
        ],
        "resolution": "geocoding_service",
        "confidence_threshold": 0.8
      },
      "coordinates": {
        "patterns": [
          "{lat}, {lon}",
          "coordinates {lat} {lon}",
          "lat {lat} lon {lon}",
          "{lat}N {lon}W"
        ],
        "validation": "coordinate_bounds_check"
      },
      "altitude": {
        "entity_types": ["QUANTITY"],
        "patterns": [
          "at {value} {unit}",
          "{value} {unit} altitude",
          "{value} {unit} high",
          "{value} {unit} AGL",
          "{value} {unit} AMSL"
        ],
        "units": {
          "feet": 0.3048,
          "meters": 1.0,
          "ft": 0.3048,
          "m": 1.0
        },
        "default_unit": "meters",
        "validation_range": [0, 400]
      },
      "speed": {
        "patterns": [
          "at {value} {unit}",
          "{value} {unit} speed",
          "{value} {unit}"
        ],
        "units": {
          "knots": 0.514444,
          "mph": 0.44704,
          "m/s": 1.0,
          "kph": 0.277778
        },
        "default_unit": "m/s",
        "validation_range": [0, 50]
      },
      "distance": {
        "patterns": [
          "{value} {unit} radius",
          "{value} {unit} wide",
          "{value} {unit} spacing"
        ],
        "units": {
          "feet": 0.3048,
          "meters": 1.0,
          "miles": 1609.34,
          "kilometers": 1000
        },
        "default_unit": "meters"
      },
      "duration": {
        "patterns": [
          "for {value} {unit}",
          "{value} {unit} duration",
          "{value} {unit} loiter"
        ],
        "units": {
          "minutes": 60,
          "hours": 3600,
          "seconds": 1
        },
        "default_unit": "seconds"
      },
      "time": {
        "entity_types": ["TIME"],
        "patterns": [
          "at {time}",
          "starting at {time}",
          "beginning {time}"
        ],
        "resolution": "time_parser"
      }
    },
    "extraction_confidence": {
      "high": 0.9,
      "medium": 0.7,
      "low": 0.5
    }
  }
}
```

### 3.3 Ambiguity Resolution

```json
{
  "llm_mission_understanding": {
    "component": "ambiguity_resolution",
    "description": "Handle ambiguous or incomplete mission requests",
    "ambiguity_types": {
      "location_ambiguity": {
        "detection": "multiple_geocoding_results OR low_confidence",
        "resolution_strategies": [
          "ask_user_clarification",
          "use_most_likely_with_confirmation",
          "use_current_position_if_near"
        ]
      },
      "template_ambiguity": {
        "detection": "multiple_templates_above_threshold",
        "resolution_strategies": [
          "ask_user_to_choose",
          "use_default_for_intent",
          "present_options_for_selection"
        ]
      },
      "parameter_missing": {
        "detection": "required_parameter_null",
        "resolution_strategies": [
          "use_default_value",
          "infer_from_context",
          "ask_user_for_value",
          "reject_mission"
        ],
        "default_priorities": {
          "safety_critical": "ask_user",
          "optional": "use_default"
        }
      },
      "conflicting_parameters": {
        "detection": "parameter_validation_fail",
        "resolution_strategies": [
          "prefer_safety_limit",
          "ask_user_preference",
          "reject_with_explanation"
        ]
      },
      "temporal_ambiguity": {
        "detection": "unclear_timing_reference",
        "examples": ["soon", "later", "when ready"],
        "resolution_strategies": [
          "ask_specific_time",
          "default_to_immediate",
          "offer_time_options"
        ]
      }
    },
    "clarification_dialogue": {
      "max_rounds": 3,
      "template": {
        "acknowledge": "I understand you want to {intent}",
        "question": "Could you clarify: {specific_question}",
        "suggestion": "Did you mean: {interpretation}?",
        "options": "Please choose: {numbered_options}"
      }
    }
  }
}
```

### 3.4 Confirmation Requirements

```json
{
  "llm_mission_understanding": {
    "component": "confirmation_requirements",
    "description": "Determine when explicit confirmation is required",
    "confirmation_levels": {
      "none": {
        "conditions": [
          "routine_mission",
          "low_risk_area",
          "parameters_within_normal",
          "operator_history > 10 missions"
        ],
        "action": "execute_immediately"
      },
      "summary": {
        "conditions": [
          "new_area",
          "moderate_risk",
          "parameters_changed_from_default",
          "duration > 30 minutes"
        ],
        "action": "show_summary_and_execute",
        "timeout_seconds": 10
      },
      "explicit": {
        "conditions": [
          "high_risk_area",
          "near_airspace_boundary",
          "parameters_near_limits",
          "modified_default_safety",
          "new_operator"
        ],
        "action": "require_explicit_approval",
        "timeout_seconds": null,
        "requires_acknowledgment": true
      },
      "voice": {
        "conditions": [
          "voice_command_uncertain",
          "noisy_environment_detected",
          "wake_word_unclear"
        ],
        "action": "require_voice_confirmation",
        "confirmation_phrase": "confirm mission start"
      }
    },
    "mission_summary_template": {
      "header": "Mission Summary",
      "fields": [
        "template_name",
        "estimated_duration",
        "max_distance",
        "max_altitude",
        "area_coverage",
        "risk_level",
        "abort_conditions"
      ],
      "safety_warnings": {
        "if_near_boundary": "Warning: Mission approaches airspace boundary",
        "if_weather_marginal": "Warning: Weather conditions are marginal",
        "if_battery_marginal": "Warning: Battery level is below 50%"
      }
    }
  }
}
```

---

## 4. Dynamic Replanning

### 4.1 Mid-Mission Target Updates

```json
{
  "dynamic_replanning": {
    "component": "target_update",
    "description": "Update mission targets during execution",
    "update_types": {
      "target_reposition": {
        "trigger": "operator_command OR intelligence_update",
        "constraints": [
          "new_target_within_range",
          "fuel_sufficient",
          "airspace_clear"
        ],
        "replan_strategy": "insert_new_waypoints",
        "resume_options": [
          "continue_from_current",
          "restart_pattern",
          "abandon_and_proceed"
        ]
      },
      "target_acquired": {
        "trigger": "visual_detection OR sensor_contact",
        "automatic_actions": [
          "switch_to_tracking_mode",
          "reduce_search_area",
          "notify_operator"
        ],
        "confirmation_required": false
      },
      "target_lost": {
        "trigger": "tracking_loss > timeout",
        "automatic_actions": [
          "initiate_search_pattern",
          "expand_search_radius",
          "predict_last_known"
        ],
        "recovery_options": [
          "search_last_known",
          "return_to_search_area",
          "abort_and_rtb"
        ]
      },
      "multiple_targets": {
        "trigger": "additional_contacts_detected",
        "strategy": "priority_ranking",
        "factors": [
          "target_confidence",
          "target_priority",
          "proximity_to_current",
          "mission_relevance"
        ]
      }
    },
    "update_protocol": {
      "priority_interrupt": true,
      "operator_notification": true,
      "validation_required": "for_major_changes",
      "rollback_capability": true
    }
  }
}
```

### 4.2 Weather-Based Adjustments

```json
{
  "dynamic_replanning": {
    "component": "weather_adjustments",
    "description": "Adapt mission to changing weather conditions",
    "weather_parameters": {
      "wind_speed": {
        "thresholds": {
          "caution": 10,
          "warning": 15,
          "abort": 20
        },
        "unit": "m/s"
      },
      "wind_gust": {
        "thresholds": {
          "caution": 15,
          "warning": 20,
          "abort": 25
        }
      },
      "visibility": {
        "thresholds": {
          "caution": 5000,
          "warning": 2000,
          "abort": 1000
        },
        "unit": "meters"
      },
      "precipitation": {
        "thresholds": {
          "caution": "light",
          "warning": "moderate",
          "abort": "heavy"
        }
      },
      "temperature": {
        "operating_range": [-10, 45],
        "unit": "celsius"
      },
      "icing_conditions": {
        "thresholds": {
          "caution": "possible",
          "abort": "likely"
        }
      }
    },
    "adjustment_strategies": {
      "altitude_change": {
        "trigger": "wind_shear OR turbulence",
        "action": "seek_optimal_altitude",
        "constraints": "within_altitude_bands"
      },
      "speed_reduction": {
        "trigger": "wind_speed > caution",
        "action": "reduce_cruise_speed",
        "factor": 0.8
      },
      "pattern_modification": {
        "trigger": "visibility < warning",
        "actions": [
          "reduce_search_radius",
          "increase_overlap",
          "lower_altitude"
        ]
      },
      "mission_abort": {
        "trigger": "weather_threshold_exceeded",
        "action": "initiate_return_home",
        "escalation_time": 60
      },
      "landing_site_change": {
        "trigger": "home_site_weather_unsuitable",
        "action": "select_alternate_landing",
        "criteria": ["wind_alignment", "surface_condition", "clear_approach"]
      }
    },
    "forecast_integration": {
      "lookahead_minutes": 30,
      "update_frequency": 300,
      "predictive_rerouting": true
    }
  }
}
```

### 4.3 Battery-Aware Shortening

```json
{
  "dynamic_replanning": {
    "component": "battery_optimization",
    "description": "Optimize mission based on remaining battery capacity",
    "battery_model": {
      "reserve_percentage": 25,
      "emergency_reserve": 15,
      "landing_consumption": 5,
      "return_consumption_factor": 1.2,
      "degradation_model": "temperature_compensated"
    },
    "shortening_strategies": {
      "search_pattern_reduction": {
        "trigger": "projected_battery < mission_requirement * 1.3",
        "actions": [
          "reduce_track_spacing (increase overlap)",
          "skip_alternate_tracks",
          "reduce_search_area_radius",
          "prioritize_high_value_zones"
        ],
        "priority_field": "coverage_priority_map"
      },
      "waypoint_elimination": {
        "trigger": "waypoint_count > optimal_for_battery",
        "algorithm": "significance_scoring",
        "factors": [
          "waypoint_criticality",
          "information_value",
          "proximity_to_others"
        ]
      },
      "speed_optimization": {
        "trigger": "always_active",
        "model": "energy_speed_curve",
        "optimal_range": [12, 18],
        "unit": "m/s"
      },
      "altitude_optimization": {
        "trigger": "terrain_permits",
        "action": "minimize_altitude_agl",
        "minimum": "safety_clearance + 10m"
      }
    },
    "rtb_decision": {
      "trigger_point": "reserve_percentage + return_consumption",
      "dynamic_calculation": {
        "distance_to_home": "current_position_to_home",
        "headwind_factor": "current_wind_component",
        "altitude_change_cost": "descent_vs_climb"
      },
      "early_rtb_conditions": [
        "battery_degradation_accelerating",
        "weather_deteriorating",
        "mission_objectives_partially_met"
      ]
    }
  }
}
```

### 4.4 Obstacle-Based Rerouting (Stage 3)

```json
{
  "dynamic_replanning": {
    "component": "obstacle_avoidance",
    "description": "Real-time obstacle detection and path replanning",
    "sensors": {
      "primary": ["lidar", "stereo_camera"],
      "secondary": ["radar", "ultrasonic"],
      "range_requirements": {
        "detection": 100,
        "classification": 50,
        "avoidance_decision": 30,
        "emergency_maneuver": 15
      },
      "unit": "meters"
    },
    "obstacle_classes": {
      "static": {
        "examples": ["buildings", "towers", "trees", "terrain"],
        "data_source": "mapped_obstacles",
        "update_frequency": "mission_planning"
      },
      "dynamic_predictable": {
        "examples": ["power_lines", "antenna guy wires"],
        "avoidance_buffer": 20
      },
      "dynamic_moving": {
        "examples": ["other_aircraft", "birds", "drones"],
        "detection_required": true,
        "reactive_avoidance": true
      },
      "pop_up": {
        "examples": ["balloons", "kites", "emerging_obstacles"],
        "response_time": "< 2 seconds"
      }
    },
    "rerouting_algorithms": {
      "local_avoidance": {
        "scope": "immediate_path",
        "algorithm": "potential_fields",
        "replan_horizon": 50,
        "unit": "meters"
      },
      "waypoint_replan": {
        "scope": "segment_to_segment",
        "algorithm": "rrt_star",
        "constraints": [
          "mission_objectives",
          "fuel_budget",
          "time_constraints"
        ]
      },
      "global_replan": {
        "scope": "entire_mission",
        "trigger": "major_obstacle_blocking",
        "algorithm": "hybrid_a_star",
        "fallback": "abort_mission"
      }
    },
    "avoidance_maneuvers": {
      "lateral": {
        "preferred": true,
        "max_deviation": 100,
        "clearance_required": 20
      },
      "vertical": {
        "options": ["climb", "descend"],
        "clearance_required": 30,
        "altitude_band_constraints": true
      },
      "speed_change": {
        "options": ["slow", "hover"],
        "clearance_required": 15
      },
      "emergency": {
        "trigger": "collision_imminent",
        "action": "maximum_performance_maneuver",
        "clearance_priority": "safety_over_mission"
      }
    },
    "map_updates": {
      "dynamic_obstacles": {
        "log_detected": true,
        "share_to_fleet": true,
        "update_basemap": "post_mission"
      }
    }
  }
}
```

---

## 5. Complete Mission Templates

### 5.1 Search and Rescue Mission

```json
{
  "mission_template": {
    "id": "sar_standard",
    "name": "Search and Rescue - Standard",
    "phases": [
      {
        "name": "transit_to_search_area",
        "template": "perimeter_scan",
        "parameters": {
          "waypoints": [
            {"position": "home", "altitude": 50, "speed": 20},
            {"position": "search_area_entry", "altitude": 80, "speed": 18}
          ],
          "path_type": "direct"
        }
      },
      {
        "name": "primary_search",
        "template": "search_lawnmower",
        "parameters": {
          "track_spacing": 50,
          "altitude": 80,
          "speed": 15,
          "overlap": 25,
          "camera_action": "continuous_record"
        },
        "abort_conditions": ["target_found", "low_battery"]
      },
      {
        "name": "target_confirmation",
        "template": "orbit_circle",
        "parameters": {
          "radius": 75,
          "altitude": 60,
          "loops": 2,
          "camera_target": "center"
        },
        "conditional": "target_detected"
      },
      {
        "name": "return_home",
        "template": "perimeter_scan",
        "parameters": {
          "waypoints": [
            {"position": "home", "altitude": 60, "speed": 18}
          ]
        }
      }
    ],
    "safety_envelopes": [
      "max_distance_from_home",
      "altitude_bands",
      "mission_phase_timeouts"
    ],
    "dynamic_replanning": [
      "target_update",
      "weather_adjustments",
      "battery_optimization"
    ]
  }
}
```

### 5.2 Infrastructure Inspection Mission

```json
{
  "mission_template": {
    "id": "infrastructure_inspection",
    "name": "Infrastructure Inspection",
    "phases": [
      {
        "name": "approach",
        "template": "perimeter_scan",
        "parameters": {
          "waypoints": [
            {"position": "inspection_site_approach", "altitude": 100, "speed": 15}
          ]
        }
      },
      {
        "name": "perimeter_survey",
        "template": "perimeter_scan",
        "parameters": {
          "waypoints": "generate_from_structure_bounds",
          "altitude": 80,
          "hover_time": 5,
          "camera_action": "capture"
        }
      },
      {
        "name": "detailed_orbit",
        "template": "orbit_circle",
        "parameters": {
          "center": "structure_center",
          "radius": 40,
          "altitude": 60,
          "loops": 3,
          "camera_target": "center"
        }
      },
      {
        "name": "top_down_scan",
        "template": "orbit_circle",
        "parameters": {
          "center": "structure_center",
          "radius": 25,
          "altitude": 40,
          "loops": 1,
          "camera_pitch": 90
        }
      }
    ],
    "obstacle_avoidance": {
      "structure_buffer": 15,
      "sensor_required": true
    }
  }
}
```

### 5.3 Perimeter Patrol Mission

```json
{
  "mission_template": {
    "id": "perimeter_patrol",
    "name": "Perimeter Patrol",
    "phases": [
      {
        "name": "patrol_loop",
        "template": "perimeter_scan",
        "parameters": {
          "waypoints": "defined_perimeter_points",
          "loop": true,
          "loop_count": 3,
          "altitude": 75,
          "speed": 12,
          "hover_time": 10,
          "camera_action": "pan_scan"
        }
      }
    ],
    "checkpoints": {
      "interval_minutes": 5,
      "action": "operator_check_in",
      "timeout_action": "return_home"
    }
  }
}
```

### 5.4 Convoy Escort Mission

```json
{
  "mission_template": {
    "id": "convoy_escort",
    "name": "Convoy Escort",
    "phases": [
      {
        "name": "acquire_convoy",
        "template": "perimeter_scan",
        "parameters": {
          "waypoints": [
            {"position": "convoy_start_point", "altitude": 100}
          ]
        }
      },
      {
        "name": "escort_trail",
        "template": "moving_target_follow",
        "parameters": {
          "follow_mode": "trail",
          "follow_distance": 150,
          "follow_altitude": 100,
          "speed_matching": true,
          "speed_buffer": 5,
          "max_speed": 25
        }
      },
      {
        "name": "route_scan",
        "template": "moving_target_follow",
        "parameters": {
          "follow_mode": "lead",
          "follow_distance": 200,
          "prediction_horizon": 10
        },
        "conditional": "route_clearance_required"
      }
    ],
    "handoff_protocol": {
      "relief_uav_arrival": "orbit_until_replaced",
      "transfer_coordination": "operator_controlled"
    }
  }
}
```

---

## 6. Implementation Guidelines

### Template Selection Flow

1. **Intent Classification**: Parse natural language to determine mission intent
2. **Template Matching**: Map intent to candidate templates
3. **Parameter Extraction**: Extract location, altitude, speed, duration from input
4. **Validation**: Check parameters against safety envelopes
5. **Ambiguity Resolution**: Clarify any uncertain parameters
6. **Confirmation**: Present summary based on confirmation level
7. **Execution**: Begin mission with dynamic replanning enabled

### Safety Hierarchy

1. **Immediate abort conditions** take precedence over all mission objectives
2. **Geofence boundaries** cannot be overridden without operator authorization
3. **Altitude bands** must be respected per flight phase
4. **Battery reserves** trigger automatic RTB when threshold reached
5. **Weather limits** enforce mission modification or abort

### Integration Points

- **Flight Controller**: PX4/ArduPilot mission protocol
- **Ground Control Station**: Mission upload and monitoring
- **LLM Service**: Natural language processing and intent classification
- **Weather Service**: Real-time conditions and forecasts
- **Geocoding Service**: Location resolution
- **Obstacle Database**: Static and dynamic obstacle information

---

## Appendix: JSON Schema for Mission Templates

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Mission Template",
  "type": "object",
  "required": ["template_id", "name", "parameters"],
  "properties": {
    "template_id": {"type": "string"},
    "name": {"type": "string"},
    "description": {"type": "string"},
    "parameters": {
      "type": "object",
      "additionalProperties": true
    },
    "waypoint_generation": {
      "type": "object",
      "properties": {
        "algorithm": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}}
      }
    },
    "validation_rules": {"type": "object"},
    "estimated_metrics": {"type": "object"},
    "safety_requirements": {"type": "array", "items": {"type": "string"}}
  }
}
```

---

*Document Version: 1.0*
*Last Updated: 2024*
*Classification: Operational*
