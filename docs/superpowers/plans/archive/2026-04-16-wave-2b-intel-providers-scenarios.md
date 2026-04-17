# Wave 2b: Intelligence + Providers + Scenario Framework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 2b (D7 hardware vision providers, D8 mission-intelligence package with OSM/SRTM/Google Maps, D9 RuntimeProfile v2, D10 scenario YAML + driver framework) so first-flight-ready intelligence and simulation harness align with the first-flight-ready spec.

**Architecture:** Split into four parallel streams after W2a + W1 D4 Docker infra: (D7) async vision provider registry wired from `RuntimeProfile` backends; (D8) offline-first `avatar/mission_intel/` with pluggable mapping/elevation providers, deterministic intent grammar, seven read-only MCP tools; (D9) Pydantic v2 profile loader with airframe templates and PX4 overlay preflight gate; (D10) YAML-driven scenario runner with injection, assertions, artifacts, and nine drivers. Gazebo-tier scenarios validate rich sim paths.

**Tech Stack:** Python 3.12+, Pydantic v2, `httpx`/`aiohttp`, `pytest`, `respx` (HTTP mocking for GMaps), `av` (PyAV) for RTSP, optional `pyrealsense2` / `depthai` / `ultralytics` / NCNN / OpenVINO, Gazebo Harmonic `gz transport` / `gz topic -e` fallback, MCP SDK patterns from `avatar/mcp_server/server.py`.

**Status:** COMPLETED - Wave 2b intel and scenarios merged to main.

**Archive date:** 2026-04-17
