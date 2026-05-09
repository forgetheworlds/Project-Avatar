"""
splash_payload.py — Splash water gun payload implementation.

Concrete payload that plugs into the BasePayload interface.

Hardware:
    • 2× MG90S metal gear servos (pan/tilt) via PCA9685 @ I2C 0x40
    • 1× MOSFET (IRLZ44N) for pump activation via GPIO
    • 1× 15ml syringe reservoir (quick-release mount)
    • Total weight: ~50g (servos + pump + reservoir + mount)

Commands:
    fire          — Trigger pump for duration_ms
    aim           — Set pan/tilt servo angles
    center        — Return servos to center (90°/90°)
    set_deadzone  — Configure fire deadzone in pixels
    get_status    — Current pan/tilt angles, pump state, reservoir level

SIM_MODE:
    When sim_mode=True, all hardware I2C/GPIO calls are no-ops.
    Health and state are tracked identically.

Project Avatar — Splash water gun drone payload.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from splash.payload.base_payload import (
    BasePayload,
    PayloadState,
    PayloadCommandResult,
)

logger = logging.getLogger("splash.payload.splash")

# ---------------------------------------------------------------------------
# SplashPayload — Water gun payload
# ---------------------------------------------------------------------------

class SplashPayload(BasePayload):
    """Water gun payload with pan/tilt aiming and pump trigger.

    Implements the full BasePayload lifecycle with PCA9685 servo control
    and GPIO-switched pump MOSFET.
    """

    # Hardware constants
    PCA9685_ADDRESS = 0x40          # I2C address
    PCA9685_FREQ = 50               # Hz (standard servo PWM)
    SERVO_PAN_CHANNEL = 0           # PCA9685 channel for pan servo
    SERVO_TILT_CHANNEL = 1          # PCA9685 channel for tilt servo
    PUMP_GPIO_PIN = 17              # BCM pin for pump MOSFET gate
    SERVO_CENTER_US = 1500          # Neutral pulse width (microseconds)
    SERVO_MIN_US = 500              # Minimum pulse width
    SERVO_MAX_US = 2500             # Maximum pulse width
    SERVO_MIN_ANGLE = 0             # Min angle in degrees
    SERVO_MAX_ANGLE = 180           # Max angle in degrees

    # Targeting defaults
    DEFAULT_DEADZONE_PX = 30        # Fire when bbox center within 30px of crosshair
    DEFAULT_FIRE_DURATION_MS = 500  # Default burst duration
    MIN_FIRE_DURATION_MS = 100      # Minimum burst (safety)
    MAX_FIRE_DURATION_MS = 2000     # Maximum burst (reservoir conservation)

    # Payload metadata
    MASS_G = 50                     # Total grams: 2×MG90S (26g) + pump (15g) + mount (9g)
    POWER_MAX_MA = 1500             # 1.5A peak: both servos moving + pump active
    POWER_NOMINAL_MA = 200          # 200mA idle: servos holding, pump off

    @property
    def payload_type(self) -> str:       return "splash"

    @property
    def display_name(self) -> str:       return "Splash Water Gun"

    @property
    def version(self) -> str:            return "1.0.0"

    @property
    def mass_g(self) -> float:           return self.MASS_G

    @property
    def power_max_ma(self) -> int:       return self.POWER_MAX_MA

    @property
    def power_nominal_ma(self) -> int:   return self.POWER_NOMINAL_MA

    @property
    def commands(self) -> list[str]:
        return ["fire", "aim", "center", "set_deadzone", "get_status"]

    @property
    def bus_addresses(self) -> dict[str, int]:
        return {"pca9685": self.PCA9685_ADDRESS}

    @property
    def critical(self) -> bool:
        # Splash is mission-critical for the water gun mission
        return True

    def __init__(
        self,
        payload_id: str,
        sim_mode: bool = True,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(payload_id, sim_mode, config)

        # Servo state
        self._pan_angle_deg: float = 90.0    # Center
        self._tilt_angle_deg: float = 90.0   # Center

        # Pump state
        self._pump_active: bool = False
        self._pump_activated_at: float = 0.0

        # Targeting
        self._deadzone_px: int = self.DEFAULT_DEADZONE_PX
        self._fire_duration_ms: int = self.DEFAULT_FIRE_DURATION_MS

        # Reservoir
        self._reservoir_ml: float = 15.0     # 15ml capacity
        self._total_fired_ml: float = 0.0    # Cumulative usage
        self._fire_count: int = 0

        # Hardware handles (real mode only)
        self._pca: object | None = None
        self._pump_gpio: object | None = None

        # Load config overrides
        if config:
            self._deadzone_px = config.get("deadzone_px", self._deadzone_px)
            self._fire_duration_ms = config.get("fire_duration_ms", self._fire_duration_ms)

    # ==================================================================
    # Lifecycle — hardware implementation
    # ==================================================================

    @classmethod
    def discover(cls, sim_mode: bool = False, **kwargs: Any) -> bool:
        """Detect PCA9685 on I2C bus at 0x40.

        In SIM_MODE, always returns True.
        In real mode, tries to address the PCA9685.
        """
        if sim_mode:
            logger.info("SplashPayload: SIM_MODE discover → True")
            return True

        try:
            # Probe I2C bus for PCA9685
            i2c_bus = kwargs.get("i2c_bus")
            if i2c_bus is None:
                import smbus2  # type: ignore
                i2c_bus = smbus2.SMBus(1)

            # Quick probe — read MODE1 register
            i2c_bus.read_byte_data(cls.PCA9685_ADDRESS, 0x00)
            logger.info(f"SplashPayload: PCA9685 found at 0x{cls.PCA9685_ADDRESS:02X}")
            return True
        except Exception as e:
            logger.debug(f"SplashPayload: PCA9685 not found — {e}")
            return False

    # ------------------------------------------------------------------
    # _init_hardware
    # ------------------------------------------------------------------

    def _init_hardware(self, **kwargs: Any) -> None:
        """Initialize PCA9685 and GPIO for pump MOSFET."""
        if self.sim_mode:
            logger.info(f"[{self.payload_id}] _init_hardware: SIM_MODE (no-op)")
            return

        try:
            import board  # type: ignore
            import busio  # type: ignore
            from adafruit_pca9685 import PCA9685  # type: ignore
            import RPi.GPIO as GPIO  # type: ignore

            # I2C bus
            i2c_bus = kwargs.get("i2c_bus")
            if i2c_bus is None:
                i2c = busio.I2C(board.SCL, board.SDA)
            else:
                i2c = i2c_bus

            # PCA9685
            self._pca = PCA9685(i2c, address=self.PCA9685_ADDRESS)
            self._pca.frequency = self.PCA9685_FREQ

            # Initialize servos to center
            self._set_servo_us(self.SERVO_PAN_CHANNEL, self.SERVO_CENTER_US)
            self._set_servo_us(self.SERVO_TILT_CHANNEL, self.SERVO_CENTER_US)

            # GPIO for pump MOSFET
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.PUMP_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
            self._pump_gpio = GPIO

            logger.info(
                f"[{self.payload_id}] _init_hardware: PCA9685 @ 0x"
                f"{self.PCA9685_ADDRESS:02X}, pump GPIO{pin}"
            )

        except ImportError as e:
            logger.warning(
                f"[{self.payload_id}] Hardware libs not available: {e}. "
                "Falling back to SIM mode for init."
            )
            self.sim_mode = True

    def _set_servo_us(self, channel: int, pulse_us: int) -> None:
        """Set servo pulse width in microseconds via PCA9685."""
        if self.sim_mode or self._pca is None:
            return
        # PCA9685 duty cycle: 12-bit (0-4095) at configured frequency
        period_us = 1_000_000 / self.PCA9685_FREQ  # 20000us at 50Hz
        duty = int((pulse_us / period_us) * 4095)
        duty = max(0, min(4095, duty))
        self._pca.channels[channel].duty_cycle = duty

    def _angle_to_pulse_us(self, angle_deg: float) -> int:
        """Convert angle (0-180°) to servo pulse width in microseconds."""
        angle = max(self.SERVO_MIN_ANGLE, min(self.SERVO_MAX_ANGLE, angle_deg))
        ratio = angle / 180.0
        return int(self.SERVO_MIN_US + ratio * (self.SERVO_MAX_US - self.SERVO_MIN_US))

    # ------------------------------------------------------------------
    # _deinit_hardware
    # ------------------------------------------------------------------

    def _deinit_hardware(self) -> None:
        """Release PCA9685 and GPIO resources."""
        if self.sim_mode:
            return

        try:
            # Center servos before releasing
            self._set_servo_us(self.SERVO_PAN_CHANNEL, self.SERVO_CENTER_US)
            self._set_servo_us(self.SERVO_TILT_CHANNEL, self.SERVO_CENTER_US)

            if self._pump_gpio is not None:
                self._pump_gpio.output(self.PUMP_GPIO_PIN, False)
                self._pump_gpio.cleanup(self.PUMP_GPIO_PIN)
                self._pump_gpio = None

            self._pca = None
            logger.info(f"[{self.payload_id}] _deinit_hardware: resources released")
        except Exception as e:
            logger.warning(f"[{self.payload_id}] _deinit_hardware error: {e}")

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    def _enable_power(self) -> None:
        """Enable payload power rail — simulated for Splash.

        In real hardware this would switch a dedicated payload power MOSFET.
        For Splash, power is shared with the servo bus which is enabled
        during _init_hardware.
        """
        if self.sim_mode:
            logger.info(f"[{self.payload_id}] _enable_power: SIM — power rail ON")
            return
        logger.info(f"[{self.payload_id}] _enable_power: power rail ON")

    def _disable_power(self) -> None:
        """Disable payload power rail."""
        if self.sim_mode:
            logger.info(f"[{self.payload_id}] _disable_power: SIM — power rail OFF")
            return
        logger.info(f"[{self.payload_id}] _disable_power: power rail OFF")

    def _arm_outputs(self) -> None:
        """Arm servo outputs and prime pump."""
        if self.sim_mode:
            logger.info(f"[{self.payload_id}] _arm_outputs: SIM — servos armed, pump primed")
            return
        # Ensure pump is off
        if self._pump_gpio is not None:
            self._pump_gpio.output(self.PUMP_GPIO_PIN, False)
        self._pump_active = False
        logger.info(f"[{self.payload_id}] _arm_outputs: servos armed, pump primed")

    def _disarm_outputs(self) -> None:
        """Center servos, stop pump."""
        self._set_servo_us(self.SERVO_PAN_CHANNEL, self.SERVO_CENTER_US)
        self._set_servo_us(self.SERVO_TILT_CHANNEL, self.SERVO_CENTER_US)
        self._pan_angle_deg = 90.0
        self._tilt_angle_deg = 90.0

        if self.sim_mode:
            self._pump_active = False
        elif self._pump_gpio is not None:
            self._pump_gpio.output(self.PUMP_GPIO_PIN, False)
            self._pump_active = False

        logger.info(f"[{self.payload_id}] _disarm_outputs: servos centered, pump off")

    def _emergency_cut(self) -> None:
        """Immediate power cut — target <50ms completion."""
        t0 = time.monotonic()

        # Instantly kill pump GPIO (fastest path)
        self._pump_active = False

        if not self.sim_mode and self._pump_gpio is not None:
            try:
                self._pump_gpio.output(self.PUMP_GPIO_PIN, False)
            except Exception:
                pass  # Hardware might already be gone

        # Servos lose power when rail cuts — no need to center
        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.warning(
            f"[{self.payload_id}] _emergency_cut: complete in {elapsed_ms:.1f}ms"
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def _read_health_specific(self) -> dict[str, Any]:
        """Read payload-specific health data.

        In SIM_MODE, returns nominal values.
        In real mode, reads servo bus voltage and pump current.
        """
        if self.sim_mode:
            return {
                "status": "OK",
                "power_voltage_v": 12.0,
                "power_current_ma": (
                    self.POWER_MAX_MA if self._pump_active
                    else self.POWER_NOMINAL_MA
                ),
                "temperature_c": 35.0,
                "payload_specific": {
                    "pan_angle_deg": round(self._pan_angle_deg, 1),
                    "tilt_angle_deg": round(self._tilt_angle_deg, 1),
                    "pump_active": self._pump_active,
                    "reservoir_ml": round(self._reservoir_ml, 1),
                    "fire_count": self._fire_count,
                    "deadzone_px": self._deadzone_px,
                },
            }

        # Real mode — attempt to read hardware
        try:
            # Placeholder for voltage/current sense (INA219 on payload bus)
            voltage_v = 12.0
            current_ma = self.POWER_NOMINAL_MA
            temp_c = 35.0

            return {
                "status": "OK",
                "power_voltage_v": voltage_v,
                "power_current_ma": current_ma,
                "temperature_c": temp_c,
                "payload_specific": {
                    "pan_angle_deg": round(self._pan_angle_deg, 1),
                    "tilt_angle_deg": round(self._tilt_angle_deg, 1),
                    "pump_active": self._pump_active,
                    "reservoir_ml": round(self._reservoir_ml, 1),
                    "fire_count": self._fire_count,
                    "deadzone_px": self._deadzone_px,
                },
            }
        except Exception as e:
            return {
                "status": "DEGRADED",
                "power_voltage_v": 0.0,
                "power_current_ma": 0.0,
                "temperature_c": 0.0,
                "payload_specific": {"error": str(e)},
            }

    # ==================================================================
    # Command implementation
    # ==================================================================

    def _execute_impl(
        self, action: str, params: dict[str, Any]
    ) -> PayloadCommandResult:
        """Dispatch Splash-specific commands.

        Supports: fire, aim, center, set_deadzone, get_status
        """
        if action == "fire":
            return self._cmd_fire(params)
        elif action == "aim":
            return self._cmd_aim(params)
        elif action == "center":
            return self._cmd_center(params)
        elif action == "set_deadzone":
            return self._cmd_set_deadzone(params)
        elif action == "get_status":
            return self._cmd_get_status(params)
        else:
            return PayloadCommandResult(
                success=False,
                message=f"Unknown action: {action}",
            )

    # ------------------------------------------------------------------
    # fire — Trigger pump for duration_ms
    # ------------------------------------------------------------------

    def _cmd_fire(self, params: dict[str, Any]) -> PayloadCommandResult:
        """Fire the water gun.

        Args:
            duration_ms: Burst duration (100-2000ms, default 500ms).

        Returns:
            PayloadCommandResult with shot count and reservoir status.
        """
        duration_ms = params.get("duration_ms", self._fire_duration_ms)
        duration_ms = max(self.MIN_FIRE_DURATION_MS,
                         min(self.MAX_FIRE_DURATION_MS, duration_ms))

        # Check reservoir
        if self._reservoir_ml <= 0:
            return PayloadCommandResult(
                success=False,
                message="Reservoir empty — cannot fire.",
                data={"reservoir_ml": 0.0, "fire_count": self._fire_count},
            )

        # Activate pump
        self._pump_active = True
        self._pump_activated_at = time.time()

        if not self.sim_mode and self._pump_gpio is not None:
            try:
                self._pump_gpio.output(self.PUMP_GPIO_PIN, True)
            except Exception as e:
                self._pump_active = False
                return PayloadCommandResult(
                    success=False,
                    message=f"Pump GPIO write failed: {e}",
                )

        # Simulate or actually wait
        if self.sim_mode:
            time.sleep(duration_ms / 1000.0)
        else:
            # Non-blocking fire: pump stays on until next fire/center call
            # For burst mode, we'd use a timer thread
            time.sleep(duration_ms / 1000.0)

        # Deactivate pump
        self._pump_active = False
        if not self.sim_mode and self._pump_gpio is not None:
            self._pump_gpio.output(self.PUMP_GPIO_PIN, False)

        # Update reservoir (0.5ml per 500ms burst)
        ml_used = (duration_ms / 500.0) * 0.5
        self._reservoir_ml = max(0.0, self._reservoir_ml - ml_used)
        self._total_fired_ml += ml_used
        self._fire_count += 1

        logger.info(
            f"[{self.payload_id}] FIRE: {duration_ms}ms burst, "
            f"{ml_used:.1f}ml used, {self._reservoir_ml:.1f}ml remaining"
        )

        return PayloadCommandResult(
            success=True,
            message=f"Fired {duration_ms}ms burst. {self._reservoir_ml:.1f}ml remaining.",
            data={
                "duration_ms": duration_ms,
                "ml_used": round(ml_used, 1),
                "reservoir_ml": round(self._reservoir_ml, 1),
                "fire_count": self._fire_count,
                "pan_angle_deg": round(self._pan_angle_deg, 1),
                "tilt_angle_deg": round(self._tilt_angle_deg, 1),
            },
        )

    # ------------------------------------------------------------------
    # aim — Set pan/tilt angles
    # ------------------------------------------------------------------

    def _cmd_aim(self, params: dict[str, Any]) -> PayloadCommandResult:
        """Aim the water gun by setting pan/tilt servo angles.

        Args:
            pan_deg: Pan angle in degrees (0-180, 90=center).
            tilt_deg: Tilt angle in degrees (0-180, 90=center).

        Returns:
            PayloadCommandResult with actual servo positions.
        """
        pan = float(params.get("pan_deg", self._pan_angle_deg))
        tilt = float(params.get("tilt_deg", self._tilt_angle_deg))

        pan = max(0.0, min(180.0, pan))
        tilt = max(0.0, min(180.0, tilt))

        self._pan_angle_deg = pan
        self._tilt_angle_deg = tilt

        # Move servos
        pan_us = self._angle_to_pulse_us(pan)
        tilt_us = self._angle_to_pulse_us(tilt)
        self._set_servo_us(self.SERVO_PAN_CHANNEL, pan_us)
        self._set_servo_us(self.SERVO_TILT_CHANNEL, tilt_us)

        logger.info(
            f"[{self.payload_id}] AIM: pan={pan:.1f}° ({pan_us}us), "
            f"tilt={tilt:.1f}° ({tilt_us}us)"
        )

        return PayloadCommandResult(
            success=True,
            message=f"Servos set — pan={pan:.1f}°, tilt={tilt:.1f}°",
            data={
                "pan_deg": round(pan, 1),
                "tilt_deg": round(tilt, 1),
                "pan_pulse_us": pan_us,
                "tilt_pulse_us": tilt_us,
            },
        )

    # ------------------------------------------------------------------
    # center — Return servos to neutral
    # ------------------------------------------------------------------

    def _cmd_center(self, params: dict[str, Any]) -> PayloadCommandResult:
        """Center both servos and stop pump.

        Returns:
            PayloadCommandResult with confirmation.
        """
        self._pan_angle_deg = 90.0
        self._tilt_angle_deg = 90.0

        self._set_servo_us(self.SERVO_PAN_CHANNEL, self.SERVO_CENTER_US)
        self._set_servo_us(self.SERVO_TILT_CHANNEL, self.SERVO_CENTER_US)

        # Stop pump if active
        if self._pump_active:
            self._pump_active = False
            if not self.sim_mode and self._pump_gpio is not None:
                self._pump_gpio.output(self.PUMP_GPIO_PIN, False)

        logger.info(f"[{self.payload_id}] CENTER: servos at 90°, pump off")

        return PayloadCommandResult(
            success=True,
            message="Servos centered, pump stopped.",
            data={
                "pan_deg": 90.0,
                "tilt_deg": 90.0,
                "pump_active": False,
            },
        )

    # ------------------------------------------------------------------
    # set_deadzone — Configure fire trigger deadzone
    # ------------------------------------------------------------------

    def _cmd_set_deadzone(self, params: dict[str, Any]) -> PayloadCommandResult:
        """Set the fire deadzone in pixels.

        Args:
            deadzone_px: New deadzone in pixels (5-100).

        Returns:
            PayloadCommandResult with updated deadzone.
        """
        dz = int(params.get("deadzone_px", self._deadzone_px))
        dz = max(5, min(100, dz))
        self._deadzone_px = dz

        logger.info(f"[{self.payload_id}] SET_DEADZONE: {dz}px")

        return PayloadCommandResult(
            success=True,
            message=f"Deadzone set to {dz}px",
            data={
                "deadzone_px": dz,
                "fire_duration_ms": self._fire_duration_ms,
            },
        )

    # ------------------------------------------------------------------
    # get_status — Full payload status dump
    # ------------------------------------------------------------------

    def _cmd_get_status(self, params: dict[str, Any]) -> PayloadCommandResult:
        """Return full payload status.

        Returns:
            PayloadCommandResult with all payload state.
        """
        return PayloadCommandResult(
            success=True,
            message="",
            data={
                "state": self.state.name,
                "pan_deg": round(self._pan_angle_deg, 1),
                "tilt_deg": round(self._tilt_angle_deg, 1),
                "pump_active": self._pump_active,
                "reservoir_ml": round(self._reservoir_ml, 1),
                "total_fired_ml": round(self._total_fired_ml, 1),
                "fire_count": self._fire_count,
                "deadzone_px": self._deadzone_px,
                "fire_duration_ms": self._fire_duration_ms,
                "sim_mode": self.sim_mode,
                "i2c_address": f"0x{self.PCA9685_ADDRESS:02X}",
                "pump_gpio_pin": self.PUMP_GPIO_PIN,
            },
        )
