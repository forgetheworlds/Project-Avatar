#!/usr/bin/env python
"""Quick validation script for profiles v2 implementation."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=" * 60)
    print("Validating RuntimeProfile v2 implementation")
    print("=" * 60)

    # Test 1: Import the profiles module
    print("\n[1/6] Testing module imports...")
    try:
        from avatar.config.profiles import (
            AIRFRAME_TEMPLATES,
            HARDWARE_PROFILE,
            MARK4_7IN_TEMPLATE,
            SITL_PROFILE,
            X500_V2_TEMPLATE,
            AirframeTemplate,
            RuntimeProfile,
            load_profile,
            verify_profile_parameters,
            ComOblRcAct,
        )
        print("  SUCCESS: All imports successful")
    except ImportError as e:
        print(f"  FAILED: Import error: {e}")
        return 1

    # Test 2: Validate SITL_PROFILE
    print("\n[2/6] Testing SITL_PROFILE...")
    try:
        assert SITL_PROFILE.name == "sitl", "SITL profile name mismatch"
        assert SITL_PROFILE.system_address == "udp://:14540", "SITL system address mismatch"
        assert SITL_PROFILE.requires_px4_parameter_check is False, "SITL parameter check should be False"
        assert SITL_PROFILE.com_obl_rc_act == 2, "SITL com_obl_rc_act should be 2"
        assert SITL_PROFILE.camera_backend == "mock_camera", "SITL camera backend mismatch"
        assert SITL_PROFILE.detector_backend == "mock_detector", "SITL detector backend mismatch"
        print("  SUCCESS: SITL_PROFILE validated")
    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1

    # Test 3: Validate HARDWARE_PROFILE
    print("\n[3/6] Testing HARDWARE_PROFILE...")
    try:
        assert HARDWARE_PROFILE.name == "hardware", "Hardware profile name mismatch"
        assert HARDWARE_PROFILE.requires_px4_parameter_check is True, "Hardware parameter check should be True"
        assert HARDWARE_PROFILE.system_address.startswith("serial://"), "Hardware system address should be serial"
        assert HARDWARE_PROFILE.com_obl_rc_act == 2, "Hardware com_obl_rc_act should be 2"
        assert HARDWARE_PROFILE.camera_backend == "rtsp_camera", "Hardware camera backend mismatch"
        assert HARDWARE_PROFILE.detector_backend == "yolo_detector", "Hardware detector backend mismatch"
        print("  SUCCESS: HARDWARE_PROFILE validated")
    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1

    # Test 4: Validate airframe templates
    print("\n[4/6] Testing airframe templates...")
    try:
        assert "mark4_7in" in AIRFRAME_TEMPLATES, "mark4_7in template missing"
        assert "x500_v2" in AIRFRAME_TEMPLATES, "x500_v2 template missing"

        mark4 = AIRFRAME_TEMPLATES["mark4_7in"]
        assert mark4.airframe_id == "mark4_7in", "mark4_7in airframe_id mismatch"
        assert mark4.mass_kg == 1.2, "mark4_7in mass mismatch"
        assert mark4.prop_size_in == 7.0, "mark4_7in prop_size mismatch"

        x500 = AIRFRAME_TEMPLATES["x500_v2"]
        assert x500.airframe_id == "x500_v2", "x500_v2 airframe_id mismatch"
        assert x500.px4_airframe_id == 4500, "x500_v2 px4_airframe_id mismatch"
        print("  SUCCESS: Airframe templates validated")
    except AssertionError as e:
        print(f"  FAILED: {e}")
        return 1

    # Test 5: Test load_profile function
    print("\n[5/6] Testing load_profile function...")
    try:
        profile = load_profile("sitl")
        assert profile.name == "sitl", "Loaded profile name mismatch"
        assert profile.system_address == "udp://:14540", "Loaded profile system address mismatch"

        # Test with overrides
        custom = load_profile(
            "custom",
            system_address="udp://:14541",
            camera_backend="custom_camera",
        )
        assert custom.system_address == "udp://:14541", "Custom profile system address not applied"
        assert custom.camera_backend == "custom_camera", "Custom profile camera backend not applied"
        print("  SUCCESS: load_profile function validated")
    except Exception as e:
        print(f"  FAILED: {e}")
        return 1

    # Test 6: Test RuntimeProfile creation
    print("\n[6/6] Testing RuntimeProfile creation...")
    try:
        from pydantic import ValidationError

        # Valid profile
        valid_profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            camera_backend="mock_camera",
            detector_backend="mock_detector",
            requires_px4_parameter_check=False,
            com_obl_rc_act=2,
        )
        assert valid_profile.name == "test", "Profile name mismatch"

        # Invalid com_obl_rc_act
        try:
            invalid_profile = RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                com_obl_rc_act=5,  # Invalid: must be 0-3
            )
            print("  FAILED: Should have raised ValidationError for invalid com_obl_rc_act")
            return 1
        except ValidationError:
            pass  # Expected

        # Invalid system_address
        try:
            invalid_profile = RuntimeProfile(
                name="test",
                system_address="invalid://address",
            )
            print("  FAILED: Should have raised ValidationError for invalid system_address")
            return 1
        except ValidationError:
            pass  # Expected

        print("  SUCCESS: RuntimeProfile validation validated")
    except Exception as e:
        print(f"  FAILED: {e}")
        return 1

    print("\n" + "=" * 60)
    print("ALL VALIDATION TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
