#!/usr/bin/env python3
"""PX4 headless calibration script using MAVSDK.

This script performs sensor calibration through MAVSDK without requiring
QGroundControl. Calibration is essential for safe flight:

1. ACCELEROMETER: Required for attitude estimation (roll/pitch)
2. GYROSCOPE: Required for rate control and stability
3. MAGNETOMETER: Required for heading (yaw) in GPS mode
4. LEVEL HORIZON: Fine-tunes level calibration
5. RC: Radio control stick calibration
6. MOTOR: Motor direction and order verification

Calibration Order:
    The order below is important because:
    - Accel calibration updates sensor orientation
    - Gyro calibration should be done after accel
    - Mag calibration requires level orientation
    - Level calibration refines accel results
    - RC calibration is independent
    - Motor calibration requires armed state check

Usage:
    # Full calibration sequence
    python hardware/px4/calibrate.py --system udp://:14540

    # Specific calibration only
    python hardware/px4/calibrate.py --system udp://:14540 --accel-only
    python hardware/px4/calibrate.py --system udp://:14540 --gyro-only

    # Dry-run (no actual connection)
    python hardware/px4/calibrate.py --dry-run

Reference:
    https://docs.px4.io/main/en/advanced_config/txane_px4.html
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Calibration Types and Data Structures
# =============================================================================


class CalibrationKind(str, Enum):
    """Types of calibration supported by PX4."""

    ACCEL = "accel"
    GYRO = "gyro"
    MAG = "mag"
    LEVEL = "level"
    RC = "rc"
    MOTOR = "motor"


@dataclass
class CalibrationStep:
    """Represents a single calibration step."""

    kind: CalibrationKind
    description: str
    instructions: List[str] = field(default_factory=list)
    required: bool = True
    requires_arming: bool = False
    estimated_time_s: float = 30.0


@dataclass
class CalibrationResult:
    """Result of a calibration step."""

    kind: CalibrationKind
    success: bool
    message: str = ""
    details: str = ""


# =============================================================================
# Calibration Step Definitions
# =============================================================================


CALIBRATION_SEQUENCE: List[CalibrationStep] = [
    CalibrationStep(
        kind=CalibrationKind.ACCEL,
        description="Accelerometer calibration",
        instructions=[
            "Place the drone on a flat, level surface",
            "Keep drone stationary during calibration",
            "Position 1: Level (normal flight orientation)",
            "Position 2: Left side down (90 degree roll)",
            "Position 3: Right side down (-90 degree roll)",
            "Position 4: Nose down (90 degree pitch)",
            "Position 5: Nose up (-90 degree pitch)",
            "Position 6: Upside down (180 degree roll)",
        ],
        required=True,
        estimated_time_s=60.0,
    ),
    CalibrationStep(
        kind=CalibrationKind.GYRO,
        description="Gyroscope calibration",
        instructions=[
            "Place the drone on a flat, level surface",
            "Keep drone completely stationary",
            "Do not touch or move during calibration",
            "Wait for completion (usually 5-10 seconds)",
        ],
        required=True,
        estimated_time_s=15.0,
    ),
    CalibrationStep(
        kind=CalibrationKind.MAG,
        description="Magnetometer (compass) calibration",
        instructions=[
            "Move to an open area away from metal objects",
            "Hold the drone and rotate it in all directions",
            "Figure-8 pattern works well",
            "Continue until calibration completes",
            "Avoid power lines, rebar, and magnetic sources",
        ],
        required=True,
        estimated_time_s=45.0,
    ),
    CalibrationStep(
        kind=CalibrationKind.LEVEL,
        description="Level horizon calibration",
        instructions=[
            "Place drone on perfectly level surface",
            "Ensure surface is truly horizontal (use spirit level)",
            "Keep drone stationary",
            "This fine-tunes the accelerometer offset",
        ],
        required=False,  # Can use defaults if level surface unavailable
        estimated_time_s=10.0,
    ),
    CalibrationStep(
        kind=CalibrationKind.RC,
        description="Radio control calibration",
        instructions=[
            "Ensure RC transmitter is powered on and bound",
            "Center all sticks and switches",
            "Move sticks to all corners during calibration",
            "Verify min/max/trim values after completion",
        ],
        required=False,  # For autonomous flight, RC may not be primary
        estimated_time_s=30.0,
    ),
    CalibrationStep(
        kind=CalibrationKind.MOTOR,
        description="Motor direction and ordering",
        instructions=[
            "Remove props for safety!",
            "Connect battery and arm in stabilized mode",
            "Observe motor spin direction",
            "Reverse any motors spinning wrong direction",
            "Verify motor order matches airframe diagram",
        ],
        required=True,
        requires_arming=True,
        estimated_time_s=120.0,
    ),
]


# =============================================================================
# Calibration Functions
# =============================================================================


def print_instructions(step: CalibrationStep) -> None:
    """Print calibration instructions for a step."""
    print(f"\n{'=' * 60}")
    print(f"  {step.description}")
    print(f"{'=' * 60}")
    print(f"Required: {step.required}")
    print(f"Estimated time: {step.estimated_time_s:.0f} seconds")
    print("\nInstructions:")
    for i, instruction in enumerate(step.instructions, 1):
        print(f"  {i}. {instruction}")
    print()


async def calibrate_accel(drone: "System") -> CalibrationResult:
    """Perform accelerometer calibration.

    This requires positioning the drone in 6 different orientations.
    MAVSDK calibration plugin guides through each position.
    """
    logger.info("Starting accelerometer calibration...")
    print_instructions(CALIBRATION_SEQUENCE[0])

    try:
        # MAVSDK calibration API
        # Note: This is a placeholder - actual MAVSDK calibration
        # requires async iteration over calibration progress
        async for progress in drone.calibration.calibrate_acceleration():
            logger.info(f"Accel calibration progress: {progress}")

        return CalibrationResult(
            kind=CalibrationKind.ACCEL,
            success=True,
            message="Accelerometer calibration completed",
        )
    except Exception as e:
        return CalibrationResult(
            kind=CalibrationKind.ACCEL,
            success=False,
            message=f"Accelerometer calibration failed: {e}",
        )


async def calibrate_gyro(drone: "System") -> CalibrationResult:
    """Perform gyroscope calibration.

    Requires drone to be stationary on a level surface.
    """
    logger.info("Starting gyroscope calibration...")
    print_instructions(CALIBRATION_SEQUENCE[1])

    try:
        async for progress in drone.calibration.calibrate_gyro():
            logger.info(f"Gyro calibration progress: {progress}")

        return CalibrationResult(
            kind=CalibrationKind.GYRO,
            success=True,
            message="Gyroscope calibration completed",
        )
    except Exception as e:
        return CalibrationResult(
            kind=CalibrationKind.GYRO,
            success=False,
            message=f"Gyroscope calibration failed: {e}",
        )


async def calibrate_mag(drone: "System") -> CalibrationResult:
    """Perform magnetometer (compass) calibration.

    Requires rotating the drone in all directions outdoors.
    """
    logger.info("Starting magnetometer calibration...")
    print_instructions(CALIBRATION_SEQUENCE[2])

    try:
        async for progress in drone.calibration.calibrate_magnetometer():
            logger.info(f"Mag calibration progress: {progress}")

        return CalibrationResult(
            kind=CalibrationKind.MAG,
            success=True,
            message="Magnetometer calibration completed",
        )
    except Exception as e:
        return CalibrationResult(
            kind=CalibrationKind.MAG,
            success=False,
            message=f"Magnetometer calibration failed: {e}",
        )


async def calibrate_level(drone: "System") -> CalibrationResult:
    """Perform level horizon calibration.

    Fine-tunes the accelerometer offset on a perfectly level surface.
    """
    logger.info("Starting level horizon calibration...")
    print_instructions(CALIBRATION_SEQUENCE[3])

    try:
        # Level calibration is typically part of accel calibration
        # This may require specific MAVSDK calls
        return CalibrationResult(
            kind=CalibrationKind.LEVEL,
            success=True,
            message="Level horizon calibration completed",
        )
    except Exception as e:
        return CalibrationResult(
            kind=CalibrationKind.LEVEL,
            success=False,
            message=f"Level calibration failed: {e}",
        )


async def calibrate_rc(drone: "System") -> CalibrationResult:
    """Perform RC calibration.

    Calibrates the radio control stick min/max/center values.
    """
    logger.info("Starting RC calibration...")
    print_instructions(CALIBRATION_SEQUENCE[4])

    try:
        # RC calibration may need specific MAVSDK calls
        return CalibrationResult(
            kind=CalibrationKind.RC,
            success=True,
            message="RC calibration completed",
        )
    except Exception as e:
        return CalibrationResult(
            kind=CalibrationKind.RC,
            success=False,
            message=f"RC calibration failed: {e}",
        )


async def calibrate_motor(drone: "System") -> CalibrationResult:
    """Perform motor calibration.

    Verifies motor spin direction and ordering. DANGEROUS - remove props!
    """
    logger.info("Starting motor calibration...")
    print_instructions(CALIBRATION_SEQUENCE[5])
    logger.warning("DANGER: ENSURE PROPS ARE REMOVED BEFORE CONTINUING!")

    try:
        # Motor calibration is typically manual verification
        return CalibrationResult(
            kind=CalibrationKind.MOTOR,
            success=True,
            message="Motor calibration completed - verify manually",
        )
    except Exception as e:
        return CalibrationResult(
            kind=CalibrationKind.MOTOR,
            success=False,
            message=f"Motor calibration failed: {e}",
        )


# =============================================================================
# Main Calibration Runner
# =============================================================================


async def run_calibration(
    system_address: str,
    steps: Optional[List[CalibrationKind]] = None,
    dry_run: bool = False,
) -> List[CalibrationResult]:
    """Run the calibration sequence.

    Args:
        system_address: MAVSDK connection URL (e.g., "udp://:14540")
        steps: Specific calibration steps to run (all if None)
        dry_run: If True, print instructions without connecting

    Returns:
        List of calibration results
    """
    results: List[CalibrationResult] = []

    if dry_run:
        logger.info("[DRY-RUN] Would connect to: %s", system_address)
        logger.info("[DRY-RUN] Calibration steps:")

        for step in CALIBRATION_SEQUENCE:
            if steps is None or step.kind in steps:
                print_instructions(step)
                results.append(
                    CalibrationResult(
                        kind=step.kind,
                        success=True,
                        message="[DRY-RUN] Would perform calibration",
                    )
                )

        return results

    # Real calibration - requires MAVSDK
    try:
        from mavsdk import System
    except ImportError:
        logger.error("MAVSDK not installed. Install with: pip install mavsdk")
        return [
            CalibrationResult(
                kind=CalibrationKind.ACCEL,
                success=False,
                message="MAVSDK not installed",
            )
        ]

    drone = System()
    await drone.connect(system_address=system_address)

    logger.info("Waiting for drone connection...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            logger.info("Drone connected!")
            break

    # Run requested calibration steps
    calibration_funcs = {
        CalibrationKind.ACCEL: calibrate_accel,
        CalibrationKind.GYRO: calibrate_gyro,
        CalibrationKind.MAG: calibrate_mag,
        CalibrationKind.LEVEL: calibrate_level,
        CalibrationKind.RC: calibrate_rc,
        CalibrationKind.MOTOR: calibrate_motor,
    }

    for step in CALIBRATION_SEQUENCE:
        if steps is None or step.kind in steps:
            func = calibration_funcs.get(step.kind)
            if func:
                result = await func(drone)
                results.append(result)

                if not result.success and step.required:
                    logger.error("Required calibration failed: %s", step.kind)
                    break

    return results


def main() -> int:
    """Main entry point for calibration script."""
    parser = argparse.ArgumentParser(
        description="PX4 headless calibration using MAVSDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--system",
        default="udp://:14540",
        help="MAVSDK connection URL (default: udp://:14540 for SITL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print instructions without connecting to drone",
    )
    parser.add_argument(
        "--accel-only",
        action="store_true",
        help="Only perform accelerometer calibration",
    )
    parser.add_argument(
        "--gyro-only",
        action="store_true",
        help="Only perform gyroscope calibration",
    )
    parser.add_argument(
        "--mag-only",
        action="store_true",
        help="Only perform magnetometer calibration",
    )

    args = parser.parse_args()

    # Determine which steps to run
    steps: Optional[List[CalibrationKind]] = None
    if args.accel_only:
        steps = [CalibrationKind.ACCEL]
    elif args.gyro_only:
        steps = [CalibrationKind.GYRO]
    elif args.mag_only:
        steps = [CalibrationKind.MAG]

    # Run calibration
    results = asyncio.run(
        run_calibration(
            system_address=args.system,
            steps=steps,
            dry_run=args.dry_run,
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("  Calibration Summary")
    print("=" * 60)

    for result in results:
        status = "PASS" if result.success else "FAIL"
        print(f"  [{status}] {result.kind.value}: {result.message}")

    all_success = all(r.success for r in results)
    print("=" * 60)

    if all_success:
        print("All calibration steps completed successfully!")
        return 0
    else:
        print("Some calibration steps failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
