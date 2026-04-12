"""Async Guardian Architecture for 20Hz Safety Operations.

This module provides a fully async safety monitoring system with concurrent
tasks for heartbeat emission, resource monitoring, state consistency checks,
and VIO sanity monitoring. Maintains <50ms precision at 20Hz operational loop.

Key features:
- 20Hz heartbeat emission with <50ms precision
- 500ms offboard timeout detection
- Concurrent monitoring tasks (health, resources, state, VIO)
- Automatic failsafe triggers (RTL, Land, Hold)
- Integration with HeartbeatService and StateMachine

Example:
    guardian = AsyncGuardian(
        connection_manager=cm,
        heartbeat_service=hb,
        state_machine=sm
    )
    await guardian.start()

    # Guardian runs all monitoring concurrently
    await asyncio.sleep(10)  # Run for 10 seconds

    await guardian.stop()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatSource
from avatar.mav.state_machine import FlightState, FlightStateMachine

logger = logging.getLogger(__name__)


class MonitorType(Enum):
    """Types of monitoring tasks."""

    HEARTBEAT = "heartbeat"
    STATE_CONSISTENCY = "state_consistency"
    RESOURCE = "resource"
    VIO_SANITY = "vio_sanity"
    NETWORK = "network"


class SafetyAction(Enum):
    """Available safety actions."""

    RTL = "return_to_launch"
    LAND = "land"
    HOLD = "hold"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class GuardianConfig:
    """Configuration for AsyncGuardian.

    Attributes:
        heartbeat_interval_s: Interval between heartbeats (default: 0.05 = 20Hz)
        offboard_timeout_s: Time before offboard timeout (default: 0.5s)
        resource_check_interval_s: Resource monitoring interval (default: 1.0s)
        state_check_interval_s: State consistency check interval (default: 0.1s)
        vio_check_interval_s: VIO sanity check interval (default: 0.2s)
        network_check_interval_s: Network connectivity check interval (default: 1.0s)
        max_cpu_percent: Maximum CPU usage before warning (default: 80%)
        max_temp_celsius: Maximum temperature before warning (default: 75C)
        max_memory_percent: Maximum memory usage before warning (default: 85%)
        enable_heartbeat_emit: Whether to emit heartbeats (default: True)
        enable_resource_monitor: Whether to monitor resources (default: True)
        enable_state_monitor: Whether to monitor state consistency (default: True)
        enable_vio_monitor: Whether to monitor VIO (default: True)
        enable_network_monitor: Whether to monitor network (default: True)
        auto_failsafe: Whether to auto-trigger failsafe on critical issues (default: True)
    """

    heartbeat_interval_s: float = 0.05  # 20Hz
    offboard_timeout_s: float = 0.5
    resource_check_interval_s: float = 1.0
    state_check_interval_s: float = 0.1
    vio_check_interval_s: float = 0.2
    network_check_interval_s: float = 1.0
    max_cpu_percent: float = 80.0
    max_temp_celsius: float = 75.0
    max_memory_percent: float = 85.0
    enable_heartbeat_emit: bool = True
    enable_resource_monitor: bool = True
    enable_state_monitor: bool = True
    enable_vio_monitor: bool = True
    enable_network_monitor: bool = True
    auto_failsafe: bool = True


@dataclass
class ResourceMetrics:
    """Resource usage metrics.

    Attributes:
        cpu_percent: CPU usage percentage
        memory_percent: Memory usage percentage
        temperature_celsius: System temperature in celsius
        timestamp: Unix timestamp of measurement
    """

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    temperature_celsius: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class VIOMetrics:
    """VIO (Visual-Inertial Odometry) metrics.

    Attributes:
        position_variance: Position estimate variance
        velocity_variance: Velocity estimate variance
        tracking_quality: Tracking quality score (0-1)
        is_valid: Whether VIO data is valid
        timestamp: Unix timestamp of measurement
    """

    position_variance: float = 0.0
    velocity_variance: float = 0.0
    tracking_quality: float = 1.0
    is_valid: bool = True
    timestamp: float = field(default_factory=time.time)


@dataclass
class Alert:
    """Safety alert record.

    Attributes:
        level: Alert level (warning, critical)
        source: Source of the alert (monitor type)
        message: Human-readable alert message
        timestamp: Unix timestamp of alert
        action_taken: Safety action taken (if any)
    """

    level: str
    source: str
    message: str
    timestamp: float = field(default_factory=time.time)
    action_taken: Optional[str] = None


@dataclass
class GuardianStatus:
    """Current status of the AsyncGuardian.

    Attributes:
        is_running: Whether guardian is running
        active_monitors: List of active monitor task names
        last_heartbeat: Timestamp of last heartbeat emission
        alerts: List of recent alerts
        resource_metrics: Latest resource metrics
        vio_metrics: Latest VIO metrics
        missed_heartbeats: Number of missed heartbeat deadlines
        heartbeat_count: Total number of heartbeats emitted
        uptime_s: Guardian uptime in seconds
    """

    is_running: bool = False
    active_monitors: List[str] = field(default_factory=list)
    last_heartbeat: float = 0.0
    alerts: List[Alert] = field(default_factory=list)
    resource_metrics: ResourceMetrics = field(default_factory=ResourceMetrics)
    vio_metrics: VIOMetrics = field(default_factory=VIOMetrics)
    missed_heartbeats: int = 0
    heartbeat_count: int = 0
    uptime_s: float = 0.0


class AsyncGuardian:
    """Async Guardian process with concurrent safety monitoring.

    Monitors:
    - 20Hz heartbeat emission (50ms precision)
    - Offboard timeout (500ms)
    - Resource usage (CPU, temperature, memory)
    - State consistency with PX4
    - VIO sanity checks
    - Network connectivity

    Usage:
        guardian = AsyncGuardian(
            connection_manager=cm,
            heartbeat_service=hb,
            state_machine=sm
        )
        await guardian.start()
        # ... operations ...
        await guardian.stop()
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        heartbeat_service: HeartbeatService,
        state_machine: FlightStateMachine,
        config: Optional[GuardianConfig] = None,
    ) -> None:
        """Initialize the AsyncGuardian.

        Args:
            connection_manager: ConnectionManager instance for drone access
            heartbeat_service: HeartbeatService instance for heartbeat tracking
            state_machine: FlightStateMachine instance for state management
            config: Guardian configuration. Uses defaults if not provided.
        """
        self.cm = connection_manager
        self.hb = heartbeat_service
        self.sm = state_machine
        self.config = config or GuardianConfig()

        # Task management
        self._tasks: Dict[MonitorType, asyncio.Task[Any]] = {}
        self._running = False
        self._stop_event = asyncio.Event()

        # Timing and metrics
        self._start_time: float = 0.0
        self._last_heartbeat_time: float = 0.0
        self._missed_heartbeats = 0
        self._heartbeat_count = 0

        # State tracking
        self._alerts: List[Alert] = []
        self._max_alerts = 100
        self._alerts_lock = asyncio.Lock()

        # Resource tracking
        self._resource_metrics = ResourceMetrics()
        self._resource_lock = asyncio.Lock()

        # VIO tracking
        self._vio_metrics = VIOMetrics()
        self._vio_lock = asyncio.Lock()

        # Network tracking
        self._last_ping_time: float = 0.0
        self._network_healthy = True

        # Telemetry state cache
        self._last_telemetry_state: Optional[FlightState] = None
        self._last_telemetry_time: float = 0.0

        # Failsafe callbacks
        self.on_failsafe: Optional[Callable[[SafetyAction, str], Coroutine[Any, Any, None]]] = None

    @property
    def is_running(self) -> bool:
        """Whether the guardian is currently running."""
        return self._running

    async def start(self) -> None:
        """Start the guardian and all monitoring tasks.

        This method is idempotent - calling it multiple times when already
        running will not create duplicate tasks.
        """
        if self._running:
            logger.debug("AsyncGuardian already running")
            return

        self._stop_event.clear()
        self._start_time = time.time()
        self._running = True

        # Register with heartbeat service
        if self.hb.is_running:
            self.hb.on_failsafe = self._on_heartbeat_failsafe

        # Start monitor tasks
        await self._start_monitors()

        logger.info("AsyncGuardian started with 20Hz safety monitoring")

    async def stop(self) -> None:
        """Stop the guardian and cleanup all tasks.

        This method is idempotent - calling it multiple times is safe.
        """
        if not self._running:
            logger.debug("AsyncGuardian already stopped")
            return

        # Signal stop
        self._stop_event.set()
        self._running = False

        # Cancel all tasks
        await self._stop_monitors()

        # Unregister from heartbeat service
        if self.hb.is_running and self.hb.on_failsafe == self._on_heartbeat_failsafe:
            self.hb.on_failsafe = None

        uptime = time.time() - self._start_time
        logger.info(f"AsyncGuardian stopped (uptime: {uptime:.1f}s)")

    async def _start_monitors(self) -> None:
        """Start all configured monitoring tasks."""
        tasks_to_start = []

        if self.config.enable_heartbeat_emit:
            task = asyncio.create_task(self._heartbeat_emitter())
            self._tasks[MonitorType.HEARTBEAT] = task
            tasks_to_start.append("heartbeat")

        if self.config.enable_state_monitor:
            task = asyncio.create_task(self._state_consistency_monitor())
            self._tasks[MonitorType.STATE_CONSISTENCY] = task
            tasks_to_start.append("state_consistency")

        if self.config.enable_resource_monitor:
            task = asyncio.create_task(self._resource_monitor())
            self._tasks[MonitorType.RESOURCE] = task
            tasks_to_start.append("resource")

        if self.config.enable_vio_monitor:
            task = asyncio.create_task(self._vio_sanity_monitor())
            self._tasks[MonitorType.VIO_SANITY] = task
            tasks_to_start.append("vio_sanity")

        if self.config.enable_network_monitor:
            task = asyncio.create_task(self._network_monitor())
            self._tasks[MonitorType.NETWORK] = task
            tasks_to_start.append("network")

        logger.debug(f"Started monitors: {tasks_to_start}")

    async def _stop_monitors(self) -> None:
        """Stop all monitoring tasks."""
        # Cancel all tasks
        for monitor_type, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.debug(f"Stopped {monitor_type.value} monitor")

        self._tasks.clear()

    async def _heartbeat_emitter(self) -> None:
        """Emit heartbeats at 20Hz (50ms intervals).

        This task maintains precise 50ms intervals using asyncio.sleep()
        with drift correction.
        """
        logger.debug("Heartbeat emitter started (20Hz)")

        next_emit_time = time.time()
        interval = self.config.heartbeat_interval_s

        while not self._stop_event.is_set():
            try:
                # Record emission
                emit_time = time.time()
                self._last_heartbeat_time = emit_time
                self._heartbeat_count += 1

                # Record heartbeat with heartbeat service
                if self.hb.is_running:
                    self.hb.record_heartbeat(HeartbeatSource.GUARDIAN, emit_time)

                # Calculate next emission time with drift correction
                next_emit_time += interval
                sleep_time = next_emit_time - time.time()

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    # Behind schedule - log warning and count missed deadline
                    lag = -sleep_time
                    self._missed_heartbeats += 1
                    logger.warning(f"Heartbeat deadline missed by {lag*1000:.1f}ms")

                    # Don't accumulate too much lag
                    if lag > interval:
                        next_emit_time = time.time() + interval

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat emitter error: {e}")
                await asyncio.sleep(interval)

        logger.debug("Heartbeat emitter stopped")

    async def _state_consistency_monitor(self) -> None:
        """Monitor state consistency between telemetry and state machine.

        Checks at 10Hz that the state machine matches the actual telemetry.
        Triggers alerts on state mismatch.
        """
        logger.debug("State consistency monitor started (10Hz)")

        interval = self.config.state_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Get current telemetry state
                telemetry_state = await self._get_telemetry_state()

                if telemetry_state is not None:
                    sm_state = self.sm.current_state

                    # Check for mismatch
                    if telemetry_state != sm_state:
                        # Some states are equivalent (e.g., FLYING and POSITION_CONTROL)
                        if not self._states_equivalent(telemetry_state, sm_state):
                            await self._add_alert(
                                "warning",
                                MonitorType.STATE_CONSISTENCY.value,
                                f"State mismatch: telemetry={telemetry_state.name}, "
                                f"state_machine={sm_state.name}",
                            )

                            # Sync state machine from telemetry
                            self._sync_state_from_telemetry(telemetry_state)

                # Check offboard timeout
                if self.hb.is_running:
                    last_hb = self.hb.get_last_heartbeat(HeartbeatSource.OFFBOARD)
                    offboard_age = time.time() - last_hb if last_hb is not None else float('inf')

                    if offboard_age > self.config.offboard_timeout_s:
                        await self._add_alert(
                            "critical",
                            MonitorType.STATE_CONSISTENCY.value,
                            f"Offboard timeout: {offboard_age:.2f}s > {self.config.offboard_timeout_s}s",
                        )

                        if self.config.auto_failsafe:
                            await self.initiate_hold("offboard_timeout")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"State consistency monitor error: {e}")

        logger.debug("State consistency monitor stopped")

    async def _resource_monitor(self) -> None:
        """Monitor system resources (CPU, temperature, memory).

        Checks at 1Hz for resource issues that could affect safety.
        """
        logger.debug("Resource monitor started (1Hz)")

        interval = self.config.resource_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Get resource metrics
                metrics = await self._get_resource_metrics()

                async with self._resource_lock:
                    self._resource_metrics = metrics

                # Check CPU
                if metrics.cpu_percent > self.config.max_cpu_percent:
                    await self._add_alert(
                        "warning",
                        MonitorType.RESOURCE.value,
                        f"High CPU usage: {metrics.cpu_percent:.1f}%",
                    )

                # Check memory
                if metrics.memory_percent > self.config.max_memory_percent:
                    await self._add_alert(
                        "warning",
                        MonitorType.RESOURCE.value,
                        f"High memory usage: {metrics.memory_percent:.1f}%",
                    )

                # Check temperature
                if metrics.temperature_celsius > self.config.max_temp_celsius:
                    await self._add_alert(
                        "critical",
                        MonitorType.RESOURCE.value,
                        f"High temperature: {metrics.temperature_celsius:.1f}C",
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Resource monitor error: {e}")

        logger.debug("Resource monitor stopped")

    async def _vio_sanity_monitor(self) -> None:
        """Monitor VIO (Visual-Inertial Odometry) sanity.

        Checks at 5Hz for VIO quality degradation.
        """
        logger.debug("VIO sanity monitor started (5Hz)")

        interval = self.config.vio_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Get VIO metrics
                metrics = await self._get_vio_metrics()

                async with self._vio_lock:
                    self._vio_metrics = metrics

                # Check VIO validity
                if not metrics.is_valid:
                    await self._add_alert(
                        "critical",
                        MonitorType.VIO_SANITY.value,
                        "VIO data invalid - position estimate unreliable",
                    )

                    if self.config.auto_failsafe and self.sm.is_flying:
                        await self.initiate_hold("vio_invalid")

                # Check position variance
                elif metrics.position_variance > 1.0:  # 1 meter variance threshold
                    await self._add_alert(
                        "warning",
                        MonitorType.VIO_SANITY.value,
                        f"High position variance: {metrics.position_variance:.2f}m",
                    )

                # Check tracking quality
                elif metrics.tracking_quality < 0.5:
                    await self._add_alert(
                        "warning",
                        MonitorType.VIO_SANITY.value,
                        f"Low VIO tracking quality: {metrics.tracking_quality:.2f}",
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"VIO sanity monitor error: {e}")

        logger.debug("VIO sanity monitor stopped")

    async def _network_monitor(self) -> None:
        """Monitor network connectivity to drone.

        Checks at 1Hz for network issues.
        """
        logger.debug("Network monitor started (1Hz)")

        interval = self.config.network_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Check connection health
                if not self.cm.health.is_healthy:
                    await self._add_alert(
                        "critical",
                        MonitorType.NETWORK.value,
                        "Connection to drone unhealthy",
                    )

                    if self.config.auto_failsafe and self.sm.is_flying:
                        await self.initiate_rtl("connection_unhealthy")

                # Check for stale telemetry
                last_heartbeat_age = time.time() - self.cm.health.last_heartbeat
                if last_heartbeat_age > 2.0:  # No telemetry for 2 seconds
                    await self._add_alert(
                        "critical",
                        MonitorType.NETWORK.value,
                        f"Stale telemetry: {last_heartbeat_age:.1f}s since last heartbeat",
                    )

                    if self.config.auto_failsafe and self.sm.is_flying:
                        await self.initiate_rtl("telemetry_stale")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Network monitor error: {e}")

        logger.debug("Network monitor stopped")

    async def initiate_rtl(self, reason: str) -> bool:
        """Initiate Return-To-Launch failsafe.

        Args:
            reason: Human-readable reason for RTL

        Returns:
            True if RTL was initiated, False otherwise
        """
        logger.warning(f"Initiating RTL: {reason}")

        # Transition state machine
        success = self.sm.trigger_failsafe("rc_loss")  # Reuse rc_loss for RTL

        if success:
            await self._add_alert(
                "critical",
                "failsafe",
                f"RTL initiated: {reason}",
                action_taken=SafetyAction.RTL.value,
            )

            # Call failsafe callback if set
            if self.on_failsafe:
                try:
                    await self.on_failsafe(SafetyAction.RTL, reason)
                except Exception as e:
                    logger.error(f"Failsafe callback error: {e}")

        return success

    async def initiate_land(self, reason: str) -> bool:
        """Initiate emergency land failsafe.

        Args:
            reason: Human-readable reason for landing

        Returns:
            True if land was initiated, False otherwise
        """
        logger.warning(f"Initiating Land: {reason}")

        # Transition state machine
        success = self.sm.trigger_failsafe("critical_battery")  # Reuse for land

        if success:
            await self._add_alert(
                "critical",
                "failsafe",
                f"Land initiated: {reason}",
                action_taken=SafetyAction.LAND.value,
            )

            if self.on_failsafe:
                try:
                    await self.on_failsafe(SafetyAction.LAND, reason)
                except Exception as e:
                    logger.error(f"Failsafe callback error: {e}")

        return success

    async def initiate_hold(self, reason: str) -> bool:
        """Initiate position hold failsafe.

        Args:
            reason: Human-readable reason for hold

        Returns:
            True if hold was initiated, False otherwise
        """
        logger.warning(f"Initiating Hold: {reason}")

        # Transition state machine
        success = self.sm.trigger_failsafe("offboard_timeout")

        if success:
            await self._add_alert(
                "warning",
                "failsafe",
                f"Hold initiated: {reason}",
                action_taken=SafetyAction.HOLD.value,
            )

            if self.on_failsafe:
                try:
                    await self.on_failsafe(SafetyAction.HOLD, reason)
                except Exception as e:
                    logger.error(f"Failsafe callback error: {e}")

        return success

    async def initiate_emergency_stop(self, reason: str) -> bool:
        """Initiate emergency stop (kill switch).

        Args:
            reason: Human-readable reason for emergency stop

        Returns:
            True if emergency stop was initiated, False otherwise
        """
        logger.critical(f"Initiating EMERGENCY STOP: {reason}")

        # Transition state machine
        success = self.sm.trigger_failsafe("kill_switch")

        if success:
            await self._add_alert(
                "critical",
                "failsafe",
                f"EMERGENCY STOP initiated: {reason}",
                action_taken=SafetyAction.EMERGENCY_STOP.value,
            )

            if self.on_failsafe:
                try:
                    await self.on_failsafe(SafetyAction.EMERGENCY_STOP, reason)
                except Exception as e:
                    logger.error(f"Failsafe callback error: {e}")

        return success

    def get_status(self) -> GuardianStatus:
        """Get current guardian status.

        Returns:
            GuardianStatus with current metrics and alerts
        """
        uptime = time.time() - self._start_time if self._start_time > 0 else 0

        active_monitors = [mt.value for mt in self._tasks.keys()]

        # Get recent alerts (last 20)
        recent_alerts = self._alerts[-20:] if self._alerts else []

        return GuardianStatus(
            is_running=self._running,
            active_monitors=active_monitors,
            last_heartbeat=self._last_heartbeat_time,
            alerts=recent_alerts,
            resource_metrics=self._resource_metrics,
            vio_metrics=self._vio_metrics,
            missed_heartbeats=self._missed_heartbeats,
            heartbeat_count=self._heartbeat_count,
            uptime_s=uptime,
        )

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self._alerts.clear()

    async def _on_heartbeat_failsafe(self, source: HeartbeatSource) -> None:
        """Handle heartbeat failsafe callback.

        Args:
            source: The heartbeat source that timed out
        """
        logger.critical(f"Heartbeat failsafe triggered for {source.value}")

        if self.config.auto_failsafe:
            if self.sm.is_flying:
                await self.initiate_hold(f"heartbeat_timeout_{source.value}")

    async def _add_alert(
        self,
        level: str,
        source: str,
        message: str,
        action_taken: Optional[str] = None,
    ) -> None:
        """Add an alert to the alert log.

        Args:
            level: Alert level (warning, critical)
            source: Source of the alert
            message: Alert message
            action_taken: Safety action taken (if any)
        """
        alert = Alert(
            level=level,
            source=source,
            message=message,
            action_taken=action_taken,
        )

        async with self._alerts_lock:
            self._alerts.append(alert)

            # Trim to max size
            if len(self._alerts) > self._max_alerts:
                self._alerts = self._alerts[-self._max_alerts:]

        # Log immediately
        if level == "critical":
            logger.critical(f"[{source}] {message}")
        else:
            logger.warning(f"[{source}] {message}")

    async def _get_telemetry_state(self) -> Optional[FlightState]:
        """Get current flight state from telemetry.

        Returns:
            FlightState from telemetry or None if unavailable
        """
        try:
            drone = await self.cm.get_drone()
            if drone is None:
                return None

            # Get armed state
            armed = False
            async for armed_state in drone.telemetry.armed():
                armed = armed_state
                break

            # Get in_air state
            in_air = False
            async for in_air_state in drone.telemetry.in_air():
                in_air = in_air_state
                break

            # Get landed state
            landed = False
            async for landed_state in drone.telemetry.landed_state():
                landed = landed_state == drone.telemetry.LandedState.ON_GROUND
                break

            # Get velocity for hovering detection
            velocity = [0.0, 0.0, 0.0]
            async for vel in drone.telemetry.velocity_ned():
                velocity = [vel.north_m_s, vel.east_m_s, vel.down_m_s]
                break

            # Determine state
            if not armed:
                return FlightState.DISARMED
            elif armed and not in_air and landed:
                return FlightState.ARMED
            elif in_air:
                velocity_magnitude = sum(v ** 2 for v in velocity) ** 0.5
                if velocity_magnitude < 0.5:
                    return FlightState.HOVERING
                else:
                    return FlightState.FLYING

            return None

        except Exception as e:
            logger.debug(f"Could not get telemetry state: {e}")
            return None

    def _states_equivalent(self, state1: FlightState, state2: FlightState) -> bool:
        """Check if two states are functionally equivalent.

        Some states like FLYING and POSITION_CONTROL are similar enough
        that mismatches shouldn't trigger alerts.

        Args:
            state1: First state
            state2: Second state

        Returns:
            True if states are equivalent
        """
        if state1 == state2:
            return True

        # Equivalent flying states
        flying_group = {
            FlightState.FLYING,
            FlightState.POSITION_CONTROL,
            FlightState.VELOCITY_CONTROL,
            FlightState.MISSION_EXECUTION,
        }

        if state1 in flying_group and state2 in flying_group:
            return True

        return False

    def _sync_state_from_telemetry(self, telemetry_state: FlightState) -> None:
        """Sync state machine from telemetry state.

        Args:
            telemetry_state: State determined from telemetry
        """
        try:
            self.sm.sync_from_telemetry({
                "armed": telemetry_state not in {FlightState.DISARMED, FlightState.INIT},
                "in_air": telemetry_state in self.sm.FLYING_STATES,
                "landed": telemetry_state == FlightState.LANDED,
            })
        except Exception as e:
            logger.debug(f"Could not sync state from telemetry: {e}")

    async def _get_resource_metrics(self) -> ResourceMetrics:
        """Get current resource metrics.

        Returns:
            ResourceMetrics with current values
        """
        try:
            import psutil

            cpu_percent = float(psutil.cpu_percent(interval=0.1))
            memory = psutil.virtual_memory()

            # Try to get temperature
            temp = 0.0
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Use first available temperature
                    for name, entries in temps.items():
                        if entries:
                            temp = float(entries[0].current)
                            break
            except Exception:
                pass

            return ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                temperature_celsius=temp,
            )

        except ImportError:
            # psutil not available - return zeros
            return ResourceMetrics()

    async def _get_vio_metrics(self) -> VIOMetrics:
        """Get current VIO metrics.

        Returns:
            VIOMetrics with current values
        """
        try:
            drone = await self.cm.get_drone()
            if drone is None:
                return VIOMetrics(is_valid=False)

            # Get odometry data for VIO metrics
            async for odometry in drone.telemetry.odometry():
                # Check velocity covariance (simplified check)
                velocity_variance = sum(odometry.velocity_covariance) / len(odometry.velocity_covariance)

                # Check position quality via position covariance
                position_variance = sum(odometry.position_covariance) / len(odometry.position_covariance)

                # Determine validity based on variance thresholds
                is_valid = position_variance < 10.0 and velocity_variance < 10.0

                # Calculate tracking quality (inverse of variance)
                tracking_quality = max(0.0, 1.0 - (position_variance / 10.0))

                return VIOMetrics(
                    position_variance=position_variance,
                    velocity_variance=velocity_variance,
                    tracking_quality=tracking_quality,
                    is_valid=is_valid,
                )

        except Exception as e:
            logger.debug(f"Could not get VIO metrics: {e}")
            return VIOMetrics(is_valid=False)

        # Fallback if async for loop doesn't execute
        return VIOMetrics(is_valid=False)

    async def __aenter__(self) -> "AsyncGuardian":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - ensures stop."""
        await self.stop()
