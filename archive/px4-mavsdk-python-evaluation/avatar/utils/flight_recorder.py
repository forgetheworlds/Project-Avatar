"""
Flight recorder for mission logging and telemetry capture.

Records flight events, telemetry snapshots, and generates reports for analysis.
Supports JSONL logging, JSON export, and KML export for Google Earth visualization.

WHY FLIGHT RECORDING MATTERS:
============================

Flight recording is essential for autonomous drone operations for several reasons:

1. SAFETY INVESTIGATION: When something goes wrong, the flight log provides
   a complete timeline of what happened, what commands were issued, and how
   the drone responded. This is critical for post-incident analysis.

2. PERFORMANCE ANALYSIS: Reviewing flight logs helps identify inefficiencies
   in flight paths, battery consumption patterns, and areas where autonomy
   can be improved.

3. REGULATORY COMPLIANCE: Aviation authorities often require detailed flight
   records for commercial drone operations, including telemetry, commands,
   and mission parameters.

4. REPLAY & SIMULATION: Flight logs enable replaying missions in simulation
   to test improvements or investigate alternate outcomes.

5. AI TRAINING: Recorded flight data provides training material for machine
   learning models to improve autonomous decision-making.

DATA FORMAT:
===========

The flight recorder uses JSONL (JSON Lines) format for real-time logging:
- Each line is a valid JSON object
- Objects are written atomically as they occur
- File remains valid even if recording is interrupted (crash-safe)

Record Types:
1. EVENT records - Significant mission events:
   {
     "type": "event",
     "timestamp": 1234567890.123,
     "event_type": "arm|disarm|takeoff|land|rtl|command|error|warning",
     "data": {...}
   }

2. TELEMETRY records - Periodic snapshots (1-10 Hz):
   {
     "type": "telemetry",
     "timestamp": 1234567890.123,
     "latitude": 37.7749,
     "longitude": -122.4194,
     "altitude_amsl_m": 100.0,
     "altitude_rel_m": 50.0,
     "ground_speed_m_s": 5.0,
     "heading_deg": 90.0,
     "battery_percent": 85.0,
     "gps_fix_type": 3,
     "in_flight": true
   }

File naming convention: {mission_name}_{YYYYMMDD}_{HHMMSS}.jsonl
Example: search_and_rescue_20260115_143022.jsonl

REPLAY WORKFLOW:
===============

Flight logs can be replayed for analysis, debugging, and simulation:

1. JSON Export (analysis/replay):
   - Use export_json() to get structured data
   - Load into analysis tools or simulators
   - Playback at original or accelerated speed

2. KML Export (visualization):
   - Use export_kml() for Google Earth visualization
   - Shows 3D flight path with altitude
   - Event markers at actual GPS coordinates
   - Useful for mission debriefs and documentation

3. Manual Replay (programmatic):
   ```python
   with open("mission.jsonl") as f:
       for line in f:
           record = json.loads(line)
           if record["type"] == "telemetry":
               replay_position(record)
           elif record["type"] == "event":
               replay_event(record)
   ```

STORAGE MANAGEMENT:
==================

Log files are stored in a configurable directory (default: ./logs/)

Storage Strategy:
- Logs are appended to JSONL files in real-time
- No rotation during a mission (single file per mission)
- In-memory buffers hold events/telemetry for statistics and export
- Statistics are computed incrementally to avoid memory issues

Size Estimates:
- Event record: ~100-500 bytes
- Telemetry record: ~200-300 bytes
- 10-minute flight at 1Hz telemetry: ~120KB + events
- 1-hour flight at 1Hz telemetry: ~720KB + events

Security:
- Export paths are validated to prevent path traversal attacks
- All exports must be within the configured log_dir
- validate_export_path() ensures no directory escape

Cleanup Recommendations:
- Implement archival policy for old logs (e.g., >30 days)
- Compress completed missions for long-term storage
- Consider cloud sync for critical mission logs
"""
import asyncio
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def validate_export_path(filepath: str, allowed_dir: str) -> Path:
    """Validate that export path is within allowed directory.

    Prevents path traversal attacks by ensuring the resolved path
    is within the allowed directory.

    Args:
        filepath: Target file path for export.
        allowed_dir: Directory that exports are allowed to be written to.

    Returns:
        Resolved absolute Path object if validation passes.

    Raises:
        ValueError: If path attempts traversal outside allowed_dir.
    """
    allowed_path = Path(allowed_dir).resolve()
    target_path = Path(filepath).resolve()

    # Check if target is within allowed directory
    try:
        target_path.relative_to(allowed_path)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{filepath}' is outside allowed directory '{allowed_dir}'"
        )

    return target_path


@dataclass
class TelemetrySnapshot:
    """
    Single telemetry data point captured during flight.

    This dataclass stores a snapshot of the drone's state at a specific
    moment in time. These snapshots are collected at regular intervals
    (typically 1-10 Hz) to reconstruct the flight path and analyze
    performance metrics.

    Attributes:
        timestamp: Unix timestamp (seconds since epoch) when data was captured
        latitude: GPS latitude in decimal degrees (-90 to 90)
        longitude: GPS longitude in decimal degrees (-180 to 180)
        altitude_amsl_m: Altitude above mean sea level in meters
        altitude_rel_m: Altitude relative to takeoff/home position in meters
        ground_speed_m_s: Ground speed in meters per second
        heading_deg: Aircraft heading in degrees (0-360, 0=north)
        battery_percent: Battery charge remaining (0-100%)
        gps_fix_type: GPS fix quality (0=no fix, 2=2D, 3=3D)
        in_flight: True if aircraft is airborne (landed state is False)
    """
    timestamp: float  # Unix timestamp
    latitude: Optional[float] = None  # Degrees
    longitude: Optional[float] = None  # Degrees
    altitude_amsl_m: Optional[float] = None  # Meters above mean sea level
    altitude_rel_m: Optional[float] = None  # Meters relative to home
    ground_speed_m_s: Optional[float] = None  # Ground speed in m/s
    heading_deg: Optional[float] = None  # Heading in degrees
    battery_percent: Optional[float] = None  # Battery remaining percentage
    gps_fix_type: Optional[int] = None  # GPS fix type (0-3)
    in_flight: Optional[bool] = None  # Aircraft is airborne


@dataclass
class FlightEvent:
    """
    A discrete flight event for mission timeline reconstruction.

    Events represent significant moments in a mission: arming, takeoff,
    waypoint arrival, command execution, errors, and landings. Unlike
    continuous telemetry, events occur at irregular intervals and
    carry contextual data specific to the event type.

    Event Types and Their Data:
    - "arm": {"source": "mcp|auto|manual"}
    - "disarm": {"source": "...", "reason": "..."}
    - "takeoff": {"altitude": 50.0, "mode": "guided"}
    - "land": {"location": "...", "mode": "rtl|land"}
    - "rtl": {"reason": "low_battery|command|failsafe"}
    - "command": {"type": "goto|orbit|survey", "params": {...}}
    - "error": {"message": "...", "severity": "..."}
    - "warning": {"message": "..."}

    Attributes:
        timestamp: Unix timestamp when event occurred
        event_type: Category string identifying the event kind
        data: Event-specific dictionary with context and parameters
    """
    timestamp: float  # Unix timestamp
    event_type: str  # Event category
    data: Dict[str, Any]  # Event-specific data


@dataclass
class MissionStats:
    """
    Aggregated statistics for a complete mission.

    These statistics are computed incrementally during flight to avoid
    memory issues with long missions. The recorder updates these values
    with each telemetry snapshot, tracking maximums, minimums, and
    cumulative values.

    Post-flight analysis uses these statistics for:
    - Mission duration and flight time comparison (hover vs moving)
    - Battery efficiency analysis (distance per % battery)
    - Altitude envelope verification (stayed within limits?)
    - Speed analysis (average vs max speeds)

    Attributes:
        mission_name: Human-readable mission identifier
        start_time: Unix timestamp when recording began
        end_time: Unix timestamp when recording stopped
        duration_s: Total recording duration in seconds
        total_events: Count of discrete events recorded
        total_telemetry_points: Count of telemetry snapshots
        max_altitude_amsl_m: Maximum altitude above sea level reached
        max_altitude_rel_m: Maximum altitude above home position reached
        max_ground_speed_m_s: Maximum ground speed achieved
        min_battery_percent: Lowest battery level observed (for stress analysis)
        total_distance_m: Cumulative distance traveled (computed via haversine)
        flight_time_s: Time spent in actual flight (airborne, not landed)
    """
    mission_name: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_s: float = 0.0
    total_events: int = 0
    total_telemetry_points: int = 0
    max_altitude_amsl_m: float = 0.0
    max_altitude_rel_m: float = 0.0
    max_ground_speed_m_s: float = 0.0
    min_battery_percent: float = 100.0
    total_distance_m: float = 0.0
    flight_time_s: float = 0.0


class FlightRecorder:
    """
    Flight recorder for mission logging and telemetry capture.

    The FlightRecorder is the primary interface for logging drone operations.
    It provides a complete audit trail of what happened during a mission,
    enabling post-flight analysis, regulatory compliance, and safety review.

    Core Responsibilities:
    1. Record flight events to JSONL log file (real-time, crash-safe)
    2. Capture telemetry snapshots at configurable intervals
    3. Generate mission statistics and performance metrics
    4. Export data to JSON (analysis) and KML (visualization) formats

    Recording Lifecycle:
    --------------------
    1. Initialize: Create FlightRecorder with log directory
       recorder = FlightRecorder("./logs")

    2. Start Recording: Begin a new mission log
       await recorder.start_recording("mission_001")
       - Creates timestamped JSONL file
       - Initializes statistics tracking
       - Clears previous mission data

    3. Log Events: Record significant mission events
       await recorder.log_event("arm", {"source": "mcp"})
       await recorder.log_event("takeoff", {"altitude": 50.0})
       await recorder.log_event("command", {"type": "goto", "lat": 37.0, "lon": -122.0})

    4. Log Telemetry: Capture periodic state snapshots (call from telemetry loop)
       await recorder.log_telemetry({
           "latitude": 37.7749,
           "longitude": -122.4194,
           "altitude_amsl_m": 100.0,
           "ground_speed_m_s": 5.0,
           "battery_percent": 85.0,
           "in_flight": True
       })

    5. Stop Recording: Finalize and close the log
       await recorder.stop_recording()
       - Computes final statistics
       - Closes file handle
       - Log file is now ready for analysis

    6. Export/Analyze: Generate reports and visualizations
       report = recorder.generate_report()  # Dictionary with stats
       recorder.export_json("mission.json")  # Structured data export
       recorder.export_kml("mission.kml")    # Google Earth visualization

    Storage Format Details:
    -----------------------
    The JSONL format is chosen for several important reasons:
    - Append-only: New records don't require reading/rewriting existing data
    - Crash-safe: If the process dies, all records written so far are valid
    - Streaming: Can be processed line-by-line without loading entire file
    - Human-readable: Each line is self-contained JSON

    File example:
    {"type": "event", "timestamp": 1234567890.123, "event_type": "arm", "data": {"source": "mcp"}}
    {"type": "telemetry", "timestamp": 1234567890.234, "latitude": 37.7749, ...}
    {"type": "telemetry", "timestamp": 1234567890.334, "latitude": 37.7750, ...}
    {"type": "event", "timestamp": 1234567891.123, "event_type": "takeoff", "data": {...}}

    Memory Management:
    ------------------
    The recorder maintains in-memory lists of events and telemetry for
    statistics calculation and export generation. For very long missions,
    this could consume significant memory. The current implementation
    computes statistics incrementally, so in-memory storage is primarily
    for post-flight export functionality.

    For production deployments with very long missions (hours), consider:
    - Periodic export and clear of in-memory data
    - Streaming export without in-memory storage
    - Database storage instead of in-memory lists

    Thread Safety:
    -------------
    All methods are async/await compatible and use asyncio.to_thread()
    for file I/O operations. This prevents blocking the event loop
    during disk writes. The class is designed for single-producer
    use (one coroutine logging) - if multiple coroutines need to
    log simultaneously, external synchronization is required.
    """

    def __init__(self, log_dir: str = "./logs"):
        """
        Initialize flight recorder.

        Creates the log directory if it doesn't exist. The recorder starts
        in an idle state - call start_recording() to begin logging.

        Args:
            log_dir: Directory to store log files. Created if not exists.
                     All exports are also restricted to this directory
                     for security (prevents path traversal attacks).
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Current recording state (None when not recording)
        self._current_mission: Optional[str] = None
        self._log_file: Optional[Any] = None
        self._log_path: Optional[Path] = None

        # In-memory storage for analysis and export generation
        # These lists grow during recording and are cleared on new mission
        self._events: List[FlightEvent] = []
        self._telemetry: List[TelemetrySnapshot] = []
        self._stats: Optional[MissionStats] = None

        # Previous position tracking for distance calculation
        # Uses haversine formula to compute great-circle distance between points
        self._prev_lat: Optional[float] = None
        self._prev_lon: Optional[float] = None

        # Flight time tracking (accumulated time spent airborne)
        self._flight_start_time: Optional[float] = None
        self._last_in_flight: bool = False

    async def start_recording(self, mission_name: str) -> bool:
        """
        Start recording a new mission.

        Creates a new JSONL log file with a timestamped filename and
        initializes recording state. Cannot start a new recording while
        one is already in progress - must call stop_recording() first.

        Filename Format: {sanitized_name}_{YYYYMMDD}_{HHMMSS}.jsonl
        Example: "search_rescue_20260115_143022.jsonl"

        Args:
            mission_name: Unique name for this mission (used in filename).
                         Non-alphanumeric characters are sanitized to underscores.

        Returns:
            True if recording started successfully, False otherwise.

        Example:
            recorder = FlightRecorder("./logs")
            success = await recorder.start_recording("survey_mission_001")
            if success:
                print(f"Recording to: {recorder.log_path}")
        """
        if self._log_file is not None:
            logger.warning(f"Recording already in progress: {self._current_mission}")
            return False

        # Sanitize mission name for safe filename (remove special chars)
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in mission_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.jsonl"
        self._log_path = self.log_dir / filename

        try:
            # Open file for append (creates if doesn't exist)
            # Using asyncio.to_thread to prevent blocking event loop
            self._log_file = await asyncio.to_thread(
                open, self._log_path, "a", encoding="utf-8"
            )
            self._current_mission = mission_name
            self._stats = MissionStats(mission_name=mission_name)
            self._stats.start_time = time.time()

            # Reset all tracking state for clean mission start
            self._events.clear()
            self._telemetry.clear()
            self._prev_lat = None
            self._prev_lon = None
            self._flight_start_time = None
            self._last_in_flight = False

            logger.info(f"Started recording mission: {mission_name} -> {self._log_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False

    async def log_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Log a discrete flight event.

        Events represent significant moments in the mission timeline.
        They are written immediately to the JSONL file and stored in memory
        for later analysis and export.

        Common Event Types:
        - "arm": Vehicle armed (motors can spin)
        - "disarm": Vehicle disarmed (motors stop)
        - "takeoff": Takeoff initiated
        - "land": Landing initiated or completed
        - "rtl": Return-to-launch mode activated
        - "command": High-level command executed (goto, orbit, etc.)
        - "error": Error condition encountered
        - "warning": Warning condition encountered
        - "waypoint": Waypoint reached during mission
        - "detect": Object detection event from vision system

        Args:
            event_type: Category string identifying the event.
            data: Event-specific data dictionary. Structure varies by event type.

        Returns:
            True if event logged successfully, False if not recording.

        Example:
            await recorder.log_event("takeoff", {
                "altitude": 50.0,
                "mode": "guided",
                "wind_speed": 5.2
            })
        """
        if self._log_file is None:
            logger.warning("Cannot log event - not recording")
            return False

        event = FlightEvent(
            timestamp=time.time(),
            event_type=event_type,
            data=data
        )
        self._events.append(event)

        # Build JSONL record - each line is self-contained JSON object
        record = {
            "type": "event",
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "data": event.data
        }

        try:
            line = json.dumps(record) + "\n"
            await asyncio.to_thread(self._log_file.write, line)
            await asyncio.to_thread(self._log_file.flush)  # Ensure written to disk
            logger.debug(f"Logged event: {event_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return False

    async def log_telemetry(self, telemetry: Dict[str, Any]) -> bool:
        """
        Log a telemetry snapshot.

        Telemetry provides continuous state monitoring of the aircraft.
        Call this periodically from your telemetry loop (typical rates:
        1-10 Hz depending on mission criticality and storage constraints).

        The recorder updates running statistics with each snapshot:
        - Maximum altitudes (absolute and relative)
        - Maximum ground speed
        - Minimum battery percentage
        - Total distance traveled (using haversine formula)
        - Flight time (time spent with in_flight=True)

        Telemetry Dictionary Keys:
        - latitude (float): GPS latitude in decimal degrees
        - longitude (float): GPS longitude in decimal degrees
        - altitude_amsl_m (float): Altitude above mean sea level (meters)
        - altitude_rel_m (float): Altitude relative to home (meters)
        - ground_speed_m_s (float): Ground speed (m/s)
        - heading_deg (float): Aircraft heading, 0-360 degrees
        - battery_percent (float): Battery remaining, 0-100%
        - gps_fix_type (int): GPS fix quality (0=no fix, 2=2D, 3=3D)
        - in_flight (bool): True if aircraft is airborne

        Args:
            telemetry: Dictionary with telemetry values. Missing keys
                      result in None values in the snapshot.

        Returns:
            True if telemetry logged successfully, False if not recording.

        Example:
            # Call this from your telemetry loop at 1-10 Hz
            while recording:
                await recorder.log_telemetry({
                    "latitude": position.lat,
                    "longitude": position.lon,
                    "altitude_amsl_m": altitude.amsl,
                    "ground_speed_m_s": ground_speed,
                    "battery_percent": battery.remaining_percent,
                    "in_flight": status.is_in_flight
                })
                await asyncio.sleep(0.1)  # 10 Hz rate
        """
        if self._log_file is None:
            logger.warning("Cannot log telemetry - not recording")
            return False

        # Create telemetry snapshot from dictionary
        snapshot = TelemetrySnapshot(
            timestamp=time.time(),
            latitude=telemetry.get("latitude"),
            longitude=telemetry.get("longitude"),
            altitude_amsl_m=telemetry.get("altitude_amsl_m"),
            altitude_rel_m=telemetry.get("altitude_rel_m"),
            ground_speed_m_s=telemetry.get("ground_speed_m_s"),
            heading_deg=telemetry.get("heading_deg"),
            battery_percent=telemetry.get("battery_percent"),
            gps_fix_type=telemetry.get("gps_fix_type"),
            in_flight=telemetry.get("in_flight")
        )
        self._telemetry.append(snapshot)

        # Update running statistics with this new snapshot
        self._update_stats(snapshot)

        # Write to JSONL file (immediate flush for crash safety)
        record = {
            "type": "telemetry",
            **asdict(snapshot)
        }

        try:
            line = json.dumps(record) + "\n"
            await asyncio.to_thread(self._log_file.write, line)
            await asyncio.to_thread(self._log_file.flush)
            logger.debug("Logged telemetry snapshot")
            return True
        except Exception as e:
            logger.error(f"Failed to log telemetry: {e}")
            return False

    async def stop_recording(self) -> None:
        """
        Stop recording and close the log file.

        Finalizes the mission statistics (computes duration, event counts)
        and closes the file handle. Safe to call even if not currently
        recording (logs a warning and returns early).

        After stopping:
        - The JSONL file is complete and ready for analysis
        - generate_report() can be called to get statistics
        - export_json() and export_kml() can be called for exports
        - start_recording() can be called to begin a new mission

        Example:
            await recorder.stop_recording()
            report = recorder.generate_report()
            print(f"Mission complete: {report['duration_s']} seconds")
        """
        if self._log_file is None:
            logger.warning("No recording in progress to stop")
            return

        # Finalize statistics before closing
        if self._stats:
            self._stats.end_time = time.time()
            self._stats.total_events = len(self._events)
            self._stats.total_telemetry_points = len(self._telemetry)
            if self._stats.start_time:
                self._stats.duration_s = self._stats.end_time - self._stats.start_time

        # Close file handle
        try:
            await asyncio.to_thread(self._log_file.close)
            logger.info(f"Stopped recording: {self._current_mission}")
        except Exception as e:
            logger.error(f"Error closing log file: {e}")

        # Clear recording state
        self._log_file = None
        self._current_mission = None

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a mission report with statistics.

        Creates a human-readable dictionary containing mission statistics
        suitable for display, logging, or JSON export. All floating-point
        values are rounded to 2 decimal places for readability.

        Report Contents:
        - mission_name: Name of the mission
        - start_time/end_time: Unix timestamps
        - duration_s: Total recording time in seconds
        - flight_time_s: Actual flight time (airborne) in seconds
        - total_events: Number of discrete events logged
        - total_telemetry_points: Number of telemetry snapshots
        - max_altitude_amsl_m: Maximum altitude above sea level
        - max_altitude_rel_m: Maximum altitude above home
        - max_ground_speed_m_s: Maximum ground speed achieved
        - min_battery_percent: Lowest battery level observed
        - total_distance_m: Total distance traveled in meters

        Returns:
            Dictionary with mission statistics and summary.
            Returns empty dict if no mission has been recorded.

        Example:
            report = recorder.generate_report()
            print(f"Flight time: {report['flight_time_s']}s")
            print(f"Distance: {report['total_distance_m']}m")
            print(f"Max altitude: {report['max_altitude_rel_m']}m")
        """
        if self._stats is None:
            return {}

        return {
            "mission_name": self._stats.mission_name,
            "start_time": self._stats.start_time,
            "end_time": self._stats.end_time,
            "duration_s": round(self._stats.duration_s, 2),
            "flight_time_s": round(self._stats.flight_time_s, 2),
            "total_events": self._stats.total_events,
            "total_telemetry_points": self._stats.total_telemetry_points,
            "max_altitude_amsl_m": round(self._stats.max_altitude_amsl_m, 2),
            "max_altitude_rel_m": round(self._stats.max_altitude_rel_m, 2),
            "max_ground_speed_m_s": round(self._stats.max_ground_speed_m_s, 2),
            "min_battery_percent": round(self._stats.min_battery_percent, 2),
            "total_distance_m": round(self._stats.total_distance_m, 2),
        }

    def export_json(self, filepath: str) -> bool:
        """
        Export mission data to a structured JSON file.

        Creates a human-readable JSON file containing the complete mission
        data: report statistics, all events, and all telemetry points.
        This format is suitable for:
        - External analysis tools (pandas, MATLAB, etc.)
        - Mission replay in simulators
        - Machine learning training data
        - Regulatory compliance documentation

        Security: The filepath is validated to ensure it stays within
        the configured log_dir. This prevents path traversal attacks
        that could write files to arbitrary system locations.

        Output Structure:
        {
          "mission": { /* report statistics */ },
          "events": [
            {"timestamp": ..., "event_type": ..., "data": {...}},
            ...
          ],
          "telemetry": [
            {"timestamp": ..., "latitude": ..., ...},
            ...
          ]
        }

        Args:
            filepath: Path for the output JSON file (relative to log_dir)

        Returns:
            True if export successful, False otherwise.

        Example:
            success = recorder.export_json("mission_001_export.json")
            if success:
                print("Export complete")
        """
        if self._stats is None:
            logger.warning("No mission data to export")
            return False

        # Validate path is within allowed directory (security check)
        try:
            output_path = validate_export_path(filepath, str(self.log_dir))
        except ValueError as e:
            logger.error(f"Invalid export path: {e}")
            return False

        # Build export structure
        data = {
            "mission": self.generate_report(),
            "events": [asdict(e) for e in self._events],
            "telemetry": [asdict(t) for t in self._telemetry]
        }

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Exported JSON to: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            return False

    def export_kml(self, filepath: str) -> bool:
        """
        Export flight path to KML for Google Earth visualization.

        Creates a KML (Keyhole Markup Language) file that can be opened
        directly in Google Earth or Google Earth Pro. The visualization
        includes:
        - Flight path as a colored line (blue LineString with 3D coordinates)
        - Placemark at home position (if determined from data)
        - Placemarks for all flight events positioned at nearest GPS point

        This is invaluable for:
        - Mission debriefs and visual analysis
        - Identifying flight path inefficiencies
        - Documentation and reporting
        - Training and demonstration

        KML Format Notes:
        - Uses lon,lat,altitude coordinate order (KML standard)
        - Altitude is meters above sea level (absolute, not relative)
        - Colors are in ABGR hex format (alpha, blue, green, red)
        - Line color is blue: ff0000ff

        Security: Export path is validated against the log_dir to prevent
        directory traversal attacks.

        Args:
            filepath: Path for the output KML file (relative to log_dir)

        Returns:
            True if export successful, False otherwise.

        Example:
            success = recorder.export_kml("mission_001.kml")
            if success:
                print("Open mission_001.kml in Google Earth to view flight path")
        """
        if self._stats is None or not self._telemetry:
            logger.warning("No telemetry data to export KML")
            return False

        # Validate path is within allowed directory
        try:
            output_path = validate_export_path(filepath, str(self.log_dir))
        except ValueError as e:
            logger.error(f"Invalid export path: {e}")
            return False

        # Filter to only telemetry with valid GPS coordinates
        # Some telemetry snapshots may lack GPS if fix was lost
        gps_points = [
            t for t in self._telemetry
            if t.latitude is not None and t.longitude is not None
        ]

        if not gps_points:
            logger.warning("No valid GPS coordinates in telemetry")
            return False

        # Build KML XML content
        kml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '  <Document>',
            f'    <name>{self._stats.mission_name}</name>',
            '    <description>Flight path recorded by Avatar Flight Recorder</description>',
            '',
            '    <!-- Flight Path Style: Blue line, 3px width -->',
            '    <Style id="flightPathStyle">',
            '      <LineStyle>',
            '        <color>ff0000ff</color>',  # ABGR format: blue
            '        <width>3</width>',
            '      </LineStyle>',
            '    </Style>',
            '',
            '    <!-- Flight Path LineString -->',
            '    <Placemark>',
            '      <name>Flight Path</name>',
            '      <styleUrl>#flightPathStyle</styleUrl>',
            '      <LineString>',
            '        <coordinates>'
        ]

        # Add coordinates (KML uses lon,lat,altitude order)
        # Altitude is meters above sea level (absolute)
        coords = []
        for t in gps_points:
            alt = t.altitude_amsl_m or 0
            coords.append(f"          {t.longitude},{t.latitude},{alt}")
        kml_lines.append(",\n".join(coords))

        kml_lines.extend([
            '        </coordinates>',
            '      </LineString>',
            '    </Placemark>',
            ''
        ])

        # Add event placemarks for key mission events
        # Events are positioned at the nearest telemetry point's GPS coordinates
        for event in self._events:
            # Find nearest telemetry point for positioning
            nearest_telem = self._find_nearest_telemetry(event.timestamp)
            if nearest_telem and nearest_telem.latitude and nearest_telem.longitude:
                kml_lines.extend([
                    '    <Placemark>',
                    f'      <name>{event.event_type}</name>',
                    f'      <description>{json.dumps(event.data)}</description>',
                    '      <Point>',
                    f'        <coordinates>{nearest_telem.longitude},{nearest_telem.latitude},{nearest_telem.altitude_amsl_m or 0}</coordinates>',
                    '      </Point>',
                    '    </Placemark>',
                    ''
                ])

        # Close KML document
        kml_lines.extend([
            '  </Document>',
            '</kml>'
        ])

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(kml_lines))
            logger.info(f"Exported KML to: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export KML: {e}")
            return False

    def _update_stats(self, snapshot: TelemetrySnapshot) -> None:
        """
        Update mission statistics with a new telemetry snapshot.

        This internal method is called by log_telemetry() to maintain
        running statistics. It computes:
        - Maximum altitudes (tracks highest points reached)
        - Maximum ground speed (tracks fastest movement)
        - Minimum battery (tracks worst battery state for safety analysis)
        - Total distance (cumulative using haversine formula between points)
        - Flight time (accumulated seconds when in_flight=True)

        The distance calculation uses the haversine formula which computes
        the great-circle distance between two GPS coordinates, accounting
        for the Earth's curvature. This is accurate for typical drone flights
        but less accurate for very long distances (use Vincenty for >100km).

        Args:
            snapshot: TelemetrySnapshot with current aircraft state
        """
        if self._stats is None:
            return

        # Track maximum altitudes (absolute and relative)
        if snapshot.altitude_amsl_m is not None:
            self._stats.max_altitude_amsl_m = max(
                self._stats.max_altitude_amsl_m, snapshot.altitude_amsl_m
            )
        if snapshot.altitude_rel_m is not None:
            self._stats.max_altitude_rel_m = max(
                self._stats.max_altitude_rel_m, snapshot.altitude_rel_m
            )

        # Track maximum ground speed
        if snapshot.ground_speed_m_s is not None:
            self._stats.max_ground_speed_m_s = max(
                self._stats.max_ground_speed_m_s, snapshot.ground_speed_m_s
            )

        # Track minimum battery (for safety analysis - when did battery get lowest?)
        if snapshot.battery_percent is not None:
            self._stats.min_battery_percent = min(
                self._stats.min_battery_percent, snapshot.battery_percent
            )

        # Calculate distance from previous point using haversine formula
        if snapshot.latitude is not None and snapshot.longitude is not None:
            if self._prev_lat is not None and self._prev_lon is not None:
                dist = self._haversine_distance(
                    self._prev_lat, self._prev_lon,
                    snapshot.latitude, snapshot.longitude
                )
                self._stats.total_distance_m += dist
            # Update previous position for next calculation
            self._prev_lat = snapshot.latitude
            self._prev_lon = snapshot.longitude

        # Track flight time (time spent airborne)
        # Uses state transitions to detect takeoff and landing
        if snapshot.in_flight is not None:
            if snapshot.in_flight and not self._last_in_flight:
                # Transition from landed to flying (takeoff detected)
                self._flight_start_time = snapshot.timestamp
            elif not snapshot.in_flight and self._last_in_flight:
                # Transition from flying to landed (landing detected)
                if self._flight_start_time is not None:
                    flight_segment = snapshot.timestamp - self._flight_start_time
                    self._stats.flight_time_s += flight_segment
                    self._flight_start_time = None
            self._last_in_flight = snapshot.in_flight

    def _find_nearest_telemetry(self, timestamp: float) -> Optional[TelemetrySnapshot]:
        """
        Find the telemetry snapshot closest to a given timestamp.

        This is used internally for positioning event markers in KML export.
        Events are logged without GPS coordinates, so we find the nearest
        telemetry point to determine where the event occurred.

        Algorithm: Simple linear search with minimum delta comparison.
        For large datasets (>10k points), a binary search would be more
        efficient. Current implementation is O(n) which is acceptable for
        typical drone missions (1000-10000 telemetry points).

        Args:
            timestamp: Target Unix timestamp to find nearest to

        Returns:
            TelemetrySnapshot closest to the given timestamp, or None
            if no telemetry data exists.
        """
        if not self._telemetry:
            return None

        nearest = min(
            self._telemetry,
            key=lambda t: abs(t.timestamp - timestamp)
        )
        return nearest

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.

        The Haversine formula calculates the great-circle distance between
        two points on a sphere given their longitudes and latitudes. This
        is accurate for typical drone operations but has limitations:

        - Assumes Earth is a perfect sphere (it's actually an ellipsoid)
        - Error is small for distances < 100km (<0.5% error)
        - For longer distances, use Vincenty formula or geodesic libraries

        The formula:
        a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
        c = 2 * atan2(√a, √(1-a))
        distance = R * c

        Where:
        - φ (phi) is latitude in radians
        - λ (lambda) is longitude in radians
        - R is Earth's radius (mean radius = 6,371,000 meters)
        - Δφ = φ2 - φ1
        - Δλ = λ2 - λ1

        Args:
            lat1, lon1: First coordinate in decimal degrees
            lat2, lon2: Second coordinate in decimal degrees

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth's mean radius in meters (6,371 km)

        # Convert to radians
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        # Haversine formula
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @property
    def is_recording(self) -> bool:
        """Check if a recording is currently in progress.

        Returns:
            True if actively recording, False otherwise.
        """
        return self._log_file is not None

    @property
    def current_mission(self) -> Optional[str]:
        """Get the name of the current mission being recorded.

        Returns:
            Mission name string if recording, None otherwise.
        """
        return self._current_mission

    @property
    def log_path(self) -> Optional[Path]:
        """Get the filesystem path to the current log file.

        Returns:
            Path object if recording or after stopping, None if never started.
        """
        return self._log_path
