# WiFi MAVLink Reliability Research for Drone Control

**Research Date:** April 2026  
**Focus:** Network reliability analysis for MAVLink-based drone telemetry over WiFi

---

## 1. UDP vs TCP for MAVLink

### 1.1 Packet Loss Tolerance

**MAVLink Design Philosophy:**
MAVLink was designed as a lightweight, connectionless protocol. Per the official MAVLink documentation: "The messages are not guaranteed to be delivered which means ground stations or companion computers must often check the state of the vehicle to determine if a command has been executed."

**UDP Characteristics:**
- **Native fit:** MAVLink messages are self-contained with checksums (CRC_EXTRA) making them suitable for UDP
- **Packet independence:** Each MAVLink message (max 280 bytes in v2.0) is complete and stateless
- **No head-of-line blocking:** Lost packets don't delay subsequent messages
- **Heartbeat as liveness:** The 1Hz HEARTBEAT message (Message ID 0) serves as implicit connection monitoring

**Packet Loss Handling:**
| Loss Type | Impact | Mitigation |
|-----------|--------|------------|
| Telemetry data loss | Stale display values | Request retransmission via REQUEST_DATA_STREAM |
| Command ACK loss | Uncertain command status | Timeout/retry with explicit COMMAND_ACK |
| Heartbeat loss | Link status unknown | Dual timeout thresholds (3s warning, 5s failsafe) |
| Mission item loss | Incomplete mission | MAVLink mission protocol with sequence ACKs |

**Recommended UDP Configuration:**
```python
# Socket configuration for MAVLink over UDP
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # 64KB recv buffer
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # 64KB send buffer
sock.setblocking(False)  # Non-blocking for async handling
```

### 1.2 Latency Characteristics on WiFi

**WiFi Latency Profile:**
- **2.4GHz typical:** 5-15ms round-trip (ideal conditions)
- **5GHz typical:** 3-10ms round-trip (ideal conditions)
- **Congested environment:** 50-200ms spikes common
- **Bufferbloat risk:** Consumer WiFi APs often have excessive buffering

**TCP vs UDP Latency Comparison:**

| Scenario | UDP Latency | TCP Latency | Winner |
|----------|-------------|-------------|--------|
| Clean link, low loss | ~5ms | ~5ms + handshake | UDP |
| 1% packet loss | ~5ms (isolated) | ~100-500ms (retransmit) | UDP |
| 5% packet loss | ~5ms (isolated) | ~1-5s (exponential backoff) | UDP |
| High jitter environment | Variable | Smoothed but delayed | Depends |

**Critical Insight:** For real-time control (position/attitude updates at 10-50Hz), TCP's retransmission behavior during packet loss creates unacceptable latency spikes. UDP allows the system to continue operating with degraded but current data.

### 1.3 Buffer Sizing Recommendations

**MAVLink Message Sizes:**
- MAVLink v1.0: Maximum 263 bytes per message
- MAVLink v2.0: Maximum 280 bytes per message

**Buffer Size Calculations:**

```
Minimum Receive Buffer = (Max Message Rate) × (Max Message Size) × (Buffer Duration)

Example for high-rate telemetry:
- 50 messages/sec × 280 bytes × 2 seconds = 28,000 bytes (minimum)
- Recommended: 64KB (allows for burst tolerance)

High-bandwidth scenario (1080p video + telemetry):
- Telemetry: 64KB
- Video stream: 512KB-1MB (separate socket recommended)
```

**Linux Socket Buffer Tuning:**
```bash
# System-wide tuning for drone control station
sudo sysctl -w net.core.rmem_max=2097152     # 2MB max receive
sudo sysctl -w net.core.wmem_max=2097152     # 2MB max send
sudo sysctl -w net.core.rmem_default=262144  # 256KB default
sudo sysctl -w net.core.wmem_default=262144  # 256KB default
```

**Flight Controller UART Buffering:**
- Flight controllers have limited UART buffers (typically 128-1024 bytes)
- MAVLink data streams must be throttled to prevent overflow
- Use `REQUEST_DATA_STREAM` or `SET_MESSAGE_INTERVAL` to control rates

### 1.4 Connection Drop Detection

**MAVLink Heartbeat Mechanism:**
- **Frequency:** 1Hz (one heartbeat per second)
- **Timeout threshold:** Industry standard is 3-5 seconds without heartbeat
- **Component identification:** HEARTBEAT contains `type` and `autopilot` fields

**Recommended Detection Strategy:**
```python
HEARTBEAT_TIMEOUT_WARNING = 3.0   # seconds - yellow status
HEARTBEAT_TIMEOUT_CRITICAL = 5.0  # seconds - trigger failsafe
HEARTBEAT_TIMEOUT_LOST = 10.0     # seconds - consider link dead

# System ID validation prevents cross-talk on shared networks
expected_system_id = 1  # Drone system ID
expected_component_id = 1  # Autopilot component
```

**Multi-Level Detection:**
1. **L1 (0-3s):** Normal operation - accept all valid MAVLink traffic
2. **L2 (3-5s):** Warning state - reduce non-critical telemetry, prepare for failsafe
3. **L3 (5-10s):** Critical - activate failsafe mode (RTL, Land, Hold)
4. **L4 (10s+):** Link declared dead - full failsafe engaged

---

## 2. WiFi Failure Modes Analysis

### 2.1 WiFi Interference: 2.4GHz vs 5GHz

**2.4GHz Band Characteristics:**
- **Channels:** 1-14 (non-overlapping: 1, 6, 11)
- **Bandwidth:** 20/40MHz
- **Pros:** Better range, better obstacle penetration
- **Cons:** Severe congestion (Bluetooth, microwaves, cordless phones, other WiFi)

**5GHz Band Characteristics:**
- **Channels:** 36-165 (many non-overlapping)
- **Bandwidth:** 20/40/80/160MHz
- **Pros:** Less congestion, higher throughput, more channels available
- **Cons:** Shorter range, poor obstacle penetration, DFS channel restrictions

**Interference Sources by Band:**

| Source | 2.4GHz Impact | 5GHz Impact |
|--------|---------------|-------------|
| Microwave ovens | Severe (2.45GHz leakage) | None |
| Bluetooth devices | Moderate-High | Minimal |
| Cordless phones | High | Minimal |
| ZigBee/IoT devices | High | None |
| Other WiFi networks | Very High | Moderate |
| Radar (weather/military) | N/A | DFS channel switches |

**Recommendation for Drone Control:**
- **Primary:** 5GHz (channels 149-161, non-DFS) for lower latency and interference
- **Fallback:** 2.4GHz (channel 1 or 11) for extended range scenarios
- **Dynamic switching:** Implement band-steering if hardware supports

### 2.2 Range Limitations

**WiFi Range Characteristics:**

| Configuration | Outdoor Range (LoS) | Indoor Range | Data Rate @ Max Range |
|---------------|---------------------|--------------|----------------------|
| 2.4GHz, 20MHz, 18dBm | 100-150m | 30-50m | 1-6 Mbps |
| 2.4GHz, 40MHz, 18dBm | 80-120m | 25-40m | 1-6 Mbps |
| 5GHz, 80MHz, 18dBm | 50-80m | 15-30m | 6-54 Mbps |
| 5GHz, 20MHz, 18dBm | 80-120m | 25-40m | 6-54 Mbps |

**Drone-Specific Considerations:**
- **Altitude advantage:** Increased line-of-sight at altitude extends effective range
- **Antenna orientation:** Ground station should use high-gain directional antennas
- **Doppler effect:** Minimal impact at drone speeds (<30 m/s) but measurable at 5GHz

**Practical Range Limits for MAVLink:**
- **Reliable control:** 100-300m (2.4GHz), 50-150m (5GHz)
- **Telemetry only:** 500m+ possible with directional antennas
- **Video + Telemetry:** 100-300m typical with WiFi

### 2.3 Packet Loss Masking as Valid Data

**The Silent Failure Problem:**
Unlike TCP which signals errors, UDP packet loss is invisible unless explicitly detected. This creates dangerous scenarios:

**Failure Modes:**
1. **Stale data display:** GCS shows old position while drone has moved significantly
2. **Masked command failure:** Command sent but never received, no ACK timeout detected
3. **Partial mission upload:** Mission items silently dropped during upload
4. **Parameter fetch incomplete:** Parameter list appears complete but is truncated

**Detection Strategies:**

```python
# Sequence number tracking (MAVLink v2)
def validate_message_sequence(msg, expected_seq):
    """Detect dropped messages via sequence gaps"""
    gap = (msg.seq - expected_seq) & 0xFF  # 8-bit wraparound
    if gap > 1 and gap < 128:  # Valid gap detection range
        log.warning(f"Detected {gap-1} dropped messages")
    return msg.seq

# Timestamp validation for critical data
last_position_timestamp = None

def validate_freshness(msg, max_age_ms=500):
    """Ensure data isn't stale"""
    msg_time = msg.time_boot_ms
    if last_position_timestamp and \
       (msg_time - last_position_timestamp) > max_age_ms:
        log.warning("Stale position data detected")
    return msg_time
```

**Mitigation Techniques:**
1. **Sequence number monitoring:** Track MAVLink sequence numbers (8-bit, wraps at 255)
2. **Timestamp validation:** Compare message timestamps against local clock
3. **Rate monitoring:** Alert if expected message rate drops
4. **CRC verification:** MAVLink v2 includes packet signing option for critical commands

### 2.4 Half-Open Connection Scenarios

**The Half-Open Problem:**
UDP is connectionless, but application state machines track "connection" status. A half-open state occurs when:
- Ground station believes link is active
- Drone has lost WiFi association or rebooted
- Packets are being sent into the void

**Common Causes:**
1. **Drone WiFi disassociation:** Power saving, interference, or AP reset
2. **Drone reboot mid-flight:** Firmware update trigger, watchdog reset
3. **IP address change:** DHCP reassignment after reassociation
4. **Firewall state timeout:** NAT table entry expired

**Detection and Recovery:**

```python
class LinkMonitor:
    def __init__(self):
        self.last_tx_heartbeat = 0
        self.last_rx_heartbeat = 0
        self.link_state = "UNKNOWN"
        
    def on_transmit(self):
        """Called when we send any MAVLink traffic"""
        self.last_tx_heartbeat = time.time()
        
    def on_heartbeat_received(self, system_id, component_id):
        """Called when HEARTBEAT received"""
        self.last_rx_heartbeat = time.time()
        
        # Validate system/component IDs
        if system_id != self.expected_system_id:
            log.warning(f"Unexpected system ID: {system_id}")
            return
            
        if self.link_state == "LOST":
            log.info("Link re-established")
            self.link_state = "ACTIVE"
    
    def check_health(self):
        """Periodic health check - call at 1Hz minimum"""
        now = time.time()
        
        # If we're transmitting but not receiving, link may be half-open
        if (now - self.last_tx_heartbeat) < 1.0 and \
           (now - self.last_rx_heartbeat) > HEARTBEAT_TIMEOUT_CRITICAL:
            log.error("Half-open connection detected - sending but not receiving")
            self.link_state = "HALF_OPEN"
            return False
            
        # If we haven't transmitted recently, link is idle not broken
        if (now - self.last_tx_heartbeat) > 5.0:
            self.link_state = "IDLE"
            return True
            
        return self.link_state in ["ACTIVE", "IDLE"]
```

---

## 3. Design Recommendations

### 3.1 Heartbeat Redundancy Strategies

**Primary Heartbeat (Autopilot):**
- Source: Flight controller (System ID 1, Component ID 1)
- Frequency: 1Hz mandatory
- Content: Vehicle type, autopilot type, flight mode, armed state

**Redundant Heartbeat Locations:**

| Location | System ID | Component ID | Purpose |
|----------|-----------|--------------|---------|
| Flight Controller | 1 | 1 | Primary control link |
| Companion Computer | 1 | 191 (MAV_COMP_ID_ONBOARD_COMPUTER1) | Secondary telemetry path |
| GCS Backup | 255 | 190 (MAV_COMP_ID_MISSIONPLANNER) | Ground-side health |
| LTE/4G Bridge | 1 | 240 (MAV_COMP_ID_ETHERNET) | Cellular fallback |

**Heartbeat Redundancy Implementation:**

```python
class RedundantHeartbeatMonitor:
    """Monitor multiple heartbeat sources for fault tolerance"""
    
    SOURCES = {
        (1, 1): "primary",           # Flight controller
        (1, 191): "companion",        # Raspberry Pi companion
        (255, 190): "gcs_backup",    # Ground station backup
    }
    
    def __init__(self):
        self.source_status = {src: {"last_seen": 0, "alive": False} 
                              for src in self.SOURCES}
        self.primary_active = False
        
    def process_heartbeat(self, system_id, component_id):
        source = (system_id, component_id)
        if source not in self.SOURCES:
            return  # Unknown source
            
        self.source_status[source]["last_seen"] = time.time()
        self.source_status[source]["alive"] = True
        
        # Update primary status
        if source == (1, 1):
            self.primary_active = True
    
    def get_link_quality(self):
        """Returns quality score 0.0-1.0 based on redundant sources"""
        now = time.time()
        active_sources = 0
        
        for source, status in self.source_status.items():
            if now - status["last_seen"] < 5.0:
                active_sources += 1
                
        return active_sources / len(self.SOURCES)
    
    def should_trigger_failsafe(self):
        """Failsafe if primary lost but consider redundancy"""
        now = time.time()
        primary_status = self.source_status[(1, 1)]
        
        # Immediate failsafe if primary lost
        if now - primary_status["last_seen"] > 5.0:
            # Check if companion can relay (via different path)
            companion = self.source_status[(1, 191)]
            if now - companion["last_seen"] < 5.0:
                log.warning("Primary lost, using companion relay")
                return False  # Degraded but not failsafe
            return True  # Failsafe required
        return False
```

### 3.2 Link Quality Monitoring

**Multi-Metric Approach:**

```python
class LinkQualityMonitor:
    """Comprehensive link quality assessment"""
    
    def __init__(self):
        self.metrics = {
            'heartbeat_latency': [],      # RTT of heartbeat/ping
            'message_rate': {},           # msgs/sec by message type
            'packet_loss': 0.0,           # calculated from seq numbers
            'signal_strength': None,      # RSSI if available
            'retry_count': 0,             # command retries needed
        }
        self.history = deque(maxlen=60)  # 60 seconds of history
        
    def update(self, msg):
        """Update metrics from incoming message"""
        now = time.time()
        msg_type = msg.get_type()
        
        # Track message rates
        if msg_type not in self.metrics['message_rate']:
            self.metrics['message_rate'][msg_type] = []
        self.metrics['message_rate'][msg_type].append(now)
        
        # Calculate packet loss from sequence gaps
        self._update_packet_loss(msg)
        
        # Store snapshot every second
        if int(now) > int(self.last_update):
            self.history.append(dict(self.metrics))
            self.last_update = now
    
    def get_quality_score(self):
        """Returns 0-100 quality score"""
        score = 100
        
        # Penalize for packet loss
        score -= self.metrics['packet_loss'] * 50  # 2% loss = -100, capped
        
        # Penalize for latency
        avg_latency = self._get_avg_latency()
        if avg_latency > 100:  # ms
            score -= (avg_latency - 100) / 10
            
        # Penalize for message rate degradation
        expected_rate = self._get_expected_rate()
        actual_rate = self._get_actual_rate()
        if actual_rate < expected_rate * 0.8:
            score -= 20
            
        return max(0, min(100, score))
    
    def get_recommendation(self):
        """Returns action recommendation based on quality"""
        score = self.get_quality_score()
        
        if score > 80:
            return "OPTIMAL", "Full capability available"
        elif score > 60:
            return "DEGRADED", "Reduce video quality, maintain control"
        elif score > 40:
            return "MARGINAL", "Pause mission, prepare for RTL"
        else:
            return "CRITICAL", "Initiate immediate failsafe"
```

**Quality Indicators:**
- **Excellent (90-100):** <1% loss, <20ms latency, full message rate
- **Good (70-89):** 1-3% loss, <50ms latency, minor rate reduction
- **Fair (50-69):** 3-5% loss, <100ms latency, noticeable degradation
- **Poor (30-49):** 5-10% loss, >100ms latency, mission risk
- **Critical (0-29):** >10% loss, >500ms latency, failsafe required

### 3.3 Graceful Degradation Patterns

**Degradation Levels:**

```python
class GracefulDegradation:
    """Manage system capability based on link quality"""
    
    LEVELS = {
        0: {
            'name': 'FULL',
            'video': '1080p@30fps',
            'telemetry': 'all_messages@10Hz',
            'commands': 'full_rate',
            'mission': 'autonomous_allowed'
        },
        1: {
            'name': 'REDUCED_VIDEO',
            'video': '720p@15fps',
            'telemetry': 'all_messages@5Hz',
            'commands': 'full_rate',
            'mission': 'autonomous_allowed'
        },
        2: {
            'name': 'ESSENTIAL_ONLY',
            'video': 'OFF',
            'telemetry': 'heartbeat+attitude+position@2Hz',
            'commands': 'throttled',
            'mission': 'pause_mission'
        },
        3: {
            'name': 'CRITICAL',
            'video': 'OFF',
            'telemetry': 'heartbeat_only',
            'commands': 'emergency_only',
            'mission': 'rtl_or_land'
        }
    }
    
    def __init__(self, link_monitor):
        self.link_monitor = link_monitor
        self.current_level = 0
        
    def evaluate(self):
        quality = self.link_monitor.get_quality_score()
        latency = self.link_monitor.get_avg_latency()
        
        new_level = self.current_level
        
        # Hysteresis for level changes
        if quality > 85 and self.current_level > 0:
            new_level = self.current_level - 1  # Improve gradually
        elif quality < 50:
            new_level = 3  # Critical immediately
        elif quality < 70:
            new_level = max(2, self.current_level)
        elif quality < 85:
            new_level = max(1, self.current_level)
            
        if new_level != self.current_level:
            self._apply_level(new_level)
            
    def _apply_level(self, level):
        config = self.LEVELS[level]
        log.warning(f"Degrading to level {level}: {config['name']}")
        
        # Update telemetry rates
        self._set_telemetry_rate(config['telemetry'])
        
        # Control video stream
        self._set_video_config(config['video'])
        
        # Update mission status
        if config['mission'] == 'rtl_or_land':
            self._trigger_failsafe()
            
        self.current_level = level
```

**Degradation Triggers:**
- **Level 0→1:** Packet loss >2% or latency >100ms sustained
- **Level 1→2:** Packet loss >5% or video stream degrading
- **Level 2→3:** Packet loss >10% or heartbeat timeout warning
- **Any level improvement:** Quality sustained >90% for 10 seconds

### 3.4 Raspberry Pi as Heartbeat Backup Location

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                         DRONE                               │
│  ┌──────────────┐      ┌──────────────┐                     │
│  │   Flight     │ UART │  Raspberry   │ WiFi                │
│  │  Controller  │◄────►│      Pi      │◄────┐               │
│  │  (Primary)   │      │  (Companion) │     │               │
│  └──────────────┘      └──────────────┘     │               │
│         │                   │                │               │
│         │ MAVLink           │ MAVLink        │               │
│         │ (primary)         │ (backup)       │               │
│         └───────────────────┘                │               │
└──────────────────────────────────────────────┼───────────────┘
                                               │
                                               ▼
                              ┌─────────────────────────────┐
                              │       GROUND STATION        │
                              │    (QGroundControl/custom)  │
                              └─────────────────────────────┘
```

**Raspberry Pi Responsibilities:**

1. **Heartbeat Relay:**
```python
#!/usr/bin/env python3
"""Companion computer heartbeat redundancy service"""

import asyncio
from pymavlink import mavutil

class CompanionHeartbeatRelay:
    def __init__(self):
        # Connect to flight controller via UART
        self.fc = mavutil.mavlink_connection('/dev/ttyAMA0', baud=921600)
        # Connect to GCS via WiFi (UDP)
        self.gcs = mavutil.mavlink_connection('udpout:192.168.1.100:14550')
        
        self.last_fc_heartbeat = 0
        self.heartbeat_seq = 0
        
    async def relay_loop(self):
        """Main relay loop - forwards messages and generates backup heartbeats"""
        while True:
            # Process messages from flight controller
            msg = self.fc.recv_match(blocking=False)
            if msg:
                # Forward to GCS
                self.gcs.mav.send(msg)
                
                # Track FC heartbeat
                if msg.get_type() == 'HEARTBEAT':
                    self.last_fc_heartbeat = time.time()
                    
            # Generate backup heartbeat if FC heartbeat missing
            if time.time() - self.last_fc_heartbeat > 2.0:
                self._send_backup_heartbeat()
                
            await asyncio.sleep(0.01)  # 100Hz processing
            
    def _send_backup_heartbeat(self):
        """Send companion computer heartbeat to indicate relay is active"""
        self.gcs.mav.heartbeat_send(
            type=mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )
```

2. **Link Quality Aggregation:**
```python
class LinkAggregation:
    """Combine multiple link paths for redundancy"""
    
    def __init__(self):
        self.paths = {
            'direct_wifi': DirectWiFiPath(),
            'pi_relay': CompanionRelayPath(),
            'lte_backup': LTEBackupPath()
        }
        self.active_path = 'direct_wifi'
        
    def send_command(self, command):
        """Send via all paths, use first ACK received"""
        ack_received = False
        
        for name, path in self.paths.items():
            if path.is_available():
                path.send(command)
                
        # Wait for ACK with timeout
        start = time.time()
        while time.time() - start < 1.0:
            for name, path in self.paths.items():
                ack = path.check_for_ack(command.id)
                if ack:
                    self.active_path = name
                    return ack
                    
        raise CommandTimeout("No ACK received on any path")
```

3. **Failsafe Decision Logic:**
```python
class FailsafeController:
    """Determine when to trigger failsafe based on all link paths"""
    
    def __init__(self):
        self.sources = {
            'fc_direct': {'timeout': 5.0, 'weight': 1.0},
            'fc_via_pi': {'timeout': 5.0, 'weight': 0.8},
            'pi_direct': {'timeout': 3.0, 'weight': 0.5},
        }
        
    def calculate_link_health(self):
        """Weighted health score from all sources"""
        total_weight = 0
        healthy_weight = 0
        
        for source, config in self.sources.items():
            if self.is_source_alive(source, config['timeout']):
                healthy_weight += config['weight']
            total_weight += config['weight']
            
        return healthy_weight / total_weight
    
    def should_failsafe(self):
        health = self.calculate_link_health()
        
        # Immediate failsafe if primary lost completely
        if not self.is_source_alive('fc_direct', 5.0) and \
           not self.is_source_alive('fc_via_pi', 5.0):
            return True
            
        # Failsafe if combined health below threshold
        if health < 0.3:
            return True
            
        return False
```

**Raspberry Pi Configuration:**

```bash
# /boot/config.txt - Enable UART for flight controller
dtoverlay=uart0,ctsrts
enable_uart=1

# Disable Bluetooth to free UART0
dtoverlay=disable-bt

# /etc/systemd/system/mavlink-relay.service
[Unit]
Description=MAVLink Heartbeat Redundancy Relay
After=network.target

[Service]
Type=simple
User=pi
ExecStart=/usr/local/bin/mavlink-relay.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 4. Summary of Mitigation Strategies

| Risk | Mitigation | Implementation Priority |
|------|------------|------------------------|
| Packet loss | UDP with sequence tracking, redundant paths | Critical |
| Latency spikes | Non-blocking sockets, priority queuing | High |
| Connection drops | Multi-source heartbeat monitoring | Critical |
| Half-open state | Bidirectional heartbeat with TX/RX tracking | High |
| Interference | 5GHz primary, 2.4GHz fallback | Medium |
| Range limits | RSSI monitoring, degraded mode trigger | High |
| Stale data | Timestamp validation, freshness checks | Medium |

**Implementation Checklist:**
- [ ] Implement dual-source heartbeat (FC + RPi companion)
- [ ] Add sequence number tracking for packet loss detection
- [ ] Configure non-blocking UDP sockets with adequate buffers (64KB+)
- [ ] Implement 4-level graceful degradation
- [ ] Set up 5GHz primary with 2.4GHz fallback
- [ ] Add link quality scoring (0-100 scale)
- [ ] Configure failsafe thresholds (3s warning, 5s critical)
- [ ] Test half-open connection recovery
- [ ] Validate timestamp freshness for critical data
- [ ] Document RSSI-to-range correlation for your hardware

---

**References:**
- MAVLink Protocol Documentation: https://mavlink.io/en/
- ArduPilot MAVLink Basics: https://ardupilot.org/dev/docs/mavlink-basics.html
- PX4 Telemetry Integration: https://docs.px4.io/main/en/data_links/telemetry.html
- pymavlink Reference Implementation: https://github.com/ArduPilot/pymavlink
