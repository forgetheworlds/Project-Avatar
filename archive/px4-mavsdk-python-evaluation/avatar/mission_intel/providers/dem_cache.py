"""SRTM DEM tile cache for offline elevation data.

Stores SRTM HGT tiles at ~/.cache/avatar/dem/ for offline access.
Supports 1-arcsecond (~30m) and 3-arcsecond (~90m) SRTM data.

HGT File Format:
- Named by southwest corner: N37W122.hgt contains data for 37-38N, 122-121W
- 1-arcsecond: 3601x3601 values (12,967,201 bytes)
- 3-arcsecond: 1201x1201 values (1,442,401 bytes)
- Big-endian signed 16-bit integers (meters)

Usage:
    from avatar.mission_intel.providers.dem_cache import DEMCache

    cache = DEMCache()
    tile = cache.get_tile(37.7749, -122.4194)
    if tile:
        elevation = tile.get_elevation(37.7749, -122.4194)
"""

from __future__ import annotations

import gzip
import logging
import math
import os
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

from avatar.mission_intel.config import get_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DEMTile:
    """A single SRTM HGT tile.

    Attributes:
        lat_min: Minimum latitude (south edge).
        lon_min: Minimum longitude (west edge).
        resolution: Resolution in arcseconds (1 or 3).
        data: Elevation data as 2D array (row-major, north to south).
    """

    lat_min: int
    lon_min: int
    resolution: int  # 1 or 3 arcseconds
    data: Tuple[Tuple[int, ...], ...]  # 2D elevation grid

    @property
    def lat_max(self) -> int:
        """Maximum latitude (north edge)."""
        return self.lat_min + 1

    @property
    def lon_max(self) -> int:
        """Maximum longitude (east edge)."""
        return self.lon_min + 1

    @property
    def grid_size(self) -> int:
        """Grid size (number of points per side)."""
        return 3601 if self.resolution == 1 else 1201

    def contains(self, lat_deg: float, lon_deg: float) -> bool:
        """Check if coordinates are within this tile.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            True if coordinates are within tile bounds.
        """
        return (
            self.lat_min <= lat_deg < self.lat_max
            and self.lon_min <= lon_deg < self.lon_max
        )

    def get_elevation(self, lat_deg: float, lon_deg: float) -> Optional[int]:
        """Get elevation at coordinates using bilinear interpolation.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Elevation in meters, or None if void value (-32768).
        """
        if not self.contains(lat_deg, lon_deg):
            return None

        # Convert to grid coordinates
        # Note: HGT files are ordered north to south (top to bottom)
        # so latitude offset needs to be inverted
        lat_offset = self.lat_max - lat_deg  # Distance from north edge
        lon_offset = lon_deg - self.lon_min  # Distance from west edge

        cell_size = 1.0 / self.grid_size  # Degrees per cell

        # Grid indices (floating point)
        row_f = lat_offset / cell_size
        col_f = lon_offset / cell_size

        # Integer indices for the surrounding cells
        row0 = int(row_f)
        col0 = int(col_f)

        # Clamp to valid range
        max_idx = self.grid_size - 1
        row0 = min(max(row0, 0), max_idx - 1)
        col0 = min(max(col0, 0), max_idx - 1)
        row1 = row0 + 1
        col1 = col0 + 1

        # Get elevation values for four corners
        e00 = self.data[row0][col0]
        e01 = self.data[row0][col1]
        e10 = self.data[row1][col0]
        e11 = self.data[row1][col1]

        # Check for void values
        void_value = -32768
        if any(e == void_value for e in (e00, e01, e10, e11)):
            return None

        # Bilinear interpolation
        row_frac = row_f - row0
        col_frac = col_f - col0

        elevation = (
            e00 * (1 - row_frac) * (1 - col_frac)
            + e01 * (1 - row_frac) * col_frac
            + e10 * row_frac * (1 - col_frac)
            + e11 * row_frac * col_frac
        )

        return int(round(elevation))


class DEMCache:
    """Cache manager for SRTM DEM tiles.

    Handles:
    - Loading tiles from disk
    - Automatic download from NASA EarthData (if credentials available)
    - In-memory caching of loaded tiles
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the DEM cache.

        Args:
            cache_dir: Directory for cached tiles. Defaults to config setting.
        """
        self._config = get_config()
        self._cache_dir = cache_dir or self._config.dem_cache_dir
        self._tiles: Dict[str, DEMTile] = {}
        self._miss_count = 0

        # Ensure cache directory exists
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _tile_filename(self, lat_deg: float, lon_deg: float) -> str:
        """Generate HGT filename for coordinates.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            HGT filename (e.g., 'N37W122.hgt').
        """
        lat_int = int(math.floor(lat_deg))
        lon_int = int(math.floor(lon_deg))

        lat_prefix = "N" if lat_int >= 0 else "S"
        lon_prefix = "E" if lon_int >= 0 else "W"

        return f"{lat_prefix}{abs(lat_int):02d}{lon_prefix}{abs(lon_int):03d}.hgt"

    def _tile_key(self, lat_deg: float, lon_deg: float) -> str:
        """Generate cache key for coordinates.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Cache key (e.g., 'N37W122').
        """
        lat_int = int(math.floor(lat_deg))
        lon_int = int(math.floor(lon_deg))

        lat_prefix = "N" if lat_int >= 0 else "S"
        lon_prefix = "E" if lon_int >= 0 else "W"

        return f"{lat_prefix}{abs(lat_int):02d}{lon_prefix}{abs(lon_int):03d}"

    def _load_tile_from_file(self, filepath: Path) -> Optional[DEMTile]:
        """Load a tile from an HGT file.

        Args:
            filepath: Path to the HGT file.

        Returns:
            Loaded DEMTile or None if file invalid.
        """
        try:
            # Check for gzipped file
            if filepath.suffix == ".gz":
                with gzip.open(filepath, "rb") as f:
                    raw_data = f.read()
            else:
                with open(filepath, "rb") as f:
                    raw_data = f.read()

            # Determine resolution from file size
            file_size = len(raw_data)
            if file_size == 3601 * 3601 * 2:  # 1-arcsecond
                resolution = 1
                grid_size = 3601
            elif file_size == 1201 * 1201 * 2:  # 3-arcsecond
                resolution = 3
                grid_size = 1201
            else:
                logger.warning(f"Unknown HGT file size: {file_size}")
                return None

            # Parse filename to get coordinates
            filename = filepath.stem if filepath.suffix == ".gz" else filepath.name
            # Parse: N37W122.hgt
            lat_prefix = filename[0]
            lat_min = int(filename[1:3])
            lon_prefix = filename[3]
            lon_min = int(filename[4:7])

            if lat_prefix == "S":
                lat_min = -lat_min
            if lon_prefix == "W":
                lon_min = -lon_min

            # Parse elevation data
            # Big-endian signed 16-bit integers
            values = struct.unpack(f">{grid_size * grid_size}h", raw_data)

            # Convert to 2D grid (row-major, north to south)
            data = tuple(
                tuple(values[row * grid_size : (row + 1) * grid_size])
                for row in range(grid_size)
            )

            return DEMTile(
                lat_min=lat_min,
                lon_min=lon_min,
                resolution=resolution,
                data=data,
            )

        except Exception as e:
            logger.error(f"Failed to load HGT file {filepath}: {e}")
            return None

    def get_tile(self, lat_deg: float, lon_deg: float) -> Optional[DEMTile]:
        """Get a DEM tile for the given coordinates.

        Checks in-memory cache first, then disk cache.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            DEMTile if available, None otherwise.
        """
        key = self._tile_key(lat_deg, lon_deg)

        # Check in-memory cache
        if key in self._tiles:
            return self._tiles[key]

        # Look for file on disk
        filename = self._tile_filename(lat_deg, lon_deg)
        filepath = self._cache_dir / filename
        gz_path = self._cache_dir / f"{filename}.gz"

        # Try uncompressed first, then gzipped
        for path in [filepath, gz_path]:
            if path.exists():
                tile = self._load_tile_from_file(path)
                if tile:
                    self._tiles[key] = tile
                    return tile

        # Not found
        self._miss_count += 1
        logger.debug(f"DEM tile not found for {lat_deg}, {lon_deg} (key={key})")
        return None

    def get_elevation(self, lat_deg: float, lon_deg: float) -> Optional[int]:
        """Get elevation for a point.

        Convenience method that gets the tile and queries it.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            Elevation in meters or None if not available.
        """
        tile = self.get_tile(lat_deg, lon_deg)
        if tile:
            return tile.get_elevation(lat_deg, lon_deg)
        return None

    def has_tile(self, lat_deg: float, lon_deg: float) -> bool:
        """Check if a tile exists for the given coordinates.

        Args:
            lat_deg: Latitude in degrees.
            lon_deg: Longitude in degrees.

        Returns:
            True if tile is available.
        """
        key = self._tile_key(lat_deg, lon_deg)
        if key in self._tiles:
            return True

        filename = self._tile_filename(lat_deg, lon_deg)
        filepath = self._cache_dir / filename
        gz_path = self._cache_dir / f"{filename}.gz"

        return filepath.exists() or gz_path.exists()

    def clear_memory_cache(self) -> None:
        """Clear the in-memory tile cache."""
        self._tiles.clear()

    def stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        return {
            "tiles_in_memory": len(self._tiles),
            "cache_misses": self._miss_count,
            "tiles_on_disk": len(list(self._cache_dir.glob("*.hgt")))
            + len(list(self._cache_dir.glob("*.hgt.gz"))),
        }


__all__ = [
    "DEMTile",
    "DEMCache",
]
