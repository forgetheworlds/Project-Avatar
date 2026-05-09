from __future__ import annotations

from pathlib import Path

import yaml


def _all_local_hooks() -> dict[str, dict]:
    """Collect hooks from all local repos into a single dict."""
    raw = yaml.safe_load(Path(".pre-commit-config.yaml").read_text())
    hooks = {}
    for repo in raw["repos"]:
        if repo.get("repo") == "local":
            for hook in repo.get("hooks", []):
                hooks[hook["id"]] = hook
    return hooks


def test_precommit_pytest_targets_tests_root() -> None:
    hooks = _all_local_hooks()
    pt = hooks["pytest-check"]["args"]
    assert "tests" in pt
    assert "tests/unit" not in pt
    cov = hooks["coverage-check"]["args"]
    assert any(a.startswith("--cov=avatar") for a in cov)
    assert "tests/unit" not in cov


def test_check_import_cycles_imports_avatar() -> None:
    hooks = _all_local_hooks()
    entry = hooks["check-import-cycles"]["entry"]
    assert "import avatar" in entry
