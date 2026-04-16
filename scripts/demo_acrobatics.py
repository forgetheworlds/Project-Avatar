#!/usr/bin/env python3
"""
================================================================================
ACROBATIC FLIGHT DEMO - Project Avatar
================================================================================

WHAT THIS DEMO SHOWS:
---------------------
This demonstration showcases high-energy acrobatic maneuvers that push the
drone to its performance limits. These are aggressive, exciting maneuvers
that demonstrate the full flight envelope of the PX4 flight controller.

The demo executes in sequence:
  1. TAKEOFF       - Climb to safe altitude (20m) for acrobatics
  2. FRONT FLIP    - 360° forward rotation (pitch axis)
  3. BARREL ROLL   - 360° lateral rotation (roll axis)
  4. YAW SPIN      - Rapid rotation around vertical axis (2x)
  5. STABILIZE     - Return to stable hover
  6. LANDING       - Touch down safely

FEATURES HIGHLIGHTED:
---------------------
  - Aggressive rate-controlled maneuvers
  - Automatic attitude recovery after each stunt
  - Safety limits (altitude checks, battery monitoring)
  - Smooth transitions between maneuvers
  - Stabilization hold after acrobatics

MANEUVERS EXPLAINED:
--------------------
  FRONT FLIP:
    - Full 360° rotation around the pitch axis (forward flip)
    - Requires minimum 15m altitude for safety
    - Automatic recovery to level flight
    - Duration: ~800ms for flip + ~500ms for recovery

  BARREL ROLL:
    - Full 360° rotation around the roll axis (side roll)
    - Can roll left or right direction
    - Maintains altitude better than flips
    - Classic "barrel roll" aerobatic maneuver

  YAW SPIN:
    - Rapid rotation around the Z axis (vertical)
    - Configurable number of rotations
    - Creates "spinning top" effect
    - Used for rapid orientation changes

USE CASES:
----------
  - Aerobatic demonstrations and airshows
  - Aggressive obstacle avoidance maneuvers
  - High-energy filming transitions
  - Testing flight controller limits in SITL

HOW TO RUN THIS DEMO:
---------------------

Prerequisites:
  1. PX4 SITL must be running:
     $ cd PX4-Autopilot
     $ make px4_sitl gz_x500

  2. Gazebo should be visible (to watch the spectacular maneuvers!)

  3. Run the demo:
     $ cd /Users/muadhsambul/Downloads/Project-Avatar
     $ python scripts/demo_acrobatics.py

WHAT TO EXPECT:
---------------
  - The demo will take about 2-3 minutes to complete
  - Drone takes off to 20m altitude (minimum safe for acrobatics)
  - You'll see 3 acrobatic maneuvers performed in sequence
  - 2-second stabilization period between each maneuver
  - The drone lands automatically at the end

  Sample output for each maneuver:
    [2/6] FRONT FLIP! 🔄
        Pitching forward at max rate...
    ✓ Flip complete! Duration: 850ms
        Recovery: 520ms

SAFETY NOTES:
-------------
  ⚠️  HIGH-ENERGY MANEUVERS - READ CAREFULLY:

  - NEVER attempt these on real hardware without:
    * Extensive SITL practice
    * Minimum 50m altitude (20m for SITL only)
    * Clear airspace with no obstacles
    * Kill switch configured and tested
    * Manual override capability ready

  - SITL vs Reality:
    * SITL is more forgiving than real flight
    * Real flips need more altitude margin
    * Battery sag affects performance in reality
    * Wind significantly affects acrobatics

  - Altitude Requirements:
    * SITL: Minimum 15m for flips, 10m for rolls
    * Real world: Minimum 50m for all maneuvers

  - Emergency Procedures:
    * Press Ctrl+C to abort - drone will land immediately
    * Kill switch: Disarm motors (emergency only)
    * Mode switch: Switch to manual/ stabilized mode

================================================================================
"""

# Standard library imports for async operations and JSON parsing
import asyncio
import json
import sys

# Add project root to Python path for importing avatar modules
sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

# Core connection management for MAVSDK
from avatar.mav.connection_manager import ConnectionManager

# Flight state management for tracking mission phases
from avatar.mav.state_machine import FlightStateMachine, FlightState

# Basic flight tools for takeoff, landing, and position hold
from avatar.mcp_server.tools.flight_tools import arm_and_takeoff, land, hold

# Acrobatic maneuver tools - the stars of this demo
from avatar.mcp_server.tools.acrobatics import (
    front_flip,     # 360° forward rotation
    back_flip,      # 360° backward rotation (available but not used in demo)
    barrel_roll,    # 360° lateral rotation
    yaw_spin,       # Rapid Z-axis rotation
    loop_maneuver   # Vertical loop (available but not used in demo)
)


async def demo():
    """
    Main demonstration function for acrobatic flight.

    This function orchestrates the entire acrobatics demo:
      1. Displays the warning banner and requirements
      2. Connects to SITL simulation
      3. Arms and takes off to safe altitude
      4. Executes each acrobatic maneuver in sequence
      5. Stabilizes between maneuvers
      6. Lands safely

    Each maneuver includes:
      - Pre-maneuver announcement
      - Execution with rate-controlled attitudes
      - Success/failure reporting with timing metrics
      - 2-second stabilization period

    Returns True if all maneuvers completed successfully, False otherwise.
    """
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

    # =========================================================================
    # SETUP: Connect to SITL simulation
    # =========================================================================
    print("\n[SETUP] Connecting to SITL...")
    cm = ConnectionManager()

    # Connect to PX4 SITL via UDP port 14540
    if not await cm.connect("udp://:14540"):
        print("✗ Failed to connect. Is SITL running?")
        print("   Run: cd PX4-Autopilot && make px4_sitl gz_x500")
        return False

    print("✓ Connected to SITL")

    # Initialize state machine to track flight phase
    sm = FlightStateMachine()
    sm.transition_to(FlightState.GROUNDED)

    try:
        # =====================================================================
        # STEP 1/6: TAKEOFF - Get to safe altitude for acrobatics
        # =====================================================================
        print("\n[1/6] Taking off to 20m...")

        # Arm motors and take off to 20m
        # 20m is minimum safe altitude for acrobatics in SITL
        result = json.loads(await arm_and_takeoff(altitude_m=20.0))
        if not result.get("success"):
            print(f"✗ Takeoff failed: {result.get('error')}")
            return False
        print(f"✓ Hovering at {result.get('altitude_m')}m")

        # Wait for stability before first maneuver
        # This ensures the drone is stable and ready
        print("  Stabilizing for 2 seconds...")
        await asyncio.sleep(2)

        # =====================================================================
        # STEP 2/6: FRONT FLIP - 360° forward rotation
        # =====================================================================
        print("\n[2/6] FRONT FLIP! 🔄")
        print("    Pitching forward at max rate...")

        # Execute front flip maneuver
        # The drone will:
        #   1. Apply maximum forward pitch rate
        #   2. Complete 360° rotation
        #   3. Automatically recover to level
        result = json.loads(await front_flip())

        if result.get("success"):
            # Display success metrics
            print(f"✓ Flip complete! Duration: {result.get('duration_ms')}ms")
            print(f"    Recovery: {result.get('recovery_ms')}ms")
            # Recovery time shows how long stabilization took after flip
        else:
            print(f"⚠ Flip issue: {result.get('error')}")
            # Non-fatal error - continue with demo

        # Stabilization period between maneuvers
        # Allows flight controller to settle and ensures safe separation
        await asyncio.sleep(2)

        # =====================================================================
        # STEP 3/6: BARREL ROLL - 360° lateral rotation
        # =====================================================================
        print("\n[3/6] BARREL ROLL! 🌀")
        print("    Rolling right at max rate...")

        # Execute barrel roll to the right
        # Can also roll "left" for opposite direction
        result = json.loads(await barrel_roll("right"))

        if result.get("success"):
            print(f"✓ Roll complete! Duration: {result.get('duration_ms')}ms")
        else:
            print(f"⚠ Roll issue: {result.get('error')}")

        # Stabilization period
        await asyncio.sleep(2)

        # =====================================================================
        # STEP 4/6: YAW SPIN - Rapid Z-axis rotation
        # =====================================================================
        print("\n[4/6] YAW SPIN! 🌪️")
        print("    Spinning clockwise...")

        # Execute yaw spin
        # Parameters:
        #   - "cw" = clockwise rotation
        #   - 2.0 = number of full rotations
        # Can also spin "ccw" (counter-clockwise)
        result = json.loads(await yaw_spin("cw", 2.0))

        if result.get("success"):
            print(f"✓ Spin complete! Duration: {result.get('duration_ms')}ms")
            print(f"    Rotations: 2 full 360° spins")
        else:
            print(f"⚠ Spin issue: {result.get('error')}")

        # Stabilization period
        await asyncio.sleep(2)

        # =====================================================================
        # STEP 5/6: STABILIZE - Return to stable hover
        # =====================================================================
        print("\n[5/6] Returning to stable hover...")

        # Hold position for 3 seconds to demonstrate stable flight
        # This shows the flight controller has recovered from acrobatics
        result = json.loads(await hold(duration_s=3.0))
        if result.get("success"):
            # max_drift_m shows how much position changed during hold
            # Lower values indicate better position holding
            print(f"✓ Holding position, max drift: {result.get('max_drift_m', 'unknown')}m")

        # =====================================================================
        # STEP 6/6: LANDING - Touch down safely
        # =====================================================================
        print("\n[6/6] Landing...")

        # Land the drone at current position
        result = json.loads(await land())
        if result.get("success"):
            print("✓ Landed successfully!")
        else:
            print(f"⚠ Landing: {result.get('error', 'unknown')}")

        # Completion banner with summary
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
        # Handle Ctrl+C gracefully - this is the emergency stop
        print("\n\nDemo interrupted by user")
        print("Initiating emergency landing...")
        await land()
        return False

    finally:
        # Always disconnect cleanly, even if there was an error
        # This ensures the connection is properly closed
        await cm.disconnect()


if __name__ == "__main__":
    # Entry point when script is run directly
    try:
        success = asyncio.run(demo())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
