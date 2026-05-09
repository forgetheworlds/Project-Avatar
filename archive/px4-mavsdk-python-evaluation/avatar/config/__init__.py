"""Configuration helpers for Project Avatar runtime profiles.

Provides Pydantic v2 models for runtime configuration with layered loading:
    1. BASE DEFAULTS (hardcoded in model defaults)
    2. FILE CONFIG (YAML/JSON from profile_path)
    3. ENV OVERRIDES (AVATAR_* environment variables)
    4. SECRETS (AVATAR_SECRET_* environment variables)

Usage:
    >>> from avatar.config import load_profile, SITL_PROFILE
    >>> profile = load_profile("sitl")
    >>> print(profile.system_address)
    udp://:14540
"""

from avatar.config.profiles import (
    AIRFRAME_TEMPLATES,
    HARDWARE_PROFILE,
    MARK4_7IN_TEMPLATE,
    SITL_PROFILE,
    X500_V2_TEMPLATE,
    AirframeTemplate,
    RuntimeProfile,
    load_profile,
    verify_profile_parameters,
)

__all__ = [
    # Predefined profiles
    "SITL_PROFILE",
    "HARDWARE_PROFILE",
    # Airframe templates
    "AIRFRAME_TEMPLATES",
    "MARK4_7IN_TEMPLATE",
    "X500_V2_TEMPLATE",
    "AirframeTemplate",
    # Main profile class
    "RuntimeProfile",
    # Loader functions
    "load_profile",
    "verify_profile_parameters",
]
