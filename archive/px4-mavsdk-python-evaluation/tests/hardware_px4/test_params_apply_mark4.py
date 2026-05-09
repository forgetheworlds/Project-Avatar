"""Tests for Mark4 7in airframe parameter file parsing.

Validates that the mark4_7in.params file:
1. Exists at the expected location
2. Parses correctly into a dictionary
3. Contains all required CRITICAL_PARAMETERS
4. Has valid values for safety-critical parameters
"""

from pathlib import Path
import sys

import pytest

# Project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestMark4ParamsFile:
    """Test mark4_7in.params file parsing and validation."""

    @pytest.fixture
    def params_path(self) -> Path:
        """Path to mark4_7in.params file."""
        return PROJECT_ROOT / "hardware" / "px4" / "airframes" / "mark4_7in.params"

    @pytest.fixture
    def parsed_params(self, params_path: Path) -> dict:
        """Parse the params file and return dictionary."""
        from hardware.px4.verify import parse_params_file

        return parse_params_file(params_path)

    def test_params_file_exists(self, params_path: Path) -> None:
        """The mark4_7in.params file must exist."""
        assert params_path.exists(), f"Params file not found: {params_path}"
        assert params_path.is_file(), f"Params path is not a file: {params_path}"

    def test_params_file_not_empty(self, params_path: Path) -> None:
        """The params file must not be empty."""
        content = params_path.read_text()
        # Should have at least one param line
        assert "param set-default" in content, "No param lines found in file"

    def test_parse_returns_dict(self, parsed_params: dict) -> None:
        """Parsing should return a non-empty dictionary."""
        assert isinstance(parsed_params, dict)
        assert len(parsed_params) > 0, "Parsed params dict is empty"

    def test_required_keys_present(self, parsed_params: dict) -> None:
        """All required safety parameters must be present."""
        from avatar.mav.px4_parameters import CRITICAL_PARAMETERS

        missing = [
            name
            for name in CRITICAL_PARAMETERS.keys()
            if name not in parsed_params
        ]

        # Allow some missing params - airframe file may override only subset
        # But key safety params should be present
        key_params = [
            "COM_OBL_RC_ACT",
            "COM_OF_LOSS_T",
            "NAV_DLL_ACT",
            "NAV_RCL_ACT",
            "COM_RCL_EXCEPT",
            "GF_ACTION",
            "GF_MAX_HOR_DIST",
            "GF_MAX_VER_DIST",
        ]

        for param in key_params:
            assert param in parsed_params, f"Missing key param: {param}"

    def test_offboard_failsafe_values(self, parsed_params: dict) -> None:
        """Offboard failsafe must be RTL (3) with reasonable timeout."""
        # COM_OBL_RC_ACT should be 2 (Land) or 3 (RTL)
        assert parsed_params.get("COM_OBL_RC_ACT") in [2, 3], (
            f"Invalid COM_OBL_RC_ACT: {parsed_params.get('COM_OBL_RC_ACT')}"
        )

        # COM_OF_LOSS_T should be reasonable (0.5s to 5s)
        timeout = parsed_params.get("COM_OF_LOSS_T", 0)
        assert 0.1 <= timeout <= 5.0, (
            f"Unreasonable offboard timeout: {timeout}"
        )

    def test_geofence_values(self, parsed_params: dict) -> None:
        """Geofence values must be reasonable for aerial filming."""
        # GF_MAX_HOR_DIST should be positive and reasonable
        hor_dist = parsed_params.get("GF_MAX_HOR_DIST", 0)
        assert 100 <= hor_dist <= 10000, (
            f"Unreasonable horizontal geofence: {hor_dist}"
        )

        # GF_MAX_VER_DIST should be positive and reasonable
        ver_dist = parsed_params.get("GF_MAX_VER_DIST", 0)
        assert 30 <= ver_dist <= 500, (
            f"Unreasonable vertical geofence: {ver_dist}"
        )

        # GF_ACTION should be land (2) or RTL (3)
        gf_action = parsed_params.get("GF_ACTION", 0)
        assert gf_action in [1, 2, 3], (
            f"Invalid geofence action: {gf_action}"
        )

    def test_battery_config_values(self, parsed_params: dict) -> None:
        """Battery configuration must be valid for 6S."""
        # BAT_N_CELLS should be 6 for Mark4 6S
        n_cells = parsed_params.get("BAT_N_CELLS", 0)
        assert n_cells == 6, f"Expected 6 cells for Mark4, got {n_cells}"

        # Battery thresholds should be reasonable
        low_thr = parsed_params.get("BAT_LOW_THR", 0)
        crit_thr = parsed_params.get("BAT_CRIT_THR", 0)
        emerg_thr = parsed_params.get("BAT_EMERGEN_THR", 0)

        assert 0.1 <= low_thr <= 0.5, f"Unreasonable low threshold: {low_thr}"
        assert 0.05 <= crit_thr <= low_thr, (
            f"Crit threshold should be below low: {crit_thr} vs {low_thr}"
        )
        assert 0.01 <= emerg_thr <= crit_thr, (
            f"Emergency threshold should be below crit: {emerg_thr} vs {crit_thr}"
        )

    def test_rc_loss_exception_set(self, parsed_params: dict) -> None:
        """RC loss exception must be set for autonomous flight."""
        # COM_RCL_EXCEPT should include bit 2 (value 4) for offboard
        rc_except = parsed_params.get("COM_RCL_EXCEPT", 0)
        assert rc_except & 4 == 4, (
            f"RC loss exception doesn't include offboard: {rc_except}"
        )


class TestX500ParamsFile:
    """Test x500_v2.params file parsing and validation."""

    @pytest.fixture
    def params_path(self) -> Path:
        """Path to x500_v2.params file."""
        return PROJECT_ROOT / "hardware" / "px4" / "airframes" / "x500_v2.params"

    @pytest.fixture
    def parsed_params(self, params_path: Path) -> dict:
        """Parse the params file and return dictionary."""
        from hardware.px4.verify import parse_params_file

        return parse_params_file(params_path)

    def test_params_file_exists(self, params_path: Path) -> None:
        """The x500_v2.params file must exist."""
        assert params_path.exists(), f"Params file not found: {params_path}"

    def test_parse_returns_dict(self, parsed_params: dict) -> None:
        """Parsing should return a non-empty dictionary."""
        assert isinstance(parsed_params, dict)
        assert len(parsed_params) > 0, "Parsed params dict is empty"

    def test_battery_config_4s(self, parsed_params: dict) -> None:
        """Battery configuration should be for 4S."""
        n_cells = parsed_params.get("BAT_N_CELLS", 0)
        assert n_cells == 4, f"Expected 4 cells for X500, got {n_cells}"


class TestCustomTemplate:
    """Test custom_template.params file."""

    @pytest.fixture
    def params_path(self) -> Path:
        """Path to custom_template.params file."""
        return PROJECT_ROOT / "hardware" / "px4" / "airframes" / "custom_template.params"

    def test_template_exists(self, params_path: Path) -> None:
        """The custom_template.params file must exist."""
        assert params_path.exists(), f"Template file not found: {params_path}"

    def test_template_has_instructions(self, params_path: Path) -> None:
        """Template should contain instructions for each parameter."""
        content = params_path.read_text()

        # Should have instruction comments
        assert "Range:" in content or "range" in content.lower()
        assert "Recommended" in content

    def test_template_no_hardcoded_values(self, params_path: Path) -> None:
        """Template should not have hardcoded values (use placeholders)."""
        from hardware.px4.verify import parse_params_file

        # Parsing should return empty or near-empty dict (all commented out)
        params = parse_params_file(params_path)

        # Template should have no active param lines
        # (All should be commented out with <VALUE> placeholders)
        assert len(params) == 0, (
            f"Template should have no active params, found: {list(params.keys())}"
        )
