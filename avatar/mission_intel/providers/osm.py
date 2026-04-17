"""OpenStreetMap providers via Overpass and Nominatim APIs.

Provides offline-capable mapping data through OSM with disk caching.
Rate-limited to respect OSM's public API guidelines.

APIs Used:
- Overpass API: Query OSM data (places, obstacles, land use)
- Nominatim: Geocoding and reverse geocoding

Rate Limits:
- 1 request per second for public APIs
- Cached responses don't count against rate limit

Usage:
    from avatar.mission_intel.providers.osm import OSMProvider

    osm = OSMProvider()
    places = await osm.search_places("park", bbox)
    obstacles = await osm.get_obstacles_in_area(bbox)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from avatar.mission_intel.config import get_config
from avatar.mission_intel.geo import BBox, Point
from avatar.mission_intel.providers.base import (
    LandUseResult,
    MappingProvider,
    ObstacleResult,
    ObstacleType,
    PlaceResult,
    PlaceType,
)

logger = logging.getLogger(__name__)


# OSM tag mappings
PLACE_TYPE_TAGS: Dict[str, PlaceType] = {
    "building": PlaceType.BUILDING,
    "park": PlaceType.PARK,
    "school": PlaceType.SCHOOL,
    "hospital": PlaceType.HOSPITAL,
    "aeroway": PlaceType.AIRPORT,
    "aerodrome": PlaceType.AIRPORT,
    "helipad": PlaceType.HELIPAD,
    "prison": PlaceType.PRISON,
    "military": PlaceType.MILITARY,
    "stadium": PlaceType.STADIUM,
    "power": PlaceType.POWER_PLANT,
    "residential": PlaceType.RESIDENTIAL,
    "commercial": PlaceType.COMMERCIAL,
    "industrial": PlaceType.INDUSTRIAL,
    "forest": PlaceType.FOREST,
    "water": PlaceType.WATER,
    "parking": PlaceType.PARKING,
}

OBSTACLE_TYPE_TAGS: Dict[str, ObstacleType] = {
    "building": ObstacleType.BUILDING,
    "tower": ObstacleType.TOWER,
    "power": ObstacleType.POWER_LINE,
    "tree": ObstacleType.TREE,
    "bridge": ObstacleType.BRIDGE,
    "crane": ObstacleType.CRANE,
    "antenna": ObstacleType.ANTENNA,
    "windmill": ObstacleType.WINDMILL,
}


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, requests_per_second: float = 1.0):
        self._interval = 1.0 / requests_per_second
        self._last_request = 0.0

    async def wait(self) -> None:
        """Wait until next request is allowed."""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._interval:
            await asyncio.sleep(self._interval - elapsed)
        self._last_request = time.monotonic()


class DiskCache:
    """Disk-based cache for OSM responses."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 86400 * 7):
        """Initialize disk cache.

        Args:
            cache_dir: Directory for cache files.
            ttl_seconds: Time-to-live for cached items (default: 7 days).
        """
        self._cache_dir = cache_dir
        self._ttl = ttl_seconds
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, query: str) -> str:
        """Generate cache key from query."""
        return hashlib.sha256(query.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        """Get cache file path."""
        return self._cache_dir / f"{key}.json"

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached response.

        Args:
            query: Query string.

        Returns:
            Cached response or None if not found/expired.
        """
        key = self._cache_key(query)
        path = self._cache_path(key)

        if not path.exists():
            return None

        # Check TTL
        stat = path.stat()
        age = time.time() - stat.st_mtime
        if age > self._ttl:
            logger.debug(f"Cache expired for {key}")
            return None

        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read cache {key}: {e}")
            return None

    def set(self, query: str, response: Dict[str, Any]) -> None:
        """Cache a response.

        Args:
            query: Query string.
            response: Response to cache.
        """
        key = self._cache_key(query)
        path = self._cache_path(key)

        try:
            with open(path, "w") as f:
                json.dump(response, f)
        except Exception as e:
            logger.warning(f"Failed to write cache {key}: {e}")


class OSMProvider(MappingProvider):
    """OpenStreetMap data provider using Overpass API.

    Provides places, obstacles, and land use data from OSM.
    All responses are cached to disk for offline capability.
    """

    # Overpass API endpoints (try multiple for reliability)
    OVERPASS_ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    ]

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        rate_limit: float = 1.0,
    ):
        """Initialize OSM provider.

        Args:
            cache_dir: Directory for cache files.
            rate_limit: Requests per second limit.
        """
        config = get_config()
        self._cache = DiskCache(cache_dir or config.osm_cache_dir)
        self._rate_limiter = RateLimiter(rate_limit)
        self._endpoint_index = 0

    async def _query_overpass(self, query: str) -> Dict[str, Any]:
        """Execute an Overpass QL query.

        Args:
            query: Overpass QL query string.

        Returns:
            Parsed JSON response.
        """
        # Check cache first
        cached = self._cache.get(query)
        if cached is not None:
            logger.debug(f"Overpass cache hit")
            return cached

        # Rate limit
        await self._rate_limiter.wait()

        # Try endpoints
        for i in range(len(self.OVERPASS_ENDPOINTS)):
            endpoint = self.OVERPASS_ENDPOINTS[
                (self._endpoint_index + i) % len(self.OVERPASS_ENDPOINTS)
            ]

            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        endpoint,
                        data={"data": query},
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._cache.set(query, data)
                            self._endpoint_index = (
                                self._endpoint_index + i
                            ) % len(self.OVERPASS_ENDPOINTS)
                            return data
                        else:
                            logger.warning(
                                f"Overpass error {resp.status} from {endpoint}"
                            )
            except asyncio.TimeoutError:
                logger.warning(f"Overpass timeout from {endpoint}")
            except Exception as e:
                logger.warning(f"Overpass error from {endpoint}: {e}")

        # All endpoints failed
        logger.error("All Overpass endpoints failed")
        return {"elements": []}

    def _parse_element(self, elem: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse an OSM element to extract coordinates.

        Args:
            elem: OSM element dict.

        Returns:
            Dict with lat/lon or None if no coordinates.
        """
        if elem.get("type") == "node":
            return {
                "lat": elem.get("lat"),
                "lon": elem.get("lon"),
                "tags": elem.get("tags", {}),
                "osm_id": f"n{elem.get('id')}",
            }
        elif elem.get("type") in ("way", "relation"):
            # Use center if available
            center = elem.get("center", {})
            if center:
                return {
                    "lat": center.get("lat"),
                    "lon": center.get("lon"),
                    "tags": elem.get("tags", {}),
                    "osm_id": f"{elem.get('type')[0]}{elem.get('id')}",
                }
        return None

    def _classify_place(self, tags: Dict[str, str]) -> PlaceType:
        """Classify place type from OSM tags.

        Args:
            tags: OSM tags dict.

        Returns:
            PlaceType classification.
        """
        for key, value in tags.items():
            # Check for specific values
            if key in PLACE_TYPE_TAGS:
                return PLACE_TYPE_TAGS[key]
            # Check if value matches
            if value in PLACE_TYPE_TAGS:
                return PLACE_TYPE_TAGS[value]
        return PlaceType.UNKNOWN

    def _classify_obstacle(self, tags: Dict[str, str]) -> ObstacleType:
        """Classify obstacle type from OSM tags.

        Args:
            tags: OSM tags dict.

        Returns:
            ObstacleType classification.
        """
        # Check building first (most common)
        if "building" in tags:
            return ObstacleType.BUILDING

        for key, value in tags.items():
            if key in OBSTACLE_TYPE_TAGS:
                return OBSTACLE_TYPE_TAGS[key]
            if value in OBSTACLE_TYPE_TAGS:
                return OBSTACLE_TYPE_TAGS[value]
        return ObstacleType.UNKNOWN

    async def search_places(
        self,
        query: str,
        bbox: Optional[BBox] = None,
        limit: int = 10,
    ) -> List[PlaceResult]:
        """Search for places matching a query.

        Args:
            query: Search query.
            bbox: Optional bounding box to limit search.
            limit: Maximum results.

        Returns:
            List of matching places.
        """
        # Build Overpass query
        if bbox:
            bbox_str = f"({bbox.south},{bbox.west},{bbox.north},{bbox.east})"
        else:
            bbox_str = ""  # Global search

        overpass_query = f"""
            [out:json][timeout:25];
            {bbox_str}
            (
                node["name"~"{query}",i];
                way["name"~"{query}",i];
                relation["name"~"{query}",i];
            );
            out center {limit};
        """

        data = await self._query_overpass(overpass_query)

        results: List[PlaceResult] = []
        for elem in data.get("elements", []):
            parsed = self._parse_element(elem)
            if parsed and parsed["lat"] and parsed["lon"]:
                results.append(
                    PlaceResult(
                        name=parsed["tags"].get("name", "Unknown"),
                        place_type=self._classify_place(parsed["tags"]),
                        location=Point(lat_deg=parsed["lat"], lon_deg=parsed["lon"]),
                        importance=0.5,  # Default importance
                        tags=tuple(parsed["tags"].items()),
                        osm_id=parsed["osm_id"],
                    )
                )

        return results[:limit]

    async def lookup_place(self, place_id: str) -> Optional[PlaceResult]:
        """Look up a specific place by OSM ID.

        Args:
            place_id: OSM ID (e.g., 'n123', 'w456', 'r789').

        Returns:
            Place details or None.
        """
        if not place_id or len(place_id) < 2:
            return None

        osm_type = place_id[0]
        osm_id = place_id[1:]

        type_map = {"n": "node", "w": "way", "r": "relation"}
        if osm_type not in type_map:
            return None

        overpass_query = f"""
            [out:json][timeout:10];
            {type_map[osm_type]}(id:{osm_id});
            out center;
        """

        data = await self._query_overpass(overpass_query)

        for elem in data.get("elements", []):
            parsed = self._parse_element(elem)
            if parsed and parsed["lat"] and parsed["lon"]:
                return PlaceResult(
                    name=parsed["tags"].get("name", "Unknown"),
                    place_type=self._classify_place(parsed["tags"]),
                    location=Point(lat_deg=parsed["lat"], lon_deg=parsed["lon"]),
                    importance=0.5,
                    tags=tuple(parsed["tags"].items()),
                    osm_id=parsed["osm_id"],
                )

        return None

    async def get_obstacles_in_area(self, bbox: BBox) -> List[ObstacleResult]:
        """Get obstacles in an area.

        Args:
            bbox: Bounding box.

        Returns:
            List of obstacles.
        """
        overpass_query = f"""
            [out:json][timeout:25];
            (
                way["building"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                way["man_made"~"tower|antenna|crane"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                node["man_made"~"tower|antenna|crane"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                way["power"~"line|tower"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                way["bridge"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
            );
            out center;
        """

        data = await self._query_overpass(overpass_query)

        results: List[ObstacleResult] = []
        for elem in data.get("elements", []):
            parsed = self._parse_element(elem)
            if parsed and parsed["lat"] and parsed["lon"]:
                tags = parsed["tags"]

                # Estimate height from tags
                height_m = None
                if "height" in tags:
                    try:
                        height_m = float(tags["height"].replace("m", ""))
                    except ValueError:
                        pass
                elif "building:levels" in tags:
                    try:
                        height_m = float(tags["building:levels"]) * 3.0
                    except ValueError:
                        pass

                results.append(
                    ObstacleResult(
                        name=tags.get("name", "Unknown Obstacle"),
                        obstacle_type=self._classify_obstacle(tags),
                        location=Point(lat_deg=parsed["lat"], lon_deg=parsed["lon"]),
                        height_m=height_m,
                        osm_id=parsed["osm_id"],
                    )
                )

        return results

    async def get_land_use(self, bbox: BBox) -> List[LandUseResult]:
        """Get land use classification for an area.

        Args:
            bbox: Bounding box.

        Returns:
            List of land use types.
        """
        overpass_query = f"""
            [out:json][timeout:25];
            (
                way["landuse"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                relation["landuse"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                way["natural"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
                relation["natural"]({bbox.south},{bbox.west},{bbox.north},{bbox.east});
            );
            out center;
        """

        data = await self._query_overpass(overpass_query)

        # Count occurrences
        land_use_counts: Dict[str, int] = {}
        for elem in data.get("elements", []):
            tags = elem.get("tags", {})
            if "landuse" in tags:
                land_use_counts[tags["landuse"]] = (
                    land_use_counts.get(tags["landuse"], 0) + 1
                )
            elif "natural" in tags:
                land_use_counts[tags["natural"]] = (
                    land_use_counts.get(tags["natural"], 0) + 1
                )

        total = sum(land_use_counts.values()) or 1

        return [
            LandUseResult(
                land_use_type=lu_type,
                coverage_percent=count / total * 100,
            )
            for lu_type, count in sorted(
                land_use_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]

    async def geocode(self, address: str) -> Optional[Point]:
        """Geocode an address using Nominatim.

        Args:
            address: Address string.

        Returns:
            Coordinates or None.
        """
        # Use Nominatim provider
        nominatim = NominatimProvider()
        return await nominatim.geocode(address)

    async def reverse_geocode(self, point: Point) -> Optional[str]:
        """Reverse geocode coordinates.

        Args:
            point: Geographic coordinates.

        Returns:
            Address string or None.
        """
        nominatim = NominatimProvider()
        return await nominatim.reverse_geocode(point)


class NominatimProvider:
    """Nominatim geocoding provider.

    Provides geocoding and reverse geocoding via Nominatim API.
    """

    NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org"

    def __init__(self, rate_limit: float = 1.0):
        """Initialize Nominatim provider.

        Args:
            rate_limit: Requests per second limit.
        """
        self._rate_limiter = RateLimiter(rate_limit)
        self._cache: Dict[str, Any] = {}

    async def geocode(self, address: str) -> Optional[Point]:
        """Geocode an address.

        Args:
            address: Address string.

        Returns:
            Coordinates or None.
        """
        cache_key = f"geocode:{address}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        await self._rate_limiter.wait()

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.NOMINATIM_ENDPOINT}/search",
                    params={"q": address, "format": "json", "limit": 1},
                    headers={"User-Agent": "Project-Avatar/1.0"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            result = Point(
                                lat_deg=float(data[0]["lat"]),
                                lon_deg=float(data[0]["lon"]),
                            )
                            self._cache[cache_key] = result
                            return result
        except Exception as e:
            logger.warning(f"Nominatim geocode error: {e}")

        return None

    async def reverse_geocode(self, point: Point) -> Optional[str]:
        """Reverse geocode coordinates.

        Args:
            point: Geographic coordinates.

        Returns:
            Address string or None.
        """
        cache_key = f"reverse:{point.lat_deg},{point.lon_deg}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        await self._rate_limiter.wait()

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.NOMINATIM_ENDPOINT}/reverse",
                    params={
                        "lat": point.lat_deg,
                        "lon": point.lon_deg,
                        "format": "json",
                    },
                    headers={"User-Agent": "Project-Avatar/1.0"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        address = data.get("display_name")
                        self._cache[cache_key] = address
                        return address
        except Exception as e:
            logger.warning(f"Nominatim reverse geocode error: {e}")

        return None


__all__ = [
    "OSMProvider",
    "NominatimProvider",
    "RateLimiter",
    "DiskCache",
]
