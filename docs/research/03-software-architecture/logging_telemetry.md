# Flight Data Logging & Telemetry Research

**Research Date:** 2026-04-10  
**Scope:** Comprehensive logging architecture for incident analysis, covering PX4 flight data logging, application telemetry, and forensic requirements  
**Status:** Reference Document for Implementation

---

## Table of Contents

1. [PX4 Flight Data Logging](#1-px4-flight-data-logging)
   - [Essential uORB Topics to Log](#essential-uorb-topics-to-log)
   - [SD Card Logging Configuration](#sd-card-logging-configuration)
   - [Logging Rates and Bandwidth](#logging-rates-and-bandwidth)
   - [Log Analysis Tools](#log-analysis-tools)

2. [Application Logging Design](#2-application-logging-design)
   - [Structured Logging for LLM Decisions](#structured-logging-for-llm-decisions)
   - [Telemetry Snapshots with Commands](#telemetry-snapshots-with-commands)
   - [Vision Pipeline Metrics](#vision-pipeline-metrics)
   - [Network Quality Logging](#network-quality-logging)

3. [Forensic Requirements](#3-forensic-requirements)
   - [Critical Data for Incident Reconstruction](#critical-data-for-incident-reconstruction)
   - [Log Rotation Without Data Loss](#log-rotation-without-data-loss)
   - [Correlating Multiple Log Sources](#correlating-multiple-log-sources)
   - [Offboard Log Streaming](#offboard-log-streaming)

4. [Python Logging Configuration](#4-python-logging-configuration)
   - [Structured Logger Implementation](#structured-logger-implementation)
   - [Async Logging for Telemetry](#async-logging-for-telemetry)
   - [Log Aggregation and Shipping](#log-aggregation-and-shipping)

5. [Implementation Checklist](#5-implementation-checklist)

---

## 1. PX4 Flight Data Logging

### Essential uORB Topics to Log

The PX4 logger captures uORB topic data to SD card for post-flight analysis. Critical topics for incident reconstruction:

#### Aircraft State (Flight Critical)
| Topic | Description | Recommended Rate | Priority |
|-------|-------------|------------------|----------|
| `vehicle_status` | Arming state, nav state, failsafe status | 5 Hz | CRITICAL |
| `vehicle_local_position` | Local position, velocity NED | 50 Hz | CRITICAL |
| `vehicle_global_position` | GPS position, altitude AMSL | 10 Hz | CRITICAL |
| `vehicle_attitude` | Quaternion attitude estimate | 250 Hz | CRITICAL |
| `vehicle_angular_velocity` | Roll/pitch/yaw rates | 250 Hz | HIGH |
| `vehicle_acceleration` | Linear acceleration NED | 250 Hz | HIGH |
| `vehicle_control_mode` | Flight mode, control state | 5 Hz | CRITICAL |

#### Control & Setpoints
| Topic | Description | Recommended Rate | Priority |
|-------|-------------|------------------|----------|
| `vehicle_rates_setpoint` | Rate controller target | 250 Hz | HIGH |
| `vehicle_attitude_setpoint` | Attitude target | 250 Hz | HIGH |
| `vehicle_local_position_setpoint` | Position control target | 50 Hz | HIGH |
| `vehicle_thrust_setpoint` | Thrust demands | 250 Hz | HIGH |
| `vehicle_torque_setpoint` | Torque demands | 250 Hz | HIGH |
| `actuator_outputs` | Final motor/servo outputs | 250 Hz | CRITICAL |

#### Estimation & Sensors
| Topic | Description | Recommended Rate | Priority |
|-------|-------------|------------------|----------|
| `estimator_status` | EKF health, innovation test ratios | 50 Hz | CRITICAL |
| `ekf2_timestamps` | EKF internal timing | 50 Hz | HIGH |
| `sensor_combined` | IMU data (accel + gyro) | 250 Hz | HIGH |
| `sensor_gps` | Raw GPS data | 10 Hz | CRITICAL |
| `sensor_baro` | Barometric pressure | 50 Hz | MEDIUM |
| `sensor_mag` | Magnetometer readings | 50 Hz | MEDIUM |
| `distance_sensor` | Range finder/LiDAR data | 20 Hz | MEDIUM |

#### Power & Battery
| Topic | Description | Recommended Rate | Priority |
|-------|-------------|------------------|----------|
| `battery_status` | Battery voltage, current, remaining | 1 Hz | CRITICAL |
| `system_power` | Board power supply status | 1 Hz | HIGH |

#### Offboard/Companion (LLM Control)
| Topic | Description | Recommended Rate | Priority |
|-------|-------------|------------------|----------|
| `offboard_control_mode` | Offboard control state | 5 Hz | CRITICAL |
| `vehicle_command` | MAVLink commands received | As received | CRITICAL |
| `vehicle_command_ack` | Command acknowledgments | As received | HIGH |
| `trajectory_setpoint` | Offboard trajectory targets | 50 Hz | HIGH |
| `timesync_status` | Companion computer sync | 1 Hz | MEDIUM |

#### Failsafe & Safety
| Topic | Description | Recommended Rate | Priority |
|-------|-------------|------------------|----------|
| `failsafe_flags` | Current failsafe state | 5 Hz | CRITICAL |
| `health_and_arming_checks` | Pre-flight check results | 1 Hz | HIGH |
| `safety` | Safety button state | 5 Hz | HIGH |
| `cpuload` | CPU load monitoring | 1 Hz | MEDIUM |

### SD Card Logging Configuration

#### Logger Module Parameters (`SDLOG_*`)

```
SDLOG_MODE = 0  # Logging disabled
SDLOG_MODE = 1  # From boot until disarm (default)
SDLOG_MODE = 2  # From boot until shutdown
SDLOG_MODE = 3  # From first arming until disarm
SDLOG_MODE = 4  # Logging based on AUX pin
SDLOG_MODE = 5  # From first arming until shutdown
```

#### Topic Subscription Configuration

The logger uses topic lists defined in:
- `/etc/logger/topics.txt` - Default topics
- `/fs/microsd/etc/logger/topics.txt` - Custom SD card override

Example custom topics file:
```
# High-frequency flight data
vehicle_attitude, 0  # 0 = topic's default rate
vehicle_local_position, 50
vehicle_rates_setpoint, 250
actuator_outputs, 250

# Control and estimation
estimator_status, 50
vehicle_control_mode, 5

# LLM-specific topics
offboard_control_mode, 5
vehicle_command, 0
vehicle_command_ack, 0
trajectory_setpoint, 50

# Power and failsafe
battery_status, 1
failsafe_flags, 5
cpuload, 1
```

#### SD Card Requirements

| Requirement | Specification | Notes |
|-------------|---------------|-------|
| Capacity | 8-32 GB | Larger cards supported but rarely needed |
| Speed Class | Class 10 minimum | UHS-I recommended for high-rate logging |
| File System | FAT32/exFAT | Auto-formatted by PX4 if needed |
| Log Format | ULog | Binary format, efficient and compressed |
| Average Size | ~1-5 MB/min | Varies based on topics/rates |
| Buffer Size | 16 KB write buffer | Configurable via `SDLOG_BUF` |

### Logging Rates and Bandwidth

#### Bandwidth Calculation

```python
def calculate_log_bandwidth(topics: list[dict]) -> float:
    """
    Calculate approximate SD card bandwidth usage.
    
    Args:
        topics: List of {name, size_bytes, rate_hz}
    
    Returns:
        Bandwidth in KB/s
    """
    total_bytes_per_sec = sum(
        t['size_bytes'] * t['rate_hz'] for t in topics
    )
    # ULog has ~50% compression overhead
    return total_bytes_per_sec / 1024 * 1.5

# Example calculation for typical flight
essential_topics = [
    {'name': 'vehicle_attitude', 'size': 48, 'rate': 250},
    {'name': 'vehicle_local_position', 'size': 72, 'rate': 50},
    {'name': 'estimator_status', 'size': 160, 'rate': 50},
    {'name': 'actuator_outputs', 'size': 32, 'rate': 250},
    {'name': 'sensor_combined', 'size': 48, 'rate': 250},
]

# Result: ~42 KB/s or ~2.5 MB/min
```

#### Rate Recommendations by Flight Phase

| Phase | Logging Mode | Topics |
|-------|--------------|--------|
| Pre-flight | Low rate | Status, health, battery (1-5 Hz) |
| Takeoff | High rate | All control topics (250 Hz) |
| Cruise | Medium rate | Navigation, status (10-50 Hz) |
| Offboard | Maximum rate | All topics at full rate |
| Landing | High rate | Control + position (50-250 Hz) |

### Log Analysis Tools

#### FlightPlot (Java-based)

```bash
# Download from: https://github.com/PX4/FlightPlot
# Standalone ULog viewer with real-time plot capabilities

# Features:
# - Multi-topic overlay plotting
# - CSV export
# - Custom expressions (math operations on fields)
# - FFT analysis for vibration detection

# Best for:
# - Quick visual inspection
# - Vibration analysis
# - Control loop tuning verification
```

#### MAVGCL (MAVLink Ground Control Log Analyzer)

```bash
# MAVGCL: https://github.com/ecmnet/MAVGCL
# JavaFX-based advanced analyzer

# Features:
# - 3D flight path visualization
# - EKF innovation analysis
# - Parameter change tracking
# - Video sync (if companion video available)
# - Model-based replay

# Best for:
# - Complex incident analysis
# - EKF health assessment
# - Flight path reconstruction
```

#### pyulog (Python Library)

```python
from pyulog import ULog
import pandas as pd

# Load PX4 log file
log = ULog('/path/to/log.ulg')

# Extract specific topic
data = log.get_dataset('vehicle_attitude')
df = pd.DataFrame(data.data)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='us')

# Common analysis patterns
def analyze_control_oscillations(log_path: str) -> dict:
    """Detect control oscillations from attitude data."""
    log = ULog(log_path)
    attitude = log.get_dataset('vehicle_attitude')
    rates = log.get_dataset('vehicle_angular_velocity')
    
    # Calculate roll/pitch rate variance
    roll_rates = rates.data['xyz[0]']
    pitch_rates = rates.data['xyz[1]']
    
    return {
        'roll_variance': np.var(roll_rates),
        'pitch_variance': np.var(pitch_rates),
        'oscillation_detected': np.var(roll_rates) > 10.0
    }

def extract_failsafe_events(log_path: str) -> list:
    """Extract all failsafe events with timestamps."""
    log = ULog(log_path)
    status = log.get_dataset('vehicle_status')
    
    events = []
    nav_states = status.data['nav_state']
    timestamps = status.data['timestamp']
    
    for i in range(1, len(nav_states)):
        if nav_states[i] != nav_states[i-1]:
            events.append({
                'timestamp': timestamps[i],
                'from_state': nav_states[i-1],
                'to_state': nav_states[i]
            })
    
    return events
```

#### Custom Analysis Scripts

```python
#!/usr/bin/env python3
"""
LLM Decision Correlator
Matches companion computer decisions with flight behavior.
"""

from pyulog import ULog
import json
from datetime import datetime

class IncidentAnalyzer:
    def __init__(self, px4_log_path: str, app_log_path: str):
        self.px4_log = ULog(px4_log_path)
        self.app_log = self._load_app_log(app_log_path)
    
    def _load_app_log(self, path: str) -> list:
        """Load structured application logs."""
        logs = []
        with open(path) as f:
            for line in f:
                logs.append(json.loads(line))
        return logs
    
    def correlate_decisions_with_flight_data(self):
        """
        Match LLM decision timestamps with PX4 attitude/position.
        Critical for understanding cause-effect in incidents.
        """
        # Get high-rate flight data
        attitude = self.px4_log.get_dataset('vehicle_attitude')
        local_pos = self.px4_log.get_dataset('vehicle_local_position')
        
        # Match LLM decisions (1-10 Hz) with flight data (250 Hz)
        correlations = []
        for decision in self.app_log:
            if decision.get('type') == 'llm_decision':
                ts = decision['timestamp']
                
                # Find nearest attitude sample
                attitude_idx = self._find_nearest(
                    attitude.data['timestamp'], ts
                )
                
                correlations.append({
                    'decision': decision['decision'],
                    'attitude_at_decision': {
                        'roll': attitude.data['q[0]'][attitude_idx],
                        'pitch': attitude.data['q[1]'][attitude_idx],
                    },
                    'position_at_decision': {
                        'x': local_pos.data['x'][attitude_idx],
                        'y': local_pos.data['y'][attitude_idx],
                        'z': local_pos.data['z'][attitude_idx],
                    }
                })
        
        return correlations
    
    def generate_incident_report(self, start_time: float, end_time: float):
        """Generate focused report for incident window."""
        return {
            'time_window': {'start': start_time, 'end': end_time},
            'flight_mode_changes': self._extract_mode_changes(start_time, end_time),
            'llm_decisions': self._extract_decisions(start_time, end_time),
            'failsafe_activations': self._extract_failsafes(start_time, end_time),
            'control_outputs': self._extract_controls(start_time, end_time),
        }
```

---

## 2. Application Logging Design

### Structured Logging for LLM Decisions

LLM-based control requires comprehensive logging for debugging and accountability.

#### Log Schema

```python
from dataclasses import dataclass
from typing import Optional, Any
from enum import Enum
import json
from datetime import datetime

class DecisionType(Enum):
    NAVIGATION = "navigation"
    OBSTACLE_AVOIDANCE = "obstacle_avoidance"
    EMERGENCY = "emergency"
    MODE_CHANGE = "mode_change"
    MISSION_UPDATE = "mission_update"

class DecisionOutcome(Enum):
    SUCCESS = "success"
    REJECTED_SAFETY = "rejected_safety"
    REJECTED_FEASIBLE = "rejected_feasible"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class LLMDecisionLog:
    """Structured log entry for LLM decisions."""
    
    # Identification
    decision_id: str  # UUID for tracking
    timestamp: str  # ISO 8601
    flight_uuid: str  # PX4 COM_FLIGHT_UUID
    
    # Context
    decision_type: DecisionType
    flight_mode: str  # Current PX4 flight mode
    position_ned: tuple[float, float, float]
    attitude_quaternion: tuple[float, float, float, float]
    velocity_ned: tuple[float, float, float]
    
    # LLM Input
    prompt_version: str  # Prompt template version
    context_summary: str  # Summarized input context
    image_references: list[str]  # Vision input frame IDs
    
    # LLM Output
    raw_response: str  # Complete LLM output
    parsed_command: dict  # Structured command extracted
    confidence_score: float  # 0.0 - 1.0
    
    # Validation
    safety_check_passed: bool
    feasibility_check_passed: bool
    rejection_reason: Optional[str]
    
    # Execution
    outcome: DecisionOutcome
    execution_timestamp: Optional[str]
    execution_duration_ms: float
    
    # PX4 Feedback
    command_ack: Optional[str]  # MAVLink ACK result
    actual_result: Optional[str]  # Telemetry-verified result
    
    def to_json(self) -> str:
        return json.dumps({
            'event_type': 'llm_decision',
            'version': '1.0',
            **self.__dict__
        }, default=str)

# Usage example
decision_logger = logging.getLogger('llm_decisions')
decision_logger.setLevel(logging.INFO)

# File handler with rotation
handler = RotatingFileHandler(
    'logs/llm_decisions.jsonl',
    maxBytes=100*1024*1024,  # 100 MB
    backupCount=10
)
decision_logger.addHandler(handler)

# Log a decision
log_entry = LLMDecisionLog(
    decision_id=str(uuid.uuid4()),
    timestamp=datetime.utcnow().isoformat(),
    flight_uuid=current_flight_uuid,
    decision_type=DecisionType.NAVIGATION,
    flight_mode='OFFBOARD',
    position_ned=(10.0, 5.0, -3.0),
    attitude_quaternion=(0.98, 0.01, 0.01, 0.01),
    velocity_ned=(2.0, 1.0, 0.0),
    prompt_version='v2.3_nav_vision',
    context_summary='Obstacle detected at 5m north, re-routing west',
    image_references=['frame_0001234', 'frame_0001235'],
    raw_response=llm_response,
    parsed_command={'type': 'setpoint', 'north': 8.0, 'east': 8.0},
    confidence_score=0.87,
    safety_check_passed=True,
    feasibility_check_passed=True,
    rejection_reason=None,
    outcome=DecisionOutcome.SUCCESS,
    execution_timestamp=datetime.utcnow().isoformat(),
    execution_duration_ms=145.2,
    command_ack='ACCEPTED',
    actual_result='setpoint_reached'
)

decision_logger.info(log_entry.to_json())
```

### Telemetry Snapshots with Commands

Each command sent to the aircraft should capture complete system state.

```python
@dataclass
class TelemetrySnapshot:
    """Complete system state at command time."""
    
    timestamp: str
    flight_uuid: str
    
    # Aircraft State
    position_ned: dict  # {north, east, down}
    velocity_ned: dict  # {north, east, down}
    attitude: dict  # {q_w, q_x, q_y, q_z} or {roll, pitch, yaw}
    angular_velocity: dict  # {roll, pitch, yaw} rad/s
    
    # Control State
    flight_mode: str
    offboard_active: bool
    arming_state: str
    
    # EKF Health
    local_position_valid: bool
    global_position_valid: bool
    home_position_valid: bool
    position_test_ratio: float
    velocity_test_ratio: float
    
    # Failsafe
    failsafe_active: bool
    failsafe_flags: dict  # Individual failsafe states
    
    # Power
    battery_remaining: float  # 0.0 - 1.0
    battery_voltage: float
    battery_current: float
    
    # Communication
    link_quality: float  # 0.0 - 1.0
    rtt_ms: float
    packets_lost: int
    
    # Vision/LLM
    vision_processing_time_ms: float
    last_detection_timestamp: Optional[str]
    active_tracks: list[dict]  # Tracked objects
    
    # Command Context
    command_id: str
    command_type: str
    command_parameters: dict

class TelemetryLogger:
    def __init__(self, log_dir: str = 'logs/telemetry'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current flight log file
        self.current_file: Optional[Path] = None
        self.snapshot_buffer: list[dict] = []
        self.buffer_size = 100
    
    async def capture_snapshot(self, drone, command_info: dict) -> TelemetrySnapshot:
        """Capture complete telemetry snapshot."""
        
        # Gather all telemetry concurrently
        position_task = asyncio.create_task(
            self._get_position(drone)
        )
        health_task = asyncio.create_task(
            self._get_health(drone)
        )
        battery_task = asyncio.create_task(
            self._get_battery(drone)
        )
        
        position = await position_task
        health = await health_task
        battery = await battery_task
        
        snapshot = TelemetrySnapshot(
            timestamp=datetime.utcnow().isoformat(),
            flight_uuid=await self._get_flight_uuid(drone),
            position_ned={'north': position.north_m, 
                         'east': position.east_m,
                         'down': position.down_m},
            velocity_ned={'north': position.velocity_north_m_s,
                         'east': position.velocity_east_m_s,
                         'down': position.velocity_down_m_s},
            attitude={'q_w': position.q[0], 'q_x': position.q[1],
                     'q_y': position.q[2], 'q_z': position.q[3]},
            angular_velocity={'roll': 0, 'pitch': 0, 'yaw': 0},  # From rates topic
            flight_mode=str(await self._get_flight_mode(drone)),
            offboard_active=health.is_offboard_mode,
            arming_state=await self._get_arming_state(drone),
            local_position_valid=health.is_local_position_ok,
            global_position_valid=health.is_global_position_ok,
            home_position_valid=health.is_home_position_ok,
            position_test_ratio=0.0,  # From estimator_status
            velocity_test_ratio=0.0,
            failsafe_active=await self._get_failsafe_state(drone),
            failsafe_flags={},  # From failsafe_flags topic
            battery_remaining=battery.remaining_percent,
            battery_voltage=battery.voltage_v,
            battery_current=battery.current_battery_a,
            link_quality=await self._get_link_quality(drone),
            rtt_ms=await self._get_rtt(drone),
            packets_lost=0,  # Track from MAVLink
            vision_processing_time_ms=self._get_vision_latency(),
            last_detection_timestamp=self._get_last_detection(),
            active_tracks=self._get_active_tracks(),
            command_id=command_info['id'],
            command_type=command_info['type'],
            command_parameters=command_info['params']
        )
        
        await self._write_snapshot(snapshot)
        return snapshot
    
    async def _write_snapshot(self, snapshot: TelemetrySnapshot):
        """Buffer and write snapshots efficiently."""
        self.snapshot_buffer.append(snapshot.__dict__)
        
        if len(self.snapshot_buffer) >= self.buffer_size:
            await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Write buffered snapshots to disk."""
        if not self.current_file:
            self.current_file = self.log_dir / f"telemetry_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        
        with open(self.current_file, 'a') as f:
            for snapshot in self.snapshot_buffer:
                f.write(json.dumps(snapshot, default=str) + '\n')
        
        self.snapshot_buffer.clear()
```

### Vision Pipeline Metrics

```python
@dataclass
class VisionPipelineMetrics:
    """Performance and quality metrics for vision processing."""
    
    # Timing
    frame_timestamp: str
    frame_id: str
    capture_latency_ms: float
    inference_latency_ms: float
    total_pipeline_ms: float
    
    # Detection Results
    detections: list[dict]  # [{class, confidence, bbox}, ...]
    tracks: list[dict]  # [{track_id, age, predicted_position}, ...]
    
    # Quality Metrics
    image_quality_score: float  # Blur/noise detection
    exposure_level: float
    
    # Performance
    model_fps: float
    gpu_utilization: float
    memory_used_mb: float
    
    # LLM Integration
    prompt_tokens: int
    completion_tokens: int
    llm_latency_ms: float

class VisionMetricsLogger:
    def __init__(self):
        self.metrics_log = logging.getLogger('vision_metrics')
        
    def log_frame_processing(self, metrics: VisionPipelineMetrics):
        """Log vision pipeline performance for each frame."""
        self.metrics_log.info(json.dumps({
            'event_type': 'vision_frame',
            'timestamp': datetime.utcnow().isoformat(),
            **metrics.__dict__
        }, default=str))
    
    def log_detection_event(self, detection: dict, decision_context: dict):
        """Log significant detection events with decision context."""
        self.metrics_log.warning(json.dumps({
            'event_type': 'significant_detection',
            'severity': detection.get('severity', 'info'),
            'detection': detection,
            'decision_context': decision_context,
            'timestamp': datetime.utcnow().isoformat()
        }, default=str))
```

### Network Quality Logging

```python
@dataclass
class NetworkQualityMetrics:
    """MAVLink connection quality metrics."""
    
    timestamp: str
    connection_type: str  # 'udp', 'tcp', 'serial'
    
    # Link Statistics
    bytes_received: int
    bytes_sent: int
    messages_received: int
    messages_sent: int
    
    # Quality Metrics
    packet_loss_percent: float
    latency_ms: float
    jitter_ms: float
    
    # MAVLink Specific
    sysid: int
    compid: int
    heartbeat_interval_ms: float
    last_heartbeat_age_ms: float
    
    # Streaming Rates
    telemetry_hz: float
    command_hz: float

class NetworkQualityLogger:
    """Continuous network quality monitoring."""
    
    def __init__(self, drone):
        self.drone = drone
        self.metrics_history: deque = deque(maxlen=1000)
        
    async def monitor_loop(self):
        """Background task for continuous monitoring."""
        while True:
            metrics = await self._collect_metrics()
            self.metrics_history.append(metrics)
            
            # Log anomalies
            if metrics.packet_loss_percent > 5:
                logging.warning(f"High packet loss: {metrics.packet_loss_percent}%")
            
            if metrics.latency_ms > 200:
                logging.warning(f"High latency: {metrics.latency_ms}ms")
            
            await asyncio.sleep(1.0)
    
    async def _collect_metrics(self) -> NetworkQualityMetrics:
        """Collect current network metrics."""
        # Implementation depends on MAVSDK statistics access
        return NetworkQualityMetrics(
            timestamp=datetime.utcnow().isoformat(),
            connection_type='udp',
            bytes_received=0,  # From MAVSDK stats
            bytes_sent=0,
            messages_received=0,
            messages_sent=0,
            packet_loss_percent=0.0,
            latency_ms=await self._measure_rtt(),
            jitter_ms=0.0,
            sysid=1,
            compid=1,
            heartbeat_interval_ms=1000.0,
            last_heartbeat_age_ms=0.0,
            telemetry_hz=10.0,
            command_hz=2.0
        )
    
    def get_link_health_report(self) -> dict:
        """Generate link health summary for incident analysis."""
        if not self.metrics_history:
            return {'status': 'no_data'}
        
        recent = list(self.metrics_history)[-100:]  # Last 100 samples
        
        return {
            'status': 'healthy' if all(
                m.packet_loss_percent < 1 for m in recent
            ) else 'degraded',
            'avg_latency_ms': sum(m.latency_ms for m in recent) / len(recent),
            'max_latency_ms': max(m.latency_ms for m in recent),
            'avg_packet_loss': sum(m.packet_loss_percent for m in recent) / len(recent),
            'dropout_events': sum(
                1 for i in range(1, len(recent))
                if recent[i].latency_ms > 500 and recent[i-1].latency_ms < 100
            )
        }
```

---

## 3. Forensic Requirements

### Critical Data for Incident Reconstruction

#### Tier 1: Must-Have (Legal/Investigation Critical)

| Data Category | Retention Period | Storage |
|---------------|------------------|---------|
| PX4 ULog files | Permanent | SD card + cloud backup |
| LLM decision logs | Permanent | Local + remote archive |
| Command history | Permanent | Immutable append-only |
| Telemetry snapshots | 90 days | Rotating local + 1 year cloud |
| Video recordings | 30 days | Cloud storage |
| Network logs | 30 days | Local rotating |

#### Timeline Reconstruction Data

```python
class IncidentReconstructor:
    """Reconstruct incident timeline from multiple log sources."""
    
    REQUIRED_DATA_SOURCES = [
        'px4_ulog',           # Aircraft state at 250Hz
        'companion_commands',  # Commands sent to PX4
        'llm_decisions',       # Decision-making process
        'vision_detections',   # Perception inputs
        'network_quality',     # Communication state
        'system_logs',         # OS/Application events
    ]
    
    def reconstruct_incident(
        self,
        incident_time: datetime,
        window_seconds: int = 60
    ) -> dict:
        """
        Reconstruct incident timeline from all sources.
        
        Returns unified timeline with all events correlated.
        """
        start_time = incident_time - timedelta(seconds=window_seconds/2)
        end_time = incident_time + timedelta(seconds=window_seconds/2)
        
        timeline = []
        
        # 1. Load PX4 high-rate data
        px4_events = self._load_px4_events(start_time, end_time)
        for event in px4_events:
            timeline.append({
                'timestamp': event['timestamp'],
                'source': 'px4',
                'type': event['topic'],
                'data': event['fields'],
                'priority': 'critical'
            })
        
        # 2. Load LLM decisions
        llm_events = self._load_llm_decisions(start_time, end_time)
        for event in llm_events:
            timeline.append({
                'timestamp': event['timestamp'],
                'source': 'llm',
                'type': f"decision_{event['decision_type']}",
                'data': {
                    'decision': event['parsed_command'],
                    'confidence': event['confidence_score'],
                    'outcome': event['outcome']
                },
                'priority': 'high'
            })
        
        # 3. Load network events
        network_events = self._load_network_events(start_time, end_time)
        for event in network_events:
            timeline.append({
                'timestamp': event['timestamp'],
                'source': 'network',
                'type': 'link_quality',
                'data': {
                    'latency': event['latency_ms'],
                    'packet_loss': event['packet_loss_percent']
                },
                'priority': 'medium'
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return {
            'incident_window': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'events': timeline,
            'event_count': len(timeline),
            'sources': list(set(e['source'] for e in timeline))
        }
```

#### Causal Chain Analysis

```python
def analyze_causal_chain(events: list[dict]) -> list[dict]:
    """
    Identify causal relationships between events.
    
    Example causal chains:
    1. vision_detection -> llm_decision -> px4_command -> attitude_change
    2. network_latency_spike -> command_delay -> setpoint_timeout -> failsafe
    3. battery_low -> rtl_triggered -> mode_change -> landing
    """
    causal_chains = []
    
    # Find root cause events
    root_events = [
        e for e in events
        if e['type'] in ['vision_detection', 'network_dropout', 
                        'battery_critical', 'gps_loss']
    ]
    
    for root in root_events:
        chain = trace_consequences(root, events)
        if len(chain) > 1:
            causal_chains.append({
                'root_cause': root,
                'consequences': chain[1:],
                'time_span_ms': (chain[-1]['timestamp'] - root['timestamp']).total_seconds() * 1000
            })
    
    return causal_chains

def trace_consequences(root_event: dict, all_events: list[dict]) -> list[dict]:
    """Trace consequences from a root event."""
    chain = [root_event]
    current = root_event
    
    # Follow causal links forward in time
    for event in all_events:
        if event['timestamp'] <= current['timestamp']:
            continue
        
        # Check if event is consequence of current
        if is_consequence(current, event):
            chain.append(event)
            current = event
            
        # Stop at significant outcome
        if event['type'] in ['crash', 'failsafe_triggered', 'emergency_land']:
            break
    
    return chain
```

### Log Rotation Without Data Loss

```python
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta

class SecureLogRotation:
    """
    Log rotation that ensures no data loss during rotation.
    Critical for forensic integrity.
    """
    
    def __init__(self, log_dir: str, max_size_mb: int = 100):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size_mb * 1024 * 1024
        
        # Active log file
        self.active_file: Optional[Path] = None
        self._lock = asyncio.Lock()
    
    async def rotate_if_needed(self) -> Optional[Path]:
        """
        Check if rotation needed and perform atomic rotation.
        
        Returns path to rotated file if rotation occurred.
        """
        async with self._lock:
            if not self.active_file or not self.active_file.exists():
                return None
            
            current_size = self.active_file.stat().st_size
            
            if current_size < self.max_size:
                return None
            
            # Atomic rotation
            rotated = self._perform_rotation()
            return rotated
    
    def _perform_rotation(self) -> Path:
        """Perform atomic log rotation."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rotated_name = f"{self.active_file.stem}_{timestamp}{self.active_file.suffix}"
        rotated_path = self.log_dir / 'archive' / rotated_name
        
        # Ensure archive directory exists
        rotated_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move atomically
        shutil.move(str(self.active_file), str(rotated_path))
        
        # Compress in background
        asyncio.create_task(self._compress_async(rotated_path))
        
        # Create new active file
        self.active_file = self.log_dir / f"{self.active_file.stem}{self.active_file.suffix}"
        
        return rotated_path
    
    async def _compress_async(self, file_path: Path):
        """Compress rotated log in background."""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,  # Default executor
            self._compress_file,
            file_path,
            compressed_path
        )
        
        # Remove original after successful compression
        file_path.unlink()
    
    @staticmethod
    def _compress_file(src: Path, dst: Path):
        """Synchronous compression."""
        with open(src, 'rb') as f_in:
            with gzip.open(dst, 'wb', compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    async def cleanup_old_logs(self, retention_days: int = 30):
        """Clean up logs older than retention period."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        archive_dir = self.log_dir / 'archive'
        if not archive_dir.exists():
            return
        
        for log_file in archive_dir.glob('*.jsonl.gz'):
            # Extract timestamp from filename
            try:
                file_time = datetime.strptime(
                    log_file.stem.split('_')[-2] + log_file.stem.split('_')[-1],
                    '%Y%m%d%H%M%S'
                )
                
                if file_time < cutoff:
                    log_file.unlink()
                    logging.info(f"Removed old log: {log_file}")
            except (ValueError, IndexError):
                continue
```

### Correlating Multiple Log Sources

```python
class LogCorrelator:
    """
    Correlate events across PX4 ULog, companion logs, and vision logs.
    
    Uses timestamp synchronization and causal analysis.
    """
    
    def __init__(self):
        self.time_offsets = {}  # Source -> offset from reference
    
    def correlate_logs(
        self,
        px4_log_path: str,
        companion_log_path: str,
        vision_log_path: str
    ) -> dict:
        """
        Produce unified event timeline from multiple sources.
        """
        # Load all logs
        px4_events = self._parse_ulog(px4_log_path)
        companion_events = self._parse_jsonl(companion_log_path)
        vision_events = self._parse_jsonl(vision_log_path)
        
        # Synchronize timestamps
        reference_time = px4_events[0]['timestamp'] if px4_events else None
        
        for event in companion_events:
            event['timestamp'] = self._sync_timestamp(
                event['timestamp'], 'companion', reference_time
            )
        
        for event in vision_events:
            event['timestamp'] = self._sync_timestamp(
                event['timestamp'], 'vision', reference_time
            )
        
        # Merge and sort
        all_events = px4_events + companion_events + vision_events
        all_events.sort(key=lambda x: x['timestamp'])
        
        # Add correlation IDs
        correlated = self._add_correlation_ids(all_events)
        
        return {
            'event_count': len(correlated),
            'time_range': {
                'start': correlated[0]['timestamp'] if correlated else None,
                'end': correlated[-1]['timestamp'] if correlated else None
            },
            'events': correlated,
            'correlation_stats': self._compute_correlation_stats(correlated)
        }
    
    def _add_correlation_ids(self, events: list[dict]) -> list[dict]:
        """Add correlation IDs linking related events."""
        
        # Track in-flight decisions and commands
        pending_decisions: dict[str, str] = {}  # decision_id -> correlation_id
        pending_commands: dict[str, str] = {}   # command_id -> correlation_id
        
        for event in events:
            event['correlations'] = []
            
            if event['source'] == 'llm' and event.get('decision_id'):
                corr_id = str(uuid.uuid4())[:8]
                event['correlation_id'] = corr_id
                pending_decisions[event['decision_id']] = corr_id
                
            elif event['source'] == 'companion' and event.get('command_id'):
                # Link to decision that generated this command
                for dec_id, corr_id in pending_decisions.items():
                    if self._command_from_decision(event, dec_id):
                        event['correlation_id'] = corr_id
                        event['correlations'].append(f"decision:{dec_id}")
                        pending_commands[event['command_id']] = corr_id
                        break
                        
            elif event['source'] == 'px4' and event.get('type') == 'command_ack':
                # Link to command that triggered this ACK
                for cmd_id, corr_id in pending_commands.items():
                    if self._ack_matches_command(event, cmd_id):
                        event['correlation_id'] = corr_id
                        event['correlations'].append(f"command:{cmd_id}")
                        break
        
        return events
```

### Offboard Log Streaming

```python
class LogStreamer:
    """
    Stream logs offboard in real-time for remote monitoring.
    Critical for incidents where SD card is lost/damaged.
    """
    
    def __init__(self, config: dict):
        self.buffer_size = config.get('buffer_size', 10000)
        self.batch_size = config.get('batch_size', 100)
        self.flush_interval_sec = config.get('flush_interval', 5)
        
        self.buffer: deque = deque(maxlen=self.buffer_size)
        self.last_flush = time.time()
        
        # Upload destinations
        self.destinations: list[LogDestination] = []
        if config.get('s3_bucket'):
            self.destinations.append(S3Destination(config['s3_bucket']))
        if config.get('websocket_url'):
            self.destinations.append(WebSocketDestination(config['websocket_url']))
    
    async def stream_event(self, event: dict):
        """Add event to stream buffer."""
        event['_streamed_at'] = datetime.utcnow().isoformat()
        self.buffer.append(event)
        
        # Flush if buffer full or interval elapsed
        if (len(self.buffer) >= self.batch_size or 
            time.time() - self.last_flush > self.flush_interval_sec):
            await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush buffer to all destinations."""
        if not self.buffer:
            return
        
        batch = list(self.buffer)
        self.buffer.clear()
        
        # Upload to all destinations concurrently
        tasks = [
            dest.upload_batch(batch)
            for dest in self.destinations
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle failures
        for dest, result in zip(self.destinations, results):
            if isinstance(result, Exception):
                logging.error(f"Log stream failed to {dest}: {result}")
                # Queue for retry
                await dest.queue_for_retry(batch)
        
        self.last_flush = time.time()
    
    async def start_px4_ulog_stream(self, drone):
        """
        Stream PX4 ULog data via MAVLink LOG_DATA messages.
        Requires LOG_BACKEND_MAVLINK enabled on PX4.
        """
        # Request log streaming via MAVLink
        # This streams the actual .ulg file data offboard
        pass

class S3Destination:
    """AWS S3 upload destination."""
    
    def __init__(self, bucket: str, prefix: str = 'logs/'):
        self.bucket = bucket
        self.prefix = prefix
        import boto3
        self.client = boto3.client('s3')
    
    async def upload_batch(self, events: list[dict]):
        """Upload batch of log events to S3."""
        timestamp = datetime.now().strftime('%Y/%m/%d/%H%M%S')
        key = f"{self.prefix}{timestamp}_{uuid.uuid4().hex[:8]}.jsonl.gz"
        
        # Compress
        data = '\n'.join(json.dumps(e) for e in events).encode()
        compressed = gzip.compress(data)
        
        # Upload
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._upload,
            key,
            compressed
        )
    
    def _upload(self, key: str, data: bytes):
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentEncoding='gzip',
            ContentType='application/x-jsonlines'
        )
```

---

## 4. Python Logging Configuration

### Structured Logger Implementation

```python
"""
Production-grade structured logging configuration.
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime
from typing import Any
from pythonjsonlogger import jsonlogger  # pip install python-json-logger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['source'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }
        
        # Add flight UUID if available
        if hasattr(record, 'flight_uuid'):
            log_record['flight_uuid'] = record.flight_uuid

class ContextFilter(logging.Filter):
    """Add contextual information to all log records."""
    
    def __init__(self, flight_uuid: str = None):
        super().__init__()
        self.flight_uuid = flight_uuid
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.flight_uuid = self.flight_uuid
        return True

def setup_logging(
    log_dir: str = 'logs',
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    flight_uuid: str = None
) -> dict[str, logging.Logger]:
    """
    Setup comprehensive logging configuration.
    
    Returns dict of configured loggers.
    """
    from pathlib import Path
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Context filter
    context_filter = ContextFilter(flight_uuid)
    
    # Console handler - human readable for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )
    console_handler.setFormatter(console_format)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)
    
    # JSON file handler - structured for analysis
    json_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/application.jsonl',
        maxBytes=100*1024*1024,  # 100 MB
        backupCount=10
    )
    json_handler.setLevel(file_level)
    json_formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    json_handler.setFormatter(json_formatter)
    json_handler.addFilter(context_filter)
    root_logger.addHandler(json_handler)
    
    # Error file handler - errors only
    error_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/errors.jsonl',
        maxBytes=50*1024*1024,
        backupCount=20
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    error_handler.addFilter(context_filter)
    root_logger.addHandler(error_handler)
    
    # Configure specific loggers
    loggers = {
        'llm': _setup_component_logger(log_dir, 'llm_decisions', context_filter),
        'telemetry': _setup_component_logger(log_dir, 'telemetry', context_filter),
        'vision': _setup_component_logger(log_dir, 'vision', context_filter),
        'network': _setup_component_logger(log_dir, 'network', context_filter),
        'commands': _setup_component_logger(log_dir, 'commands', context_filter),
    }
    
    return loggers

def _setup_component_logger(
    log_dir: str,
    name: str,
    context_filter: ContextFilter
) -> logging.Logger:
    """Setup component-specific logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Don't bubble to root
    
    # Component-specific file
    handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/{name}.jsonl',
        maxBytes=100*1024*1024,
        backupCount=10
    )
    handler.setFormatter(CustomJsonFormatter())
    handler.addFilter(context_filter)
    logger.addHandler(handler)
    
    return logger
```

### Async Logging for Telemetry

```python
import asyncio
from asyncio import Queue
from dataclasses import asdict

class AsyncTelemetryLogger:
    """
    High-performance async logger for high-rate telemetry.
    
    Uses queue-based buffering to avoid blocking telemetry threads.
    """
    
    def __init__(self, log_path: str, max_queue_size: int = 10000):
        self.log_path = log_path
        self.queue: Queue = Queue(maxsize=max_queue_size)
        self.writer_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self.dropped_count = 0
        
    async def start(self):
        """Start the background writer task."""
        self.writer_task = asyncio.create_task(self._writer_loop())
        
    async def stop(self):
        """Stop logger and flush remaining events."""
        self._shutdown = True
        await self.queue.put(None)  # Sentinel
        if self.writer_task:
            await self.writer_task
    
    def log_snapshot(self, snapshot: TelemetrySnapshot):
        """
        Log telemetry snapshot (non-blocking).
        
        May drop events if queue is full to prevent memory issues.
        """
        try:
            self.queue.put_nowait(snapshot)
        except asyncio.QueueFull:
            self.dropped_count += 1
            if self.dropped_count % 100 == 1:
                logging.warning(f"Telemetry queue full, dropped {self.dropped_count} events")
    
    async def _writer_loop(self):
        """Background task that writes events to disk."""
        buffer: list[TelemetrySnapshot] = []
        buffer_limit = 100
        flush_interval = 1.0  # seconds
        
        last_flush = asyncio.get_event_loop().time()
        
        with open(self.log_path, 'a') as f:
            while not self._shutdown or not self.queue.empty():
                try:
                    # Wait for event with timeout
                    timeout = max(0, flush_interval - (asyncio.get_event_loop().time() - last_flush))
                    snapshot = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    
                    if snapshot is None:  # Shutdown sentinel
                        break
                    
                    buffer.append(snapshot)
                    
                    # Flush if buffer full
                    if len(buffer) >= buffer_limit:
                        await self._flush_buffer(f, buffer)
                        buffer.clear()
                        last_flush = asyncio.get_event_loop().time()
                        
                except asyncio.TimeoutError:
                    # Periodic flush
                    if buffer:
                        await self._flush_buffer(f, buffer)
                        buffer.clear()
                        last_flush = asyncio.get_event_loop().time()
            
            # Final flush
            if buffer:
                await self._flush_buffer(f, buffer)
    
    async def _flush_buffer(self, file_handle, buffer: list[TelemetrySnapshot]):
        """Write buffered snapshots to file."""
        loop = asyncio.get_event_loop()
        
        # Convert to JSON lines
        lines = [json.dumps(asdict(s), default=str) for s in buffer]
        data = '\n'.join(lines) + '\n'
        
        # Write in executor to avoid blocking
        await loop.run_in_executor(None, file_handle.write, data)
        file_handle.flush()
```

### Log Aggregation and Shipping

```python
"""
Log aggregation and shipping configuration for production.
Supports multiple backends: Elasticsearch, S3, custom HTTP.
"""

from abc import ABC, abstractmethod
import aiohttp
from elasticsearch import AsyncElasticsearch

class LogShipper(ABC):
    """Abstract base for log shipping destinations."""
    
    @abstractmethod
    async def ship(self, logs: list[dict]) -> bool:
        """Ship logs to destination. Returns success."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if destination is reachable."""
        pass

class ElasticsearchShipper(LogShipper):
    """Ship logs to Elasticsearch."""
    
    def __init__(self, hosts: list[str], index_prefix: str = 'drone-logs'):
        self.es = AsyncElasticsearch(hosts=hosts)
        self.index_prefix = index_prefix
    
    async def ship(self, logs: list[dict]) -> bool:
        """Bulk index logs to Elasticsearch."""
        if not logs:
            return True
        
        # Group by date for index naming
        from collections import defaultdict
        by_date = defaultdict(list)
        
        for log in logs:
            date = log.get('timestamp', datetime.now().isoformat())[:10]
            by_date[date].append(log)
        
        # Bulk index each date group
        for date, date_logs in by_date.items():
            index = f"{self.index_prefix}-{date}"
            
            actions = [
                {'_index': index, '_source': log}
                for log in date_logs
            ]
            
            try:
                await self.es.bulk(body=actions)
            except Exception as e:
                logging.error(f"ES bulk index failed: {e}")
                return False
        
        return True
    
    async def health_check(self) -> bool:
        try:
            return await self.es.ping()
        except:
            return False

class HttpWebhookShipper(LogShipper):
    """Ship logs to custom HTTP webhook."""
    
    def __init__(self, webhook_url: str, headers: dict = None):
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def ship(self, logs: list[dict]) -> bool:
        session = await self._get_session()
        
        try:
            async with session.post(
                self.webhook_url,
                headers=self.headers,
                json={'logs': logs, 'batch_size': len(logs)}
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logging.error(f"Webhook ship failed: {e}")
            return False
    
    async def health_check(self) -> bool:
        # Implement HEAD request check
        return True

class LogAggregationManager:
    """
    Manages multiple log shippers with failover.
    """
    
    def __init__(self, shippers: list[LogShipper]):
        self.shippers = shippers
        self.failed_shippers: set = set()
        self.retry_queue: deque = deque(maxlen=10000)
    
    async def ship_batch(self, logs: list[dict]):
        """Ship to all healthy destinations."""
        if not logs:
            return
        
        # Try each shipper
        for shipper in self.shippers:
            if shipper in self.failed_shippers:
                # Skip failed, will retry later
                continue
            
            success = await shipper.ship(logs)
            
            if not success:
                self.failed_shippers.add(shipper)
                logging.warning(f"Shipper {shipper} failed, queuing for retry")
                
                # Queue for retry
                for log in logs:
                    self.retry_queue.append((shipper, log))
    
    async def retry_failed(self):
        """Background task to retry failed shipments."""
        while True:
            await asyncio.sleep(60)  # Retry every minute
            
            # Check health of failed shippers
            for shipper in list(self.failed_shippers):
                if await shipper.health_check():
                    self.failed_shippers.remove(shipper)
                    logging.info(f"Shipper {shipper} recovered")
            
            # Retry queued items
            retry_batch = []
            while self.retry_queue and len(retry_batch) < 100:
                shipper, log = self.retry_queue.popleft()
                if shipper not in self.failed_shippers:
                    retry_batch.append((shipper, log))
            
            # Group by shipper and retry
            from collections import defaultdict
            by_shipper = defaultdict(list)
            for shipper, log in retry_batch:
                by_shipper[shipper].append(log)
            
            for shipper, logs in by_shipper.items():
                success = await shipper.ship(logs)
                if not success:
                    # Re-queue
                    for log in logs:
                        self.retry_queue.append((shipper, log))
```

---

## 5. Implementation Checklist

### PX4 Configuration
- [ ] Configure SDLOG_MODE for appropriate logging trigger
- [ ] Create custom logger_topics.txt with LLM-specific topics
- [ ] Enable LOG_BACKEND_MAVLINK for offboard streaming
- [ ] Verify SD card speed class (Class 10 minimum)
- [ ] Test log continuity during arm/disarm cycles
- [ ] Configure LOG_FILE_DSRMACT for disarm behavior

### Companion Computer Logging
- [ ] Implement structured JSON logging for all components
- [ ] Setup async telemetry snapshot capture
- [ ] Configure log rotation with compression
- [ ] Implement offboard log streaming
- [ ] Setup multiple shipping destinations
- [ ] Add correlation ID generation for cross-source tracking

### Forensic Readiness
- [ ] Document all log formats and schemas
- [ ] Create log correlation scripts
- [ ] Setup automated log backup to cloud storage
- [ ] Implement incident reconstruction tools
- [ ] Test recovery procedures for corrupted logs
- [ ] Document chain of custody for legal requirements

### Testing & Validation
- [ ] Verify PX4 ULog integrity after hard shutdown
- [ ] Test log rotation under high-load scenarios
- [ ] Validate correlation accuracy across sources
- [ ] Test offboard streaming during communication loss
- [ ] Verify forensic timeline reconstruction accuracy
- [ ] Load test with maximum logging rates

### Monitoring & Alerting
- [ ] Monitor SD card remaining capacity
- [ ] Alert on log write errors
- [ ] Track telemetry snapshot queue depth
- [ ] Monitor log shipping success rates
- [ ] Alert on log destination failures

---

## References

- PX4 Logger Documentation: https://docs.px4.io/main/en/dev_log/
- ULog Format Specification: https://docs.px4.io/main/en/dev_log/ulog_file_format.html
- pyulog Library: https://github.com/PX4/pyulog
- MAVGCL Analyzer: https://github.com/ecmnet/MAVGCL
- FlightPlot Tool: https://github.com/PX4/FlightPlot
- MAVSDK Logging: https://mavsdk.mavlink.io/main/en/cpp/api_reference/classmavsdk_1_1_log_files.html

---

## Appendix: Quick Reference Tables

### PX4 Topic Sizes (Approximate)

| Topic | Size (bytes) | Notes |
|-------|--------------|-------|
| vehicle_attitude | 48 | Quaternion + timestamp |
| vehicle_local_position | 72 | NED position + velocity |
| vehicle_rates_setpoint | 24 | Roll/pitch/yaw rates |
| actuator_outputs | 32 | 16 output channels |
| sensor_combined | 48 | Accel + gyro |
| estimator_status | 160 | Full EKF state |
| battery_status | 64 | Voltage, current, remaining |

### Log Bandwidth by Scenario

| Scenario | Topics | Rate | Bandwidth |
|----------|--------|------|-----------|
| Minimal | Status + Position | 10 Hz | ~5 KB/s |
| Standard | Flight + Estimation | 50 Hz | ~25 KB/s |
| Debug | All topics full rate | 250 Hz | ~150 KB/s |
| LLM Control | + Offboard topics | 250 Hz | ~175 KB/s |

### Retention Recommendations

| Log Type | Local Retention | Remote Retention | Compression |
|----------|----------------|------------------|-------------|
| PX4 ULog | 30 days | Permanent | Gzip |
| LLM Decisions | 90 days | 1 year | Gzip |
| Telemetry Snapshots | 7 days | 90 days | Gzip |
| Vision Frames | 1 day | 7 days | H.264 |
| Network Logs | 3 days | 30 days | Gzip |

---

*Document Version: 1.0*  
*Last Updated: 2026-04-10*  
*Project Avatar: Flight Data Logging Research*
