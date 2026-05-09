# Wave 3: Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 3 integration: twelve declarative pipeline scenarios with subprocess tests, GitHub Actions CI (PR fast path, nightly Gazebo matrix, release digest pinning), Raspberry Pi OS image + flash + systemd bring-up, and PX4 flash/calibration/verify/preflight tooling — all gated by W3 verification commands.

**Architecture:** Four parallel streams (D11–D14) branch from completed W2a/W2b: D11 adds YAML scenarios under `avatar/sim/scenarios/` plus `tests/sim/scenarios/` wrappers that shell out to `scripts/run-scenario.sh`; D12 adds `.github/workflows/` and helper scripts with caching and artifact retention; D13 bakes operator-facing Pi provisioning under `hardware/pi/`; D14 bakes FC provisioning under `hardware/px4/` with `.params` overlays aligned to `PX4ParameterManager` and a dry-run preflight CLI.

**Tech stack:** YAML 1.2, pytest + subprocess, GitHub Actions (Ubuntu), Docker Buildx, shellcheck, systemd, cloud-init, PX4 `upload.py` / QGC-style param files, MAVSDK-Python, Python 3.12.

**Status:** COMPLETED - Wave 3 integration merged to main.

**Archive date:** 2026-04-17
