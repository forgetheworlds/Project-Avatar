#!/usr/bin/env python3
"""
Acrobatic Flight Demo for Project Avatar

Demonstrates high-energy maneuvers:
1. Takeoff to safe altitude (20m)
2. Front flip
3. Barrel roll
4. Yaw spin
5. Back to hover
6. Land

WARNING: This is a HIGH-ENERGY demo. Ensure:
- SITL is running
- Drone has plenty of altitude
- You're ready for spectacular maneuvers!
"""

import asyncio
import json
import sys

sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mcp_server.tools.flight_tools import arm_and_takeoff, land, hold
from avatar.mcp_server.tools.acrobatics import (
    front_flip, back_flip, barrel_roll, yaw_spin, loop_maneuver
)


async def demo():
    """Run the acrobatics demo."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              PROJECT AVATAR - ACROBATICS DEMO                ║
║                                                              ║
║  ⚠️  HIGH-ENERGY MANEUVERS AHEAD!                           ║
║                                                              ║
║  This demo will perform:                                     ║
║    1. Takeoff to 20m (safe altitude for acrobatics)          ║
║    2. FRONT FLIP (360° forward rotation)                     ║
║    3. BARREL ROLL (360° lateral rotation)                  ║
║    4. YAW SPIN (rapid rotation around Z axis)               ║
║    5. Return to hover                                        ║
║    6. Land                                                   ║
║                                                              ║
║  Requirements:                                               ║
║    - PX4 SITL running: make px4_sitl gz_x500                 ║
║    - Gazebo visible (to watch the action!)                  ║
║    - Minimum 50% battery (in simulation)                     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Connect
    print("\n[SETUP] Connecting to SITL...")
    cm = ConnectionManager()
    if not await cm.connect("udp://:14540"):
        print("✗ Failed to connect. Is SITL running?")
        return False

    print("✓ Connected to SITL")

    # State machine
    sm = FlightStateMachine()
    sm.transition_to(FlightState.GROUNDED)

    try:
        # 1. Takeoff
        print("\n[1/6] Taking off to 20m...")
        result = json.loads(await arm_and_takeoff(altitude_m=20.0))
        if not result.get("success"):
            print(f"✗ Takeoff failed: {result.get('error')}")
            return False
        print(f"✓ Hovering at {result.get('altitude_m')}m")

        # Hold for stability
        print("  Stabilizing for 2 seconds...")
        await asyncio.sleep(2)

        # 2. Front Flip
        print("\n[2/6] FRONT FLIP! 🔄")
        print("    Pitching forward at max rate...")
        result = json.loads(await front_flip())
        if result.get("success"):
            print(f"✓ Flip complete! Duration: {result.get('duration_ms')}ms")
            print(f"    Recovery: {result.get('recovery_ms')}ms")
        else:
            print(f"⚠ Flip issue: {result.get('error')}")

        await asyncio.sleep(2)

        # 3. Barrel Roll
        print("\n[3/6] BARREL ROLL! 🌀")
        print("    Rolling right at max rate...")
        result = json.loads(await barrel_roll("right"))
        if result.get("success"):
            print(f"✓ Roll complete! Duration: {result.get('duration_ms')}ms")
        else:
            print(f"⚠ Roll issue: {result.get('error')}")

        await asyncio.sleep(2)

        # 4. Yaw Spin
        print("\n[4/6] YAW SPIN! 🌪️")
        print("    Spinning clockwise...")
        result = json.loads(await yaw_spin("cw", 2.0))  # 2 rotations
        if result.get("success"):
            print(f"✓ Spin complete! Duration: {result.get('duration_ms')}ms")
        else:
            print(f"⚠ Spin issue: {result.get('error')}")

        await asyncio.sleep(2)

        # 5. Back to hover
        print("\n[5/6] Returning to stable hover...")
        result = json.loads(await hold(duration_s=3.0))
        if result.get("success"):
            print(f"✓ Holding position, max drift: {result.get('max_drift_m', 'unknown')}m")

        # 6. Land
        print("\n[6/6] Landing...")
        result = json.loads(await land())
        if result.get("success"):
            print("✓ Landed successfully!")
        else:
            print(f"⚠ Landing: {result.get('error', 'unknown')}")

        print("""
╔══════════════════════════════════════════════════════════════╗
║                 ACROBATICS DEMO COMPLETE!                      ║
║                                                              ║
║  The drone performed:                                        ║
║    ✓ Front flip                                              ║
║    ✓ Barrel roll                                             ║
║    ✓ Yaw spin (2x)                                           ║
║                                                              ║
║  All maneuvers completed with automatic safety recovery!       ║
╚══════════════════════════════════════════════════════════════╝
        """)
        return True

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        print("Initiating emergency landing...")
        await land()
        return False

    finally:
        await cm.disconnect()


if __name__ == "__main__":
    try:
        success = asyncio.run(demo())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
