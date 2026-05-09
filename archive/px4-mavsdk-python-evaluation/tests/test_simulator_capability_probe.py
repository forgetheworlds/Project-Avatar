from pathlib import Path

from scripts.check_simulator_capabilities import detect_capabilities


def test_simulator_capability_probe_reports_expected_commands():
    capabilities = detect_capabilities(Path(__file__).resolve().parents[1])

    commands = capabilities["commands"]
    assert "gazebo_gz_x500" in commands
    assert "gazebo_depth" in commands
    assert "gazebo_vision" in commands
    assert "px4_sih" in commands
    assert "jmavsim" in commands
    assert commands["px4_sih"] == "cd PX4-Autopilot && make px4_sitl_default sihsim_quadx"
    assert capabilities["recommended_order"][0] == "gazebo_gz_x500"
