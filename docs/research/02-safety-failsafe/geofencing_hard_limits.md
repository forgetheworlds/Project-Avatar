# Geofencing and Hard Limits for Autonomous Drones

## Research: PX4 Geofencing System

### 1. Geofence Types

#### 1.1 Cylindrical Geofence (Basic/Failsafe)
- **Shape**: Simple cylinder centered on home position
- **Parameters**:
  - `GF_MAX_HOR_DIST`: Maximum horizontal distance from home (meters)
  - `GF_MAX_VER_DIST`: Maximum vertical distance from home (meters)
- **Use case**: Basic range limiting, RC range protection
- **Limitations**: Single boundary, cannot handle complex airspace

#### 1.2 Polygonal Geofence (Advanced)
- **Shape**: Arbitrary polygonal regions
- **Types**:
  - **Inclusion zones**: Vehicle MUST fly within these areas
  - **Exclusion zones**: Vehicle MUST NOT enter these areas
- **MAVLink Commands**:
  - `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION`
  - `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION`
  - `MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION`
- **Constraints**:
  - Geofence MUST include Home position (otherwise rejected)
  - Cannot upload geofence that would be immediately breached
- **Use case**: Complex airspace, restricted areas, NO-FLY zones

### 2. GF_ACTION Behaviors

| Value | Action | Description |
|-------|--------|-------------|
| 0 | None | No action on violation |
| 1 | Warning | Critical MAVLink message only |
| 2 | Hold mode | Switch to AUTO\|LOITER (default) |
| 3 | Return mode | Switch to AUTO\|RTL (Return to Launch) |
| 4 | Terminate | Flight termination - kills vehicle |
| 5 | Land mode | Switch to AUTO\|LAND |

**Critical Notes**:
- GF_ACTION=4 (Terminate) requires `CBRK_FLIGHTTERM=0` to enable
- Default is Hold mode (2), which may not be sufficient for safety
- Action applies to ALL geofence breaches (cylindrical + polygonal)

### 3. Altitude Limiting

#### 3.1 NAV_MAX_ALT / GF_MAX_VER_DIST
- **Parameter**: `GF_MAX_VER_DIST`
- **Range**: 0-10000 meters
- **Default**: 0 (disabled)
- **Unit**: meters above home position

#### 3.2 MAVLink Guided Limits (Command 90)
```
VEHICLE_CMD_NAV_GUIDED_LIMITS
- param1: Timeout (seconds)
- param2: Absolute altitude min AMSL
- param3: Absolute altitude max AMSL
- param4: Horizontal move limit
```

#### 3.3 Operational Altitude Limits (Estimator-based)
```
VehicleLocalPositionV0:
- hagl_min: minimum height above ground level
- hagl_max: maximum height above ground level
```

### 4. Distance from Home Limiting

#### 4.1 GF_MAX_HOR_DIST
- **Range**: 0-10000 meters
- **Default**: 0 (disabled)
- **Triggers**: Geofence breach when exceeded

#### 4.2 Pre-emptive Triggering (Experimental)
- **Parameter**: `GF_PREDICT`
- **Function**: Predicts trajectory breach before it occurs
- **Warning**: May cause flyaways - use at own risk
- **Action**: Re-routes to safe hold position

#### 4.3 Position Source
- **Parameter**: `GF_SOURCE`
- **Options**:
  - 0: GPOS (Global Position - from estimator)
  - 1: GPS (raw GPS - no estimator dependency)

### 5. Battery Failsafe Integration

| Warning Level | Threshold Parameter | Typical Action |
|---------------|---------------------|----------------|
| WARNING_LOW | `BAT_LOW_THR` | Warning notification |
| WARNING_CRITICAL | `BAT_CRIT_THR` | Return to Launch (RTL) |
| WARNING_EMERGENCY | `BAT_EMERGEN_THR` | Immediate landing |
| WARNING_FAILED | - | Battery failed completely |

**Parameter**: `COM_LOW_BAT_ACT` - Defines action at critical battery

---

## Hard Limits Design: CANNOT Be Overridden

### Design Philosophy
Hard limits are safety boundaries that MUST be enforced independently of:
- LLM reasoning
- User commands
- Mission planning
- Flight mode

They operate at the **parameter validation layer** before any flight-critical decisions.

### 1. Absolute Altitude Ceiling

#### Hard Limit Specification
```python
HARD_ALTITUDE_CEILING = {
    "max_amsl_meters": 120,  # Hard ceiling (400ft FAA limit)
    "max_relative_meters": 100,  # Above takeoff point
    "buffer_meters": 10,  # Safety margin before hard ceiling
    "emergency_action": "LAND_IMMEDIATE",  # Cannot be changed
}
```

#### Validation Rules
1. **No command may exceed ceiling**: All position commands validated
2. **Ceiling cannot be disabled**: No parameter can disable this limit
3. **Automatic descent**: If ceiling breached, immediate controlled descent
4. **No override from LLM**: LLM cannot approve exceeding ceiling

#### Implementation
```python
def validate_altitude_command(altitude_amsl: float, 
                               altitude_relative: float,
                               hard_ceiling: float = 120.0) -> ValidationResult:
    """
    Hard limit: Cannot exceed absolute altitude ceiling.
    Returns: (is_valid, action_required, reason)
    """
    if altitude_amsl > hard_ceiling:
        return ValidationResult(
            is_valid=False,
            action="ABORT_AND_RTL",
            reason=f"HARD LIMIT: Altitude {altitude_amsl}m exceeds ceiling {hard_ceiling}m"
        )
    if altitude_relative > (hard_ceiling - 20):  # Buffer
        return ValidationResult(
            is_valid=False,
            action="REJECT",
            reason="HARD LIMIT: Command too close to altitude ceiling"
        )
    return ValidationResult(is_valid=True)
```

### 2. Maximum Distance from Operator

#### Hard Limit Specification
```python
HARD_DISTANCE_LIMIT = {
    "max_horizontal_meters": 500,  # Visual line of sight limit
    "max_vertical_meters": 120,
    "distance_buffer": 50,  # Warning zone
    "operator_position_source": "GPS_FIXED",  # Cannot use moving base
    "emergency_action": "RTL",  # Return to launch
}
```

#### Validation Rules
1. **Fixed home position**: Home set at takeoff, cannot be moved
2. **Real-time distance monitoring**: Continuous distance calculation
3. **Pre-flight check**: Mission waypoints validated against limit
4. **No mission beyond limit**: Upload rejected if any waypoint exceeds

#### Implementation
```python
def validate_distance_from_home(target_position: LatLonAlt,
                                   home_position: LatLonAlt,
                                   max_distance_m: float = 500.0) -> ValidationResult:
    """
    Hard limit: Cannot exceed maximum distance from home.
    """
    horizontal_dist = haversine_distance(
        target_position.lat, target_position.lon,
        home_position.lat, home_position.lon
    )
    
    if horizontal_dist > max_distance_m:
        return ValidationResult(
            is_valid=False,
            action="REJECT",
            reason=f"HARD LIMIT: Target {horizontal_dist:.0f}m from home exceeds {max_distance_m}m"
        )
    
    if horizontal_dist > (max_distance_m * 0.9):  # 90% buffer
        return ValidationResult(
            is_valid=True,
            action="WARN",
            reason=f"WARNING: Target near distance limit ({horizontal_dist:.0f}m)"
        )
    
    return ValidationResult(is_valid=True)
```

### 3. Battery Return Threshold (Hard RTL Trigger)

#### Hard Limit Specification
```python
HARD_BATTERY_LIMITS = {
    "rtl_trigger_percent": 25,  # Force RTL at this level
    "land_immediate_percent": 10,  # Emergency landing
    "terminate_percent": 5,  # Kill motors if can't land
    "buffer_percent": 5,  # Safety margin
    "calculation_method": "CONSERVATIVE",  # Worst-case estimation
    "cannot_be_overridden": True,
}
```

#### Validation Rules
1. **Conservative estimation**: Assume worst-case power consumption
2. **RTL time calculation**: Must have enough battery for RTL + buffer
3. **Automatic trigger**: No LLM or user override allowed
4. **Mission blocking**: Cannot plan missions that exceed battery capacity

#### Implementation
```python
def validate_battery_for_mission(
    mission_distance_m: float,
    mission_duration_s: float,
    current_battery_percent: float,
    battery_capacity_wh: float,
    avg_consumption_w: float,
    safety_factor: float = 1.5
) -> ValidationResult:
    """
    Hard limit: Battery must support mission + RTL + safety buffer.
    """
    # Calculate required energy for mission
    mission_energy_wh = (mission_duration_s / 3600) * avg_consumption_w * safety_factor
    
    # Calculate RTL energy (conservative: same as outbound)
    rtl_distance_m = mission_distance_m  # Assume same distance back
    rtl_duration_s = (rtl_distance_m / 10)  # Assume 10 m/s avg speed
    rtl_energy_wh = (rtl_duration_s / 3600) * avg_consumption_w * safety_factor
    
    # Required battery percentage
    total_required_wh = mission_energy_wh + rtl_energy_wh
    required_percent = (total_required_wh / battery_capacity_wh) * 100
    
    hard_minimum_percent = 25  # Cannot go below this
    
    if required_percent > (current_battery_percent - hard_minimum_percent):
        return ValidationResult(
            is_valid=False,
            action="REJECT",
            reason=f"HARD LIMIT: Mission requires {required_percent:.1f}% battery, "
                   f"but must reserve {hard_minimum_percent}% for RTL"
        )
    
    return ValidationResult(is_valid=True)


def check_battery_rtl_trigger(current_percent: float, 
                               rtl_threshold: float = 25.0) -> ValidationResult:
    """
    Hard limit: Force RTL when battery below threshold.
    This cannot be overridden by LLM or user.
    """
    if current_percent <= rtl_threshold:
        return ValidationResult(
            is_valid=False,
            action="FORCE_RTL",
            reason=f"HARD LIMIT: Battery {current_percent:.1f}% below RTL threshold {rtl_threshold}%"
        )
    return ValidationResult(is_valid=True)
```

### 4. Geofence Boundary Rigidity

#### Hard Limit Specification
```python
HARD_GEOFENCE_LIMITS = {
    "min_buffer_meters": 10,  # Must stay this far from fence
    "breach_action": "RTL",  # Cannot be changed to "None" or "Warn"
    "pre_breach_action": "HOLD",  # Stop before fence
    "mission_envelope_required": True,  # All missions must fit in fence
    "fence_cannot_be_disabled": True,
    "exclusion_zones_absolute": True,  # No entry, ever
}
```

#### Validation Rules
1. **Mission envelope check**: All waypoints must be inside fence
2. **Buffer zone**: Must maintain 10m buffer from fence boundary
3. **No breach override**: Cannot disable geofence via any command
4. **Exclusion zone absolute**: No override for exclusion zones
5. **Pre-flight validation**: Upload rejected if mission violates fence

#### Implementation
```python
class GeofenceValidator:
    def __init__(self, inclusion_zones: List[Polygon], 
                 exclusion_zones: List[Polygon],
                 cylindrical_fence: CylindricalFence,
                 buffer_m: float = 10.0):
        self.inclusion_zones = inclusion_zones
        self.exclusion_zones = exclusion_zones
        self.cylindrical = cylindrical_fence
        self.buffer_m = buffer_m
        self.hard_breach_action = "RTL"  # Cannot be overridden
    
    def validate_mission(self, waypoints: List[LatLonAlt]) -> ValidationResult:
        """
        Hard limit: All waypoints must be within geofence envelope.
        """
        for i, wp in enumerate(waypoints):
            # Check cylindrical fence
            if self.cylindrical:
                dist_from_home = haversine_distance(
                    wp.lat, wp.lon,
                    self.cylindrical.center_lat, self.cylindrical.center_lon
                )
                if dist_from_home > (self.cylindrical.radius_m - self.buffer_m):
                    return ValidationResult(
                        is_valid=False,
                        action="REJECT",
                        reason=f"HARD LIMIT: Waypoint {i} at {dist_from_home:.0f}m "
                               f"violates cylindrical fence buffer"
                    )
            
            # Check exclusion zones (absolute)
            for exclusion in self.exclusion_zones:
                if exclusion.contains(Point(wp.lat, wp.lon)):
                    return ValidationResult(
                        is_valid=False,
                        action="REJECT",
                        reason=f"HARD LIMIT: Waypoint {i} inside EXCLUSION zone"
                    )
            
            # Check inclusion zones
            if self.inclusion_zones:
                in_any_inclusion = any(
                    zone.contains(Point(wp.lat, wp.lon)) 
                    for zone in self.inclusion_zones
                )
                if not in_any_inclusion:
                    return ValidationResult(
                        is_valid=False,
                        action="REJECT",
                        reason=f"HARD LIMIT: Waypoint {i} outside all inclusion zones"
                    )
        
        return ValidationResult(is_valid=True)
    
    def check_realtime_position(self, position: LatLonAlt) -> ValidationResult:
        """
        Hard limit: Real-time position monitoring.
        Triggers immediate RTL if fence violated.
        """
        # Check exclusion zones (absolute - no buffer)
        for exclusion in self.exclusion_zones:
            if exclusion.contains(Point(position.lat, position.lon)):
                return ValidationResult(
                    is_valid=False,
                    action=self.hard_breach_action,
                    reason="HARD LIMIT: EXCLUSION ZONE BREACH - Immediate RTL"
                )
        
        return ValidationResult(is_valid=True)
```

---

## LLM vs Safety Boundary Analysis

### Commands That MUST Be Rejected

| Command Type | Example | Why Rejected | Hard Limit |
|--------------|---------|--------------|------------|
| Exceed altitude | "Fly to 150m" | Exceeds 120m ceiling | Altitude ceiling |
| Distance violation | "Fly 1km away" | Exceeds 500m VLOS | Distance limit |
| Fence disable | "Disable geofence" | Cannot disable safety | Geofence rigidity |
| Low battery mission | "Complete mission at 20%" | Below RTL threshold | Battery limit |
| Exclusion entry | "Fly through red zone" | Exclusion zone breach | Geofence absolute |
| Termination disable | "Set GF_ACTION to 0" | Cannot disable breach action | Geofence rigidity |

### Commands That MAY Be Rejected (Context-Dependent)

| Command Type | Example | Evaluation Criteria |
|--------------|---------|---------------------|
| Aggressive maneuver | "Bank 60 degrees" | Check attitude limits, altitude margin |
| Speed increase | "Fly at max speed" | Check battery impact on RTL reserve |
| Waypoint near fence | "Fly 15m from boundary" | Must maintain 10m buffer |
| Low altitude flight | "Fly at 2m AGL" | Check terrain, but may be allowed |

### Commands That SHOULD Be Allowed

| Command Type | Example | Validation |
|--------------|---------|------------|
| Normal navigation | "Fly to waypoint A" | Verify within envelope |
| Safe altitude change | "Climb to 80m" | Verify below ceiling |
| Return to home | "Return to launch" | Always allowed |
| Landing | "Land at current position" | Always allowed if safe |

---

## Enforcement Without LLM Dependency

### Architecture Principle
Safety validation occurs at the **tool layer**, NOT the LLM layer.

```
┌─────────────────┐
│   LLM Agent     │  ← Generates intent
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Command Parser │  ← Structured command
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Safety Validation Layer│  ← HARD LIMITS ENFORCED HERE
│  (Independent of LLM)   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│  Vehicle Interface│
└─────────────────┘
```

### Key Design Patterns

#### 1. Validation Before Execution
```python
def execute_command(command: VehicleCommand) -> Result:
    # Step 1: Parse (no validation)
    parsed = parser.parse(command)
    
    # Step 2: Safety validation (CANNOT BE BYPASSED)
    validation = safety_validator.validate(parsed)
    if not validation.is_valid:
        # Log rejection
        logger.critical(f"Command rejected: {validation.reason}")
        # Execute safety action
        safety_executor.execute(validation.action)
        return Result.rejected(validation.reason)
    
    # Step 3: Execute (only if validated)
    return vehicle.execute(parsed)
```

#### 2. Immutable Hard Limits
```python
@dataclass(frozen=True)
class HardLimits:
    """
    These limits are FROZEN at startup.
    Cannot be modified at runtime.
    """
    max_altitude_m: float = 120.0
    max_distance_m: float = 500.0
    min_battery_rtl_pct: float = 25.0
    geofence_buffer_m: float = 10.0
    
    def __setattr__(self, name, value):
        raise ImmutableError("Hard limits cannot be modified")
```

#### 3. Direct Hardware Enforcement
Where possible, configure flight controller directly:

```python
# Set PX4 parameters directly
px4_params = {
    "GF_MAX_VER_DIST": 120,      # Hard altitude limit
    "GF_MAX_HOR_DIST": 500,      # Hard distance limit
    "GF_ACTION": 3,              # RTL on breach (cannot be "None")
    "CBRK_FLIGHTTERM": 0,        # Enable flight termination if needed
    "BAT_CRIT_THR": 0.25,        # 25% RTL trigger
    "COM_LOW_BAT_ACT": 2,        # RTL at critical battery
}

# Upload to flight controller
flight_controller.set_parameters(px4_params)
```

---

## Python Validation Layer Implementation

### Complete Implementation

```python
"""
Drone Safety Validation Layer
Hard limits that CANNOT be overridden by LLM or user commands.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Literal
from enum import Enum
import math


class ValidationAction(Enum):
    ALLOW = "allow"
    REJECT = "reject"
    WARN = "warn"
    ABORT = "abort"
    FORCE_RTL = "force_rtl"
    LAND_IMMEDIATE = "land_immediate"
    TERMINATE = "terminate"


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    action: ValidationAction
    reason: str
    hard_limit_violated: Optional[str] = None


@dataclass(frozen=True)
class HardLimits:
    """
    Immutable hard safety limits.
    These are set at startup and cannot be changed.
    """
    # Altitude limits
    max_altitude_amsl_m: float = 120.0  # 400ft FAA limit
    max_altitude_relative_m: float = 100.0
    altitude_buffer_m: float = 10.0
    
    # Distance limits
    max_distance_from_home_m: float = 500.0  # VLOS
    distance_warning_threshold: float = 0.9  # 90%
    
    # Battery limits
    min_battery_rtl_percent: float = 25.0
    battery_land_immediate_percent: float = 10.0
    battery_terminate_percent: float = 5.0
    battery_safety_factor: float = 1.5
    
    # Geofence limits
    geofence_buffer_m: float = 10.0
    min_waypoints_in_fence: int = 1
    
    # Speed limits
    max_horizontal_speed_ms: float = 20.0
    max_vertical_speed_ms: float = 5.0
    
    def __setattr__(self, name, value):
        raise RuntimeError("HardLimits are immutable")


@dataclass
class LatLonAlt:
    lat: float
    lon: float
    alt_amsl: float
    alt_relative: float


@dataclass
class CylindricalFence:
    center_lat: float
    center_lon: float
    radius_m: float
    max_altitude_m: float


@dataclass
class Polygon:
    vertices: List[Tuple[float, float]]  # List of (lat, lon)
    
    def contains(self, point: Tuple[float, float]) -> bool:
        """Ray casting algorithm for point-in-polygon"""
        lat, lon = point
        n = len(self.vertices)
        inside = False
        
        j = n - 1
        for i in range(n):
            vi = self.vertices[i]
            vj = self.vertices[j]
            
            if ((vi[1] > lon) != (vj[1] > lon)) and \
               (lat < (vj[0] - vi[0]) * (lon - vi[1]) / (vj[1] - vi[1]) + vi[0]):
                inside = not inside
            j = i
        
        return inside


class SafetyValidator:
    """
    Safety validation layer that operates INDEPENDENTLY of LLM.
    All hard limits are enforced here before any command reaches the vehicle.
    """
    
    def __init__(self, limits: Optional[HardLimits] = None):
        self.limits = limits or HardLimits()
        self.home_position: Optional[LatLonAlt] = None
        self.cylindrical_fence: Optional[CylindricalFence] = None
        self.inclusion_zones: List[Polygon] = []
        self.exclusion_zones: List[Polygon] = []
        self._initialized = False
    
    def initialize(self, home_position: LatLonAlt, 
                   cylindrical_fence: Optional[CylindricalFence] = None,
                   inclusion_zones: Optional[List[Polygon]] = None,
                   exclusion_zones: Optional[List[Polygon]] = None):
        """Initialize validator with geofence boundaries"""
        self.home_position = home_position
        self.cylindrical_fence = cylindrical_fence or CylindricalFence(
            center_lat=home_position.lat,
            center_lon=home_position.lon,
            radius_m=self.limits.max_distance_from_home_m,
            max_altitude_m=self.limits.max_altitude_relative_m
        )
        self.inclusion_zones = inclusion_zones or []
        self.exclusion_zones = exclusion_zones or []
        self._initialized = True
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """Calculate distance between two lat/lon points in meters"""
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    # ========== HARD LIMIT VALIDATORS ==========
    
    def validate_altitude(self, target_altitude_amsl: float,
                          target_altitude_relative: float) -> ValidationResult:
        """
        HARD LIMIT: Absolute altitude ceiling.
        Cannot be overridden by LLM or user.
        """
        if target_altitude_amsl > self.limits.max_altitude_amsl_m:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.ABORT,
                reason=f"HARD LIMIT: Altitude {target_altitude_amsl}m AMSL exceeds "
                       f"ceiling {self.limits.max_altitude_amsl_m}m",
                hard_limit_violated="max_altitude_amsl"
            )
        
        if target_altitude_relative > self.limits.max_altitude_relative_m:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.ABORT,
                reason=f"HARD LIMIT: Relative altitude {target_altitude_relative}m "
                       f"exceeds limit {self.limits.max_altitude_relative_m}m",
                hard_limit_violated="max_altitude_relative"
            )
        
        # Warning zone
        if target_altitude_relative > (self.limits.max_altitude_relative_m - 
                                        self.limits.altitude_buffer_m):
            return ValidationResult(
                is_valid=True,
                action=ValidationAction.WARN,
                reason=f"WARNING: Altitude {target_altitude_relative}m near ceiling"
            )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason="Altitude within limits"
        )
    
    def validate_distance(self, target_position: LatLonAlt) -> ValidationResult:
        """
        HARD LIMIT: Maximum distance from home.
        Cannot be overridden.
        """
        if not self.home_position:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.REJECT,
                reason="Validator not initialized with home position"
            )
        
        horizontal_dist = self.haversine_distance(
            target_position.lat, target_position.lon,
            self.home_position.lat, self.home_position.lon
        )
        
        if horizontal_dist > self.limits.max_distance_from_home_m:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.FORCE_RTL,
                reason=f"HARD LIMIT: Distance {horizontal_dist:.0f}m from home exceeds "
                       f"maximum {self.limits.max_distance_from_home_m}m",
                hard_limit_violated="max_distance_from_home"
            )
        
        # Warning threshold
        if horizontal_dist > (self.limits.max_distance_from_home_m * 
                              self.limits.distance_warning_threshold):
            return ValidationResult(
                is_valid=True,
                action=ValidationAction.WARN,
                reason=f"WARNING: Distance {horizontal_dist:.0f}m near limit"
            )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason="Distance within limits"
        )
    
    def validate_battery_mission(self, 
                                  mission_duration_s: float,
                                  mission_distance_m: float,
                                  current_battery_percent: float,
                                  battery_capacity_wh: float,
                                  avg_consumption_w: float) -> ValidationResult:
        """
        HARD LIMIT: Battery must support mission + RTL + safety buffer.
        """
        # Calculate energy requirements
        mission_energy_wh = (mission_duration_s / 3600) * avg_consumption_w * \
                           self.limits.battery_safety_factor
        
        # RTL estimate (conservative: same distance back, slower speed)
        rtl_duration_s = (mission_distance_m / 8.0)  # Assume 8 m/s RTL speed
        rtl_energy_wh = (rtl_duration_s / 3600) * avg_consumption_w * \
                       self.limits.battery_safety_factor
        
        total_required_wh = mission_energy_wh + rtl_energy_wh
        required_percent = (total_required_wh / battery_capacity_wh) * 100
        
        available_for_mission = current_battery_percent - \
                               self.limits.min_battery_rtl_percent
        
        if required_percent > available_for_mission:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.REJECT,
                reason=f"HARD LIMIT: Mission requires {required_percent:.1f}% battery, "
                       f"but must reserve {self.limits.min_battery_rtl_percent}% "
                       f"for RTL. Available: {available_for_mission:.1f}%",
                hard_limit_violated="min_battery_rtl"
            )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason="Battery sufficient for mission + RTL reserve"
        )
    
    def check_battery_rtl_trigger(self, current_battery_percent: float) -> ValidationResult:
        """
        HARD LIMIT: Force RTL when battery below threshold.
        This is checked continuously during flight.
        """
        if current_battery_percent <= self.limits.battery_land_immediate_percent:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.LAND_IMMEDIATE,
                reason=f"HARD LIMIT: Battery {current_battery_percent:.1f}% at emergency level. "
                       f"Immediate landing required.",
                hard_limit_violated="battery_emergency"
            )
        
        if current_battery_percent <= self.limits.min_battery_rtl_percent:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.FORCE_RTL,
                reason=f"HARD LIMIT: Battery {current_battery_percent:.1f}% below RTL threshold "
                       f"{self.limits.min_battery_rtl_percent}%. Returning to launch.",
                hard_limit_violated="min_battery_rtl"
            )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason="Battery above RTL threshold"
        )
    
    def validate_geofence_position(self, position: LatLonAlt) -> ValidationResult:
        """
        HARD LIMIT: Real-time geofence checking.
        Exclusion zones are ABSOLUTE - no entry allowed.
        """
        # Check exclusion zones - ABSOLUTE
        for exclusion in self.exclusion_zones:
            if exclusion.contains((position.lat, position.lon)):
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.FORCE_RTL,
                    reason=f"HARD LIMIT: Position ({position.lat:.6f}, {position.lon:.6f}) "
                           f"inside EXCLUSION ZONE. Immediate RTL.",
                    hard_limit_violated="exclusion_zone_breach"
                )
        
        # Check cylindrical fence
        if self.cylindrical_fence:
            dist_from_center = self.haversine_distance(
                position.lat, position.lon,
                self.cylindrical_fence.center_lat,
                self.cylindrical_fence.center_lon
            )
            if dist_from_center > self.cylindrical_fence.radius_m:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.FORCE_RTL,
                    reason=f"HARD LIMIT: Distance from center {dist_from_center:.0f}m "
                           f"exceeds fence radius {self.cylindrical_fence.radius_m}m",
                    hard_limit_violated="cylindrical_fence_breach"
                )
        
        # Check inclusion zones (if defined)
        if self.inclusion_zones:
            in_any_inclusion = any(
                zone.contains((position.lat, position.lon))
                for zone in self.inclusion_zones
            )
            if not in_any_inclusion:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.FORCE_RTL,
                    reason=f"HARD LIMIT: Position outside all inclusion zones",
                    hard_limit_violated="inclusion_zone_breach"
                )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason="Position within geofence"
        )
    
    def validate_mission_waypoints(self, waypoints: List[LatLonAlt]) -> ValidationResult:
        """
        HARD LIMIT: Pre-flight mission validation.
        All waypoints must be within safe envelope.
        """
        if not self._initialized:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.REJECT,
                reason="Validator not initialized"
            )
        
        for i, wp in enumerate(waypoints):
            # Validate altitude
            alt_result = self.validate_altitude(wp.alt_amsl, wp.alt_relative)
            if not alt_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: Waypoint {i} altitude violation - {alt_result.reason}",
                    hard_limit_violated=alt_result.hard_limit_violated
                )
            
            # Validate distance
            dist_result = self.validate_distance(wp)
            if not dist_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: Waypoint {i} distance violation - {dist_result.reason}",
                    hard_limit_violated=dist_result.hard_limit_violated
                )
            
            # Validate geofence envelope
            fence_result = self.validate_geofence_position(wp)
            if not fence_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: Waypoint {i} geofence violation - {fence_result.reason}",
                    hard_limit_violated=fence_result.hard_limit_violated
                )
            
            # Check buffer zones
            if self.cylindrical_fence:
                dist_from_home = self.haversine_distance(
                    wp.lat, wp.lon,
                    self.home_position.lat, self.home_position.lon
                )
                if dist_from_home > (self.cylindrical_fence.radius_m - 
                                     self.limits.geofence_buffer_m):
                    return ValidationResult(
                        is_valid=False,
                        action=ValidationAction.REJECT,
                        reason=f"HARD LIMIT: Waypoint {i} too close to fence boundary "
                               f"({dist_from_home:.0f}m, buffer={self.limits.geofence_buffer_m}m)",
                        hard_limit_violated="geofence_buffer"
                    )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason=f"All {len(waypoints)} waypoints validated within hard limits"
        )
    
    def validate_command(self, command_type: str, 
                         parameters: dict) -> ValidationResult:
        """
        Main entry point for command validation.
        Called before ANY command reaches the flight controller.
        """
        # Reject known dangerous commands
        dangerous_commands = {
            "disable_geofence": "HARD LIMIT: Geofence cannot be disabled",
            "set_gf_action_none": "HARD LIMIT: GF_ACTION cannot be set to None",
            "disable_battery_failsafe": "HARD LIMIT: Battery failsafe cannot be disabled",
            "disable_altitude_limit": "HARD LIMIT: Altitude limit cannot be disabled",
        }
        
        if command_type in dangerous_commands:
            return ValidationResult(
                is_valid=False,
                action=ValidationAction.REJECT,
                reason=dangerous_commands[command_type],
                hard_limit_violated="safety_system_tampering"
            )
        
        # Validate position commands
        if command_type in ["goto", "waypoint", "position_set"]:
            if "position" in parameters:
                pos = parameters["position"]
                target = LatLonAlt(
                    lat=pos.get("lat"),
                    lon=pos.get("lon"),
                    alt_amsl=pos.get("alt_amsl", 0),
                    alt_relative=pos.get("alt_relative", 0)
                )
                
                # Run all validations
                results = [
                    self.validate_altitude(target.alt_amsl, target.alt_relative),
                    self.validate_distance(target),
                    self.validate_geofence_position(target)
                ]
                
                for result in results:
                    if not result.is_valid:
                        return result
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason="Command passed hard limit validation"
        )


# ========== PARAMETER VALIDATION LAYER ==========

class ParameterValidator:
    """
    Validates parameter changes to prevent safety system tampering.
    """
    
    # Parameters that CANNOT be modified to unsafe values
    PROTECTED_PARAMETERS = {
        "GF_ACTION": {
            "allowed_values": [2, 3, 4, 5],  # Hold, RTL, Terminate, Land
            "forbidden_values": [0, 1],  # None, Warning
            "reason": "GF_ACTION must enforce safety on breach"
        },
        "GF_MAX_VER_DIST": {
            "max_value": 120,
            "reason": "Maximum vertical distance cannot exceed hard ceiling"
        },
        "GF_MAX_HOR_DIST": {
            "max_value": 500,
            "reason": "Maximum horizontal distance cannot exceed hard limit"
        },
        "BAT_CRIT_THR": {
            "min_value": 0.20,  # 20%
            "reason": "Critical battery threshold cannot be too low"
        },
        "CBRK_FLIGHTTERM": {
            "forbidden_values": [121212],  # Disabled
            "allowed_values": [0],  # Enabled
            "reason": "Flight termination must be available for emergencies"
        }
    }
    
    def validate_parameter_set(self, param_name: str, 
                                param_value: any) -> ValidationResult:
        """
        Validate a parameter change request.
        Rejects changes that would compromise safety.
        """
        if param_name not in self.PROTECTED_PARAMETERS:
            return ValidationResult(
                is_valid=True,
                action=ValidationAction.ALLOW,
                reason="Parameter not in protected list"
            )
        
        rules = self.PROTECTED_PARAMETERS[param_name]
        
        # Check forbidden values
        if "forbidden_values" in rules:
            if param_value in rules["forbidden_values"]:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: Cannot set {param_name}={param_value}. "
                           f"{rules['reason']}",
                    hard_limit_violated="parameter_safety"
                )
        
        # Check allowed values
        if "allowed_values" in rules:
            if param_value not in rules["allowed_values"]:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: {param_name} must be one of "
                           f"{rules['allowed_values']}. {rules['reason']}",
                    hard_limit_violated="parameter_safety"
                )
        
        # Check max value
        if "max_value" in rules:
            if param_value > rules["max_value"]:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: {param_name} cannot exceed "
                           f"{rules['max_value']}. {rules['reason']}",
                    hard_limit_violated="parameter_safety"
                )
        
        # Check min value
        if "min_value" in rules:
            if param_value < rules["min_value"]:
                return ValidationResult(
                    is_valid=False,
                    action=ValidationAction.REJECT,
                    reason=f"HARD LIMIT: {param_name} cannot be below "
                           f"{rules['min_value']}. {rules['reason']}",
                    hard_limit_violated="parameter_safety"
                )
        
        return ValidationResult(
            is_valid=True,
            action=ValidationAction.ALLOW,
            reason=f"Parameter {param_name}={param_value} accepted"
        )


# ========== EXECUTION WRAPPER ==========

class SafeExecutor:
    """
    Wrapper that enforces safety validation on all commands.
    This is the ONLY path to the flight controller.
    """
    
    def __init__(self, validator: SafetyValidator, 
                 param_validator: ParameterValidator):
        self.validator = validator
        self.param_validator = param_validator
        self.emergency_active = False
    
    def execute(self, command_type: str, parameters: dict) -> dict:
        """
        Execute a command with full safety validation.
        Returns result dict with status and action taken.
        """
        # Step 1: Validate command
        validation = self.validator.validate_command(command_type, parameters)
        
        if not validation.is_valid:
            # Log the rejection
            self._log_rejection(command_type, validation)
            
            # Execute safety action
            self._execute_safety_action(validation.action, validation.reason)
            
            return {
                "success": False,
                "rejected": True,
                "reason": validation.reason,
                "hard_limit": validation.hard_limit_violated,
                "action_taken": validation.action.value
            }
        
        # Step 2: Execute (would connect to actual vehicle here)
        return {
            "success": True,
            "rejected": False,
            "warning": validation.action == ValidationAction.WARN,
            "reason": validation.reason
        }
    
    def set_parameter(self, param_name: str, param_value: any) -> dict:
        """
        Set a parameter with safety validation.
        """
        validation = self.param_validator.validate_parameter_set(
            param_name, param_value
        )
        
        if not validation.is_valid:
            self._log_rejection(f"SET_PARAM {param_name}", validation)
            return {
                "success": False,
                "rejected": True,
                "reason": validation.reason,
                "hard_limit": validation.hard_limit_violated
            }
        
        # Would set parameter on actual vehicle here
        return {
            "success": True,
            "rejected": False
        }
    
    def _log_rejection(self, command: str, validation: ValidationResult):
        """Log rejected commands for audit trail"""
        # Implementation would log to secure audit log
        pass
    
    def _execute_safety_action(self, action: ValidationAction, reason: str):
        """Execute emergency safety action"""
        if action == ValidationAction.FORCE_RTL:
            # Trigger RTL on flight controller
            pass
        elif action == ValidationAction.LAND_IMMEDIATE:
            # Trigger immediate landing
            pass
        elif action == ValidationAction.TERMINATE:
            # Flight termination (kill motors)
            pass


# ========== USAGE EXAMPLE ==========

def example_usage():
    """Example of how to use the safety validation layer"""
    
    # Initialize hard limits
    limits = HardLimits(
        max_altitude_amsl_m=120,
        max_distance_from_home_m=500,
        min_battery_rtl_percent=25
    )
    
    # Create validators
    validator = SafetyValidator(limits)
    param_validator = ParameterValidator()
    
    # Initialize with home position
    home = LatLonAlt(lat=37.7749, lon=-122.4194, alt_amsl=50, alt_relative=0)
    validator.initialize(home)
    
    # Create safe executor
    executor = SafeExecutor(validator, param_validator)
    
    # Example 1: Valid command
    result = executor.execute("goto", {
        "position": {"lat": 37.7750, "lon": -122.4195, "alt_relative": 30}
    })
    print(f"Valid command: {result}")
    
    # Example 2: Altitude violation (REJECTED)
    result = executor.execute("goto", {
        "position": {"lat": 37.7750, "lon": -122.4195, "alt_amsl": 150}
    })
    print(f"Altitude violation: {result}")
    
    # Example 3: Dangerous parameter (REJECTED)
    result = executor.set_parameter("GF_ACTION", 0)  # Try to disable
    print(f"Parameter rejection: {result}")


if __name__ == "__main__":
    example_usage()
```

---

## 5. Additional PX4 Parameters (from Context7 Research)

### 5.1 GF_SOURCE - Position Source Selection

| Value | Source | Description | Recommendation |
|-------|--------|-------------|----------------|
| 0 | GPOS | Global Position from state estimator | Default - depends on EKF |
| 1 | GPS | Raw GPS position | **Recommended** - removes estimator dependency |

**Setting:**
```
GF_SOURCE = 1  # Use GPS for geofence checking
```

### 5.2 GF_PREDICT - Pre-emptive Geofence Triggering

**Status:** EXPERIMENTAL

From PX4 documentation: "WARNING: This experimental feature may cause flyaways. Use at your own risk."

- Predicts vehicle trajectory and triggers breach before it occurs
- Re-routes vehicle to safe hold position
- **Recommendation: DO NOT ENABLE (set to 0)**

```
GF_PREDICT = 0  # Disabled - not safe for production autonomous ops
```

### 5.3 RTL (Return to Launch) Parameters

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `RTL_RETURN_ALT` | Return altitude in meters | 60m | 60m |
| `RTL_DESCEND_ALT` | Loiter/descend altitude | 30m | 30m |
| `RTL_MIN_DIST` | Min distance for cone calculation | 10m | 10m |
| `RTL_CONE_ANG` | Half-angle of return cone | 0 (no cone) | 45 |
| `RTL_LAND_DELAY` | Delay before landing | 0s | -1 (don't auto-land) |

**RTL_CONE_ANG Values:**
- 0: No cone, always climb to RTL_RETURN_ALT
- 25: 25 degrees half cone angle
- 45: 45 degrees half cone angle
- 65: 65 degrees half cone angle
- 80: 80 degrees half cone angle
- 90: Only climb to RTL_DESCEND_ALT

### 5.4 Battery Failsafe Parameters

| Parameter | Description | Range | Recommended |
|-----------|-------------|-------|-------------|
| `COM_LOW_BAT_ACT` | Battery failsafe action | 0-3 | 3 |
| `BAT_CRIT_THR` | Critical battery threshold | 0.0-0.5 | 0.15 (15%) |
| `BAT_EMERGEN_THR` | Emergency battery threshold | 0.0-0.5 | 0.10 (10%) |

**COM_LOW_BAT_ACT Values:**
- 0: Warning only
- 1: Return mode (RTL)
- 2: Land mode
- 3: **Return at critical level, land at emergency level (RECOMMENDED)**

### 5.5 CBRK_FLIGHTTERM - Flight Termination Circuit Breaker

Controls the circuit breaker for flight termination:

| Value | Meaning | Notes |
|-------|---------|-------|
| 0 | Flight termination ENABLED | Required for parachute/emergency stop |
| 121212 | Flight termination DISABLED | Default - motors keep running on failure |

**Important:** This circuit breaker does NOT affect RC loss, data link loss, geofence, or takeoff failure detection - those operate independently.

**Recommendation for autonomous drones:**
```
CBRK_FLIGHTTERM = 0  # Enable flight termination capability
```

This allows emergency motor kill via:
- MAVLink command `VEHICLE_CMD_DO_FLIGHTTERMINATION` (command 185)
- Failure detector triggers
- GF_ACTION=4 (Terminate) on geofence breach

### 5.6 MAV_CMD_NAV_GUIDED_LIMITS (Command 90)

Dynamic guided control limits via MAVLink:

```
VEHICLE_CMD_NAV_GUIDED_LIMITS = 90
- param1: Timeout (seconds) - max time external controller can control
- param2: Absolute altitude min AMSL (0 = no limit)
- param3: Absolute altitude max AMSL (0 = no limit)  ← Use for dynamic ceiling
- param4: Horizontal move limit from command position
```

**Use case:** Set temporary limits for LLM-guided flight that are MORE restrictive than hard limits.

---

## 6. Emergency Override Procedures

### 6.1 Human Operator Override Methods

| Method | Trigger | Effect | Notes |
|--------|---------|--------|-------|
| **RC Mode Switch** | Physical switch on transmitter | Switch to manual/posctl | Must be configured in QGC |
| **Kill Switch** | Dedicated RC switch | Immediate motor stop | Emergency only |
| **Return Switch** | Dedicated RTL switch | Trigger RTL mode | Safer than kill switch |
| **GCS Command** | QGroundControl | Change mode, RTL, land | Requires data link |
| **MAVLink Command** | Direct command injection | Any mode change | Same as GCS |

### 6.2 Emergency Procedure Decision Tree

```
EMERGENCY DETECTED
        │
        ├─ Can you communicate with drone? ──YES──┐
        │                                         │
        NO                                        ▼
        │                              Send RTL command via MAVLink
        ▼                              or switch to RTL mode
Check failsafe settings:
- Data link loss action?
- RC loss action?
        │
        ▼
Default: Drone executes
pre-configured failsafe
(Return/Land/Hold)

        │
        ▼
CRITICAL SITUATION
(Flyaway/crash imminent)
        │
        ├─ Is drone over safe area? ──YES──┐
        │                                  ▼
        NO                        Flight termination
        │                         (kill motors)
        ▼                         if CBRK_FLIGHTTERM=0
Attempt RTL or Land
regardless of location
```

### 6.3 PX4 Native Failsafe Actions

PX4 has built-in failsafes that operate independently of the LLM:

| Failsafe | Trigger | Default Action | Configurable |
|----------|---------|----------------|--------------|
| RC Loss | No RC signal for timeout | Return/Land/Hold | Yes (NAV_RCL_ACT) |
| Data Link Loss | No MAVLink heartbeat | Return/Land/Continue | Yes (COM_DL_LOSS_ACT) |
| Geofence Breach | Outside GF_MAX_HOR/VER_DIST | RTL (GF_ACTION=3) | Yes |
| Low Battery | Below BAT_CRIT_THR | RTL then Land | Yes (COM_LOW_BAT_ACT) |
| Position Loss | No valid position estimate | Land/Descend | Yes (COM_POSCTL_NAVL) |

---

## 7. QGroundControl Geofence Upload Format

### 7.1 Polygon Geofence JSON Format

```json
{
    "geoFence": {
        "polygons": [
            {
                "inclusion": true,
                "polygon": [
                    [47.39807773798406, 8.543834631785785],
                    [47.39983519888905, 8.550024648373267],
                    [47.39641100087146, 8.54499282423751],
                    [47.395590322265186, 8.539435808992085]
                ],
                "version": 1
            }
        ],
        "circles": [],
        "version": 2
    }
}
```

### 7.2 Circular Geofence JSON Format

```json
{
    "geoFence": {
        "circles": [
            {
                "circle": {
                    "center": [47.39756763610029, 8.544649762407738],
                    "radius": 319.85
                },
                "inclusion": true,
                "version": 1
            }
        ],
        "polygons": [],
        "version": 2
    }
}
```

**Critical Rules:**
1. Geofence MUST include Home position (otherwise rejected by PX4)
2. If vehicle is flying, any geofence that would immediately breach is rejected
3. Must use clockwise winding order for polygons

---

## Summary: Key Safety Principles

1. **Hard Limits are Absolute**: Cannot be overridden by LLM, user, or mission planning
2. **Validation at Tool Layer**: Safety checks occur BEFORE any command reaches the vehicle
3. **Immutable Boundaries**: Hard limits are set at startup and cannot be modified
4. **Automatic Enforcement**: Violations trigger automatic safety actions (RTL, Land, Terminate)
5. **Audit Trail**: All rejections are logged for post-flight analysis
6. **Fail-Safe Defaults**: If validation system fails, default to safest action (RTL/Land)
7. **Hardware Integration**: Critical limits also set directly in flight controller (PX4) parameters
8. **Layered Defense**: Python validation + PX4 parameters provide redundancy
9. **Emergency Override**: Human operator can always take control via RC or GCS
10. **Continuous Monitoring**: Battery and position are checked continuously during flight

### Complete PX4 Safety Parameters Checklist

```python
# Upload these to PX4 before first flight
PX4_SAFETY_PARAMS = {
    # Geofence (Cylindrical)
    "GF_ACTION": 3,              # RTL on breach (DO NOT CHANGE)
    "GF_MAX_HOR_DIST": 500,      # 500m horizontal limit
    "GF_MAX_VER_DIST": 120,      # 120m altitude limit (below 400ft)
    "GF_SOURCE": 1,              # GPS source (no estimator dependency)
    "GF_PREDICT": 0,             # Disable experimental prediction
    
    # Battery Failsafe
    "COM_LOW_BAT_ACT": 3,        # Return at critical, land at emergency
    "BAT_CRIT_THR": 0.15,        # 15% critical threshold
    "BAT_EMERGEN_THR": 0.10,     # 10% emergency threshold
    
    # RTL Behavior
    "RTL_RETURN_ALT": 60,        # Return at 60m
    "RTL_DESCEND_ALT": 30,       # Descend to 30m before landing
    "RTL_CONE_ANG": 45,          # 45-degree cone for altitude calculation
    "RTL_MIN_DIST": 10,          # 10m minimum distance for cone
    
    # Flight Termination (for emergency)
    "CBRK_FLIGHTTERM": 0,        # Enable flight termination capability
    
    # Position Loss Failsafe
    "COM_POSCTL_NAVL": 0,        # Land immediately if position lost
    
    # Data Link Loss
    "COM_DL_LOSS_EN": 1,         # Enable data link loss failsafe
    "COM_DL_LOSS_T": 10,         # 10 second timeout
    "COM_DL_LOSS_ACT": 1,        # RTL on data link loss
}
```

---

## References

### PX4 Documentation (via Context7)

1. **PX4 Geofence Guide**: https://docs.px4.io/main/en/flying/geofence.html
2. **Safety Configuration**: https://docs.px4.io/main/en/config/safety.html
3. **Parameter Reference**: https://docs.px4.io/main/en/advanced_config/parameter_reference.html
4. **Return Mode**: https://docs.px4.io/main/en/flight_modes/return.html
5. **MAVLink Vehicle Commands**: https://mavlink.io/en/messages/common.html

### Key MAVLink Commands

- `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION` - Define polygon inclusion zone
- `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION` - Define polygon exclusion zone  
- `MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION` - Define circular inclusion zone
- `MAV_CMD_NAV_GUIDED_LIMITS` (90) - Set guided control limits
- `MAV_CMD_DO_FLIGHTTERMINATION` (185) - Emergency flight termination
- `MAV_CMD_NAV_RETURN_TO_LAUNCH` - Trigger RTL mode
- `MAV_CMD_NAV_LAND` - Trigger land mode

### Regulatory

1. **FAA Part 107**: 14 CFR Part 107 - Small Unmanned Aircraft Regulations
2. **EASA Easy Access Rules**: Regulation (EU) 2019/947
3. **ICAO Annex 2**: Rules of the Air

---

*Research compiled from PX4 Autopilot documentation via Context7*
*Enhanced with additional parameter details, RTL settings, and emergency procedures*
*Document version: 2.0*
*Date: 2026-04-09*  
*Next Review: Before first autonomous flight test*  
*Status: READY FOR IMPLEMENTATION*  

**WARNING**: This document defines SAFETY-CRITICAL hard limits. Any modification requires safety review and flight testing.

1. **Hard Limits are Absolute**: Cannot be overridden by LLM, user, or mission planning
2. **Validation at Tool Layer**: Safety checks occur BEFORE any command reaches the vehicle
3. **Immutable Boundaries**: Hard limits are set at startup and cannot be modified
4. **Automatic Enforcement**: Violations trigger automatic safety actions (RTL, Land, Terminate)
5. **Audit Trail**: All rejections are logged for post-flight analysis
6. **Fail-Safe Defaults**: If validation system fails, default to safest action (RTL/Land)
7. **Hardware Integration**: Critical limits also set directly in flight controller (PX4) parameters

### Critical Parameters to Set on PX4

```python
# These PX4 parameters should be set directly on the flight controller
# to provide hardware-level enforcement

PX4_SAFETY_PARAMS = {
    # Geofence
    "GF_ACTION": 3,              # RTL on breach
    "GF_MAX_HOR_DIST": 500,      # 500m distance limit
    "GF_MAX_VER_DIST": 120,      # 120m altitude limit
    "GF_SOURCE": 1,              # GPS source (no estimator dependency)
    
    # Battery
    "BAT_CRIT_THR": 0.25,        # 25% RTL
    "BAT_EMERGEN_THR": 0.10,     # 10% emergency land
    "COM_LOW_BAT_ACT": 2,        # RTL at critical
    
    # Flight termination
    "CBRK_FLIGHTTERM": 0,        # Enabled (not 121212)
    
    # Altitude limits (additional)
    "MPC_ALT_MAX": 120,          # Maximum altitude
}
```

---

*Research compiled from PX4 Autopilot documentation via Context7*
*Document version: 1.0*
*Date: 2026-04-09*
