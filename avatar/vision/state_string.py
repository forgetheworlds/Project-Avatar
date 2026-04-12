"""State string generation for vision pipeline.

Converts detection results into human-readable state strings
for use in prompts and status reporting.
"""

from typing import List, Union, Dict, Any, Optional, Tuple
from collections import Counter


def generate_state_string(
    detections: List[Union[Dict[str, Any], Any]],
    include_confidence: bool = False,
    include_location: bool = False,
    empty_message: str = "Area clear"
) -> str:
    """Generate a human-readable state string from detections.

    Takes a list of detections and produces a natural language
    description suitable for status reporting or LLM prompts.

    Args:
        detections: List of detection objects or dictionaries.
            Each detection should have a 'label' attribute/key.
            Optionally 'confidence' and 'bbox' for extended output.
        include_confidence: Include confidence scores in output.
        include_location: Include location hints (left/center/right).
        empty_message: Message to return when no detections.

    Returns:
        Human-readable string describing detected objects.

    Example:
        >>> detections = [{"label": "person"}, {"label": "person"}, {"label": "vehicle"}]
        >>> generate_state_string(detections)
        '2 people and 1 vehicle detected'

        >>> generate_state_string([])
        'Area clear'
    """
    if not detections:
        return empty_message

    # Extract labels from detections (handle both dict and object formats)
    labels = []
    confidences = []
    locations = []

    for det in detections:
        if isinstance(det, dict):
            labels.append(det.get("label", "unknown"))
            if include_confidence and "confidence" in det:
                confidences.append(det["confidence"])
            if include_location and "bbox" in det:
                locations.append(_bbox_to_location(det["bbox"]))
        else:
            # Assume object with attributes
            labels.append(getattr(det, "label", "unknown"))
            if include_confidence:
                confidences.append(getattr(det, "confidence", None))
            if include_location:
                bbox = getattr(det, "bbox", None)
                if bbox:
                    locations.append(_bbox_to_location(bbox))

    # Count occurrences of each label
    label_counts = Counter(labels)

    # Build the state string
    if len(label_counts) == 1:
        # Single object type
        label = list(label_counts.keys())[0]
        count = label_counts[label]
        return _format_single_type(label, count, confidences, locations,
                                   include_confidence, include_location)
    else:
        # Multiple object types
        return _format_multiple_types(label_counts, include_confidence,
                                     include_location)


def _format_single_type(
    label: str,
    count: int,
    confidences: List[float],
    locations: List[str],
    include_confidence: bool,
    include_location: bool
) -> str:
    """Format detection string for single object type.

    Args:
        label: Object label.
        count: Number of objects.
        confidences: List of confidence scores.
        locations: List of location strings.
        include_confidence: Whether to include confidence.
        include_location: Whether to include location.

    Returns:
        Formatted string for single object type.
    """
    # Pluralize the label
    plural_label = _pluralize(label, count)

    base = f"{count} {plural_label} detected"

    extras = []

    if include_confidence and confidences:
        avg_conf = sum(c for c in confidences if c) / len(confidences)
        if avg_conf > 0:
            extras.append(f"avg confidence {avg_conf:.0%}")

    if include_location and locations:
        unique_locations = list(set(locations))
        if len(unique_locations) == 1:
            extras.append(f"located {unique_locations[0]}")
        else:
            extras.append(f"at {', '.join(unique_locations)}")

    if extras:
        return f"{base} ({'; '.join(extras)})"
    return base


def _format_multiple_types(
    label_counts: Counter[str],
    include_confidence: bool,
    include_location: bool
) -> str:
    """Format detection string for multiple object types.

    Args:
        label_counts: Counter of label occurrences.
        include_confidence: Whether to include confidence.
        include_location: Whether to include location.

    Returns:
        Formatted string for multiple object types.
    """
    total = sum(label_counts.values())

    # Build parts for each object type
    parts = []
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        plural_label = _pluralize(label, count)
        parts.append(f"{count} {plural_label}")

    # Combine with "and" for the last item
    if len(parts) == 2:
        objects_str = f"{parts[0]} and {parts[1]}"
    else:
        objects_str = ", ".join(parts[:-1]) + f", and {parts[-1]}"

    return f"{objects_str} detected"


def _pluralize(label: str, count: int) -> str:
    """Return plural form of label if count > 1.

    Handles common pluralization rules. For complex cases,
    simply appends 's'.

    Args:
        label: Singular form of the label.
        count: Number of objects.

    Returns:
        Pluralized label if count > 1, otherwise original.
    """
    if count == 1:
        return label

    # Common irregular plurals
    irregulars = {
        "person": "people",
        "child": "children",
        "foot": "feet",
        "tooth": "teeth",
        "goose": "geese",
        "mouse": "mice",
        "man": "men",
        "woman": "women",
    }

    if label.lower() in irregulars:
        return irregulars[label.lower()]

    # Words ending in 'y' -> 'ies'
    if label.endswith("y") and len(label) > 1 and label[-2] not in "aeiou":
        return label[:-1] + "ies"

    # Words ending in 's', 'x', 'z', 'ch', 'sh' -> 'es'
    if label.endswith(("s", "x", "z", "ch", "sh")):
        return label + "es"

    # Default: add 's'
    return label + "s"


def _bbox_to_location(bbox: List[float]) -> str:
    """Convert normalized bounding box to location description.

    Args:
        bbox: Normalized bounding box [x, y, width, height].

    Returns:
        Location string: "left", "center", or "right".
    """
    if not bbox or len(bbox) < 1:
        return "unknown"

    # Use x-center of bounding box
    x_center = bbox[0] + (bbox[2] / 2 if len(bbox) > 2 else 0)

    if x_center < 0.33:
        return "left"
    elif x_center < 0.67:
        return "center"
    else:
        return "right"


def generate_detailed_state(
    detections: List[Union[Dict[str, Any], Any]],
    frame_shape: Optional[Tuple[int, int]] = None
) -> str:
    """Generate detailed state string with full detection info.

    Provides comprehensive detection information including
    confidence, location, and spatial relationships.

    Args:
        detections: List of detection objects or dictionaries.
        frame_shape: Optional (height, width) for pixel coordinates.

    Returns:
        Detailed multi-line state string.
    """
    if not detections:
        return "Area clear - no objects detected"

    lines = [f"{len(detections)} objects detected:"]

    for i, det in enumerate(detections, 1):
        if isinstance(det, dict):
            label = det.get("label", "unknown")
            conf = det.get("confidence", None)
            bbox = det.get("bbox", None)
        else:
            label = getattr(det, "label", "unknown")
            conf = getattr(det, "confidence", None)
            bbox = getattr(det, "bbox", None)

        detail = f"  {i}. {label}"

        if conf is not None:
            detail += f" ({conf:.0%} confidence)"

        if bbox:
            loc = _bbox_to_location(bbox)
            detail += f" - {loc}"

            if frame_shape:
                h, w = frame_shape[:2]
                px = int(bbox[0] * w)
                py = int(bbox[1] * h)
                pw = int(bbox[2] * w)
                ph = int(bbox[3] * h)
                detail += f" [{px},{py},{pw},{ph}px]"

        lines.append(detail)

    return "\n".join(lines)
