"""Configuration for Mission Intelligence Layer.

Manages API keys, cache directories, rate limits, and daily budgets.
Google Maps integration is optional and gracefully degrades when unavailable.

Environment Variables:
    - GOGL_MAPS_API_KEY: Google Maps API key (optional)
    - GMAPS_DAILY_BUDGET: Daily request budget for Google Maps (default: 500)
    - AVATAR_CACHE_DIR: Base cache directory (default: ~/.cache/avatar)

Usage:
    from avatar.mission_intel.config import get_config

    config = get_config()
    if config.gmaps_api_key:
        # Google Maps available
        pass
    else:
        # Fall back to OSM/SRTM only
        pass
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class GMapsEndpoints:
    """Per-endpoint configuration for Google Maps API."""

    places: bool = True
    static_maps: bool = True
    street_view: bool = True
    roads: bool = True
    geocoding: bool = True

    # Per-endpoint TTLs in seconds
    places_ttl_s: int = 86400 * 7  # 7 days
    static_maps_ttl_s: int = 86400 * 30  # 30 days
    street_view_ttl_s: int = 86400 * 30  # 30 days
    roads_ttl_s: int = 86400  # 1 day
    geocoding_ttl_s: int = 86400 * 30  # 30 days


@dataclass(frozen=True)
class RateLimits:
    """Rate limiting configuration."""

    osm_requests_per_second: float = 1.0  # Overpass/Nominatim are public
    gmaps_requests_per_second: float = 10.0
    open_elevation_requests_per_second: float = 1.0


@dataclass
class MissionIntelConfig:
    """Configuration for mission intelligence layer.

    Attributes:
        gmaps_api_key: Google Maps API key (from GOGL_MAPS_API_KEY env).
            If not set, Google Maps features are silently disabled.
        gmaps_daily_budget: Maximum Google Maps requests per day.
        gmaps_endpoints: Per-endpoint configuration.
        cache_dir: Base cache directory for all providers.
        dem_cache_dir: SRTM tile cache directory.
        gmaps_cache_dir: Google Maps response cache directory.
        rate_limits: Rate limiting configuration.
        enable_srtm_offline: Whether to use local SRTM tiles (default: True).
        fallback_to_open_elevation: Whether to fall back to Open-Elevation API.
    """

    gmaps_api_key: Optional[str] = None
    gmaps_daily_budget: int = 500
    gmaps_endpoints: GMapsEndpoints = field(default_factory=GMapsEndpoints)
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "avatar")
    rate_limits: RateLimits = field(default_factory=RateLimits)
    enable_srtm_offline: bool = True
    fallback_to_open_elevation: bool = True

    @property
    def dem_cache_dir(self) -> Path:
        """SRTM tile cache directory."""
        return self.cache_dir / "dem"

    @property
    def gmaps_cache_dir(self) -> Path:
        """Google Maps response cache directory."""
        return self.cache_dir / "gmaps"

    @property
    def osm_cache_dir(self) -> Path:
        """OSM response cache directory."""
        return self.cache_dir / "osm"

    @property
    def gmaps_enabled(self) -> bool:
        """Check if Google Maps is available (API key present)."""
        return bool(self.gmaps_api_key)

    def ensure_cache_dirs(self) -> None:
        """Create cache directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dem_cache_dir.mkdir(parents=True, exist_ok=True)
        if self.gmaps_enabled:
            self.gmaps_cache_dir.mkdir(parents=True, exist_ok=True)
        self.osm_cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_config() -> MissionIntelConfig:
    """Get the singleton configuration instance.

    Configuration is loaded from environment variables:
    - GOGL_MAPS_API_KEY: Google Maps API key
    - GMAPS_DAILY_BUDGET: Daily request budget (default: 500)
    - AVATAR_CACHE_DIR: Base cache directory (default: ~/.cache/avatar)

    Returns:
        MissionIntelConfig: The configuration instance.
    """
    gmaps_api_key = os.environ.get("GOGL_MAPS_API_KEY")

    gmaps_daily_budget = int(os.environ.get("GMAPS_DAILY_BUDGET", "500"))

    cache_dir_str = os.environ.get("AVATAR_CACHE_DIR")
    if cache_dir_str:
        cache_dir = Path(cache_dir_str)
    else:
        cache_dir = Path.home() / ".cache" / "avatar"

    config = MissionIntelConfig(
        gmaps_api_key=gmaps_api_key,
        gmaps_daily_budget=gmaps_daily_budget,
        cache_dir=cache_dir,
    )

    config.ensure_cache_dirs()
    return config


__all__ = [
    "MissionIntelConfig",
    "GMapsEndpoints",
    "RateLimits",
    "get_config",
]
