"""Hypothesis configuration for property-based tests.

This module configures Hypothesis for property-based testing of the
drone control system. Property tests find edge cases that traditional
unit tests might miss.
"""
import pytest
from hypothesis import settings, Verbosity

# Configure Hypothesis profiles for different environments
settings.register_profile("ci", max_examples=50, deadline=None, derandomize=True)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.normal)
settings.register_profile("debug", max_examples=100, verbosity=Verbosity.verbose)
settings.register_profile("thorough", max_examples=500, deadline=None)

# Default to CI profile for deterministic testing
settings.load_profile("ci")


@pytest.fixture(scope="module")
def hypothesis_settings():
    """Provide hypothesis settings for property-based tests.

    Returns:
        Hypothesis settings object configured for CI.
    """
    return settings(max_examples=50)
