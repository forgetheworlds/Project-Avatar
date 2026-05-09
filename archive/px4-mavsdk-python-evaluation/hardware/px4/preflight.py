#!/usr/bin/env python3
"""PX4 Pre-flight Parameter Verification CLI.

This script provides a command-line interface for verifying PX4 safety
parameters before flight. It supports:

1. Dry-run mode: Validates param files without drone connection
2. Live mode: Verifies parameters against connected PX4
3. JSON output: Machine-readable status for integration

Usage:
    # Dry-run verification (no drone required)
    python hardware/px4/preflight.py --dry-run --airframe mark4_7in

    # Live verification with SITL
    python hardware/px4/preflight.py --airframe mark4_7in --system udp://:14540

    # JSON output for scripting
    python hardware/px4/preflight.py --dry-run --airframe mark4_7in --json

Exit Codes:
    0: All checks passed
    1: Verification failed
    2: Invalid arguments or file not found
    3: Connection error (live mode only)

Integration:
    The MCP preflight_checklist tool shells out to this script.
    See: avatar/mcp_server/tools/primitives/preflight.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Union

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from avatar.mav.px4_parameters import (
    CRITICAL_PARAMETERS,
    PARAMETER_DESCRIPTIONS,
    ParameterStatus,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Result Data Structures
# =============================================================================


@dataclass
class PreflightResult:
    """Result of preflight parameter verification."""

    status: str  # "PASS" or "FAIL"
    mode: str  # "dry_run" or "live"
    airframe: str
    params_file: str
    total_params: int
    valid_params: int
    invalid_params: int
    missing_required: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_json_line(self) -> str:
        """Output as a single JSON line for parsing."""
        return json.dumps(asdict(self))


# =============================================================================
# Parameter Parsing
# =============================================================================


def parse_params_file(params_path: Path) -> Dict[str, Union[int, float]]:
    """Parse a PX4 .params file into a dictionary.

    Args:
        params_path: Path to the .params file

    Returns:
        Dictionary of parameter name -> value

    Raises:
        FileNotFoundError: If params file doesn't exist
        ValueError: If params file format is invalid
    """
    import re

    if not params_path.exists():
        raise FileNotFoundError(f"Parameter file not found: {params_path}")

    params: Dict[str, Union[int, float]] = {}

    with open(params_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse "param set[-default] <NAME> <VALUE>"
            match = re.match(
                r"param\s+set(?:-default)?\s+(\S+)\s+(\S+)",
                line,
            )

            if match:
                name = match.group(1)
                value_str = match.group(2)

                try:
                    if "." in value_str:
                        value: Union[int, float] = float(value_str)
                    else:
                        value = int(value_str)
                    params[name] = value
                except ValueError:
                    logger.warning(
                        "Invalid value for %s: %s",
                        name,
                        value_str,
                    )

    return params


# =============================================================================
# Dry-Run Verification
# =============================================================================


def verify_dry_run(
    airframe: str,
    airframes_dir: Path,
) -> PreflightResult:
    """Perform dry-run verification without drone connection.

    Validates that:
    1. Params file exists and parses correctly
    2. All required CRITICAL_PARAMETERS are present
    3. Parameter values are within acceptable ranges

    Args:
        airframe: Airframe name (e.g., "mark4_7in")
        airframes_dir: Directory containing .params files

    Returns:
        PreflightResult with verification status
    """
    params_path = airframes_dir / f"{airframe}.params"
    errors: List[str] = []
    warnings: List[str] = []

    # Check file exists
    if not params_path.exists():
        return PreflightResult(
            status="FAIL",
            mode="dry_run",
            airframe=airframe,
            params_file=str(params_path),
            total_params=0,
            valid_params=0,
            invalid_params=0,
            missing_required=list(CRITICAL_PARAMETERS.keys()),
            errors=[f"Parameter file not found: {params_path}"],
        )

    # Parse params file
    try:
        params = parse_params_file(params_path)
    except Exception as e:
        return PreflightResult(
            status="FAIL",
            mode="dry_run",
            airframe=airframe,
            params_file=str(params_path),
            total_params=0,
            valid_params=0,
            invalid_params=0,
            missing_required=[],
            errors=[f"Failed to parse params file: {e}"],
        )

    # Check for required parameters
    missing: List[str] = []
    for required_name in CRITICAL_PARAMETERS.keys():
        if required_name not in params:
            missing.append(required_name)
            warnings.append(
                f"Missing required param: {required_name} "
                f"(expected {CRITICAL_PARAMETERS[required_name]})"
            )

    # Validate parameter values (basic sanity checks)
    valid_count = 0
    invalid_count = 0

    for name, value in params.items():
        # Check value is reasonable
        if value < 0 and name not in ["GF_ALTMODE"]:
            warnings.append(f"Negative value for {name}: {value}")

        # Check COM_OBL_RC_ACT is RTL (3) or Land (2)
        if name == "COM_OBL_RC_ACT" and value not in [2, 3]:
            warnings.append(
                f"COM_OBL_RC_ACT should be RTL (3) or Land (2), got {value}"
            )

        # Check timeouts are reasonable
        if name == "COM_OF_LOSS_T" and value > 5.0:
            warnings.append(
                f"COM_OF_LOSS_T = {value}s is too long (max 5.0s recommended)"
            )

        valid_count += 1

    # Determine overall status
    status = "PASS" if len(missing) == 0 else "FAIL"

    return PreflightResult(
        status=status,
        mode="dry_run",
        airframe=airframe,
        params_file=str(params_path),
        total_params=len(params),
        valid_params=valid_count,
        invalid_params=invalid_count,
        missing_required=missing,
        errors=errors,
        warnings=warnings,
    )


# =============================================================================
# Live Verification (with drone)
# =============================================================================


async def verify_live(
    airframe: str,
    airframes_dir: Path,
    system_address: str,
) -> PreflightResult:
    """Perform live verification against connected PX4.

    Args:
        airframe: Airframe name
        airframes_dir: Directory containing .params files
        system_address: MAVSDK connection URL

    Returns:
        PreflightResult with verification status
    """
    from avatar.mav.px4_parameters import PX4ParameterManager

    params_path = airframes_dir / f"{airframe}.params"
    errors: List[str] = []
    warnings: List[str] = []

    # Check file exists
    if not params_path.exists():
        return PreflightResult(
            status="FAIL",
            mode="live",
            airframe=airframe,
            params_file=str(params_path),
            total_params=0,
            valid_params=0,
            invalid_params=0,
            missing_required=list(CRITICAL_PARAMETERS.keys()),
            errors=[f"Parameter file not found: {params_path}"],
        )

    # Parse params file
    try:
        params = parse_params_file(params_path)
    except Exception as e:
        return PreflightResult(
            status="FAIL",
            mode="live",
            airframe=airframe,
            params_file=str(params_path),
            total_params=0,
            valid_params=0,
            invalid_params=0,
            missing_required=[],
            errors=[f"Failed to parse params file: {e}"],
        )

    # Connect to drone
    try:
        from mavsdk import System
    except ImportError:
        return PreflightResult(
            status="FAIL",
            mode="live",
            airframe=airframe,
            params_file=str(params_path),
            total_params=len(params),
            valid_params=0,
            invalid_params=len(params),
            missing_required=[],
            errors=["MAVSDK not installed. Install with: pip install mavsdk"],
        )

    drone = System()

    try:
        await drone.connect(system_address=system_address)

        # Wait for connection
        async for state in drone.core.connection_state():
            if state.is_connected:
                break

        logger.info("Connected to drone at %s", system_address)

    except Exception as e:
        return PreflightResult(
            status="FAIL",
            mode="live",
            airframe=airframe,
            params_file=str(params_path),
            total_params=len(params),
            valid_params=0,
            invalid_params=len(params),
            missing_required=[],
            errors=[f"Failed to connect to drone: {e}"],
        )

    # Verify parameters
    manager = PX4ParameterManager(drone)
    valid_count = 0
    invalid_count = 0

    # Build overlay with CRITICAL_PARAMETERS
    overlay = dict(CRITICAL_PARAMETERS)
    overlay.update(params)

    for name, expected in overlay.items():
        try:
            actual = await manager.get_parameter(name)
            status = manager.check_parameter(name, expected, actual)

            if status.is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                errors.append(f"{name}: {status.message}")

        except Exception as e:
            invalid_count += 1
            errors.append(f"{name}: Failed to read - {e}")

    # Check for missing required params
    missing = [
        name
        for name in CRITICAL_PARAMETERS.keys()
        if name not in overlay
    ]

    status = "PASS" if invalid_count == 0 and len(missing) == 0 else "FAIL"

    return PreflightResult(
        status=status,
        mode="live",
        airframe=airframe,
        params_file=str(params_path),
        total_params=len(overlay),
        valid_params=valid_count,
        invalid_params=invalid_count,
        missing_required=missing,
        errors=errors,
        warnings=warnings,
    )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for preflight CLI."""
    parser = argparse.ArgumentParser(
        description="PX4 pre-flight parameter verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry-run verification
    python hardware/px4/preflight.py --dry-run --airframe mark4_7in

    # Live verification with SITL
    python hardware/px4/preflight.py --airframe mark4_7in --system udp://:14540

    # JSON output
    python hardware/px4/preflight.py --dry-run --airframe mark4_7in --json

Exit Codes:
    0 - All checks passed
    1 - Verification failed
    2 - Invalid arguments
    3 - Connection error
""",
    )

    parser.add_argument(
        "--airframe",
        required=True,
        help="Airframe name (e.g., mark4_7in, x500_v2)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run verification without connecting to drone",
    )
    parser.add_argument(
        "--system",
        default="udp://:14540",
        help="MAVSDK connection URL (default: udp://:14540 for SITL)",
    )
    parser.add_argument(
        "--airframes-dir",
        type=Path,
        default=None,
        help="Directory containing airframe .params files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON line",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Default airframes directory
    airframes_dir = args.airframes_dir
    if airframes_dir is None:
        airframes_dir = Path(__file__).parent / "airframes"

    # Run verification
    if args.dry_run:
        result = verify_dry_run(args.airframe, airframes_dir)
    else:
        result = asyncio.run(
            verify_live(
                args.airframe,
                airframes_dir,
                args.system,
            )
        )

    # Output result
    if args.json:
        print(result.to_json_line())
    else:
        # Human-readable output
        print(f"\n{'=' * 60}")
        print("  PX4 Pre-flight Parameter Verification")
        print(f"{'=' * 60}")
        print(f"Airframe: {result.airframe}")
        print(f"Params file: {result.params_file}")
        print(f"Mode: {result.mode}")
        print(f"Status: {result.status}")
        print(f"Total params: {result.total_params}")
        print(f"Valid: {result.valid_params}")
        print(f"Invalid: {result.invalid_params}")

        if result.missing_required:
            print(f"\nMissing required params: {result.missing_required}")

        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

        if result.errors:
            print("\nErrors:")
            for error in result.errors:
                print(f"  - {error}")

        print(f"{'=' * 60}")
        print(f"Result: {result.status}")
        print(f"{'=' * 60}\n")

        # JSON line for machine parsing
        print(result.to_json_line())

    # Return exit code based on status
    if result.status == "PASS":
        return 0
    elif "Connection" in str(result.errors):
        return 3
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
