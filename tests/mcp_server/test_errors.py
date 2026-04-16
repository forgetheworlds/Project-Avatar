"""Tests for ErrorCode enum and structured error envelope.

This module tests the D2.1 error handling contract that downstream
waves depend on for structured error responses.
"""

from avatar.mcp_server.errors import _CODE_CATEGORY, ErrorCode, to_error_envelope


class TestErrorCodeEnum:
    """Tests for ErrorCode StrEnum."""

    def test_error_code_is_strenum(self) -> None:
        """ErrorCode should be a StrEnum (string values)."""
        assert isinstance(ErrorCode.GUARDIAN_VIOLATION, str)
        assert ErrorCode.GUARDIAN_VIOLATION == "GUARDIAN_VIOLATION"

    def test_error_code_has_19_codes(self) -> None:
        """ErrorCode must have exactly 19 codes as per contract."""
        expected_codes = {
            "GUARDIAN_VIOLATION",
            "OFFBOARD_OWNERSHIP_CONFLICT",
            "CONFIRMATION_REQUIRED",
            "CONFIRMATION_EXPIRED",
            "MAV_COMMAND_REJECTED",
            "MAV_TIMEOUT",
            "MAV_NOT_CONNECTED",
            "PREFLIGHT_BLOCKED",
            "PROVIDER_UNAVAILABLE",
            "QUOTA_EXCEEDED",
            "INVALID_MISSION",
            "MISSION_SPEC_ERROR",
            "ALTITUDE_DOMAIN_AMBIGUOUS",
            "PARAMETER_NOT_FOUND",
            "PARAMETER_OUT_OF_RANGE",
            "CANCELLED",
            "INTERNAL_ERROR",
            "NOT_IMPLEMENTED",
            "SCHEMA_VALIDATION_FAILED",
        }
        actual_codes = {code.name for code in ErrorCode}
        assert actual_codes == expected_codes, f"Missing or extra codes: {actual_codes.symmetric_difference(expected_codes)}"

    def test_all_codes_have_category_mapping(self) -> None:
        """Every ErrorCode must have a category in _CODE_CATEGORY."""
        for code in ErrorCode:
            assert code in _CODE_CATEGORY, f"Missing category mapping for {code}"


class TestCodeCategory:
    """Tests for _CODE_CATEGORY mapping."""

    def test_category_values_are_valid(self) -> None:
        """Categories must be one of the allowed values."""
        valid_categories = {"safety", "operator", "mavlink", "runtime", "mission", "parameter", "input"}
        for code, category in _CODE_CATEGORY.items():
            assert category in valid_categories, f"Invalid category '{category}' for {code}"

    def test_safety_codes_mapping(self) -> None:
        """Safety-related codes should map to 'safety' category."""
        safety_codes = {
            ErrorCode.GUARDIAN_VIOLATION,
            ErrorCode.OFFBOARD_OWNERSHIP_CONFLICT,
            ErrorCode.PREFLIGHT_BLOCKED,
        }
        for code in safety_codes:
            assert _CODE_CATEGORY[code] == "safety"

    def test_operator_codes_mapping(self) -> None:
        """Operator-related codes should map to 'operator' category."""
        operator_codes = {
            ErrorCode.CONFIRMATION_REQUIRED,
            ErrorCode.CONFIRMATION_EXPIRED,
            ErrorCode.CANCELLED,
        }
        for code in operator_codes:
            assert _CODE_CATEGORY[code] == "operator"

    def test_mavlink_codes_mapping(self) -> None:
        """MAVLink-related codes should map to 'mavlink' category."""
        mavlink_codes = {
            ErrorCode.MAV_COMMAND_REJECTED,
            ErrorCode.MAV_TIMEOUT,
            ErrorCode.MAV_NOT_CONNECTED,
        }
        for code in mavlink_codes:
            assert _CODE_CATEGORY[code] == "mavlink"

    def test_mission_codes_mapping(self) -> None:
        """Mission-related codes should map to 'mission' category."""
        mission_codes = {
            ErrorCode.INVALID_MISSION,
            ErrorCode.MISSION_SPEC_ERROR,
            ErrorCode.ALTITUDE_DOMAIN_AMBIGUOUS,
        }
        for code in mission_codes:
            assert _CODE_CATEGORY[code] == "mission"

    def test_parameter_codes_mapping(self) -> None:
        """Parameter-related codes should map to 'parameter' category."""
        parameter_codes = {
            ErrorCode.PARAMETER_NOT_FOUND,
            ErrorCode.PARAMETER_OUT_OF_RANGE,
        }
        for code in parameter_codes:
            assert _CODE_CATEGORY[code] == "parameter"

    def test_input_codes_mapping(self) -> None:
        """Input validation codes should map to 'input' category."""
        input_codes = {
            ErrorCode.SCHEMA_VALIDATION_FAILED,
        }
        for code in input_codes:
            assert _CODE_CATEGORY[code] == "input"

    def test_runtime_codes_mapping(self) -> None:
        """Runtime-related codes should map to 'runtime' category."""
        runtime_codes = {
            ErrorCode.PROVIDER_UNAVAILABLE,
            ErrorCode.QUOTA_EXCEEDED,
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.NOT_IMPLEMENTED,
        }
        for code in runtime_codes:
            assert _CODE_CATEGORY[code] == "runtime"


class TestToErrorEnvelope:
    """Tests for to_error_envelope function."""

    def test_to_error_envelope_shape(self) -> None:
        """Error envelope must have the correct structure."""
        envelope = to_error_envelope(
            ErrorCode.GUARDIAN_VIOLATION,
            "Safety violation occurred",
            recoverable=False,
        )

        # Top-level structure
        assert "isError" in envelope
        assert envelope["isError"] is True
        assert "error" in envelope

        # Error object structure
        error = envelope["error"]
        assert "code" in error
        assert "category" in error
        assert "message" in error
        assert "recoverable" in error

        # Verify values
        assert error["code"] == "GUARDIAN_VIOLATION"
        assert error["category"] == "safety"
        assert error["message"] == "Safety violation occurred"
        assert error["recoverable"] is False

    def test_to_error_envelope_with_recoverable_true(self) -> None:
        """Error envelope should preserve recoverable=True."""
        envelope = to_error_envelope(
            ErrorCode.MAV_TIMEOUT,
            "Command timed out, retry possible",
            recoverable=True,
        )

        assert envelope["error"]["recoverable"] is True

    def test_to_error_envelope_with_suggested_action(self) -> None:
        """Error envelope should include suggested_action when provided."""
        envelope = to_error_envelope(
            ErrorCode.MAV_TIMEOUT,
            "Command timed out",
            recoverable=True,
            suggested_action="Retry the command with a longer timeout",
        )

        assert "suggestedAction" in envelope["error"]
        assert envelope["error"]["suggestedAction"] == "Retry the command with a longer timeout"

    def test_to_error_envelope_with_details(self) -> None:
        """Error envelope should include details when provided."""
        details = {"timeout_ms": 5000, "command": "MAV_CMD_DO_SET_MODE"}
        envelope = to_error_envelope(
            ErrorCode.MAV_TIMEOUT,
            "Command timed out",
            recoverable=True,
            details=details,
        )

        assert "details" in envelope["error"]
        assert envelope["error"]["details"] == details

    def test_to_error_envelope_without_optional_fields(self) -> None:
        """Error envelope should not include optional fields when not provided."""
        envelope = to_error_envelope(
            ErrorCode.INTERNAL_ERROR,
            "Internal server error",
            recoverable=False,
        )

        # Optional fields should not be present when not provided
        assert "suggestedAction" not in envelope["error"]
        assert "details" not in envelope["error"]

    def test_to_error_envelope_category_from_mapping(self) -> None:
        """Category should be automatically derived from _CODE_CATEGORY."""
        envelope = to_error_envelope(
            ErrorCode.PARAMETER_OUT_OF_RANGE,
            "Parameter value out of range",
            recoverable=False,
        )

        assert envelope["error"]["category"] == "parameter"

    def test_to_error_envelope_all_codes(self) -> None:
        """All error codes should produce valid envelopes."""
        for code in ErrorCode:
            envelope = to_error_envelope(
                code,
                f"Error with {code.name}",
                recoverable=True,
            )

            assert envelope["isError"] is True
            assert envelope["error"]["code"] == code.value
            assert envelope["error"]["category"] == _CODE_CATEGORY[code]
            assert isinstance(envelope["error"]["message"], str)
            assert isinstance(envelope["error"]["recoverable"], bool)
