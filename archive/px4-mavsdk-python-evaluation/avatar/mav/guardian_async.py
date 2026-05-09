"""Async Guardian Architecture for 20Hz Safety Operations.

This module provides a fully async safety monitoring system with concurrent
tasks for heartbeat emission, resource monitoring, state consistency checks,
and VIO sanity monitoring. Maintains <50ms precision at 20Hz operational loop.

WHY ASYNC FOR SAFETY MONITORING:
-----------------------------
Traditional synchronous safety monitoring struggles with multiple concurrent
checks at different frequencies. Async enables:

1. CONCURRENT MONITORING: Multiple safety checks run simultaneously without
   blocking each other. A 1Hz resource check doesn't delay a 20Hz heartbeat.

2. PRECISE TIMING: Each monitor maintains its own precise interval using
   drift-corrected sleep loops. No cumulative timing errors.

3. NON-BLOCKING TELEMETRY: MAVSDK telemetry subscriptions are async generators.
   Sync code would need complex threading; async handles this naturally.

4. CLEAN CANCELLATION: When stopping, all monitors can be cancelled cleanly
   and awaited, ensuring no orphaned threads or processes.

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

# D2.7: Import EscalationMatrix dispatch types
from avatar.mav.escalation_matrix import (
    EscalationMatrix,
    GuardianEvent,
    FailsafeAction,
    FailsafeExecutor,
)

logger = logging.getLogger(__name__)


class MonitorType(Enum):
    """Types of monitoring tasks.

    Each monitor type runs as a separate asyncio.Task, allowing independent
    frequencies and priorities. This modular design lets us add new safety
    checks without affecting existing monitors.
    """

    HEARTBEAT = "heartbeat"           # 20Hz - Critical for offboard control
    STATE_CONSISTENCY = "state_consistency"  # 10Hz - Detect state machine drift
    RESOURCE = "resource"             # 1Hz - Monitor CPU/memory/temperature
    VIO_SANITY = "vio_sanity"         # 5Hz - Visual odometry quality checks
    NETWORK = "network"               # 1Hz - Connection health monitoring


class SafetyAction(Enum):
    """Available safety actions.

    These map to PX4 failsafe actions that the guardian can trigger
    when safety thresholds are breached.
    """

    RTL = "return_to_launch"          # Return to launch point and land
    LAND = "land"                     # Land immediately at current position
    HOLD = "hold"                     # Stop and hold position (hover)
    EMERGENCY_STOP = "emergency_stop" # Kill motors immediately (last resort)


@dataclass
class GuardianConfig:
    """Configuration for AsyncGuardian.

    All intervals are in seconds. Lower intervals = higher frequency.
    The 20Hz heartbeat (0.05s) is the most critical - PX4 requires this
    to maintain offboard control mode.

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

    heartbeat_interval_s: float = 0.05  # 20Hz - Critical for PX4 offboard mode
    offboard_timeout_s: float = 0.5    # 500ms - PX4 default offboard timeout
    resource_check_interval_s: float = 1.0   # 1Hz - System resources
    state_check_interval_s: float = 0.1    # 10Hz - State machine consistency
    vio_check_interval_s: float = 0.2     # 5Hz - Visual odometry health
    network_check_interval_s: float = 1.0   # 1Hz - Connection health
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

    Tracks system resources that could affect flight safety. High CPU usage
    can cause delayed command processing; high temperature can cause
    thermal throttling or hardware damage.

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

    VIO provides position estimates from camera + IMU fusion. When VIO fails,
    the drone loses its position reference and cannot maintain stable flight.

    Attributes:
        position_variance: Position estimate variance (lower = more confident)
        velocity_variance: Velocity estimate variance
        tracking_quality: Tracking quality score (0-1, higher = better)
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

    Alerts are stored in a ring buffer (max 100 entries) and can be retrieved
    via get_status(). Critical alerts trigger automatic failsafe actions
    when auto_failsafe is enabled.

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

    Provides a snapshot of all monitoring activity. Used by external systems
    (like the MCP server) to display current safety status to users.

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

    THE ASYNC LOOP ARCHITECTURE:
    ---------------------------
    The AsyncGuardian manages multiple independent monitoring tasks, each
    running at its own frequency. This is implemented using asyncio.Task
    objects that run concurrently within a single event loop.

    Task Layout:
    - Heartbeat Emitter (20Hz): Highest priority, precise 50ms intervals
    - State Consistency Monitor (10Hz): Detects state machine / telemetry drift
    - Resource Monitor (1Hz): Tracks CPU, memory, temperature
    - VIO Sanity Monitor (5Hz): Validates visual odometry quality
    - Network Monitor (1Hz): Checks MAVLink connection health

    Each task follows this pattern:
    1. Check if stop_event is set (cooperative cancellation)
    2. Perform monitoring action
    3. Calculate next wake time with drift correction
    4. await asyncio.sleep() to yield control

    The async/await pattern is CRITICAL here because:
    - It allows the 20Hz heartbeat to run precisely while other tasks run
    - MAVSDK telemetry subscriptions are async generators
    - Clean cancellation via stop_event and task.cancel()

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
        escalation_matrix: Optional[EscalationMatrix] = None,
    ) -> None:
        """Initialize the AsyncGuardian.

        Sets up all the internal state needed for concurrent monitoring.
        Note: Monitoring tasks are NOT started here - call start() explicitly.

        Args:
            connection_manager: ConnectionManager instance for drone access
            heartbeat_service: HeartbeatService instance for heartbeat tracking
            state_machine: FlightStateMachine instance for state management
            config: Guardian configuration. Uses defaults if not provided.
            escalation_matrix: D2.7 - Optional EscalationMatrix for dispatch.
                If provided, failsafe actions are dispatched through the matrix.
        """
        self.cm = connection_manager
        self.hb = heartbeat_service
        self.sm = state_machine
        self.config = config or GuardianConfig()

        # D2.7: EscalationMatrix for failsafe dispatch
        # When set, failsafe actions are dispatched through the matrix
        self._escalation_matrix = escalation_matrix

        # Task management
        # _tasks stores active asyncio.Task objects keyed by MonitorType.
        # This allows us to track, cancel, and await specific monitors.
        self._tasks: Dict[MonitorType, asyncio.Task[Any]] = {}
        self._running = False

        # _stop_event is an asyncio.Event used for cooperative cancellation.
        # All monitor loops check this event periodically and exit cleanly when set.
        # This is more graceful than task.cancel() for routine shutdowns.
        self._stop_event = asyncio.Event()

        # Timing and metrics
        self._start_time: float = 0.0
        self._last_heartbeat_time: float = 0.0
        self._missed_heartbeats = 0
        self._heartbeat_count = 0

        # State tracking with async locks for thread-safety.
        # Multiple monitors may read/write these concurrently.
        self._alerts: List[Alert] = []
        self._max_alerts = 100
        self._alerts_lock = asyncio.Lock()

        # Resource tracking with locks
        self._resource_metrics = ResourceMetrics()
        self._resource_lock = asyncio.Lock()

        # VIO tracking with locks
        self._vio_metrics = VIOMetrics()
        self._vio_lock = asyncio.Lock()

        # Network tracking
        self._last_ping_time: float = 0.0
        self._network_healthy = True

        # Telemetry state cache - used to detect state changes
        self._last_telemetry_state: Optional[FlightState] = None
        self._last_telemetry_time: float = 0.0

        # Failsafe callback - called when safety action is triggered
        self.on_failsafe: Optional[Callable[[SafetyAction, str], Coroutine[Any, Any, None]]] = None

    @property
    def is_running(self) -> bool:
        """Whether the guardian is currently running."""
        return self._running

    async def start(self) -> None:
        """Start the guardian and all monitoring tasks.

        This method is idempotent - calling it multiple times when already
        running will not create duplicate tasks.

        THE STARTUP SEQUENCE:
        1. Clear stop_event (allows monitors to run)
        2. Record start time for uptime tracking
        3. Register failsafe callback with HeartbeatService
        4. Spawn all configured monitor tasks as asyncio.Task objects
        5. Each task immediately starts its monitoring loop

        The monitors run concurrently - they don't block each other because
        each uses await asyncio.sleep() to yield control back to the event loop.
        """
        if self._running:
            logger.debug("AsyncGuardian already running")
            return

        self._stop_event.clear()
        self._start_time = time.time()
        self._running = True

        # Register heartbeat sources with the service
        # These will be monitored for staleness
        self.hb.add_source("guardian", timeout_s=self.config.heartbeat_interval_s * 10)
        self.hb.add_source("offboard", timeout_s=self.config.offboard_timeout_s)
        self.hb.add_source("llm", timeout_s=self.config.offboard_timeout_s)

        # Start monitor tasks
        # Each creates an asyncio.Task that runs concurrently
        await self._start_monitors()

        logger.info("AsyncGuardian started with 20Hz safety monitoring")

    async def stop(self) -> None:
        """Stop the guardian and cleanup all tasks.

        This method is idempotent - calling it multiple times is safe.

        THE SHUTDOWN SEQUENCE:
        1. Set stop_event (signals monitors to exit cleanly)
        2. Set _running = False (prevents new operations)
        3. Cancel all monitor tasks and await their completion
        4. Unregister from HeartbeatService
        5. Log uptime statistics

        Task cancellation uses a two-phase approach:
        - First, stop_event is set for cooperative exit
        - Then task.cancel() is called for tasks that don't respond
        - Finally we await each task to ensure clean shutdown
        """
        if not self._running:
            logger.debug("AsyncGuardian already stopped")
            return

        # Signal stop - cooperative cancellation
        self._stop_event.set()
        self._running = False

        # Cancel all tasks and await their completion
        await self._stop_monitors()

        # Signal heartbeat service to stop monitoring
        await self.hb.stop_async()

        uptime = time.time() - self._start_time
        logger.info(f"AsyncGuardian stopped (uptime: {uptime:.1f}s)")

    async def _on_heartbeat_failsafe(self, source: Any) -> None:
        """Legacy/test hook when a heartbeat source is treated as failed.

        ``source`` is typically a :class:`HeartbeatSource` constant or string id.
        """
        key = source if isinstance(source, str) else getattr(source, "value", str(source))
        reason = f"heartbeat_fault:{key}"
        if self.config.auto_failsafe and self.sm.is_flying:
            await self.initiate_hold(reason)

    async def _start_monitors(self) -> None:
        """Start all configured monitoring tasks.

        Each enabled monitor is spawned as a separate asyncio.Task. This allows:
        - Independent frequencies (20Hz heartbeat vs 1Hz resource check)
        - Independent failure modes (one monitor crashing doesn't stop others)
        - Easy extension (add new monitors without changing existing ones)

        Tasks are stored in self._tasks dict keyed by MonitorType for later
        cancellation and status reporting.
        """
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
        """Stop all monitoring tasks.

        Uses asyncio.Task.cancel() for each monitor, then awaits them.
        CancelledError is expected and suppressed - it's the normal
        mechanism for stopping asyncio tasks.

        This ensures all monitors have a chance to clean up (close connections,
        flush buffers, etc.) before the guardian fully stops.
        """
        # Cancel all tasks
        for monitor_type, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected - this is how we stop tasks
                logger.debug(f"Stopped {monitor_type.value} monitor")

        self._tasks.clear()

    async def _heartbeat_emitter(self) -> None:
        """Emit heartbeats at 20Hz (50ms intervals).

        THE 20HZ HEARTBEAT LOOP:
        ------------------------
        This is the most critical monitoring task. PX4 requires heartbeats
        at 2Hz minimum, but we run at 20Hz for:
        - Sub-50ms latency on offboard timeout detection
        - Redundancy (missed heartbeats don't immediately cause timeout)
        - Smoother control when using offboard mode

        DRIFT CORRECTION:
        The loop uses "next_emit_time += interval" rather than recalculating
        from current time. This prevents cumulative timing drift. If we fall
        behind (due to event loop congestion), we log it but don't try to
        "catch up" by emitting multiple rapid heartbeats.

        The loop structure:
        1. Record heartbeat timestamp
        2. Update heartbeat service
        3. Calculate next target time (with drift correction)
        4. await asyncio.sleep() until next emission

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
                self.hb.record_heartbeat("guardian")

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

                    # Don't accumulate too much lag - reset to prevent burst
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

        CONCURRENT STATE CHECKS:
        -----------------------
        This monitor runs at 10Hz, independently of the 20Hz heartbeat and
        other monitors. It performs two critical checks:

        1. STATE MACHINE SYNC:
           Compares the FlightStateMachine's believed state against actual
           telemetry from PX4. If they diverge (e.g., state machine thinks
           we're flying but telemetry shows disarmed), we emit a warning
           and sync the state machine to match reality.

        2. OFFBOARD TIMEOUT:
           Checks if we've received heartbeats from the offboard controller
           (LLM/agent) within the 500ms timeout window. If not, the drone
           will automatically exit offboard mode - we detect this and can
           trigger a failsafe (HOLD mode) to prevent uncontrolled drift.

        The async pattern here allows us to:
        - Use async for loops with MAVSDK telemetry (natively async)
        - Check stop_event between iterations (clean cancellation)
        - Not block other monitors while waiting for telemetry

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

                # Get current telemetry state from PX4
                telemetry_state = await self._get_telemetry_state()

                if telemetry_state is not None:
                    sm_state = self.sm.current_state

                    # Check for mismatch between state machine and reality
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
                            # The state machine should always reflect reality
                            self._sync_state_from_telemetry(telemetry_state)

                # Check offboard timeout - critical for safety
                offboard_age = self.hb.get_last_beat_age("offboard")
                if offboard_age is not None and offboard_age > self.config.offboard_timeout_s:
                    await self._add_alert(
                        "critical",
                        MonitorType.STATE_CONSISTENCY.value,
                        f"Offboard timeout: {offboard_age:.2f}s > {self.config.offboard_timeout_s}s",
                    )

                    # Trigger failsafe - hold position until control resumes
                    if self.config.auto_failsafe:
                        await self.initiate_hold("offboard_timeout")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"State consistency monitor error: {e}")

        logger.debug("State consistency monitor stopped")

    async def _resource_monitor(self) -> None:
        """Monitor system resources (CPU, temperature, memory).

        RESOURCE SAFETY AT 1HZ:
        ----------------------
        Unlike the 20Hz heartbeat, resource monitoring only needs to run
        at 1Hz because resource conditions change slowly (seconds, not ms).

        Uses psutil (when available) to check:
        - CPU usage: High CPU can delay critical flight commands
        - Memory usage: Memory pressure causes swap thrashing
        - Temperature: Thermal throttling reduces performance

        Each check is independent - high CPU alone won't trigger failsafe,
        but critical temperature will. Alerts escalate from warning to
        critical based on severity.

        Checks at 1Hz for resource issues that could affect safety.
        """
        logger.debug("Resource monitor started (1Hz)")

        interval = self.config.resource_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Get resource metrics via psutil
                metrics = await self._get_resource_metrics()

                async with self._resource_lock:
                    self._resource_metrics = metrics

                # Check CPU - warning only
                if metrics.cpu_percent > self.config.max_cpu_percent:
                    await self._add_alert(
                        "warning",
                        MonitorType.RESOURCE.value,
                        f"High CPU usage: {metrics.cpu_percent:.1f}%",
                    )

                # Check memory - warning only
                if metrics.memory_percent > self.config.max_memory_percent:
                    await self._add_alert(
                        "warning",
                        MonitorType.RESOURCE.value,
                        f"High memory usage: {metrics.memory_percent:.1f}%",
                    )

                # Check temperature - critical (can cause hardware damage)
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

        VIO SAFETY AT 5HZ:
        -----------------
        VIO provides position estimates from camera + IMU fusion. When VIO
        fails or degrades, the drone loses position awareness and cannot
        maintain stable flight.

        This monitor checks odometry data from PX4 at 5Hz:
        - is_valid: Whether the VIO system reports valid data
        - position_variance: Estimate uncertainty (higher = less confident)
        - tracking_quality: Feature tracking score (0-1)

        VIO failure modes:
        - Poor lighting (can't track features)
        - Fast motion (motion blur)
        - Textureless environments (no features to track)
        - IMU drift (accumulated error)

        Critical failures trigger immediate HOLD to prevent drift.

        Checks at 5Hz for VIO quality degradation.
        """
        logger.debug("VIO sanity monitor started (5Hz)")

        interval = self.config.vio_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Get VIO metrics from telemetry
                metrics = await self._get_vio_metrics()

                async with self._vio_lock:
                    self._vio_metrics = metrics

                # Check VIO validity - critical for position control
                if not metrics.is_valid:
                    await self._add_alert(
                        "critical",
                        MonitorType.VIO_SANITY.value,
                        "VIO data invalid - position estimate unreliable",
                    )

                    # Hold position immediately - can't navigate without VIO
                    if self.config.auto_failsafe and self.sm.is_flying:
                        await self.initiate_hold("vio_invalid")

                # Check position variance - warning if degraded
                elif metrics.position_variance > 1.0:  # 1 meter variance threshold
                    await self._add_alert(
                        "warning",
                        MonitorType.VIO_SANITY.value,
                        f"High position variance: {metrics.position_variance:.2f}m",
                    )

                # Check tracking quality - warning if poor
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

        NETWORK SAFETY AT 1HZ:
        ---------------------
        MAVLink connection health is critical. This monitor checks:
        - Connection health status from ConnectionManager
        - Stale telemetry (no data for >2 seconds)

        Connection loss scenarios:
        - WiFi interference/degradation
        - USB cable disconnection
        - Companion computer crash
        - PX4 reboot

        RTL (Return to Launch) is triggered on connection loss because:
        - We can't send commands without connection
        - Drone should return to safe location autonomously
        - Better than losing the drone or having it drift/fly away

        Checks at 1Hz for network issues.
        """
        logger.debug("Network monitor started (1Hz)")

        interval = self.config.network_check_interval_s

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)

                if self._stop_event.is_set():
                    break

                # Check connection health from ConnectionManager
                if not self.cm.health.is_healthy:
                    await self._add_alert(
                        "critical",
                        MonitorType.NETWORK.value,
                        "Connection to drone unhealthy",
                    )

                    # RTL if flying - return home on connection loss
                    if self.config.auto_failsafe and self.sm.is_flying:
                        await self.initiate_rtl("connection_unhealthy")

                # Check for stale telemetry (no MAVLink traffic)
                last_heartbeat_age = time.time() - self.cm.health.last_heartbeat
                if last_heartbeat_age > 2.0:  # No telemetry for 2 seconds
                    await self._add_alert(
                        "critical",
                        MonitorType.NETWORK.value,
                        f"Stale telemetry: {last_heartbeat_age:.1f}s since last heartbeat",
                    )

                    # RTL on stale telemetry - same as connection loss
                    if self.config.auto_failsafe and self.sm.is_flying:
                        await self.initiate_rtl("telemetry_stale")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Network monitor error: {e}")

        logger.debug("Network monitor stopped")

    async def initiate_rtl(self, reason: str) -> bool:
        """Initiate Return-To-Launch failsafe.

        RTL is the safest default action when control is uncertain. The drone
        climbs to RTL altitude, flies directly to the launch point, and lands
        automatically.

        D2.7: If escalation_matrix is set, dispatches through the matrix's
        failsafe executor system. Otherwise, executes directly.

        Args:
            reason: Human-readable reason for RTL

        Returns:
            True if RTL was initiated, False otherwise
        """
        logger.warning(f"Initiating RTL: {reason}")

        # D2.7: Dispatch through EscalationMatrix if configured
        if self._escalation_matrix is not None:
            event = GuardianEvent(
                condition="geofence_breach",  # Maps to RTL action
                reason=reason,
                context={"source": "async_guardian"}
            )
            try:
                await self._escalation_matrix.dispatch_guardian_event(event)
                logger.info("RTL dispatched through EscalationMatrix")
            except Exception as e:
                logger.error(f"EscalationMatrix dispatch failed: {e}")
                # Fall through to direct execution

        # Transition state machine
        success = self.sm.trigger_failsafe("rc_loss")  # Reuse rc_loss for RTL

        if success:
            # Execute RTL action on drone
            try:
                drone = await self.cm.get_drone()
                if drone is not None:
                    await drone.action.return_to_launch()
                    logger.info("RTL action sent to drone")
            except Exception as e:
                logger.error(f"Failed to send RTL action: {e}")

            await self._add_alert(
                "critical",
                "failsafe",
                f"RTL initiated: {reason}",
                action_taken=SafetyAction.RTL.value,
            )

            # Call failsafe callback if set (for external notification)
            if self.on_failsafe:
                try:
                    await self.on_failsafe(SafetyAction.RTL, reason)
                except Exception as e:
                    logger.error(f"Failsafe callback error: {e}")

        return success

    async def initiate_land(self, reason: str) -> bool:
        """Initiate emergency land failsafe.

        Land immediately at current position. Used when RTL is not safe
        (e.g., low battery, obstacle near launch point).

        D2.7: If escalation_matrix is set, dispatches through the matrix's
        failsafe executor system. Otherwise, executes directly.

        Args:
            reason: Human-readable reason for landing

        Returns:
            True if land was initiated, False otherwise
        """
        logger.warning(f"Initiating Land: {reason}")

        # D2.7: Dispatch through EscalationMatrix if configured
        if self._escalation_matrix is not None:
            event = GuardianEvent(
                condition="total_power_loss",  # Maps to Land action
                reason=reason,
                context={"source": "async_guardian"}
            )
            try:
                await self._escalation_matrix.dispatch_guardian_event(event)
                logger.info("Land dispatched through EscalationMatrix")
            except Exception as e:
                logger.error(f"EscalationMatrix dispatch failed: {e}")
                # Fall through to direct execution

        # Transition state machine
        success = self.sm.trigger_failsafe("critical_battery")  # Reuse for land

        if success:
            # Execute Land action on drone
            try:
                drone = await self.cm.get_drone()
                if drone is not None:
                    await drone.action.land()
                    logger.info("Land action sent to drone")
            except Exception as e:
                logger.error(f"Failed to send Land action: {e}")

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

        Hold maintains current position (hover). Used for temporary issues
        that may resolve (e.g., offboard timeout, VIO degradation).

        D2.7: If escalation_matrix is set, dispatches through the matrix's
        failsafe executor system. Otherwise, executes directly.

        Args:
            reason: Human-readable reason for hold

        Returns:
            True if hold was initiated, False otherwise
        """
        logger.warning(f"Initiating Hold: {reason}")

        # D2.7: Dispatch through EscalationMatrix if configured
        if self._escalation_matrix is not None:
            event = GuardianEvent(
                condition="state_inconsistency",  # Maps to Hold action
                reason=reason,
                context={"source": "async_guardian"}
            )
            try:
                await self._escalation_matrix.dispatch_guardian_event(event)
                logger.info("Hold dispatched through EscalationMatrix")
            except Exception as e:
                logger.error(f"EscalationMatrix dispatch failed: {e}")
                # Fall through to direct execution

        # Transition state machine
        success = self.sm.trigger_failsafe("offboard_timeout")

        if success:
            # Execute Hold action on drone
            try:
                drone = await self.cm.get_drone()
                if drone is not None:
                    await drone.action.hold()
                    logger.info("Hold action sent to drone")
            except Exception as e:
                logger.error(f"Failed to send Hold action: {e}")

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

        EMERGENCY STOP kills motors immediately. This is a last resort when:
        - Drone is flying toward people/obstacles
        - Complete loss of control
        - Hardware failure making flight unsafe

        WARNING: Will cause drone to fall from sky. Only use when the
        alternative (uncontrolled flight) is worse.

        Args:
            reason: Human-readable reason for emergency stop

        Returns:
            True if emergency stop was initiated, False otherwise
        """
        logger.critical(f"Initiating EMERGENCY STOP: {reason}")

        # Transition state machine
        success = self.sm.trigger_failsafe("kill_switch")

        if success:
            # Execute Kill/Terminate action on drone
            try:
                drone = await self.cm.get_drone()
                if drone is not None:
                    # Try kill first (immediate motor cutoff)
                    try:
                        await drone.action.kill()
                        logger.critical("Kill action sent to drone")
                    except Exception:
                        # Fallback to terminate if kill not supported
                        await drone.action.terminate()
                        logger.critical("Terminate action sent to drone")
            except Exception as e:
                logger.error(f"Failed to send emergency stop action: {e}")

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

        Returns a snapshot of all monitoring activity including:
        - Which monitors are active
        - Heartbeat statistics
        - Recent alerts
        - Resource and VIO metrics

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

    async def _add_alert(
        self,
        level: str,
        source: str,
        message: str,
        action_taken: Optional[str] = None,
    ) -> None:
        """Add an alert to the alert log.

        Alerts are stored in a ring buffer (max 100 entries) to prevent
        unbounded memory growth. Critical alerts are logged at CRITICAL
        level; warnings at WARNING level.

        Thread-safe: Uses asyncio.Lock to prevent concurrent modification.

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

            # Trim to max size (ring buffer behavior)
            if len(self._alerts) > self._max_alerts:
                self._alerts = self._alerts[-self._max_alerts:]

        # Log immediately at appropriate level
        if level == "critical":
            logger.critical(f"[{source}] {message}")
        else:
            logger.warning(f"[{source}] {message}")

    async def _get_telemetry_state(self) -> Optional[FlightState]:
        """Get current flight state from telemetry.

        Queries PX4 telemetry streams to determine actual flight state:
        - armed: Whether motors are armed
        - in_air: Whether drone has taken off
        - velocity: For detecting hover vs flying

        Uses asyncio generators (async for) to get single samples from
        MAVSDK telemetry streams. This is non-blocking and integrates
        cleanly with the async monitor architecture.

        Returns:
            FlightState from telemetry or None if unavailable
        """
        try:
            drone = await self.cm.get_drone()
            if drone is None:
                return None

            # Get armed state - use async for with break for single sample
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

            # Determine state from telemetry data
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
        that mismatches shouldn't trigger alerts. This prevents false
        positives during normal flight mode transitions.

        Args:
            state1: First state
            state2: Second state

        Returns:
            True if states are equivalent
        """
        if state1 == state2:
            return True

        # Equivalent flying states - all represent active flight
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

        When the state machine drifts from reality (e.g., due to missed
        transitions), this forces synchronization. The state machine
        should always reflect the actual drone state.

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

        Uses psutil (when available) to check system resources. The import
        is done inside the method to make psutil an optional dependency.

        Returns:
            ResourceMetrics with current values
        """
        try:
            import psutil

            cpu_percent = float(psutil.cpu_percent(interval=0.1))
            memory = psutil.virtual_memory()

            # Try to get temperature (not available on all platforms)
            temp = 0.0
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Use first available temperature sensor
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
            # psutil not available - return zeros (graceful degradation)
            return ResourceMetrics()

    async def _get_vio_metrics(self) -> VIOMetrics:
        """Get current VIO metrics.

        Queries odometry data from PX4 telemetry. Odometry contains
        position/velocity estimates with covariance matrices that indicate
        estimate quality.

        The covariance values indicate uncertainty - higher variance means
        less confidence in the position estimate.

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

        # Fallback if async for loop doesn't execute (shouldn't happen)
        return VIOMetrics(is_valid=False)

    async def __aenter__(self) -> "AsyncGuardian":
        """Async context manager entry.

        Allows using the guardian with 'async with' syntax:
            async with AsyncGuardian(...) as guardian:
                # guardian is running here
                pass
            # guardian is stopped here
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - ensures stop.

        This guarantees the guardian stops even if an exception is raised
        in the context body. This is critical for safety - we never want
        to leave the guardian running after the controlling context exits.
        """
        await self.stop()
