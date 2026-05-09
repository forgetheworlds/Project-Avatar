#!/usr/bin/env python3
"""PX4 parameter verification with airframe overlay support.

This module provides functionality to:
1. Load airframe parameter overlays from .params files
2. Merge with CRITICAL_PARAMETERS from px4_parameters module
3. Verify parameters against PX4 or mock drone

The overlay system allows airframe-specific parameters to override
the default safety parameters defined in CRITICAL_PARAMETERS.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from avatar.mav.px4_parameters import (
    CRITICAL_PARAMETERS,
    PARAMETER_DESCRIPTIONS,
    PARAMETER_TYPES,
    ParameterStatus,
    PX4ParameterManager,
    SafetyError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Parameter File Parsing
# =============================================================================


def parse_params_file(params_path: Path) -> Dict[str, Union[int, float]]:
    """Parse a PX4 .params file into a dictionary.

    Supports QGroundControl parameter file format:
        # Comment lines are ignored
        param set-default <NAME> <VALUE>

    Args:
        params_path: Path to the .params file

    Returns:
        Dictionary mapping parameter names to their values

    Raises:
        FileNotFoundError: If the params file doesn't exist
        ValueError: If the file format is invalid
    """
    if not params_path.exists():
        raise FileNotFoundError(f"Parameter file not found: {params_path}")

    params: Dict[str, Union[int, float]] = {}

    with open(params_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse "param set-default <NAME> <VALUE>"
            # Also support "param set <NAME> <VALUE>" for compatibility
            match = re.match(
                r"param\s+set(?:-default)?\s+(\S+)\s+(\S+)",
                line,
            )

            if match:
                name = match.group(1)
                value_str = match.group(2)

                # Convert value to int or float
                try:
                    # Try int first
                    if "." in value_str:
                        value: Union[int, float] = float(value_str)
                    else:
                        value = int(value_str)
                except ValueError:
                    logger.warning(
                        "Line %d: Invalid value '%s' for parameter '%s'",
                        line_num,
                        value_str,
                        name,
                    )
                    continue

                params[name] = value
                logger.debug("Parsed parameter: %s = %s", name, value)

    logger.info("Parsed %d parameters from %s", len(params), params_path)
    return params


def build_overlay_dict(
    airframe_params: Dict[str, Union[int, float]],
    base_params: Optional[Dict[str, Union[int, float]]] = None,
) -> Dict[str, Union[int, float]]:
    """Build merged parameter dict from airframe overlay and base params.

    The overlay wins on key intersection - airframe-specific params
    override the base CRITICAL_PARAMETERS.

    Args:
        airframe_params: Airframe-specific parameters from .params file
        base_params: Base parameters (defaults to CRITICAL_PARAMETERS)

    Returns:
        Merged dictionary with overlay taking precedence
    """
    if base_params is None:
        base_params = CRITICAL_PARAMETERS

    # Start with base parameters
    merged = dict(base_params)

    # Overlay airframe-specific params (airframe wins)
    for name, value in airframe_params.items():
        merged[name] = value
        if name in base_params:
            logger.debug(
                "Overlay: %s = %s (base had %s)",
                name,
                value,
                base_params[name],
            )
        else:
            logger.debug("New param from overlay: %s = %s", name, value)

    return merged


# =============================================================================
# Verification Results
# =============================================================================


@dataclass
class VerificationResult:
    """Result of verifying parameters against a drone or mock."""

    airframe: str
    params_path: Path
    total_params: int
    valid_count: int
    invalid_count: int
    is_valid: bool
    status_list: List[ParameterStatus]
    missing_params: List[str]
    extra_params: List[str]


# =============================================================================
# Verification Functions
# =============================================================================


async def verify_with_overlay(
    drone: "System",
    overlay: Dict[str, Union[int, float]],
) -> List[ParameterStatus]:
    """Verify parameters against a drone using the overlay dict.

    This extends the standard PX4ParameterManager to accept an overlay
    dict that overrides CRITICAL_PARAMETERS.

    Args:
        drone: MAVSDK System instance (connected to PX4 or mock)
        overlay: Merged parameter dict to verify against

    Returns:
        List of ParameterStatus for each verified parameter
    """
    manager = PX4ParameterManager(drone)
    results: List[ParameterStatus] = []

    # Read all parameters from the overlay
    for name, expected in overlay.items():
        # Determine if we need to check this param type
        param_type = PARAMETER_TYPES.get(name, "float")

        try:
            if param_type == "int":
                actual = await drone.param.get_param_int(name)
            else:
                actual = await drone.param.get_param_float(name)

            actual_float = float(actual) if actual is not None else None
        except Exception as e:
            logger.warning("Failed to read parameter %s: %s", name, e)
            actual_float = None

        # Check parameter using manager's comparison logic
        status = manager.check_parameter(name, expected, actual_float)
        results.append(status)

    return results


async def verify_airframe(
    airframe: str,
    drone: Optional["System"] = None,
    airframes_dir: Optional[Path] = None,
) -> VerificationResult:
    """Verify an airframe's parameters.

    Args:
        airframe: Airframe name (e.g., "mark4_7in", "x500_v2")
        drone: MAVSDK System instance (None for dry-run)
        airframes_dir: Directory containing .params files

    Returns:
        VerificationResult with complete status
    """
    # Default airframes directory
    if airframes_dir is None:
        airframes_dir = Path(__file__).parent / "airframes"

    params_path = airframes_dir / f"{airframe}.params"

    # Parse the params file
    try:
        airframe_params = parse_params_file(params_path)
    except FileNotFoundError:
        return VerificationResult(
            airframe=airframe,
            params_path=params_path,
            total_params=0,
            valid_count=0,
            invalid_count=0,
            is_valid=False,
            status_list=[],
            missing_params=[],
            extra_params=[],
        )

    # Build overlay
    overlay = build_overlay_dict(airframe_params)

    # Check for missing required params
    missing = [
        name
        for name in CRITICAL_PARAMETERS.keys()
        if name not in overlay
    ]

    # Check for extra params not in base
    extra = [
        name
        for name in overlay.keys()
        if name not in CRITICAL_PARAMETERS
    ]

    # If no drone provided, return mock result
    if drone is None:
        # In dry-run mode, we consider params valid if file parses correctly
        return VerificationResult(
            airframe=airframe,
            params_path=params_path,
            total_params=len(overlay),
            valid_count=len(overlay),  # Assume all valid in dry-run
            invalid_count=0,
            is_valid=True,
            status_list=[],
            missing_params=missing,
            extra_params=extra,
        )

    # Real verification with drone
    status_list = await verify_with_overlay(drone, overlay)

    valid_count = sum(1 for s in status_list if s.is_valid)
    invalid_count = len(status_list) - valid_count

    return VerificationResult(
        airframe=airframe,
        params_path=params_path,
        total_params=len(overlay),
        valid_count=valid_count,
        invalid_count=invalid_count,
        is_valid=invalid_count == 0 and len(missing) == 0,
        status_list=status_list,
        missing_params=missing,
        extra_params=extra,
    )


def format_verification_result(result: VerificationResult) -> str:
    """Format a VerificationResult for display."""
    lines = [
        f"Airframe: {result.airframe}",
        f"Params file: {result.params_path}",
        f"Total parameters: {result.total_params}",
        f"Valid: {result.valid_count}",
        f"Invalid: {result.invalid_count}",
        f"Overall status: {'PASS' if result.is_valid else 'FAIL'}",
    ]

    if result.missing_params:
        lines.append(f"Missing required params: {result.missing_params}")

    if result.extra_params:
        lines.append(f"Extra params (not in base): {result.extra_params}")

    # Add invalid parameter details
    invalid = [s for s in result.status_list if not s.is_valid]
    if invalid:
        lines.append("\nInvalid parameters:")
        for status in invalid:
            lines.append(f"  - {status.name}: {status.message}")

    return "\n".join(lines)


# =============================================================================
# Main Entry Point (for testing)
# =============================================================================


def main() -> int:
    """Command-line interface for verify.py."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Verify PX4 airframe parameter overlays",
    )
    parser.add_argument(
        "--airframe",
        required=True,
        help="Airframe name (e.g., mark4_7in, x500_v2)",
    )
    parser.add_argument(
        "--airframes-dir",
        type=Path,
        help="Directory containing .params files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    # Run verification (dry-run without drone)
    async def run() -> VerificationResult:
        return await verify_airframe(
            airframe=args.airframe,
            drone=None,  # Dry-run mode
            airframes_dir=args.airframes_dir,
        )

    result = asyncio.run(run())

    if args.json:
        output = {
            "airframe": result.airframe,
            "params_path": str(result.params_path),
            "total_params": result.total_params,
            "valid_count": result.valid_count,
            "invalid_count": result.invalid_count,
            "is_valid": result.is_valid,
            "missing_params": result.missing_params,
            "extra_params": result.extra_params,
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_verification_result(result))

    return 0 if result.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
