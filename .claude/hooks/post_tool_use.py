#!/usr/bin/env python3
"""
Post-Tool-Use Hook: Drone Telemetry Logger

Logs telemetry and updates safety state after drone commands are executed.
Tracks:
- All drone command executions
- Flight state changes
- Safety state updates
- Command success/failure

Writes to: /tmp/drone_telemetry.log and /tmp/drone_state.json
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import re


@dataclass
class TelemetryEntry:
    """Single telemetry log entry."""
    timestamp: str
    tool_name: str
    command: str
    result: str
    success: bool
    altitude_m: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    battery_percent: Optional[float] = None
    armed: Optional[bool] = None
    in_flight: Optional[bool] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class TelemetryLogger:
    """Logs drone telemetry and updates state."""

    TELEMETRY_LOG_PATH = "/tmp/drone_telemetry.log"
    STATE_FILE_PATH = "/tmp/drone_state.json"

    # Patterns to extract telemetry from command results
    ALTITUDE_PATTERN = r'altitude[:\s]+(\d+(?:\.\d+)?)\s*m'
    POSITION_PATTERN = r'(?:lat|position)[:\s]+(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)'
    BATTERY_PATTERN = r'battery[:\s]+(\d+(?:\.\d+)?)\s*%'

    def __init__(self):
        """Initialize the telemetry logger."""
        self._ensure_log_file()
        self.current_state = self._load_state()

    def _ensure_log_file(self) -> None:
        """Ensure log file exists with header."""
        if not os.path.exists(self.TELEMETRY_LOG_PATH):
            with open(self.TELEMETRY_LOG_PATH, 'w') as f:
                f.write("# Drone Telemetry Log\n")
                f.write("# Format: JSON entries, one per line\n")
                f.write(f"# Created: {datetime.utcnow().isoformat()}Z\n")

    def _load_state(self) -> Dict[str, Any]:
        """Load current drone state from file."""
        if os.path.exists(self.STATE_FILE_PATH):
            try:
                with open(self.STATE_FILE_PATH, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "altitude_m": 0.0,
            "latitude": 0.0,
            "longitude": 0.0,
            "battery_percent": 100.0,
            "armed": False,
            "in_flight": False,
            "home_lat": 0.0,
            "home_lon": 0.0,
            "last_command": None,
            "last_command_time": None,
            "total_flight_time_s": 0,
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
        }

    def _save_state(self) -> None:
        """Save current drone state to file."""
        self.current_state["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(self.STATE_FILE_PATH, 'w') as f:
            json.dump(self.current_state, f, indent=2)

    def _extract_telemetry(self, text: str) -> Dict[str, Any]:
        """Extract telemetry values from text."""
        telemetry = {}

        # Extract altitude
        alt_match = re.search(self.ALTITUDE_PATTERN, text.lower())
        if alt_match:
            telemetry["altitude_m"] = float(alt_match.group(1))

        # Extract position
        pos_match = re.search(self.POSITION_PATTERN, text.lower())
        if pos_match:
            telemetry["latitude"] = float(pos_match.group(1))
            telemetry["longitude"] = float(pos_match.group(2))

        # Extract battery
        bat_match = re.search(self.BATTERY_PATTERN, text.lower())
        if bat_match:
            telemetry["battery_percent"] = float(bat_match.group(1))

        return telemetry

    def _categorize_command(self, command: str) -> str:
        """Categorize the command type."""
        command_lower = command.lower()

        if any(kw in command_lower for kw in ['takeoff', 'launch', 'ascend']):
            return "takeoff"
        elif any(kw in command_lower for kw in ['land', 'touchdown', 'rtl', 'return_home']):
            return "land"
        elif any(kw in command_lower for kw in ['arm', 'motors on']):
            return "arm"
        elif any(kw in command_lower for kw in ['disarm', 'motors off']):
            return "disarm"
        elif any(kw in command_lower for kw in ['goto', 'fly_to', 'navigate', 'move_to']):
            return "navigation"
        elif any(kw in command_lower for kw in ['mission', 'waypoint']):
            return "mission"
        elif any(kw in command_lower for kw in ['status', 'telemetry', 'get_', 'read_']):
            return "telemetry"
        else:
            return "other"

    def _update_state_from_command(self, command: str, success: bool) -> None:
        """Update drone state based on command execution."""
        category = self._categorize_command(command)
        self.current_state["total_commands"] += 1

        if success:
            self.current_state["successful_commands"] += 1
        else:
            self.current_state["failed_commands"] += 1

        # Update state based on command category
        if category == "takeoff" and success:
            self.current_state["in_flight"] = True
            self.current_state["armed"] = True
        elif category == "land" and success:
            self.current_state["in_flight"] = False
            self.current_state["altitude_m"] = 0.0
        elif category == "arm" and success:
            self.current_state["armed"] = True
        elif category == "disarm" and success:
            self.current_state["armed"] = False
            self.current_state["in_flight"] = False

        self.current_state["last_command"] = command[:200]
        self.current_state["last_command_time"] = datetime.utcnow().isoformat() + "Z"

    def _update_state_from_result(self, result: str) -> None:
        """Update drone state from command result telemetry."""
        telemetry = self._extract_telemetry(result)

        if "altitude_m" in telemetry:
            self.current_state["altitude_m"] = telemetry["altitude_m"]
        if "latitude" in telemetry:
            self.current_state["latitude"] = telemetry["latitude"]
        if "longitude" in telemetry:
            self.current_state["longitude"] = telemetry["longitude"]
        if "battery_percent" in telemetry:
            self.current_state["battery_percent"] = telemetry["battery_percent"]

    def log(self, entry: TelemetryEntry) -> None:
        """Log a telemetry entry."""
        # Update state
        self._update_state_from_command(entry.command, entry.success)
        if entry.result:
            self._update_state_from_result(entry.result)

        # Merge current state into entry
        entry.altitude_m = entry.altitude_m or self.current_state.get("altitude_m")
        entry.latitude = entry.latitude or self.current_state.get("latitude")
        entry.longitude = entry.longitude or self.current_state.get("longitude")
        entry.battery_percent = entry.battery_percent or self.current_state.get("battery_percent")
        entry.armed = entry.armed if entry.armed is not None else self.current_state.get("armed")
        entry.in_flight = entry.in_flight if entry.in_flight is not None else self.current_state.get("in_flight")

        # Write to log file
        log_entry = asdict(entry)
        with open(self.TELEMETRY_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")

        # Save updated state
        self._save_state()

        # Print summary
        status = "SUCCESS" if entry.success else "FAILED"
        print(f"[TELEMETRY] {status}: {entry.tool_name} - {entry.command[:50]}...")


def main():
    """Main entry point for the hook."""
    # Read the tool input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Extract tool information
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    tool_result = input_data.get("tool_result", {})
    duration_ms = input_data.get("duration_ms")

    # Build command string
    command = ""
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")
        command = tool_input.get("prompt", command)
        command = tool_input.get("text", command)

    # Check if this is a drone-related command
    drone_keywords = ['drone', 'uav', 'copter', 'quad', 'fly', 'arm', 'takeoff', 'land', 'mission', 'altitude', 'geofence']
    is_drone_command = any(kw in str(tool_input).lower() for kw in drone_keywords)

    if not is_drone_command:
        # Not a drone command, skip logging
        sys.exit(0)

    # Determine success
    success = True
    error_message = None

    if isinstance(tool_result, dict):
        success = tool_result.get("success", True)
        error_message = tool_result.get("error") or tool_result.get("message")
    elif isinstance(tool_result, str):
        # Check for error indicators
        error_indicators = ["error", "failed", "exception", "timeout", "rejected"]
        success = not any(ind in tool_result.lower() for ind in error_indicators)
        if not success:
            error_message = tool_result[:200]

    # Build result string
    result = ""
    if isinstance(tool_result, dict):
        result = json.dumps(tool_result)
    elif isinstance(tool_result, str):
        result = tool_result

    # Create and log telemetry entry
    entry = TelemetryEntry(
        timestamp=datetime.utcnow().isoformat() + "Z",
        tool_name=tool_name,
        command=command[:500] if command else "",
        result=result[:1000] if result else "",
        success=success,
        duration_ms=duration_ms,
        error_message=error_message[:500] if error_message else None,
    )

    logger = TelemetryLogger()
    logger.log(entry)

    sys.exit(0)


if __name__ == "__main__":
    main()
