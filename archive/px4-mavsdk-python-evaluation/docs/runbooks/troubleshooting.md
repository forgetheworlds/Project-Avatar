# MCP troubleshooting

Map structured MCP errors (`isError: true` envelope) to operator actions.

| Code | Typical cause | Remediation | Escalation |
|------|---------------|-------------|------------|
| `GUARDIAN_VIOLATION` | Safety gatekeeper rejected operation | Check Guardian limits (altitude, geofence, speed). Reduce command to within safe bounds. | If limits appear incorrect: verify params against `hardware/px4/airframes/` overlay. |
| `OFFBOARD_OWNERSHIP_CONFLICT` | OffboardOwner already acquired by another session | Ensure only one MCP client controls offboard at a time. Stop other sessions. | If conflict persists after disconnecting all clients: restart MAVSDK server and FC. |
| `CONFIRMATION_REQUIRED` | Operation needs user confirmation | Respond to confirmation prompt with `confirm_token` from the confirmation workflow. | If confirmation workflow stuck: check `avatar.mcp_server.confirmation` logs. |
| `CONFIRMATION_EXPIRED` | Confirmation token timed out | Re-issue the original command to get a fresh confirmation token. | If tokens expire immediately: check system clock sync and token TTL config. |
| `MAV_COMMAND_REJECTED` | Drone rejected MAVLink command | Check drone state (armed, in-air, mode). Verify command is valid for current flight mode. | Capture flight log and PX4 ulog; verify PX4 params. |
| `MAV_TIMEOUT` | MAVLink command timed out | Check serial/UDP connection. Verify FC is powered and responsive. Increase timeout if needed. | If timeouts persist: check cable, baud rate, FC health. |
| `MAV_NOT_CONNECTED` | No connection to drone | Verify FC is powered, USB cable connected, or UDP link active. Check `mavsdk_server` status. | Check `/dev/pixhawk` symlink, udev rules, MAVSDK process. |
| `PREFLIGHT_BLOCKED` | Preflight checks failed | Run `hardware/px4/preflight.py` for detailed failure report. Fix reported issues. | If preflight fails unexpectedly: compare params vs `hardware/px4/airframes/` overlay. |
| `PROVIDER_UNAVAILABLE` | External provider unavailable | Check network connectivity to Kimi/Google Maps API. Verify API keys are configured. | If provider down: check Fireworks/Google status pages; use offline fallback if available. |
| `QUOTA_EXCEEDED` | API quota or resource limit exceeded | Wait for quota reset or upgrade API tier. Reduce request frequency. | Log quota usage patterns; consider caching or request batching. |
| `INVALID_MISSION` | Mission definition is invalid | Verify mission JSON schema. Check waypoint coordinates are within geofence. | If valid mission rejected: check Guardian geofence config. |
| `MISSION_SPEC_ERROR` | Mission spec parsing/formatting error | Verify mission spec syntax. Check for missing required fields. | Compare mission spec to schema in `avatar/mcp_server/schemas.py`. |
| `ALTITUDE_DOMAIN_AMBIGUOUS` | Altitude reference frame unclear | Specify `altitude_domain` (AGL vs AMSL) explicitly in mission/command. | If domain still ambiguous: check local terrain database. |
| `PARAMETER_NOT_FOUND` | PX4 parameter does not exist | Verify parameter name is correct for this PX4 version. Check airframe overlay. | If param missing in newer PX4: check release notes for renamed/removed params. |
| `PARAMETER_OUT_OF_RANGE` | Parameter value outside bounds | Set value within min/max bounds reported by PX4. | If bounds seem wrong: verify against PX4 docs for your version. |
| `CANCELLED` | Operation cancelled by user | No action needed—this is expected user-initiated cancellation. | If unexpected cancellation: check for stray abort signals. |
| `INTERNAL_ERROR` | Unexpected internal error | Check server logs for stack trace. Retry operation after brief wait. | If repeats: capture logs, ulog, flight_recorder JSONL; file bug report. |
| `NOT_IMPLEMENTED` | Feature not yet implemented | Use an alternative tool or workflow. Check roadmap for implementation timeline. | No escalation—this is a known limitation. |
| `SCHEMA_VALIDATION_FAILED` | Input schema validation failed | Check input parameters match expected types and ranges. | If schema appears correct: compare against `avatar/mcp_server/schemas.py`. |

## Notes

- Agents branch on `code`, not `message`.
- Escalation means: stop autonomous flight, capture logs, do not retry until root cause class is understood.
- Airspace and weather tooling are out of scope (spec section 13); MCP errors never imply legal clearance to fly.
