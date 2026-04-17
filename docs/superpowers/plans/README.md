# Superpowers implementation plans

This directory contains implementation plans for Project Avatar's first-flight-ready wave sequence.

## Active

| Plan | Status | Description |
|------|--------|-------------|
| [2026-04-16-wave-4-hitl-runbook.md](2026-04-16-wave-4-hitl-runbook.md) | In progress | Wave 4: HITL harness, runbooks, trivial-flash, repo polish |

## Archive

Completed wave plans are in [archive/](archive/):

| Plan | Description |
|------|-------------|
| [wave-0-foundation.md](archive/2026-04-16-wave-0-foundation.md) | Wave 0: Unified tests, pytest SITL gating, MCP validation, SIH target pin |
| [wave-1-spines.md](archive/2026-04-16-wave-1-spines.md) | Wave 1: Safety spine, MCP hardening v1, Docker sim infrastructure |
| [wave-2a-mcp-expansion.md](archive/2026-04-16-wave-2a-mcp-expansion.md) | Wave 2a: 16 MCP primitives, 6 orchestrators, cinematic merge |
| [wave-2b-intel-providers-scenarios.md](archive/2026-04-16-wave-2b-intel-providers-scenarios.md) | Wave 2b: Mission intel, vision providers, RuntimeProfile v2, scenario framework |
| [wave-3-integration.md](archive/2026-04-16-wave-3-integration.md) | Wave 3: 12 scenario pipelines, GitHub Actions CI, Pi/PX4 provisioning |

## Spec

The authoritative design document is:

- [2026-04-16-project-avatar-first-flight-plan-design.md](../specs/2026-04-16-project-avatar-first-flight-plan-design.md) — First-flight-ready spec with wave gates (section 11)

## Wave gate summary

| Wave | Gate | Verification |
|------|------|--------------|
| W0 | Unified tests + MCP validator | `pytest tests/ -q && scripts/validate_mcp_server.py` |
| W1 | Safety spine + Docker SIH | `scripts/sim.sh sih && scripts/test-sih-smoke.sh` |
| W2a | 51 MCP tools | `scripts/validate_mcp_server.py --expected-count 51` |
| W2b | Mission intel + scenarios | `pytest tests/sim/test_scenarios.py -q` |
| W3 | 12 scenario pipelines + CI | `scripts/sim.sh all-scenarios` + green CI |
| W4 | HITL preflight + runbooks | `pytest tests/hitl -m preflight --run-hitl` |
