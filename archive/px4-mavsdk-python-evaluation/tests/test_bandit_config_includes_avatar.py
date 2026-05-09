from __future__ import annotations

from pathlib import Path

import yaml


def test_bandit_includes_avatar_tree() -> None:
    cfg = yaml.safe_load(Path(".bandit.yaml").read_text())
    include = cfg["include"]
    assert "./avatar/**/*.py" in include
    assert "./src/**/*.py" not in include
    assert "./drone/**/*.py" not in include
