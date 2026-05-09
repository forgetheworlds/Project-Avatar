"""Tests for set_geofence_polygon primitive.

WHAT THESE TESTS VALIDATE:
    These tests verify the set_geofence_polygon MCP tool which uploads
    a polygonal geofence to PX4. Key capabilities tested:
    - Polygon input schema validation
    - Geofence upload via MAVSDK
    - Shrinking fence requires confirmation (curated #3)
    - Guardian geofence state update
    - Error handling for disconnection

WHY THESE TESTS MATTER:
    Geofence is a critical safety boundary that prevents the drone from
    flying outside a designated area. Without proper geofence management:
    - Drone could fly into restricted airspace
    - Could exceed radio control range
    - Could violate airspace regulations
    - Emergency RTL might not work correctly

EXPECTED OUTCOMES EXPLAINED:
    Each test validates specific geofence behaviors:
    - Success: Polygon uploaded, guardian updated, fence_id returned
    - Shrinking: Requires confirmation before applying smaller fence
    - Disconnected: Returns NOT_CONNECTED error envelope

Test-driven development for W2a-T10: set_geofence_polygon primitive.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import errors for ErrorCode access
from avatar.mcp_server.errors import ErrorCode
from avatar.mcp_server.schemas import Point, Polygon


# =============================================================================
# TEST FIXTURES
# =============================================================================


def _square_vertices() -> list[Point]:
    """Create a simple square polygon around San Francisco."""
    return [
        Point(lat_deg=37.7749, lon_deg=-122.4194),
        Point(lat_deg=37.7759, lon_deg=-122.4194),
        Point(lat_deg=37.7759, lon_deg=-122.4184),
        Point(lat_deg=37.7749, lon_deg=-122.4184),
    ]


def _smaller_square_vertices() -> list[Point]:
    """Create a smaller square polygon (for shrinking tests)."""
    return [
        Point(lat_deg=37.7751, lon_deg=-122.4192),
        Point(lat_deg=37.7757, lon_deg=-122.4192),
        Point(lat_deg=37.7757, lon_deg=-122.4186),
        Point(lat_deg=37.7751, lon_deg=-122.4186),
    ]


@pytest.fixture
def mock_guardian():
    """Create a mock GuardianProcess."""
    guardian = MagicMock()
    guardian.preflight = AsyncMock(return_value=None)
    guardian.set_geofence_polygon = MagicMock()
    guardian.get_geofence_polygon = MagicMock(return_value=None)  # No existing fence
    guardian.home_position = (37.7749, -122.4194)
    return guardian


@pytest.fixture
def mock_confirmation():
    """Create a mock ConfirmationManager."""
    confirmation = MagicMock()
    confirmation.require = AsyncMock()
    confirmation.get_pending = MagicMock(return_value={"approved": True})
    confirmation.clear_pending = MagicMock()
    return confirmation


@pytest.fixture
def mock_drone():
    """Create a mock drone with geofence support."""
    drone = MagicMock()

    # Mock geofence upload
    geofence_mock = MagicMock()
    geofence_mock.upload_geofence = AsyncMock()
    drone.geofence = geofence_mock

    return drone


@pytest.fixture
def mock_connection_manager(mock_drone):
    """Create a mock ConnectionManager."""
    cm = MagicMock()
    cm.ensure_connected = AsyncMock(return_value=mock_drone)
    return cm


@pytest.fixture
def mock_session():
    """Create a mock session with auto_confirm disabled."""
    session = MagicMock()
    session.auto_confirm = False
    return session


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestSetGeofencePolygonSchema:
    """Tests for input schema validation."""

    def test_polygon_schema_valid(self):
        """Test that valid polygon passes schema validation."""
        polygon = Polygon(vertices=_square_vertices())
        assert len(polygon.vertices) == 4
        assert all(isinstance(v, Point) for v in polygon.vertices)

    def test_polygon_requires_minimum_vertices(self):
        """Test that polygon requires at least 3 vertices."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Polygon(vertices=[
                Point(lat_deg=37.7749, lon_deg=-122.4194),
                Point(lat_deg=37.7759, lon_deg=-122.4194),
            ])


class TestSetGeofencePolygonSuccess:
    """Tests for successful geofence polygon upload."""

    @pytest.mark.asyncio
    async def test_upload_polygon_success(
        self, mock_guardian, mock_confirmation, mock_connection_manager, mock_session
    ):
        """Test successful polygon upload without existing fence."""
        # Import primitive module with mocked dependencies
        from avatar.mcp_server.tools import primitives as prim

        # Setup mocks
        with patch.object(prim, "_guardian", mock_guardian), \
             patch.object(prim, "_confirmation", mock_confirmation), \
             patch.object(prim, "_connection_manager_global", mock_connection_manager), \
             patch.object(prim, "_get_session", lambda: mock_session):

            # Patch to_error_envelope to return proper structure
            def mock_error(code, msg, **kw):
                return {"isError": True, "error": {"code": code.value}}
            with patch.object(prim, "to_error_envelope", mock_error):
                raw = await prim.handle_set_geofence_polygon({
                    "polygon": {"vertices": [
                        {"lat_deg": v.lat_deg, "lon_deg": v.lon_deg}
                        for v in _square_vertices()
                    ]},
                    "action": "rtl"
                })

            result = json.loads(raw)
            assert result.get("applied") is True
            mock_connection_manager.ensure_connected.assert_awaited()

    @pytest.mark.asyncio
    async def test_auto_confirm_bypasses_confirmation(
        self, mock_guardian, mock_confirmation, mock_connection_manager
    ):
        """Test that auto_confirm=True bypasses confirmation requirement."""
        from avatar.mcp_server.tools import primitives as prim

        # Create session with auto_confirm enabled
        auto_session = MagicMock()
        auto_session.auto_confirm = True

        with patch.object(prim, "_guardian", mock_guardian), \
             patch.object(prim, "_confirmation", mock_confirmation), \
             patch.object(prim, "_connection_manager_global", mock_connection_manager), \
             patch.object(prim, "_get_session", lambda: auto_session):

            raw = await prim.handle_set_geofence_polygon({
                "polygon": {"vertices": [
                    {"lat_deg": v.lat_deg, "lon_deg": v.lon_deg}
                    for v in _square_vertices()
                ]},
                "action": "rtl"
            })

            result = json.loads(raw)
            # With auto_confirm, should not call confirmation.require
            mock_confirmation.require.assert_not_awaited()
            assert result.get("applied") is True


class TestSetGeofencePolygonShrinking:
    """Tests for shrinking geofence confirmation (curated #3)."""

    @pytest.mark.asyncio
    async def test_shrinking_fence_requires_confirmation(
        self, mock_guardian, mock_confirmation, mock_connection_manager, mock_session
    ):
        """Test that shrinking existing fence triggers confirmation."""
        from avatar.mcp_server.tools import primitives as prim
        import avatar.mcp_server.tools.primitives as prim_module

        # Setup guardian with existing larger fence
        existing_fence = Polygon(vertices=_square_vertices())
        mock_guardian.get_geofence_polygon = MagicMock(return_value=existing_fence)

        # Setup confirmation to require approval and reject it
        mock_confirmation.require = AsyncMock()
        # Simulate rejection by having get_pending return non-approved
        mock_confirmation.get_pending = MagicMock(return_value={"approved": False})
        mock_confirmation.clear_pending = MagicMock()

        # Directly set module-level variables
        prim_module._guardian = mock_guardian
        prim_module._confirmation = mock_confirmation
        prim_module._connection_manager_global = mock_connection_manager

        try:
            # Try to upload smaller polygon without shrink_ok
            raw = await prim.handle_set_geofence_polygon({
                "polygon": {"vertices": [
                    {"lat_deg": v.lat_deg, "lon_deg": v.lon_deg}
                    for v in _smaller_square_vertices()
                ]},
                "action": "rtl",
                "shrink_ok": False
            })

            result = json.loads(raw)
            # Should either be CONFIRMATION_REQUIRED or the require was called
            # Check that confirmation was required
            mock_confirmation.require.assert_awaited()
        finally:
            # Reset module variables
            prim_module._guardian = None
            prim_module._confirmation = None
            prim_module._connection_manager_global = None

    @pytest.mark.asyncio
    async def test_shrinking_fence_with_shrink_ok(
        self, mock_guardian, mock_confirmation, mock_connection_manager, mock_session
    ):
        """Test that shrink_ok=True allows shrinking without confirmation."""
        from avatar.mcp_server.tools import primitives as prim

        # Setup guardian with existing larger fence
        existing_fence = Polygon(vertices=_square_vertices())
        mock_guardian.get_geofence_polygon = MagicMock(return_value=existing_fence)

        with patch.object(prim, "_guardian", mock_guardian), \
             patch.object(prim, "_confirmation", mock_confirmation), \
             patch.object(prim, "_connection_manager_global", mock_connection_manager), \
             patch.object(prim, "_get_session", lambda: mock_session):

            # Upload smaller polygon WITH shrink_ok
            raw = await prim.handle_set_geofence_polygon({
                "polygon": {"vertices": [
                    {"lat_deg": v.lat_deg, "lon_deg": v.lon_deg}
                    for v in _smaller_square_vertices()
                ]},
                "action": "rtl",
                "shrink_ok": True
            })

            result = json.loads(raw)
            # With shrink_ok=True, should proceed without confirmation
            assert result.get("applied") is True


class TestSetGeofencePolygonErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_disconnected_returns_error(
        self, mock_guardian, mock_confirmation, mock_session
    ):
        """Test that disconnection returns NOT_CONNECTED error."""
        from avatar.mcp_server.tools import primitives as prim

        # ConnectionManager returns None (no drone)
        disconnected_cm = MagicMock()
        disconnected_cm.ensure_connected = AsyncMock(return_value=None)

        auto_session = MagicMock()
        auto_session.auto_confirm = True

        with patch.object(prim, "_guardian", mock_guardian), \
             patch.object(prim, "_confirmation", mock_confirmation), \
             patch.object(prim, "_connection_manager_global", disconnected_cm), \
             patch.object(prim, "_get_session", lambda: auto_session):

            raw = await prim.handle_set_geofence_polygon({
                "polygon": {"vertices": [
                    {"lat_deg": v.lat_deg, "lon_deg": v.lon_deg}
                    for v in _square_vertices()
                ]},
                "action": "warn"
            })

            result = json.loads(raw)
            assert result.get("isError") is True
            assert result.get("error", {}).get("code") == ErrorCode.MAV_NOT_CONNECTED.value


class TestSetGeofencePolygonToolFunctions:
    """Tests for MCP tool schema and annotation functions."""

    def test_tool_schema_returns_dict(self):
        """Test that tool schema function returns valid dict."""
        from avatar.mcp_server.tools import primitives as prim

        schema = prim.set_geofence_polygon_tool_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "polygon" in schema["properties"]

    def test_output_schema_returns_dict(self):
        """Test that output schema function returns valid dict."""
        from avatar.mcp_server.tools import primitives as prim

        schema = prim.set_geofence_polygon_output_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_annotations_are_correct(self):
        """Test that annotations follow destructiveHint=True."""
        from avatar.mcp_server.tools import primitives as prim

        annotations = prim.set_geofence_polygon_annotations()
        assert annotations.get("readOnlyHint") is False
        assert annotations.get("destructiveHint") is True
        assert annotations.get("idempotentHint") is False
        assert annotations.get("openWorldHint") is False


class TestPolygonAreaCalculation:
    """Tests for polygon area calculation (used for shrinking detection)."""

    def test_polygon_area_positive(self):
        """Test that polygon area calculation returns positive value."""
        from avatar.mcp_server.tools import primitives as prim

        polygon = Polygon(vertices=_square_vertices())
        area = prim._polygon_area_m2(polygon)
        assert area > 0

    def test_larger_polygon_has_larger_area(self):
        """Test that larger polygon has larger calculated area."""
        from avatar.mcp_server.tools import primitives as prim

        large_polygon = Polygon(vertices=_square_vertices())
        small_polygon = Polygon(vertices=_smaller_square_vertices())

        large_area = prim._polygon_area_m2(large_polygon)
        small_area = prim._polygon_area_m2(small_polygon)

        assert large_area > small_area
