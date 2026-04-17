"""Test suite for RuntimeProfile v2 Pydantic models (Wave 2b - D9).

Tests cover:
- Pydantic v2 model validation
- Layered configuration loading (ENV + file + secrets)
- Airframe templates (mark4_7in, x500_v2, custom)
- PX4 parameter overlay integration
- com_obl_rc_act configuration
- Vision profile fields
- Backward compatibility with frozen dataclass behavior
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Union
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from avatar.config.profiles import (
    AIRFRAME_TEMPLATES,
    HARDWARE_PROFILE,
    MARK4_7IN_TEMPLATE,
    SITL_PROFILE,
    X500_V2_TEMPLATE,
    AirframeTemplate,
    ComOblRcAct,
    RuntimeProfile,
    _get_env_overrides,
    _load_file_config,
    load_profile,
    verify_profile_parameters,
)


# =============================================================================
# AIRFRAME TEMPLATE TESTS
# =============================================================================


class TestAirframeTemplate:
    """Tests for AirframeTemplate Pydantic model."""

    def test_mark4_7in_template_has_required_fields(self):
        """D9: mark4_7in template must have all required fields."""
        template = MARK4_7IN_TEMPLATE

        assert template.airframe_id == "mark4_7in"
        assert template.mass_kg == 1.2
        assert template.prop_size_in == 7.0
        assert template.px4_airframe_id is None  # Custom airframe
        assert template.battery_cells == 4
        assert template.max_thrust_n == 30.0
        assert template.param_overlay_path is None
        assert "COM_OBL_RC_ACT" in template.param_overlay

    def test_x500_v2_template_has_required_fields(self):
        """D9: x500_v2 template must have all required fields."""
        template = X500_V2_TEMPLATE

        assert template.airframe_id == "x500_v2"
        assert template.mass_kg == 1.5
        assert template.prop_size_in == 10.0
        assert template.px4_airframe_id == 4500
        assert template.battery_cells == 4
        assert template.max_thrust_n == 35.0

    def test_airframe_template_validates_mass(self):
        """D9: AirframeTemplate must validate mass_kg > 0."""
        with pytest.raises(ValidationError):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=0.0,  # Invalid: must be > 0
                prop_size_in=5.0,
            )

        with pytest.raises(ValidationError):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=-1.0,  # Invalid: must be > 0
                prop_size_in=5.0,
            )

    def test_airframe_template_validates_prop_size(self):
        """D9: AirframeTemplate must validate prop_size_in > 0."""
        with pytest.raises(ValidationError):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=1.0,
                prop_size_in=0.0,  # Invalid: must be > 0
            )

    def test_airframe_template_validates_battery_cells(self):
        """D9: AirframeTemplate must validate battery_cells in [1, 12]."""
        # Valid values
        for cells in [1, 4, 6, 12]:
            template = AirframeTemplate(
                airframe_id="test",
                mass_kg=1.0,
                prop_size_in=5.0,
                battery_cells=cells,
            )
            assert template.battery_cells == cells

        # Invalid values
        with pytest.raises(ValidationError):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=1.0,
                prop_size_in=5.0,
                battery_cells=0,  # Invalid: must be >= 1
            )

        with pytest.raises(ValidationError):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=1.0,
                prop_size_in=5.0,
                battery_cells=13,  # Invalid: must be <= 12
            )

    def test_airframe_template_param_overlay_defaults_to_empty(self):
        """D9: param_overlay should default to empty dict."""
        template = AirframeTemplate(
            airframe_id="test",
            mass_kg=1.0,
            prop_size_in=5.0,
        )
        assert template.param_overlay == {}

    def test_airframe_template_thrust_to_weight_warning(self):
        """D9: Warn on unreasonable thrust-to-weight ratio."""
        with pytest.warns(UserWarning, match="Low thrust-to-weight"):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=10.0,
                prop_size_in=5.0,
                max_thrust_n=50.0,  # ~0.5:1 TWR
            )

        with pytest.warns(UserWarning, match="Very high thrust-to-weight"):
            AirframeTemplate(
                airframe_id="test",
                mass_kg=0.1,
                prop_size_in=5.0,
                max_thrust_n=50.0,  # ~51:1 TWR
            )

    def test_airframe_template_from_dict(self):
        """D9: AirframeTemplate can be created from dict."""
        data = {
            "airframe_id": "custom_quad",
            "mass_kg": 2.0,
            "prop_size_in": 9.0,
            "px4_airframe_id": 4100,
            "battery_cells": 6,
            "max_thrust_n": 60.0,
            "param_overlay": {"COM_OBL_RC_ACT": 1},
        }
        template = AirframeTemplate.model_validate(data)

        assert template.airframe_id == "custom_quad"
        assert template.mass_kg == 2.0
        assert template.param_overlay["COM_OBL_RC_ACT"] == 1

    def test_airframe_registry_contains_predefined(self):
        """D9: AIRFRAME_TEMPLATES must contain predefined templates."""
        assert "mark4_7in" in AIRFRAME_TEMPLATES
        assert "x500_v2" in AIRFRAME_TEMPLATES

        # Templates should be identical to constants
        assert AIRFRAME_TEMPLATES["mark4_7in"] is MARK4_7IN_TEMPLATE
        assert AIRFRAME_TEMPLATES["x500_v2"] is X500_V2_TEMPLATE


# =============================================================================
# RUNTIME PROFILE TESTS
# =============================================================================


class TestRuntimeProfile:
    """Tests for RuntimeProfile Pydantic v2 model."""

    def test_sitl_profile_uses_sitl_udp_connection(self):
        """D9: SITL_PROFILE must use UDP connection."""
        assert SITL_PROFILE.name == "sitl"
        assert SITL_PROFILE.system_address == "udp://:14540"
        assert SITL_PROFILE.requires_px4_parameter_check is False

    def test_hardware_profile_requires_parameter_check(self):
        """D9: HARDWARE_PROFILE must require PX4 parameter check."""
        assert HARDWARE_PROFILE.name == "hardware"
        assert HARDWARE_PROFILE.requires_px4_parameter_check is True
        assert HARDWARE_PROFILE.system_address.startswith("serial://")

    def test_profile_validates_system_address(self):
        """D9: RuntimeProfile must validate system_address format."""
        # Valid addresses
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
        )
        assert profile.system_address == "udp://:14540"

        profile = RuntimeProfile(
            name="test",
            system_address="serial:///dev/ttyACM0:921600",
        )
        assert profile.system_address == "serial:///dev/ttyACM0:921600"

        profile = RuntimeProfile(
            name="test",
            system_address="tcp://localhost:5760",
        )
        assert profile.system_address == "tcp://localhost:5760"

        # Invalid addresses
        with pytest.raises(ValidationError, match="must start with"):
            RuntimeProfile(
                name="test",
                system_address="invalid://address",
            )

    def test_profile_vision_fields(self):
        """D9: RuntimeProfile must have camera_backend and detector_backend fields."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            camera_backend="rtsp_camera",
            detector_backend="yolo_detector",
        )

        assert profile.camera_backend == "rtsp_camera"
        assert profile.detector_backend == "yolo_detector"

    def test_profile_vision_fields_default_to_mock(self):
        """D9: Vision fields should default to mock implementations."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
        )

        assert profile.camera_backend == "mock_camera"
        assert profile.detector_backend == "mock_detector"

    def test_profile_com_obl_rc_act_default(self):
        """D9: com_obl_rc_act should default to 2 (RTL)."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
        )

        assert profile.com_obl_rc_act == 2

    def test_profile_com_obl_rc_act_valid_values(self):
        """D9: com_obl_rc_act must accept all valid values [0, 1, 2, 3]."""
        for value in [0, 1, 2, 3]:
            profile = RuntimeProfile(
                name=f"test_{value}",
                system_address="udp://:14540",
                com_obl_rc_act=value,
            )
            assert profile.com_obl_rc_act == value

    def test_profile_com_obl_rc_act_invalid_value(self):
        """D9: com_obl_rc_act must reject invalid values."""
        with pytest.raises(ValidationError):
            RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                com_obl_rc_act=4,  # Invalid: must be in [0, 1, 2, 3]
            )

        with pytest.raises(ValidationError):
            RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                com_obl_rc_act=-1,  # Invalid
            )

    def test_profile_airframe_defaults_to_x500_v2(self):
        """D9: airframe should default to x500_v2."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
        )

        assert profile.airframe == "x500_v2"

    def test_profile_airframe_from_string(self):
        """D9: airframe can be specified as string template ID."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            airframe="mark4_7in",
        )

        assert profile.airframe == "mark4_7in"

    def test_profile_airframe_from_dict(self):
        """D9: airframe can be specified as inline dict."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            airframe={
                "airframe_id": "custom",
                "mass_kg": 2.0,
                "prop_size_in": 10.0,
            },
        )

        assert isinstance(profile.airframe, AirframeTemplate)
        assert profile.airframe.airframe_id == "custom"

    def test_profile_battery_threshold_validation(self):
        """D9: rtl_battery_percent must be less than min_battery_percent."""
        with pytest.raises(ValidationError, match="must be less than"):
            RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                min_battery_percent=20.0,
                rtl_battery_percent=30.0,  # Invalid: must be < min
            )

    def test_profile_get_airframe_template(self):
        """D9: get_airframe_template returns resolved AirframeTemplate."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            airframe="x500_v2",
        )

        template = profile.get_airframe_template()
        assert template is X500_V2_TEMPLATE

    def test_profile_get_airframe_template_inline(self):
        """D9: get_airframe_template returns inline AirframeTemplate."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            airframe={
                "airframe_id": "inline",
                "mass_kg": 1.5,
                "prop_size_in": 8.0,
            },
        )

        template = profile.get_airframe_template()
        assert isinstance(template, AirframeTemplate)
        assert template.airframe_id == "inline"

    def test_profile_get_merged_param_overlay(self):
        """D9: get_merged_param_overlay merges airframe and profile params."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            airframe="x500_v2",
            com_obl_rc_act=1,  # Override
            param_overlay={"COM_OF_LOSS_T": 1.0},  # Additional param
        )

        merged = profile.get_merged_param_overlay()

        # Should include airframe defaults
        assert "COM_OBL_RC_ACT" in merged
        # Should include profile overrides
        assert merged["COM_OBL_RC_ACT"] == 1  # Overridden
        assert merged["COM_OF_LOSS_T"] == 1.0  # Added

    def test_profile_model_dump_frozen(self):
        """D9: model_dump_frozen returns copy to prevent mutation."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
        )

        dump = profile.model_dump_frozen()
        dump["name"] = "mutated"

        # Original profile should not be affected
        assert profile.name == "test"


# =============================================================================
# LAYERED CONFIGURATION TESTS
# =============================================================================


class TestLayeredConfiguration:
    """Tests for layered configuration loading."""

    def test_load_profile_with_defaults(self):
        """D9: load_profile creates profile with default values."""
        profile = load_profile("sitl")

        assert profile.name == "sitl"
        assert profile.system_address == "udp://:14540"

    def test_load_profile_with_overrides(self):
        """D9: load_profile accepts caller overrides."""
        profile = load_profile(
            "custom",
            system_address="udp://:14541",
            camera_backend="custom_camera",
        )

        assert profile.name == "custom"
        assert profile.system_address == "udp://:14541"
        assert profile.camera_backend == "custom_camera"

    def test_load_profile_from_json_file(self, tmp_path: Path):
        """D9: load_profile loads from JSON file."""
        config_file = tmp_path / "test_profile.json"
        config_file.write_text(json.dumps({
            "name": "from_file",
            "system_address": "udp://:14542",
            "camera_backend": "file_camera",
        }))

        profile = load_profile("test", config_path=config_file)

        assert profile.system_address == "udp://:14542"
        assert profile.camera_backend == "file_camera"
        assert profile.config_path == str(config_file)

    def test_load_profile_from_yaml_file(self, tmp_path: Path):
        """D9: load_profile loads from YAML file."""
        pytest.importorskip("yaml")

        config_file = tmp_path / "test_profile.yaml"
        config_file.write_text("""
name: from_yaml
system_address: udp://:14543
camera_backend: yaml_camera
detector_backend: yaml_detector
""")

        profile = load_profile("test", config_path=config_file)

        assert profile.system_address == "udp://:14543"
        assert profile.camera_backend == "yaml_camera"

    def test_load_profile_env_overrides(self, monkeypatch: pytest.MonkeyPatch):
        """D9: ENV variables override file config."""
        monkeypatch.setenv("AVATAR_SYSTEM_ADDRESS", "udp://:14544")
        monkeypatch.setenv("AVATAR_CAMERA_BACKEND", "env_camera")

        profile = load_profile("test")

        assert profile.system_address == "udp://:14544"
        assert profile.camera_backend == "env_camera"
        assert "system_address" in profile.env_overrides

    def test_load_profile_secret_env_highest_precedence(self, monkeypatch: pytest.MonkeyPatch):
        """D9: AVATAR_SECRET_* variables have highest precedence."""
        monkeypatch.setenv("AVATAR_SYSTEM_ADDRESS", "udp://:14545")
        monkeypatch.setenv("AVATAR_SECRET_SYSTEM_ADDRESS", "udp://:14546")

        profile = load_profile("test")

        assert profile.system_address == "udp://:14546"  # Secret wins

    def test_load_profile_env_type_coercion(self, monkeypatch: pytest.MonkeyPatch):
        """D9: ENV variables are type-coerced correctly."""
        monkeypatch.setenv("AVATAR_REQUIRES_PX4_CHECK", "true")
        monkeypatch.setenv("AVATAR_COM_OBL_RC_ACT", "1")
        monkeypatch.setenv("AVATAR_MIN_BATTERY_PERCENT", "50.5")

        profile = load_profile("test")

        assert profile.requires_px4_parameter_check is True
        assert profile.com_obl_rc_act == 1
        assert profile.min_battery_percent == 50.5

    def test_load_profile_env_bool_false(self, monkeypatch: pytest.MonkeyPatch):
        """D9: ENV boolean false values work correctly."""
        monkeypatch.setenv("AVATAR_REQUIRES_PX4_CHECK", "false")

        profile = load_profile("test")

        assert profile.requires_px4_parameter_check is False

    def test_get_env_overrides_extracts_values(self, monkeypatch: pytest.MonkeyPatch):
        """D9: _get_env_overrides extracts all relevant env vars."""
        monkeypatch.setenv("AVATAR_SYSTEM_ADDRESS", "udp://test")
        monkeypatch.setenv("AVATAR_CAMERA_BACKEND", "test_camera")
        monkeypatch.setenv("AVATAR_COM_OBL_RC_ACT", "3")

        overrides = _get_env_overrides()

        assert overrides["system_address"] == "udp://test"
        assert overrides["camera_backend"] == "test_camera"
        assert overrides["com_obl_rc_act"] == 3

    def test_load_profile_file_not_found(self):
        """D9: load_profile raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_profile("test", config_path="/nonexistent/config.yaml")

    def test_load_profile_unsupported_format(self, tmp_path: Path):
        """D9: load_profile raises ValueError for unsupported format."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("name = 'test'")

        with pytest.raises(ValueError, match="Unsupported configuration"):
            load_profile("test", config_path=config_file)


# =============================================================================
# PX4 PARAMETER VERIFICATION TESTS
# =============================================================================


class TestPX4ParameterVerification:
    """Tests for PX4 parameter overlay preflight gate."""

    def test_verify_profile_parameters_skip_if_not_required(self):
        """D9: verify_profile_parameters skips if check not required."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            requires_px4_parameter_check=False,
        )

        # Should return empty list without verification
        import asyncio
        results = asyncio.run(verify_profile_parameters(profile, None))

        assert results == []

    @pytest.mark.asyncio
    async def test_verify_profile_parameters_calls_manager(self):
        """D9: verify_profile_parameters calls PX4ParameterManager."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            requires_px4_parameter_check=True,
            airframe="x500_v2",
        )

        # Mock drone and parameter manager
        mock_drone = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True

        with patch("avatar.config.profiles.PX4ParameterManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.verify_safety_parameters = AsyncMock(
                return_value=[mock_result]
            )

            results = await verify_profile_parameters(profile, mock_drone)

            # Should have called verify_safety_parameters
            manager_instance.verify_safety_parameters.assert_called_once()
            assert len(results) == 1
            assert results[0].is_valid is True

    @pytest.mark.asyncio
    async def test_verify_profile_parameters_raises_on_mismatch(self):
        """D9: verify_profile_parameters raises SafetyError on mismatch."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            requires_px4_parameter_check=True,
        )

        mock_drone = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = False
        mock_result.name = "COM_OBL_RC_ACT"

        with patch("avatar.config.profiles.PX4ParameterManager") as MockManager:
            manager_instance = MockManager.return_value
            manager_instance.verify_safety_parameters = AsyncMock(
                return_value=[mock_result]
            )

            from avatar.mav.px4_parameters import SafetyError

            with pytest.raises(SafetyError, match="verification failed"):
                await verify_profile_parameters(profile, mock_drone)


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with frozen dataclass behavior."""

    def test_sitl_profile_com_obl_rc_act_value(self):
        """D9: SITL_PROFILE com_obl_rc_act should be 2 (RTL)."""
        assert SITL_PROFILE.com_obl_rc_act == 2

    def test_hardware_profile_com_obl_rc_act_value(self):
        """D9: HARDWARE_PROFILE com_obl_rc_act should be 2 (RTL)."""
        assert HARDWARE_PROFILE.com_obl_rc_act == 2

    def test_profile_exports_match_legacy(self):
        """D9: Profile exports should match legacy expectations."""
        # Legacy imports should still work
        from avatar.config.profiles import (
            HARDWARE_PROFILE,
            SITL_PROFILE,
            RuntimeProfile,
            ComOblRcAct,
        )

        assert SITL_PROFILE is not None
        assert HARDWARE_PROFILE is not None
        assert RuntimeProfile is not None
        assert ComOblRcAct is not None

    def test_profile_can_be_created_like_dataclass(self):
        """D9: RuntimeProfile can be created like frozen dataclass."""
        # This mimics the old frozen dataclass usage
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
        )

        assert profile.name == "test"
        assert profile.system_address == "udp://:14540"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestProfileIntegration:
    """Integration tests for RuntimeProfile system."""

    def test_full_profile_lifecycle(self, tmp_path: Path):
        """D9: Full profile lifecycle from file to verification."""
        # Create config file
        config_file = tmp_path / "production.json"
        config_file.write_text(json.dumps({
            "name": "production",
            "system_address": "serial:///dev/ttyACM0:921600",
            "camera_backend": "rtsp_camera",
            "detector_backend": "yolo_detector",
            "requires_px4_parameter_check": True,
            "airframe": "mark4_7in",
            "geofence_max_hor_dist_m": 300.0,
            "geofence_max_ver_dist_m": 100.0,
        }))

        # Load profile
        profile = load_profile("production", config_path=config_file)

        # Verify all fields
        assert profile.name == "production"
        assert profile.system_address == "serial:///dev/ttyACM0:921600"
        assert profile.camera_backend == "rtsp_camera"
        assert profile.detector_backend == "yolo_detector"
        assert profile.requires_px4_parameter_check is True
        assert profile.airframe == "mark4_7in"
        assert profile.geofence_max_hor_dist_m == 300.0
        assert profile.geofence_max_ver_dist_m == 100.0

        # Get merged param overlay
        overlay = profile.get_merged_param_overlay()
        assert "COM_OBL_RC_ACT" in overlay

        # Get airframe template
        template = profile.get_airframe_template()
        assert template.airframe_id == "mark4_7in"

    def test_custom_airframe_full_config(self):
        """D9: Custom airframe with full configuration."""
        profile = RuntimeProfile(
            name="custom_hex",
            system_address="serial:///dev/ttyUSB0:57600",
            camera_backend="gst_camera",
            detector_backend="tensorrt_detector",
            requires_px4_parameter_check=True,
            com_obl_rc_act=2,
            airframe={
                "airframe_id": "custom_hex",
                "mass_kg": 3.5,
                "prop_size_in": 15.0,
                "px4_airframe_id": 6001,
                "battery_cells": 6,
                "max_thrust_n": 100.0,
                "param_overlay": {
                    "COM_OBL_RC_ACT": 2,
                    "COM_OF_LOSS_T": 0.5,
                },
            },
            param_overlay={
                "GF_MAX_HOR_DIST": 1000,
                "GF_MAX_VER_DIST": 200,
            },
            geofence_max_hor_dist_m=1000.0,
            geofence_max_ver_dist_m=200.0,
            min_battery_percent=50.0,
            rtl_battery_percent=30.0,
        )

        assert profile.name == "custom_hex"
        template = profile.get_airframe_template()
        assert template.mass_kg == 3.5
        assert template.battery_cells == 6

        # Merged overlay should have both airframe and profile params
        overlay = profile.get_merged_param_overlay()
        assert "COM_OBL_RC_ACT" in overlay
        assert "GF_MAX_HOR_DIST" in overlay

    def test_multiple_profile_instances_independent(self):
        """D9: Multiple profile instances should be independent."""
        profile1 = RuntimeProfile(
            name="profile1",
            system_address="udp://:14540",
            com_obl_rc_act=1,
        )
        profile2 = RuntimeProfile(
            name="profile2",
            system_address="udp://:14541",
            com_obl_rc_act=2,
        )

        assert profile1.com_obl_rc_act == 1
        assert profile2.com_obl_rc_act == 2
        assert profile1.system_address != profile2.system_address


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_param_overlay_valid(self):
        """D9: Empty param_overlay should be valid."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            param_overlay={},
        )

        assert profile.param_overlay == {}

    def test_unknown_airframe_string_warns(self):
        """D9: Unknown airframe string should warn but not error."""
        with pytest.warns(UserWarning, match="Unknown airframe template"):
            profile = RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                airframe="unknown_frame",
            )

        assert profile.airframe == "unknown_frame"

        # get_airframe_template should raise for unknown
        with pytest.raises(ValueError, match="Unknown airframe template"):
            profile.get_airframe_template()

    def test_profile_extra_fields_forbidden(self):
        """D9: Profile should reject extra fields."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                unknown_field="value",  # Should be rejected
            )

    def test_geofence_validation_bounds(self):
        """D9: Geofence values should be within bounds."""
        # Valid values
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            geofence_max_hor_dist_m=5000.0,
            geofence_max_ver_dist_m=500.0,
        )
        assert profile.geofence_max_hor_dist_m == 5000.0

        # Invalid: too high
        with pytest.raises(ValidationError):
            RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                geofence_max_hor_dist_m=20000.0,  # > 10000
            )

        # Invalid: zero or negative
        with pytest.raises(ValidationError):
            RuntimeProfile(
                name="test",
                system_address="udp://:14540",
                geofence_max_hor_dist_m=0.0,
            )

    def test_load_profile_with_none_values_in_file(self, tmp_path: Path):
        """D9: File with None values should use defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "name": "partial",
            "system_address": None,  # Should cause validation error
        }))

        with pytest.raises(ValidationError):
            load_profile("test", config_path=config_file)
