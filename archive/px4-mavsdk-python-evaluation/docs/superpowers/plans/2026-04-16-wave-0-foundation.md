# Wave 0: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Task count:** 11 (Tasks 1–7, 8a, 8b, 9).

**Goal:** Deliver Wave 0 (D1) foundation: working `avatar` CLI, lint hooks aligned to `avatar/`, unified `tests/` tree, pytest-native SITL gating, removal of legacy `avatar/mav/connection.py`, MCP tool-count validation tied to `server.py`, and a pinned PX4 SIH target constant so downstream Docker work can import one string.

**Architecture:** Keep Wave 0 changes mechanical: thin CLI delegates to the existing async MCP `main`, pre-commit and Bandit scan the real package layout, all pytest collection lives under `tests/`, SITL tests use a registered `sitl` marker plus `--run-sitl`, legacy `DroneConnection` implementation is deleted while `ConnectionConfig` and the compat-layer `DroneConnection` shim remain, and the MCP validator derives tool count from the same tool list the server exposes (via a single extracted catalog function in `server.py`).

**Tech Stack:** Python 3.12 (target), pydantic v2, pytest + pytest-asyncio, Ruff, mypy, bandit, pre-commit, Hatchling, MAVSDK-Python, MCP SDK.

---

## Wave Scope

- Repair packaging and repo hygiene: `avatar` console script, pre-commit coverage/pytest/import-cycle hooks, Bandit include globs, and `pyproject.toml` test discovery so CI and local runs agree on `tests/` only.
- Collapse the split test tree (`avatar/tests/` → `tests/`) and replace brittle `sys.argv` SITL detection with pytest configuration (`pytest_addoption`, `sitl` marker).
- Remove legacy `avatar/mav/connection.py` by relocating `ConnectionConfig` and re-pointing all imports at `avatar/mav/connection_config.py` plus `avatar/mcp_server/compat.DroneConnection` where a shim is required.
- Pin the PX4 SIH make target string in `avatar/sim/constants.py` after an upstream probe, and make `scripts/validate_mcp_server.py` assert live tool count (with optional `--expected-count`).

## Dependencies

None. Wave 0 is the root of the dependency graph in the first-flight spec.

## Wave Gate

Reproduce W0 from `docs/superpowers/specs/2026-04-16-project-avatar-first-flight-plan-design.md` §11 verbatim:

| Wave | Gate | Verification |
|---|---|---|
| W0 | Lint/mypy/bandit clean; console script runs; unified test suite passes; validator script matches live tool count | `pytest -q -m "not slow and not hardware_in_loop" && avatar --version && python scripts/validate_mcp_server.py` |

## Branch Setup

Create branch `wave-0-foundation` from `main`. All tasks below commit on this branch. Do not merge until the W0 gate command above passes on a clean working tree.

---

### Task 1: Console script and `avatar/main.py`

**Files:**

- Create: `avatar/main.py`
- Modify: `pyproject.toml` (lines 10–10 `requires-python`, 78–79 `[project.scripts]`, 99–100 `[tool.mypy] python_version`, 420–421 `[tool.ruff] target-version` — align declared 3.12 with the shared contract)

- [ ] **Step 1: Write the failing test**

Create `tests/test_avatar_entrypoint.py`:

```python
from __future__ import annotations

import importlib.metadata

import avatar.main as entry


def test_version_flag(capsys: object) -> None:
    entry.main(["--version"])
    assert capsys.readouterr().out.strip() == importlib.metadata.version("drone-control-system")


def test_main_delegates_to_server_main(monkeypatch: object) -> None:
    recorded: list[str] = []

    def fake_run(coro: object) -> None:
        recorded.append(type(coro).__name__)

    monkeypatch.setattr(entry.asyncio, "run", fake_run)
    entry.main([])
    assert recorded == ["coroutine"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_avatar_entrypoint.py -v`

Expected: `ModuleNotFoundError: No module named 'avatar.main'` or import error.

- [ ] **Step 3: Write minimal implementation**

Create `avatar/main.py`:

```python
"""Console entry for the `avatar` setuptools script (Wave 0)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from importlib.metadata import version


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server, or print ``--version`` and exit."""
    parser = argparse.ArgumentParser(prog="avatar")
    parser.add_argument("--version", action="store_true", help="Print package version and exit.")
    ns, _unknown = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    if ns.version:
        print(version("drone-control-system"))
        return

    from avatar.mcp_server.server import main as srv_main

    asyncio.run(srv_main())
```

Modify `pyproject.toml`:

```toml
requires-python = ">=3.12"
```

(under `[project]`)

```toml
[project.scripts]
avatar = "avatar.main:main"
```

(unchanged entry point path; now resolves)

```toml
python_version = "3.12"
```

(under `[tool.mypy]`)

```toml
target-version = "py312"
```

(under `[tool.ruff]`)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_avatar_entrypoint.py -v`

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add avatar/main.py pyproject.toml tests/test_avatar_entrypoint.py
git commit -m "feat: add avatar CLI entrypoint and Python 3.12 metadata"
```

---

### Task 2: Repair `.pre-commit-config.yaml` for `avatar/`

**Files:**

- Modify: `.pre-commit-config.yaml` (hooks `pytest-check`, `coverage-check`, `check-import-cycles`, lines 254–347)

- [ ] **Step 1: Write the failing test**

Create `tests/test_precommit_config_paths.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


def test_precommit_pytest_targets_tests_root() -> None:
    raw = yaml.safe_load(Path(".pre-commit-config.yaml").read_text())
    repos = raw["repos"]
    local = next(r for r in repos if r.get("repo") == "local")
    hooks = {h["id"]: h for h in local["hooks"]}
    pt = hooks["pytest-check"]["args"]
    assert "tests" in pt
    assert "tests/unit" not in pt
    cov = hooks["coverage-check"]["args"]
    assert any(a.startswith("--cov=avatar") for a in cov)
    assert "tests/unit" not in cov


def test_check_import_cycles_imports_avatar() -> None:
    raw = yaml.safe_load(Path(".pre-commit-config.yaml").read_text())
    repos = raw["repos"]
    local = next(r for r in repos if r.get("repo") == "local")
    hooks = {h["id"]: h for h in local["hooks"]}
    entry = hooks["check-import-cycles"]["entry"]
    assert "import avatar" in entry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_precommit_config_paths.py -v`

Expected: `AssertionError` on one of the assertions.

- [ ] **Step 3: Write minimal implementation**

Replace the `pytest-check` hook `args` block with:

```yaml
        args:
          - -q
          - tests
          - --tb=short
          - --timeout=60
          - -m
          - "not slow and not hardware_in_loop"
```

Replace the `coverage-check` hook `args` block with:

```yaml
        args:
          - --cov=avatar
          - --cov-fail-under=90
          - --cov-report=term-missing
          - tests
          - -m
          - "not slow and not hardware_in_loop"
```

Replace `check-import-cycles` `entry` with:

```yaml
        entry: python -c "import avatar"
```

Remove `-xvs` from pytest-check if present (use `-q` as above for faster pre-push).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_precommit_config_paths.py -v`

Expected: `2 passed`

- [ ] **Step 5: Run pre-commit locally**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && pre-commit run --all-files --hook-stage pre-commit`

Expected: tail contains `Passed` / `All checks passed` with no hook failures (mypy/ruff may report issues fixed in later tasks; if failures are pre-existing, fix only what this task’s YAML breaks, or document follow-up — prefer fixing obvious path-related errors in this commit).

- [ ] **Step 6: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add .pre-commit-config.yaml tests/test_precommit_config_paths.py
git commit -m "fix: align pre-commit pytest and coverage with avatar/"
```

---

### Task 3: Repair `.bandit.yaml` include globs

**Files:**

- Modify: `.bandit.yaml` (section `include`, lines 127–131)

- [ ] **Step 1: Write the failing test**

Create `tests/test_bandit_config_includes_avatar.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml


def test_bandit_includes_avatar_tree() -> None:
    cfg = yaml.safe_load(Path(".bandit.yaml").read_text())
    include = cfg["include"]
    assert "./avatar/**/*.py" in include
    assert "./src/**/*.py" not in include
    assert "./drone/**/*.py" not in include
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_bandit_config_includes_avatar.py -v`

Expected: `AssertionError`

- [ ] **Step 3: Write minimal implementation**

Set `include` to:

```yaml
include:
  - "./avatar/**/*.py"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_bandit_config_includes_avatar.py -v`

Expected: `1 passed`

- [ ] **Step 5: Run bandit**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && bandit -r -c .bandit.yaml avatar`

Expected: `Total issues (By severity):` with zero high/medium if clean; if findings exist, fix or inline `# nosec` only with justification in the same commit scope (prefer real fixes).

- [ ] **Step 6: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add .bandit.yaml tests/test_bandit_config_includes_avatar.py
git commit -m "fix: point bandit includes at avatar package tree"
```

---

### Task 4: Migrate `avatar/tests/` into `tests/` (single migration commit)

**Files:**

- Move: `avatar/tests/test_vision_pipeline.py` → `tests/test_vision_pipeline.py`
- Move: `avatar/tests/test_safety_scenarios.py` → `tests/test_safety_scenarios.py`
- Move: `avatar/tests/test_mcp_tools.py` → `tests/test_mcp_tools.py`
- Move: `avatar/tests/test_sitl_basic.py` → `tests/test_sitl_basic.py`
- Move: `avatar/tests/mav/test_px4_parameters.py` → `tests/mav/test_px4_parameters.py`
- Move: `avatar/tests/tools/test_set_velocity.py` → `tests/tools/test_set_velocity.py`
- Remove: `avatar/tests/__init__.py` after migration
- Replace: `tests/conftest.py` (merge with former `avatar/tests/conftest.py`)
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]` `testpaths = ["tests"]` only; extend `markers` with `sitl` in Task 5 — do not add `sitl` in this commit if you want strict one-topic commits; **prefer** adding `sitl` marker only in Task 5 and keep Task 4 markers unchanged)
- Modify: `pyproject.toml` `[[tool.mypy.overrides]]` module list: replace `avatar.tests.*` with `tests.*`

- [ ] **Step 1: Write the failing test**

Add `tests/test_pytest_collects_only_tests_package.py`:

```python
from __future__ import annotations

from pathlib import Path


def test_avatar_tests_tree_removed() -> None:
    assert not Path("avatar/tests").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_pytest_collects_only_tests_package.py -v`

Expected: `AssertionError` (directory still exists).

- [ ] **Step 3: Move test modules and merge conftest**

Run moves:

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git mv avatar/tests/test_vision_pipeline.py tests/test_vision_pipeline.py
git mv avatar/tests/test_safety_scenarios.py tests/test_safety_scenarios.py
git mv avatar/tests/test_mcp_tools.py tests/test_mcp_tools.py
git mv avatar/tests/test_sitl_basic.py tests/test_sitl_basic.py
git mv avatar/tests/mav/test_px4_parameters.py tests/mav/test_px4_parameters.py
git mv avatar/tests/tools/test_set_velocity.py tests/tools/test_set_velocity.py
```

Generate merged `tests/conftest.py` with this **complete** script. Run it **before** `git rm avatar/tests/conftest.py` while `avatar/tests/conftest.py` is still on disk (other test modules may already be `git mv`’d):

```python
from pathlib import Path

root_lines = Path("tests/conftest.py").read_text().splitlines()
hyp_block = "\n".join(root_lines[65:110])
av_lines = Path("avatar/tests/conftest.py").read_text().splitlines()
body = "\n".join(av_lines[74:])
merged = "\n".join(
    [
        '"""Unified pytest configuration for Project Avatar (Wave 0 migration)."""',
        "",
        "import asyncio",
        "from typing import AsyncGenerator",
        "from unittest.mock import AsyncMock, MagicMock, patch",
        "",
        "import pytest",
        "",
        hyp_block,
        "",
        body,
    ]
).replace("\nn    WHY", "\n    WHY")
Path("tests/conftest.py").write_text(merged + "\n")
print("Wrote tests/conftest.py", len(merged.splitlines()), "lines")
```

Then:

```bash
git rm avatar/tests/conftest.py
git rm avatar/tests/__init__.py
rmdir avatar/tests/mav 2>/dev/null || true
rmdir avatar/tests/tools 2>/dev/null || true
rmdir avatar/tests 2>/dev/null || true
```

Update `pyproject.toml`:

```toml
testpaths = ["tests"]
```

Change mypy override block from:

```toml
    "avatar.tests.*",
```

to:

```toml
    "tests.*",
```

- [ ] **Step 4: Run pytest collection**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest --collect-only -q 2>&1 | tail -n 5`

Expected: ends with `no tests collected` **false** — you should see a non-zero test count; no import errors mentioning `avatar.tests`.

- [ ] **Step 5: Run migration guard test**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_pytest_collects_only_tests_package.py -v`

Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add tests/ pyproject.toml
git add -u avatar/tests
git commit -m "refactor: migrate avatar/tests into unified tests tree"
```

---

### Task 5: Pytest-native `--run-sitl` and `sitl` marker

**Files:**

- Modify: `tests/conftest.py` (add hooks at end of file)
- Modify: `pyproject.toml` (`markers` list)
- Modify: `tests/test_sitl_basic.py` (remove `sys` argv skip; use marker + pytest hook)
- Modify: `avatar/sim/scenarios.py` (acceptance_test strings that reference pytest CLI — update paths only if they still said `avatar/tests`; keep `--run-sitl` flag text once it exists as a real option)

- [ ] **Step 1: Write the failing test**

Create `tests/test_sitl_marker_behavior.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_sitl_tests_skipped_without_flag() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(Path("tests/test_sitl_basic.py")),
            "-m",
            "sitl",
            "-q",
            "--collect-only",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert "deselected" in out or "skipped" in out or "no tests collected" in out


def test_not_sitl_excludes_sitl_marker() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(Path("tests/test_sitl_basic.py")),
            "-m",
            "not sitl",
            "-q",
            "--collect-only",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert "test_connection" not in out or "deselected" in out
```

Refine after implementation: collection output varies. Prefer asserting exit code 0 and `0/6 selected` style — tune assertions once hooks exist.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_sitl_marker_behavior.py -v`

Expected: failure until hooks/markers exist.

- [ ] **Step 3: Implement pytest hooks and marker**

Append to `tests/conftest.py`:

```python


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-sitl",
        action="store_true",
        default=False,
        help="Run SITL integration tests that require a live PX4 SITL instance.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "sitl: requires PX4 SITL and --run-sitl")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-sitl"):
        return
    skip = pytest.mark.skip(reason="SITL tests require PX4 SITL running and --run-sitl")
    for item in items:
        if "sitl" in item.keywords:
            item.add_marker(skip)
```

Add to `pyproject.toml` under `markers = [`:

```toml
    "sitl: marks tests that require PX4 SITL and --run-sitl",
```

In `tests/test_sitl_basic.py`, **delete** lines 38–55 (`import sys` only if unused elsewhere; remove `sys.argv` skip and `pytestmark = pytest.mark.skipif(...)`).

Add after imports:

```python
pytestmark = [pytest.mark.sitl, pytest.mark.integration, pytest.mark.hardware_in_loop, pytest.mark.slow]
```

Apply per-test markers already present — replace module-level `pytestmark` with the list above **including** `pytest.mark.sitl` once for the module, and remove duplicate `pytest.mark.integration` on each test if redundant (optional cleanup; minimal change is module-level `pytestmark` only).

Minimal edit: remove `sys` import if unused; remove `skipif` block; add:

```python
pytestmark = pytest.mark.sitl
```

Keep existing per-function markers.

- [ ] **Step 4: Run targeted tests**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_sitl_basic.py -m "not sitl" -q`

Expected: `X deselected` / `no tests ran` / exit 0 with skips — not failures.

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_sitl_basic.py --run-sitl -m sitl --collect-only -q`

Expected: lists `test_connection` etc. as selected (six tests).

- [ ] **Step 5: Run new marker tests**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_sitl_marker_behavior.py -v`

Expected: `2 passed` (adjust assertions to match pytest output format).

- [ ] **Step 6: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add tests/conftest.py tests/test_sitl_basic.py tests/test_sitl_marker_behavior.py pyproject.toml avatar/sim/scenarios.py
git commit -m "test: gate SITL tests behind pytest --run-sitl and sitl marker"
```

---

### Task 6: Extract `ConnectionConfig`, delete `avatar/mav/connection.py`, fix imports

**Files:**

- Create: `avatar/mav/connection_config.py` (dataclass `ConnectionConfig` and `MavsdkError` alias copied from `avatar/mav/connection.py` lines 108–143)
- Modify: `avatar/mcp_server/compat.py` (import `ConnectionConfig` from `avatar.mav.connection_config` instead of `avatar.mav.connection`)
- Modify: `avatar/mcp_server/tools/flight_tools.py` (import `DroneConnection` from `avatar.mcp_server.compat`, `ConnectionConfig` from `avatar.mav.connection_config`)
- Modify: `avatar/mcp_server/tools/telemetry_tools.py` (same import change)
- Modify: `tests/conftest.py` (fixture `mock_drone_connection`: same import change)
- Modify: `tests/test_mcp_tools.py` (replace `from avatar.mav.connection import ...` with `from avatar.mav.connection_config import ConnectionConfig` and `from avatar.mcp_server.compat import DroneConnection` as needed)
- Modify: `pyproject.toml` (mypy override: remove `avatar.mav.connection` entry; add `avatar.mav.connection_config` if strict errors — mirror `connection` override line 153)
- Delete: `avatar/mav/connection.py`

- [ ] **Step 1: Write the failing test**

Add `tests/test_connection_legacy_module_removed.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


def test_connection_py_deleted() -> None:
    assert not Path("avatar/mav/connection.py").exists()


def test_connection_config_importable() -> None:
    from avatar.mav.connection_config import ConnectionConfig

    assert ConnectionConfig().system_address == "udp://:14540"


def test_drone_connection_shim_in_compat() -> None:
    from avatar.mcp_server.compat import DroneConnection

    assert DroneConnection.__module__ == "avatar.mcp_server.compat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_connection_legacy_module_removed.py -v`

Expected: `FAILED` on `connection.py` exists.

- [ ] **Step 3: Add `avatar/mav/connection_config.py`**

Create `avatar/mav/connection_config.py`:

```python
"""MAVLink connection settings shared by tools and compat shims."""

from __future__ import annotations

from dataclasses import dataclass

MavsdkError = Exception


@dataclass
class ConnectionConfig:
    """Configuration parameters for MAVSDK drone connection."""

    system_address: str = "udp://:14540"
    max_retries: int = 3
    retry_delay_s: float = 1.0
    health_timeout_s: float = 30.0
```

- [ ] **Step 4: Update all imports and delete legacy file**

Apply import edits listed under **Files** above. In `compat.py`, replace:

```python
from avatar.mav.connection import ConnectionConfig as NewConnectionConfig
```

with:

```python
from avatar.mav.connection_config import ConnectionConfig as NewConnectionConfig
```

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && rg 'from avatar\.mav\.connection import|import avatar\.mav\.connection' --glob '*.py'`

Expected: **no matches** (update docstring examples in `compat.py` that show old import paths so they reference `avatar.mav.connection_config` / `avatar.mcp_server.compat` instead of executable `from avatar.mav.connection import`).

Delete `avatar/mav/connection.py`:

```bash
git rm avatar/mav/connection.py
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_connection_legacy_module_removed.py tests/test_mcp_tools.py -v --tb=short -m "not slow and not hardware_in_loop"`

Expected: `passed` for collected items (may skip some; no import errors).

- [ ] **Step 6: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add avatar/mav/connection_config.py avatar/mcp_server/compat.py avatar/mcp_server/tools/flight_tools.py avatar/mcp_server/tools/telemetry_tools.py tests/conftest.py tests/test_mcp_tools.py tests/test_connection_legacy_module_removed.py pyproject.toml
git add -u avatar/mav/connection.py
git commit -m "refactor: remove legacy mav connection module; centralize ConnectionConfig"
```

---

### Task 7: `scripts/validate_mcp_server.py` introspected tool count and `--expected-count`

**Files:**

- Modify: `avatar/mcp_server/server.py` (extract the tool list returned by `handle_list_tools` into a module-level `def avatar_mcp_tool_definitions() -> list[types.Tool]:` returning the same list; change `handle_list_tools` to `return avatar_mcp_tool_definitions()`)
- Modify: `scripts/validate_mcp_server.py` (replace hard-coded tool list; add argparse)
- Add: `tests/test_validate_mcp_server_tool_count.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_validate_mcp_server_tool_count.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


def test_tool_definitions_count_matches_server_source() -> None:
    from avatar.mcp_server.server import avatar_mcp_tool_definitions

    tools = avatar_mcp_tool_definitions()
    names = {t.name for t in tools}
    assert len(names) == len(tools)
    assert len(tools) == 26


def test_validate_script_accepts_expected_count() -> None:
    import subprocess
    import sys

    script = Path("scripts/validate_mcp_server.py")
    proc = subprocess.run(
        [sys.executable, str(script), "--expected-count", "26"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_validate_mcp_server_tool_count.py -v`

Expected: `ImportError: cannot import name 'avatar_mcp_tool_definitions'`.

- [ ] **Step 3: Refactor `server.py` and rewrite validator**

In `avatar/mcp_server/server.py`, cut the entire list literal inside `handle_list_tools` (from `return [` through matching `]`) into a new top-level function placed **immediately above** `_setup_handlers` is not possible without class — define **after** imports of `types`:

```python
def avatar_mcp_tool_definitions() -> List[types.Tool]:
    return [
        # ... every existing types.Tool(...) entry unchanged order ...
    ]
```

Inside `AvatarMCPServer._setup_handlers`, replace the inner `handle_list_tools` body with:

```python
        async def handle_list_tools() -> List[types.Tool]:
            return avatar_mcp_tool_definitions()
```

Implement `scripts/validate_mcp_server.py` core logic (full replacement sketch — engineer must preserve existing print style where reasonable):

```python
#!/usr/bin/env python3
"""MCP Server Validation Script for Project Avatar (Wave 0)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def check_server_imports() -> bool:
    print("[1/5] Checking server imports...")
    try:
        import avatar.mcp_server.server as server_module  # noqa: F401

        print("  ✓ Server module imports successfully")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def check_tools_available(expected: int | None) -> bool:
    print("\n[2/5] Checking available tools...")
    try:
        from avatar.mcp_server.server import avatar_mcp_tool_definitions

        tools = avatar_mcp_tool_definitions()
        names = [t.name for t in tools]
        print(f"  ✓ {len(names)} tools registered:")
        for name in names:
            print(f"    - {name}")
        if expected is not None and len(names) != expected:
            print(f"  ✗ Expected {expected} tools, found {len(names)}")
            return False
        return True
    except Exception as e:
        print(f"  ✗ Tool check failed: {e}")
        return False


def check_mcp_configuration() -> bool:
    print("\n[3/5] Checking Claude Code MCP configuration...")
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        with settings_path.open() as f:
            settings = json.load(f)
        mcp_servers = settings.get("mcpServers", {})
        if "drone" in mcp_servers:
            print("  ✓ Drone MCP server registered in settings.json")
            drone_config = mcp_servers["drone"]
            print(
                f"    Command: {drone_config.get('command')} {' '.join(drone_config.get('args', []))}"
            )
            return True
        print("  ✗ Drone MCP server not found in settings.json")
        print("  ℹ Run: Claude will need to register the MCP server")
        return False
    except Exception as e:
        print(f"  ✗ Configuration check failed: {e}")
        return False


def check_core_components() -> bool:
    print("\n[4/5] Checking core MAV components...")
    try:
        from avatar.mav.connection_manager import ConnectionManager
        from avatar.mav.telemetry_cache import TelemetryCache
        from avatar.mav.heartbeat_service import HeartbeatService
        from avatar.mav.state_machine import FlightStateMachine
        from avatar.mav.guardian_async import AsyncGuardian

        _ = (ConnectionManager, TelemetryCache, HeartbeatService, FlightStateMachine, AsyncGuardian)
        print("  ✓ All core components importable")
        return True
    except Exception as e:
        print(f"  ✗ Component check failed: {e}")
        return False


def check_code_quality() -> bool:
    print("\n[5/5] Checking code quality...")
    try:
        root = _repo_root()
        test_count = sum(
            1
            for p in (root / "tests").rglob("test_*.py")
            if p.is_file()
        )
        print(f"  ✓ {test_count} test files under tests/")
        from avatar.core.decorators import require_state, retry, timeout  # noqa: F401
        from avatar.core.context_managers import FlightSession, managed_connection, managed_offboard  # noqa: F401

        print("  ✓ Safety decorators and context managers importable")
        return True
    except Exception as e:
        print(f"  ✗ Quality check failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Avatar MCP server installation.")
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="If set, fail when live tool count does not equal this number.",
    )
    args = parser.parse_args()

    checks = [
        check_server_imports,
        lambda: check_tools_available(args.expected_count),
        check_mcp_configuration,
        check_core_components,
        check_code_quality,
    ]

    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as exc:
            print(f"  ✗ Check failed with exception: {exc}")
            results.append(False)

    passed = sum(results)
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

Use `list[int] | None` only if `from __future__ import annotations` present (shown). Fix duplicate imports and match repo style (script above is illustrative; integrate with any retained checks from the original file).

- [ ] **Step 4: Run tests**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_validate_mcp_server_tool_count.py -v`

Expected: `2 passed`

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python scripts/validate_mcp_server.py --expected-count 26`

Expected: `Passed: 5/5` (or `4/5` if settings.json missing — W0 gate runs bare `python scripts/validate_mcp_server.py` without `--expected-count`; make settings check **non-fatal** for W0 if spec implies full pass: if settings optional, return True when file missing). **Adjust** `check_mcp_configuration` to return `True` with a printed warning when `settings.json` is absent so `python scripts/validate_mcp_server.py` passes in CI.

Updated `check_mcp_configuration`:

```python
    if not settings_path.is_file():
        print("  ℹ No ~/.claude/settings.json — skipping MCP client registration check")
        return True
```

- [ ] **Step 5: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add avatar/mcp_server/server.py scripts/validate_mcp_server.py tests/test_validate_mcp_server_tool_count.py
git commit -m "fix: validate MCP tool count from server tool definitions"
```

---

### Task 8a: Probe PX4 upstream for SIH vehicle target (commands only, record string)

**Files:**

- None required (documentation in execution notes); optional `docs/research/wave0-sih-target-probe.md` is **out of scope** per instruction not to add docs unless needed — record probed string in Task 8b commit.

- [ ] **Step 1: Clone or update PX4-Autopilot**

Run (adjust path if PX4 already present):

```bash
cd /Users/muadhsambul/Downloads
test -d PX4-Autopilot || git clone --depth 1 https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot && git pull --ff-only
```

Expected: `Already up to date.` or clone progress completes.

- [ ] **Step 2: List SITL targets containing `sih`**

Run:

```bash
cd /Users/muadhsambul/Downloads/PX4-Autopilot
make list_config_targets 2>/dev/null | rg -i sih || rg -n "sihsim" platforms/posix/cmake boards/px4 -S
```

Expected: lines such as `px4_sitl_default sihsim_quadx` or `sihsim_quadrotor` appear — **record the exact token** that pairs with `px4_sitl_default` for Software-In-Hardware quad.

- [ ] **Step 3: Cross-check cmake sitl target file**

Run:

```bash
rg -n "sihsim" PX4-Autopilot/platforms/posix/cmake -S | head -n 40
```

Expected: file path such as `platforms/posix/cmake/sitl_target.cmake` referencing `sihsim_*` targets.

- [ ] **Step 4: No commit** (probe is informational; string consumed in Task 8b)

---

### Task 8b: Add `avatar/sim/constants.py` with pinned `SIH_VEHICLE_TARGET`

**Files:**

- Create: `avatar/sim/constants.py`
- Modify: `avatar/sim/scenarios.py` only if you need to import the constant for DRY — **optional in Wave 0**; prefer leaving scenario strings unchanged unless they embed wrong target.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sim_constants_sih_target.py`:

```python
from __future__ import annotations

from avatar.sim import constants as c


def test_sih_vehicle_target_is_non_empty_ident() -> None:
    assert c.SIH_VEHICLE_TARGET
    assert c.SIH_VEHICLE_TARGET.replace("_", "").isalnum()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_sim_constants_sih_target.py -v`

Expected: `ModuleNotFoundError: avatar.sim.constants` or `AttributeError`.

- [ ] **Step 3: Implement `avatar/sim/constants.py`**

Use the **exact** string discovered in Task 8a. If Task 8a recorded `sihsim_quadx`, create:

```python
"""Simulation constants shared across Avatar SIH/Gazebo tooling.

`SIH_VEHICLE_TARGET` is the PX4 CMake / make target name for Software-In-Hardware
quad simulation, taken from upstream PX4-Autopilot (see
`platforms/posix/cmake/sitl_target*.cmake` on the probed commit).
"""

SIH_VEHICLE_TARGET: str = "sihsim_quadx"
```

If the probe yields a different string (for example `sihsim_quadrotor`), substitute that exact value for the right-hand side of `SIH_VEHICLE_TARGET`.

- [ ] **Step 4: Run test**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python -m pytest tests/test_sim_constants_sih_target.py -v`

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add avatar/sim/constants.py tests/test_sim_constants_sih_target.py
git commit -m "feat: pin PX4 SIH vehicle target for simulation tooling"
```

---

### Task 9: W0 gate, static checks, and changelog entry

**Files:**

- Modify: `CHANGELOG.md` (add `## [Unreleased]` or append under a new `0.5.1` section per project style — match existing heading levels)
- Optionally modify: `changes-made.md` if you maintain it in parallel (include one line "Wave 0 foundation complete")

- [ ] **Step 1: Run Ruff**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && ruff check avatar tests`

Expected: `All checks passed!`

- [ ] **Step 2: Run mypy**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && mypy avatar`

Expected: `Success: no issues found in ...` (fix any new errors introduced by Wave 0 files before claiming gate pass.)

- [ ] **Step 3: Run bandit**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && bandit -r -c .bandit.yaml avatar`

Expected: `No issues identified.` or equivalent summary with no high/medium issues.

- [ ] **Step 4: Run W0 pytest slice**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && pytest -q -m "not slow and not hardware_in_loop"`

Expected: final line like `XXXX passed` with **0 failed** (warnings acceptable if not errors).

- [ ] **Step 5: Run console and validator per gate**

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && avatar --version`

Expected: `1.0.0` printed to stdout.

Run: `cd /Users/muadhsambul/Downloads/Project-Avatar && python scripts/validate_mcp_server.py --expected-count 26`

Expected: `Passed: 5/5` (after optional settings soft-skip).

- [ ] **Step 6: Update changelog**

Append under `CHANGELOG.md` top section after `## [0.5.0]` block (create `## [Unreleased]` if missing):

```markdown
## [Unreleased]

### Changed

- Wave 0 foundation: unified `tests/` tree, pytest `--run-sitl` / `sitl` marker, removed legacy `avatar/mav/connection.py`, repaired pre-commit/Bandit paths for `avatar/`, MCP validator uses live tool definitions (26 tools), pinned `SIH_VEHICLE_TARGET` for PX4 SIH builds.
```

- [ ] **Step 7: Commit**

```bash
cd /Users/muadhsambul/Downloads/Project-Avatar
git add CHANGELOG.md changes-made.md 2>/dev/null || git add CHANGELOG.md
git commit -m "docs: record Wave 0 foundation completion"
```

---

## Self-Review

**1. Spec coverage (§4 Wave 0 D1 + §11 W0):**

| Requirement | Task |
|---|---|
| Console script / `avatar/main.py` | Task 1 |
| `.pre-commit-config.yaml` coverage + pytest + import cycles → `avatar/` / `tests` | Task 2 |
| `.bandit.yaml` include globs | Task 3 |
| Delete `avatar/mav/connection.py` + import updates | Task 6 (+ `rg` cleanup) |
| Migrate `avatar/tests/` → `tests/`, `testpaths` | Task 4 |
| Replace `sys.argv` `--run-sitl` with pytest option + marker | Task 5 |
| `scripts/validate_mcp_server.py` live tool count | Task 7 |
| Probe SIH target + `avatar/sim/constants.py` | Task 8a + 8b |
| W0 verification command + changelog | Task 9 |

**2. Placeholder scan:** No `TODO`/`TBD` strings intentionally left; `SIH_VEHICLE_TARGET` literal must be replaced with probed upstream value if differs from `sihsim_quadx`. Task 8b Step 3 calls this out explicitly (not an open-ended placeholder).

**3. Type consistency:** `ConnectionConfig` lives only in `avatar/mav/connection_config.py`; `DroneConnection` shim remains in `avatar/mcp_server/compat.py`; `avatar_mcp_tool_definitions()` returns the same `List[types.Tool]` type as the former inner handler.

**4. Downstream wave naming (§6 / §10 skim):** No MCP tool renames in Wave 0; `avatar_mcp_tool_definitions` preserves existing tool `name=` strings for Wave 1 annotation work.
