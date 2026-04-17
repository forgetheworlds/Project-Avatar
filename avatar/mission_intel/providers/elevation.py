"""Elevation providers: SRTM (offline) and Open-Elevation (online fallback).

SRTM Provider:
- Uses local HGT tile cache (offline-capable)
- 1-arcsecond (~30m) or 3-arcsecond (~90m) resolution
- Covers land between 60N and 56S latitude

Open-Elevation Provider:
- Free API for SRTM data
- Fallback when local tiles unavailable
- Rate-limited to 1 request per second

Usage:
    from avatar.mission_intel.providers.elevation import SRTMProvider

    # Prefer SRTM (offline)
    srtm = SRTMProvider()
    elevation = await srtm.get_elevation(37.7749, -122.4194)

    # Or use Open-Elevation as fallback
    open_elev = OpenElevationProvider()
    elevation = await open_elev.get_elevation(37.7749, -122.4194)
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from avatar.mission_intel.geo import Point
from avatar.mission_intel.providers.base import ElevationProvider, ElevationResult
from avatar.mission_intel.providers.dem_cache import DEMCache
from avatar.mission_intel.providers.osm import RateLimiter

logger = logging.getLogger(__name__)


class SRTMProvider(ElevationProvider):
    """SRTM elevation data provider using local HGT tiles.

    Primary elevation source - works offline when tiles are cached.
    Resolution: 1-arcsecond (~30m) or 3-arcsecond (~90m).
    Coverage: Land between 60N and 56S latitude.
    """

    def __init__(self, dem_cache: Optional[DEMCache] = None):
        """Initialize SRTM provider.

        Args:
            dem_cache: DEM cache instance. Created if not provided.
        """
        self._cache = dem_cache or DEMCache()

    async def get_elevation(
        self,
        lat_deg: float,
        lon_deg: float,
    ) -> Optional[ElevationResult]:
        """Get elevation for a single point.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Elevation result or None if tile not available.
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        elevation = await loop.run_in_executor(
            None,
            self._cache.get_elevation,
            lat_deg,
            lon_deg,
        )

        if elevation is not None:
            # Determine resolution
            tile = self._cache.get_tile(lat_deg, lon_deg)
            resolution = tile.resolution if tile else 30

            return ElevationResult(
                elevation_m=float(elevation),
                source="SRTM",
                resolution_m=30.0 if resolution == 1 else 90.0,
                is_interpolated=True,  # Bilinear interpolation is used
            )

        return None

    async def get_elevations(
        self,
        points: List[Point],
    ) -> List[Optional[ElevationResult]]:
        """Get elevations for multiple points.

        Args:
            points: List of geographic points.

        Returns:
            List of elevation results (None for missing tiles).
        """
        results: List[Optional[ElevationResult]] = []
        for point in points:
            result = await self.get_elevation(point.lat_deg, point.lon_deg)
            results.append(result)
        return results

    def is_available(self) -> bool:
        """Check if SRTM provider is available.

        Returns:
            True (SRTM provider always available, though tiles may be missing).
        """
        return True

    def has_tile_for(self, lat_deg: float, lon_deg: float) -> bool:
        """Check if a tile exists for coordinates.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            True if tile is cached.
        """
        return self._cache.has_tile(lat_deg, lon_deg)


class OpenElevationProvider(ElevationProvider):
    """Open-Elevation API provider for SRTM data.

    Free API for SRTM elevation data.
    Use as fallback when local tiles are not available.

    API: https://api.open-elevation.com/api/v1/lookup
    Rate limit: ~1 request per second (be nice to public API).
    """

    API_ENDPOINT = "https://api.open-elevation.com/api/v1/lookup"

    def __init__(self, rate_limit: float = 1.0):
        """Initialize Open-Elevation provider.

        Args:
            rate_limit: Requests per second limit.
        """
        self._rate_limiter = RateLimiter(rate_limit)
        self._cache: dict = {}

    async def get_elevation(
        self,
        lat_deg: float,
        lon_deg: float,
    ) -> Optional[ElevationResult]:
        """Get elevation for a single point.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Elevation result or None if API error.
        """
        cache_key = f"{lat_deg:.4f},{lon_deg:.4f}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        await self._rate_limiter.wait()

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.API_ENDPOINT,
                    params={
                        "locations": f"{lat_deg},{lon_deg}",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            elevation = results[0].get("elevation")
                            if elevation is not None:
                                result = ElevationResult(
                                    elevation_m=float(elevation),
                                    source="Open-Elevation",
                                    resolution_m=30.0,  # SRTM 1-arcsecond
                                    is_interpolated=False,
                                )
                                self._cache[cache_key] = result
                                return result
        except Exception as e:
            logger.warning(f"Open-Elevation error: {e}")

        return None

    async def get_elevations(
        self,
        points: List[Point],
    ) -> List[Optional[ElevationResult]]:
        """Get elevations for multiple points in batch.

        Open-Elevation supports batch queries.

        Args:
            points: List of geographic points.

        Returns:
            List of elevation results.
        """
        if not points:
            return []

        # Build batch query
        locations = "|".join(
            f"{p.lat_deg},{p.lon_deg}" for p in points
        )

        await self._rate_limiter.wait()

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.API_ENDPOINT,
                    params={"locations": locations},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        return [
                            ElevationResult(
                                elevation_m=float(r.get("elevation", 0)),
                                source="Open-Elevation",
                                resolution_m=30.0,
                                is_interpolated=False,
                            )
                            if r.get("elevation") is not None
                            else None
                            for r in results
                        ]
        except Exception as e:
            logger.warning(f"Open-Elevation batch error: {e}")

        # Return None for each point on error
        return [None] * len(points)

    def is_available(self) -> bool:
        """Check if Open-Elevation provider is available.

        Returns:
            True (assumes API is available).
        """
        return True


class CompositeElevationProvider(ElevationProvider):
    """Composite provider that tries SRTM first, then Open-Elevation.

    Provides the best of both worlds:
    - Fast offline access via SRTM when tiles available
    - Automatic fallback to Open-Elevation when tiles missing
    """

    def __init__(
        self,
        srtm: Optional[SRTMProvider] = None,
        open_elevation: Optional[OpenElevationProvider] = None,
        prefer_srtm: bool = True,
    ):
        """Initialize composite provider.

        Args:
            srtm: SRTM provider instance.
            open_elevation: Open-Elevation provider instance.
            prefer_srtm: Whether to prefer SRTM over Open-Elevation.
        """
        self._srtm = srtm or SRTMProvider()
        self._open_elevation = open_elevation or OpenElevationProvider()
        self._prefer_srtm = prefer_srtm

    async def get_elevation(
        self,
        lat_deg: float,
        lon_deg: float,
    ) -> Optional[ElevationResult]:
        """Get elevation, preferring SRTM if available.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Elevation result or None.
        """
        if self._prefer_srtm:
            # Try SRTM first
            result = await self._srtm.get_elevation(lat_deg, lon_deg)
            if result is not None:
                return result

            # Fall back to Open-Elevation
            return await self._open_elevation.get_elevation(lat_deg, lon_deg)
        else:
            # Try Open-Elevation first
            result = await self._open_elevation.get_elevation(lat_deg, lon_deg)
            if result is not None:
                return result

            # Fall back to SRTM
            return await self._srtm.get_elevation(lat_deg, lon_deg)

    async def get_elevations(
        self,
        points: List[Point],
    ) -> List[Optional[ElevationResult]]:
        """Get elevations for multiple points.

        Args:
            points: List of geographic points.

        Returns:
            List of elevation results.
        """
        results: List[Optional[ElevationResult]] = []

        for point in points:
            result = await self.get_elevation(point.lat_deg, point.lon_deg)
            results.append(result)

        return results

    def is_available(self) -> bool:
        """Check if either provider is available.

        Returns:
            True (at least one provider is always available).
        """
        return True


__all__ = [
    "SRTMProvider",
    "OpenElevationProvider",
    "CompositeElevationProvider",
]
