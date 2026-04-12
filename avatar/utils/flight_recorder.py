"""
Flight recorder for mission logging and telemetry capture.

Records flight events, telemetry snapshots, and generates reports for analysis.
Supports JSONL logging, JSON export, and KML export for Google Earth visualization.
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
    """Single telemetry data point."""
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
    """A recorded flight event."""
    timestamp: float  # Unix timestamp
    event_type: str  # Event category
    data: Dict[str, Any]  # Event-specific data


@dataclass
class MissionStats:
    """Mission statistics summary."""
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

    Responsibilities:
    - Record flight events to JSONL log file
    - Capture telemetry snapshots at intervals
    - Generate mission statistics and reports
    - Export data to JSON and KML formats

    Usage:
        recorder = FlightRecorder("./logs")
        await recorder.start_recording("mission_001")

        # Log events
        await recorder.log_event("arm", {"source": "command"})
        await recorder.log_event("takeoff", {"altitude": 50.0})

        # Log telemetry (typically from telemetry loop)
        await recorder.log_telemetry({
            "latitude": 37.7749,
            "longitude": -122.4194,
            "altitude_amsl_m": 100.0,
            "ground_speed_m_s": 5.0,
            "battery_percent": 85.0
        })

        # Stop recording and generate report
        await recorder.stop_recording()
        report = recorder.generate_report()
        recorder.export_json("mission_001.json")
        recorder.export_kml("mission_001.kml")
    """

    def __init__(self, log_dir: str = "./logs"):
        """
        Initialize flight recorder.

        Args:
            log_dir: Directory to store log files. Created if not exists.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._current_mission: Optional[str] = None
        self._log_file: Optional[Any] = None
        self._log_path: Optional[Path] = None

        # In-memory storage for analysis
        self._events: List[FlightEvent] = []
        self._telemetry: List[TelemetrySnapshot] = []
        self._stats: Optional[MissionStats] = None

        # Track previous position for distance calculation
        self._prev_lat: Optional[float] = None
        self._prev_lon: Optional[float] = None
        self._flight_start_time: Optional[float] = None
        self._last_in_flight: bool = False

    async def start_recording(self, mission_name: str) -> bool:
        """
        Start recording a new mission.

        Creates a new JSONL log file and initializes recording state.
        Cannot start a new recording while one is in progress.

        Args:
            mission_name: Unique name for this mission (used in filename).

        Returns:
            True if recording started successfully, False otherwise.
        """
        if self._log_file is not None:
            logger.warning(f"Recording already in progress: {self._current_mission}")
            return False

        # Sanitize mission name for filename
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in mission_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.jsonl"
        self._log_path = self.log_dir / filename

        try:
            self._log_file = await asyncio.to_thread(
                open, self._log_path, "a", encoding="utf-8"
            )
            self._current_mission = mission_name
            self._stats = MissionStats(mission_name=mission_name)
            self._stats.start_time = time.time()

            # Clear previous data
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
        Log a flight event.

        Events are written immediately to the JSONL file and stored in memory.
        Common event types: arm, disarm, takeoff, land, rtl, command, error, warning.

        Args:
            event_type: Category of the event.
            data: Event-specific data dictionary.

        Returns:
            True if event logged successfully, False if not recording.
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

        # Write to JSONL
        record = {
            "type": "event",
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "data": event.data
        }

        try:
            line = json.dumps(record) + "\n"
            await asyncio.to_thread(self._log_file.write, line)
            await asyncio.to_thread(self._log_file.flush)
            logger.debug(f"Logged event: {event_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return False

    async def log_telemetry(self, telemetry: Dict[str, Any]) -> bool:
        """
        Log a telemetry snapshot.

        Telemetry is written to the JSONL file and stored for analysis.
        Call this periodically from your telemetry loop (e.g., 1-10 Hz).

        Args:
            telemetry: Dictionary with telemetry values. Supported keys:
                - latitude: Position latitude (degrees)
                - longitude: Position longitude (degrees)
                - altitude_amsl_m: Altitude above mean sea level (meters)
                - altitude_rel_m: Altitude relative to home (meters)
                - ground_speed_m_s: Ground speed (m/s)
                - heading_deg: Heading (degrees)
                - battery_percent: Battery remaining (%)
                - gps_fix_type: GPS fix type (0-3)
                - in_flight: Aircraft is airborne

        Returns:
            True if telemetry logged successfully, False if not recording.
        """
        if self._log_file is None:
            logger.warning("Cannot log telemetry - not recording")
            return False

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

        # Update statistics
        self._update_stats(snapshot)

        # Write to JSONL
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

        Finalizes the mission statistics and closes the file handle.
        Safe to call even if not recording.
        """
        if self._log_file is None:
            logger.warning("No recording in progress to stop")
            return

        # Finalize statistics
        if self._stats:
            self._stats.end_time = time.time()
            self._stats.total_events = len(self._events)
            self._stats.total_telemetry_points = len(self._telemetry)
            if self._stats.start_time:
                self._stats.duration_s = self._stats.end_time - self._stats.start_time

        # Close file
        try:
            await asyncio.to_thread(self._log_file.close)
            logger.info(f"Stopped recording: {self._current_mission}")
        except Exception as e:
            logger.error(f"Error closing log file: {e}")

        self._log_file = None
        self._current_mission = None

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a mission report with statistics.

        Returns:
            Dictionary with mission statistics and summary.
            Returns empty dict if no mission has been recorded.
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
        Export mission data to a JSON file.

        Creates a human-readable JSON file with all events, telemetry,
        and statistics for external analysis.

        Args:
            filepath: Path for the output JSON file.

        Returns:
            True if export successful, False otherwise.
        """
        if self._stats is None:
            logger.warning("No mission data to export")
            return False

        # Validate path is within allowed directory
        try:
            output_path = validate_export_path(filepath, str(self.log_dir))
        except ValueError as e:
            logger.error(f"Invalid export path: {e}")
            return False

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

        Creates a KML file with:
        - Flight path as a LineString
        - Placemark at home position
        - Placemarks for events

        Args:
            filepath: Path for the output KML file.

        Returns:
            True if export successful, False otherwise.
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

        # Filter telemetry with valid GPS
        gps_points = [
            t for t in self._telemetry
            if t.latitude is not None and t.longitude is not None
        ]

        if not gps_points:
            logger.warning("No valid GPS coordinates in telemetry")
            return False

        # Build KML content
        kml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<kml xmlns="http://www.opengis.net/kml/2.2">',
            '  <Document>',
            f'    <name>{self._stats.mission_name}</name>',
            '    <description>Flight path recorded by Avatar Flight Recorder</description>',
            '',
            '    <!-- Flight Path Style -->',
            '    <Style id="flightPathStyle">',
            '      <LineStyle>',
            '        <color>ff0000ff</color>',  # ABGR format: blue
            '        <width>3</width>',
            '      </LineStyle>',
            '    </Style>',
            '',
            '    <!-- Flight Path -->',
            '    <Placemark>',
            '      <name>Flight Path</name>',
            '      <styleUrl>#flightPathStyle</styleUrl>',
            '      <LineString>',
            '        <coordinates>'
        ]

        # Add coordinates (KML uses lon,lat,altitude order)
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

        # Add event placemarks
        for event in self._events:
            # Find nearest telemetry point for position
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

        # Close document
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
        """Update statistics with new telemetry snapshot."""
        if self._stats is None:
            return

        # Altitude records
        if snapshot.altitude_amsl_m is not None:
            self._stats.max_altitude_amsl_m = max(
                self._stats.max_altitude_amsl_m, snapshot.altitude_amsl_m
            )
        if snapshot.altitude_rel_m is not None:
            self._stats.max_altitude_rel_m = max(
                self._stats.max_altitude_rel_m, snapshot.altitude_rel_m
            )

        # Speed record
        if snapshot.ground_speed_m_s is not None:
            self._stats.max_ground_speed_m_s = max(
                self._stats.max_ground_speed_m_s, snapshot.ground_speed_m_s
            )

        # Battery minimum
        if snapshot.battery_percent is not None:
            self._stats.min_battery_percent = min(
                self._stats.min_battery_percent, snapshot.battery_percent
            )

        # Distance calculation
        if snapshot.latitude is not None and snapshot.longitude is not None:
            if self._prev_lat is not None and self._prev_lon is not None:
                dist = self._haversine_distance(
                    self._prev_lat, self._prev_lon,
                    snapshot.latitude, snapshot.longitude
                )
                self._stats.total_distance_m += dist
            self._prev_lat = snapshot.latitude
            self._prev_lon = snapshot.longitude

        # Flight time tracking
        if snapshot.in_flight is not None:
            if snapshot.in_flight and not self._last_in_flight:
                # Just took off
                self._flight_start_time = snapshot.timestamp
            elif not snapshot.in_flight and self._last_in_flight:
                # Just landed
                if self._flight_start_time is not None:
                    self._stats.flight_time_s += snapshot.timestamp - self._flight_start_time
                    self._flight_start_time = None
            self._last_in_flight = snapshot.in_flight

    def _find_nearest_telemetry(self, timestamp: float) -> Optional[TelemetrySnapshot]:
        """Find telemetry snapshot closest to given timestamp."""
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

        Args:
            lat1, lon1: First coordinate (degrees)
            lat2, lon2: Second coordinate (degrees)

        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @property
    def is_recording(self) -> bool:
        """Check if a recording is in progress."""
        return self._log_file is not None

    @property
    def current_mission(self) -> Optional[str]:
        """Get the name of the current mission being recorded."""
        return self._current_mission

    @property
    def log_path(self) -> Optional[Path]:
        """Get the path to the current log file."""
        return self._log_path
