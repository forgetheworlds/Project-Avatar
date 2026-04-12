#!/usr/bin/env python3
"""
Cinematic Shots Demo

Demonstrates professional-quality cinematic shot capabilities:
1. List and preview available shot templates
2. Execute orbit shots around a subject
3. Execute follow shots for action tracking
4. Execute height-locked tracking for tricks

Perfect for:
- Sports filming (snowboarding, skateboarding, motocross)
- Cinematic reveals and establishing shots
- Action sports trick tracking at specific heights
"""

import asyncio
import json
import sys

sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

from avatar.mav.connection_manager import ConnectionManager
from avatar.mcp_server.tools.flight_tools import arm_and_takeoff, land
from avatar.mcp_server.tools.cinematic_shots import (
    list_cinematic_templates,
    preview_cinematic_shot,
    execute_cinematic_shot,
)


async def demo_list_templates():
    """Demo listing available cinematic templates."""
    print("\n[LISTING CINEMATIC TEMPLATES]")
    print("=" * 60)

    result = json.loads(await list_cinematic_templates())

    if result.get("success"):
        print(f"\nFound {result['count']} cinematic shot templates:")
        print("-" * 60)

        for template in result["templates"]:
            height_lock_icon = "🔒" if template["height_lock"] else "  "
            print(f"  {height_lock_icon} {template['name']:25} | {template['display_name']}")
            print(f"      Type: {template['shot_type']}, Distance: {template['distance_m']}m, "
                  f"Height: {template['height_offset_m']}m")
            print()

        print("\n🔒 = Height-locked shot (maintains exact altitude offset)")
    else:
        print(f"✗ Failed to list templates: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_preview_shots():
    """Demo previewing different shot trajectories."""
    print("\n[PREVIEWING SHOT TRAJECTORIES]")
    print("=" * 60)

    # Target location (example: top of a snowboarding run)
    target_lat = 47.397742
    target_lon = 8.545594

    shots_to_preview = [
        ("orbit_close", "Close orbit - tight circle around subject"),
        ("follow_close", "Close follow - tracks action from behind"),
        ("reveal_hero", "Hero reveal - dramatic rising shot"),
        ("snowboard_halfpipe", "Snowboard halfpipe - height-locked for jumps"),
    ]

    for shot_name, description in shots_to_preview:
        print(f"\n  Previewing: {shot_name}")
        print(f"  Description: {description}")

        result = json.loads(await preview_cinematic_shot(
            template_name=shot_name,
            target_lat=target_lat,
            target_lon=target_lon
        ))

        if result.get("success"):
            print(f"    ✓ Estimated duration: {result['estimated_duration_s']:.1f}s")
            print(f"    ✓ Waypoints: {result['total_waypoints']}")
            print(f"    ✓ Motion curve: {result['motion_curve']}")

            if result.get("sample_trajectory"):
                first = result["sample_trajectory"][0]
                print(f"    ✓ Start position: ({first['lat']:.6f}, {first['lon']:.6f}, {first['alt_m']:.1f}m)")
        else:
            print(f"    ⚠ Preview failed: {result.get('error')}")

        await asyncio.sleep(1)


async def demo_orbit_shot():
    """Demo orbit shot execution."""
    print("\n[ORBIT SHOT EXECUTION]")
    print("=" * 60)
    print("Circling target with camera locked...")
    print("Imagine: Filming a snowboarder waiting at the top of a jump")

    result = json.loads(await execute_cinematic_shot(
        template_name="orbit_close",
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=10.0,  # Subject at 10m
        duration_s=15.0  # Shorter demo
    ))

    if result.get("success"):
        print(f"✓ Orbit shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")

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
    """Demo follow shot execution."""
    print("\n[FOLLOW SHOT EXECUTION]")
    print("=" * 60)
    print("Following target dynamically...")
    print("Imagine: Tracking a snowboarder down the slope")

    result = json.loads(await execute_cinematic_shot(
        template_name="follow_close",
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=15.0,
        duration_s=10.0  # Shorter demo
    ))

    if result.get("success"):
        print(f"✓ Follow shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")

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
    """Demo height-locked tracking for tricks."""
    print("\n[HEIGHT-LOCKED TRACKING SHOT]")
    print("=" * 60)
    print("Maintaining exact altitude offset for trick filming...")
    print("Imagine: Capturing a kickflip at exactly 2m height")

    result = json.loads(await execute_cinematic_shot(
        template_name="height_locked_jump",
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=2.0,  # Trick height
        duration_s=8.0
    ))

    if result.get("success"):
        print(f"✓ Height-locked shot complete!")
        print(f"  Duration: {result['duration_s']:.1f}s")
        print(f"  Template: {result['template']}")

        result_data = result.get("result", {})
        if result_data.get("height_lock_maintained"):
            print(f"  ✓ Height lock maintained throughout shot")
            print(f"  ✓ Target offset: {result_data.get('target_offset_m', 0):.1f}m")

        metrics = result.get("quality_metrics", {})
        # Height-locked shots have tighter tolerance
        if metrics.get("avg_height_error_m", 1.0) < 0.3:
            print(f"  ✓ Excellent height accuracy: {metrics['avg_height_error_m']:.2f}m error")
    else:
        print(f"✗ Height-locked shot failed: {result.get('error')}")

    await asyncio.sleep(2)


async def demo_snowboard_halfpipe():
    """Demo snowboard halfpipe optimized shot."""
    print("\n[SNOWBOARD HALFPIPE SHOT]")
    print("=" * 60)
    print("Optimized for halfpipe filming with height-lock...")
    print("Imagine: Following a snowboarder through the pipe")

    result = json.loads(await execute_cinematic_shot(
        template_name="snowboard_halfpipe",
        target_lat=47.397742,
        target_lon=8.545594,
        target_alt_m=5.0,  # Top of pipe
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
    """Run all cinematic shot demos."""
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

    # Connect to SITL
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
        await demo_list_templates()
        await demo_preview_shots()
        await demo_orbit_shot()
        await demo_follow_shot()
        await demo_height_locked_shot()
        await demo_snowboard_halfpipe()

        # Land
        print("\n[LANDING]")
        result = json.loads(await land())
        if result.get("success"):
            print("✓ Landed successfully!")
        else:
            print(f"⚠ Landing: {result.get('error', 'unknown')}")

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
