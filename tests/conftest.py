"""Root conftest for pytest configuration."""
import pytest


@pytest.fixture(scope="session")
def hypothesis_settings():
    """Provide hypothesis settings for property-based tests."""
    from hypothesis import settings
    return settings(max_examples=50)
