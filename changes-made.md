## 2026-04-16 Wave 0 Task 7 - MCP Tool Count Introspection

**Task:** `scripts/validate_mcp_server.py` introspected tool count and `--expected-count`

**Changes:**

1. **Added** `tests/test_validate_mcp_server_tool_count.py`:
   - `test_tool_definitions_count_matches_server_source()` - verifies 26 tools
   - `test_validate_script_accepts_expected_count()` - verifies argparse works

2. **Modified** `avatar/mcp_server/server.py`:
   - Added module-level `avatar_mcp_tool_definitions()` function (returns list of 26 types.Tool)
   - Refactored `handle_list_tools()` to call `avatar_mcp_tool_definitions()`

3. **Modified** `scripts/validate_mcp_server.py`:
   - Added `--expected-count` argparse argument (default: 26)
   - Updated `check_tools_available()` to use `avatar_mcp_tool_definitions()`
   - Made `check_mcp_configuration()` non-fatal (returns True when settings.json missing)

4. **Modified** `avatar/mcp_server/__init__.py`:
   - Exported `avatar_mcp_tool_definitions` from package level
   - Added to `__all__` list

**Verification:**
- `python3 scripts/validate_mcp_server.py --expected-count 26` should exit 0
- `python3 -m pytest tests/test_validate_mcp_server_tool_count.py -v` should pass

---

## 2026-04-13 Project Avatar SITL-To-Hardware Build Status

- MCP stdio discovery: PASS
- Shared MCP flight routing: PASS
- Guardian MAVSDK failsafe callbacks: PASS
- Offboard velocity streamer: PASS
- Vision backend seam: PASS
- Full collection: PASS
- Full test suite: PASS
- MCP SITL smoke mission: PASS
- Remaining hardware-only items: physical serial link, real camera transport, real YOLO backend, PX4 parameter verification on hardware

Verification commands:

```bash
python3 -m py_compile avatar/mcp_server/server.py avatar/mcp_server/tools/flight_tools.py avatar/mcp_server/tools/tracking_tools.py avatar/mcp_server/tools/cinematic_shots.py avatar/mav/offboard_streamer.py avatar/mav/heartbeat_service.py avatar/mav/guardian_async.py avatar/vision/providers.py
python3 -m pytest tests/mcp_server/test_server_offline_protocol.py tests/mcp_server/test_mcp_stdio_smoke.py tests/mcp_server/test_server_flight_routing.py tests/mcp_server/test_guardian_failsafe_actions.py tests/mav/test_offboard_streamer.py tests/vision/test_vision_providers.py avatar/tests/test_vision_pipeline.py -q
.venv/bin/python -m pytest tests/mcp_server/test_server_offline_protocol.py tests/mcp_server/test_mcp_stdio_smoke.py tests/mcp_server/test_server_flight_routing.py tests/mcp_server/test_guardian_failsafe_actions.py tests/mav/test_offboard_streamer.py tests/mav/test_connection_manager.py::TestConnectionHealth::test_unready_vehicle_health_does_not_trigger_transport_reconnect tests/tools/test_hold.py tests/vision/test_vision_providers.py tests/vision/test_gazebo_camera_provider.py avatar/tests/test_vision_pipeline.py tests/sim/test_scenarios.py -q -rs
python3 -m pytest --collect-only -q
python3 -m pytest -q
cd PX4-Autopilot && make px4_sitl_default sihsim_quadx
.venv/bin/python -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl -rs --timeout=180
```

Verification results:

- Compile: PASS
- Focused non-SITL system Python suite: 59 passed, 1 skipped, 1 warning
- Focused dependency-complete venv suite: 81 passed
- Collection: 744 tests collected, 2 skipped, 1 warning
- Full suite: 697 passed, 49 skipped, 1 warning
- MCP SITL smoke against PX4 SIH: 1 passed
