"""Tests for vision pipeline components.

Tests the mock detector and state string generation for the vision pipeline.
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


class TestMockDetector:
    """Tests for MockDetector class."""

    def test_mock_detector_initialization(self):
        """Test MockDetector initializes with correct defaults."""
        detector = MockDetector()

        assert detector.confidence_threshold == 0.5
        assert detector.num_detections == 3
        assert detector.deterministic is True
        assert detector._detection_count == 0

    def test_mock_detector_custom_config(self):
        """Test MockDetector with custom configuration."""
        detector = MockDetector(
            confidence_threshold=0.7,
            num_detections=5,
            deterministic=False
        )

        assert detector.confidence_threshold == 0.7
        assert detector.num_detections == 5
        assert detector.deterministic is False

    def test_mock_detector_detect_returns_detections(self, sample_frame):
        """Test that detect returns a list of Detection objects."""
        detector = MockDetector()
        detections = detector.detect(sample_frame)

        assert isinstance(detections, list)
        assert all(isinstance(d, Detection) for d in detections)

    def test_mock_detector_detect_numpy_array(self, sample_frame):
        """Test detection on numpy array input."""
        detector = MockDetector()
        detections = detector.detect(sample_frame)

        assert len(detections) > 0

    def test_mock_detector_detect_pil_image(self, sample_pil_image):
        """Test detection on PIL Image input."""
        detector = MockDetector()
        detections = detector.detect(sample_pil_image)

        assert len(detections) > 0

    def test_mock_detector_deterministic_mode(self, sample_frame):
        """Test that deterministic mode produces consistent results."""
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
        """Test that non-deterministic mode varies results."""
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
        """Test that confidence threshold filters detections."""
        detector = MockDetector(confidence_threshold=0.9, num_detections=3)

        # Create a frame that will produce specific confidence
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        detections = detector.detect(frame)

        # All returned detections should meet threshold
        for det in detections:
            assert det.confidence >= detector.confidence_threshold

    def test_mock_detector_detection_properties(self, sample_frame):
        """Test that Detection objects have correct properties."""
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
        """Test that class_names property returns expected classes."""
        detector = MockDetector()

        class_names = detector.class_names

        assert "person" in class_names
        assert "vehicle" in class_names
        assert "object" in class_names

    def test_mock_detector_detect_with_labels_filter(self, sample_frame):
        """Test detection with label filtering."""
        detector = MockDetector()
        detections = detector.detect_with_labels(
            sample_frame,
            target_labels=["person"]
        )

        # All detections should be 'person'
        for det in detections:
            assert det.label == "person"

    def test_mock_detector_detect_with_labels_no_filter(self, sample_frame):
        """Test detection without label filter returns all."""
        detector = MockDetector()
        all_detections = detector.detect_with_labels(sample_frame)

        # Should return all detections
        assert len(all_detections) > 0

    def test_mock_detector_reset(self, sample_frame):
        """Test that reset clears detection count."""
        detector = MockDetector(deterministic=False)

        _ = detector.detect(sample_frame)
        assert detector._detection_count == 1

        detector.reset()
        assert detector._detection_count == 0

    def test_mock_detector_to_dict(self, sample_frame):
        """Test Detection.to_dict() method."""
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
        """Test string representation of MockDetector."""
        detector = MockDetector(confidence_threshold=0.6, num_detections=2)

        repr_str = repr(detector)

        assert "MockDetector" in repr_str
        assert "0.6" in repr_str
        assert "2" in repr_str


# =============================================================================
# STATE STRING GENERATION TESTS
# =============================================================================


class TestStateStringGeneration:
    """Tests for state string generation."""

    def test_generate_state_string_empty(self):
        """Test empty detection list returns clear message."""
        result = generate_state_string([])

        assert result == "Area clear"

    def test_generate_state_string_single_detection(self):
        """Test single detection string."""
        detections = [{"label": "person", "confidence": 0.85}]

        result = generate_state_string(detections)

        assert "1 person" in result
        assert "detected" in result

    def test_generate_state_string_multiple_same_type(self):
        """Test multiple detections of same type."""
        detections = [
            {"label": "person", "confidence": 0.9},
            {"label": "person", "confidence": 0.8},
            {"label": "person", "confidence": 0.7},
        ]

        result = generate_state_string(detections)

        assert "3 people" in result  # Pluralized
        assert "detected" in result

    def test_generate_state_string_multiple_types(self):
        """Test multiple detection types."""
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
        """Test state string includes confidence when requested."""
        detections = [
            {"label": "person", "confidence": 0.9},
            {"label": "person", "confidence": 0.8},
        ]

        result = generate_state_string(detections, include_confidence=True)

        assert "confidence" in result.lower()
        # Average of 0.9 and 0.8 is 0.85 = 85%
        assert "85%" in result

    def test_generate_state_string_with_location(self):
        """Test state string includes location when requested."""
        detections = [
            {"label": "person", "bbox": [0.1, 0.2, 0.1, 0.1]},  # Left
            {"label": "person", "bbox": [0.5, 0.2, 0.1, 0.1]},  # Center
        ]

        result = generate_state_string(detections, include_location=True)

        # Should include location info
        assert "left" in result.lower() or "center" in result.lower()

    def test_generate_state_string_custom_empty_message(self):
        """Test custom empty message."""
        result = generate_state_string([], empty_message="No objects found")

        assert result == "No objects found"

    def test_generate_state_string_detection_objects(self, sample_detection):
        """Test state string with Detection objects (not dicts)."""
        detections = [sample_detection]

        result = generate_state_string(detections)

        assert "person" in result

    def test_bbox_to_location_left(self):
        """Test bbox location detection - left."""
        # x_center = 0.1 + 0.1/2 = 0.15 (< 0.33)
        bbox = [0.1, 0.2, 0.1, 0.1]

        result = _bbox_to_location(bbox)

        assert result == "left"

    def test_bbox_to_location_center(self):
        """Test bbox location detection - center."""
        # x_center = 0.4 + 0.2/2 = 0.5 (between 0.33 and 0.67)
        bbox = [0.4, 0.2, 0.2, 0.1]

        result = _bbox_to_location(bbox)

        assert result == "center"

    def test_bbox_to_location_right(self):
        """Test bbox location detection - right."""
        # x_center = 0.7 + 0.1/2 = 0.75 (> 0.67)
        bbox = [0.7, 0.2, 0.1, 0.1]

        result = _bbox_to_location(bbox)

        assert result == "right"

    def test_bbox_to_location_empty(self):
        """Test bbox location with empty bbox."""
        result = _bbox_to_location([])

        assert result == "unknown"

    def test_pluralize_singular(self):
        """Test pluralize returns singular for count 1."""
        assert _pluralize("person", 1) == "person"
        assert _pluralize("vehicle", 1) == "vehicle"

    def test_pluralize_regular(self):
        """Test regular pluralization."""
        assert _pluralize("vehicle", 2) == "vehicles"
        assert _pluralize("object", 3) == "objects"

    def test_pluralize_irregular_person(self):
        """Test irregular plural - person -> people."""
        assert _pluralize("person", 2) == "people"

    def test_pluralize_irregular_child(self):
        """Test irregular plural - child -> children."""
        assert _pluralize("child", 2) == "children"

    def test_pluralize_ending_y(self):
        """Test plural for words ending in y."""
        assert _pluralize("city", 2) == "cities"

    def test_pluralize_ending_s(self):
        """Test plural for words ending in s."""
        assert _pluralize("bus", 2) == "buses"

    def test_pluralize_ending_ch(self):
        """Test plural for words ending in ch."""
        assert _pluralize("match", 2) == "matches"


class TestDetailedStateGeneration:
    """Tests for detailed state string generation."""

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
        """Test detailed state with multiple detections."""
        detections = [
            {"label": "person", "confidence": 0.9, "bbox": [0.1, 0.2, 0.1, 0.1]},
            {"label": "vehicle", "confidence": 0.8, "bbox": [0.5, 0.3, 0.2, 0.15]},
        ]

        result = generate_detailed_state(detections)

        assert "2 objects" in result
        assert "person" in result
        assert "vehicle" in result

    def test_generate_detailed_state_with_frame_shape(self, sample_detection):
        """Test detailed state includes pixel coordinates when frame_shape provided."""
        result = generate_detailed_state(
            [sample_detection],
            frame_shape=(480, 640)
        )

        # Should include pixel coordinates
        assert "px" in result


# =============================================================================
# GAZEBO CAMERA CLIENT TESTS
# =============================================================================


class TestGazeboCameraClient:
    """Tests for GazeboCameraClient."""

    def test_initialization_defaults(self):
        """Test client initializes with default parameters."""
        client = GazeboCameraClient()

        assert client.width == 640
        assert client.height == 480
        assert client.topic == "/drone/camera/image_raw"
        assert client.connected is True

    def test_initialization_custom(self):
        """Test client with custom parameters."""
        client = GazeboCameraClient(
            width=1280,
            height=720,
            topic="/custom/camera"
        )

        assert client.width == 1280
        assert client.height == 720
        assert client.topic == "/custom/camera"

    def test_capture_frame(self):
        """Test capturing a frame returns PIL Image."""
        client = GazeboCameraClient()

        frame = client.capture_frame()

        assert isinstance(frame, Image.Image)
        assert frame.size == (640, 480)

    def test_capture_frame_as_numpy(self):
        """Test capturing frame as numpy array."""
        client = GazeboCameraClient()

        frame = client.capture_frame_as_numpy()

        assert isinstance(frame, np.ndarray)
        assert frame.shape == (480, 640, 3)

    def test_capture_frame_deterministic_pattern(self):
        """Test that frames have deterministic gradient pattern."""
        client = GazeboCameraClient()

        frame1 = client.capture_frame()
        frame2 = client.capture_frame()

        # Frames should be different (frame_count affects pattern)
        arr1 = np.array(frame1)
        arr2 = np.array(frame2)

        # They should be different due to frame counter
        assert not np.array_equal(arr1, arr2)

    def test_disconnect(self):
        """Test disconnecting from camera."""
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


class TestVisionPipelineIntegration:
    """Integration tests for complete vision pipeline."""

    def test_full_pipeline(self):
        """Test complete pipeline: capture -> detect -> state string."""
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
        """Test pipeline with detection filtering."""
        camera = GazeboCameraClient()
        frame = camera.capture_frame_as_numpy()

        detector = MockDetector()
        detections = detector.detect_with_labels(frame, target_labels=["person"])

        state = generate_state_string(detections)

        # All should be persons
        for det in detections:
            assert det.label == "person"
