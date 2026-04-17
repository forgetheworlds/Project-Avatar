# Wave 2a: Core MCP Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 2a (D5 + D6): sixteen low-level MCP primitives, six high-level orchestrators, merge `cinematic_shots_personal.py` into `cinematic_shots.py` with typed per-template overrides, and register `acrobatic_sequence` with Guardian preflight plus ConfirmationManager per section 10 item 7—each tool schema-validated, annotated, unit-tested, and wired through `AvatarMCPServer` without regressing the existing baseline tool set.

**Architecture:** Shared Pydantic models and JSON Schema live in `avatar/mcp_server/schemas.py` (minimal Mission v1.0 subset, forward-compatible with W2b). New handlers live in `avatar/mcp_server/tools/primitives.py` and `avatar/mcp_server/tools/orchestrators.py`, registered from `avatar/mcp_server/server.py` alongside Wave-1 `errors.py` structured envelopes, `ConfirmationManager`, `OffboardOwner`, and `AsyncGuardian.preflight` (W1 contract). Destructive tools call `await guardian.preflight(tool=..., payload=...)` before MAVSDK; curated confirmations use `ConfirmationManager.require(...)`.

**Tech Stack:** Python 3.12+, Pydantic v2 (`model_json_schema`), MCP Python SDK `types.Tool` with `inputSchema` / `outputSchema` / annotations, pytest + pytest-asyncio, MAVSDK-Python (mocked in unit tests), existing `OffboardVelocityStreamer`, `FlightRecorder`, `KalmanTracker` / `TrackingState` from `advanced_tracking.py`.

**Status:** COMPLETED - Wave 2a MCP expansion merged to main.

**Archive date:** 2026-04-17
