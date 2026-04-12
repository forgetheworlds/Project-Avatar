#!/usr/bin/env python3
"""
Camera Tracking and Target Following Demo

Demonstrates advanced tracking capabilities:
1. Orbit around target with camera locked
2. Track moving target (snowboarder simulation)
3. Gimbal control demo
4. Spiral search pattern

Perfect for:
- Cinematic shots
- Search and rescue
- Sports filming (snowboarding, skiing, motocross)
- Surveillance
"""

import asyncio
import json
import sys

sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mcp_server.tools.flight_tools import arm_and_takeoff, land, goto_gps
from avatar.mcp_server.tools.tracking_tools import (
    set_gimbal, point_camera_at, orbit_target, track_target, spiral_search
)


async def demo_orbit():
    """Demo orbiting around target."""
    print("\n[ORBIT DEMO]")
    print("=" * 50)
    print("Flying in circle around target while keeping camera locked...")
    print("Imagine circling a snowboarder waiting at the top of a jump")

    # Orbit with 15m radius, 20m altitude, 30 seconds
    result = json.loads(await orbit_target(
        target_lat=47.397742,  # Example coordinates
        target_lon=8.545594,
        target_alt_m=0.0,
        radius_m=15.0,
        speed_m_s=4.0,
        altitude_offset_m=20.0,
        clockwise=True,
        duration_s=30.0,
        keep_camera_locked=True
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
    """Demo tracking a moving target."""
    print("\n[MOVING TARGET TRACKING DEMO]")
    print("=" * 50)
    print("Following a simulated snowboarder down a hill...")
    print("Target moving at 8 m/s (29 km/h or 18 mph)")

    # Track target moving south at 8 m/s (snowboarder speed)
    result = json.loads(await track_target(
        target_lat=47.397742,
        target_lon=8.545594,
        target_velocity_north=-8.0,  # Moving south
        target_velocity_east=2.0,      # Slightly east
        follow_distance_m=10.0,
        altitude_m=25.0,
        speed_m_s=12.0,
        duration_s=20.0,
        predictive=True,
        tracking_mode="follow"
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
    """Demo gimbal control."""
    print("\n[GIMBAL CONTROL DEMO]")
    print("=" * 50)
    print("Moving camera independently of drone...")

    angles = [
        (-45, 0, "Looking down at 45° (nadir)"),
        (0, 0, "Looking straight ahead (level)"),
        (-60, 45, "Looking down and right"),
        (-30, -90, "Looking down and left"),
        (-45, 180, "Looking down and behind"),
    ]

    for pitch, yaw, description in angles:
        print(f"\n  Setting: {description}")
        result = json.loads(await set_gimbal(
            pitch_deg=pitch,
            yaw_deg=yaw,
            roll_deg=0.0
        ))

        if result.get("success"):
            print(f"  ✓ Gimbal: pitch={result.get('pitch_deg')}°, yaw={result.get('yaw_deg')}°")
        else:
            print(f"  ⚠ {result.get('error', 'Gimbal command failed')}")

        await asyncio.sleep(1.5)


async def demo_spiral_search():
    """Demo spiral search pattern."""
    print("\n[SPIRAL SEARCH DEMO]")
    print("=" * 50)
    print("Expanding spiral search pattern...")
    print("Starting from center and spiraling outward while climbing")

    result = json.loads(await spiral_search(
        center_lat=47.397742,
        center_lon=8.545594,
        start_altitude_m=20.0,
        max_radius_m=80.0,
        max_altitude_m=40.0,
        rotations=2.5,
        speed_m_s=5.0
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
    """Run all tracking demos."""
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

    # Connect
    print("\n[SETUP] Connecting to SITL...")
    cm = ConnectionManager()
    if not await cm.connect("udp://:14540"):
        print("✗ Failed to connect. Is SITL running?")
        return False
    print("✓ Connected")

    try:
        # Takeoff
        print("\n[TAKING OFF] Climbing to 30m...")
        result = json.loads(await arm_and_takeoff(altitude_m=30.0))
        if not result.get("success"):
            print(f"✗ Takeoff failed: {result.get('error')}")
            return False
        print(f"✓ Hovering at {result.get('altitude_m')}m")
        await asyncio.sleep(2)

        # Run demos
        await demo_orbit()
        await demo_tracking()
        await demo_gimbal()
        await demo_spiral_search()

        # Land
        print("\n[LANDING]")
        result = json.loads(await land())
        if result.get("success"):
            print("✓ Landed successfully!")
        else:
            print(f"⚠ Landing: {result.get('error', 'unknown')}")

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
        print("\n\nDemo interrupted - landing...")
        await land()
        return False

    finally:
        await cm.disconnect()


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
