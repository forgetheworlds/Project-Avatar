# Wave 1: Spines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 1 parallel spines—safety spine (D2), MCP hardening v1 (D3), and Docker simulation infrastructure (D4)—so first-flight tooling meets the W1 gate in spec section 11.

**Architecture:** D2 centralizes failsafe policy in `EscalationMatrix` with async MAVSDK handlers, splits agent liveness (`HeartbeatService`) from offboard setpoint ownership (`OffboardOwner` + `OffboardVelocityStreamer`), and wires `ConfirmationManager` into the MCP server with a curated policy module. D3 standardizes every MCP tool with annotations, `outputSchema`, structured error envelopes, singleton tool services, cancel-safe loops, and two new control-plane tools. D4 adds reproducible SIH and Gazebo Docker tiers plus compose profiles and shell entrypoints; scenario execution remains a thin stub until Wave 2b fills `avatar/sim/runner.py`.

**Tech Stack:** Python 3.12+, MAVSDK-Python, MCP SDK (`mcp`), Ruff, pytest, Docker / Docker Compose, PX4 SITL (SIH + `gz_x500`), bash.

**Status:** COMPLETED - Wave 1 spines merged to main.

**Archive date:** 2026-04-17
