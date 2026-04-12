#!/usr/bin/env python3
"""
End-to-End MCP Real-Time Drone Control Test

Tests the complete MCP server with real-time flight control:
1. Connect to SITL
2. Arm and takeoff
3. Real-time velocity control (20Hz streaming)
4. Position hold
5. Body-relative movement
6. Return to launch

This test validates that Claude Code can control the drone in real-time
through the MCP protocol.
"""

import asyncio
import json
import sys
import time
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')

from avatar.mav.connection_manager import ConnectionManager
from avatar.mav.telemetry_cache import TelemetryCache
from avatar.mav.heartbeat_service import HeartbeatService, HeartbeatConfig
from avatar.mav.state_machine import FlightStateMachine, FlightState
from avatar.mcp_server.tools.flight_tools import (
    FlightTools, arm_and_takeoff, land, rtl, goto_gps,
    fly_body_offset, set_velocity, hold
)
from avatar.mcp_server.tools.telemetry_tools import get_telemetry, get_status


class MCPRealtimeTest:
    """End-to-end real-time control test via MCP."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.connection_manager = ConnectionManager()
        self.telemetry_cache = TelemetryCache()
        self.state_machine = FlightStateMachine()
        self.flight_tools = FlightTools()

    async def setup(self) -> bool:
        """Initialize all components."""
        print("\n" + "="*60)
        print("MCP REAL-TIME DRONE CONTROL TEST")
        print("="*60)

        try:
            # Connect to SITL
            print("\n[1/6] Connecting to SITL...")
            await self.connection_manager.connect("udp://:14540")
            drone = self.connection_manager.get_drone()

            # Initialize telemetry cache
            print("[2/6] Initializing telemetry cache...")
            await self.telemetry_cache.initialize(drone)

            # Initialize state machine
            print("[3/6] Initializing state machine...")
            self.state_machine.transition_to(FlightState.DISCONNECTED)
            self.state_machine.transition_to(FlightState.GROUNDED)

            print("✓ Setup complete")
            return True

        except Exception as e:
            print(f"✗ Setup failed: {e}")
            return False

    async def test_arm_and_takeoff(self) -> bool:
        """Test arm and takeoff via MCP tool."""
        print("\n[4/6] Testing arm_and_takeoff...")

        try:
            # Call the MCP tool
            result_json = await arm_and_takeoff(altitude_m=10.0)
            result = json.loads(result_json)

            if result.get("success"):
                print(f"  ✓ Armed and took off to {result.get('altitude_m', 'unknown')}m")
                print(f"  ✓ State: {result.get('state', 'unknown')}")
                self.results.append({"test": "arm_and_takeoff", "status": "PASS", "result": result})
                return True
            else:
                print(f"  ✗ Failed: {result.get('error', 'unknown error')}")
                self.results.append({"test": "arm_and_takeoff", "status": "FAIL", "error": result.get("error")})
                return False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            self.results.append({"test": "arm_and_takeoff", "status": "FAIL", "error": str(e)})
            return False

    async def test_realtime_velocity_control(self) -> bool:
        """Test real-time velocity control (20Hz streaming simulation)."""
        print("\n[5/6] Testing real-time velocity control (20Hz)...")

        try:
            # Simulate 20Hz velocity control for 3 seconds
            start_time = time.time()
            iterations = 0
            duration = 3.0

            print(f"  Streaming velocity commands at ~20Hz for {duration}s...")

            while time.time() - start_time < duration:
                loop_start = time.time()

                # Send velocity command (north at 2 m/s)
                result_json = await set_velocity(
                    north_m_s=2.0,
                    east_m_s=0.0,
                    down_m_s=0.0,
                    duration_s=0.05  # 50ms = 20Hz
                )
                result = json.loads(result_json)

                if not result.get("success"):
                    print(f"    ✗ Velocity command failed: {result.get('error')}")
                    return False

                iterations += 1

                # Maintain 20Hz timing
                elapsed = time.time() - loop_start
                if elapsed < 0.05:
                    await asyncio.sleep(0.05 - elapsed)

            actual_duration = time.time() - start_time
            actual_hz = iterations / actual_duration

            print(f"  ✓ Sent {iterations} velocity commands")
            print(f"  ✓ Actual rate: {actual_hz:.1f}Hz (target: 20Hz)")

            if actual_hz >= 15:  # Allow some tolerance
                self.results.append({
                    "test": "realtime_velocity",
                    "status": "PASS",
                    "iterations": iterations,
                    "rate_hz": actual_hz
                })
                return True
            else:
                print(f"  ✗ Rate too low (< 15Hz)")
                return False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            self.results.append({"test": "realtime_velocity", "status": "FAIL", "error": str(e)})
            return False

    async def test_position_hold(self) -> bool:
        """Test position hold."""
        print("\n[6/6] Testing position hold...")

        try:
            result_json = await hold(duration_s=2.0)
            result = json.loads(result_json)

            if result.get("success"):
                print(f"  ✓ Held position for {result.get('duration_s', 'unknown')}s")
                print(f"  ✓ Max drift: {result.get('max_drift_m', 'unknown')}m")
                self.results.append({"test": "hold", "status": "PASS", "result": result})
                return True
            else:
                print(f"  ✗ Failed: {result.get('error', 'unknown error')}")
                return False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            return False

    async def test_telemetry_realtime(self) -> bool:
        """Test real-time telemetry access."""
        print("\n[BONUS] Testing real-time telemetry (100ms cache)...")

        try:
            # Get telemetry multiple times rapidly
            times = []
            for i in range(10):
                start = time.time()
                result_json = await get_telemetry()
                elapsed = time.time() - start
                times.append(elapsed)
                await asyncio.sleep(0.1)

            avg_time = sum(times) / len(times)
            max_time = max(times)

            print(f"  ✓ Telemetry queries: {len(times)}")
            print(f"  ✓ Average response time: {avg_time*1000:.1f}ms (target: <1ms cache)")
            print(f"  ✓ Max response time: {max_time*1000:.1f}ms")

            if avg_time < 0.01:  # Should be <10ms with cache
                print(f"  ✓ Cache performance: EXCELLENT")
            elif avg_time < 0.1:
                print(f"  ✓ Cache performance: GOOD")
            else:
                print(f"  ⚠ Cache performance: SLOW")

            return True

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            return False

    async def test_body_offset(self) -> bool:
        """Test body-relative movement."""
        print("\n[BONUS] Testing body-relative movement...")

        try:
            result_json = await fly_body_offset(
                forward_m=5.0,
                right_m=0.0,
                up_m=0.0,
                speed_m_s=3.0
            )
            result = json.loads(result_json)

            if result.get("success"):
                print(f"  ✓ Moved {result.get('offset', {}).get('forward_m', 'unknown')}m forward")
                print(f"  ✓ Transform applied: {result.get('transform', 'N/A')}")
                return True
            else:
                print(f"  ✗ Failed: {result.get('error', 'unknown error')}")
                return False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            return False

    async def test_rtl(self) -> bool:
        """Test return to launch."""
        print("\n[FINAL] Testing return to launch (RTL)...")

        try:
            result_json = await rtl()
            result = json.loads(result_json)

            if result.get("success"):
                print(f"  ✓ RTL initiated")
                print(f"  ✓ Home position: {result.get('home_position', 'unknown')}")
                return True
            else:
                print(f"  ✗ Failed: {result.get('error', 'unknown error')}")
                return False

        except Exception as e:
            print(f"  ✗ Exception: {e}")
            return False

    async def cleanup(self):
        """Cleanup resources."""
        print("\n[CLEANUP] Releasing resources...")

        try:
            await self.telemetry_cache.stop()
            await self.connection_manager.disconnect()
            print("✓ Cleanup complete")
        except Exception as e:
            print(f"⚠ Cleanup warning: {e}")

    async def run_all_tests(self):
        """Run complete test suite."""
        all_passed = True

        # Setup
        if not await self.setup():
            print("\n✗ SETUP FAILED - Aborting tests")
            return False

        # Core tests
        tests = [
            ("Arm & Takeoff", self.test_arm_and_takeoff),
            ("Real-time Velocity", self.test_realtime_velocity_control),
            ("Position Hold", self.test_position_hold),
        ]

        for name, test_func in tests:
            try:
                passed = await test_func()
                if not passed:
                    all_passed = False
            except Exception as e:
                print(f"\n✗ {name} failed with exception: {e}")
                all_passed = False

        # Bonus tests (don't fail if these don't work)
        try:
            await self.test_telemetry_realtime()
        except:
            pass

        try:
            await self.test_body_offset()
        except:
            pass

        # RTL to land
        try:
            await self.test_rtl()
        except:
            pass

        # Cleanup
        await self.cleanup()

        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")

        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if all_passed:
            print("\n✓ ALL TESTS PASSED - MCP server ready for real-time control!")
        else:
            print("\n✗ SOME TESTS FAILED - Check output above")

        return all_passed


async def main():
    """Main entry point."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Project Avatar - MCP Real-Time Control Test             ║
║                                                              ║
║  This test validates that Claude Code can control the       ║
║  drone in real-time through the MCP protocol.               ║
║                                                              ║
║  Prerequisites:                                              ║
║  - PX4 SITL running: make px4_sitl gz_x500                  ║
║  - Gazebo simulation visible                                  ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Check if SITL is running
    print("Checking SITL connection...")
    test = MCPRealtimeTest()

    try:
        success = await test.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        await test.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
