from avatar.sim.scenarios import SCENARIOS, get_scenario, list_scenarios


def test_scenario_catalog_contains_real_use_cases():
    assert "runner_follow_basic" in SCENARIOS
    assert "sailboat_follow_wide" in SCENARIOS
    assert "nature_orbit_reveal" in SCENARIOS
    assert "indoor_obstacle_room_depth" in SCENARIOS


def test_each_scenario_has_acceptance_command():
    for scenario in list_scenarios():
        assert scenario.acceptance_test.startswith("python3 -m pytest ")
        assert scenario.px4_command.startswith("cd PX4-Autopilot && make ")
        assert "mcp_stdio" in scenario.required_backends


def test_get_scenario_returns_named_scenario():
    scenario = get_scenario("sailboat_follow_wide")

    assert scenario.kind == "sailboat_follow"
    assert "boat" in scenario.description.lower()
