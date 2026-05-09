# Python Asyncio Patterns for Safety-Critical Drone Control

## Executive Summary

This document provides concrete asyncio design patterns for the Project Avatar drone orchestrator, addressing safety-critical requirements: real-time task prioritization, event loop stability, graceful degradation, and fault recovery without process exit.

**Key Principles:**
- Heartbeat tasks are **life-critical** and must never be blocked
- LLM inference is **variable-latency** and must be isolated from real-time tasks
- Task failure is **expected**; recovery is **required**
- Process restart is **unacceptable** mid-flight

---

## 1. Real-Time Task Prioritization Strategies

### 1.1 Priority-Based Task Scheduling

Python asyncio uses cooperative scheduling, not preemption. Priority is enforced through:
1. **Strategic yielding** - High-priority tasks yield minimally
2. **Dedicated event loop policies** - Use `asyncio.PriorityQueue` for work items
3. **CPU isolation** - Thread-based separation for GIL-sensitive work

```python
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
import heapq

@dataclass(order=True)
class PriorityTask:
    """Priority queue entry for scheduled work."""
    priority: int  # Lower = higher priority
    seq: int = field(compare=True)  # Tie-breaker for FIFO within priority
    coro: Callable = field(compare=False)
    name: str = field(compare=False)
    deadline: Optional[float] = field(default=None, compare=False)

class PriorityScheduler:
    """
    Deadline-aware priority scheduler for safety-critical tasks.
    
    Priorities (lower = higher priority):
    0 - CRITICAL: MAVSDK heartbeat, emergency stop
    1 - HIGH: Telemetry processing, safety monitor
    2 - MEDIUM: Vision inference, state updates
    3 - LOW: LLM orchestration, logging
    4 - BACKGROUND: Analytics, model warmup
    """
    
    PRIORITY_CRITICAL = 0   # Never block, 20Hz heartbeat
    PRIORITY_HIGH = 1       # < 10ms latency
    PRIORITY_MEDIUM = 2     # < 50ms latency
    PRIORITY_LOW = 3        # < 500ms latency
    PRIORITY_BACKGROUND = 4 # Best effort
    
    def __init__(self):
        self._queue: asyncio.PriorityQueue[PriorityTask] = asyncio.PriorityQueue()
        self._seq = 0
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the scheduler worker."""
        self._running = True
        self._task = asyncio.create_task(self._worker(), name="priority_scheduler")
        
    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    def submit(
        self,
        coro: Callable[[], Any],
        priority: int,
        name: str,
        deadline_ms: Optional[float] = None
    ):
        """Submit work with priority and optional deadline."""
        self._seq += 1
        deadline = time.monotonic() + (deadline_ms / 1000) if deadline_ms else None
        task = PriorityTask(
            priority=priority,
            seq=self._seq,
            coro=coro,
            name=name,
            deadline=deadline
        )
        self._queue.put_nowait(task)
        
    async def _worker(self):
        """Process queue with deadline awareness."""
        while self._running:
            try:
                # Use timeout to allow periodic checks
                task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.001  # 1ms max wait
                )
                
                # Check deadline violation
                if task.deadline and time.monotonic() > task.deadline:
                    print(f"WARNING: Task {task.name} missed deadline!")
                    # Still execute - missing data is worse than late data
                    # But log for post-flight analysis
                    
                # Execute the coroutine
                try:
                    await task.coro()
                except Exception as e:
                    print(f"Task {task.name} failed: {e}")
                    # Continue processing - don't let one task kill the scheduler
                    
            except asyncio.TimeoutError:
                # No work available - yield control
                await asyncio.sleep(0)  # Yield to event loop
            except asyncio.CancelledError:
                break

# Usage example
scheduler = PriorityScheduler()

async def heartbeat_task():
    """Critical: 20Hz heartbeat to PX4."""
    pass

async def vision_inference():
    """Medium priority: YOLO detection."""
    pass

# Submit with priorities
scheduler.submit(heartbeat_task, PriorityScheduler.PRIORITY_CRITICAL, "heartbeat")
scheduler.submit(vision_inference, PriorityScheduler.PRIORITY_MEDIUM, "yolo", deadline_ms=50)
```

### 1.2 Deadline Scheduling with `call_at()` and `call_later()`

For time-critical callbacks, use the event loop's scheduling primitives directly:

```python
import asyncio
from typing import Callable, Optional

class DeadlineScheduler:
    """
    Hard real-time scheduling using event loop timer handles.
    
    Guarantees callback execution at specified times, not "whenever the loop is free".
    """
    
    def __init__(self):
        self._handles: list[asyncio.TimerHandle] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    async def start(self):
        self._loop = asyncio.get_running_loop()
        
    def schedule_periodic(
        self,
        callback: Callable,
        period_seconds: float,
        jitter_tolerance_ms: float = 5.0
    ) -> asyncio.TimerHandle:
        """
        Schedule a callback to run at precise intervals.
        
        Args:
            callback: Function to call (not a coroutine - use run_coroutine_threadsafe if needed)
            period_seconds: Exact period between calls
            jitter_tolerance_ms: Acceptable timing deviation before warning
        """
        async def wrapper():
            while True:
                start = self._loop.time()
                
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
                    
                # Calculate precise next time
                elapsed = self._loop.time() - start
                sleep_time = max(0, period_seconds - elapsed)
                
                # Check jitter
                actual_period = elapsed + sleep_time
                jitter_ms = abs(actual_period - period_seconds) * 1000
                if jitter_ms > jitter_tolerance_ms:
                    print(f"JITTER: {callback.__name__} jitter = {jitter_ms:.2f}ms")
                    
                await asyncio.sleep(sleep_time)
                
        task = asyncio.create_task(wrapper(), name=f"periodic_{callback.__name__}")
        return task
        
    def schedule_at(
        self,
        when: float,
        callback: Callable,
        *args
    ) -> asyncio.TimerHandle:
        """Schedule callback at absolute timestamp (using loop time)."""
        return self._loop.call_at(when, callback, *args)
        
    def schedule_later(
        self,
        delay: float,
        callback: Callable,
        *args
    ) -> asyncio.TimerHandle:
        """Schedule callback after delay seconds."""
        return self._loop.call_later(delay, callback, *args)

# Usage for drone heartbeat
async def critical_heartbeat():
    """
    20Hz heartbeat to PX4 offboard control.
    
    Per PX4 docs: minimum 2Hz, recommended 10-20Hz.
    This implementation targets 20Hz (50ms period).
    """
    # Send MAVSDK setpoint
    await drone.offboard.set_position_ned(setpoint)
    
scheduler = DeadlineScheduler()
await scheduler.start()

# Start 20Hz heartbeat (50ms period)
heartbeat_task = scheduler.schedule_periodic(
    critical_heartbeat,
    period_seconds=0.05,  # 50ms = 20Hz
    jitter_tolerance_ms=5.0  # Warn if >5ms jitter
)
```

---

## 2. Preventing Event Loop Blocking

### 2.1 CPU-Bound Work Isolation

YOLO inference and LLM calls block the event loop. Isolate them:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import TypeVar, Callable, Any
import functools

T = TypeVar('T')

class ComputeIsolator:
    """
    Isolate CPU/GPU-bound work from the asyncio event loop.
    
    Pattern: Event loop manages coordination; thread/process pool handles computation.
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        use_processes: bool = False  # Processes for GIL-heavy work
    ):
        if use_processes:
            self._executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=max_workers)
            
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    async def start(self):
        self._loop = asyncio.get_running_loop()
        
    async def shutdown(self):
        """Graceful executor shutdown."""
        self._executor.shutdown(wait=True, cancel_futures=True)
        
    async def run_cpu_bound(
        self,
        func: Callable[..., T],
        *args,
        timeout_seconds: Optional[float] = None,
        priority: str = "normal"  # "high", "normal", "low"
    ) -> T:
        """
        Run CPU-bound function in executor without blocking event loop.
        
        Args:
            func: Synchronous function to execute
            args: Arguments to pass to func
            timeout_seconds: Maximum time to wait (raises TimeoutError)
            priority: Scheduling hint (implementation-dependent)
            
        Returns:
            Result of func(*args)
            
        Raises:
            TimeoutError: If execution exceeds timeout
            Exception: Any exception raised by func
        """
        # Create partial for kwargs support
        partial_func = functools.partial(func, *args)
        
        # Submit to executor
        future = self._loop.run_in_executor(self._executor, partial_func)
        
        # Apply timeout if specified
        if timeout_seconds:
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        
        return await future

# Usage in drone orchestrator
isolator = ComputeIsolator(max_workers=2)

async def run_yolo_inference(frame: np.ndarray) -> Detections:
    """
    Run YOLO inference without blocking heartbeat.
    
    YOLO on MPS takes 17-40ms. Without isolation, this blocks all async tasks.
    """
    return await isolator.run_cpu_bound(
        yolo_model.predict,
        frame,
        timeout_seconds=0.1,  # 100ms max
        priority="high"
    )
    
async def run_llm_query(prompt: str) -> str:
    """
    LLM inference takes 1.5-2.5s. Never run on event loop.
    """
    return await isolator.run_cpu_bound(
        ollama.generate,
        model="llama3.1:8b",
        prompt=prompt,
        timeout_seconds=5.0,
        priority="low"  # LLM can wait; heartbeat cannot
    )
```

### 2.2 Asyncio-Safe Sleep and Precise Timing

```python
import asyncio
import time

class PreciseSleeper:
    """
    High-precision asyncio sleep that accounts for execution time.
    
    Standard asyncio.sleep() doesn't compensate for processing time between
    calls, causing cumulative drift in periodic tasks.
    """
    
    def __init__(self, target_hz: float):
        self.period = 1.0 / target_hz
        self.next_time = time.monotonic()
        
    async def sleep(self):
        """
        Sleep exactly until next period boundary.
        
        Usage:
            sleeper = PreciseSleeper(target_hz=20)  # 20Hz
            while True:
                do_work()
                await sleeper.sleep()  # Compensates for work duration
        """
        self.next_time += self.period
        
        # Calculate sleep duration
        now = time.monotonic()
        sleep_duration = self.next_time - now
        
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)
        else:
            # We've missed the deadline - log but continue
            # Don't try to "catch up" - that causes burst processing
            print(f"Deadline missed by {-sleep_duration*1000:.1f}ms")
            self.next_time = now  # Reset to avoid compounding

# Comparison: naive vs precise
async def naive_heartbeat():
    """Drifts over time due to execution overhead."""
    while True:
        await send_setpoint()
        await asyncio.sleep(0.05)  # Actual period = 50ms + execution time
        
async def precise_heartbeat():
    """Maintains exact 20Hz regardless of execution time."""
    sleeper = PreciseSleeper(target_hz=20)
    while True:
        await send_setpoint()
        await sleeper.sleep()  # Compensates for send_setpoint() duration
```

---

## 3. Memory Fragmentation Prevention in Long-Running Loops

### 3.1 Preallocated Buffer Pools

```python
from collections import deque
import numpy as np
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class PreallocatedPool(Generic[T]):
    """
    Preallocated object pool to prevent GC pressure in long-running loops.
    
    Critical for vision pipelines: allocate once, reuse indefinitely.
    """
    
    def __init__(
        self,
        factory: Callable[[], T],
        reset: Callable[[T], None],
        size: int,
        name: str = "pool"
    ):
        self.factory = factory
        self.reset = reset
        self.name = name
        self._available: deque[T] = deque()
        self._in_use: set[T] = set()
        self._emergency_allocations = 0
        
        # Preallocate
        for _ in range(size):
            obj = factory()
            self._available.append(obj)
            
    def acquire(self) -> T:
        """Get object from pool or emergency allocate."""
        if self._available:
            obj = self._available.popleft()
            self._in_use.add(obj)
            return obj
        
        # Pool exhausted - emergency allocation
        self._emergency_allocations += 1
        if self._emergency_allocations % 100 == 1:
            print(f"WARNING: {self.name} pool exhausted ({self._emergency_allocations} emergency allocs)")
        return self.factory()
        
    def release(self, obj: T):
        """Return object to pool after resetting."""
        if obj in self._in_use:
            self._in_use.remove(obj)
            self.reset(obj)
            self._available.append(obj)
        # If not in _in_use, it was emergency allocated - let GC collect it
        
    def stats(self) -> dict:
        return {
            "available": len(self._available),
            "in_use": len(self._in_use),
            "emergency_allocations": self._emergency_allocations,
            "pool_size": len(self._available) + len(self._in_use)
        }

# Drone-specific pools

class FrameBufferPool:
    """Pool for 416x416 RGB frames (YOLO input size)."""
    
    def __init__(self, num_buffers: int = 5):
        def factory():
            # Force contiguous memory for efficient GPU transfer
            return np.zeros((416, 416, 3), dtype=np.uint8, order='C')
        
        def reset(buf):
            buf.fill(0)  # Zero-fill for determinism
            
        self.pool = PreallocatedPool(factory, reset, num_buffers, "frame_buffer")
        
    def acquire(self) -> np.ndarray:
        return self.pool.acquire()
        
    def release(self, buf: np.ndarray):
        self.pool.release(buf)

class DetectionResultPool:
    """Pool for YOLO detection results to prevent list/dict churn."""
    
    def __init__(self, num_slots: int = 10):
        def factory():
            return {
                'boxes': [],      # List of [x1, y1, x2, y2]
                'confidences': [],
                'classes': [],
                'timestamp': 0.0,
                'frame_id': 0
            }
        
        def reset(d):
            d['boxes'].clear()
            d['confidences'].clear()
            d['classes'].clear()
            d['timestamp'] = 0.0
            d['frame_id'] = 0
            
        self.pool = PreallocatedPool(factory, reset, num_slots, "detection_result")
```

### 3.2 Memory Pressure Monitoring

```python
import psutil
import gc
from typing import Callable, Optional

class MemoryGuard:
    """
    Monitor memory pressure and trigger defensive actions.
    
    Critical for 16GB MacBook M3 where LLM + YOLO + system compete for RAM.
    """
    
    def __init__(
        self,
        warning_threshold_gb: float = 12.0,
        critical_threshold_gb: float = 14.0,
        absolute_max_gb: float = 15.0
    ):
        self.warning_threshold = warning_threshold_gb * 1024**3
        self.critical_threshold = critical_threshold_gb * 1024**3
        self.absolute_max = absolute_max_gb * 1024**3
        self._callbacks: dict[str, list[Callable]] = {
            'warning': [],
            'critical': [],
            'emergency': []
        }
        self._monitor_task: Optional[asyncio.Task] = None
        
    def on_warning(self, callback: Callable):
        self._callbacks['warning'].append(callback)
        
    def on_critical(self, callback: Callable):
        self._callbacks['critical'].append(callback)
        
    def on_emergency(self, callback: Callable):
        self._callbacks['emergency'].append(callback)
        
    async def start_monitoring(self, check_interval_seconds: float = 5.0):
        """Start background memory monitoring."""
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(check_interval_seconds),
            name="memory_guard"
        )
        
    async def stop(self):
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
    async def _monitor_loop(self, interval: float):
        """Background monitoring coroutine."""
        while True:
            try:
                mem = psutil.virtual_memory()
                used = mem.used
                
                if used > self.absolute_max:
                    # EMERGENCY: Force garbage collection, clear caches
                    print(f"EMERGENCY: Memory at {used/1024**3:.1f}GB!")
                    gc.collect()
                    for cb in self._callbacks['emergency']:
                        await cb()
                        
                elif used > self.critical_threshold:
                    # CRITICAL: Drop non-essential buffers
                    print(f"CRITICAL: Memory at {used/1024**3:.1f}GB")
                    for cb in self._callbacks['critical']:
                        await cb()
                        
                elif used > self.warning_threshold:
                    # WARNING: Reduce cache sizes
                    print(f"WARNING: Memory at {used/1024**3:.1f}GB")
                    for cb in self._callbacks['warning']:
                        await cb()
                        
            except Exception as e:
                print(f"Memory monitor error: {e}")
                
            await asyncio.sleep(interval)
            
    def get_status(self) -> dict:
        mem = psutil.virtual_memory()
        return {
            'used_gb': mem.used / 1024**3,
            'available_gb': mem.available / 1024**3,
            'percent': mem.percent,
            'status': self._get_status_label(mem.used)
        }
        
    def _get_status_label(self, used: int) -> str:
        if used > self.absolute_max:
            return 'emergency'
        elif used > self.critical_threshold:
            return 'critical'
        elif used > self.warning_threshold:
            return 'warning'
        return 'ok'

# Usage in drone orchestrator
memory_guard = MemoryGuard(
    warning_threshold_gb=12.0,
    critical_threshold_gb=14.0,
    absolute_max_gb=15.0
)

# Register defensive actions
async def on_warning():
    """Reduce frame buffer pool size."""
    await frame_pool.resize(max_buffers=3)
    
async def on_critical():
    """Clear LLM cache, drop old telemetry."""
    ollama.clear_cache()
    telemetry_buffer.trim(keep_last=50)
    
async def on_emergency():
    """Emergency: Request immediate RTL."""
    await safety_monitor.emergency_rtl("Memory emergency")

memory_guard.on_warning(on_warning)
memory_guard.on_critical(on_critical)
memory_guard.on_emergency(on_emergency)

await memory_guard.start_monitoring(check_interval_seconds=5.0)
```

---

## 4. Shared State Patterns for Drone Control

### 4.1 Lock-Free Shared State with `asyncio.Lock`

```python
import asyncio
from dataclasses import dataclass, field
from typing import Optional
import copy

@dataclass
class DroneState:
    """
    Thread-safe shared state container.
    
    Pattern: Immutable snapshots for readers, locked updates for writers.
    """
    timestamp: float = field(default_factory=time.monotonic)
    position_ned: Optional[tuple[float, float, float]] = None  # North, East, Down
    velocity_ned: Optional[tuple[float, float, float]] = None
    attitude: Optional[tuple[float, float, float]] = None  # Roll, Pitch, Yaw
    battery_percent: float = 0.0
    flight_mode: str = "unknown"
    armed: bool = False
    in_air: bool = False
    gps_satellites: int = 0
    ekf_status: str = "unknown"

class ThreadSafeStateManager:
    """
    Manages shared drone state with proper synchronization.
    
    - Writers acquire lock
    - Readers get immutable snapshot (no lock needed for read)
    - Atomic updates prevent partial state reads
    """
    
    def __init__(self):
        self._state = DroneState()
        self._lock = asyncio.Lock()
        self._update_count = 0
        
    async def update(self, **kwargs):
        """
        Atomic update of state fields.
        
        Usage:
            await state_manager.update(
                position_ned=(1.0, 2.0, -3.0),
                battery_percent=85.0
            )
        """
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._state.timestamp = time.monotonic()
            self._update_count += 1
            
    def get_snapshot(self) -> DroneState:
        """
        Get immutable copy of current state.
        
        No lock needed - we return a copy, so caller gets consistent view.
        """
        return copy.deepcopy(self._state)
        
    def get_fast_read(self) -> DroneState:
        """
        Fast read without copy - use only if you accept potential inconsistency.
        
        Safe for: logging, display, non-critical checks
        Unsafe for: flight decisions, safety checks
        """
        return copy.copy(self._state)  # Shallow copy is faster

# Specialized for heartbeat/LLM coordination

class SharedSetpointManager:
    """
    Coordinates between LLM decision loop (1-2 Hz) and heartbeat (20 Hz).
    
    Pattern: LLM publishes targets; heartbeat streams interpolated setpoints.
    """
    
    def __init__(self):
        self._current_target: Optional[dict] = None
        self._target_timestamp: float = 0.0
        self._lock = asyncio.Lock()
        self._cv = asyncio.Condition(self._lock)  # For "wait for new target"
        
    async def set_target(
        self,
        north_m: float,
        east_m: float,
        down_m: float,
        yaw_deg: Optional[float] = None,
        speed_ms: float = 5.0
    ):
        """
        LLM calls this to set new target position.
        
        Thread-safe: can be called from any task.
        """
        async with self._lock:
            self._current_target = {
                'north': north_m,
                'east': east_m,
                'down': down_m,
                'yaw': yaw_deg,
                'speed': speed_ms,
                'set_time': time.monotonic()
            }
            self._target_timestamp = time.monotonic()
            self._cv.notify_all()  # Wake up any waiting heartbeat tasks
            
    async def get_current_target(self) -> Optional[dict]:
        """Heartbeat task calls this to get latest target."""
        async with self._lock:
            return copy.copy(self._current_target) if self._current_target else None
            
    async def wait_for_target(self, timeout: float = 30.0) -> Optional[dict]:
        """
        Block until a target is set or timeout.
        
        Useful for: initial takeoff, mission start synchronization.
        """
        async with self._cv:
            try:
                await asyncio.wait_for(
                    self._cv.wait_for(lambda: self._current_target is not None),
                    timeout=timeout
                )
                return copy.copy(self._current_target)
            except asyncio.TimeoutError:
                return None
```

### 4.2 Async Queue Patterns for Command Pipeline

```python
import asyncio
from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Optional

class CommandPriority(Enum):
    """Priority levels for command queue."""
    EMERGENCY = 0    # Stop, RTL, land now
    SAFETY = 1       # Speed limit, geofence response
    MISSION = 2      # Goto, orbit, follow
    TELEMETRY = 3    # Status requests, logging

@dataclass(order=True)
class DroneCommand:
    """Priority queue entry for commands."""
    priority: int
    seq: int  # Tie-breaker for FIFO
    command_type: str
    payload: dict
    timeout_seconds: float = 10.0
    requires_confirmation: bool = False
    
class CommandPipeline:
    """
    Priority command queue with flow control and backpressure.
    
    Pattern: Producer (LLM/Vision/Safety) -> Queue -> Consumer (MAVSDK executor)
    """
    
    def __init__(self, max_queue_size: int = 100):
        self._queue: asyncio.PriorityQueue[DroneCommand] = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self._seq = 0
        self._emergency_event = asyncio.Event()  # Set when emergency in queue
        self._processing = False
        
    async def submit(
        self,
        command_type: str,
        payload: dict,
        priority: CommandPriority = CommandPriority.MISSION,
        timeout_seconds: float = 10.0,
        requires_confirmation: bool = False
    ) -> bool:
        """
        Submit command to pipeline. Returns False if queue full (backpressure).
        
        Never blocks - caller handles backpressure appropriately.
        """
        try:
            self._seq += 1
            cmd = DroneCommand(
                priority=priority.value,
                seq=self._seq,
                command_type=command_type,
                payload=payload,
                timeout_seconds=timeout_seconds,
                requires_confirmation=requires_confirmation
            )
            self._queue.put_nowait(cmd)
            
            if priority == CommandPriority.EMERGENCY:
                self._emergency_event.set()
                
            return True
        except asyncio.QueueFull:
            print(f"WARNING: Command pipeline full, dropping {command_type}")
            return False
            
    async def get_next(self) -> Optional[DroneCommand]:
        """
        Get next command for execution. Blocks until available.
        
        Consumer (command executor) calls this.
        """
        try:
            cmd = await self._queue.get()
            
            # Clear emergency event if no more emergencies
            if cmd.priority == CommandPriority.EMERGENCY.value:
                # Check if more emergencies pending
                temp_list = []
                has_more_emergencies = False
                while not self._queue.empty():
                    item = self._queue.get_nowait()
                    temp_list.append(item)
                    if item.priority == CommandPriority.EMERGENCY.value:
                        has_more_emergencies = True
                        
                # Restore items
                for item in temp_list:
                    self._queue.put_nowait(item)
                    
                if not has_more_emergencies:
                    self._emergency_event.clear()
                    
            return cmd
        except asyncio.CancelledError:
            raise
            
    def has_emergency(self) -> bool:
        """Fast check for pending emergency commands."""
        return self._emergency_event.is_set()
        
    def size(self) -> int:
        """Current queue depth."""
        return self._queue.qsize()

# Command executor with priority awareness

class CommandExecutor:
    """
    Execute commands from pipeline with proper error handling.
    
    Runs as dedicated task; never blocks other orchestrator functions.
    """
    
    def __init__(self, pipeline: CommandPipeline, drone):
        self.pipeline = pipeline
        self.drone = drone
        self._task: Optional[asyncio.Task] = None
        self._current_cmd: Optional[DroneCommand] = None
        self._stats = {'executed': 0, 'failed': 0, 'timeout': 0}
        
    async def start(self):
        """Start command execution loop."""
        self._task = asyncio.create_task(
            self._execution_loop(),
            name="command_executor"
        )
        
    async def stop(self):
        """Graceful shutdown."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    async def _execution_loop(self):
        """Main execution loop - runs forever until cancelled."""
        while True:
            try:
                # Wait for next command (blocks here)
                cmd = await self.pipeline.get_next()
                self._current_cmd = cmd
                
                # Execute with timeout
                try:
                    await asyncio.wait_for(
                        self._execute_command(cmd),
                        timeout=cmd.timeout_seconds
                    )
                    self._stats['executed'] += 1
                except asyncio.TimeoutError:
                    print(f"Command {cmd.command_type} timed out")
                    self._stats['timeout'] += 1
                    await self._handle_timeout(cmd)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Command execution error: {e}")
                self._stats['failed'] += 1
                
    async def _execute_command(self, cmd: DroneCommand):
        """Dispatch to appropriate handler."""
        handlers = {
            'goto': self._handle_goto,
            'land': self._handle_land,
            'rtl': self._handle_rtl,
            'set_speed': self._handle_set_speed,
            'emergency_stop': self._handle_emergency_stop,
        }
        
        handler = handlers.get(cmd.command_type)
        if handler:
            await handler(cmd.payload)
        else:
            print(f"Unknown command type: {cmd.command_type}")
            
    async def _handle_emergency_stop(self, payload: dict):
        """Emergency stop - immediate velocity zero."""
        await self.drone.offboard.set_velocity_ned(
            velocity_ned_m_s=(0.0, 0.0, 0.0)
        )
        
    async def _handle_timeout(self, cmd: DroneCommand):
        """Handle command timeout - may escalate to emergency."""
        if cmd.priority == CommandPriority.EMERGENCY.value:
            # Emergency command timed out - this is critical
            print("CRITICAL: Emergency command timed out!")
            # Trigger higher-level failsafe
```

---

## 5. Cancellation and Cleanup on Shutdown

### 5.1 Graceful Shutdown Pattern

```python
import asyncio
from typing import Optional, Callable
import signal

class GracefulShutdownManager:
    """
    Coordinate graceful shutdown across all tasks.
    
    Ensures:
    1. Emergency tasks complete first (RTL, land)
    2. Ongoing commands complete or timeout
    3. Resources are released
    4. No zombie tasks left running
    """
    
    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        self._cleanup_handlers: list[Callable] = []
        self._emergency_handler: Optional[Callable] = None
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False
        
    def register_task(self, task: asyncio.Task) -> asyncio.Task:
        """Register a task for lifecycle management."""
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task
        
    def on_cleanup(self, handler: Callable):
        """Register cleanup handler called during shutdown."""
        self._cleanup_handlers.append(handler)
        
    def on_emergency(self, handler: Callable):
        """Set emergency handler for critical shutdown."""
        self._emergency_handler = handler
        
    async def initiate_shutdown(self, emergency: bool = False, timeout: float = 10.0):
        """
        Initiate graceful shutdown sequence.
        
        Args:
            emergency: If True, skip graceful steps, execute emergency handler
            timeout: Maximum time to wait for cleanup
        """
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        
        print(f"Initiating {'emergency' if emergency else 'graceful'} shutdown...")
        
        if emergency and self._emergency_handler:
            try:
                await asyncio.wait_for(self._emergency_handler(), timeout=5.0)
            except Exception as e:
                print(f"Emergency handler failed: {e}")
        
        # Cancel all non-essential tasks
        essential_tasks = {'heartbeat', 'safety_monitor', 'emergency_handler'}
        
        for task in list(self._tasks):
            task_name = task.get_name()
            if task_name not in essential_tasks and not task.done():
                print(f"Cancelling task: {task_name}")
                task.cancel()
                
        # Wait for cancellation to propagate
        if self._tasks:
            await asyncio.sleep(0.5)
            
        # Run cleanup handlers
        for handler in self._cleanup_handlers:
            try:
                await asyncio.wait_for(handler(), timeout=2.0)
            except Exception as e:
                print(f"Cleanup handler failed: {e}")
                
        # Final wait for remaining tasks
        remaining = [t for t in self._tasks if not t.done()]
        if remaining:
            print(f"Waiting for {len(remaining)} tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*remaining, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                print("WARNING: Some tasks did not terminate gracefully")
                for t in remaining:
                    if not t.done():
                        print(f"  - Force cancelling: {t.get_name()}")
                        t.cancel()
                        
        self._shutdown_event.set()
        print("Shutdown complete")
        
    async def wait_for_shutdown(self):
        """Block until shutdown is complete."""
        await self._shutdown_event.wait()

# Signal handler integration

async def setup_signal_handlers(shutdown_manager: GracefulShutdownManager):
    """Set up UNIX signal handlers for graceful shutdown."""
    
    loop = asyncio.get_running_loop()
    
    def handle_signal(sig):
        print(f"Received signal {sig}")
        asyncio.create_task(shutdown_manager.initiate_shutdown(emergency=False))
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

# Task wrapper with automatic registration

def managed_task(coro, name: str, shutdown_manager: GracefulShutdownManager) -> asyncio.Task:
    """
    Create a task that is automatically managed for shutdown.
    
    Usage:
        heartbeat_task = managed_task(heartbeat_loop(), "heartbeat", shutdown_mgr)
    """
    task = asyncio.create_task(coro, name=name)
    shutdown_manager.register_task(task)
    return task
```

### 5.2 Context Manager Pattern for Cleanup

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

@asynccontextmanager
async def managed_heartbeat(drone, shutdown_manager) -> AsyncGenerator[asyncio.Task, None]:
    """
    Context manager for heartbeat task lifecycle.
    
    Ensures heartbeat continues until explicitly released, even during exceptions.
    """
    task = asyncio.create_task(heartbeat_loop(drone), name="heartbeat")
    shutdown_manager.register_task(task)
    
    try:
        yield task
    finally:
        # Only cancel if we're not in emergency shutdown
        # (emergency shutdown handles critical tasks specially)
        if not shutdown_manager._is_shutting_down:
            print("Stopping heartbeat...")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

@asynccontextmanager
async def managed_mavsdk_connection(connection_string: str) -> AsyncGenerator[Any, None]:
    """
    Context manager for MAVSDK connection with automatic cleanup.
    """
    drone = System()
    
    try:
        await drone.connect(system_address=connection_string)
        
        # Wait for connection with timeout
        async for state in drone.core.connection_state():
            if state.is_connected:
                break
        else:
            raise ConnectionError("Failed to connect to PX4")
            
        yield drone
        
    finally:
        print("Disconnecting from PX4...")
        # MAVSDK doesn't have explicit disconnect, but we can
        # ensure offboard is stopped before exiting
        try:
            await drone.offboard.stop()
        except:
            pass
```

---

## 6. Exception Propagation in Task Groups

### 6.1 Task Group Error Handling

```python
import asyncio
from typing import Optional

class ResilientTaskGroup:
    """
    TaskGroup variant that doesn't fail fast on individual task errors.
    
    Standard asyncio.TaskGroup cancels all tasks when one fails.
    For drone control, we need: "one fails, others continue with graceful degradation".
    """
    
    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        self._exceptions: list[tuple[str, Exception]] = []
        
    async def create_task(self, coro, name: str) -> asyncio.Task:
        """Create a task with automatic error handling."""
        task = asyncio.create_task(
            self._wrapped_coro(coro, name),
            name=name
        )
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return task
        
    async def _wrapped_coro(self, coro, name: str):
        """Wrapper that catches and logs exceptions without propagating."""
        try:
            return await coro
        except asyncio.CancelledError:
            raise  # Always propagate cancellation
        except Exception as e:
            self._exceptions.append((name, e))
            print(f"Task {name} failed (continuing): {e}")
            # Don't re-raise - let other tasks continue
            
    def _on_task_done(self, task: asyncio.Task):
        """Callback when task completes."""
        self._tasks.discard(task)
        
    async def gather(self, return_exceptions: bool = True):
        """Wait for all tasks with optional exception return."""
        if not self._tasks:
            return []
            
        results = await asyncio.gather(
            *self._tasks,
            return_exceptions=return_exceptions
        )
        return results
        
    async def wait_for_essential(self, essential_names: set[str], timeout: float = 5.0):
        """
        Wait for essential tasks, with fast-fail if any essential task errors.
        
        Non-essential tasks can fail without affecting the group.
        """
        essential_tasks = {
            t for t in self._tasks
            if t.get_name() in essential_names
        }
        
        done, pending = await asyncio.wait(
            essential_tasks,
            timeout=timeout,
            return_when=asyncio.FIRST_EXCEPTION
        )
        
        # Check if any essential task failed
        for task in done:
            if task.exception():
                raise task.exception()
                
        return done, pending

# Usage with essential vs non-essential tasks

async def run_drone_orchestrator():
    """Main orchestrator using resilient task group."""
    
    group = ResilientTaskGroup()
    
    # Essential tasks - if these fail, we must abort
    await group.create_task(heartbeat_loop(), "heartbeat")
    await group.create_task(safety_monitor_loop(), "safety_monitor")
    
    # Non-essential tasks - can fail gracefully
    await group.create_task(vision_pipeline_loop(), "vision")
    await group.create_task(llm_orchestrator_loop(), "llm")
    await group.create_task(telemetry_logger_loop(), "logger")
    
    # Wait forever, but fail fast if essential tasks die
    while True:
        try:
            await group.wait_for_essential(
                essential_names={"heartbeat", "safety_monitor"},
                timeout=1.0
            )
        except Exception as e:
            print(f"Essential task failed: {e}")
            await initiate_emergency_rtl()
            break
```

### 6.2 Exception Hierarchy for Drone Operations

```python
class DroneException(Exception):
    """Base class for all drone-related exceptions."""
    pass

class SafetyCriticalError(DroneException):
    """
    Exception requiring immediate safety response.
    
    These are never suppressed - they propagate to the safety monitor.
    """
    def __init__(self, message: str, auto_action: str = "emergency_stop"):
        super().__init__(message)
        self.auto_action = auto_action

class HeartbeatTimeoutError(SafetyCriticalError):
    """Critical: MAVSDK heartbeat not acknowledged."""
    def __init__(self, last_heartbeat_ms: float):
        super().__init__(
            f"Heartbeat timeout (last: {last_heartbeat_ms}ms ago)",
            auto_action="emergency_land"
        )

class GeofenceViolationError(SafetyCriticalError):
    """Critical: Drone outside permitted flight area."""
    def __init__(self, position: tuple, boundary: str):
        super().__init__(
            f"Geofence violation: {position} outside {boundary}",
            auto_action="emergency_rtl"
        )

class RecoverableError(DroneException):
    """
    Exception that can be recovered from without aborting mission.
    
    These are logged and retried, but don't stop other tasks.
    """
    pass

class VisionPipelineError(RecoverableError):
    """YOLO or tracker failed on a frame - can retry next frame."""
    pass

class LLMCommunicationError(RecoverableError):
    """LLM API call failed - can retry with backoff."""
    pass

class TelemetryStaleError(RecoverableError):
    """Telemetry data is old - may be transient network issue."""
    pass

# Exception handling in main loop

async def resilient_task_wrapper(coro, name: str, error_classifier):
    """
    Wrapper that classifies exceptions and responds appropriately.
    
    SafetyCriticalError -> Propagate to trigger failsafe
    RecoverableError -> Log, retry with backoff
    Other -> Log, continue
    """
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            return await coro()
        except SafetyCriticalError as e:
            # Never suppress - propagate to trigger emergency response
            print(f"SAFETY CRITICAL in {name}: {e}")
            await safety_monitor.trigger_action(e.auto_action)
            raise  # Continue propagating for full shutdown
            
        except RecoverableError as e:
            retry_count += 1
            backoff = min(2 ** retry_count, 30)  # Exponential backoff, max 30s
            print(f"Recoverable error in {name} (retry {retry_count}/{max_retries}): {e}")
            await asyncio.sleep(backoff)
            
        except asyncio.CancelledError:
            raise  # Always propagate cancellation
            
        except Exception as e:
            # Unexpected error - log extensively for post-mortem
            print(f"UNEXPECTED in {name}: {type(e).__name__}: {e}")
            # In production, send to error tracking service
            # For now, continue running but degrade functionality
            await asyncio.sleep(5)  # Brief pause before retry
            retry_count += 1
    
    print(f"Max retries exceeded for {name}, task failing")
    raise RuntimeError(f"Task {name} exceeded max retries")
```

---

## 7. Task Watchdog Patterns

### 7.1 Stuck Coroutine Detection

```python
import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Callable

@dataclass
class WatchdogConfig:
    """Configuration for task health monitoring."""
    name: str
    max_heartbeat_interval_seconds: float
    warning_threshold: float = 0.8  # Warn at 80% of max interval

class TaskWatchdog:
    """
    Detect stuck or dead tasks by monitoring heartbeat timestamps.
    
    Pattern: Each critical task periodically calls heartbeat().
    Watchdog monitors and triggers alerts if heartbeats stop.
    """
    
    def __init__(self, check_interval_seconds: float = 1.0):
        self._monitors: dict[str, dict] = {}
        self._check_interval = check_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._alert_handlers: list[Callable[[str, float], None]] = []
        
    def register_monitor(self, config: WatchdogConfig):
        """Register a task to be monitored."""
        self._monitors[config.name] = {
            'config': config,
            'last_heartbeat': time.monotonic(),
            'status': 'healthy'
        }
        
    def heartbeat(self, task_name: str):
        """Call this periodically from monitored tasks."""
        if task_name in self._monitors:
            self._monitors[task_name]['last_heartbeat'] = time.monotonic()
            self._monitors[task_name]['status'] = 'healthy'
            
    def on_alert(self, handler: Callable[[str, float], None]):
        """Register handler called when task appears stuck."""
        self._alert_handlers.append(handler)
        
    async def start(self):
        """Start watchdog monitoring loop."""
        self._task = asyncio.create_task(self._monitor_loop(), name="watchdog")
        
    async def stop(self):
        """Stop watchdog."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    async def _monitor_loop(self):
        """Background monitoring."""
        while True:
            now = time.monotonic()
            
            for name, monitor in self._monitors.items():
                config = monitor['config']
                elapsed = now - monitor['last_heartbeat']
                
                if elapsed > config.max_heartbeat_interval_seconds:
                    # Task is stuck!
                    monitor['status'] = 'stuck'
                    for handler in self._alert_handlers:
                        await handler(name, elapsed)
                        
                elif elapsed > config.max_heartbeat_interval_seconds * config.warning_threshold:
                    # Warning: task is slow
                    if monitor['status'] != 'slow':
                        monitor['status'] = 'slow'
                        print(f"WARNING: Task {name} is slow ({elapsed:.1f}s since heartbeat)")
                        
            await asyncio.sleep(self._check_interval)

# Integrated example

async def heartbeat_task(watchdog: TaskWatchdog):
    """MAVSDK heartbeat with watchdog integration."""
    # Register with 100ms max interval (20Hz = 50ms, allow 2x margin)
    watchdog.register_monitor(WatchdogConfig(
        name="mavsdk_heartbeat",
        max_heartbeat_interval_seconds=0.1
    ))
    
    while True:
        await send_mavsdk_setpoint()
        watchdog.heartbeat("mavsdk_heartbeat")
        await asyncio.sleep(0.05)  # 20Hz

async def vision_task(watchdog: TaskWatchdog):
    """Vision pipeline with watchdog."""
    # Vision can be slower - 200ms max (5Hz min)
    watchdog.register_monitor(WatchdogConfig(
        name="vision_pipeline",
        max_heartbeat_interval_seconds=0.2
    ))
    
    while True:
        frame = await get_frame()
        detections = await run_yolo(frame)  # May take 20-40ms
        update_tracker(detections)
        watchdog.heartbeat("vision_pipeline")
        await asyncio.sleep(0.033)  # ~30 FPS capture

# Alert handler

async def on_watchdog_alert(task_name: str, elapsed_seconds: float):
    """Handle stuck task detection."""
    print(f"WATCHDOG ALERT: Task {task_name} stuck for {elapsed_seconds:.1f}s")
    
    if task_name == "mavsdk_heartbeat":
        # CRITICAL: Heartbeat stopped - trigger failsafe
        await safety_monitor.emergency_land("Heartbeat watchdog timeout")
    elif task_name == "vision_pipeline":
        # Vision failed - fly "blind" with position hold
        await command_pipeline.submit(
            command_type="hold",
            payload={"reason": "vision_watchdog_timeout"},
            priority=CommandPriority.SAFETY
        )
    # Other tasks can be restarted
```

### 7.2 Graceful Degradation When Tasks Fail

```python
from enum import Enum, auto
from typing import Optional
import asyncio

class SystemMode(Enum):
    """Flight capability levels - degrade gracefully."""
    FULL = auto()           # All systems operational
    DEGRADED_VISION = auto()  # Vision failed, GPS/position still works
    DEGRADED_LLM = auto()     # LLM offline, RC/manual control required
    POSITION_HOLD = auto()    # Only position hold + manual control
    EMERGENCY = auto()        # Emergency RTL or land

class GracefulDegradationManager:
    """
    Manage system capability degradation when components fail.
    
    Never fails completely - always maintains safe flight capability.
    """
    
    def __init__(self):
        self.mode = SystemMode.FULL
        self._component_status: dict[str, bool] = {
            'heartbeat': True,
            'vision': True,
            'llm': True,
            'telemetry': True,
            'rc_link': True
        }
        self._mode_listeners: list[Callable[[SystemMode, SystemMode], None]] = []
        
    def on_mode_change(self, listener: Callable[[SystemMode, SystemMode], None]):
        """Register listener for mode changes."""
        self._mode_listeners.append(listener)
        
    def mark_component_failed(self, component: str) -> SystemMode:
        """
        Mark a component as failed, potentially degrading system mode.
        
        Returns new system mode.
        """
        old_mode = self.mode
        self._component_status[component] = False
        
        # Determine new mode based on what's working
        if not self._component_status['heartbeat']:
            new_mode = SystemMode.EMERGENCY
        elif not self._component_status['rc_link']:
            new_mode = SystemMode.EMERGENCY  # No RC = can't recover
        elif not self._component_status['vision'] and not self._component_status['llm']:
            new_mode = SystemMode.POSITION_HOLD
        elif not self._component_status['llm']:
            new_mode = SystemMode.DEGRADED_LLM
        elif not self._component_status['vision']:
            new_mode = SystemMode.DEGRADED_VISION
        else:
            new_mode = SystemMode.FULL
            
        if new_mode != old_mode:
            print(f"MODE CHANGE: {old_mode.name} -> {new_mode.name}")
            self.mode = new_mode
            
            # Notify listeners
            for listener in self._mode_listeners:
                asyncio.create_task(listener(old_mode, new_mode))
                
        return new_mode
        
    def get_capabilities(self) -> dict[str, bool]:
        """Get available capabilities in current mode."""
        capabilities = {
            'autonomous_flight': self.mode in (SystemMode.FULL, SystemMode.DEGRADED_VISION),
            'vision_guidance': self.mode in (SystemMode.FULL, SystemMode.DEGRADED_LLM),
            'llm_decisions': self.mode == SystemMode.FULL,
            'manual_control': self.mode != SystemMode.EMERGENCY,
            'position_hold': self.mode in (SystemMode.FULL, SystemMode.DEGRADED_VISION, 
                                           SystemMode.DEGRADED_LLM, SystemMode.POSITION_HOLD),
            'emergency_rtl': True  # Always available
        }
        return capabilities

# Usage in orchestrator

degradation_mgr = GracefulDegradationManager()

async def on_mode_change(old_mode: SystemMode, new_mode: SystemMode):
    """React to capability degradation."""
    
    if new_mode == SystemMode.DEGRADED_VISION:
        # Vision failed - switch to GPS-only navigation
        await llm_interface.notify("Vision system offline. Switching to GPS navigation.")
        # Reduce LLM dependency on visual data
        state_string_generator.disable_vision_features()
        
    elif new_mode == SystemMode.DEGRADED_LLM:
        # LLM failed - require operator commands
        await command_pipeline.submit(
            command_type="hold",
            payload={"reason": "llm_degraded"},
            priority=CommandPriority.SAFETY
        )
        await audio.alert("LLM offline. Manual control required.")
        
    elif new_mode == SystemMode.POSITION_HOLD:
        # Minimal capability - just hold position
        await command_pipeline.submit(
            command_type="position_hold",
            payload={"indefinite": True},
            priority=CommandPriority.SAFETY
        )
        await audio.alert("Position hold only. Land immediately.")
        
    elif new_mode == SystemMode.EMERGENCY:
        # Full emergency - RTL
        await safety_monitor.emergency_rtl("System mode emergency")

degradation_mgr.on_mode_change(on_mode_change)

# In task failure handlers

try:
    await vision_pipeline_loop()
except Exception as e:
    print(f"Vision pipeline failed: {e}")
    new_mode = degradation_mgr.mark_component_failed('vision')
    # Task ends, but system continues in degraded mode
```

---

## 8. Restart Strategies Without Process Exit

### 8.1 Task Restart Pattern

```python
import asyncio
from typing import Callable, Optional
from dataclasses import dataclass

@dataclass
class RestartPolicy:
    """Configuration for automatic task restart."""
    max_restarts: int = 5
    restart_window_seconds: float = 60.0  # Reset counter after this time
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    reset_on_success_seconds: float = 10.0  # Consider stable after this time

class ResilientTaskRunner:
    """
    Run tasks with automatic restart on failure.
    
    Never exits process - keeps critical functions running.
    """
    
    def __init__(self, policy: RestartPolicy = None):
        self.policy = policy or RestartPolicy()
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._restart_counts: dict[str, list[float]] = {}  # Timestamps of restarts
        
    async def run(
        self,
        name: str,
        coro_factory: Callable[[], asyncio.Coroutine],
        is_critical: bool = False
    ):
        """
        Run a coroutine, restarting it if it fails.
        
        Args:
            name: Task identifier
            coro_factory: Function that returns a fresh coroutine
            is_critical: If True, escalate backoff on repeated failures
        """
        while True:
            try:
                # Check restart rate
                if not self._can_restart(name):
                    wait_time = self.policy.restart_window_seconds
                    print(f"Task {name}: Restart rate exceeded, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    self._restart_counts[name] = []
                    
                # Calculate backoff
                backoff = self._calculate_backoff(name)
                if backoff > 0:
                    print(f"Task {name}: Backing off for {backoff}s")
                    await asyncio.sleep(backoff)
                
                # Record restart
                self._restart_counts.setdefault(name, []).append(time.monotonic())
                
                # Create and run task
                print(f"Task {name}: Starting (attempt {len(self._restart_counts[name])})")
                coro = coro_factory()
                task = asyncio.create_task(coro, name=name)
                self._running_tasks[name] = task
                
                await task
                
                # Clean exit - task completed naturally
                print(f"Task {name}: Completed normally")
                break
                
            except asyncio.CancelledError:
                # Propagate cancellation for graceful shutdown
                print(f"Task {name}: Cancelled")
                raise
                
            except Exception as e:
                print(f"Task {name}: Failed with {type(e).__name__}: {e}")
                
                if is_critical and not self._can_restart(name):
                    # Critical task failing repeatedly - escalate
                    print(f"CRITICAL: Task {name} failing repeatedly!")
                    await self._handle_critical_failure(name, e)
                    
            finally:
                self._running_tasks.pop(name, None)
                
    def _can_restart(self, name: str) -> bool:
        """Check if restart is allowed under current policy."""
        restarts = self._restart_counts.get(name, [])
        
        # Clean old restarts outside the window
        now = time.monotonic()
        window_start = now - self.policy.restart_window_seconds
        recent_restarts = [t for t in restarts if t > window_start]
        self._restart_counts[name] = recent_restarts
        
        return len(recent_restarts) < self.policy.max_restarts
        
    def _calculate_backoff(self, name: str) -> float:
        """Calculate exponential backoff based on restart count."""
        restarts = len(self._restart_counts.get(name, []))
        
        if restarts == 0:
            return 0
            
        backoff = self.policy.backoff_base_seconds * (2 ** (restarts - 1))
        return min(backoff, self.policy.backoff_max_seconds)
        
    async def _handle_critical_failure(self, name: str, error: Exception):
        """Handle repeated failures of a critical task."""
        # This is where you'd notify operators, log extensively, etc.
        # For now, just continue trying but with longer delays
        pass
        
    async def stop(self, name: Optional[str] = None):
        """Stop a specific task or all tasks."""
        if name:
            task = self._running_tasks.get(name)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        else:
            # Stop all
            tasks = list(self._running_tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

# Usage

runner = ResilientTaskRunner(
    policy=RestartPolicy(
        max_restarts=5,
        restart_window_seconds=60.0,
        backoff_base_seconds=0.5,
        backoff_max_seconds=10.0
    )
)

# Start critical heartbeat with automatic restart
async def heartbeat_factory():
    """Factory that creates a fresh heartbeat coroutine."""
    return heartbeat_loop(drone)

asyncio.create_task(
    runner.run("heartbeat", heartbeat_factory, is_critical=True),
    name="heartbeat_supervisor"
)

# Start non-critical LLM with restart
asyncio.create_task(
    runner.run("llm", lambda: llm_orchestrator_loop(), is_critical=False),
    name="llm_supervisor"
)
```

### 8.2 Hot-Reload Pattern for Configuration

```python
import asyncio
from typing import Callable, Any
import json
from pathlib import Path

class HotReloader:
    """
    Support runtime configuration updates without process restart.
    
    Pattern: Watch config file, reload parameters, signal tasks to adapt.
    """
    
    def __init__(self, config_path: str, check_interval_seconds: float = 5.0):
        self.config_path = Path(config_path)
        self.check_interval = check_interval_seconds
        self._last_mtime: float = 0
        self._config: dict = {}
        self._listeners: list[Callable[[dict], None]] = []
        self._task: Optional[asyncio.Task] = None
        
    def on_reload(self, listener: Callable[[dict], None]):
        """Register listener called when config changes."""
        self._listeners.append(listener)
        
    async def start(self):
        """Start config file monitoring."""
        # Load initial config
        await self._load_config()
        self._task = asyncio.create_task(self._watch_loop(), name="config_watcher")
        
    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    async def _watch_loop(self):
        """Background loop watching for file changes."""
        while True:
            try:
                if self.config_path.exists():
                    mtime = self.config_path.stat().st_mtime
                    
                    if mtime > self._last_mtime:
                        self._last_mtime = mtime
                        await self._load_config()
                        
            except Exception as e:
                print(f"Config watch error: {e}")
                
            await asyncio.sleep(self.check_interval)
            
    async def _load_config(self):
        """Load and validate config, notify listeners."""
        try:
            with open(self.config_path) as f:
                new_config = json.load(f)
                
            # Validate required fields
            self._validate_config(new_config)
            
            # Update and notify
            old_config = self._config
            self._config = new_config
            
            print(f"Config reloaded: {self.config_path}")
            
            for listener in self._listeners:
                try:
                    await listener(new_config)
                except Exception as e:
                    print(f"Config listener failed: {e}")
                    
        except Exception as e:
            print(f"Config reload failed: {e}")
            # Keep old config if reload fails
            
    def _validate_config(self, config: dict):
        """Validate config structure. Raises on invalid config."""
        required = {'heartbeat_hz', 'vision_resolution', 'llm_model'}
        missing = required - config.keys()
        if missing:
            raise ValueError(f"Missing config keys: {missing}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get current config value."""
        return self._config.get(key, default)

# Usage

reloader = HotReloader("drone_config.json", check_interval_seconds=5.0)

async def on_config_change(new_config: dict):
    """Adapt to new configuration without restart."""
    
    # Update heartbeat frequency
    new_hz = new_config.get('heartbeat_hz', 20)
    heartbeat_task.set_frequency(new_hz)
    
    # Update vision resolution
    new_resolution = new_config.get('vision_resolution', 416)
    vision_pipeline.set_resolution(new_resolution)
    
    # Update LLM model
    new_model = new_config.get('llm_model', 'llama3.1:8b')
    await llm_interface.switch_model(new_model)  # Hot-swap model
    
reloader.on_reload(on_config_change)
await reloader.start()
```

---

## 9. Complete Orchestrator Template

```python
#!/usr/bin/env python3
"""
Project Avatar Drone Orchestrator

Safety-critical asyncio patterns implementation.
"""

import asyncio
import signal
import sys
from dataclasses import dataclass
from typing import Optional
import time

# Import patterns from above
# from priority_scheduler import PriorityScheduler, PriorityTask
# from compute_isolator import ComputeIsolator
# from state_manager import ThreadSafeStateManager, SharedSetpointManager
# from command_pipeline import CommandPipeline, CommandPriority
# from task_watchdog import TaskWatchdog, WatchdogConfig
# from graceful_shutdown import GracefulShutdownManager
# from degradation_manager import GracefulDegradationManager, SystemMode
# from resilient_runner import ResilientTaskRunner, RestartPolicy

@dataclass
class DroneConfig:
    """Orchestrator configuration."""
    heartbeat_hz: float = 20.0
    vision_fps: int = 15
    llm_max_latency_seconds: float = 3.0
    safety_monitor_hz: float = 10.0
    command_timeout_seconds: float = 10.0

class DroneOrchestrator:
    """
    Main orchestrator coordinating all drone subsystems.
    
    Design goals:
    - Never block the event loop with CPU/GPU work
    - Critical tasks (heartbeat, safety) always run
    - Graceful degradation when components fail
    - No process restart required for recovery
    """
    
    def __init__(self, config: DroneConfig = None):
        self.config = config or DroneConfig()
        
        # Core systems
        self.shutdown_manager = GracefulShutdownManager()
        self.degradation_manager = GracefulDegradationManager()
        self.task_runner = ResilientTaskRunner(RestartPolicy())
        
        # Compute isolation
        self.compute = ComputeIsolator(max_workers=4)
        
        # State management
        self.state_manager = ThreadSafeStateManager()
        self.setpoint_manager = SharedSetpointManager()
        
        # Command pipeline
        self.command_pipeline = CommandPipeline(max_queue_size=100)
        
        # Watchdog
        self.watchdog = TaskWatchdog(check_interval_seconds=1.0)
        
        # Drone connection
        self.drone: Optional[System] = None
        
    async def initialize(self):
        """Initialize all subsystems."""
        print("Initializing drone orchestrator...")
        
        # Start compute isolator
        await self.compute.start()
        
        # Connect to PX4 via MAVSDK
        self.drone = System()
        await self.drone.connect(system_address="udp://:14540")
        
        # Wait for connection
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                print("Connected to PX4")
                break
                
        # Start watchdog
        await self.watchdog.start()
        
        # Start memory monitoring
        self.memory_guard = MemoryGuard(
            warning_threshold_gb=12.0,
            critical_threshold_gb=14.0,
            absolute_max_gb=15.0
        )
        await self.memory_guard.start_monitoring(check_interval_seconds=5.0)
        
        # Register shutdown handlers
        self.shutdown_manager.on_emergency(self._emergency_shutdown)
        self.shutdown_manager.on_cleanup(self._cleanup)
        
        print("Orchestrator initialized")
        
    async def run(self):
        """Run all subsystems with automatic restart on failure."""
        
        # Critical tasks - restart forever if they fail
        asyncio.create_task(
            self.task_runner.run(
                "heartbeat",
                lambda: self._heartbeat_loop(),
                is_critical=True
            ),
            name="heartbeat_supervisor"
        )
        
        asyncio.create_task(
            self.task_runner.run(
                "safety_monitor",
                lambda: self._safety_monitor_loop(),
                is_critical=True
            ),
            name="safety_supervisor"
        )
        
        # Command executor
        self.command_executor = CommandExecutor(
            self.command_pipeline,
            self.drone
        )
        await self.command_executor.start()
        
        # Non-critical tasks - restart with backoff
        asyncio.create_task(
            self.task_runner.run(
                "vision",
                lambda: self._vision_loop(),
                is_critical=False
            ),
            name="vision_supervisor"
        )
        
        asyncio.create_task(
            self.task_runner.run(
                "llm_orchestrator",
                lambda: self._llm_loop(),
                is_critical=False
            ),
            name="llm_supervisor"
        )
        
        # Register with watchdog
        self.watchdog.on_alert(self._on_watchdog_alert)
        
        # Register with degradation manager
        self.degradation_manager.on_mode_change(self._on_mode_change)
        
        # Block forever (or until shutdown)
        await self.shutdown_manager.wait_for_shutdown()
        
    async def _heartbeat_loop(self):
        """
        Critical: 20Hz MAVSDK offboard heartbeat.
        
        This task must never block. Use PreciseSleeper to maintain exact timing.
        """
        from priority_scheduler import PreciseSleeper
        
        # Register with watchdog (max 100ms between heartbeats)
        self.watchdog.register_monitor(WatchdogConfig(
            name="mavsdk_heartbeat",
            max_heartbeat_interval_seconds=0.1
        ))
        
        sleeper = PreciseSleeper(target_hz=self.config.heartbeat_hz)
        
        while True:
            # Get current target from setpoint manager
            target = await self.setpoint_manager.get_current_target()
            
            if target and self.drone:
                # Interpolate towards target
                current = self.state_manager.get_fast_read().position_ned
                if current:
                    setpoint = self._interpolate_setpoint(current, target)
                    await self.drone.offboard.set_position_ned(setpoint)
                    
            # Heartbeat watchdog
            self.watchdog.heartbeat("mavsdk_heartbeat")
            
            # Precise timing
            await sleeper.sleep()
            
    async def _safety_monitor_loop(self):
        """
        Critical: 10Hz safety monitoring.
        
        Runs independently of LLM; can override any command.
        """
        self.watchdog.register_monitor(WatchdogConfig(
            name="safety_monitor",
            max_heartbeat_interval_seconds=0.2  # 200ms = 5Hz min
        ))
        
        while True:
            state = self.state_manager.get_snapshot()
            
            # Check safety conditions
            checks = [
                self._check_geofence(state),
                self._check_battery(state),
                self._check_ekf_health(state),
                self._check_altitude(state),
            ]
            
            for check_name, is_safe, action in checks:
                if not is_safe:
                    print(f"SAFETY VIOLATION: {check_name}")
                    await self._execute_safety_action(action, state)
                    
            self.watchdog.heartbeat("safety_monitor")
            await asyncio.sleep(0.1)  # 10Hz
            
    async def _vision_loop(self):
        """
        Non-critical: Vision pipeline at 15 FPS.
        
        Runs in compute isolator to prevent blocking event loop.
        """
        self.watchdog.register_monitor(WatchdogConfig(
            name="vision_pipeline",
            max_heartbeat_interval_seconds=0.2  # 200ms = 5Hz min
        ))
        
        while True:
            try:
                # Get frame (async I/O)
                frame = await self._get_video_frame()
                
                # Run YOLO in thread pool (CPU/GPU bound)
                detections = await self.compute.run_cpu_bound(
                    self.yolo_model.predict,
                    frame,
                    timeout_seconds=0.1
                )
                
                # Update tracking (fast, on event loop)
                tracks = self.tracker.update(detections)
                
                # Publish to state manager
                await self.state_manager.update(
                    last_detections=tracks,
                    last_detection_time=time.monotonic()
                )
                
                self.watchdog.heartbeat("vision_pipeline")
                
            except Exception as e:
                print(f"Vision error: {e}")
                # Mark component failed - triggers graceful degradation
                self.degradation_manager.mark_component_failed('vision')
                raise  # Let task runner handle restart
                
            await asyncio.sleep(1.0 / self.config.vision_fps)
            
    async def _llm_loop(self):
        """
        Non-critical: LLM decision loop at ~0.5 Hz.
        
        Variable latency (1.5-2.5s) - isolated from real-time tasks.
        """
        self.watchdog.register_monitor(WatchdogConfig(
            name="llm_orchestrator",
            max_heartbeat_interval_seconds=10.0  # LLM is slow
        ))
        
        while True:
            try:
                # Assemble context
                state = self.state_manager.get_snapshot()
                state_string = self._generate_state_string(state)
                
                # Query LLM (slow, isolated)
                response = await self.compute.run_cpu_bound(
                    self._query_llm,
                    state_string,
                    timeout_seconds=self.config.llm_max_latency_seconds
                )
                
                # Parse and validate tool calls
                commands = self._parse_llm_response(response)
                
                # Submit to command pipeline
                for cmd in commands:
                    await self.command_pipeline.submit(
                        command_type=cmd['type'],
                        payload=cmd['payload'],
                        priority=CommandPriority.MISSION
                    )
                    
                self.watchdog.heartbeat("llm_orchestrator")
                
            except Exception as e:
                print(f"LLM error: {e}")
                self.degradation_manager.mark_component_failed('llm')
                raise
                
    async def _emergency_shutdown(self):
        """Emergency cleanup - stop offboard, trigger failsafe."""
        print("EMERGENCY SHUTDOWN")
        
        if self.drone:
            try:
                await self.drone.offboard.stop()
                await self.drone.action.hold()
            except Exception as e:
                print(f"Emergency shutdown error: {e}")
                
    async def _cleanup(self):
        """Normal cleanup - release resources."""
        print("Cleaning up...")
        
        await self.compute.shutdown()
        await self.watchdog.stop()
        await self.memory_guard.stop()
        
    async def _on_watchdog_alert(self, task_name: str, elapsed: float):
        """Handle stuck task detection."""
        if task_name == "mavsdk_heartbeat":
            # CRITICAL
            await self._emergency_shutdown()
            await self.shutdown_manager.initiate_shutdown(emergency=True)
        elif task_name == "safety_monitor":
            # CRITICAL
            await self._emergency_shutdown()
            await self.shutdown_manager.initiate_shutdown(emergency=True)
        else:
            # Non-critical - degrade gracefully
            component = task_name.replace("_pipeline", "").replace("_orchestrator", "")
            self.degradation_manager.mark_component_failed(component)
            
    async def _on_mode_change(self, old_mode, new_mode):
        """Handle system capability degradation."""
        print(f"System mode: {old_mode.name} -> {new_mode.name}")
        
        if new_mode == SystemMode.EMERGENCY:
            await self._emergency_shutdown()
            
    # Additional helper methods...
    def _interpolate_setpoint(self, current, target):
        """Interpolate between current and target position."""
        # Implementation: smooth trajectory generation
        pass
        
    def _check_geofence(self, state):
        """Check if drone is within geofence."""
        # Implementation: geofence validation
        pass
        
    async def _execute_safety_action(self, action, state):
        """Execute emergency safety action."""
        await self.command_pipeline.submit(
            command_type=action,
            payload={"triggered_by": "safety_monitor"},
            priority=CommandPriority.EMERGENCY
        )

async def main():
    """Entry point."""
    orchestrator = DroneOrchestrator(
        config=DroneConfig(
            heartbeat_hz=20.0,
            vision_fps=15,
            llm_max_latency_seconds=3.0
        )
    )
    
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(
                orchestrator.shutdown_manager.initiate_shutdown()
            )
        )
        
    try:
        await orchestrator.initialize()
        await orchestrator.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        await orchestrator._emergency_shutdown()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 10. Summary: Key Takeaways

### For Real-Time Control:

1. **Never run CPU/GPU work on the event loop** - Always use `run_in_executor()`
2. **Use `PreciseSleeper` for periodic tasks** - Compensates for execution time
3. **Critical tasks get dedicated scheduling** - Heartbeat never yields to LLM tasks
4. **Event loop health is paramount** - Use `loop.call_at()` for time-critical callbacks

### For Shared State:

1. **Readers get immutable snapshots** - `copy.deepcopy()` prevents race conditions
2. **Writers acquire `asyncio.Lock()`** - Short critical sections only
3. **Use `asyncio.Condition` for coordination** - Between heartbeat and setpoint updates
4. **Command queue with priority** - Emergency commands skip the line

### For Safety-Critical Operation:

1. **Watchdog every critical task** - Detect stuck coroutines within 100ms
2. **Graceful degradation** - Vision fails? Fly GPS-only. LLM fails? Manual control.
3. **Never exit process mid-flight** - Automatic restart with exponential backoff
4. **Safety monitor runs independently** - Can override LLM at any time

### For Production Deployment:

1. **Preallocate all buffers** - Frame pools, detection pools, zero GC pressure
2. **Monitor memory continuously** - Trigger defensive actions at 12GB/14GB/15GB
3. **Log extensively** - Black-box recording for crash analysis
4. **Test failure modes** - Simulate WiFi drop, LLM timeout, thermal throttle

---

## References

- Python asyncio documentation (Context7 /python/cpython)
- Project Avatar Performance Optimization Analysis (M3 16GB)
- Project Avatar Architecture Critique (Safety-critical findings)
- PX4 Offboard Control documentation (20Hz requirement)
- MAVSDK-Python async patterns

**Document Version:** 1.0  
**Date:** 2026-04-09  
**Author:** Claude Async Specialist  
**For:** Project Avatar Drone Orchestrator Implementation
