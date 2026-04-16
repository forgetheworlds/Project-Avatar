#!/usr/bin/env python3
"""
Post-Tool-Use Hook: Drone Telemetry Logger

WHAT ARE CLAUDE CODE HOOKS?
==========================
Hooks in Claude Code are executable scripts that run at specific points in the
tool execution lifecycle. Unlike pre_tool_use which validates before execution,
post_tool_use runs AFTER the tool completes, enabling:

- Logging and auditing of all operations
- State tracking across multiple commands
- Result analysis and telemetry extraction
- Success/failure monitoring
- Performance metrics collection

WHEN THIS HOOK FIRES
====================
The post_tool_use hook executes AFTER a tool finishes executing. It receives:
- The original tool input
- The tool result/output
- Execution duration
- Any errors that occurred

This allows the hook to analyze what happened and update persistent state.

Hook Input Format (via stdin):
{
    "tool_name": "mcp__drone__arm_and_takeoff",
    "tool_input": {"command": "arm and takeoff to 50m"},
    "tool_result": {"success": true, "altitude": 50.0},
    "duration_ms": 5234
}

WHAT THIS HOOK DOES
===================
This hook maintains comprehensive telemetry and state tracking for drone operations:

1. COMMAND LOGGING
   - Records every drone command executed
   - Timestamps all operations in UTC
   - Tracks success/failure status
   - Captures execution duration

2. STATE TRACKING
   - Maintains persistent drone state in /tmp/drone_state.json
   - Updates altitude, position, battery from results
   - Tracks flight status (armed, in_flight)
   - Counts total commands and success rate

3. TELEMETRY EXTRACTION
   - Parses command results for embedded telemetry
   - Extracts altitude, position, battery from text output
   - Uses regex patterns to find values in natural language responses

4. FLIGHT STATISTICS
   - Total commands executed
   - Success vs failure counts
   - Last command tracking for debugging
   - Flight time accumulation

HOW THIS IMPROVES WORKFLOW
============================
- Provides audit trail for all drone operations
- Enables the pre_tool_use hook to make informed safety decisions
   (pre_tool_use reads the state file this hook maintains)
- Tracks mission progress and success rates
- Simplifies debugging with complete command history
- Supports analytics on flight patterns and reliability

Output Files:
- /tmp/drone_telemetry.log: Line-delimited JSON of all commands
- /tmp/drone_state.json: Current drone state for cross-command persistence
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
    """
    Single telemetry log entry representing one drone command execution.

    This data class captures all relevant information about a tool call
    for logging and analysis purposes.

    Attributes:
        timestamp: ISO8601 UTC timestamp of command execution
        tool_name: Name of the MCP tool that was called
        command: The command string or prompt that was sent
        result: The tool result/output (truncated for large outputs)
        success: Whether the command succeeded (True) or failed (False)
        altitude_m: Current altitude in meters (from telemetry or result parsing)
        latitude: Current GPS latitude
        longitude: Current GPS longitude
        battery_percent: Current battery percentage
        armed: Whether motors are currently armed
        in_flight: Whether drone is currently in flight
        duration_ms: Command execution time in milliseconds
        error_message: Error details if command failed
    """
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
    """
    Logs drone telemetry and maintains persistent state across commands.

    This class is the core of the post_tool_use hook functionality. It:
    1. Logs each command to a line-delimited JSON file
    2. Updates and saves drone state for cross-command persistence
    3. Parses results to extract telemetry data
    4. Tracks flight statistics and command history

    The state file (/tmp/drone_state.json) is read by the pre_tool_use hook
to make informed safety decisions for subsequent commands.
    """

    # File paths for persistent storage
    TELEMETRY_LOG_PATH = "/tmp/drone_telemetry.log"
    STATE_FILE_PATH = "/tmp/drone_state.json"

    # Regex patterns for extracting telemetry from result text
    # These match common formats found in drone command outputs
    ALTITUDE_PATTERN = r'altitude[:\s]+(\d+(?:\.\d+)?)\s*m'
    POSITION_PATTERN = r'(?:lat|position)[:\s]+(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)'
    BATTERY_PATTERN = r'battery[:\s]+(\d+(?:\.\d+)?)\s*%'

    def __init__(self):
        """
        Initialize the telemetry logger.

        Ensures log file exists with header and loads current state from
        persistent storage. This state will be updated as commands execute.
        """
        self._ensure_log_file()
        self.current_state = self._load_state()

    def _ensure_log_file(self) -> None:
        """
        Ensure the telemetry log file exists with proper header.

        Creates the file if it doesn't exist and writes a comment header
        explaining the format. This makes the log self-documenting.
        """
        if not os.path.exists(self.TELEMETRY_LOG_PATH):
            with open(self.TELEMETRY_LOG_PATH, 'w') as f:
                f.write("# Drone Telemetry Log\n")
                f.write("# Format: JSON entries, one per line\n")
                f.write(f"# Created: {datetime.utcnow().isoformat()}Z\n")

    def _load_state(self) -> Dict[str, Any]:
        """
        Load current drone state from persistent storage.

        Reads from /tmp/drone_state.json and returns default values if
        the file doesn't exist or is corrupted. This state is shared
        across all commands and is read by the pre_tool_use hook.

        Returns:
            Dictionary containing current drone state
        """
        if os.path.exists(self.STATE_FILE_PATH):
            try:
                with open(self.STATE_FILE_PATH, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Return defaults if file is corrupted

        # Default state for a fresh session
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
        """
        Save current drone state to persistent storage.

        Writes to /tmp/drone_state.json with the current timestamp.
        This file is read by the pre_tool_use hook to make safety decisions.
        """
        self.current_state["last_updated"] = datetime.utcnow().isoformat() + "Z"
        with open(self.STATE_FILE_PATH, 'w') as f:
            json.dump(self.current_state, f, indent=2)

    def _extract_telemetry(self, text: str) -> Dict[str, Any]:
        """
        Extract telemetry values from result text using regex patterns.

        Parses the tool result to find embedded telemetry data that might
        be present in natural language responses from the drone MCP server.

        Args:
            text: The result text to parse

        Returns:
            Dictionary of extracted telemetry values
        """
        telemetry = {}

        # Extract altitude using regex pattern
        alt_match = re.search(self.ALTITUDE_PATTERN, text.lower())
        if alt_match:
            telemetry["altitude_m"] = float(alt_match.group(1))

        # Extract position (lat, lon)
        pos_match = re.search(self.POSITION_PATTERN, text.lower())
        if pos_match:
            telemetry["latitude"] = float(pos_match.group(1))
            telemetry["longitude"] = float(pos_match.group(2))

        # Extract battery percentage
        bat_match = re.search(self.BATTERY_PATTERN, text.lower())
        if bat_match:
            telemetry["battery_percent"] = float(bat_match.group(1))

        return telemetry

    def _categorize_command(self, command: str) -> str:
        """
        Categorize the command type for state tracking.

        Similar to pre_tool_use categorization but simplified for logging.
        Determines how the command affects flight state.

        Args:
            command: The command string to categorize

        Returns:
            Category string (takeoff, land, arm, disarm, navigation, mission, telemetry, other)
        """
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
        """
        Update drone state based on command execution and category.

        This method tracks the logical state of the drone based on what
        commands were executed. It updates:
        - in_flight status (set True on successful takeoff, False on land)
        - armed status (set True on arm, False on disarm)
        - altitude (reset to 0 on successful land)
        - Command statistics (total, success, failure counts)

        Args:
            command: The command that was executed
            success: Whether the command succeeded
        """
        category = self._categorize_command(command)
        self.current_state["total_commands"] += 1

        if success:
            self.current_state["successful_commands"] += 1
        else:
            self.current_state["failed_commands"] += 1

        # Update state based on command category
        # These state transitions enable the pre_tool_use hook to make
        # informed decisions about subsequent commands
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

        # Track last command for debugging and context
        self.current_state["last_command"] = command[:200]
        self.current_state["last_command_time"] = datetime.utcnow().isoformat() + "Z"

    def _update_state_from_result(self, result: str) -> None:
        """
        Update drone state from telemetry extracted in command result.

        Parses the result text for embedded telemetry and updates state
        with actual values from the drone. This is more accurate than
        inferring state from command categories.

        Args:
            result: The result text from the tool execution
        """
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
        """
        Log a telemetry entry and update persistent state.

        This is the main logging method that:
        1. Updates state from the command and its result
        2. Merges current state into the telemetry entry
        3. Appends the entry to the log file
        4. Saves updated state for the pre_tool_use hook

        Args:
            entry: TelemetryEntry containing command details
        """
        # Update state from command execution
        self._update_state_from_command(entry.command, entry.success)
        if entry.result:
            self._update_state_from_result(entry.result)

        # Merge current state into entry for complete telemetry picture
        # This ensures the log entry contains all known state at execution time
        entry.altitude_m = entry.altitude_m or self.current_state.get("altitude_m")
        entry.latitude = entry.latitude or self.current_state.get("latitude")
        entry.longitude = entry.longitude or self.current_state.get("longitude")
        entry.battery_percent = entry.battery_percent or self.current_state.get("battery_percent")
        entry.armed = entry.armed if entry.armed is not None else self.current_state.get("armed")
        entry.in_flight = entry.in_flight if entry.in_flight is not None else self.current_state.get("in_flight")

        # Write to log file as line-delimited JSON
        log_entry = asdict(entry)
        with open(self.TELEMETRY_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")

        # Save updated state for pre_tool_use hook to read
        self._save_state()

        # Print status to console for immediate feedback
        status = "SUCCESS" if entry.success else "FAILED"
        print(f"[TELEMETRY] {status}: {entry.tool_name} - {entry.command[:50]}...")


def main():
    """
    Main entry point for the Claude Code post_tool_use hook.

    This function handles the stdin protocol with Claude Code:
    1. Read JSON input from stdin containing tool result details
    2. Check if this was a drone-related command
    3. Extract telemetry and update state if it was
    4. Log the command execution
    5. Exit cleanly (post_tool_use doesn't block, only logs)

    Unlike pre_tool_use, this hook always exits with code 0 because
    it runs after execution - it can't block, only observe and record.
    """
    # Read the tool result from stdin (Claude Code sends JSON here)
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # If no valid JSON, silently exit (not a tool we care about)
        sys.exit(0)

    # Extract tool information from Claude's input
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    tool_result = input_data.get("tool_result", {})
    duration_ms = input_data.get("duration_ms")

    # Build command string from various input formats
    command = ""
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")
        command = tool_input.get("prompt", command)
        command = tool_input.get("text", command)

    # Filter for drone-related commands only
    drone_keywords = ['drone', 'uav', 'copter', 'quad', 'fly', 'arm', 'takeoff', 'land', 'mission', 'altitude', 'geofence']
    is_drone_command = any(kw in str(tool_input).lower() for kw in drone_keywords)

    if not is_drone_command:
        # Not a drone command, skip logging
        sys.exit(0)

    # Determine success status from result
    success = True
    error_message = None

    if isinstance(tool_result, dict):
        success = tool_result.get("success", True)
        error_message = tool_result.get("error") or tool_result.get("message")
    elif isinstance(tool_result, str):
        # Check for error indicators in text result
        error_indicators = ["error", "failed", "exception", "timeout", "rejected"]
        success = not any(ind in tool_result.lower() for ind in error_indicators)
        if not success:
            error_message = tool_result[:200]

    # Build result string for logging
    result = ""
    if isinstance(tool_result, dict):
        result = json.dumps(tool_result)
    elif isinstance(tool_result, str):
        result = tool_result

    # Create telemetry entry with all available information
    entry = TelemetryEntry(
        timestamp=datetime.utcnow().isoformat() + "Z",
        tool_name=tool_name,
        command=command[:500] if command else "",  # Truncate long commands
        result=result[:1000] if result else "",  # Truncate large results
        success=success,
        duration_ms=duration_ms,
        error_message=error_message[:500] if error_message else None,
    )

    # Log the entry and update state
    logger = TelemetryLogger()
    logger.log(entry)

    sys.exit(0)


if __name__ == "__main__":
    main()
