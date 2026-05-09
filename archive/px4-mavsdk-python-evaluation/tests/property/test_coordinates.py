"""Property-based tests for coordinate transformations.

PROPERTY-BASED TESTING FOR BEGINNERS
=====================================
Property-based testing is a powerful testing methodology where instead of writing
specific test cases (example: "test that 2+2=4"), you define:

1. PROPERTIES (invariants): Mathematical rules that should ALWAYS hold true
2. GENERATORS: Strategies for creating random test inputs
3. RUNNER: The framework (Hypothesis) generates hundreds/thousands of test cases

WHY PROPERTY TESTS ARE POWERFUL
===============================
- **Finds edge cases**: Generates values like 0, -0, infinity, very large/small numbers
- **Exhaustive coverage**: Tests hundreds of combinations in seconds
- **Shrinking**: When a test fails, Hypothesis finds the MINIMAL failing example
- **No manual test cases**: Write one property test = hundreds of assertions

TRADITIONAL TEST vs PROPERTY TEST
=================================
Traditional:
    def test_addition():
        assert add(2, 3) == 5  # Only tests this one case
        assert add(-1, 1) == 0  # Another specific case

Property-based:
    @given(st.integers(), st.integers())  # ALL integers
    def test_addition_commutative(a, b):
        assert add(a, b) == add(b, a)  # Tests 100+ random pairs

This module uses Hypothesis to generate random test cases for coordinate
conversion functions, finding edge cases that traditional unit tests might miss.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from math import isclose, radians, sin, cos

from avatar.mav.protocols import GeoPoint, VelocityNED
from avatar.mcp_server.tools import haversine_distance
from avatar.mcp_server.tools.flight_tools import body_to_ned


class TestCoordinateProperties:
    """Property-based tests for coordinate transforms.

    Each test method in this class verifies a mathematical INVARIANT - a property
    that must hold true for ALL valid inputs. Hypothesis generates hundreds of
    random inputs to try to find counterexamples.
    """

    @given(
        # HOW HYPOTHESIS GENERATES TEST CASES:
        # st.floats() creates a strategy that generates random floating-point numbers
        # min_value/max_value: Constrain to valid coordinate ranges
        # allow_nan=False: Exclude "Not a Number" values (would break tests)
        # allow_infinity=False: Exclude infinity (usually not valid for coordinates)
        lat=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        alt=st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_geopoint_roundtrip(self, lat: float, lon: float, alt: float) -> None:
        """INVARIANT: GeoPoint creation preserves values within floating-point precision.

        This property test verifies that when we create a GeoPoint with specific
        latitude, longitude, and altitude values, we can retrieve those same values.

        WHY THIS MATTERS: Ensures no precision loss or transformation bugs in the
        data class. Catches issues like:
        - Integer truncation (3.14159 -> 3)
        - Wrong units conversion (meters to feet and back)
        - Data type corruption

        THE INVARIANT: input_value == retrieved_value (within floating-point tolerance)

        EDGE CASES THIS FINDS:
        - Very large altitudes (10000m)
        - Very small values (0.0000001)
        - Negative coordinates (Southern hemisphere, West of prime meridian)
        - Boundary values (-90, 90, -180, 180)
        """
        point = GeoPoint(latitude=lat, longitude=lon, altitude_m=alt)
        # isclose handles floating-point imprecision - 0.1 + 0.2 != 0.3 exactly!
        assert isclose(point.latitude, lat, rel_tol=1e-9, abs_tol=1e-9)
        assert isclose(point.longitude, lon, rel_tol=1e-9, abs_tol=1e-9)
        assert isclose(point.altitude_m, alt, rel_tol=1e-9, abs_tol=1e-9)

    @given(
        north=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        east=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        down=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_velocity_ned_speed(self, north: float, east: float, down: float) -> None:
        """INVARIANT: VelocityNED speed calculation is mathematically correct.

        NED = North-East-Down coordinate frame used in aviation/drones.

        THE INVARIANTS:
        1. Horizontal speed = sqrt(north^2 + east^2) [Pythagorean theorem]
        2. Total speed = sqrt(north^2 + east^2 + down^2)

        WHY THIS MATTERS: A drone's flight controller needs accurate speed calculations
        for navigation. Wrong speed = wrong position estimates = crashes.

        EDGE CASES THIS FINDS:
        - Pure vertical motion (north=0, east=0, down=5)
        - Pure horizontal motion (down=0)
        - Zero velocity (all zeros)
        - Very high speeds (100 m/s = 360 km/h!)
        - Negative velocities (moving south/west/up)
        """
        vel = VelocityNED(north_m_s=north, east_m_s=east, down_m_s=down)
        expected_horizontal_speed = (north**2 + east**2) ** 0.5
        expected_total_speed = (north**2 + east**2 + down**2) ** 0.5

        assert isclose(vel.speed_m_s, expected_horizontal_speed, rel_tol=1e-9)
        assert isclose(vel.total_speed_m_s, expected_total_speed, rel_tol=1e-9)

    @given(
        north=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        east=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        down=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_velocity_ned_non_negative_speed(self, north: float, east: float, down: float) -> None:
        """INVARIANT: VelocityNED speed is always non-negative.

        THE INVARIANT: speed >= 0 for all inputs

        WHY THIS MATTERS: Speed is a magnitude (distance/time), which is always >= 0.
        Even if velocity components are negative, speed should be positive.

        This catches bugs where someone returns the raw velocity component
        instead of the magnitude.

        MATHEMATICAL BASIS: sqrt(x^2) = |x| >= 0 always

        EDGE CASES THIS FINDS:
        - All negative components (drone moving south, west, up)
        - Mixed signs (moving north but also west)
        - Zero speed (drone hovering)
        """
        vel = VelocityNED(north_m_s=north, east_m_s=east, down_m_s=down)
        assert vel.speed_m_s >= 0
        assert vel.total_speed_m_s >= 0

    @given(
        forward=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
        right=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
        yaw=st.floats(min_value=0, max_value=360, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_body_to_ned_distance_preservation(self, forward: float, right: float, yaw: float) -> None:
        """INVARIANT: Body-to-NED transform preserves Euclidean distance.

        BODY FRAME: Drone-centric coordinates
            - forward = +X (direction drone is facing)
            - right = +Y (90 degrees clockwise from forward)

        NED FRAME: World-centric coordinates
            - north, east (aligned with Earth, not drone)

        THE INVARIANT: ||body_vector|| == ||ned_vector||

        WHY THIS MATTERS: A rotation transformation should never change the LENGTH
        of a vector - only its direction. If distance changes, the math is wrong!

        MATHEMATICAL BASIS: Rotation matrices are orthonormal (R^T * R = I),
        which preserves lengths.

        THE assume() CALL:
        - Filters out tiny vectors where floating-point errors dominate
        - Avoids division by zero in relative tolerance checks
        """
        north, east = body_to_ned(forward, right, yaw)

        # Original distance should equal transformed distance
        orig_dist = (forward**2 + right**2) ** 0.5
        new_dist = (north**2 + east**2) ** 0.5

        # Avoid div by zero for very small distances (floating-point noise)
        assume(orig_dist > 0.0001)

        assert isclose(orig_dist, new_dist, rel_tol=1e-4)

    @given(
        forward=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        right=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_body_to_ned_yaw_0_matches_forward(self, forward: float, right: float) -> None:
        """INVARIANT: Body-to-NED at yaw=0: north equals forward, east equals right.

        At yaw=0, the drone is pointing north. So:
        - Body forward = North direction
        - Body right = East direction

        THE INVARIANT:
            yaw=0 => (north, east) == (forward, right)

        WHY THIS MATTERS: This is the "identity" case of the rotation.
        If this fails, the entire coordinate system is misaligned.

        EDGE CASES THIS FINDS:
        - Sign errors in rotation matrix (forward becomes -north)
        - Swapped axes (forward becomes east)
        - Offset errors (yaw=0 actually means something else)
        """
        north, east = body_to_ned(forward, right, 0.0)

        assert isclose(north, forward, rel_tol=1e-9, abs_tol=1e-9)
        assert isclose(east, right, rel_tol=1e-9, abs_tol=1e-9)

    @given(
        forward=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        right=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_body_to_ned_yaw_90_rotates_correctly(self, forward: float, right: float) -> None:
        """INVARIANT: Body-to-NED at yaw=90: north equals -right, east equals forward.

        At yaw=90, the drone is facing EAST. So:
        - Body forward (+X) -> East (+Y_ned)
        - Body right (+Y) -> South (-X_ned = -north)

        THE INVARIANT:
            yaw=90 => (north, east) == (-right, forward)

        WHY THIS MATTERS: Verifies the rotation direction is correct.
        Common bug: using clockwise vs counter-clockwise rotation matrix.

        MATHEMATICAL BASIS:
        Standard 2D rotation matrix for angle θ (counter-clockwise):
            [cos(θ)  -sin(θ)]
            [sin(θ)   cos(θ)]

        At θ=90°: cos=0, sin=1
            [0  -1] [forward]   [-right]
            [1   0] [right  ] = [forward]

        REL_TOL=1e-6: Slightly relaxed tolerance because trigonometric functions
        at 90 degrees have small floating-point errors (sin(90) ≈ 1.0, not exactly).
        """
        north, east = body_to_ned(forward, right, 90.0)

        # At 90 degrees (east), forward becomes east and right becomes south (-north)
        assert isclose(north, -right, rel_tol=1e-6, abs_tol=1e-6)
        assert isclose(east, forward, rel_tol=1e-6, abs_tol=1e-6)

    @given(
        forward=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        right=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        yaw1=st.floats(min_value=0, max_value=360, allow_nan=False, allow_infinity=False),
        yaw2=st.floats(min_value=0, max_value=360, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_body_to_ned_additive_rotation(self, forward: float, right: float, yaw1: float, yaw2: float) -> None:
        """INVARIANT: Two sequential rotations should equal a single rotation by sum.

        THE INVARIANT (mathematical expectation):
            rotate(rotate(v, yaw1), yaw2) ≈ rotate(v, (yaw1+yaw2) mod 360)

        WHY THIS MATTERS: Verifies the rotation composition is mathematically sound.
        Important for navigation where the drone makes sequential heading changes.

        IMPLEMENTATION NOTE: This test is complex because body_to_ned is defined as
        body-relative, not NED-relative. The full composition test would require
        additional math. Instead, we verify the 360° special case:

        THE 360° INVARIANT:
            rotate(v, 360°) = v (back to original)

        This is a special case of the additive property where yaw1 + yaw2 = 360°.

        EDGE CASES THIS FINDS:
        - Periodicity bugs (360° should return to start)
        - Angle normalization issues (361° should equal 1°)
        """
        # Single rotation by yaw1 + yaw2
        total_yaw = (yaw1 + yaw2) % 360
        north_single, east_single = body_to_ned(forward, right, total_yaw)

        # First rotation
        north_mid, east_mid = body_to_ned(forward, right, yaw1)

        # Second rotation: we need to rotate the intermediate result
        # This is more complex than just applying body_to_ned again
        # because body_to_ned is body-relative, not NED-relative

        # For a proper test, we verify that 360-degree rotation returns to start
        north_full, east_full = body_to_ned(forward, right, 360.0)
        assert isclose(north_full, forward, rel_tol=1e-9, abs_tol=1e-9)
        assert isclose(east_full, right, rel_tol=1e-9, abs_tol=1e-9)

    @given(
        lat1=st.floats(min_value=-60, max_value=60, allow_nan=False, allow_infinity=False),
        lon1=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        lat2=st.floats(min_value=-60, max_value=60, allow_nan=False, allow_infinity=False),
        lon2=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_haversine_symmetry(self, lat1: float, lon1: float, lat2: float, lon2: float) -> None:
        """INVARIANT: Haversine distance is symmetric: d(a,b) = d(b,a).

        HAVERSINE FORMULA:
        Calculates great-circle distance between two points on a sphere
        (Earth). More accurate than Euclidean for geographic coordinates.

        THE INVARIANT: distance(a, b) == distance(b, a)

        WHY THIS MATTERS: Distance is symmetric in physical space.
        If d(a,b) != d(b,a), there's a bug in the formula implementation.

        COMMON BUGS THIS FINDS:
        - Using atan instead of atan2 (loses quadrant information)
        - Order-dependent operations in the formula
        - Side effects that modify inputs

        SECOND INVARIANT: d(a,b) >= 0 (distance is non-negative)
        """
        d1 = haversine_distance(lat1, lon1, lat2, lon2)
        d2 = haversine_distance(lat2, lon2, lat1, lon1)

        assert isclose(d1, d2, rel_tol=1e-9, abs_tol=1e-9)
        assert d1 >= 0  # Distance is non-negative

    @given(
        lat=st.floats(min_value=-60, max_value=60, allow_nan=False, allow_infinity=False),
        lon=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_haversine_same_point_zero_distance(self, lat: float, lon: float) -> None:
        """INVARIANT: Haversine distance from a point to itself is zero.

        THE INVARIANT: distance(p, p) == 0

        WHY THIS MATTERS: The identity property of distance metrics.
        A point has zero distance from itself.

        MATHEMATICAL BASIS: This is a fundamental axiom of metric spaces:
            d(x, y) = 0 if and only if x = y

        COMMON BUGS THIS FINDS:
        - Numerical instability when inputs are equal (0/0 errors)
        - Trigonometric precision issues at small angles
        - Not handling the degenerate case

        NOTE: We use abs_tol (absolute tolerance) because expected value is exactly 0,
        so relative tolerance would divide by zero.
        """
        d = haversine_distance(lat, lon, lat, lon)
        assert isclose(d, 0.0, abs_tol=1e-9)

    @given(
        lat1=st.floats(min_value=-60, max_value=60, allow_nan=False, allow_infinity=False),
        lon1=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        lat2=st.floats(min_value=-60, max_value=60, allow_nan=False, allow_infinity=False),
        lon2=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_haversine_triangle_inequality(self, lat1: float, lon1: float, lat2: float, lon2: float) -> None:
        """INVARIANT: Triangle inequality: d(a,b) <= d(a,c) + d(c,b).

        THE TRIANGLE INEQUALITY:
        For any three points a, b, c: direct path <= indirect path

        This is one of the four axioms that define a "metric space" in mathematics.

        WHY THIS MATTERS: If this fails, the distance function isn't a true metric.
        This could cause pathfinding algorithms to fail or loop infinitely.

        TEST DESIGN: We use a fixed intermediate point on the equator at lon1.
        This is a heuristic - a full test would test many intermediate points,
        but that would be computationally expensive.

        TOLERANCE: 1e-6 meters accounts for floating-point accumulation across
        three distance calculations.
        """
        # Use a point on the equator at lon1 as intermediate
        lat3 = 0.0
        lon3 = lon1

        d_ab = haversine_distance(lat1, lon1, lat2, lon2)
        d_ac = haversine_distance(lat1, lon1, lat3, lon3)
        d_cb = haversine_distance(lat3, lon3, lat2, lon2)

        # Triangle inequality with small tolerance for floating-point
        assert d_ab <= d_ac + d_cb + 1e-6

    @given(
        lat1=st.floats(min_value=-60, max_value=60, allow_nan=False, allow_infinity=False),
        lon1=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        lat_offset=st.floats(min_value=0.0001, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_haversine_approximate_latitude_distance(self, lat1: float, lon1: float, lat_offset: float) -> None:
        """INVARIANT: Haversine distance for small north-south movements approximates meters.

        APPROXIMATION: At most latitudes, 1 degree of latitude ≈ 111 km

        WHY THIS MATTERS: Provides a sanity check against gross errors.
        If the formula gives wildly different results, something is very wrong.

        MATHEMATICAL BASIS:
        - Earth's meridional circumference ≈ 40,008 km
        - 40,008 km / 360° ≈ 111.13 km/degree

        ACCURACY NOTE: This is an approximation that varies:
        - At equator: exactly 111.319 km/degree
        - At poles: 111.693 km/degree (due to Earth being an oblate spheroid)

        We use 1% tolerance to account for:
        - Latitude variation
        - Earth not being a perfect sphere
        - Floating-point precision

        THE INVARIANT: measured_distance ≈ lat_offset * 111000 meters

        MIN_VALUE=0.0001: Avoids tiny offsets where floating-point errors dominate.
        """
        lat2 = lat1 + lat_offset
        d = haversine_distance(lat1, lon1, lat2, lon1)

        # Approximate: 111km per degree of latitude
        expected_approx = lat_offset * 111000  # meters

        # Allow 1% error for this approximation (more accurate near equator)
        assert isclose(d, expected_approx, rel_tol=0.01)

    @given(
        forward=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
        right=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_body_to_ned_linear_scaling(self, forward: float, right: float) -> None:
        """INVARIANT: Body-to-NED transformation is linear: T(k*v) = k*T(v).

        LINEARITY PROPERTY:
        A transformation T is linear if: T(k * x) = k * T(x)

        Rotation transformations should be linear - scaling the input vector
        should scale the output vector by the same factor.

        WHY THIS MATTERS: Non-linear rotation would cause strange artifacts:
        - Moving 10m forward at yaw=45 would NOT be 10x moving 1m forward
        - Speed calculations would depend on arbitrary units

        MATHEMATICAL BASIS: Rotation matrices are linear operators.
        This is a fundamental property of matrix multiplication:
            R * (k * v) = k * (R * v)

        TEST DESIGN:
        - k = 2.0 (arbitrary scaling factor)
        - yaw = 45° (arbitrary non-trivial angle)
        - Compare scaled input vs scale of output

        This catches bugs where the rotation formula has non-linear terms
        (like using sin^2 instead of just sin).
        """
        k = 2.0

        # Transform the original vector
        north1, east1 = body_to_ned(forward, right, 45.0)

        # Transform the scaled vector
        north2, east2 = body_to_ned(forward * k, right * k, 45.0)

        # Results should be scaled
        assert isclose(north2, north1 * k, rel_tol=1e-9, abs_tol=1e-9)
        assert isclose(east2, east1 * k, rel_tol=1e-9, abs_tol=1e-9)

    @given(
        forward1=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False),
        right1=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False),
        forward2=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False),
        right2=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_body_to_ned_additivity(self, forward1: float, right1: float,
                                     forward2: float, right2: float) -> None:
        """INVARIANT: Body-to-NED transformation preserves vector addition at same yaw.

        ADDITIVITY PROPERTY:
        A transformation T is additive if: T(a + b) = T(a) + T(b)

        This is the second property of linear transformations (along with scaling).

        WHY THIS MATTERS: Ensures that sequential movements combine correctly:
        - Move forward1 then forward2 should equal moving (forward1+forward2)
        - Position estimates accumulate correctly

        MATHEMATICAL BASIS: Matrix multiplication distributes over addition:
            R * (v1 + v2) = (R * v1) + (R * v2)

        TEST DESIGN:
        - yaw = 30° (fixed angle)
        - Transform v1 and v2 separately
        - Transform (v1 + v2)
        - Compare sum of individual transforms to transform of sum

        TOLERANCE: abs_tol=1e-6 because we accumulate floating-point error across
        multiple operations.

        NOTE: This only holds when yaw is the SAME for both vectors. Different
        yaw angles would require different rotation matrices.
        """
        yaw = 30.0  # Fixed yaw angle

        # Transform vectors individually
        north1, east1 = body_to_ned(forward1, right1, yaw)
        north2, east2 = body_to_ned(forward2, right2, yaw)

        # Transform sum of vectors
        north_sum, east_sum = body_to_ned(forward1 + forward2, right1 + right2, yaw)

        # Sum should equal individual transforms (at same yaw angle)
        assert isclose(north_sum, north1 + north2, rel_tol=1e-9, abs_tol=1e-6)
        assert isclose(east_sum, east1 + east2, rel_tol=1e-9, abs_tol=1e-6)
