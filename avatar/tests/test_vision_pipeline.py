"""Tests for vision pipeline components.

VISION PIPELINE OVERVIEW
========================

The Avatar vision pipeline processes camera feeds from the drone to detect objects
and provide situational awareness for the LLM mission planner. The pipeline consists
of three main stages:

    Camera Capture → Object Detection → State String Generation
           ↓                ↓                  ↓
    GazeboCamera    MockDetector (YOLO)   Human-readable
    (or real camera)  (or real model)      scene description

1. CAMERA CAPTURE (GazeboCameraClient)
   ------------------------------------
   - Simulates or captures real camera frames from the drone
   - In SITL: Generates synthetic test patterns for testing
   - In production: Connects to ROS2/Gazebo camera topics or real camera
   - Outputs: PIL Image or NumPy array (H, W, 3) in RGB format

2. OBJECT DETECTION (MockDetector / YOLODetector)
   ----------------------------------------------
   - Processes frames to detect objects (people, vehicles, obstacles)
   - MockDetector: Deterministic test implementation for unit tests
   - YOLODetector (production): Real YOLOv8-nano model running on CPU
   - Outputs: List of Detection objects with:
       * label: str (e.g., "person", "vehicle")
       * confidence: float (0-1, detection certainty)
       * bbox: [x, y, width, height] in normalized 0-1 coordinates
       * class_id: int (YOLO class index)

3. STATE STRING GENERATION (state_string.py)
   ------------------------------------------
   - Converts detection list to natural language description
   - Used by LLM to understand surroundings without processing raw images
   - Includes object counts, locations (left/center/right), confidence levels
   - Example output: "3 people detected (center), 1 vehicle detected (left)"

MOCK DETECTION VS REAL YOLO
===========================

MockDetector (Testing):
  - Deterministic: Same input always produces same output
  - Configurable: Set confidence thresholds, detection count
  - Fast: No model inference overhead
  - Used for: Unit tests, SITL development, CI/CD pipelines

YOLODetector (Production):
  - Real inference: Runs YOLOv8-nano ONNX model
  - Variable latency: ~50-200ms per frame on CPU
  - Real accuracy: Subject to lighting, occlusion, distance
  - Used for: Real hardware flights, validation tests

COORDINATE SYSTEM
=================

Bounding Box Format [x, y, width, height] - all normalized 0-1:

    (0,0) ------------------------ (1,0)
          |  x,y (top-left)        |
          |     ┌────────┐         |
          |     │ Object │ height  |
          |     └────────┘         |
          |        width           |
          |                        |
    (0,1) ------------------------ (1,1)

Location Mapping (horizontal field of view):
  - x_center < 0.33  → "left"     (left third of frame)
  - 0.33 < x_center < 0.67 → "center" (middle third)
  - x_center > 0.67  → "right"    (right third)

This coordinate system is camera-centric, not world-centric. The LLM uses
this to understand relative positioning for navigation decisions.
"""

import numpy as np
from PIL import Image

import pytest

from avatar.vision.mock_detector import MockDetector, Detection
from avatar.vision.state_string import (
    generate_state_string,
    generate_detailed_state,
    _pluralize,
    _bbox_to_location,
)
from avatar.vision.gazebo_camera_client import GazeboCameraClient


# =============================================================================
# MOCK DETECTOR TESTS
# =============================================================================
# These tests validate the MockDetector which provides deterministic,
# controlled object detection for testing the vision pipeline without
# requiring actual YOLO model inference or camera hardware.


class TestMockDetector:
    """Tests for MockDetector class.

    MockDetector is a test double that simulates YOLO detection behavior
    with deterministic, configurable outputs. This allows reliable unit
    testing and SITL development without model dependencies.
    """

    def test_mock_detector_initialization(self):
        """Test MockDetector initializes with correct defaults.

        Validates that the detector starts with sensible defaults for testing:
        - confidence_threshold=0.5 (filters low-confidence detections)
        - num_detections=3 (produces 3 mock objects per frame)
        - deterministic=True (same input = same output for reproducibility)
        """
        detector = MockDetector()

        assert detector.confidence_threshold == 0.5
        assert detector.num_detections == 3
        assert detector.deterministic is True
        assert detector._detection_count == 0

    def test_mock_detector_custom_config(self):
        """Test MockDetector with custom configuration.

        Verifies that all parameters can be customized for different test
        scenarios, such as high-precision mode or varying detection counts.
        """
        detector = MockDetector(
            confidence_threshold=0.7,
            num_detections=5,
            deterministic=False
        )

        assert detector.confidence_threshold == 0.7
        assert detector.num_detections == 5
        assert detector.deterministic is False

    def test_mock_detector_detect_returns_detections(self, sample_frame):
        """Test that detect returns a list of Detection objects.

        Validates the core contract: detect() returns a list of Detection
        dataclass instances, each containing label, confidence, bbox, class_id.
        This matches the interface expected by the real YOLODetector.
        """
        detector = MockDetector()
        detections = detector.detect(sample_frame)

        assert isinstance(detections, list)
        assert all(isinstance(d, Detection) for d in detections)

    def test_mock_detector_detect_numpy_array(self, sample_frame):
        """Test detection on numpy array input.

        Verifies pipeline works with raw camera frames as NumPy arrays
        (H, W, 3) in uint8 format, which is the typical output from
        OpenCV or Gazebo camera subscribers.
        """
        detector = MockDetector()
        detections = detector.detect(sample_frame)

        assert len(detections) > 0

    def test_mock_detector_detect_pil_image(self, sample_pil_image):
        """Test detection on PIL Image input.

        Validates that the detector also accepts PIL Image objects,
        which are easier to manipulate for testing and used by some
        camera interfaces.
        """
        detector = MockDetector()
        detections = detector.detect(sample_pil_image)

        assert len(detections) > 0

    def test_mock_detector_deterministic_mode(self, sample_frame):
        """Test that deterministic mode produces consistent results.

        CRITICAL TEST: Determinism is essential for reproducible tests.
        In deterministic mode, the same input frame must always produce
        the same detections, labels, and confidence scores. This allows
        assertions like "expect exactly 3 people detected" to be reliable.

        Real YOLO is NOT deterministic (floating point variations), so
        this property is unique to the mock and valuable for testing.
        """
        detector = MockDetector(deterministic=True)

        detections1 = detector.detect(sample_frame)
        detections2 = detector.detect(sample_frame)

        # Same frame should produce same detections
        assert len(detections1) == len(detections2)

        # Detections should have same labels
        labels1 = [d.label for d in detections1]
        labels2 = [d.label for d in detections2]
        assert labels1 == labels2

    def test_mock_detector_non_deterministic_mode(self, sample_frame):
        """Test that non-deterministic mode varies results.

        Non-deterministic mode simulates real-world variability where
        detection counts and confidence scores fluctuate between frames.
        Useful for testing error handling and statistical aggregation.
        """
        detector = MockDetector(deterministic=False, num_detections=3)

        all_detections = []
        for _ in range(10):
            detector.reset()
            detections = detector.detect(sample_frame)
            all_detections.append(len(detections))

        # Results may vary (though not guaranteed to be different)
        # At least verify it runs without error
        assert len(all_detections) == 10

    def test_mock_detector_confidence_threshold(self):
        """Test that confidence threshold filters detections.

        Validates the filtering logic: when a high confidence threshold
        is set, only detections meeting that threshold should be returned.
        This mirrors real YOLO behavior where low-confidence predictions
        are suppressed to reduce false positives.
        """
        detector = MockDetector(confidence_threshold=0.9, num_detections=3)

        # Create a frame that will produce specific confidence
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        detections = detector.detect(frame)

        # All returned detections should meet threshold
        for det in detections:
            assert det.confidence >= detector.confidence_threshold

    def test_mock_detector_detection_properties(self, sample_frame):
        """Test that Detection objects have correct properties.

        Validates the Detection dataclass contract:
        - label: string class name
        - confidence: float in [0, 1]
        - bbox: 4 normalized floats [x, y, w, h] all in [0, 1]
        - class_id: integer class index

        These properties must match what the real YOLODetector produces.
        """
        detector = MockDetector()
        detections = detector.detect(sample_frame)

        for det in detections:
            assert hasattr(det, 'label')
            assert hasattr(det, 'confidence')
            assert hasattr(det, 'bbox')
            assert hasattr(det, 'class_id')

            # Confidence should be between 0 and 1
            assert 0 <= det.confidence <= 1

            # BBox should be 4 values normalized 0-1
            assert len(det.bbox) == 4
            for val in det.bbox:
                assert 0 <= val <= 1

    def test_mock_detector_class_names(self):
        """Test that class_names property returns expected classes.

        Validates the set of detectable objects matches the COCO-derived
        classes used by YOLOv8: person, vehicle, and generic object.
        """
        detector = MockDetector()

        class_names = detector.class_names

        assert "person" in class_names
        assert "vehicle" in class_names
        assert "object" in class_names

    def test_mock_detector_detect_with_labels_filter(self, sample_frame):
        """Test detection with label filtering.

        Validates the detect_with_labels() method which filters results
        to only return detections of specific types. This is used by
        mission planners to focus on relevant objects (e.g., "only look
        for people during search and rescue").
        """
        detector = MockDetector()
        detections = detector.detect_with_labels(
            sample_frame,
            target_labels=["person"]
        )

        # All detections should be 'person'
        for det in detections:
            assert det.label == "person"

    def test_mock_detector_detect_with_labels_no_filter(self, sample_frame):
        """Test detection without label filter returns all.

        Without a target_labels filter, all detections should be returned
        regardless of class, matching the behavior of detect().
        """
        detector = MockDetector()
        all_detections = detector.detect_with_labels(sample_frame)

        # Should return all detections
        assert len(all_detections) > 0

    def test_mock_detector_reset(self, sample_frame):
        """Test that reset clears detection count.

        The internal detection counter tracks how many frames have been
        processed. Resetting allows deterministic tests to start fresh,
        ensuring frame sequence doesn't affect results.
        """
        detector = MockDetector(deterministic=False)

        _ = detector.detect(sample_frame)
        assert detector._detection_count == 1

        detector.reset()
        assert detector._detection_count == 0

    def test_mock_detector_to_dict(self, sample_frame):
        """Test Detection.to_dict() method.

        Validates serialization to dictionary format, used for:
        - JSON logging of detection results
        - State string generation
        - MCP tool responses to the LLM
        """
        detector = MockDetector()
        detections = detector.detect(sample_frame)

        for det in detections:
            det_dict = det.to_dict()

            assert isinstance(det_dict, dict)
            assert "label" in det_dict
            assert "confidence" in det_dict
            assert "bbox" in det_dict
            assert "class_id" in det_dict

    def test_mock_detector_repr(self):
        """Test string representation of MockDetector.

        Good for debugging - repr should show key configuration parameters
        so developers can quickly identify detector settings in logs.
        """
        detector = MockDetector(confidence_threshold=0.6, num_detections=2)

        repr_str = repr(detector)

        assert "MockDetector" in repr_str
        assert "0.6" in repr_str
        assert "2" in repr_str


# =============================================================================
# STATE STRING GENERATION TESTS
# =============================================================================
# These tests validate the conversion of detection lists to natural language
# descriptions for the LLM. The state string provides situational awareness
# without requiring the LLM to process raw images or detection tensors.


class TestStateStringGeneration:
    """Tests for state string generation.

    State strings convert structured detection data into natural language
    that the LLM can easily understand for mission planning. For example:

    Input detections:  [
        {"label": "person", "confidence": 0.9, "bbox": [0.4, 0.2, 0.1, 0.2]},
        {"label": "vehicle", "confidence": 0.8, "bbox": [0.7, 0.3, 0.2, 0.15]}
    ]

    Output: "1 person detected (center, confidence: 90%), 1 vehicle detected (right)"

    This allows the LLM to make navigation decisions based on object
    positions ("avoid the vehicle on the right", "approach the person in center").
    """

    def test_generate_state_string_empty(self):
        """Test empty detection list returns clear message.

        When no objects are detected, the LLM should receive explicit
        confirmation that the area is clear, not an empty string.
        """
        result = generate_state_string([])

        assert result == "Area clear"

    def test_generate_state_string_single_detection(self):
        """Test single detection string.

        Validates correct formatting for a single object detection,
        including proper singular form ("1 person" not "1 people").
        """
        detections = [{"label": "person", "confidence": 0.85}]

        result = generate_state_string(detections)

        assert "1 person" in result
        assert "detected" in result

    def test_generate_state_string_multiple_same_type(self):
        """Test multiple detections of same type.

        Validates grouping of multiple objects of the same class,
        with correct pluralization ("3 people" not "3 persons").
        """
        detections = [
            {"label": "person", "confidence": 0.9},
            {"label": "person", "confidence": 0.8},
            {"label": "person", "confidence": 0.7},
        ]

        result = generate_state_string(detections)

        assert "3 people" in result  # Pluralized
        assert "detected" in result

    def test_generate_state_string_multiple_types(self):
        """Test multiple detection types.

        Validates that different object types are reported separately,
        allowing the LLM to understand the full scene composition.
        """
        detections = [
            {"label": "person"},
            {"label": "person"},
            {"label": "vehicle"},
        ]

        result = generate_state_string(detections)

        assert "2 people" in result
        assert "1 vehicle" in result
        assert "detected" in result

    def test_generate_state_string_with_confidence(self):
        """Test state string includes confidence when requested.

        With include_confidence=True, the average confidence for each
        object type is reported. This helps the LLM assess detection
        reliability (low confidence = might be false positive).
        """
        detections = [
            {"label": "person", "confidence": 0.9},
            {"label": "person", "confidence": 0.8},
        ]

        result = generate_state_string(detections, include_confidence=True)

        assert "confidence" in result.lower()
        # Average of 0.9 and 0.8 is 0.85 = 85%
        assert "85%" in result

    def test_generate_state_string_with_location(self):
        """Test state string includes location when requested.

        With include_location=True, objects are annotated with their
        position in the frame: left, center, or right. This spatial
        information is crucial for navigation commands ("land near the
        vehicle on the left").

        Location is determined from bbox x_center (see _bbox_to_location).
        """
        detections = [
            {"label": "person", "bbox": [0.1, 0.2, 0.1, 0.1]},  # Left
            {"label": "person", "bbox": [0.5, 0.2, 0.1, 0.1]},  # Center
        ]

        result = generate_state_string(detections, include_location=True)

        # Should include location info
        assert "left" in result.lower() or "center" in result.lower()

    def test_generate_state_string_custom_empty_message(self):
        """Test custom empty message.

        Allows mission-specific terminology (e.g., "No targets found"
        for search missions vs "Area clear" for security patrols).
        """
        result = generate_state_string([], empty_message="No objects found")

        assert result == "No objects found"

    def test_generate_state_string_detection_objects(self, sample_detection):
        """Test state string with Detection objects (not dicts).

        Validates that the function accepts both raw dictionaries (from
        JSON) and Detection dataclass objects (from detector output).
        """
        detections = [sample_detection]

        result = generate_state_string(detections)

        assert "person" in result

    def test_bbox_to_location_left(self):
        """Test bbox location detection - left.

        COORDINATE TRANSFORMATION TEST:
        Converts normalized bbox coordinates to spatial location.

        For bbox [x, y, width, height]:
            x_center = x + width/2

        x_center < 0.33 → "left" (left third of camera view)

        Test case: x=0.1, w=0.1 → x_center=0.15 → "left"
        """
        # x_center = 0.1 + 0.1/2 = 0.15 (< 0.33)
        bbox = [0.1, 0.2, 0.1, 0.1]

        result = _bbox_to_location(bbox)

        assert result == "left"

    def test_bbox_to_location_center(self):
        """Test bbox location detection - center.

        COORDINATE TRANSFORMATION TEST:
        Center region spans x_center between 0.33 and 0.67.

        Test case: x=0.4, w=0.2 → x_center=0.5 → "center"
        """
        # x_center = 0.4 + 0.2/2 = 0.5 (between 0.33 and 0.67)
        bbox = [0.4, 0.2, 0.2, 0.1]

        result = _bbox_to_location(bbox)

        assert result == "center"

    def test_bbox_to_location_right(self):
        """Test bbox location detection - right.

        COORDINATE TRANSFORMATION TEST:
        Right region is x_center > 0.67 (right third of camera view).

        Test case: x=0.7, w=0.1 → x_center=0.75 → "right"
        """
        # x_center = 0.7 + 0.1/2 = 0.75 (> 0.67)
        bbox = [0.7, 0.2, 0.1, 0.1]

        result = _bbox_to_location(bbox)

        assert result == "right"

    def test_bbox_to_location_empty(self):
        """Test bbox location with empty bbox.

        Graceful handling of missing/empty bounding box data.
        """
        result = _bbox_to_location([])

        assert result == "unknown"

    def test_pluralize_singular(self):
        """Test pluralize returns singular for count 1."""
        assert _pluralize("person", 1) == "person"
        assert _pluralize("vehicle", 1) == "vehicle"

    def test_pluralize_regular(self):
        """Test regular pluralization.

        Standard plural rules: add 's' for most words.
        """
        assert _pluralize("vehicle", 2) == "vehicles"
        assert _pluralize("object", 3) == "objects"

    def test_pluralize_irregular_person(self):
        """Test irregular plural - person -> people.

        English irregular plural handling for natural-sounding output.
        """
        assert _pluralize("person", 2) == "people"

    def test_pluralize_irregular_child(self):
        """Test irregular plural - child -> children."""
        assert _pluralize("child", 2) == "children"

    def test_pluralize_ending_y(self):
        """Test plural for words ending in y.

        Words ending in consonant + y → change y to ies.
        """
        assert _pluralize("city", 2) == "cities"

    def test_pluralize_ending_s(self):
        """Test plural for words ending in s.

        Words ending in s → add es.
        """
        assert _pluralize("bus", 2) == "buses"

    def test_pluralize_ending_ch(self):
        """Test plural for words ending in ch.

        Words ending in ch → add es.
        """
        assert _pluralize("match", 2) == "matches"


class TestDetailedStateGeneration:
    """Tests for detailed state string generation.

    Detailed state provides comprehensive scene description including:
    - Total object count
    - Individual object details (class, confidence, location)
    - Pixel coordinates when frame dimensions are known

    Used when the LLM needs full situational awareness for complex missions.
    """

    def test_generate_detailed_state_empty(self):
        """Test detailed state with empty detections."""
        result = generate_detailed_state([])

        assert "no objects detected" in result.lower()

    def test_generate_detailed_state_single(self, sample_detection):
        """Test detailed state with single detection."""
        result = generate_detailed_state([sample_detection])

        assert "1 object" in result
        assert "person" in result

    def test_generate_detailed_state_multiple(self):
        """Test detailed state with multiple detections.

        Validates detailed formatting of multiple objects with full
        metadata including class labels, confidence scores, and
        spatial positions.
        """
        detections = [
            {"label": "person", "confidence": 0.9, "bbox": [0.1, 0.2, 0.1, 0.1]},
            {"label": "vehicle", "confidence": 0.8, "bbox": [0.5, 0.3, 0.2, 0.15]},
        ]

        result = generate_detailed_state(detections)

        assert "2 objects" in result
        assert "person" in result
        assert "vehicle" in result

    def test_generate_detailed_state_with_frame_shape(self, sample_detection):
        """Test detailed state includes pixel coordinates when frame_shape provided.

        COORDINATE TRANSFORMATION TEST:
        When frame dimensions are provided, normalized bbox coordinates
        are converted to pixel coordinates for easier interpretation.

        Conversion: pixel_x = normalized_x * frame_width

        Example: bbox x=0.1 on 640px wide frame → 64px
        """
        result = generate_detailed_state(
            [sample_detection],
            frame_shape=(480, 640)
        )

        # Should include pixel coordinates
        assert "px" in result


# =============================================================================
# GAZEBO CAMERA CLIENT TESTS
# =============================================================================
# These tests validate the camera interface that captures frames from
# Gazebo simulation (or ROS2 topics in production). The client provides
# a unified interface for frame capture in both SITL and real flights.


class TestGazeboCameraClient:
    """Tests for GazeboCameraClient.

    The camera client abstracts the video source, providing consistent
    PIL Image or NumPy array outputs regardless of the underlying camera
    implementation (Gazebo simulation camera, ROS2 image topic, or real
    camera hardware).

    In SITL mode, it generates synthetic test patterns for repeatable
    testing without requiring a running Gazebo instance.
    """

    def test_initialization_defaults(self):
        """Test client initializes with default parameters.

        Default resolution of 640x480 is chosen for:
        - Balance between detection accuracy and processing speed
        - YOLOv8-nano optimal input size
        - Network bandwidth considerations for telemetry
        """
        client = GazeboCameraClient()

        assert client.width == 640
        assert client.height == 480
        assert client.topic == "/drone/camera/image_raw"
        assert client.connected is True

    def test_initialization_custom(self):
        """Test client with custom parameters.

        Supports different resolutions for different mission needs:
        - 640x480: Standard detection, fast processing
        - 1280x720: Higher accuracy, slower processing
        - Custom topics for multi-camera setups
        """
        client = GazeboCameraClient(
            width=1280,
            height=720,
            topic="/custom/camera"
        )

        assert client.width == 1280
        assert client.height == 720
        assert client.topic == "/custom/camera"

    def test_capture_frame(self):
        """Test capturing a frame returns PIL Image.

        PIL Image format is used for:
        - Easy format conversion (RGB, BGR, grayscale)
        - Direct compatibility with YOLO preprocessing
        - Simple resizing and cropping operations
        """
        client = GazeboCameraClient()

        frame = client.capture_frame()

        assert isinstance(frame, Image.Image)
        assert frame.size == (640, 480)

    def test_capture_frame_as_numpy(self):
        """Test capturing frame as numpy array.

        NumPy format is used for:
        - Direct OpenCV integration
        - Fast array operations
        - Computer vision preprocessing (blur, threshold, etc.)
        """
        client = GazeboCameraClient()

        frame = client.capture_frame_as_numpy()

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (480, 640, 3)

    def test_capture_frame_deterministic_pattern(self):
        """Test that frames have deterministic gradient pattern.

        In test/SITL mode, each frame has a subtle gradient pattern
        that changes with frame_count. This allows vision tests to
        have slightly different inputs per frame while remaining
        deterministic and reproducible.
        """
        client = GazeboCameraClient()

        frame1 = client.capture_frame()
        frame2 = client.capture_frame()

        # Frames should be different (frame_count affects pattern)
        arr1 = np.array(frame1)
        arr2 = np.array(frame2)

        # They should be different due to frame counter
        assert not np.array_equal(arr1, arr2)

    def test_disconnect(self):
        """Test disconnecting from camera.

        Proper cleanup is essential for:
        - Releasing ROS2 topic subscriptions
        - Closing camera hardware handles
        - Preventing memory leaks in long-running missions
        """
        client = GazeboCameraClient()

        client.disconnect()

        assert client.connected is False

        # Capturing after disconnect should raise
        with pytest.raises(RuntimeError):
            client.capture_frame()

    def test_repr(self):
        """Test string representation."""
        client = GazeboCameraClient()

        repr_str = repr(client)

        assert "GazeboCameraClient" in repr_str
        assert "640" in repr_str
        assert "480" in repr_str


# =============================================================================
# INTEGRATION TESTS
# =============================================================================
# These tests validate the complete vision pipeline from camera capture
# through detection to state string generation, ensuring all components
# work together correctly.


class TestVisionPipelineIntegration:
    """Integration tests for complete vision pipeline.

    These tests exercise the full data flow:
        Camera → Frame → Detector → Detections → State String

    They validate that component interfaces are compatible and the
    end-to-end pipeline produces sensible output for LLM consumption.
    """

    def test_full_pipeline(self):
        """Test complete pipeline: capture -> detect -> state string.

        FULL PIPELINE INTEGRATION TEST:
        1. Capture frame from simulated camera
        2. Run mock object detection
        3. Generate human-readable state description

        This mirrors the production flow that runs continuously during
        flight, providing the LLM with scene understanding at ~1Hz.
        """
        # 1. Capture frame
        camera = GazeboCameraClient()
        frame = camera.capture_frame_as_numpy()

        # 2. Run detection
        detector = MockDetector(deterministic=True)
        detections = detector.detect(frame)

        # 3. Generate state string
        state_string = generate_state_string(detections)

        # Verify complete pipeline worked
        assert len(detections) > 0
        assert "detected" in state_string.lower()

    def test_pipeline_with_filtered_detections(self):
        """Test pipeline with detection filtering.

        Validates mission-specific filtering where only certain
        object types are relevant. Example: search-and-rescue mission
        only cares about "person" detections, ignoring vehicles.
        """
        camera = GazeboCameraClient()
        frame = camera.capture_frame_as_numpy()

        detector = MockDetector()
        detections = detector.detect_with_labels(frame, target_labels=["person"])

        state = generate_state_string(detections)

        # All should be persons
        for det in detections:
            assert det.label == "person"
