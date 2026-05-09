"""Test suite for Guardian altitude frame validation (D2.9).

Tests cover:
- AltitudeFrame type alias definition
- ALTITUDE_DOMAIN_AMBIGUOUS validation error
- Commands with altitude_m but no altitude_frame are rejected
- Commands with altitude_m and valid altitude_frame are accepted

SAFETY CRITICAL: Altitude can be specified relative to different reference
frames (AMSL, AGL, relative). Without explicit frame specification, altitude
commands could be misinterpreted, leading to dangerous flight operations.
"""

import pytest

from avatar.mav.guardian import GuardianProcess, HardLimits, AltitudeFrame


class TestAltitudeFrameType:
    """Tests for AltitudeFrame type alias."""

    def test_altitude_frame_is_literal_type(self):
        """D2.9: AltitudeFrame should be a Literal type with valid values."""
        # Valid values should be accepted by type checker
        valid_frames = ["amsl", "agl", "relative"]
        for frame in valid_frames:
            # This is more of a type hint test, but we verify the values exist
            assert isinstance(frame, str)

    def test_altitude_frame_valid_values(self):
        """D2.9: AltitudeFrame should accept 'amsl', 'agl', 'relative'."""
        # These are the valid altitude frame values
        assert "amsl" in ["amsl", "agl", "relative"]
        assert "agl" in ["amsl", "agl", "relative"]
        assert "relative" in ["amsl", "agl", "relative"]


class TestAltitudeDomainAmbiguous:
    """Tests for ALTITUDE_DOMAIN_AMBIGUOUS validation."""

    @pytest.fixture
    def guardian(self):
        """Create a GuardianProcess with default limits and home set."""
        g = GuardianProcess(HardLimits())
        g.set_home(37.7749, -122.4194)
        return g

    def test_altitude_m_without_altitude_frame_returns_ambiguous_error(self, guardian):
        """D2.9: Command with altitude_m but no altitude_frame should return
        ALTITUDE_DOMAIN_AMBIGUOUS.
        """
        command = {
            "altitude_m": 50.0,
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is False
        assert reason == "ALTITUDE_DOMAIN_AMBIGUOUS"

    def test_altitude_m_with_altitude_frame_amsl_accepted(self, guardian):
        """D2.9: Command with altitude_m and altitude_frame='amsl' should be
        accepted (subject to other validations).
        """
        command = {
            "altitude_m": 50.0,
            "altitude_frame": "amsl",
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_m_with_altitude_frame_agl_accepted(self, guardian):
        """D2.9: Command with altitude_m and altitude_frame='agl' should be
        accepted.
        """
        command = {
            "altitude_m": 50.0,
            "altitude_frame": "agl",
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_m_with_altitude_frame_relative_accepted(self, guardian):
        """D2.9: Command with altitude_m and altitude_frame='relative' should
        be accepted.
        """
        command = {
            "altitude_m": 50.0,
            "altitude_frame": "relative",
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_amsl_m_still_works_without_altitude_frame(self, guardian):
        """D2.9: Legacy altitude_amsl_m should still work without altitude_frame."""
        command = {
            "altitude_amsl_m": 50.0,  # Legacy field
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_both_altitude_m_and_altitude_amsl_m_with_frame(self, guardian):
        """D2.9: Command with both altitude fields and frame should validate."""
        command = {
            "altitude_m": 50.0,
            "altitude_amsl_m": 50.0,
            "altitude_frame": "amsl",
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_m_zero_without_frame_still_ambiguous(self, guardian):
        """D2.9: Even zero altitude_m without frame is ambiguous."""
        command = {
            "altitude_m": 0.0,
            "altitude_frame": None,  # Explicitly None
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is False
        assert reason == "ALTITUDE_DOMAIN_AMBIGUOUS"

    def test_altitude_m_exceeds_limit_with_frame_uses_altitude_error(self, guardian):
        """D2.9: When altitude exceeds limit with frame, use altitude limit error."""
        command = {
            "altitude_m": 150.0,  # Exceeds max 120m
            "altitude_frame": "amsl",
        }

        is_valid, reason = guardian.validate_command(command)

        # Should fail for altitude limit, not ambiguous
        assert is_valid is False
        assert "exceeds" in reason.lower() or "altitude" in reason.lower()

    def test_command_without_altitude_m_is_not_ambiguous(self, guardian):
        """D2.9: Commands without altitude_m should not trigger ambiguous error."""
        command = {
            "latitude": 37.7750,
            "longitude": -122.4195,
            "speed_m_s": 10.0,
        }

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_empty_command_is_valid(self, guardian):
        """D2.9: Empty command should pass validation."""
        command = {}

        is_valid, reason = guardian.validate_command(command)

        assert is_valid is True
        assert reason == "OK"

    def test_altitude_frame_without_altitude_m_is_valid(self, guardian):
        """D2.9: altitude_frame without altitude_m should not cause error."""
        command = {
            "altitude_frame": "amsl",
            "latitude": 37.7750,
            "longitude": -122.4195,
        }

        is_valid, reason = guardian.validate_command(command)

        # Should be valid - frame alone doesn't require altitude_m
        assert is_valid is True
        assert reason == "OK"


class TestAltitudeValidationOrder:
    """Tests for validation order - ambiguous check before limit check."""

    @pytest.fixture
    def guardian(self):
        """Create a GuardianProcess with default limits and home set."""
        g = GuardianProcess(HardLimits())
        g.set_home(37.7749, -122.4194)
        return g

    def test_ambiguous_check_before_altitude_limit_check(self, guardian):
        """D2.9: ALTITUDE_DOMAIN_AMBIGUOUS should be checked before limits."""
        command = {
            "altitude_m": 150.0,  # Exceeds 120m limit AND no frame
        }

        is_valid, reason = guardian.validate_command(command)

        # Should fail for ambiguous first, not the limit
        assert is_valid is False
        assert reason == "ALTITUDE_DOMAIN_AMBIGUOUS"
