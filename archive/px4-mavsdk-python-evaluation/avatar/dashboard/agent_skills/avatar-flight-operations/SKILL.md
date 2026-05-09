---
name: avatar-flight-operations
description: Use when the Project Avatar flight deck operator asks for takeoff, landing, movement, position, velocity, return-to-launch, hold, acrobatics, cinematic shots, or hardware/SITL flight control.
---

# Avatar Flight Operations

## Operating Loop
Use this loop for every movement request:
1. Read current status, telemetry, battery, health, flight mode, and safety state.
2. Confirm the environment: SITL or hardware.
3. Run or request preflight when state is stale or before arming.
4. Pick the smallest reversible command.
5. Execute through Avatar MCP tools only.
6. Verify the outcome through telemetry.

## Safety Gates
- First arm/takeoff needs explicit operator confirmation unless session `auto_confirm` is enabled for CI/SITL.
- Never bypass Guardian, geofence, battery thresholds, PX4 failsafes, or confirmation policy.
- Prefer `hold`, `land`, or `rtl` when telemetry is stale, target confidence is low, or state is ambiguous.
- Acrobatic tools require explicit confirmation and SITL-first testing.

## Command Selection
- “Stop”, “wait”, “pause”, uncertain state -> hold.
- “Come back”, low battery, link issues -> RTL.
- “Go to coordinate” -> validate geofence and altitude frame.
- “Follow/orbit/reveal” -> use orchestrator/cinematic tools with bounded radius, speed, altitude, and duration.
- “Move a little” -> use bounded velocity/body-offset primitives.

## Common Mistakes
- Do not claim motion happened without telemetry confirmation.
- Do not use raw shell commands to bypass MCP flight tools.
- Do not convert relative altitude to AMSL unless the tool requires it.

