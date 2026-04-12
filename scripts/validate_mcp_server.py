#!/usr/bin/env python3
"""
Quick MCP Server Validation

Validates that the MCP server is properly configured and can be used by Claude Code.
"""

import json
import sys
import subprocess

def check_server_imports():
    """Check that server modules can be imported."""
    print("[1/5] Checking server imports...")
    try:
        import avatar.mcp_server.server as server_module
        print("  ✓ Server module imports successfully")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False

def check_tools_available():
    """Check that all tools are available."""
    print("\n[2/5] Checking available tools...")
    try:
        sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')
        from avatar.mcp_server.tools.flight_tools import (
            arm_and_takeoff, land, rtl, goto_gps,
            fly_body_offset, set_velocity, hold
        )
        from avatar.mcp_server.tools.telemetry_tools import get_telemetry, get_status
        from avatar.mcp_server.tools.vision_tools import detect_objects, get_detected_objects

        tools = [
            "arm_and_takeoff", "land", "rtl", "goto_gps",
            "fly_body_offset", "set_velocity", "hold",
            "get_telemetry", "get_status",
            "detect_objects", "get_detected_objects"
        ]

        print(f"  ✓ {len(tools)} tools available:")
        for tool in tools:
            print(f"    - {tool}")
        return True
    except Exception as e:
        print(f"  ✗ Tool check failed: {e}")
        return False

def check_mcp_configuration():
    """Check Claude Code MCP configuration."""
    print("\n[3/5] Checking Claude Code MCP configuration...")
    try:
        import json
        with open('/Users/muadhsambul/.claude/settings.json') as f:
            settings = json.load(f)

        mcp_servers = settings.get('mcpServers', {})
        if 'drone' in mcp_servers:
            print("  ✓ Drone MCP server registered in settings.json")
            drone_config = mcp_servers['drone']
            print(f"    Command: {drone_config.get('command')} {' '.join(drone_config.get('args', []))}")
            return True
        else:
            print("  ✗ Drone MCP server not found in settings.json")
            print("  ℹ Run: Claude will need to register the MCP server")
            return False
    except Exception as e:
        print(f"  ✗ Configuration check failed: {e}")
        return False

def check_core_components():
    """Check core MAV components."""
    print("\n[4/5] Checking core MAV components...")
    try:
        sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')
        from avatar.mav.connection_manager import ConnectionManager
        from avatar.mav.telemetry_cache import TelemetryCache
        from avatar.mav.heartbeat_service import HeartbeatService
        from avatar.mav.state_machine import FlightStateMachine
        from avatar.mav.guardian_async import AsyncGuardian

        components = [
            "ConnectionManager (singleton)",
            "TelemetryCache (100ms refresh)",
            "HeartbeatService (20Hz)",
            "FlightStateMachine (15 states)",
            "AsyncGuardian (safety)"
        ]

        print("  ✓ All core components available:")
        for comp in components:
            print(f"    - {comp}")
        return True
    except Exception as e:
        print(f"  ✗ Component check failed: {e}")
        return False

def check_code_quality():
    """Check code quality metrics."""
    print("\n[5/5] Checking code quality...")
    try:
        # Count test files
        import os
        test_count = 0
        for root, dirs, files in os.walk('/Users/muadhsambul/Downloads/Project-Avatar/tests'):
            test_count += len([f for f in files if f.startswith('test_') and f.endswith('.py')])

        print(f"  ✓ {test_count} test files available")

        # Check for decorators
        sys.path.insert(0, '/Users/muadhsambul/Downloads/Project-Avatar')
        from avatar.core.decorators import timeout, retry, require_state
        print("  ✓ Safety decorators available (@timeout, @retry, @require_state)")

        # Check for context managers
        from avatar.core.context_managers import managed_connection, managed_offboard, FlightSession
        print("  ✓ Context managers available (managed_connection, managed_offboard, FlightSession)")

        return True
    except Exception as e:
        print(f"  ✗ Quality check failed: {e}")
        return False

def main():
    """Run all validation checks."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          MCP Server Validation for Claude Code              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    checks = [
        check_server_imports,
        check_tools_available,
        check_mcp_configuration,
        check_core_components,
        check_code_quality,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"  ✗ Check failed with exception: {e}")
            results.append(False)

    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if all(results):
        print("\n✓ MCP Server is ready for Claude Code!")
        print("\nNext steps:")
        print("  1. Start SITL: cd PX4-Autopilot && make px4_sitl gz_x500")
        print("  2. Restart Claude Code to load the drone MCP server")
        print("  3. Try: 'Connect to drone and arm for takeoff'")
        return 0
    else:
        print("\n✗ Some checks failed - review output above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
