#!/usr/bin/env python3
"""Wait for PX4 SITL to be ready via MAVSDK health check.

Exit codes:
    0: PX4 is ready (global position OK)
    1: Timeout or connection failure
"""
import argparse
import asyncio
from mavsdk import System


async def main(timeout_s: float) -> int:
    drone = System()
    await drone.connect(system_address="udp://:14540")
    try:
        async with asyncio.timeout(timeout_s):
            async for health in drone.telemetry.health():
                if health.is_global_position_ok:
                    return 0
    except TimeoutError:
        return 1
    return 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Wait for PX4 SITL to be ready")
    p.add_argument("--timeout-s", type=float, default=30.0, help="Timeout in seconds (default: 30)")
    args = p.parse_args()
    raise SystemExit(asyncio.run(main(args.timeout_s)))
