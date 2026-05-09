"""
Confirmation workflow for human-in-the-loop drone operations.

Provides confirmation dialogs for critical flight operations requiring human approval.

SAFETY RATIONALE:
================
Autonomous drones operate in physical space where errors can cause property damage,
injury, or loss of life. While LLMs can plan missions and process telemetry, they:

1. May hallucinate or misinterpret sensor data
2. Cannot be held legally accountable for accidents
3. Lack true situational awareness of the physical environment
4. May make errors in edge cases not seen in training

Human-in-the-loop confirmation provides a critical safety layer where a human operator
must explicitly approve:
- Mission plans before takeoff
- Arming the motors (enabling potential flight)
- How to handle unexpected situations (exceptions)

This follows aviation best practices where a human pilot has final authority.

CONFIRMATION LEVELS:
===================
The system uses progressive confirmation with increasing scrutiny:

Level 1 - Pre-Flight Confirmation:
  - Trigger: Before any takeoff
  - Reviews: Mission plan, waypoints, duration, altitude, distance
  - Default action: Reject (safe - stay on ground)
  - User options: yes (proceed), no (retry later), abort (cancel mission)

Level 2 - Pre-Arm Confirmation:
  - Trigger: Before arming motors
  - Reviews: Battery, GPS status, position, flight mode
  - Default action: Reject (safe - stay disarmed)
  - User options: yes (arm), no (stay disarmed), abort (end mission)

Level 3 - Exception Confirmation:
  - Trigger: During flight when anomalies detected
  - Reviews: Exception type (person detected, obstacle, low battery, etc.)
  - Default action: Pause/wait (safe - don't proceed blindly)
  - User options: yes (continue despite risk), no (pause), abort (RTL/emergency)

Level 4 - Timeout:
  - Trigger: When user doesn't respond within timeout window
  - Action: Returns to default safe state
  - Purpose: Prevents indefinite waiting in dangerous situations

MCP INTEGRATION:
===============
This module is designed to work with the MCP (Model Context Protocol) server:

1. MCP Tool Handlers:
   - When an LLM agent calls a drone tool (e.g., `takeoff`, `goto`), the tool handler
     creates the appropriate confirmation request
   - The handler passes control to ConfirmationManager

2. Response Flow:
   - Agent calls tool → Tool validates parameters → ConfirmationManager requests approval
   - If confirmed → Tool executes via GuardianProcess → Result returned to agent
   - If rejected → Tool returns rejection message, mission may continue or abort

3. Response Submission:
   - The `submit_response()` method allows MCP tool handlers to inject responses
   - In production, responses may come from:
     * CLI stdin (interactive operator)
     * Web UI button clicks
     * API calls from ground control station
     * Voice commands (with confirmation)

4. GuardianProcess Integration:
   - All actual drone commands pass through GuardianProcess after confirmation
   - GuardianProcess enforces hard safety limits (geofence, altitude, speed)
   - Confirmation is the "soft" safety layer (human judgment)
   - GuardianProcess is the "hard" safety layer (programmatic limits)

WORKFLOW PROGRESSION:
====================
A typical mission follows this confirmation flow:

1. PLANNING PHASE (no confirmation needed):
   Agent receives mission request → Plans waypoints → Calls `set_mission_plan`

2. PRE-FLIGHT PHASE (Level 1 confirmation):
   Agent calls `arm_and_takeoff` or `execute_mission`
   → ConfirmationManager.pre_flight_confirmation() displays mission plan
   → User reviews waypoints, altitude, duration
   → User responds: yes → proceed to pre-arm, no → wait and retry, abort → end

3. PRE-ARM PHASE (Level 2 confirmation):
   If pre-flight confirmed → ConfirmationManager.pre_arm_confirmation()
   → Displays telemetry (battery, GPS, position)
   → User verifies drone is ready and safe to arm
   → User responds: yes → GuardianProcess arms motors, no → stay disarmed

4. IN-FLIGHT PHASE (Level 3 confirmation for exceptions):
   During flight, if ExceptionMonitor detects:
   - Person detected → exception_confirmation(PERSON_DETECTED)
   - Obstacle ahead → exception_confirmation(OBSTACLE_DETECTED)
   - Low battery → exception_confirmation(LOW_BATTERY)
   - User decides: yes (continue), no (hover/wait), abort (RTL)

5. TIMEOUT HANDLING (Level 4):
   If user doesn't respond within timeout_s (default 10s):
   → timeout_confirmation() returns default_action
   → Default is always the safest option (no, abort, or pause)

6. MISSION COMPLETION:
   Mission completes or aborts → Drone RTL or lands → Ready for next mission

CONFIGURATION:
=============
The ConfirmationConfig dataclass allows customization:

- timeout_s: How long to wait for user response (default: 10 seconds)
  Shorter = more responsive but risk of false timeouts
  Longer = gives operator more time but delays action

- show_telemetry_details: Whether to show full telemetry in confirmations
  True = verbose output for debugging/awareness
  False = minimal output for experienced operators

- require_explicit_abort: How to interpret "no" response
  True = "no" means abort mission entirely
  False = "no" means decline this step but allow retry later

USAGE EXAMPLES:
==============

Basic usage with ConfirmationManager:

    # Initialize with default config
    manager = ConfirmationManager()

    # Or with custom config
    config = ConfirmationConfig(
        timeout_s=15.0,
        show_telemetry_details=True,
        require_explicit_abort=True
    )
    manager = ConfirmationManager(config)

    # Pre-flight confirmation
    plan = MissionPlan(
        waypoints=[{"lat": 37.7749, "lon": -122.4194, "alt": 50}],
        estimated_duration_s=120,
        max_altitude_m=50,
        max_distance_m=200,
        description="Survey mission Alpha"
    )
    confirmed = await manager.pre_flight_confirmation(plan)
    if not confirmed:
        # Handle rejection - maybe ask user what to change
        return {"status": "rejected", "reason": "User declined mission"}

    # Pre-arm confirmation
    telemetry = TelemetrySnapshot(
        position={"lat": 37.7749, "lon": -122.4194, "alt": 0},
        battery_percent=85.0,
        gps_fix=True,
        satellite_count=12,
        flight_mode="HOLD",
        armed=False,
        in_air=False
    )
    can_arm = await manager.pre_arm_confirmation(telemetry)
    if not can_arm:
        return {"status": "rejected", "reason": "User declined to arm"}

    # Exception handling during flight
    response = await manager.exception_confirmation(
        ExceptionType.PERSON_DETECTED,
        context={"distance_m": 15.0, "confidence": 0.92}
    )
    if response == ConfirmationResponse.ABORT:
        await drone.action.return_to_launch()
    elif response == ConfirmationResponse.NO:
        await drone.action.hold()
    elif response == ConfirmationResponse.YES:
        # Continue despite detection (acknowledge risk)
        pass

MCP Tool Integration Example:

    @mcp_server.tool()
    async def takeoff(altitude: float) -> dict:
        # First, get current telemetry for pre-arm check
        telemetry = await get_telemetry_snapshot()

        # Request pre-arm confirmation
        manager = ConfirmationManager()
        confirmed = await manager.pre_arm_confirmation(telemetry)

        if not confirmed:
            return {
                "status": "rejected",
                "reason": "User declined to arm motors"
            }

        # Only proceed if confirmed - GuardianProcess enforces hard limits
        return await guardian_process.execute_takeoff(altitude)

RESPONSE OPTIONS:
===============
For all confirmations, the user has three response options:

- "yes"  : Approve and proceed with the operation
- "no"   : Decline this step (may allow retry depending on config)
- "abort": Cancel the entire mission/operation

The default action on timeout is always the safest option:
- Pre-flight: "no" (stay on ground, can retry)
- Pre-arm: "no" (stay disarmed)
- Exceptions: "no" (pause and wait)

EXCEPTION TYPES:
===============
The system handles these exception types requiring human judgment:

- PERSON_DETECTED: Vision system detected human in flight path
- OBSTACLE_DETECTED: Lidar/radar detected obstacle ahead
- NO_FLY_ZONE: Approaching restricted airspace
- LOW_BATTERY: Battery below safe threshold
- WEATHER_WARNING: Wind/rain/visibility issues
- GPS_DEGRADATION: Position accuracy degrading
- CUSTOM: Any other unexpected situation

Each exception type has a descriptive message explaining the situation
and the risks of continuing.
"""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfirmationResponse(str, Enum):
    """Possible responses from confirmation dialogs.

    These are the standardized responses a user can provide when
    prompted for confirmation. Using an Enum ensures type safety
    and prevents typos in response handling code.

    Attributes:
        YES: User approves the operation - proceed as requested
        NO: User declines this step - safe default, may allow retry
        ABORT: User wants to cancel entire mission/operation
        TIMEOUT: No response received within timeout window - use default
    """

    YES = "yes"
    NO = "no"
    ABORT = "abort"
    TIMEOUT = "timeout"


class ExceptionType(str, Enum):
    """Types of exceptions that may require confirmation.

    These represent situations where the drone has encountered
    something unexpected that requires human judgment to proceed.

    Each type maps to a human-readable description used in the
    confirmation dialog to help the operator understand the situation.

    Safety Note: These are "soft" exceptions - the GuardianProcess
    may also enforce "hard" limits that override user decisions
    (e.g., geofence violations, critical battery failsafes).

    Attributes:
        PERSON_DETECTED: Vision system detected human in flight path
        OBSTACLE_DETECTED: Sensor detected obstacle ahead
        NO_FLY_ZONE: Approaching restricted airspace boundary
        LOW_BATTERY: Battery below safe operating threshold
        WEATHER_WARNING: Environmental conditions deteriorating
        GPS_DEGRADATION: Position accuracy falling below safe limits
        CUSTOM: Any other situation requiring operator judgment
    """

    PERSON_DETECTED = "person_detected"
    OBSTACLE_DETECTED = "obstacle_detected"
    NO_FLY_ZONE = "no_fly_zone"
    LOW_BATTERY = "low_battery"
    WEATHER_WARNING = "weather_warning"
    GPS_DEGRADATION = "gps_degradation"
    CUSTOM = "custom"


@dataclass
class MissionPlan:
    """Represents a mission plan for pre-flight confirmation.

    This dataclass holds all information about a planned mission
    that the operator needs to review before approving takeoff.

    The confirmation dialog displays these details in a formatted
    table showing waypoints, duration, altitude, and distance
    limits so the operator can verify the plan is safe and correct.

    Attributes:
        waypoints: List of waypoint dictionaries with lat/lon/alt.
            Example: [{"lat": 37.7749, "lon": -122.4194, "alt": 50}]
        estimated_duration_s: Estimated mission duration in seconds.
            Used to inform operator how long drone will be airborne.
        max_altitude_m: Maximum planned altitude in meters.
            Shows highest point in mission - should be below legal limits.
        max_distance_m: Maximum planned distance from home in meters.
            Shows how far drone will travel - should be within radio range.
        description: Human-readable mission description.
            Helps operator understand the purpose of the mission.
    """

    waypoints: list[dict[str, float]] = field(default_factory=list)
    estimated_duration_s: float = 0.0
    max_altitude_m: float = 0.0
    max_distance_m: float = 0.0
    description: str = ""


@dataclass
class TelemetrySnapshot:
    """Snapshot of drone telemetry for pre-arm confirmation.

    This dataclass captures the critical drone state information
    that an operator must verify before approving arming.

    The pre-arm confirmation displays battery level (must be sufficient
    for planned mission), GPS status (must have fix for navigation),
    position (verify correct location), and flight mode (verify ready).

    Warnings are automatically generated for concerning states:
    - Battery < 30%: Warns of low power
    - No GPS fix: Warns navigation may be unsafe
    - < 6 satellites: Warns of poor GPS accuracy

    Attributes:
        position: Current position (lat, lon, alt). Used to verify
            drone is at expected location before takeoff.
        battery_percent: Battery level percentage (0-100). Should be
            sufficient for planned mission duration plus reserve.
        gps_fix: Whether GPS has a valid fix. Required for navigation.
        satellite_count: Number of GPS satellites in view. More = better
            accuracy. Minimum 6 recommended, 10+ preferred.
        flight_mode: Current flight mode (e.g., "HOLD", "MANUAL").
            Should be appropriate for arming (usually "HOLD").
        armed: Whether the drone is armed. Should be False before
            arming confirmation (otherwise redundant).
        in_air: Whether the drone is in the air. Should be False
            before takeoff confirmation.
    """

    position: Optional[dict[str, float]] = None
    battery_percent: float = 0.0
    gps_fix: bool = False
    satellite_count: int = 0
    flight_mode: str = "UNKNOWN"
    armed: bool = False
    in_air: bool = False


@dataclass
class ConfirmationConfig:
    """Configuration for confirmation workflow.

    This dataclass allows customization of confirmation behavior
    to suit different operational environments and risk tolerances.

    For example:
    - Research/testing: Longer timeout, verbose telemetry
    - Production operations: Shorter timeout, minimal output
    - High-risk environments: Require explicit abort, strict timeouts

    Attributes:
        timeout_s: Seconds to wait for user response before timeout.
            Default: 10 seconds. Shorter = more responsive but risk
            of false timeouts if operator is slow. Longer = gives
            operator more time but delays mission execution.
        show_telemetry_details: Whether to show full telemetry in confirmations.
            Default: True (verbose). Set to False for minimal output
            when operators are experienced and don't need details.
        require_explicit_abort: If True, 'no' counts as abort (end mission).
            If False, 'no' allows retry later (decline this attempt
            but keep mission active). Default: False (allow retry).
    """

    timeout_s: float = 10.0
    show_telemetry_details: bool = True
    require_explicit_abort: bool = False


# =============================================================================
# D2.6: NEW CONFIRMATION API
# =============================================================================
# Token-based confirmation system for programmatic confirmation flows.
# This allows MCP tools to request confirmation and wait for response
# via external mechanisms (CLI, web UI, API, etc.).


@dataclass(frozen=True)
class ConfirmationToken:
    """Immutable token representing a pending confirmation request.

    A ConfirmationToken is created when a confirmation is requested via
    ConfirmationManager.require(). The token contains:
    - A unique identifier for correlating responses
    - The action name that requires confirmation

    The token is returned to the caller who can then submit a response
    via ConfirmationManager.submit() with the same token string.

    Attributes:
        token: Unique identifier for this confirmation request.
            Generated using secrets.token_urlsafe() for cryptographic
            randomness. Used to correlate responses with requests.
        action: Human-readable action name (e.g., "arm_and_takeoff",
            "set_parameter", "initiate_rtl").

    Example:
        >>> token = await manager.require(
        ...     action="arm_and_takeoff",
        ...     destructive=True,
        ...     summary="Arm motors and takeoff to 15m",
        ...     payload={"altitude_m": 15.0}
        ... )
        >>> print(f"Waiting for confirmation: {token.token}")
        >>> # Later, from another context:
        >>> await manager.submit(token.token, approved=True, note="Operator approved")
    """

    token: str
    action: str


@dataclass
class PendingConfirmation:
    """Internal structure for tracking pending confirmations.

    This is used internally by ConfirmationManager to store the state
    of each pending confirmation request while waiting for a response.

    Attributes:
        event: asyncio.Event that will be set when response is received.
        response: Dict containing the response data (approved, note).
        action: The action being confirmed.
        summary: Human-readable summary for display.
        payload: Additional context data.
        created_at: Timestamp when the confirmation was requested.
        destructive: Whether this is a destructive/irreversible action.
    """

    event: asyncio.Event
    response: Optional[dict] = None
    action: str = ""
    summary: str = ""
    payload: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    destructive: bool = False


class ConfirmationManager:
    """
    Manages human-in-the-loop confirmation for critical drone operations.

    This class provides confirmation dialogs for operations that require
    explicit human approval before proceeding. It implements a
    progressive confirmation system with three levels:

    1. Pre-flight: Review mission plan before takeoff
    2. Pre-arm: Verify drone state before arming motors
    3. Exception: Handle unexpected situations during flight

    SAFETY ARCHITECTURE:
    ===================
    The confirmation system works alongside the GuardianProcess as
    part of a layered safety architecture:

    Layer 1 - ConfirmationManager (Soft Safety):
        Human operator approves/rejects operations based on judgment
        and situational awareness. This catches planning errors and
        unexpected conditions.

    Layer 2 - GuardianProcess (Hard Safety):
        Programmatic limits enforced regardless of confirmation.
        Includes geofence, max altitude, speed limits, battery failsafe.
        Cannot be overridden by operator.

    Layer 3 - PX4 Failsafes (Emergency Safety):
        Autopilot-level protections that activate automatically.
        Includes RC loss return-to-home, low battery landing, etc.

    CONFIRMATION FLOW:
    =================
    A typical mission uses ConfirmationManager like this:

    1. Agent plans mission → calls set_mission_plan (no confirmation)
    2. Agent initiates takeoff → pre_flight_confirmation() displays plan
       → Operator reviews and approves → proceed to pre-arm
    3. Before arming → pre_arm_confirmation() shows telemetry
       → Operator verifies battery/GPS/position → approves arming
    4. During flight → if exception detected → exception_confirmation()
       → Operator decides: continue, pause, or abort
    5. If operator doesn't respond within timeout_s → timeout_confirmation()
       → Returns default safe action (usually "no")

    RESPONSE MECHANISM:
    ==================
    The manager supports multiple response mechanisms:

    1. Interactive (CLI): Operator types response at terminal
    2. Programmatic: External system calls submit_response()
    3. MCP Tool: Response injected via MCP tool call
    4. Web UI: Button clicks converted to responses
    5. Voice: Speech recognition converted to text responses

    All responses are validated against allowed options before acceptance.

    THREAD SAFETY:
    ==============
    This class uses asyncio for concurrency and is designed for
    single-operator use. The _input_queue ensures thread-safe response
    handling. For multi-operator scenarios, additional coordination
    would be needed.

    USAGE EXAMPLE:
    =============
        # Initialize manager with custom timeout
        config = ConfirmationConfig(timeout_s=15.0)
        manager = ConfirmationManager(config)

        # Create a mission plan
        plan = MissionPlan(
            waypoints=[
                {"lat": 37.7749, "lon": -122.4194, "alt": 50},
                {"lat": 37.7750, "lon": -122.4195, "alt": 50}
            ],
            estimated_duration_s=300,
            max_altitude_m=50,
            max_distance_m=100,
            description="Perimeter survey of building"
        )

        # Request pre-flight confirmation
        confirmed = await manager.pre_flight_confirmation(plan)

        if confirmed:
            print("Mission approved - proceeding to arming")
            # Get telemetry snapshot
            telemetry = TelemetrySnapshot(
                battery_percent=85.0,
                gps_fix=True,
                satellite_count=12,
                # ... other fields
            )

            # Request pre-arm confirmation
            can_arm = await manager.pre_arm_confirmation(telemetry)

            if can_arm:
                print("Arming approved - proceeding with takeoff")
                # Proceed to arm and takeoff via GuardianProcess
            else:
                print("Arming declined - mission aborted")
        else:
            print("Mission declined - not taking off")

        # During flight, handle exceptions
        response = await manager.exception_confirmation(
            ExceptionType.PERSON_DETECTED,
            context={"distance_m": 15, "confidence": 0.95}
        )

        if response == ConfirmationResponse.ABORT:
            await drone.action.return_to_launch()
        elif response == ConfirmationResponse.NO:
            await drone.action.hold()  # Hover in place
        elif response == ConfirmationResponse.YES:
            # Continue despite detection (acknowledge risk)
            pass
    """

    def __init__(self, config: Optional[ConfirmationConfig] = None):
        """Initialize the confirmation manager.

        Sets up the internal state for managing confirmations including
        the input queue for receiving responses and tracking pending
        confirmation state.

        Args:
            config: Configuration for confirmation behavior. Uses defaults
                if not provided. Can customize timeout, verbosity, and
                abort behavior.

        Example:
            # Default configuration
            manager = ConfirmationManager()

            # Custom configuration with 20 second timeout
            config = ConfirmationConfig(timeout_s=20.0)
            manager = ConfirmationManager(config)
        """
        self.config = config or ConfirmationConfig()
        self._pending_confirmation: Optional[asyncio.Event] = None
        self._confirmation_response: Optional[str] = None
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

        # D2.6: Token-based confirmation API
        # _pending stores pending confirmations keyed by token string
        # Each entry is a tuple of (asyncio.Event, dict) for response data
        self._pending: dict[str, PendingConfirmation] = {}
        self.default_ttl_s: float = 60.0  # Default TTL for confirmations
        self.auto_confirm: bool = False  # Auto-approve all confirmations

    async def pre_flight_confirmation(self, plan: MissionPlan) -> bool:
        """Request user confirmation before starting a mission.

        This is Level 1 confirmation in the progressive safety system.
        It displays the complete mission plan for operator review before
        any takeoff occurs.

        The operator reviews:
        - Mission description and purpose
        - Waypoint coordinates (lat/lon/alt)
        - Estimated duration (time airborne)
        - Maximum altitude (highest point in mission)
        - Maximum distance from home (radio range check)

        SAFETY PURPOSE:
        ===============
        This catches planning errors before the drone leaves the ground:
        - Wrong coordinates (flight to incorrect location)
        - Excessive altitude (violating regulations)
        - Excessive distance (beyond radio/visual range)
        - Wrong duration (insufficient battery)
        - Misunderstood mission (operator vs. agent misalignment)

        Args:
            plan: MissionPlan containing waypoints and mission details.
                Must include at least waypoints list. Other fields used
                for operator information but not strictly required.

        Returns:
            True if user confirmed the mission with "yes" response.
            False if user declined with "no" or "abort" response,
            or if timeout occurred (returns default "no").

        Example:
            plan = MissionPlan(
                waypoints=[{"lat": 37.7749, "lon": -122.4194, "alt": 50}],
                description="Roof inspection",
                estimated_duration_s=180,
                max_altitude_m=50,
                max_distance_m=75
            )

            confirmed = await manager.pre_flight_confirmation(plan)
            if confirmed:
                print("Approved - proceeding to pre-arm check")
            else:
                print("Declined - staying on ground")
        """
        logger.info("Requesting pre-flight confirmation...")

        # Build confirmation message
        message = self._format_pre_flight_message(plan)

        # Display and wait for response
        response = await self._request_confirmation(
            prompt=message,
            options=["yes", "no", "abort"],
            default_action="no",
        )

        confirmed = response == ConfirmationResponse.YES

        if confirmed:
            logger.info("Mission plan confirmed by user")
        else:
            logger.info(f"Mission plan rejected by user: {response}")

        return confirmed

    async def pre_arm_confirmation(self, telemetry: TelemetrySnapshot) -> bool:
        """Request user confirmation before arming the drone.

        This is Level 2 confirmation in the progressive safety system.
        It displays current drone telemetry for operator review before
        arming the motors (enabling potential flight).

        The operator reviews:
        - Current position (lat/lon/alt) - verify correct location
        - Battery percentage - must be sufficient for mission
        - GPS fix status - must be True for navigation
        - Satellite count - should be 6+ for accuracy
        - Flight mode - should be appropriate (HOLD)
        - Armed/In Air status - should be False before arming

        SAFETY PURPOSE:
        ===============
        This catches unsafe conditions before enabling flight:
        - Low battery (can't complete mission + reserve)
        - No GPS fix (can't navigate safely)
        - Poor satellite count (inaccurate position)
        - Wrong location (drone moved since planning)
        - Already armed (confusion about state)

        Automatic warnings are generated for:
        - Battery < 30%: "[WARNING] Low battery!"
        - No GPS fix: "[WARNING] No GPS fix!"
        - Satellites < 6: "[WARNING] Low satellite count!"

        Args:
            telemetry: TelemetrySnapshot with current drone state.
                Should be fetched immediately before confirmation for
                accurate status. All fields used for display/warnings.

        Returns:
            True if user confirmed with "yes" response.
            False if user declined with "no" or "abort" response,
            or if timeout occurred (returns default "no").

        Example:
            # Get current telemetry from drone
            telemetry = TelemetrySnapshot(
                position={"lat": 37.7749, "lon": -122.4194, "alt": 0},
                battery_percent=87.5,
                gps_fix=True,
                satellite_count=14,
                flight_mode="HOLD",
                armed=False,
                in_air=False
            )

            can_arm = await manager.pre_arm_confirmation(telemetry)
            if can_arm:
                print("Approved - arming motors via GuardianProcess")
                await guardian.arm()
            else:
                print("Declined - motors stay disarmed")
        """
        logger.info("Requesting pre-arm confirmation...")

        # Build confirmation message
        message = self._format_pre_arm_message(telemetry)

        # Display and wait for response
        response = await self._request_confirmation(
            prompt=message,
            options=["yes", "no", "abort"],
            default_action="no",
        )

        confirmed = response == ConfirmationResponse.YES

        if confirmed:
            logger.info("Pre-arm confirmation received")
        else:
            logger.info(f"Arm confirmation rejected: {response}")

        return confirmed

    async def exception_confirmation(
        self, exception_type: ExceptionType, context: Optional[dict[str, Any]] = None
    ) -> str:
        """Request user decision for an exception situation.

        This is Level 3 confirmation in the progressive safety system.
        It is triggered when the drone encounters an unexpected situation
        during flight that requires human judgment to proceed safely.

        Exception Types Handled:
        - PERSON_DETECTED: Vision system detected human in flight path
        - OBSTACLE_DETECTED: Sensors detected obstacle ahead
        - NO_FLY_ZONE: Approaching restricted airspace
        - LOW_BATTERY: Battery below safe operating threshold
        - WEATHER_WARNING: Environmental conditions deteriorating
        - GPS_DEGRADATION: Position accuracy falling below safe limits
        - CUSTOM: Any other unexpected situation

        SAFETY PURPOSE:
        ===============
        LLMs and automated systems may not handle edge cases correctly:
        - May not recognize safety implications of detections
        - May make wrong tradeoff decisions (risk vs. mission completion)
        - Cannot be held accountable for accidents

        Human operator judgment is required because:
        - Operator has full context of the mission and environment
        - Operator can assess if detection is false positive
        - Operator knows if area is actually restricted
        - Operator can weigh mission importance vs. safety risk

        Response Options:
        - YES: Continue mission despite the situation
          Use when: Detection is false positive, situation is manageable
          Risk: Proceeding despite potential hazard

        - NO: Pause and wait for further instruction
          Use when: Need more time to assess, want to investigate
          Action: Drone hovers in place (HOLD mode)
          Risk: Wasting battery while hovering

        - ABORT: Stop mission and return to launch
          Use when: Situation is dangerous, mission should not continue
          Action: Drone executes Return-to-Launch (RTL)
          Risk: Aborting valid mission, but safest option

        Args:
            exception_type: Type of exception encountered from
                ExceptionType enum. Determines the message shown.
            context: Optional additional context about the exception.
                May include distance, confidence, coordinates, etc.
                Displayed to operator for informed decision.

        Returns:
            User's choice as string: "yes" (continue), "no" (pause/wait),
            "abort" (stop mission), or "timeout" if no response.

        Example:
            # Vision system detected person nearby
            response = await manager.exception_confirmation(
                ExceptionType.PERSON_DETECTED,
                context={
                    "distance_m": 12.5,
                    "confidence": 0.94,
                    "direction": "north"
                }
            )

            if response == ConfirmationResponse.ABORT:
                print("Aborting - returning to launch")
                await drone.action.return_to_launch()
            elif response == ConfirmationResponse.NO:
                print("Pausing - hovering in place")
                await drone.action.hold()
            elif response == ConfirmationResponse.YES:
                print("Continuing - acknowledging person detected")
                # Continue mission
        """
        logger.warning(f"Exception detected: {exception_type.value}")

        # Build confirmation message
        message = self._format_exception_message(exception_type, context)

        # Display and wait for response
        response = await self._request_confirmation(
            prompt=message,
            options=["yes", "no", "abort"],
            default_action="no",  # Default to safe pause
        )

        logger.info(f"Exception response: {response}")

        return response

    async def timeout_confirmation(self, default_action: str) -> str:
        """Handle timeout waiting for user response.

        This is Level 4 confirmation handling. Called when the operator
        doesn't respond within the configured timeout window.

        SAFETY PURPOSE:
        ===============
        Without timeout handling, the system could wait indefinitely
        for operator input while:
        - Battery continues draining
        - Drone hovers in place (wasting power)
        - Drone continues into dangerous situation
        - Weather conditions deteriorate

        The timeout ensures the drone always takes SOME action rather
        than waiting forever. The default action is always the safest
        option for the specific confirmation type:

        - Pre-flight: "no" (stay on ground - safe)
        - Pre-arm: "no" (stay disarmed - safe)
        - Exception: "no" (pause/wait - safer than continuing)

        This is a "fail-safe" design - when in doubt, do the safe thing.

        Args:
            default_action: Default action to take on timeout.
                Should be the safest option for the specific context.
                Typically "no" or "abort".

        Returns:
            The default action string that was applied.

        Example:
            # If user doesn't respond in 10 seconds, default to "no"
            response = await manager._request_confirmation(
                prompt="Proceed?",
                options=["yes", "no", "abort"],
                default_action="no"  # Safe default
            )
            # If timeout, response will be "no"
        """
        logger.warning(
            f"Confirmation timeout - taking default action: {default_action}"
        )

        # Log the timeout event
        message = (
            f"\n{'='*50}\n"
            f"TIMEOUT: No response received within {self.config.timeout_s}s\n"
            f"Taking default action: {default_action}\n"
            f"{'='*50}\n"
        )
        print(message)

        return default_action

    async def _request_confirmation(
        self,
        prompt: str,
        options: list[str],
        default_action: str,
    ) -> str:
        """Request confirmation from user with timeout.

        Internal method that displays a prompt to the operator and waits
        for a response. If no response is received within the configured
        timeout, returns the default action.

        This is the core confirmation flow used by all confirmation types:
        1. Display formatted prompt to operator
        2. Wait for input via _get_user_input()
        3. Validate response against allowed options
        4. Return response or default on timeout

        TIMEOUT BEHAVIOR:
        =================
        If asyncio.wait_for() raises TimeoutError, we call
        timeout_confirmation() which logs the timeout and returns
        the default action. This ensures the system never hangs
        waiting for user input.

        Args:
            prompt: Message to display to user. Should include all
                relevant context for decision making. Formatted by
                the calling method (pre_flight, pre_arm, exception).
            options: Valid response options. Typically ["yes", "no", "abort"].
                User must provide one of these exact strings.
            default_action: Action to take on timeout. Must be one
                of the options. Typically "no" (safe default).

        Returns:
            User's validated response (one of options) or default_action
            if timeout occurred.

        Example:
            response = await self._request_confirmation(
                prompt="Mission: Survey. Duration: 120s. Altitude: 50m. Proceed?",
                options=["yes", "no", "abort"],
                default_action="no"
            )
        """
        # Display the prompt
        print(prompt)

        # Try to get response with timeout
        try:
            response = await asyncio.wait_for(
                self._get_user_input(options),
                timeout=self.config.timeout_s,
            )
            return response
        except asyncio.TimeoutError:
            return await self.timeout_confirmation(default_action)

    async def _get_user_input(self, valid_options: list[str]) -> str:
        """Get and validate user input.

        Internal method that waits for and validates user input.
        Uses an asyncio.Queue for thread-safe input handling.

        INPUT SOURCES:
        ==============
        In production, this can receive input from multiple sources:
        1. stdin: Operator typing at terminal
        2. MCP tool: Response from LLM agent via MCP tool call
        3. submit_response(): Programmatic injection via method call
        4. Web UI: Button clicks converted to queue items
        5. Voice: Speech-to-text converted to text responses

        The queue design allows asynchronous input without blocking.

        VALIDATION:
        ===========
        Input is validated against valid_options. Invalid input
        prints an error and loops for another attempt. This prevents
        typos from causing unintended actions.

        Args:
            valid_options: List of valid response strings.
                Input must match one exactly (case-insensitive).

        Returns:
            Validated user response (lowercase, in valid_options).

        Raises:
            asyncio.CancelledError: If input waiting is cancelled
                (e.g., mission abort signal).

        Example:
            response = await self._get_user_input(["yes", "no", "abort"])
            # Loops until user provides valid response
        """
        while True:
            # In a real implementation, this would read from stdin or
            # receive input via MCP tool call
            # For now, we simulate with queue-based input
            try:
                raw_input = await self._input_queue.get()
                response = raw_input.strip().lower()

                if response in valid_options:
                    return response
                else:
                    print(f"Invalid response. Options: {', '.join(valid_options)}")
            except asyncio.CancelledError:
                logger.info("Input waiting cancelled")
                raise

    def submit_response(self, response: str) -> None:
        """Submit a response programmatically.

        This method allows external systems (MCP tools, web UIs, etc.)
        to provide confirmation responses without interactive input.

        MCP INTEGRATION:
        ===============
        When an MCP tool needs confirmation, it can:
        1. Call this method with the operator's response
        2. The response is added to _input_queue
        3. _get_user_input() receives it from the queue
        4. Confirmation flow continues

        Example MCP tool handler:
            @mcp_server.tool()
            async def submit_confirmation(response: str) -> dict:
                manager.submit_response(response)
                return {"status": "response received"}

        This decouples the confirmation logic from the input mechanism.

        THREAD SAFETY:
        =============
        Uses put_nowait() which is thread-safe for asyncio.Queue.
        Safe to call from any context (async, sync, different threads).

        Args:
            response: User's response string. Should be one of the
                valid options ("yes", "no", "abort"). Will be
                validated by _get_user_input().

        Example:
            # Web UI button click handler
            def on_approve_clicked():
                manager.submit_response("yes")

            # MCP tool call
            @mcp_server.tool()
            async def confirm(response: str):
                manager.submit_response(response)
        """
        logger.debug(f"Submitting response: {response}")
        self._input_queue.put_nowait(response)

    # =========================================================================
    # D2.6: TOKEN-BASED CONFIRMATION API
    # =========================================================================
    # These methods provide a programmatic confirmation flow that supports
    # external confirmation mechanisms (CLI, web UI, API, MCP tools).
    #
    # Flow:
    # 1. Tool calls require() -> returns ConfirmationToken
    # 2. Tool displays summary to operator or waits
    # 3. External system calls submit() with token and approval
    # 4. require() returns with approval status
    #
    # This decouples the confirmation request from the confirmation response,
    # enabling multi-process and distributed confirmation workflows.

    async def require(
        self,
        *,
        action: str,
        destructive: bool,
        summary: str,
        payload: dict,
        ttl_s: Optional[float] = None,
    ) -> ConfirmationToken:
        """Request confirmation for an action.

        Creates a confirmation request and waits for a response via submit().
        If auto_confirm is True, immediately returns an approved token without
        waiting.

        This is the main entry point for the token-based confirmation API.
        It supports:
        - Destructive action flagging (for UI highlighting)
        - Human-readable summaries
        - Additional context via payload
        - Configurable time-to-live (TTL)

        Args:
            action: Human-readable action name (e.g., "arm_and_takeoff").
            destructive: Whether this action is destructive/irreversible.
                Used by UI to highlight risk (e.g., red button for disarm).
            summary: Human-readable summary for display to operator.
                Should clearly state what will happen if approved.
            payload: Additional context data (e.g., {"altitude_m": 15.0}).
                Can be used for detailed UI display or logging.
            ttl_s: Time-to-live in seconds. If no response within TTL,
                the confirmation times out. Defaults to default_ttl_s (60s).

        Returns:
            ConfirmationToken containing the unique token ID and action name.
            If auto_confirm is True, returns token with "__auto__" value.

        Raises:
            asyncio.TimeoutError: If TTL expires without response.
            asyncio.CancelledError: If the confirmation is cancelled.

        Example:
            >>> token = await manager.require(
            ...     action="set_parameter",
            ...     destructive=True,
            ...     summary="Set NAV_DLL_ACT to 0 (disable datalink loss action)",
            ...     payload={"parameter": "NAV_DLL_ACT", "value": 0}
            ... )
            >>> # Wait for external submit() call...
            >>> # After submit(), this await completes
        """
        # Auto-confirm mode: skip confirmation entirely
        if self.auto_confirm:
            logger.info(f"Auto-confirming action: {action}")
            return ConfirmationToken(token="__auto__", action=action)

        # Generate unique token
        token_str = secrets.token_urlsafe(32)

        # Create pending confirmation entry
        event = asyncio.Event()
        pending = PendingConfirmation(
            event=event,
            action=action,
            summary=summary,
            payload=payload,
            destructive=destructive,
        )
        self._pending[token_str] = pending

        # Log the confirmation request
        logger.info(f"Confirmation required: {action}")
        logger.debug(f"  Token: {token_str}")
        logger.debug(f"  Destructive: {destructive}")
        logger.debug(f"  Summary: {summary}")

        # Wait for response with TTL
        ttl = ttl_s if ttl_s is not None else self.default_ttl_s
        try:
            await asyncio.wait_for(event.wait(), timeout=ttl)

            # Check response
            if pending.response is None:
                # Should not happen, but handle gracefully
                logger.error(f"Confirmation response missing for token {token_str}")
                return ConfirmationToken(token=token_str, action=action)

            # Response received - return token
            # The caller should check pending.response for approval status
            return ConfirmationToken(token=token_str, action=action)

        except asyncio.TimeoutError:
            # Remove from pending on timeout
            self._pending.pop(token_str, None)
            logger.warning(f"Confirmation timed out: {action} (TTL: {ttl}s)")
            raise

        except asyncio.CancelledError:
            # Remove from pending on cancellation
            self._pending.pop(token_str, None)
            logger.info(f"Confirmation cancelled: {action}")
            raise

    async def submit(
        self,
        token: str,
        approved: bool,
        note: Optional[str] = None,
    ) -> None:
        """Submit a response to a pending confirmation.

        This is called by external systems (CLI, web UI, MCP tool) to
        provide the operator's decision on a confirmation request.

        The token must match an active confirmation request. If the token
        is not found (already responded to, timed out, or invalid), this
        method logs a warning and returns without error.

        Args:
            token: The token string from ConfirmationToken.
            approved: True if operator approved, False if rejected.
            note: Optional note from operator (e.g., reason for rejection).

        Raises:
            Nothing. Invalid tokens are logged but don't raise.

        Example:
            >>> # From CLI:
            >>> await manager.submit("abc123...", approved=True, note="Operator approved")
            >>> # From MCP tool:
            >>> await manager.submit(token_str, approved=False, note="Battery too low")
        """
        # Handle auto-confirm token (no-op, already approved)
        if token == "__auto__":
            logger.debug("Ignoring submit for auto-confirm token")
            return

        # Find pending confirmation
        pending = self._pending.get(token)
        if pending is None:
            logger.warning(f"Submit called with unknown/expired token: {token[:16]}...")
            return

        # Store response
        pending.response = {
            "approved": approved,
            "note": note,
            "timestamp": time.time(),
        }

        # Signal that response is ready
        pending.event.set()

        # Log the response
        status = "APPROVED" if approved else "REJECTED"
        logger.info(f"Confirmation {status}: {pending.action}")
        if note:
            logger.debug(f"  Note: {note}")

    def get_pending(self, token: str) -> Optional[dict]:
        """Get the response for a pending confirmation.

        After require() returns, this method can be used to retrieve
        the approval status and any notes from the operator.

        Args:
            token: The token string from ConfirmationToken.

        Returns:
            Dict with "approved" and "note" keys, or None if not found.
            For auto-confirm tokens, returns {"approved": True, "note": "auto"}.

        Example:
            >>> token = await manager.require(...)
            >>> # After submit() is called...
            >>> response = manager.get_pending(token.token)
            >>> if response and response["approved"]:
            ...     # Proceed with action
        """
        if token == "__auto__":
            return {"approved": True, "note": "auto"}

        pending = self._pending.get(token)
        if pending is None:
            return None

        return pending.response

    def clear_pending(self, token: str) -> bool:
        """Clear a pending confirmation.

        Removes a pending confirmation from the tracking dict. This should
        be called after the confirmation flow is complete to clean up.

        Args:
            token: The token string from ConfirmationToken.

        Returns:
            True if the token was found and removed, False otherwise.

        Example:
            >>> token = await manager.require(...)
            >>> response = manager.get_pending(token.token)
            >>> # Process response...
            >>> manager.clear_pending(token.token)
        """
        if token == "__auto__":
            return True

        if token in self._pending:
            del self._pending[token]
            return True
        return False

    def _format_pre_flight_message(self, plan: MissionPlan) -> str:
        """Format mission plan for display.

        Creates a human-readable formatted string showing all mission
        details for operator review before takeoff.

        DISPLAY FORMAT:
        ==============
        Shows clear headers, mission summary, waypoint list with
        coordinates, and action prompt. Uses visual separators (=)
        to make important sections stand out.

        WAYPOINT FORMAT:
        ================
        Waypoints displayed as:
          1. (latitude, longitude) @ altitude m
          2. (latitude, longitude) @ altitude m
        etc.

        Handles both naming conventions:
        - lat/lon/alt (common abbreviations)
        - latitude/longitude/altitude (full names)

        Args:
            plan: MissionPlan to format.

        Returns:
            Formatted string ready for display via print().
        """
        lines = [
            "\n" + "=" * 60,
            "PRE-FLIGHT CONFIRMATION",
            "=" * 60,
            "",
            f"Mission: {plan.description}",
            f"Duration: {plan.estimated_duration_s:.0f} seconds",
            f"Max Altitude: {plan.max_altitude_m:.1f} m",
            f"Max Distance: {plan.max_distance_m:.1f} m from home",
            "",
            "Waypoints:",
        ]

        for i, wp in enumerate(plan.waypoints, 1):
            lat = wp.get("lat", wp.get("latitude", 0))
            lon = wp.get("lon", wp.get("longitude", 0))
            alt = wp.get("alt", wp.get("altitude", 0))
            lines.append(f"  {i}. ({lat:.6f}, {lon:.6f}) @ {alt:.1f}m")

        lines.extend(
            [
                "",
                "-" * 60,
                "Confirm mission start? (yes/no/abort)",
                "-" * 60,
            ]
        )

        return "\n".join(lines)

    def _format_pre_arm_message(self, telemetry: TelemetrySnapshot) -> str:
        """Format telemetry for pre-arm confirmation.

        Creates a human-readable formatted string showing current
        drone state for operator review before arming.

        DISPLAY FORMAT:
        ==============
        Shows clear headers, position info, system status, and
        any warnings about concerning states.

        WARNING GENERATION:
        ==================
        Automatically generates warnings for:
        - Battery < 30%: Low battery warning
        - No GPS fix: Navigation safety warning
        - < 6 satellites: GPS accuracy warning

        These warnings help operators catch unsafe conditions.

        POSITION FORMAT:
        ================
        Position displayed as:
          Latitude: value
          Longitude: value
          Altitude: value m

        Handles both naming conventions:
        - lat/lon/alt
        - latitude_deg/longitude_deg/relative_altitude_m

        Args:
            telemetry: TelemetrySnapshot to format.

        Returns:
            Formatted string ready for display via print().
        """
        lines = [
            "\n" + "=" * 60,
            "PRE-ARM CONFIRMATION",
            "=" * 60,
            "",
        ]

        # Position info
        if telemetry.position:
            pos = telemetry.position
            lat = pos.get("lat", pos.get("latitude_deg", 0))
            lon = pos.get("lon", pos.get("longitude_deg", 0))
            alt = pos.get("alt", pos.get("relative_altitude_m", 0))
            lines.extend(
                [
                    "Position:",
                    f"  Latitude: {lat:.6f}",
                    f"  Longitude: {lon:.6f}",
                    f"  Altitude: {alt:.1f} m",
                    "",
                ]
            )

        # System status
        lines.extend(
            [
                "System Status:",
                f"  Battery: {telemetry.battery_percent:.1f}%",
                f"  GPS Fix: {'YES' if telemetry.gps_fix else 'NO'}",
                f"  Satellites: {telemetry.satellite_count}",
                f"  Flight Mode: {telemetry.flight_mode}",
                f"  Armed: {'YES' if telemetry.armed else 'NO'}",
                f"  In Air: {'YES' if telemetry.in_air else 'NO'}",
                "",
            ]
        )

        # Warnings for concerning states
        warnings = []
        if telemetry.battery_percent < 30:
            warnings.append("  [WARNING] Low battery!")
        if not telemetry.gps_fix:
            warnings.append("  [WARNING] No GPS fix!")
        if telemetry.satellite_count < 6:
            warnings.append("  [WARNING] Low satellite count!")

        if warnings:
            lines.extend(["Warnings:"] + warnings + [""])

        lines.extend(
            [
                "-" * 60,
                "Proceed with arming? (yes/no/abort)",
                "-" * 60,
            ]
        )

        return "\n".join(lines)

    def _format_exception_message(
        self,
        exception_type: ExceptionType,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """Format exception for confirmation display.

        Creates a human-readable formatted string explaining an
        exception situation and asking for operator decision.

        DISPLAY FORMAT:
        ==============
        Uses attention-grabbing separators (!) to highlight urgency.
        Shows exception type, human-readable description, and
        context details. Provides clear explanation of each option.

        EXCEPTION DESCRIPTIONS:
        ======================
        Maps ExceptionType to human-readable explanations:
        - PERSON_DETECTED: "Person detected in flight path"
        - OBSTACLE_DETECTED: "Obstacle detected ahead"
        - NO_FLY_ZONE: "Approaching no-fly zone boundary"
        - LOW_BATTERY: "Battery level critically low"
        - WEATHER_WARNING: "Adverse weather conditions detected"
        - GPS_DEGRADATION: "GPS signal quality degrading"
        - CUSTOM: "Unexpected situation detected"

        RESPONSE EXPLANATIONS:
        =====================
        Each option is explained so operator understands consequences:
        - yes: Continue mission (acknowledge risk)
        - no: Pause and wait for further instruction
        - abort: Abort mission and RTL (Return to Launch)

        Args:
            exception_type: Type of exception from ExceptionType enum.
            context: Additional context dict. May include distance,
                confidence, coordinates, etc. Displayed as key: value.

        Returns:
            Formatted string ready for display via print().
        """
        # Exception descriptions
        descriptions = {
            ExceptionType.PERSON_DETECTED: "Person detected in flight path",
            ExceptionType.OBSTACLE_DETECTED: "Obstacle detected ahead",
            ExceptionType.NO_FLY_ZONE: "Approaching no-fly zone boundary",
            ExceptionType.LOW_BATTERY: "Battery level critically low",
            ExceptionType.WEATHER_WARNING: "Adverse weather conditions detected",
            ExceptionType.GPS_DEGRADATION: "GPS signal quality degrading",
            ExceptionType.CUSTOM: "Unexpected situation detected",
        }

        lines = [
            "\n" + "!" * 60,
            "EXCEPTION CONFIRMATION",
            "!" * 60,
            "",
            f"Type: {exception_type.value}",
            f"Description: {descriptions.get(exception_type, 'Unknown exception')}",
            "",
        ]

        # Add context if provided
        if context:
            lines.append("Details:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        lines.extend(
            [
                "-" * 60,
                "How would you like to proceed?",
                "  yes   - Continue mission (acknowledge risk)",
                "  no    - Pause and wait for further instruction",
                "  abort - Abort mission and RTL",
                "-" * 60,
            ]
        )

        return "\n".join(lines)
