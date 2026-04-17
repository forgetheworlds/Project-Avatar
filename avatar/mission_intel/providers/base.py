"""Base protocols for mapping and elevation providers.

Defines the interfaces that all providers must implement, allowing for
easy swapping between OSM/Google Maps and SRTM/Open-Elevation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Protocol, Tuple, runtime_checkable

from avatar.mission_intel.geo import BBox, Point


class PlaceType(str, Enum):
    """Classification of place types."""

    BUILDING = "building"
    PARK = "park"
    SCHOOL = "school"
    HOSPITAL = "hospital"
    AIRPORT = "airport"
    HELIPAD = "helipad"
    PRISON = "prison"
    MILITARY = "military"
    STADIUM = "stadium"
    POWER_PLANT = "power_plant"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    FOREST = "forest"
    WATER = "water"
    ROAD = "road"
    PARKING = "parking"
    UNKNOWN = "unknown"


class ObstacleType(str, Enum):
    """Types of obstacles for drone flight."""

    BUILDING = "building"
    TOWER = "tower"
    POWER_LINE = "power_line"
    TREE = "tree"
    BRIDGE = "bridge"
    CRANE = "crane"
    ANTENNA = "antenna"
    WINDMILL = "windmill"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PlaceResult:
    """Result from a place search.

    Attributes:
        name: Name of the place.
        place_type: Classification of the place.
        location: Geographic location.
        importance: Relevance score (0-1).
        tags: Additional OSM tags.
        address: Formatted address if available.
        osm_id: OSM relation/way/node ID if from OSM.
    """

    name: str
    place_type: PlaceType
    location: Point
    importance: float = 0.5
    tags: Tuple[Tuple[str, str], ...] = ()
    address: Optional[str] = None
    osm_id: Optional[str] = None

    @property
    def is_no_fly_zone(self) -> bool:
        """Check if this place type is typically a no-fly zone."""
        no_fly_types = {
            PlaceType.AIRPORT,
            PlaceType.HELIPAD,
            PlaceType.PRISON,
            PlaceType.MILITARY,
            PlaceType.HOSPITAL,
            PlaceType.POWER_PLANT,
            PlaceType.STADIUM,
        }
        return self.place_type in no_fly_types


@dataclass(frozen=True, slots=True)
class ObstacleResult:
    """Result from an obstacle search.

    Attributes:
        name: Name or description of the obstacle.
        obstacle_type: Type of obstacle.
        location: Geographic location (center point).
        height_m: Estimated height in meters (if known).
        radius_m: Estimated radius/extent in meters.
        osm_id: OSM ID if from OSM.
    """

    name: str
    obstacle_type: ObstacleType
    location: Point
    height_m: Optional[float] = None
    radius_m: Optional[float] = None
    osm_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ElevationResult:
    """Result from an elevation query.

    Attributes:
        elevation_m: Elevation above sea level in meters.
        source: Data source (SRTM, Open-Elevation, etc.).
        resolution_m: Resolution of the elevation data in meters.
        is_interpolated: True if value was interpolated between data points.
    """

    elevation_m: float
    source: str
    resolution_m: float = 30.0
    is_interpolated: bool = False


@dataclass(frozen=True, slots=True)
class LandUseResult:
    """Land use classification for an area.

    Attributes:
        land_use_type: Primary land use type.
        coverage_percent: Percentage coverage in the area.
    """

    land_use_type: str
    coverage_percent: float = 0.0


@runtime_checkable
class MappingProvider(Protocol):
    """Protocol for mapping data providers.

    Implementations: OSMProvider, GoogleMapsProvider
    """

    async def search_places(
        self,
        query: str,
        bbox: Optional[BBox] = None,
        limit: int = 10,
    ) -> List[PlaceResult]:
        """Search for places matching a query.

        Args:
            query: Search query (e.g., "park", "school").
            bbox: Optional bounding box to limit search area.
            limit: Maximum number of results.

        Returns:
            List of matching places.
        """
        ...

    async def lookup_place(self, place_id: str) -> Optional[PlaceResult]:
        """Look up a specific place by ID.

        Args:
            place_id: Place identifier (OSM ID or Google Place ID).

        Returns:
            Place details or None if not found.
        """
        ...

    async def get_obstacles_in_area(
        self,
        bbox: BBox,
    ) -> List[ObstacleResult]:
        """Get obstacles in an area.

        Args:
            bbox: Bounding box to search.

        Returns:
            List of obstacles in the area.
        """
        ...

    async def get_land_use(
        self,
        bbox: BBox,
    ) -> List[LandUseResult]:
        """Get land use classification for an area.

        Args:
            bbox: Bounding box to analyze.

        Returns:
            List of land use types and their coverage.
        """
        ...

    async def geocode(
        self,
        address: str,
    ) -> Optional[Point]:
        """Geocode an address to coordinates.

        Args:
            address: Address string.

        Returns:
            Coordinates or None if not found.
        """
        ...

    async def reverse_geocode(
        self,
        point: Point,
    ) -> Optional[str]:
        """Reverse geocode coordinates to an address.

        Args:
            point: Geographic coordinates.

        Returns:
            Address string or None if not found.
        """
        ...


@runtime_checkable
class ElevationProvider(Protocol):
    """Protocol for elevation data providers.

    Implementations: SRTMProvider, OpenElevationProvider
    """

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
            Elevation result or None if not available.
        """
        ...

    async def get_elevations(
        self,
        points: List[Point],
    ) -> List[Optional[ElevationResult]]:
        """Get elevations for multiple points.

        Args:
            points: List of geographic points.

        Returns:
            List of elevation results (None for points without data).
        """
        ...

    def is_available(self) -> bool:
        """Check if the elevation provider is available.

        Returns:
            True if the provider can serve elevation data.
        """
        ...


__all__ = [
    "PlaceType",
    "ObstacleType",
    "PlaceResult",
    "ObstacleResult",
    "ElevationResult",
    "LandUseResult",
    "MappingProvider",
    "ElevationProvider",
]
