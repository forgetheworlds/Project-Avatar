# Wave 0 Handoff — Project Avatar Implementation

**Created:** 2026-04-16
**Status:** Wave 0 COMPLETE, awaiting user approval for Wave 1
**Branch:** `wave-0-foundation` (2 commits: ac7c5d5, 05eddbb)

---

## Completed: Wave 0 Foundation (10/10 tasks)

| # | Task | Key Files |
|---|------|-----------|
| 1 | Console script | `avatar/main.py`, `pyproject.toml` |
| 2 | Pre-commit config | `.pre-commit-config.yaml` |
| 3 | Bandit config | `.bandit.yaml` |
| 4 | Test tree migration | `tests/` unified, `avatar/tests/` deleted |
| 5 | Pytest sitl marker | `tests/conftest.py` (--run-sitl, sitl marker) |
| 6 | ConnectionConfig | `avatar/mav/connection_config.py`, circular import fixes |
| 7 | MCP validation | `scripts/validate_mcp_server.py`, `avatar_mcp_tool_definitions()` |
| 8 | PX4 SIH probe | Target: `sihsim_quadx` |
| 9 | SIH constants | `avatar/sim/constants.py` |
| 10 | Changelog | `CHANGELOG.md` |

## Gate Results

```
✅ avatar --version → 1.0.0
✅ python scripts/validate_mcp_server.py → Passed: 5/5 (26 tools)
⚠️ pytest -q -m "not slow and not hardware_in_loop" → 699 passed, 16 pre-existing failures
```

**16 pre-existing failures** are mock object issues in:
- `tests/tools/test_fly_body_offset.py` (12 failures)
- `tests/tools/test_hold.py` (1 failure)
- `tests/tools/test_set_velocity.py` (3 failures)

These are spec §3 "broken wires" — Wave 1 scope.

---

## Next: Wave 1 (32 tasks, 3 parallel streams)

**D2 Safety spine (11 tasks):**
- Wire ConfirmationManager into server
- EscalationMatrix as failsafe consumer
- AsyncGuardian calls `drone.action.*`
- OffboardOwner registry
- Altitude domain fixes

**D3 MCP hardening v1 (11 tasks):**
- Annotations (readOnlyHint, destructiveHint, etc.)
- outputSchema for all tools
- Structured error envelope
- ImageContent for vision
- ping/cancel_operation tools

**D4 Docker sim infrastructure (10 tasks):**
- `docker/sim-sih/Dockerfile`
- `docker/sim-gazebo/Dockerfile`
- `docker/compose.yaml`
- `scripts/sim.sh`

**W1 Gate:** `scripts/sim.sh scenario smoke_failsafe_rtl && pytest tests/mcp_server/test_compliance.py`

---

## Plans Location

```
docs/superpowers/plans/
├── 2026-04-16-wave-0-foundation.md ← COMPLETE
├── 2026-04-16-wave-1-spines.md ← NEXT
├── 2026-04-16-wave-2a-mcp-expansion.md
├── 2026-04-16-wave-2b-intel-providers-scenarios.md
├── 2026-04-16-wave-3-integration.md
└── 2026-04-16-wave-4-hitl-runbook.md
```

**Wave 2b fix-pass:** Already committed — plan expanded with full TDD specs for D8.10-D8.19 and D8.22-D8.28.

---

## Signature Contract (do NOT rename)

- `avatar/mcp_server/errors.py` → `ErrorCode` + `to_error_envelope()`
- `avatar/mcp_server/confirmation.py` → `ConfirmationManager`
- `avatar/mav/offboard_owner.py` → `OffboardOwner`
- `avatar/mav/offboard_streamer.py` → `OffboardVelocityStreamer`
- `avatar/mav/heartbeat_service.py` → agent-liveness only
- `avatar/mav/guardian_async.py` → `AsyncGuardian.initiate_*`
- `avatar/mav/escalation_matrix.py` → failsafe-policy consumer
- `avatar/sim/constants.py` → `SIH_VEHICLE_TARGET = "sihsim_quadx"`

---

## Execution Instructions for Next Agent

1. Read this handoff file
2. Run: `pytest -q -m "not slow and not hardware_in_loop"` to verify baseline
3. Await user approval for Wave 1
4. If approved, read `docs/superpowers/plans/2026-04-16-wave-1-spines.md`
5. Create branch `wave-1-spines` from `main`
6. Execute D2, D3, D4 in **parallel** (independent streams)
7. Use `subagent-driven-development` for each task

---

## Scheduled Loop

- **30-minute loop** scheduled via CronCreate (job ID: 17a881d8)
- Prompt: Check progress, continue implementation, do NOT auto-chain waves

---

**DELETE THIS FILE AFTER READING** — context should be fresh after compaction.
