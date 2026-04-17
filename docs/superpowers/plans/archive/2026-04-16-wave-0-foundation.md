# Wave 0: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Task count:** 11 (Tasks 1–7, 8a, 8b, 9).

**Goal:** Deliver Wave 0 (D1) foundation: working `avatar` CLI, lint hooks aligned to `avatar/`, unified `tests/` tree, pytest-native SITL gating, removal of legacy `avatar/mav/connection.py`, MCP tool-count validation tied to `server.py`, and a pinned PX4 SIH target constant so downstream Docker work can import one string.

**Architecture:** Keep Wave 0 changes mechanical: thin CLI delegates to the existing async MCP `main`, pre-commit and Bandit scan the real package layout, all pytest collection lives under `tests/`, SITL tests use a registered `sitl` marker plus `--run-sitl`, legacy `DroneConnection` implementation is deleted while `ConnectionConfig` and the compat-layer `DroneConnection` shim remain, and the MCP validator derives tool count from the same tool list the server exposes (via a single extracted catalog function in `server.py`).

**Tech Stack:** Python 3.12 (target), pydantic v2, pytest + pytest-asyncio, Ruff, mypy, bandit, pre-commit, Hatchling, MAVSDK-Python, MCP SDK.

**Status:** COMPLETED - Wave 0 foundation merged to main.

**Archive date:** 2026-04-17
