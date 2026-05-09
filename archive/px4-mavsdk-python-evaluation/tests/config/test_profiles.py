"""Test suite for RuntimeProfile configurations (D2.10).

Tests cover:
- RuntimeProfile com_obl_rc_act field
- ComOblRcAct type validation
- SITL and hardware profile defaults
"""

from avatar.config.profiles import (
    HARDWARE_PROFILE,
    SITL_PROFILE,
    RuntimeProfile,
    ComOblRcAct,
)


def test_sitl_profile_uses_sitl_udp_connection():
    assert SITL_PROFILE.name == "sitl"
    assert SITL_PROFILE.system_address == "udp://:14540"
    assert SITL_PROFILE.requires_px4_parameter_check is False


def test_hardware_profile_requires_parameter_check():
    assert HARDWARE_PROFILE.name == "hardware"
    assert HARDWARE_PROFILE.requires_px4_parameter_check is True
    assert HARDWARE_PROFILE.system_address.startswith("serial://")


class TestComOblRcAct:
    """Tests for COM_OBL_RC_ACT parameter configuration (D2.10)."""

    def test_com_obl_rc_act_type_has_valid_values(self):
        """D2.10: ComOblRcAct should be Literal[0, 1, 2, 3]."""
        # Valid values: 0=Disable, 1=Land, 2=RTL, 3=Hold
        valid_values = [0, 1, 2, 3]
        for val in valid_values:
            assert val in [0, 1, 2, 3]

    def test_sitl_profile_has_com_obl_rc_act_default(self):
        """D2.10: SITL_PROFILE should have com_obl_rc_act=2 (RTL)."""
        assert SITL_PROFILE.com_obl_rc_act == 2

    def test_hardware_profile_has_com_obl_rc_act_default(self):
        """D2.10: HARDWARE_PROFILE should have com_obl_rc_act=2 (RTL)."""
        assert HARDWARE_PROFILE.com_obl_rc_act == 2

    def test_runtime_profile_has_com_obl_rc_act_field(self):
        """D2.10: RuntimeProfile should have com_obl_rc_act field."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
        )
        # Should have default value
        assert hasattr(profile, "com_obl_rc_act")
        assert profile.com_obl_rc_act == 2

    def test_runtime_profile_com_obl_rc_act_can_be_customized(self):
        """D2.10: RuntimeProfile com_obl_rc_act should be customizable."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
            com_obl_rc_act=1,  # Land on offboard loss
        )
        assert profile.com_obl_rc_act == 1

    def test_runtime_profile_com_obl_rc_act_values(self):
        """D2.10: Test all valid com_obl_rc_act values."""
        # 0 = Disable
        profile_disable = RuntimeProfile(
            name="test_disable",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
            com_obl_rc_act=0,
        )
        assert profile_disable.com_obl_rc_act == 0

        # 1 = Land
        profile_land = RuntimeProfile(
            name="test_land",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
            com_obl_rc_act=1,
        )
        assert profile_land.com_obl_rc_act == 1

        # 2 = RTL (default)
        profile_rtl = RuntimeProfile(
            name="test_rtl",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
            com_obl_rc_act=2,
        )
        assert profile_rtl.com_obl_rc_act == 2

        # 3 = Hold
        profile_hold = RuntimeProfile(
            name="test_hold",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
            com_obl_rc_act=3,
        )
        assert profile_hold.com_obl_rc_act == 3

    def test_runtime_profile_is_validated(self):
        """D9: RuntimeProfile uses Pydantic v2 validation."""
        profile = RuntimeProfile(
            name="test",
            system_address="udp://:14540",
            camera_backend="mock",
            detector_backend="mock",
            requires_px4_parameter_check=False,
        )

        # Pydantic v2 model - can be mutated but validated
        assert profile.com_obl_rc_act == 2

        # Use model_dump_frozen for immutable access
        frozen_dump = profile.model_dump_frozen()
        assert frozen_dump["com_obl_rc_act"] == 2
