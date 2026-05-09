"""Tests for mission_intel.area_analyzer module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from avatar.mission_intel.area_analyzer import (
    analyze_area,
    AreaReport,
    ObstacleInfo,
    LandUseInfo,
    AirspaceInfo,
)
from avatar.mission_intel.geo import Point, BBox


class TestAreaReport:
    """Tests for AreaReport dataclass."""

    def test_create_area_report(self):
        """Test creating an area report."""
        center = Point(lat_deg=37.7749, lon_deg=-122.4194)
        report = AreaReport(
            center=center,
            radius_m=500,
            ground_elevation_m=10.0,
        )
        assert report.center.lat_deg == 37.7749
        assert report.radius_m == 500
        assert report.ground_elevation_m == 10.0

    def test_is_suitable_for_flight(self):
        """Test suitability check."""
        center = Point(lat_deg=37.7749, lon_deg=-122.4194)

        # Suitable report
        suitable = AreaReport(center=center, radius_m=500, suitability=0.8)
        assert suitable.is_suitable_for_flight

        # Unsuitable due to low suitability
        unsuitable = AreaReport(center=center, radius_m=500, suitability=0.3)
        assert not unsuitable.is_suitable_for_flight

    def test_is_suitable_with_restricted_airspace(self):
        """Test that restricted airspace makes area unsuitable."""
        center = Point(lat_deg=37.7749, lon_deg=-122.4194)
        report = AreaReport(
            center=center,
            radius_m=500,
            suitability=0.9,
            airspace=AirspaceInfo(has_restricted_area=True),
        )
        assert not report.is_suitable_for_flight


class TestObstacleInfo:
    """Tests for ObstacleInfo dataclass."""

    def test_create_obstacle_info(self):
        """Test creating obstacle info."""
        location = Point(lat_deg=37.7749, lon_deg=-122.4194)
        obstacle = ObstacleInfo(
            name="Building",
            obstacle_type="building",
            location=location,
            height_m=50.0,
            distance_m=100.0,
            bearing_deg=45.0,
        )
        assert obstacle.name == "Building"
        assert obstacle.height_m == 50.0
        assert not obstacle.is_no_fly  # Buildings aren't no-fly by default


class TestLandUseInfo:
    """Tests for LandUseInfo dataclass."""

    def test_create_land_use_info(self):
        """Test creating land use info."""
        lu = LandUseInfo(
            land_use_type="residential",
            coverage_percent=60.0,
            is_restricted=False,
        )
        assert lu.land_use_type == "residential"
        assert lu.coverage_percent == 60.0

    def test_restricted_land_use(self):
        """Test restricted land use."""
        lu = LandUseInfo(
            land_use_type="military",
            coverage_percent=100.0,
            is_restricted=True,
        )
        assert lu.is_restricted


class TestAirspaceInfo:
    """Tests for AirspaceInfo dataclass."""

    def test_empty_airspace(self):
        """Test empty airspace info."""
        airspace = AirspaceInfo()
        assert not airspace.has_airport
        assert not airspace.has_helipad
        assert not airspace.has_restricted_area

    def test_airport_airspace(self):
        """Test airspace with airport."""
        airspace = AirspaceInfo(
            has_airport=True,
            warning="Airport in area - check NOTAMs",
        )
        assert airspace.has_airport
        assert "Airport" in airspace.warning


class TestAnalyzeArea:
    """Tests for analyze_area function."""

    @pytest.mark.asyncio
    async def test_analyze_area_returns_report(self):
        """Test that analyze_area returns a valid report."""
        # Mock the providers to avoid actual API calls
        with patch("avatar.mission_intel.area_analyzer.OSMProvider") as mock_osm:
            mock_osm_instance = MagicMock()
            mock_osm_instance.get_obstacles_in_area = AsyncMock(return_value=[])
            mock_osm_instance.get_land_use = AsyncMock(return_value=[])
            mock_osm_instance.search_places = AsyncMock(return_value=[])
            mock_osm.return_value = mock_osm_instance

            with patch("avatar.mission_intel.area_analyzer.TerrainAnalyzer") as mock_terrain:
                mock_terrain_instance = MagicMock()
                mock_terrain_instance.get_ground_elevation = AsyncMock(return_value=10.0)
                mock_terrain_instance.analyze_terrain = AsyncMock(
                    return_value=MagicMock(
                        ground_elevation_m=10.0,
                        slope_deg=5.0,
                        ruggedness=0.2,
                    )
                )
                mock_terrain.return_value = mock_terrain_instance

                report = await analyze_area(
                    center_lat=37.7749,
                    center_lon=-122.4194,
                    radius_m=500,
                    include_places=False,
                )

                assert isinstance(report, AreaReport)
                assert report.center.lat_deg == 37.7749
                assert report.center.lon_deg == -122.4194
                assert report.radius_m == 500

    @pytest.mark.asyncio
    async def test_analyze_area_offline_sources(self):
        """Test that analyze_area uses OSM/SRTM sources (offline-capable)."""
        with patch("avatar.mission_intel.area_analyzer.OSMProvider") as mock_osm:
            mock_osm_instance = MagicMock()
            mock_osm_instance.get_obstacles_in_area = AsyncMock(return_value=[])
            mock_osm_instance.get_land_use = AsyncMock(return_value=[])
            mock_osm_instance.search_places = AsyncMock(return_value=[])
            mock_osm.return_value = mock_osm_instance

            with patch("avatar.mission_intel.area_analyzer.TerrainAnalyzer") as mock_terrain:
                mock_terrain_instance = MagicMock()
                mock_terrain_instance.get_ground_elevation = AsyncMock(return_value=None)
                mock_terrain_instance.analyze_terrain = AsyncMock(
                    return_value=MagicMock(
                        ground_elevation_m=0.0,
                        slope_deg=0.0,
                        ruggedness=0.0,
                    )
                )
                mock_terrain.return_value = mock_terrain_instance

                report = await analyze_area(
                    center_lat=37.7749,
                    center_lon=-122.4194,
                    radius_m=500,
                    include_places=False,
                )

                # Should indicate OSM as data source
                assert "OSM" in report.data_sources
                assert report.is_offline

    @pytest.mark.asyncio
    async def test_analyze_area_with_obstacles(self):
        """Test analyze_area with obstacles."""
        from avatar.mission_intel.providers.base import ObstacleResult, ObstacleType

        mock_obstacles = [
            ObstacleResult(
                name="Tower",
                obstacle_type=ObstacleType.TOWER,
                location=Point(lat_deg=37.7759, lon_deg=-122.4184),
                height_m=50.0,
            )
        ]

        with patch("avatar.mission_intel.area_analyzer.OSMProvider") as mock_osm:
            mock_osm_instance = MagicMock()
            mock_osm_instance.get_obstacles_in_area = AsyncMock(return_value=mock_obstacles)
            mock_osm_instance.get_land_use = AsyncMock(return_value=[])
            mock_osm_instance.search_places = AsyncMock(return_value=[])
            mock_osm.return_value = mock_osm_instance

            with patch("avatar.mission_intel.area_analyzer.TerrainAnalyzer") as mock_terrain:
                mock_terrain_instance = MagicMock()
                mock_terrain_instance.get_ground_elevation = AsyncMock(return_value=10.0)
                mock_terrain_instance.analyze_terrain = AsyncMock(
                    return_value=MagicMock(
                        ground_elevation_m=10.0,
                        slope_deg=0.0,
                        ruggedness=0.0,
                    )
                )
                mock_terrain.return_value = mock_terrain_instance

                report = await analyze_area(
                    center_lat=37.7749,
                    center_lon=-122.4194,
                    radius_m=500,
                    include_places=False,
                )

                assert len(report.obstacles) == 1
                assert report.obstacles[0].name == "Tower"
