from avatar.config.profiles import HARDWARE_PROFILE, SITL_PROFILE


def test_sitl_profile_uses_sitl_udp_connection():
    assert SITL_PROFILE.name == "sitl"
    assert SITL_PROFILE.system_address == "udp://:14540"
    assert SITL_PROFILE.requires_px4_parameter_check is False


def test_hardware_profile_requires_parameter_check():
    assert HARDWARE_PROFILE.name == "hardware"
    assert HARDWARE_PROFILE.requires_px4_parameter_check is True
    assert HARDWARE_PROFILE.system_address.startswith("serial://")
