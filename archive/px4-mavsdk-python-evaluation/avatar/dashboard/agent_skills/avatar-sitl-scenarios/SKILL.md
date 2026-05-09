---
name: avatar-sitl-scenarios
description: Use when testing Project Avatar in PX4 SITL, Gazebo, scenario runner, simulated camera feeds, dynamic follow tests, sailboat/nature/indoor scenarios, or pre-hardware validation.
---

# Avatar SITL Scenarios

## Purpose
Use simulation to prove behavior before hardware. Prefer repeatable scenario tests over ad hoc claims.

## Useful Commands
```bash
scripts/sim.sh scenario flight_recorder_replay_diff
scripts/sim.sh all-scenarios
python -m pytest tests/e2e/test_mcp_sitl_smoke.py -q --run-sitl
python scripts/validate_mcp_server.py
```

## Scenario Practice
- If Docker/Gazebo is unavailable, run offline scenarios and report the limitation.
- For dynamic movement, prefer bounded velocity commands and verify telemetry.
- For camera workflows, use simulated camera stream only as UI plumbing unless a real provider is configured.
- Capture exact commands and pass/fail results.

## Common Mistakes
- Do not report `all-scenarios` as pass if Docker/Gazebo was unavailable.
- Do not confuse a dashboard demo orbit with actual SITL vehicle motion.
- Do not skip the MCP smoke test when claiming MCP flight readiness.

