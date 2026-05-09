"""Runtime profiles for SITL and hardware connection boundaries.

Pydantic v2 models with layered configuration for Project Avatar.

================================================================================
ARCHITECTURE: Layered Configuration
================================================================================

Configuration is loaded in order of increasing precedence:
    1. BASE DEFAULTS (hardcoded in model defaults)
    2. FILE CONFIG (YAML/JSON from profile_path)
    3. ENV OVERRIDES (environment variables with AVATAR_ prefix)
    4. SECRETS (environment variables with AVATAR_SECRET_ prefix)

Layer precedence: SECRETS > ENV > FILE > DEFAULTS

================================================================================
USAGE
================================================================================

Basic profile loading:
    >>> from avatar.config.profiles import RuntimeProfile, load_profile
    >>> profile = load_profile("sitl")
    >>> print(profile.system_address)
    udp://:14540

From YAML file with env overrides:
    >>> # config/sitl.yaml:
    >>> # name: sitl
    >>> # system_address: udp://:14540
    >>> # airframe: x500_v2
    >>> profile = load_profile("sitl", config_path="config/sitl.yaml")

With PX4 parameter verification:
    >>> if profile.requires_px4_parameter_check:
    ...     results = await verify_profile_parameters(profile, drone)
    ...     if not all(r.is_valid for r in results):
    ...         raise SafetyError("Parameter mismatch")

================================================================================
AIRFRAME TEMPLATES
================================================================================

Airframe templates define hardware-specific configuration:

    mark4_7in:
        - Mark4 7" frame
        - Pixhawk 6C Mini
        - Raspberry Pi 4
        - Pi Camera 3 Wide

    x500_v2:
        - PX4 X500 v2 development frame
        - Standard SITL simulation target

    custom:
        - User-defined airframe
        - Requires all fields specified

================================================================================
SAFETY INTEGRATION
================================================================================

The `requires_px4_parameter_check` flag enables preflight safety verification:

1. If True: PX4ParameterManager.verify_safety_parameters() is called with
   the airframe's param_overlay before flight operations begin.

2. Mismatches block startup - this is a HARD GATE for safety-critical ops.

3. The param_overlay allows per-airframe parameter customization beyond
   the default CRITICAL_PARAMETERS.

================================================================================
COM_OBL_RC_ACT CONFIGURATION
================================================================================

COM_OBL_RC_ACT controls offboard loss failsafe behavior:

    0: Disabled (DANGEROUS - no automatic action)
    1: Land at current position
    2: RTL (Return to Launch) - DEFAULT, safest for filming
    3: Hold position (loiter)

For filming operations, RTL (2) is recommended because:
    - Preserves equipment for recovery
    - Predictable return path
    - Can resume mission after link restored
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

# COM_OBL_RC_ACT parameter values for offboard loss failsafe action
# 0: Disable, 1: Land, 2: Return to Launch, 3: Hold position
ComOblRcAct = Literal[0, 1, 2, 3]

# Airframe template identifiers
AirframeId = Literal["mark4_7in", "x500_v2", "custom"]


# =============================================================================
# AIRFRAME TEMPLATE MODEL
# =============================================================================


class AirframeTemplate(BaseModel):
    """Airframe configuration template.

    Defines physical and PX4 parameters for a specific drone configuration.
    Used to configure failsafe parameters, flight characteristics, and
    hardware-specific settings.

    Attributes:
        airframe_id: Unique identifier for this airframe template.
        mass_kg: Total takeoff mass in kilograms (includes battery, camera).
        prop_size_in: Propeller diameter in inches.
        px4_airframe_id: PX4 firmware airframe ID (e.g., 4500 for X500).
        battery_cells: Number of battery cells (3S=3, 4S=4, 6S=6).
        max_thrust_n: Maximum thrust in Newtons (for thrust-to-weight ratio).
        param_overlay_path: Optional path to PX4 parameter overlay file.
        param_overlay: Inline parameter overrides (merged with param_overlay_path).
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_default=True,
    )

    airframe_id: str = Field(..., min_length=1, max_length=64, description="Unique airframe identifier")
    mass_kg: float = Field(..., gt=0.0, le=50.0, description="Total takeoff mass in kg")
    prop_size_in: float = Field(..., gt=0.0, le=30.0, description="Propeller diameter in inches")
    px4_airframe_id: Optional[int] = Field(
        default=None,
        ge=1,
        le=99999,
        description="PX4 firmware airframe ID",
    )
    battery_cells: int = Field(default=4, ge=1, le=12, description="Number of battery cells")
    max_thrust_n: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=500.0,
        description="Maximum thrust in Newtons",
    )
    param_overlay_path: Optional[str] = Field(
        default=None,
        description="Path to PX4 parameter overlay file",
    )
    param_overlay: Dict[str, Union[int, float]] = Field(
        default_factory=dict,
        description="Inline parameter overrides",
    )

    @field_validator("param_overlay_path", mode="before")
    @classmethod
    def validate_param_overlay_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate param_overlay_path exists if specified."""
        if v is None:
            return None
        path = Path(v)
        if not path.is_absolute():
            # Allow relative paths - resolution happens at load time
            return v
        if not path.exists():
            warnings.warn(
                f"Parameter overlay file not found: {v}",
                UserWarning,
                stacklevel=2,
            )
        return v

    @model_validator(mode="after")
    def validate_thrust_to_weight(self) -> "AirframeTemplate":
        """Validate thrust-to-weight ratio is reasonable."""
        if self.max_thrust_n is not None and self.mass_kg > 0:
            # Thrust-to-weight ratio should be > 1.5 for safe flight
            # and < 10 for reasonable power consumption
            twr = self.max_thrust_n / (self.mass_kg * 9.81)
            if twr < 1.5:
                warnings.warn(
                    f"Low thrust-to-weight ratio: {twr:.2f} (recommend > 1.5)",
                    UserWarning,
                    stacklevel=2,
                )
            elif twr > 10:
                warnings.warn(
                    f"Very high thrust-to-weight ratio: {twr:.2f} (may cause instability)",
                    UserWarning,
                    stacklevel=2,
                )
        return self


# =============================================================================
# PREDEFINED AIRFRAME TEMPLATES
# =============================================================================

# Mark4 7" Cinematic Drone
# - 7" props for smooth, efficient flight
# - Pixhawk 6C Mini for reliable flight control
# - Raspberry Pi 4 for onboard compute
# - Pi Camera 3 Wide for wide-angle filming
MARK4_7IN_TEMPLATE = AirframeTemplate(
    airframe_id="mark4_7in",
    mass_kg=1.2,
    prop_size_in=7.0,
    px4_airframe_id=None,  # Custom airframe, requires parameter setup
    battery_cells=4,  # 4S LiPo
    max_thrust_n=30.0,  # ~2.5:1 thrust-to-weight
    param_overlay_path=None,
    param_overlay={
        "COM_OBL_RC_ACT": 2,  # RTL on offboard loss
        "COM_OF_LOSS_T": 0.5,  # 500ms timeout
    },
)

# PX4 X500 v2 Development Frame
# - Standard development frame for SITL testing
# - Well-characterized in PX4 documentation
# - Default for simulation workflows
X500_V2_TEMPLATE = AirframeTemplate(
    airframe_id="x500_v2",
    mass_kg=1.5,
    prop_size_in=10.0,
    px4_airframe_id=4500,  # PX4 standard X500 airframe ID
    battery_cells=4,  # 4S LiPo
    max_thrust_n=35.0,  # ~2.4:1 thrust-to-weight
    param_overlay_path=None,
    param_overlay={
        "COM_OBL_RC_ACT": 2,  # RTL on offboard loss
        "COM_OF_LOSS_T": 0.5,  # 500ms timeout
    },
)

# Template registry for lookup by ID
AIRFRAME_TEMPLATES: Dict[str, AirframeTemplate] = {
    "mark4_7in": MARK4_7IN_TEMPLATE,
    "x500_v2": X500_V2_TEMPLATE,
}


# =============================================================================
# RUNTIME PROFILE MODEL
# =============================================================================


class RuntimeProfile(BaseModel):
    """Configuration seam between simulated and physical drone runtimes.

    Pydantic v2 model with layered configuration loading and validation.

    Layered Load Order (increasing precedence):
        1. BASE DEFAULTS (model field defaults)
        2. FILE CONFIG (YAML/JSON from profile_path)
        3. ENV OVERRIDES (AVATAR_* environment variables)
        4. SECRETS (AVATAR_SECRET_* environment variables)

    Attributes:
        name: Profile name (e.g., "sitl", "hardware").
        system_address: MAVSDK connection address (UDP or serial).
        camera_backend: Camera backend implementation ("mock_camera", "rtsp_camera", etc.).
        detector_backend: Object detector implementation ("mock_detector", "yolo_detector", etc.).
        requires_px4_parameter_check: Whether to verify PX4 safety parameters before flight.
        com_obl_rc_act: Offboard loss failsafe action (0=disabled, 1=land, 2=RTL, 3=hold).
        airframe: Airframe template ID or configuration.
        param_overlay: Additional PX4 parameter overrides.
        geofence_max_hor_dist_m: Maximum horizontal distance from home in meters.
        geofence_max_ver_dist_m: Maximum vertical distance from home in meters.
        min_battery_percent: Minimum battery percentage to allow arming.
        rtl_battery_percent: Battery percentage that triggers RTL.
        config_path: Path to configuration file (if loaded from file).
        env_overrides: Environment variables that were applied.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_default=True,
        # Allow frozen-like behavior for safety-critical immutability
        frozen=False,  # Pydantic v2 doesn't support frozen=True well with validators
    )

    # Core configuration
    name: str = Field(..., min_length=1, max_length=64, description="Profile name")
    system_address: str = Field(
        ...,
        min_length=1,
        description="MAVSDK connection address (UDP or serial)",
    )

    # Vision configuration
    camera_backend: str = Field(
        default="mock_camera",
        min_length=1,
        description="Camera backend implementation",
    )
    detector_backend: str = Field(
        default="mock_detector",
        min_length=1,
        description="Object detector implementation",
    )

    # Safety configuration
    requires_px4_parameter_check: bool = Field(
        default=True,
        description="Verify PX4 safety parameters before flight",
    )
    com_obl_rc_act: ComOblRcAct = Field(
        default=2,
        description="Offboard loss failsafe action (0=disabled, 1=land, 2=RTL, 3=hold)",
    )

    # Airframe configuration
    airframe: Union[str, AirframeTemplate] = Field(
        default="x500_v2",
        description="Airframe template ID or configuration",
    )
    param_overlay: Dict[str, Union[int, float]] = Field(
        default_factory=dict,
        description="Additional PX4 parameter overrides",
    )

    # Geofence configuration
    geofence_max_hor_dist_m: float = Field(
        default=500.0,
        gt=0.0,
        le=10000.0,
        description="Maximum horizontal distance from home in meters",
    )
    geofence_max_ver_dist_m: float = Field(
        default=120.0,
        gt=0.0,
        le=5000.0,
        description="Maximum vertical distance from home in meters",
    )

    # Battery configuration
    min_battery_percent: float = Field(
        default=40.0,
        ge=5.0,
        le=95.0,
        description="Minimum battery percentage to allow arming",
    )
    rtl_battery_percent: float = Field(
        default=25.0,
        ge=5.0,
        le=50.0,
        description="Battery percentage that triggers RTL",
    )

    # Configuration metadata
    config_path: Optional[str] = Field(
        default=None,
        description="Path to configuration file (if loaded from file)",
    )
    env_overrides: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables that were applied",
    )

    @field_validator("system_address", mode="before")
    @classmethod
    def validate_system_address(cls, v: str) -> str:
        """Validate system address format."""
        if not v:
            raise ValueError("system_address cannot be empty")
        valid_prefixes = ("udp://", "serial://", "tcp://")
        if not v.startswith(valid_prefixes):
            raise ValueError(
                f"system_address must start with one of: {valid_prefixes}, got: {v}"
            )
        return v

    @field_validator("airframe", mode="before")
    @classmethod
    def validate_airframe(cls, v: Union[str, Dict[str, Any]]) -> Union[str, AirframeTemplate]:
        """Validate and resolve airframe template."""
        if isinstance(v, str):
            # Check if it's a known template ID
            if v in AIRFRAME_TEMPLATES:
                return v
            # Unknown template ID - will be treated as custom
            warnings.warn(
                f"Unknown airframe template: {v}. Treating as custom.",
                UserWarning,
                stacklevel=2,
            )
            return v
        elif isinstance(v, dict):
            # Inline airframe configuration
            return AirframeTemplate.model_validate(v)
        elif isinstance(v, AirframeTemplate):
            return v
        else:
            raise ValueError(f"Invalid airframe type: {type(v)}")

    @model_validator(mode="after")
    def validate_battery_thresholds(self) -> "RuntimeProfile":
        """Validate battery threshold ordering."""
        if self.rtl_battery_percent >= self.min_battery_percent:
            raise ValueError(
                f"rtl_battery_percent ({self.rtl_battery_percent}) must be less than "
                f"min_battery_percent ({self.min_battery_percent})"
            )
        return self

    def get_airframe_template(self) -> AirframeTemplate:
        """Get the resolved AirframeTemplate for this profile.

        Returns:
            AirframeTemplate instance (either from registry or inline config).

        Raises:
            ValueError: If airframe is a string but not found in registry.
        """
        if isinstance(self.airframe, AirframeTemplate):
            return self.airframe

        # Must be a string ID
        if self.airframe in AIRFRAME_TEMPLATES:
            return AIRFRAME_TEMPLATES[self.airframe]

        raise ValueError(
            f"Unknown airframe template: {self.airframe}. "
            f"Known templates: {list(AIRFRAME_TEMPLATES.keys())}"
        )

    def get_merged_param_overlay(self) -> Dict[str, Union[int, float]]:
        """Get merged parameter overlay from airframe and profile.

        Merges parameters in order (later overrides earlier):
        1. Airframe param_overlay
        2. Profile param_overlay

        Returns:
            Dictionary of merged PX4 parameter overrides.
        """
        result: Dict[str, Union[int, float]] = {}

        # Start with airframe defaults
        try:
            airframe = self.get_airframe_template()
            result.update(airframe.param_overlay)
        except ValueError:
            pass  # Custom airframe without template

        # Apply profile-specific overrides
        result.update(self.param_overlay)

        # Apply com_obl_rc_act to param overlay
        result["COM_OBL_RC_ACT"] = self.com_obl_rc_act

        return result

    def model_dump_frozen(self) -> Dict[str, Any]:
        """Dump model as immutable dict (for safety-critical contexts).

        Returns a copy of the model dict to prevent accidental mutation.
        """
        return dict(self.model_dump())


# =============================================================================
# PREDEFINED PROFILES
# =============================================================================

# SITL Profile - Default for PX4 SITL simulation
SITL_PROFILE = RuntimeProfile(
    name="sitl",
    system_address="udp://:14540",
    camera_backend="mock_camera",
    detector_backend="mock_detector",
    requires_px4_parameter_check=False,  # SITL uses safe defaults
    com_obl_rc_act=2,  # RTL on offboard loss
    airframe="x500_v2",
    geofence_max_hor_dist_m=500.0,
    geofence_max_ver_dist_m=120.0,
    min_battery_percent=40.0,
    rtl_battery_percent=25.0,
)

# Hardware Profile - Default for physical drone
HARDWARE_PROFILE = RuntimeProfile(
    name="hardware",
    system_address="serial:///dev/ttyACM0:921600",
    camera_backend="rtsp_camera",
    detector_backend="yolo_detector",
    requires_px4_parameter_check=True,  # Required for safety
    com_obl_rc_act=2,  # RTL on offboard loss (safest for hardware)
    airframe="mark4_7in",
    geofence_max_hor_dist_m=500.0,
    geofence_max_ver_dist_m=120.0,
    min_battery_percent=40.0,
    rtl_battery_percent=25.0,
)


# =============================================================================
# LAYERED CONFIGURATION LOADER
# =============================================================================

# Environment variable prefix for profile settings
ENV_PREFIX = "AVATAR_"
ENV_SECRET_PREFIX = "AVATAR_SECRET_"

# Mapping of profile fields to environment variable names
ENV_FIELD_MAP: Dict[str, str] = {
    "name": "AVATAR_PROFILE_NAME",
    "system_address": "AVATAR_SYSTEM_ADDRESS",
    "camera_backend": "AVATAR_CAMERA_BACKEND",
    "detector_backend": "AVATAR_DETECTOR_BACKEND",
    "requires_px4_parameter_check": "AVATAR_REQUIRES_PX4_CHECK",
    "com_obl_rc_act": "AVATAR_COM_OBL_RC_ACT",
    "airframe": "AVATAR_AIRFRAME",
    "geofence_max_hor_dist_m": "AVATAR_GEOFENCE_MAX_HOR_DIST_M",
    "geofence_max_ver_dist_m": "AVATAR_GEOFENCE_MAX_VER_DIST_M",
    "min_battery_percent": "AVATAR_MIN_BATTERY_PERCENT",
    "rtl_battery_percent": "AVATAR_RTL_BATTERY_PERCENT",
}


def _load_file_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file.

    Args:
        config_path: Path to configuration file.

    Returns:
        Dictionary of configuration values.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file format not supported.
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            import yaml

            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            raise ImportError(
                "PyYAML is required to load YAML configuration files. "
                "Install with: pip install pyyaml"
            )
    elif suffix == ".json":
        with open(path, "r") as f:
            return json.load(f)
    else:
        raise ValueError(
            f"Unsupported configuration file format: {suffix}. "
            "Supported formats: .yaml, .yml, .json"
        )


def _get_env_overrides() -> Dict[str, Any]:
    """Extract configuration overrides from environment variables.

    Environment variable naming:
        AVATAR_<FIELD_NAME> - Standard overrides
        AVATAR_SECRET_<FIELD_NAME> - Secret overrides (higher precedence)

    Returns:
        Dictionary of configuration overrides from environment.
    """
    overrides: Dict[str, Any] = {}

    for field_name, env_var in ENV_FIELD_MAP.items():
        # Check standard env var
        if env_var in os.environ:
            value = os.environ[env_var]

            # Type coercion based on field type
            if field_name in ("requires_px4_parameter_check",):
                value = value.lower() in ("true", "1", "yes")
            elif field_name in ("com_obl_rc_act",):
                value = int(value)
            elif field_name in (
                "geofence_max_hor_dist_m",
                "geofence_max_ver_dist_m",
                "min_battery_percent",
                "rtl_battery_percent",
            ):
                value = float(value)

            overrides[field_name] = value

    # Check secret env vars (higher precedence)
    for field_name in ENV_FIELD_MAP.keys():
        secret_var = f"{ENV_SECRET_PREFIX}{field_name.upper()}"
        if secret_var in os.environ:
            value = os.environ[secret_var]

            # Type coercion
            if field_name in ("requires_px4_parameter_check",):
                value = value.lower() in ("true", "1", "yes")
            elif field_name in ("com_obl_rc_act",):
                value = int(value)
            elif field_name in (
                "geofence_max_hor_dist_m",
                "geofence_max_ver_dist_m",
                "min_battery_percent",
                "rtl_battery_percent",
            ):
                value = float(value)

            overrides[field_name] = value

    return overrides


def _get_env_metadata() -> Dict[str, str]:
    """Get metadata about which env vars were applied.

    Returns:
        Dictionary mapping field names to their source env var.
    """
    metadata: Dict[str, str] = {}

    for field_name, env_var in ENV_FIELD_MAP.items():
        if env_var in os.environ:
            metadata[field_name] = env_var

        secret_var = f"{ENV_SECRET_PREFIX}{field_name.upper()}"
        if secret_var in os.environ:
            metadata[field_name] = secret_var

    return metadata


def load_profile(
    name: str,
    config_path: Optional[Union[str, Path]] = None,
    env_prefix: str = ENV_PREFIX,
    **overrides: Any,
) -> RuntimeProfile:
    """Load a runtime profile with layered configuration.

    Layered Load Order (increasing precedence):
        1. BASE DEFAULTS (from RuntimeProfile field defaults)
        2. FILE CONFIG (from config_path if provided)
        3. ENV OVERRIDES (from AVATAR_* environment variables)
        4. SECRETS (from AVATAR_SECRET_* environment variables)
        5. CALLER OVERRIDES (from **overrides kwargs)

    Args:
        name: Profile name (e.g., "sitl", "hardware").
        config_path: Optional path to YAML/JSON configuration file.
        env_prefix: Prefix for environment variables (default: "AVATAR_").
        **overrides: Additional overrides passed by caller.

    Returns:
        RuntimeProfile instance with merged configuration.

    Example:
        >>> # Load with defaults
        >>> profile = load_profile("sitl")

        >>> # Load from file with env overrides
        >>> profile = load_profile("sitl", config_path="config/sitl.yaml")

        >>> # Load with caller overrides (highest precedence)
        >>> profile = load_profile(
        ...     "custom",
        ...     system_address="udp://:14541",
        ...     com_obl_rc_act=1,
        ... )
    """
    # Start with base defaults based on known profiles
    base_config: Dict[str, Any] = {"name": name}

    # Apply known profile defaults
    if name == "sitl":
        base_config.update(SITL_PROFILE.model_dump())
    elif name == "hardware":
        base_config.update(HARDWARE_PROFILE.model_dump())

    # Layer 2: File config
    file_config: Dict[str, Any] = {}
    resolved_config_path = None

    if config_path is not None:
        file_config = _load_file_config(config_path)
        resolved_config_path = str(config_path)
    else:
        # Try to find default config file
        default_paths = [
            Path("config") / f"{name}.yaml",
            Path("config") / f"{name}.yml",
            Path("config") / f"{name}.json",
            Path(f"{name}.yaml"),
            Path(f"{name}.yml"),
            Path(f"{name}.json"),
        ]

        for default_path in default_paths:
            if default_path.exists():
                file_config = _load_file_config(default_path)
                resolved_config_path = str(default_path)
                break

    # Layer 3 & 4: Environment overrides
    env_config = _get_env_overrides()
    env_metadata = _get_env_metadata()

    # Merge all layers
    merged_config: Dict[str, Any] = {}
    merged_config.update(base_config)  # Layer 1
    merged_config.update(file_config)  # Layer 2
    merged_config.update(env_config)  # Layer 3 & 4
    merged_config.update(overrides)  # Layer 5

    # Add metadata
    merged_config["config_path"] = resolved_config_path
    merged_config["env_overrides"] = env_metadata

    # Validate and create profile
    return RuntimeProfile.model_validate(merged_config)


# =============================================================================
# PX4 PARAMETER VERIFICATION INTEGRATION
# =============================================================================


async def verify_profile_parameters(
    profile: RuntimeProfile,
    drone: Any,
) -> list[Any]:
    """Verify PX4 safety parameters for a runtime profile.

    This is the preflight gate that blocks startup if safety parameters
    don't match expected values. It checks:
    1. Default CRITICAL_PARAMETERS (safety-critical defaults)
    2. Airframe-specific param_overlay (hardware-specific settings)

    Args:
        profile: RuntimeProfile to verify.
        drone: MAVSDK System instance (connected to PX4).

    Returns:
        List of ParameterStatus from verification.

    Raises:
        ImportError: If PX4ParameterManager is not available.
        SafetyError: If parameters don't match expected values.

    Example:
        >>> from avatar.config.profiles import load_profile, verify_profile_parameters
        >>> profile = load_profile("hardware")
        >>> if profile.requires_px4_parameter_check:
        ...     results = await verify_profile_parameters(profile, drone)
        ...     if not all(r.is_valid for r in results):
        ...         raise SafetyError("Parameter verification failed")
    """
    # Import here to avoid circular dependency
    from avatar.mav.px4_parameters import (
        CRITICAL_PARAMETERS,
        PX4ParameterManager,
        SafetyError,
    )

    if not profile.requires_px4_parameter_check:
        logger.info(f"Profile '{profile.name}' does not require PX4 parameter check")
        return []

    # Get merged parameter overlay (airframe + profile settings)
    param_overlay = profile.get_merged_param_overlay()

    logger.info(
        f"Verifying PX4 parameters for profile '{profile.name}' "
        f"with {len(param_overlay)} overlay params"
    )

    # Create parameter manager
    param_manager = PX4ParameterManager(drone)

    # Run default safety parameter verification first
    results = list(await param_manager.verify_safety_parameters())

    # Verify airframe-specific parameters from overlay
    # These override defaults, so we check them separately
    for param_name, expected_value in param_overlay.items():
        # Skip if already checked in CRITICAL_PARAMETERS
        if param_name in CRITICAL_PARAMETERS:
            # Update the expected value from overlay
            actual = await param_manager.get_parameter(param_name)
            status = param_manager.check_parameter(param_name, expected_value, actual)
            # Replace the existing result if found
            for i, r in enumerate(results):
                if r.name == param_name:
                    results[i] = status
                    break
            else:
                # Not found, add new result
                results.append(status)
        else:
            # Not in CRITICAL_PARAMETERS - check separately
            actual = await param_manager.get_parameter(param_name)
            status = param_manager.check_parameter(param_name, expected_value, actual)
            results.append(status)

    # Check for mismatches
    invalid_count = sum(1 for r in results if not r.is_valid)

    if invalid_count > 0:
        invalid_names = [r.name for r in results if not r.is_valid]
        logger.error(
            f"Parameter verification failed: {invalid_count} mismatches found: {invalid_names}"
        )
        raise SafetyError(
            f"Safety parameter verification failed for profile '{profile.name}'. "
            f"{invalid_count} parameters have incorrect values: {invalid_names}"
        )

    logger.info(f"Parameter verification passed for profile '{profile.name}'")
    return results


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Backward compatibility for frozen dataclass behavior
def _freeze_profile(profile: RuntimeProfile) -> RuntimeProfile:
    """Create a frozen-like profile for backward compatibility.

    Note: Pydantic v2 doesn't support frozen models with validators well.
    This is a workaround to maintain immutability semantics.

    Args:
        profile: RuntimeProfile to freeze.

    Returns:
        Same profile (validation already happened at creation).
    """
    return profile


# Export for backward compatibility
__all__ = [
    # Models
    "RuntimeProfile",
    "AirframeTemplate",
    "ComOblRcAct",
    "AirframeId",
    # Predefined profiles
    "SITL_PROFILE",
    "HARDWARE_PROFILE",
    # Predefined templates
    "MARK4_7IN_TEMPLATE",
    "X500_V2_TEMPLATE",
    "AIRFRAME_TEMPLATES",
    # Loader functions
    "load_profile",
    "verify_profile_parameters",
    # Environment configuration
    "ENV_PREFIX",
    "ENV_SECRET_PREFIX",
    "ENV_FIELD_MAP",
]
