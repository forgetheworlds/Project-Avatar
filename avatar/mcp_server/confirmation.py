"""
Confirmation workflow for human-in-the-loop drone operations.

Provides confirmation dialogs for critical flight operations requiring human approval.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfirmationResponse(str, Enum):
    """Possible responses from confirmation dialogs."""

    YES = "yes"
    NO = "no"
    ABORT = "abort"
    TIMEOUT = "timeout"


class ExceptionType(str, Enum):
    """Types of exceptions that may require confirmation."""

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

    Attributes:
        waypoints: List of waypoint dictionaries with lat/lon/alt.
        estimated_duration_s: Estimated mission duration in seconds.
        max_altitude_m: Maximum planned altitude in meters.
        max_distance_m: Maximum planned distance from home in meters.
        description: Human-readable mission description.
    """

    waypoints: list[dict[str, float]] = field(default_factory=list)
    estimated_duration_s: float = 0.0
    max_altitude_m: float = 0.0
    max_distance_m: float = 0.0
    description: str = ""


@dataclass
class TelemetrySnapshot:
    """Snapshot of drone telemetry for pre-arm confirmation.

    Attributes:
        position: Current position (lat, lon, alt).
        battery_percent: Battery level percentage.
        gps_fix: Whether GPS has a valid fix.
        satellite_count: Number of GPS satellites.
        flight_mode: Current flight mode.
        armed: Whether the drone is armed.
        in_air: Whether the drone is in the air.
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

    Attributes:
        timeout_s: Seconds to wait for user response before timeout.
        show_telemetry_details: Whether to show full telemetry in confirmations.
        require_explicit_abort: If True, 'no' counts as abort. If False, 'no' allows retry.
    """

    timeout_s: float = 10.0
    show_telemetry_details: bool = True
    require_explicit_abort: bool = False


class ConfirmationManager:
    """
    Manages human-in-the-loop confirmation for critical drone operations.

    This class provides confirmation dialogs for operations that require
    explicit human approval before proceeding:

    - Pre-flight: Review mission plan before takeoff
    - Pre-arm: Verify drone state before arming
    - Exception: Handle unexpected situations (person detected, etc.)
    - Timeout: Default action when no response received

    Usage:
        manager = ConfirmationManager()

        # Pre-flight confirmation
        plan = MissionPlan(
            waypoints=[{"lat": 37.7749, "lon": -122.4194, "alt": 50}],
            estimated_duration_s=120,
            max_altitude_m=50,
            max_distance_m=200,
            description="Survey mission Alpha"
        )
        confirmed = await manager.pre_flight_confirmation(plan)

        # Exception handling
        response = await manager.exception_confirmation(ExceptionType.PERSON_DETECTED)
        if response == ConfirmationResponse.ABORT:
            await abort_mission()
    """

    def __init__(self, config: Optional[ConfirmationConfig] = None):
        """Initialize the confirmation manager.

        Args:
            config: Configuration for confirmation behavior. Uses defaults if not provided.
        """
        self.config = config or ConfirmationConfig()
        self._pending_confirmation: Optional[asyncio.Event] = None
        self._confirmation_response: Optional[str] = None
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

    async def pre_flight_confirmation(self, plan: MissionPlan) -> bool:
        """Request user confirmation before starting a mission.

        Displays the mission plan details and asks for confirmation.
        User can approve (yes), decline with retry option (no), or abort.

        Args:
            plan: MissionPlan containing waypoints and mission details.

        Returns:
            True if user confirmed the mission, False otherwise.
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

        Shows current drone state (battery, GPS, position) and asks
        for confirmation to proceed with arming.

        Args:
            telemetry: TelemetrySnapshot with current drone state.

        Returns:
            True if user confirmed to arm, False otherwise.
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

        Used when the drone encounters an unexpected situation that
        requires human judgment to proceed safely.

        Args:
            exception_type: Type of exception encountered.
            context: Optional additional context about the exception.

        Returns:
            User's choice: "yes" (continue), "no" (pause/wait), or "abort" (stop mission).
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

        Called when no response is received within the configured timeout.
        Returns the configured default action.

        Args:
            default_action: Default action to take on timeout.

        Returns:
            The default action string.
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

        Displays the prompt and waits for user input. If no response
        within timeout, returns the default action.

        Args:
            prompt: Message to display to user.
            options: Valid response options.
            default_action: Action to take on timeout.

        Returns:
            User's response or default action on timeout.
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

        Prompts for input and validates against allowed options.
        Loops until valid input received.

        Args:
            valid_options: List of valid response strings.

        Returns:
            Validated user response.
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

        Used by MCP tools or other systems to provide responses
        without interactive input.

        Args:
            response: User's response string.
        """
        logger.debug(f"Submitting response: {response}")
        self._input_queue.put_nowait(response)

    def _format_pre_flight_message(self, plan: MissionPlan) -> str:
        """Format mission plan for display.

        Args:
            plan: MissionPlan to format.

        Returns:
            Formatted string for display.
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

        Args:
            telemetry: TelemetrySnapshot to format.

        Returns:
            Formatted string for display.
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

        Args:
            exception_type: Type of exception.
            context: Additional context about the exception.

        Returns:
            Formatted string for display.
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
