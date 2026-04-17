"""Data providers for mission intelligence.

Provides protocols and implementations for:
- OpenStreetMap (OSM): Places, land use, obstacles (via Overpass/Nominatim)
- SRTM Elevation: Offline elevation data from HGT tiles
- Open-Elevation: Fallback elevation API
- Google Maps: Places, Static Maps, Street View, Roads, Geocoding (optional)

Offline-First Design:
- OSM/SRTM work without internet (with disk cache)
- Google Maps is optional, gracefully degrades when API key absent
- All providers implement common protocols for easy swapping

Usage:
    from avatar.mission_intel.providers import OSMProvider, SRTMProvider

    # OSM lookup (offline-capable with cache)
    osm = OSMProvider()
    places = await osm.search_places("park", bbox)

    # SRTM elevation (offline)
    srtm = SRTMProvider()
    elevation = await srtm.get_elevation(37.7749, -122.4194)
"""

from avatar.mission_intel.providers.base import (
    MappingProvider,
    ElevationProvider,
    PlaceResult,
    ElevationResult,
)
from avatar.mission_intel.providers.osm import OSMProvider, NominatimProvider
from avatar.mission_intel.providers.elevation import SRTMProvider, OpenElevationProvider
from avatar.mission_intel.providers.dem_cache import DEMCache, DEMTile
from avatar.mission_intel.providers.gmaps import (
    GoogleMapsProvider,
    GoogleMapsBudgetExceeded,
)

__all__ = [
    # Protocols
    "MappingProvider",
    "ElevationProvider",
    "PlaceResult",
    "ElevationResult",
    # OSM
    "OSMProvider",
    "NominatimProvider",
    # Elevation
    "SRTMProvider",
    "OpenElevationProvider",
    "DEMCache",
    "DEMTile",
    # Google Maps
    "GoogleMapsProvider",
    "GoogleMapsBudgetExceeded",
]
