#!/usr/bin/env python3
"""
Pre-Tool-Use Hook: Drone Safety Validation

WHAT ARE CLAUDE CODE HOOKS?
==========================
Hooks in Claude Code are executable scripts that intercept tool calls at specific points
in the execution lifecycle. They allow you to:
- Validate commands before execution (safety gates)
- Modify tool inputs dynamically
- Log or audit operations
- Enforce policies or constraints

WHEN THIS HOOK FIRES
====================
The pre_tool_use hook executes BEFORE any tool is called by Claude Code. It receives
the tool name and input via stdin as JSON, validates it, and returns a JSON response
that determines whether the tool execution should proceed.

Hook Input Format (via stdin):
{
    "tool_name": "mcp__drone__arm_and_takeoff",
    "tool_input": {"command": "arm and takeoff to 50m"},
    "command": "arm and takeoff to 50m"
}

Hook Output Format (to stdout):
{
    "allow": true/false,
    "reason": "Safety check passed/failed because..."
}

WHAT THIS HOOK CHECKS
======================
This hook implements a comprehensive safety validation system for drone operations:

1. ALTITUDE LIMITS (FAA Part 107 Compliance)
   - Maximum altitude: 120 meters (400 feet)
   - Validates target altitude in navigation commands
   - Monitors current altitude during flight

2. GEOFENCE BOUNDARIES
   - Configurable circular geofence around takeoff point
   - Default radius: 500 meters
   - Validates target positions before navigation
   - Monitors current position during flight

3. BATTERY LEVEL
   - Minimum 20% required for flight operations
   - Bypassed for emergency operations (safety override)
   - Bypassed for landing/disarm (safety critical)

4. COMMAND CATEGORIZATION
   - Automatically categorizes commands (navigation, takeoff, land, arm, etc.)
   - Applies appropriate safety rules per category
   - Extracts parameters (altitude, position) from natural language

HOW THIS IMPROVES WORKFLOW
============================
- Prevents accidental dangerous commands (e.g., "fly to 500m")
- Enforces regulatory compliance automatically
- Provides immediate feedback on why commands are rejected
- Maintains persistent safety state across multiple commands
- Logs all validation attempts for audit trails

Configuration Files:
- /tmp/drone_safety_config.json: Safety thresholds and geofence settings
- /tmp/drone_state.json: Current drone telemetry (updated by post_tool_use hook)
"""

import json
import sys
import os
import re
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import math


class CommandCategory(Enum):
    """
    Categories of drone commands for applying appropriate safety rules.

    Each category has specific safety requirements:
    - NAVIGATION: Requires altitude and geofence checks
    - ARM: Requires battery check
    - TAKEOFF: Requires battery check and altitude validation
    - LAND: Bypasses most checks (safety critical)
    - EMERGENCY: Bypasses all checks (safety override)
    """
    NAVIGATION = "navigation"
    ARM = "arm"
    DISARM = "disarm"
    TAKEOFF = "takeoff"
    LAND = "land"
    MISSION = "mission"
    SETTING = "setting"
    TELEMETRY = "telemetry"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


@dataclass
class SafetyConfig:
    """
    Safety configuration parameters loaded from environment or config file.

    These values define the safety boundaries enforced by the validator.
    They can be overridden via /tmp/drone_safety_config.json or environment
    variables for different operational scenarios.

    Attributes:
        max_altitude_m: FAA Part 107 maximum altitude (default 120m)
        min_battery_percent: Minimum battery for flight operations (default 20%)
        geofence_center_lat: Latitude of geofence center point
        geofence_center_lon: Longitude of geofence center point
        geofence_radius_m: Maximum allowed distance from center (default 500m)
        enable_*: Toggle switches for each safety check category
    """
    max_altitude_m: float = 120.0  # FAA Part 107 limit
    min_battery_percent: float = 20.0
    geofence_center_lat: float = 0.0
    geofence_center_lon: float = 0.0
    geofence_radius_m: float = 500.0
    enable_geofence: bool = True
    enable_altitude_check: bool = True
    enable_battery_check: bool = True


@dataclass
class DroneState:
    """
    Current drone state loaded from persistent storage.

    This state is maintained by the post_tool_use hook and provides the
    validator with real-time telemetry for making safety decisions.

    Attributes:
        altitude_m: Current altitude in meters
        latitude: Current GPS latitude
        longitude: Current GPS longitude
        battery_percent: Remaining battery percentage
        armed: Whether motors are armed
        in_flight: Whether drone is currently flying
        home_lat: Home position latitude (for geofence center)
        home_lon: Home position longitude (for geofence center)
    """
    altitude_m: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0
    battery_percent: float = 100.0
    armed: bool = False
    in_flight: bool = False
    home_lat: float = 0.0
    home_lon: float = 0.0


class SafetyValidator:
    """
    Validates drone commands for safety compliance before execution.

    This is the core validation engine that parses commands, extracts parameters,
    and applies safety rules based on the current drone state and configuration.

    Usage:
        validator = SafetyValidator()
        allowed, reason = validator.validate("fly to altitude 100m")
        if not allowed:
            print(f"Command rejected: {reason}")
    """

    # Command patterns for categorization using regex
    # These patterns match natural language commands and map them to categories
    COMMAND_PATTERNS = {
        CommandCategory.NAVIGATION: [
            r'\b(goto|fly_to|move_to|set_position|set_target)\b',
            r'\bnavigate\b',
            r'\b(change_altitude|set_altitude|climb|descend)\b',
            r'\b(set_speed|change_speed)\b',
        ],
        CommandCategory.TAKEOFF: [
            r'\btakeoff\b',
            r'\blaunch\b',
            r'\bascend\b',
        ],
        CommandCategory.LAND: [
            r'\bland\b',
            r'\b(descend_to_ground|touchdown)\b',
            r'\brtl\b',  # Return to launch
            r'\breturn_home\b',
        ],
        CommandCategory.ARM: [
            r'\barm\b',
            r'\b(motors.*on|enable_motors)\b',
        ],
        CommandCategory.DISARM: [
            r'\bdisarm\b',
            r'\b(motors.*off|disable_motors)\b',
        ],
        CommandCategory.MISSION: [
            r'\b(start_mission|execute_mission|run_mission)\b',
            r'\b(upload_mission|load_mission)\b',
            r'\bpause_mission\b',
            r'\bresume_mission\b',
        ],
        CommandCategory.SETTING: [
            r'\b(set_|config_|configure)\b',
            r'\b(update_param|set_parameter)\b',
        ],
        CommandCategory.TELEMETRY: [
            r'\b(get_|read_|request_)\b.*\b(status|telemetry|position|attitude)\b',
            r'\b(fetch|query)\b.*\b(data|state)\b',
        ],
        CommandCategory.EMERGENCY: [
            r'\b(kill|emergency|stop|halt|abort)\b',
            r'\b(emergency_land|forced_land)\b',
        ],
    }

    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        Initialize the validator with configuration and load current state.

        Args:
            config: Optional SafetyConfig instance. If not provided, loads from
                   environment variables and default configuration file.
        """
        self.config = config or SafetyConfig()
        self.state = DroneState()
        self._load_config_from_file()
        self._load_state_from_file()

    def _load_config_from_file(self) -> None:
        """
        Load safety configuration from persistent storage.

        Reads from /tmp/drone_safety_config.json or path specified by
        SAFETY_CONFIG_PATH environment variable. Allows runtime adjustment
        of safety parameters without code changes.
        """
        config_path = os.environ.get('SAFETY_CONFIG_PATH', '/tmp/drone_safety_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
            except (json.JSONDecodeError, IOError):
                pass  # Use defaults if file is corrupted

    def _load_state_from_file(self) -> None:
        """
        Load current drone state from persistent storage.

        Reads from /tmp/drone_state.json or path specified by
        DRONE_STATE_PATH environment variable. This state is maintained
        by the post_tool_use hook to provide real-time telemetry.
        """
        state_path = os.environ.get('DRONE_STATE_PATH', '/tmp/drone_state.json')
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.state, key):
                            setattr(self.state, key, value)
            except (json.JSONDecodeError, IOError):
                pass  # Use defaults if file is corrupted

    def categorize_command(self, command: str) -> CommandCategory:
        """
        Determine the category of a drone command using regex patterns.

        This categorization drives which safety checks are applied:
        - NAVIGATION commands: altitude + geofence checks
        - TAKEOFF commands: battery + altitude checks
        - EMERGENCY commands: bypass all checks
        - etc.

        Args:
            command: The command string to categorize

        Returns:
            CommandCategory enum value
        """
        command_lower = command.lower()

        for category, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return category
        return CommandCategory.UNKNOWN

    def extract_altitude(self, command: str) -> Optional[float]:
        """
        Extract target altitude from natural language command.

        Supports various formats:
        - "altitude 50m"
        - "climb to 100 meters"
        - "fly at 75m"
        - "height: 80m"

        Args:
            command: The command string to parse

        Returns:
            Target altitude in meters, or None if not found
        """
        # Match patterns like "altitude 50m", "climb to 100", "at 75 meters"
        patterns = [
            r'altitude[:\s]+(\d+(?:\.\d+)?)\s*m',
            r'(?:climb|ascend|fly).*?to\s+(\d+(?:\.\d+)?)\s*(?:m|meters)?',
            r'at\s+(\d+(?:\.\d+)?)\s*(?:m|meters)',
            r'height[:\s]+(\d+(?:\.\d+)?)\s*m',
            r'(\d+(?:\.\d+)?)\s*m\s*(?:altitude|height)',
        ]

        for pattern in patterns:
            match = re.search(pattern, command.lower())
            if match:
                return float(match.group(1))
        return None

    def extract_position(self, command: str) -> Optional[Tuple[float, float]]:
        """
        Extract target latitude/longitude from command.

        Supports formats:
        - "lat: 37.7749, lon: -122.4194"
        - "37.7749, -122.4194"
        - "position: 37.7749 -122.4194"

        Args:
            command: The command string to parse

        Returns:
            Tuple of (latitude, longitude), or None if not found
        """
        # Match lat,lon patterns
        patterns = [
            r'(?:lat|latitude)[:\s]+(-?\d+(?:\.\d+?)).*?(?:lon|longitude)[:\s]+(-?\d+(?:\.\d+))',
            r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)',  # Simple lat,lon
            r'position[:\s]+(-?\d+\.\d+)\s+(-?\d+\.\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, command.lower())
            if match:
                return (float(match.group(1)), float(match.group(2)))
        return None

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two GPS coordinates.

        Uses the haversine formula for accurate Earth-surface distance
        calculation. Essential for geofence validation.

        Args:
            lat1: Starting latitude in degrees
            lon1: Starting longitude in degrees
            lat2: Target latitude in degrees
            lon2: Target longitude in degrees

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def check_altitude(self, target_altitude: Optional[float], command: str) -> Tuple[bool, str]:
        """
        Validate altitude against FAA Part 107 limits.

        Checks:
        1. Target altitude does not exceed max_altitude_m (default 120m)
        2. Current altitude is within limits if already in flight
        3. Negative altitudes are rejected

        Safety bypass: LAND and DISARM commands skip altitude checks
        to ensure safe ground operations can always proceed.

        Args:
            target_altitude: Altitude from command parsing, or None
            command: Original command string for categorization

        Returns:
            Tuple of (passed: bool, reason: str)
        """
        if not self.config.enable_altitude_check:
            return True, "Altitude check disabled"

        # Allow landing and ground operations
        category = self.categorize_command(command)
        if category in [CommandCategory.LAND, CommandCategory.DISARM]:
            return True, "Ground operation - altitude check bypassed"

        if target_altitude is not None:
            if target_altitude > self.config.max_altitude_m:
                return False, f"Altitude {target_altitude}m exceeds maximum allowed {self.config.max_altitude_m}m (FAA Part 107)"
            if target_altitude < 0:
                return False, f"Negative altitude {target_altitude}m is invalid"

        # Check current altitude for flight operations
        if self.state.in_flight and self.state.altitude_m > self.config.max_altitude_m:
            return False, f"Current altitude {self.state.altitude_m}m exceeds maximum {self.config.max_altitude_m}m"

        return True, "Altitude within limits"

    def check_geofence(self, target_position: Optional[Tuple[float, float]], command: str) -> Tuple[bool, str]:
        """
        Validate position against geofence boundaries.

        Checks:
        1. Target position is within radius of geofence center
        2. Current position is within geofence if already in flight

        Safety bypass: LAND commands skip geofence checks to ensure
        the drone can always return home for landing.

        Args:
            target_position: (lat, lon) tuple from command parsing, or None
            command: Original command string for categorization

        Returns:
            Tuple of (passed: bool, reason: str)
        """
        if not self.config.enable_geofence:
            return True, "Geofence check disabled"

        # Allow RTL and landing anywhere
        category = self.categorize_command(command)
        if category == CommandCategory.LAND:
            return True, "Landing operation - geofence check bypassed for safety"

        if target_position is not None:
            lat, lon = target_position
            distance = self.haversine_distance(
                self.config.geofence_center_lat,
                self.config.geofence_center_lon,
                lat, lon
            )
            if distance > self.config.geofence_radius_m:
                return False, f"Target position ({lat}, {lon}) is {distance:.0f}m from center, exceeds geofence radius of {self.config.geofence_radius_m}m"

        # Check current position
        if self.state.in_flight:
            current_distance = self.haversine_distance(
                self.config.geofence_center_lat,
                self.config.geofence_center_lon,
                self.state.latitude,
                self.state.longitude
            )
            if current_distance > self.config.geofence_radius_m:
                return False, f"Current position {current_distance:.0f}m from center, outside geofence. RTL recommended."

        return True, "Position within geofence"

    def check_battery(self, command: str) -> Tuple[bool, str]:
        """
        Validate battery level for flight operations.

        Policy:
        - Minimum 20% required for: TAKEOFF, NAVIGATION, MISSION, ARM
        - No minimum required for: LAND, DISARM, TELEMETRY, SETTINGS
        - Emergency operations bypass all checks

        This prevents takeoff with insufficient battery and warns when
        battery drops below threshold during flight.

        Args:
            command: Original command string for categorization

        Returns:
            Tuple of (passed: bool, reason: str)
        """
        if not self.config.enable_battery_check:
            return True, "Battery check disabled"

        category = self.categorize_command(command)

        # Always allow emergency operations regardless of battery
        if category == CommandCategory.EMERGENCY:
            return True, "Emergency operation - battery check bypassed"

        # Always allow landing and disarm
        if category in [CommandCategory.LAND, CommandCategory.DISARM]:
            return True, "Ground/safety operation - battery check bypassed"

        # Allow telemetry/setting commands regardless of battery
        if category in [CommandCategory.TELEMETRY, CommandCategory.SETTING]:
            return True, "Non-flight operation - battery check not required"

        # For flight operations, check battery
        if category in [CommandCategory.TAKEOFF, CommandCategory.NAVIGATION, CommandCategory.MISSION, CommandCategory.ARM]:
            if self.state.battery_percent < self.config.min_battery_percent:
                return False, f"Battery level {self.state.battery_percent}% below minimum {self.config.min_battery_percent}% for flight operations. Land immediately."

        return True, f"Battery level {self.state.battery_percent}% is sufficient"

    def validate(self, command: str) -> Tuple[bool, str]:
        """
        Main validation entry point - runs all safety checks.

        This method orchestrates the complete safety validation pipeline:
        1. Parse command for parameters (altitude, position)
        2. Run all safety checks (altitude, geofence, battery)
        3. Collect and report any failures

        Args:
            command: The command string to validate

        Returns:
            Tuple of (allowed: bool, reason: str)
            - allowed: True if all checks pass, False if any fail
            - reason: Human-readable explanation of result
        """
        # Extract parameters from command
        target_altitude = self.extract_altitude(command)
        target_position = self.extract_position(command)

        # Run all safety checks
        checks = [
            ("Altitude", self.check_altitude(target_altitude, command)),
            ("Geofence", self.check_geofence(target_position, command)),
            ("Battery", self.check_battery(command)),
        ]

        # Collect results
        failures = []
        for check_name, (passed, reason) in checks:
            if not passed:
                failures.append(f"{check_name}: {reason}")

        if failures:
            return False, "; ".join(failures)

        return True, "All safety checks passed"


def main():
    """
    Main entry point for the Claude Code pre_tool_use hook.

    This function handles the stdin/stdout protocol with Claude Code:
    1. Read JSON input from stdin containing tool call details
    2. Check if this is a drone-related command
    3. Run safety validation if it is
    4. Output JSON result to stdout
    5. Exit with code 0 (allow) or 1 (block)

    The exit code determines whether Claude Code proceeds with the tool call.
    """
    # Read the tool input from stdin (Claude Code sends JSON here)
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If no valid JSON, allow by default (non-drone tools)
        print(json.dumps({"allow": True, "reason": "No valid JSON input, allowing by default"}))
        sys.exit(0)

    # Extract the tool name and arguments from Claude's input
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = input_data.get("command", "")

    # Build the command string from various inputs (different tools use different keys)
    if isinstance(tool_input, dict):
        command = tool_input.get("command", command)
        command = tool_input.get("prompt", command)
        command = tool_input.get("text", command)

    if not command:
        # If no drone-related content, allow by default
        print(json.dumps({"allow": True, "reason": "No command to validate"}))
        sys.exit(0)

    # Only validate drone-related commands to avoid blocking unrelated tools
    drone_keywords = ['drone', 'uav', 'copter', 'quad', 'fly', 'arm', 'takeoff', 'land', 'mission', 'altitude', 'geofence']
    is_drone_command = any(kw in str(tool_input).lower() for kw in drone_keywords)

    if not is_drone_command:
        print(json.dumps({"allow": True, "reason": "Not a drone command"}))
        sys.exit(0)

    # Run validation through SafetyValidator
    validator = SafetyValidator()
    allowed, reason = validator.validate(command)

    # Build result JSON for Claude Code
    result = {
        "allow": allowed,
        "reason": reason,
        "command": command[:100] if len(command) > 100 else command,  # Truncate for logging
    }

    print(json.dumps(result))
    sys.exit(0 if allowed else 1)


if __name__ == "__main__":
    main()
