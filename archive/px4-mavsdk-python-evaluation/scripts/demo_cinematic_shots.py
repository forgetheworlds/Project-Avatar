#!/usr/bin/env python3
"""
================================================================================
CINEMATIC SHOTS DEMO - Project Avatar
================================================================================

WHAT THIS DEMO SHOWS:
---------------------
This demonstration showcases professional-quality drone cinematography using
pre-programmed cinematic shot templates. The drone autonomously executes
smooth, cinematic movements that would typically require an experienced
human pilot with specialized equipment.

The demo covers:
  1. Template Discovery - View all available cinematic shot types
  2. Shot Previewing - See trajectory and timing without flying
  3. Orbit Shots - Circle around a subject with camera locked
  4. Follow Shots - Track moving subjects dynamically
  5. Height-Locked Shots - Maintain exact altitude offset (for tricks)
  6. Sport-Specific Templates - Optimized for snowboarding, skateboarding

FEATURES HIGHLIGHTED:
---------------------
  - Motion curves (ease-in-out, exponential, linear) for smooth footage
  - Automatic framing (rule of thirds, lead room) for professional shots
  - Height-locked tracking with ±0.2m accuracy for action sports
  - Quality metrics (position error, smoothness, framing score)
  - 11 pre-programmed templates ready to use

USE CASES:
----------
  - Sports filming (snowboarding, skateboarding, motocross, surfing)
  - Cinematic reveals and establishing shots for video production
  - Action sports trick tracking at specific heights
  - Automated B-roll footage collection

HOW TO RUN THIS DEMO:
---------------------

Prerequisites:
  1. PX4 SITL must be running:
     $ cd PX4-Autopilot
     $ make px4_sitl gz_x500

  2. Gazebo should be visible (to watch the cinematic movements)

  3. Run the demo:
     $ cd /Users/muadhsambul/Downloads/Project-Avatar
     $ python scripts/demo_cinematic_shots.py

WHAT TO EXPECT:
---------------
  - The demo will take about 3-4 minutes to complete
  - Drone takes off to 30m altitude for safe maneuvering space
  - You'll see 6 separate demonstrations, each with printed output
  - After each shot, quality metrics show how accurate the flight was
  - The drone lands automatically at the end

  Sample output for each shot:
    ✓ Orbit shot complete!
      Duration: 15.0s
      Quality Metrics:
        - Avg position error: 0.12m
        - Avg height error: 0.08m
        - Avg framing score: 0.95

SAFETY NOTES:
-------------
  - Always run in SITL simulation first before attempting on real hardware
  - Real-world cinematic shots need proper geofencing and kill switch setup
  - Height-locked shots require excellent GPS signal and calibrated barometer

================================================================================
"""

# Standard library imports - asyncio for async/await, json for parsing tool results
import asyncio
import json
import sys

# Add the project root to Python path so we can import avatar modules
# This allows importing from avatar/ regardless of where the script is run from
sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

# ConnectionManager handles MAVSDK connection to the PX4 autopilot
from avatar.mav.connection_manager import ConnectionManager

# Basic flight tools for takeoff and landing operations
from avatar.mcp_server.tools.flight_tools import arm_and_takeoff, land

# Cinematic shot-specific tools - these are the stars of this demo
from avatar.mcp_server.tools.cinematic_shots import (
    list_cinematic_templates,    # Get list of available shot templates
    preview_cinematic_shot,       # Preview trajectory without flying
    execute_cinematic_shot,       # Actually perform the shot
)


async def demo_list_templates():
    """
    Demonstrates listing all available cinematic shot templates.

    This shows what shots are available in the system before executing any.
    Templates include orbit variations, follow shots, reveals, and sport-specific
    shots like 'snowboard_halfpipe' and 'skate_stairset'.
    """
    print("\n[LISTING CINEMATIC TEMPLATES]")
    print("=" * 60)

    # Call the tool to get all available templates
    # Result is a JSON string that we parse into a Python dict
    result = json.loads(await list_cinematic_templates())

    if result.get("success"):
        # Print summary of available templates
        print(f"\nFound {result['count']} cinematic shot templates:")
        print("-" * 60)

        # Iterate through each template and display its properties
        for template in result["templates"]:
            # Height lock icon - 🔒 means the shot maintains exact altitude
            # This is critical for filming tricks where subject height matters
            height_lock_icon = "🔒" if template["height_lock"] else "  "
            print(f"  {height_lock_icon} {template['name']:25} | {template['display_name']}")
            print(f"      Type: {template['shot_type']}, Distance: {template['distance_m']}m, "
                  f"Height: {template['height_offset_m']}m")
            print()

        print("\n🔒 = Height-locked shot (maintains exact altitude offset)")
    else:
        print(f"✗ Failed to list templates: {result.get('error')}")

    # Pause between demos so user can read output
    await asyncio.sleep(2)


async def demo_preview_shots():
    """
    Demonstrates previewing shot trajectories before execution.

    Previewing allows you to see the flight path, timing, and waypoints
    without actually flying. This is useful for planning and checking if
    the shot will work for your scene.

    We preview 4 different shot types to show the variety available.
    """
    print("\n[PREVIEWING SHOT TRAJECTORIES]")
    print("=" * 60)

    # Target location - in a real scenario, this would be your subject's GPS position
    # Using Zurich coordinates (47.397742, 8.545594) as example location
    # This is near ETH Zurich where PX4 is developed
    target_lat = 47.397742
    target_lon = 8.545594

    # List of shots to preview with descriptions
    shots_to_preview = [
        ("orbit_close", "Close orbit - tight circle around subject"),
        ("follow_close", "Close follow - tracks action from behind"),
        ("reveal_hero", "Hero reveal - dramatic rising shot"),
        ("snowboard_halfpipe", "Snowboard halfpipe - height-locked for jumps"),
    ]

    for shot_name, description in shots_to_preview:
        print(f"\n  Previewing: {shot_name}")
        print(f"  Description: {description}")

        # Call preview tool - this calculates the trajectory without flying
        result = json.loads(await preview_cinematic_shot(
            template_name=shot_name,
            target_lat=target_lat,
            target_lon=target_lon
        ))

        if result.get("success"):
            # Display preview results
            print(f"    ✓ Estimated duration: {result['estimated_duration_s']:.1f}s")
            print(f"    ✓ Waypoints: {result['total_waypoints']}")
            print(f"    ✓ Motion curve: {result['motion_curve']}")

            # Show first waypoint as example
            if result.get("sample_trajectory"):
                first = result["sample_trajectory"][0]
                print(f"    ✓ Start position: ({first['lat']:.6f}, {first['lon']:.6f}, {first['alt_m']:.1f}m)")
        else:
            print(f"    ⚠ Preview failed: {result.get('error')}")

        await asyncio.sleep(1)


async def demo_orbit_shot():
    """
    Demonstrates an orbit shot - circling around a target with camera locked.

    The orbit shot flies in a circle around the subject, keeping the camera
    pointed at the target throughout. This is a classic cinematic technique
    used in everything from nature documentaries to action sports.

    Imagine: Filming a snowboarder waiting at the top of a jump, or capturing
    a dramatic reveal shot around a subject.
    """
    print("\n[ORBIT SHOT EXECUTION]")
    print("=" * 60)
    print("Circling target with camera locked...")
    print("Imagine: Filming a snowboarder waiting at the top of a jump")

    # Execute the orbit shot
    result = json.loads(await execute_cinematic_shot(
        template_name="orbit_close",      # Close orbit template (tight circle)
        target_lat=47.397742,              # Target latitude
        target_lon=8.545594,               # Target longitude
        target_alt_m=10.0,                 # Subject is at 10m elevation
        duration_s=15.0                    # 15 seconds for demo (can be longer)
    ))

    if result.get("success"):
        print(f"✓ Orbit shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")

        # Display quality metrics - these show how accurate the flight was
        metrics = result.get("quality_metrics", {})
        print(f"  Quality Metrics:")
        print(f"    - Avg position error: {metrics.get('avg_position_error_m', 0):.2f}m")
        print(f"    - Avg height error: {metrics.get('avg_height_error_m', 0):.2f}m")
        print(f"    - Avg framing score: {metrics.get('avg_framing_score', 0):.2f}")
        print(f"    - Samples collected: {metrics.get('samples_collected', 0)}")
    else:
        print(f"✗ Orbit shot failed: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_follow_shot():
    """
    Demonstrates a follow shot - tracking a target from behind.

    The follow shot maintains a set distance behind the subject, perfect
    for tracking action as it moves. The camera stays locked on the target
    while the drone maintains relative position.

    Imagine: Tracking a snowboarder down the slope from behind, keeping them
    centered in frame as they carve turns.
    """
    print("\n[FOLLOW SHOT EXECUTION]")
    print("=" * 60)
    print("Following target dynamically...")
    print("Imagine: Tracking a snowboarder down the slope")

    result = json.loads(await execute_cinematic_shot(
        template_name="follow_close",     # Close follow template
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=15.0,                 # 15m above target
        duration_s=10.0                    # Shorter demo duration
    ))

    if result.get("success"):
        print(f"✓ Follow shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")

        # Show the parameters that were used for this shot
        params = result.get("parameters_used", {})
        print(f"  Shot Parameters:")
        print(f"    - Distance: {params.get('distance_m', 0):.1f}m")
        print(f"    - Height offset: {params.get('height_offset_m', 0):.1f}m")
        print(f"    - Speed: {params.get('speed_m_s', 0):.1f}m/s")
        print(f"    - Motion curve: {params.get('motion_curve', 'unknown')}")
    else:
        print(f"✗ Follow shot failed: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_height_locked_shot():
    """
    Demonstrates height-locked tracking for filming tricks.

    Height-locked shots maintain an exact altitude offset from the target,
    regardless of the drone's position. This is critical for action sports
    where you want to capture a trick at a specific height (e.g., a kickflip
    at exactly 2m above ground).

    The ±0.2m accuracy ensures consistent framing for the critical moment.

    Imagine: Capturing a kickflip at exactly 2m height, with the drone
    maintaining that exact altitude offset even as the subject moves.
    """
    print("\n[HEIGHT-LOCKED TRACKING SHOT]")
    print("=" * 60)
    print("Maintaining exact altitude offset for trick filming...")
    print("Imagine: Capturing a kickflip at exactly 2m height")

    result = json.loads(await execute_cinematic_shot(
        template_name="height_locked_jump",  # Template optimized for jump filming
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=2.0,                    # Trick height - locked precisely
        duration_s=8.0
    ))

    if result.get("success"):
        print(f"✓ Height-locked shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")

        # Check if height lock was maintained throughout
        result_data = result.get("result", {})
        if result_data.get("height_lock_maintained"):
            print(f"  ✓ Height lock maintained throughout shot")
            print(f"  ✓ Target offset: {result_data.get('target_offset_m', 0):.1f}m")

        # Height-locked shots have tighter tolerance requirements
        metrics = result.get("quality_metrics", {})
        if metrics.get("avg_height_error_m", 1.0) < 0.3:
            print(f"  ✓ Excellent height accuracy: {metrics['avg_height_error_m']:.2f}m error")
    else:
        print(f"✗ Height-locked shot failed: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_snowboard_halfpipe():
    """
    Demonstrates snowboard halfpipe optimized shot.

    This is a sport-specific template optimized for halfpipe filming.
    It combines height-locked tracking with lateral offset positioning
    to capture the snowboarder as they transition up the pipe walls.

    The shot is designed to stay at the top of the pipe (where the
    snowboarder gets air) while maintaining proper distance for safety.

    Imagine: Following a snowboarder through the halfpipe, capturing them
    at the top of each wall transition.
    """
    print("\n[SNOWBOARD HALFPIPE SHOT]")
    print("=" * 60)
    print("Optimized for halfpipe filming with height-lock...")
    print("Imagine: Following a snowboarder through the pipe")

    result = json.loads(await execute_cinematic_shot(
        template_name="snowboard_halfpipe",  # Sport-specific template
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=5.0,                  # Top of pipe height
        duration_s=12.0
    ))

    if result.get("success"):
        print(f"✓ Halfpipe shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")
        print(f"  Shot type: Height-locked tracking with lateral offset")

        metrics = result.get("quality_metrics", {})
        print(f"  Quality:")
        print(f"    - Position error: {metrics.get('avg_position_error_m', 0):.2f}m")
        print(f"    - Height accuracy: {metrics.get('avg_height_error_m', 0):.2f}m")
    else:
        print(f"✗ Halfpipe shot failed: {result.get('error')}")

    await asyncio.sleep(2)


async def main():
    """
    Main entry point - runs all cinematic shot demonstrations.

    This function:
      1. Displays welcome banner with feature overview
      2. Connects to the SITL simulation
      3. Takes off to safe altitude
      4. Runs all demo functions in sequence
      5. Lands the drone
      6. Displays completion summary

    Returns True if all demos completed successfully, False otherwise.
    """
    print("""
╔════════════════════════════════════════════════════════════════╗
║           PROJECT AVATAR - CINEMATIC SHOTS DEMO                ║
║                                                                ║
║  Professional-quality drone filming for action sports:       ║
║                                                                ║
║  🎬 ORBIT        - Circle around subject, camera locked      ║
║  🏂 FOLLOW       - Track snowboarder down the hill            ║
║  🔒 HEIGHT-LOCK - Exact altitude for trick filming          ║
║  🏔️  HALFPIPE    - Optimized for snowboarding pipes            ║
║                                                                ║
║  Features:                                                     ║
║    ✓ Motion curves (ease-in-out, exponential, linear)        ║
║    ✓ Automatic framing (rule of thirds, lead room)          ║
║    ✓ Height-locked tracking (±0.2m accuracy)                ║
║    ✓ Quality metrics (position error, smoothness)          ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # =========================================================================
    # SETUP: Connect to SITL simulation
    # =========================================================================
    print("\n[SETUP] Connecting to SITL...")
    cm = ConnectionManager()

    # Connect to PX4 SITL via UDP on port 14540 (standard SITL port)
    if not await cm.connect("udp://:14540"):
        print("✗ Failed to connect. Is SITL running?")
        print("   Run: cd PX4-Autopilot && make px4_sitl gz_x500")
        return False
    print("✓ Connected to PX4 autopilot")

    try:
        # =====================================================================
        # TAKEOFF: Get to safe altitude for maneuvering
        # =====================================================================
        print("\n[TAKING OFF] Climbing to 30m...")
        result = json.loads(await arm_and_takeoff(altitude_m=30.0))
        if not result.get("success"):
            print(f"✗ Takeoff failed: {result.get('error')}")
            return False
        print(f"✓ Hovering at {result.get('altitude_m')}m")
        await asyncio.sleep(2)

        # =====================================================================
        # RUN ALL DEMOS: Execute each cinematic shot demonstration
        # =====================================================================
        await demo_list_templates()      # Show available shot templates
        await demo_preview_shots()       # Preview trajectories
        await demo_orbit_shot()          # Execute orbit shot
        await demo_follow_shot()         # Execute follow shot
        await demo_height_locked_shot()  # Execute height-locked shot
        await demo_snowboard_halfpipe()  # Execute sport-specific shot

        # =====================================================================
        # LANDING: Return to ground safely
        # =====================================================================
        print("\n[LANDING]")
        result = json.loads(await land())
        if result.get("success"):
            print("✓ Landed successfully!")
        else:
            print(f"⚠ Landing: {result.get('error', 'unknown')}")

        # Completion banner with summary
        print("""
╔════════════════════════════════════════════════════════════════╗
║              CINEMATIC SHOTS DEMO COMPLETE!                    ║
║                                                                ║
║  Demonstrated capabilities:                                    ║
║    ✓ 11 pre-programmed cinematic shot templates              ║
║    ✓ Orbit shots with smooth motion curves                   ║
║    ✓ Follow shots with predictive tracking                   ║
║    ✓ Height-locked tracking for trick filming              ║
║    ✓ Sport-specific templates (snowboard, skate)             ║
║    ✓ Quality metrics and shot validation                   ║
║                                                                ║
║  Ready for professional action sports filming!                ║
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
