"""Google Maps provider for enhanced mapping capabilities.

Provides Places, Static Maps, Street View, Roads, and Geocoding APIs.
REQUIRES: GOGL_MAPS_API_KEY environment variable.

Guardrails:
- Silent no-op when API key not set
- Daily budget enforcement (GMAPS_DAILY_BUDGET env)
- Per-endpoint TTL caching
- Rate limiting

Usage:
    from avatar.mission_intel.providers.gmaps import GoogleMapsProvider

    # Will silently no-op if no API key
    gmaps = GoogleMapsProvider()
    if gmaps.is_available():
        places = await gmaps.search_places("coffee", bbox)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from avatar.mission_intel.config import get_config
from avatar.mission_intel.geo import BBox, Point
from avatar.mission_intel.providers.base import (
    LandUseResult,
    MappingProvider,
    ObstacleResult,
    PlaceResult,
    PlaceType,
)
from avatar.mission_intel.providers.osm import RateLimiter

logger = logging.getLogger(__name__)


class GoogleMapsBudgetExceeded(Exception):
    """Raised when daily Google Maps API budget is exceeded."""

    pass


@dataclass
class BudgetTracker:
    """Track daily API request budget."""

    daily_budget: int
    cache_dir: Path

    def __post_init__(self) -> None:
        self._budget_file = self.cache_dir / "gmaps_budget.json"
        self._load_budget()

    def _load_budget(self) -> None:
        """Load budget state from disk."""
        try:
            if self._budget_file.exists():
                with open(self._budget_file, "r") as f:
                    data = json.load(f)
                    # Reset if day changed
                    if data.get("date") == time.strftime("%Y-%m-%d"):
                        self._current_count = data.get("count", 0)
                    else:
                        self._current_count = 0
            else:
                self._current_count = 0
        except Exception:
            self._current_count = 0

    def _save_budget(self) -> None:
        """Save budget state to disk."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self._budget_file, "w") as f:
                json.dump(
                    {
                        "date": time.strftime("%Y-%m-%d"),
                        "count": self._current_count,
                    },
                    f,
                )
        except Exception as e:
            logger.warning(f"Failed to save budget: {e}")

    def can_request(self) -> bool:
        """Check if a request can be made within budget."""
        return self._current_count < self.daily_budget

    def record_request(self) -> None:
        """Record a request."""
        self._current_count += 1
        self._save_budget()

    def remaining(self) -> int:
        """Get remaining budget."""
        return max(0, self.daily_budget - self._current_count)


class EndpointCache:
    """Per-endpoint TTL cache for Google Maps responses."""

    def __init__(self, cache_dir: Path, endpoint_ttls: Dict[str, int]):
        """Initialize endpoint cache.

        Args:
            cache_dir: Cache directory.
            endpoint_ttls: Dict mapping endpoint names to TTL in seconds.
        """
        self._cache_dir = cache_dir
        self._endpoint_ttls = endpoint_ttls
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, endpoint: str, key: str) -> Path:
        """Get cache file path."""
        return self._cache_dir / endpoint / f"{key}.json"

    def get(self, endpoint: str, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response.

        Args:
            endpoint: API endpoint name.
            key: Cache key.

        Returns:
            Cached response or None.
        """
        path = self._cache_path(endpoint, key)
        if not path.exists():
            return None

        ttl = self._endpoint_ttls.get(endpoint, 86400)
        age = time.time() - path.stat().st_mtime
        if age > ttl:
            return None

        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, endpoint: str, key: str, response: Dict[str, Any]) -> None:
        """Cache a response.

        Args:
            endpoint: API endpoint name.
            key: Cache key.
            response: Response to cache.
        """
        path = self._cache_path(endpoint, key)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w") as f:
                json.dump(response, f)
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")


class GoogleMapsProvider(MappingProvider):
    """Google Maps API provider.

    Provides:
    - Places API: Search for businesses and points of interest
    - Static Maps: Generate map images
    - Street View: Get street-level imagery metadata
    - Roads API: Snap to roads, speed limits
    - Geocoding API: Address to coordinates conversion

    Guardrails:
    - Silent no-op when API key not set
    - Daily budget enforcement
    - Per-endpoint TTL caching
    - Rate limiting
    """

    PLACES_API = "https://maps.googleapis.com/maps/api/place"
    GEOCODING_API = "https://maps.googleapis.com/maps/api/geocode"
    STATIC_MAP_API = "https://maps.googleapis.com/maps/api/staticmap"
    STREET_VIEW_API = "https://maps.googleapis.com/maps/api/streetview"
    ROADS_API = "https://roads.googleapis.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        daily_budget: int = 500,
        cache_dir: Optional[Path] = None,
    ):
        """Initialize Google Maps provider.

        Args:
            api_key: Google Maps API key. Defaults to env var.
            daily_budget: Daily request budget.
            cache_dir: Cache directory.
        """
        config = get_config()
        self._api_key = api_key or config.gmaps_api_key
        self._daily_budget = daily_budget

        if self._api_key:
            self._budget_tracker = BudgetTracker(
                daily_budget=daily_budget,
                cache_dir=cache_dir or config.gmaps_cache_dir,
            )
            self._cache = EndpointCache(
                cache_dir=cache_dir or config.gmaps_cache_dir,
                endpoint_ttls={
                    "places": config.gmaps_endpoints.places_ttl_s,
                    "static_maps": config.gmaps_endpoints.static_maps_ttl_s,
                    "street_view": config.gmaps_endpoints.street_view_ttl_s,
                    "roads": config.gmaps_endpoints.roads_ttl_s,
                    "geocoding": config.gmaps_endpoints.geocoding_ttl_s,
                },
            )
            self._rate_limiter = RateLimiter(config.rate_limits.gmaps_requests_per_second)
        else:
            self._budget_tracker = None  # type: ignore
            self._cache = None  # type: ignore
            self._rate_limiter = None  # type: ignore

    def is_available(self) -> bool:
        """Check if Google Maps is available.

        Returns:
            True if API key is set and budget remaining.
        """
        if not self._api_key:
            return False
        if self._budget_tracker and not self._budget_tracker.can_request():
            return False
        return True

    def _check_budget(self) -> None:
        """Check budget and raise if exceeded."""
        if self._budget_tracker and not self._budget_tracker.can_request():
            raise GoogleMapsBudgetExceeded(
                f"Daily budget of {self._daily_budget} requests exceeded"
            )

    def _cache_key(self, *args: Any) -> str:
        """Generate cache key from arguments."""
        key_str = "|".join(str(a) for a in args)
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    async def _make_request(
        self,
        endpoint: str,
        url: str,
        params: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Make an API request with caching and budget tracking.

        Args:
            endpoint: Endpoint name for caching.
            url: API URL.
            params: Request parameters.

        Returns:
            Response data or None.
        """
        if not self.is_available():
            return None

        # Check cache
        cache_key = self._cache_key(url, params)
        if self._cache:
            cached = self._cache.get(endpoint, cache_key)
            if cached:
                logger.debug(f"Google Maps cache hit for {endpoint}")
                return cached

        # Check budget
        self._check_budget()

        # Rate limit
        if self._rate_limiter:
            await self._rate_limiter.wait()

        # Make request
        params["key"] = self._api_key

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Track budget
                        if self._budget_tracker:
                            self._budget_tracker.record_request()

                        # Cache response
                        if self._cache:
                            self._cache.set(endpoint, cache_key, data)

                        return data
                    else:
                        logger.warning(f"Google Maps API error: {resp.status}")
        except Exception as e:
            logger.warning(f"Google Maps request error: {e}")

        return None

    async def search_places(
        self,
        query: str,
        bbox: Optional[BBox] = None,
        limit: int = 10,
    ) -> List[PlaceResult]:
        """Search for places using Google Places API.

        Args:
            query: Search query.
            bbox: Optional bounding box (uses center as location bias).
            limit: Maximum results.

        Returns:
            List of matching places.
        """
        if not self.is_available():
            return []

        params: Dict[str, Any] = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,geometry,formatted_address,types",
        }

        if bbox:
            center = bbox.center()
            params["locationbias"] = f"point:{center.lat_deg},{center.lon_deg}"

        data = await self._make_request(
            "places",
            f"{self.PLACES_API}/findplacefromtext/json",
            params,
        )

        if not data:
            return []

        results: List[PlaceResult] = []
        for candidate in data.get("candidates", [])[:limit]:
            location = candidate.get("geometry", {}).get("location", {})
            name = candidate.get("name", "Unknown")
            types = candidate.get("types", [])

            # Map Google types to our PlaceType
            place_type = PlaceType.UNKNOWN
            for t in types:
                if t == "park":
                    place_type = PlaceType.PARK
                    break
                elif t == "school":
                    place_type = PlaceType.SCHOOL
                    break
                elif t == "hospital":
                    place_type = PlaceType.HOSPITAL
                    break
                elif t in ("airport", "sublocality_level_1"):
                    place_type = PlaceType.AIRPORT
                    break

            if location.get("lat") and location.get("lng"):
                results.append(
                    PlaceResult(
                        name=name,
                        place_type=place_type,
                        location=Point(
                            lat_deg=location["lat"],
                            lon_deg=location["lng"],
                        ),
                        importance=0.5,
                        address=candidate.get("formatted_address"),
                        osm_id=None,  # Google Place ID is different
                    )
                )

        return results

    async def lookup_place(self, place_id: str) -> Optional[PlaceResult]:
        """Look up a specific place by Google Place ID.

        Args:
            place_id: Google Place ID.

        Returns:
            Place details or None.
        """
        if not self.is_available():
            return None

        data = await self._make_request(
            "places",
            f"{self.PLACES_API}/details/json",
            {
                "place_id": place_id,
                "fields": "name,geometry,formatted_address,types",
            },
        )

        if not data or not data.get("result"):
            return None

        result = data["result"]
        location = result.get("geometry", {}).get("location", {})

        if not location.get("lat") or not location.get("lng"):
            return None

        return PlaceResult(
            name=result.get("name", "Unknown"),
            place_type=PlaceType.UNKNOWN,  # Would need to parse types
            location=Point(lat_deg=location["lat"], lon_deg=location["lng"]),
            importance=0.5,
            address=result.get("formatted_address"),
        )

    async def get_obstacles_in_area(self, bbox: BBox) -> List[ObstacleResult]:
        """Get obstacles in area.

        Note: Google Maps doesn't provide obstacle data.
        Use OSM provider for this.

        Args:
            bbox: Bounding box.

        Returns:
            Empty list (not supported by Google Maps).
        """
        # Google Maps doesn't provide obstacle data
        # This should use OSM provider instead
        return []

    async def get_land_use(self, bbox: BBox) -> List[LandUseResult]:
        """Get land use classification.

        Note: Google Maps doesn't provide land use data.
        Use OSM provider for this.

        Args:
            bbox: Bounding box.

        Returns:
            Empty list (not supported by Google Maps).
        """
        # Google Maps doesn't provide land use data
        return []

    async def geocode(self, address: str) -> Optional[Point]:
        """Geocode an address.

        Args:
            address: Address string.

        Returns:
            Coordinates or None.
        """
        if not self.is_available():
            return None

        data = await self._make_request(
            "geocoding",
            f"{self.GEOCODING_API}/json",
            {"address": address},
        )

        if not data or not data.get("results"):
            return None

        location = data["results"][0].get("geometry", {}).get("location", {})
        if location.get("lat") and location.get("lng"):
            return Point(lat_deg=location["lat"], lon_deg=location["lng"])

        return None

    async def reverse_geocode(self, point: Point) -> Optional[str]:
        """Reverse geocode coordinates.

        Args:
            point: Geographic coordinates.

        Returns:
            Address string or None.
        """
        if not self.is_available():
            return None

        data = await self._make_request(
            "geocoding",
            f"{self.GEOCODING_API}/json",
            {
                "latlng": f"{point.lat_deg},{point.lon_deg}",
            },
        )

        if not data or not data.get("results"):
            return None

        return data["results"][0].get("formatted_address")

    async def get_static_map_url(
        self,
        center: Point,
        zoom: int = 15,
        size: str = "400x400",
        markers: Optional[List[Point]] = None,
    ) -> Optional[str]:
        """Get URL for a static map image.

        Args:
            center: Center point.
            zoom: Zoom level (1-20).
            size: Image size (e.g., "400x400").
            markers: Optional marker points.

        Returns:
            Static map URL or None.
        """
        if not self._api_key:
            return None

        params = {
            "center": f"{center.lat_deg},{center.lon_deg}",
            "zoom": zoom,
            "size": size,
            "key": self._api_key,
        }

        if markers:
            for i, m in enumerate(markers):
                params[f"markers"] = f"{m.lat_deg},{m.lon_deg}"

        # Build URL
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.STATIC_MAP_API}?{query}"

    async def get_street_view_metadata(
        self,
        point: Point,
    ) -> Optional[Dict[str, Any]]:
        """Get Street View metadata for a location.

        Args:
            point: Geographic coordinates.

        Returns:
            Metadata dict or None if no imagery available.
        """
        if not self.is_available():
            return None

        data = await self._make_request(
            "street_view",
            f"{self.STREET_VIEW_API}/metadata",
            {
                "location": f"{point.lat_deg},{point.lon_deg}",
            },
        )

        if data and data.get("status") == "OK":
            return data

        return None

    async def snap_to_roads(
        self,
        points: List[Point],
    ) -> List[Point]:
        """Snap points to nearest road.

        Args:
            points: List of geographic points.

        Returns:
            List of snapped points.
        """
        if not self.is_available():
            return points

        # Build path string
        path = "|".join(f"{p.lat_deg},{p.lon_deg}" for p in points)

        data = await self._make_request(
            "roads",
            f"{self.ROADS_API}/snapToRoads",
            {"path": path},
        )

        if not data or not data.get("snappedPoints"):
            return points

        return [
            Point(
                lat_deg=sp["location"]["latitude"],
                lon_deg=sp["location"]["longitude"],
            )
            for sp in data["snappedPoints"]
        ]


__all__ = [
    "GoogleMapsProvider",
    "GoogleMapsBudgetExceeded",
    "BudgetTracker",
    "EndpointCache",
]
