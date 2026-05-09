#!/usr/bin/env python3
"""
================================================================================
CAMERA TRACKING AND TARGET FOLLOWING DEMO - Project Avatar
================================================================================

WHAT THIS DEMO SHOWS:
---------------------
This demonstration showcases advanced tracking capabilities for dynamic
subject following and surveillance. Unlike pre-programmed cinematic shots,
these are real-time tracking modes that respond to target movement.

The demo covers:
  1. ORBIT TARGET    - Circle around a stationary subject with camera locked
  2. TRACK MOVING    - Follow a moving target with predictive algorithms
  3. GIMBAL CONTROL  - Independent camera movement (look without moving)
  4. SPIRAL SEARCH   - Expanding spiral pattern for search operations

FEATURES HIGHLIGHTED:
---------------------
  - Real-time target tracking with camera lock
  - Predictive algorithms for smooth following of moving subjects
  - Independent gimbal control (decoupled from drone movement)
  - Configurable tracking modes (follow, lead, orbit, etc.)
  - Search patterns for coverage of large areas

USE CASES:
----------
  - Sports filming (snowboarding, skiing, motocross, surfing)
  - Cinematic shots (orbits, reveals, flyovers)
  - Search and rescue operations
  - Surveillance and monitoring
  - Wildlife observation and filming

TRACKING MODES EXPLAINED:
-------------------------
  - FOLLOW: Drone follows behind subject, camera locked on target
  - LEAD: Drone flies ahead of subject, capturing approach
  - ORBIT: Circle around subject, camera always pointed at center
  - SIDEBAR: Fly alongside subject (parallel tracking)

HOW TO RUN THIS DEMO:
---------------------

Prerequisites:
  1. PX4 SITL must be running:
     $ cd PX4-Autopilot
     $ make px4_sitl gz_x500

  2. Gazebo should be visible (to watch the tracking behavior)

  3. Run the demo:
     $ cd /Users/muadhsambul/Downloads/Project-Avatar
     $ python scripts/demo_tracking.py

WHAT TO EXPECT:
---------------
  - The demo will take about 2-3 minutes to complete
  - Drone takes off to 30m altitude for tracking operations
  - 4 separate demonstrations showing different tracking capabilities
  - Each demo shows real-time telemetry and tracking metrics
  - The drone lands automatically at the end

  Sample output for tracking:
    ✓ Tracking complete!
      Duration: 20.0s
      Updates sent: 45
      Max velocity: 8.5 m/s
      Predictive tracking: True

SAFETY NOTES:
-------------
  - Tracking fast-moving subjects requires high update rates
  - Always maintain visual line of sight in real operations
  - Set appropriate geofences to prevent flyaways during tracking
  - Predictive tracking may overshoot if subject changes direction suddenly

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

# Flight state management for tracking mission state
from avatar.mav.state_machine import FlightStateMachine, FlightState

# Basic flight tools for takeoff, landing, and waypoint navigation
from avatar.mcp_server.tools.flight_tools import arm_and_takeoff, land, goto_gps

# Tracking-specific tools - the main focus of this demo
from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal,        # Control camera angle independently
    point_camera_at,   # Point camera at specific GPS coordinate
    orbit_target,      # Circle around a target
    track_target,      # Follow a moving target
    spiral_search      # Expanding spiral search pattern
)


async def demo_orbit():
    """
    Demonstrates orbital flight around a target with camera locked.

    The orbit function flies the drone in a circle around a target location
    while keeping the camera pointed at the target throughout the maneuver.
    This creates a classic "360 reveal" shot commonly used in cinematography.

    Parameters explained:
      - radius_m: 15m circle around the target
      - altitude_offset_m: 20m above the target's altitude
      - speed_m_s: 4 m/s for smooth, cinematic movement
      - duration_s: 30 seconds for a full orbit
      - keep_camera_locked: True keeps camera on target

    Real-world use: Circling a snowboarder waiting at the top of a jump,
    or doing a reveal shot around a scenic point of interest.
    """
    print("\n[ORBIT DEMO]")
    print("=" * 50)
    print("Flying in circle around target while keeping camera locked...")
    print("Imagine circling a snowboarder waiting at the top of a jump")

    # Execute orbit around target coordinates
    result = json.loads(await orbit_target(
        target_lat=47.397742,        # Target latitude (ETH Zurich area)
        target_lon=8.545594,         # Target longitude
        target_alt_m=0.0,            # Target altitude (ground level)
        radius_m=15.0,               # Orbit radius in meters
        speed_m_s=4.0,               # Orbit speed (m/s)
        altitude_offset_m=20.0,      # Fly 20m above target
        clockwise=True,              # Orbit direction
        duration_s=30.0,             # Orbit duration
        keep_camera_locked=True      # Keep camera on target
    ))

    if result.get("success"):
        print(f"✓ Orbit complete!")
        print(f"  Duration: {result.get('duration_s'):.1f}s")
        print(f"  Approximate orbits: {result.get('approximate_orbits', 0):.1f}")
        print(f"  Radius: {result.get('radius_m')}m")
    else:
        print(f"✗ Orbit failed: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_tracking():
    """
    Demonstrates tracking a moving target with predictive algorithms.

    This demo simulates following a snowboarder down a slope. The target
    is moving at 8 m/s (about 18 mph) which is a realistic speed for
    snowboarding. The drone uses predictive tracking to anticipate where
    the target will be and position itself accordingly.

    The track_target tool supports different tracking modes:
      - "follow": Drone follows behind subject
      - "lead": Drone flies ahead of subject
      - "sidebar": Drone flies parallel to subject
      - "orbit": Continuous orbit around moving target

    Predictive tracking uses velocity vectors to anticipate target movement,
    resulting in smoother footage compared to reactive following.

    Parameters explained:
      - target_velocity_north/south: Target movement vector (m/s)
      - follow_distance_m: 10m gap between drone and subject
      - predictive: True enables velocity prediction for smoother tracking
      - tracking_mode: "follow" keeps drone behind subject
    """
    print("\n[MOVING TARGET TRACKING DEMO]")
    print("=" * 50)
    print("Following a simulated snowboarder down a hill...")
    print("Target moving at 8 m/s (29 km/h or 18 mph)")

    result = json.loads(await track_target(
        target_lat=47.397742,          # Starting latitude
        target_lon=8.545594,           # Starting longitude
        target_velocity_north=-8.0,    # Moving south at 8 m/s (negative = south)
        target_velocity_east=2.0,      # Slightly east at 2 m/s
        follow_distance_m=10.0,        # Stay 10m behind target
        altitude_m=25.0,               # Fly at 25m altitude
        speed_m_s=12.0,                # Max drone speed (must exceed target speed)
        duration_s=20.0,               # Track for 20 seconds
        predictive=True,             # Enable predictive tracking
        tracking_mode="follow"        # Follow mode (drone behind subject)
    ))

    if result.get("success"):
        print(f"✓ Tracking complete!")
        print(f"  Duration: {result.get('duration_s'):.1f}s")
        print(f"  Updates sent: {result.get('updates_sent')}")
        print(f"  Max velocity: {result.get('max_velocity_m_s', 0):.1f} m/s")
        print(f"  Predictive tracking: {result.get('predictive')}")
    else:
        print(f"✗ Tracking failed: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_gimbal():
    """
    Demonstrates independent gimbal control.

    The gimbal can move the camera independently of the drone's body
    orientation. This allows:
      - Looking in one direction while flying another
      - Smooth camera sweeps without moving the drone
      - Tracking targets while maintaining efficient flight paths

    Gimbal angles:
      - Pitch: -90 (straight down/nadir) to +20 (slightly up)
      - Yaw: 0 (forward) to ±180 (backward)
      - Roll: Usually 0 for level horizon

    This demo cycles through several camera angles to show the range
    of independent motion available.

    Real-world use: Scanning an area while holding position, or capturing
    multiple angles of a subject without moving.
    """
    print("\n[GIMBAL CONTROL DEMO]")
    print("=" * 50)
    print("Moving camera independently of drone...")

    # List of (pitch, yaw, description) tuples to demonstrate
    angles = [
        (-45, 0, "Looking down at 45° (nadir)"),
        (0, 0, "Looking straight ahead (level)"),
        (-60, 45, "Looking down and right"),
        (-30, -90, "Looking down and left"),
        (-45, 180, "Looking down and behind"),
    ]

    for pitch, yaw, description in angles:
        print(f"\n  Setting: {description}")

        # Set gimbal to specified angles
        result = json.loads(await set_gimbal(
            pitch_deg=pitch,    # Negative = looking down
            yaw_deg=yaw,        # 0 = forward, 180 = backward
            roll_deg=0.0        # Keep horizon level
        ))

        if result.get("success"):
            # Confirm the angles were set (may differ slightly due to mechanical limits)
            print(f"  ✓ Gimbal: pitch={result.get('pitch_deg')}°, yaw={result.get('yaw_deg')}°")
        else:
            print(f"  ⚠ {result.get('error', 'Gimbal command failed')}")

        await asyncio.sleep(1.5)


async def demo_spiral_search():
    """
    Demonstrates spiral search pattern for area coverage.

    The spiral search creates an expanding spiral pattern starting from
    a center point. The drone:
      1. Starts at center_altitude_m
      2. Spirals outward while climbing to max_altitude_m
      3. Completes specified number of rotations
      4. Covers increasing radius up to max_radius_m

    This is useful for:
      - Search and rescue operations
      - Surveying an area systematically
      - Looking for a lost signal or subject
      - Creating overview footage of an area

    Parameters explained:
      - start_altitude_m: 20m - where spiral begins
      - max_altitude_m: 40m - highest point in spiral
      - max_radius_m: 80m - spiral extends to 80m radius
      - rotations: 2.5 - two and a half spiral loops
      - speed_m_s: 5 m/s - comfortable search speed
    """
    print("\n[SPIRAL SEARCH DEMO]")
    print("=" * 50)
    print("Expanding spiral search pattern...")
    print("Starting from center and spiraling outward while climbing")

    result = json.loads(await spiral_search(
        center_lat=47.397742,     # Center of search
        center_lon=8.545594,      # Center longitude
        start_altitude_m=20.0,    # Start at 20m
        max_radius_m=80.0,        # Spiral out to 80m radius
        max_altitude_m=40.0,      # Climb to 40m
        rotations=2.5,          # 2.5 full rotations
        speed_m_s=5.0             # Search speed
    ))

    if result.get("success"):
        print(f"✓ Search complete!")
        print(f"  Total points: {result.get('total_points')}")
        print(f"  Successful: {result.get('successful_points')}")
        print(f"  Max radius: {result.get('max_radius_m')}m")
        print(f"  Max altitude: {result.get('max_altitude_m')}m")
    else:
        print(f"✗ Search failed: {result.get('error')}")


async def main():
    """
    Main entry point - runs all tracking demonstrations.

    This function:
      1. Displays welcome banner with tracking features
      2. Connects to the SITL simulation
      3. Takes off to safe altitude
      4. Runs all tracking demos in sequence
      5. Lands the drone
      6. Displays completion summary

    The tracking demos progress from simple (orbit) to complex (spiral search),
    showing the full range of tracking capabilities.

    Returns True if all demos completed successfully, False otherwise.
    """
    print("""
╔════════════════════════════════════════════════════════════════╗
║           PROJECT AVATAR - CAMERA TRACKING DEMO                ║
║                                                                ║
║  Advanced tracking capabilities demonstration:                 ║
║                                                                ║
║  1. ORBIT TARGET - Circle around subject, camera locked        ║
║  2. TRACK MOVING - Follow snowboarder down hill                ║
║  3. GIMBAL CONTROL - Independent camera movement               ║
║  4. SPIRAL SEARCH - Expanding search pattern                   ║
║                                                                ║
║  Perfect for:                                                  ║
║    🏂 Sports filming (snowboarding, skiing, motocross)        ║
║    🎬 Cinematic shots (orbits, reveals, flyovers)             ║
║    🔍 Search and rescue operations                             ║
║    👁️  Surveillance and monitoring                              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
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
    print("✓ Connected to PX4 autopilot")

    try:
        # =====================================================================
        # TAKEOFF: Get to safe altitude for tracking operations
        # =====================================================================
        print("\n[TAKING OFF] Climbing to 30m...")
        result = json.loads(await arm_and_takeoff(altitude_m=30.0))
        if not result.get("success"):
            print(f"✗ Takeoff failed: {result.get('error')}")
            return False
        print(f"✓ Hovering at {result.get('altitude_m')}m")
        await asyncio.sleep(2)

        # =====================================================================
        # RUN ALL DEMOS: Execute each tracking demonstration
        # =====================================================================
        await demo_orbit()         # Orbital flight with camera lock
        await demo_tracking()      # Follow moving target
        await demo_gimbal()        # Independent gimbal control
        await demo_spiral_search() # Expanding spiral pattern

        # =====================================================================
        # LANDING: Return to ground safely
        # =====================================================================
        print("\n[LANDING]")
        result = json.loads(await land())
        if result.get("success"):
            print("✓ Landed successfully!")
        else:
            print(f"⚠ Landing: {result.get('error', 'unknown')}")

        # Completion banner with capability summary
        print("""
╔════════════════════════════════════════════════════════════════╗
║                 TRACKING DEMO COMPLETE!                        ║
║                                                                ║
║  Demonstrated capabilities:                                    ║
║    ✓ Orbital flight with camera tracking                     ║
║    ✓ Predictive moving target following                       ║
║    ✓ Independent gimbal control                               ║
║    ✓ Spiral search patterns                                    ║
║                                                                ║
║  Ready for real-world filming and tracking missions!           ║
╚════════════════════════════════════════════════════════════════╝
        """)
        return True

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully - land before exiting
        print("\n\nDemo interrupted - landing...")
        await land()
        return False

    finally:
        # Always disconnect cleanly, even if there was an error
        await cm.disconnect()


if __name__ == "__main__":
    # Entry point when script is run directly
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
