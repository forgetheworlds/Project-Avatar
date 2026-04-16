"""Migration guard test - verifies avatar/tests tree was removed.

This test ensures the test migration from avatar/tests/ to tests/ was completed.
It fails if the old avatar/tests directory still exists.
"""


def test_avatar_tests_tree_removed() -> None:
    """VALIDATES: avatar/tests directory no longer exists after migration.

    The test migration moved all tests from avatar/tests/ to tests/.
    This guard test ensures the migration is complete and prevents
    accidental re-creation of the old structure.
    """
    from pathlib import Path
    assert not Path("avatar/tests").exists()
