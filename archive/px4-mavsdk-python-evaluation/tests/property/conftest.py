"""Hypothesis configuration for property-based tests.

WHAT IS CONFTEST.PY?
--------------------
conftest.py is a special pytest file that pytest automatically discovers and loads
before running any tests in the same directory or subdirectories. It provides:
- Shared fixtures (test dependencies)
- Library configuration (like Hypothesis settings below)
- Custom hooks to modify test behavior

Key characteristics:
- Automatically loaded by pytest - no imports needed in test files
- Applies to all tests in the same folder and subfolders
- Can define fixtures that multiple tests can share
- Perfect for configuring testing libraries like Hypothesis

WHAT ARE FIXTURES?
------------------
Fixtures are pytest's way of providing test dependencies. They handle:
- Setup: Preparing the environment/objects needed for tests
- Teardown: Cleaning up after tests complete (even if they fail)
- Reuse: Same setup can be shared across multiple tests
- Scope control: Fixtures can run once per test, module, or entire test session

How fixtures work:
1. You define a fixture using the @pytest.fixture decorator
2. Tests request fixtures by including them as function parameters
3. pytest automatically calls the fixture, yields the value, then cleans up
4. The 'yield' statement separates setup (before yield) from teardown (after yield)

SETUP/TEARDOWN PATTERN
----------------------
Fixtures use Python generators (the 'yield' keyword) for setup/teardown:

    @pytest.fixture
    def my_fixture():
        # SETUP: Runs before the test - create resources, configure systems
        resource = create_resource()
        yield resource  # Provides the resource to the test
        # TEARDOWN: Runs after the test completes (even if it failed!)
        resource.cleanup()

This file contains one fixture that provides Hypothesis settings.

WHAT IS PROPERTY-BASED TESTING?
-------------------------------
Property-based testing (with Hypothesis) is different from traditional unit tests:

Traditional test:
    def test_addition():
        assert add(2, 3) == 5  # Test one specific case

Property-based test:
    @given(st.integers(), st.integers())  # Generate random integers
    def test_addition_commutative(a, b):
        assert add(a, b) == add(b, a)  # Test property, not specific values

Benefits:
- Finds edge cases you didn't think of
- Tests thousands of scenarios automatically
- Documents behavior/properties of your code

WHAT THIS CONFTEST PROVIDES
-----------------------------
This conftest.py configures Hypothesis for property-based testing of the
drone control system. It includes:

1. Multiple Hypothesis profiles for different environments (CI, dev, debug)
2. A hypothesis_settings fixture that provides settings for tests
"""

import pytest

hypothesis = pytest.importorskip(
    "hypothesis", reason="hypothesis is required for property tests"
)
settings = hypothesis.settings
Verbosity = hypothesis.Verbosity

# =============================================================================
# HYPOTHESIS PROFILE CONFIGURATION
# =============================================================================
# Hypothesis profiles let us have different settings for different environments.
# We can switch profiles with: hypothesis.settings.load_profile("profile_name")

# CI profile: Fast, deterministic testing for continuous integration
# - max_examples=50: Run 50 test cases per test
# - deadline=None: Disable timing checks (CI can be slow)
# - derandomize=True: Same test cases every run for reproducibility
settings.register_profile("ci", max_examples=50, deadline=None, derandomize=True)

# Dev profile: Quick feedback during development
# - max_examples=10: Just 10 cases for fast feedback
# - verbosity=normal: Standard output level
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.normal)

# Debug profile: Verbose output for debugging test failures
# - max_examples=100: More cases to catch edge cases
# - verbosity=verbose: Lots of output about what's being tested
settings.register_profile("debug", max_examples=100, verbosity=Verbosity.verbose)

# Thorough profile: Exhaustive testing before releases
# - max_examples=500: Many test cases
# - deadline=None: No timing constraints
settings.register_profile("thorough", max_examples=500, deadline=None)

# Default to CI profile for deterministic testing in CI/CD pipelines
# Developers can override by setting HYPOTHESIS_PROFILE env var
settings.load_profile("ci")


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="module")
def hypothesis_settings():
    """Provide hypothesis settings for property-based tests.

    WHAT IT PROVIDES:
        A Hypothesis settings object configured for the current environment.
        This is useful when tests need to create custom strategies or
        override settings for specific tests.

    SCOPE: module
        The same settings object is shared across all tests in a module.
        This is efficient since settings are immutable once created.

    SETUP: Returns the current Hypothesis settings object
    TEARDOWN: None needed (settings are immutable)

    RETURNS:
        Hypothesis settings object with max_examples=50 (CI profile)

    USAGE IN TESTS:
        @given(st.lists(st.integers()))
        def test_with_settings(data, hypothesis_settings):
            # Can reference settings if needed
            assert len(data) <= hypothesis_settings.max_examples * 2

        # Or use in custom strategies:
        def test_custom_strategy(hypothesis_settings):
            from hypothesis import given, strategies as st

            @given(st.data())
            def test(data):
                # Use settings to configure custom generation
                pass
    """
    return settings(max_examples=50)
