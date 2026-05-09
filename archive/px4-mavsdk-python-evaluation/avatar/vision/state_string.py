"""State string generation for vision pipeline.

Converts detection results into human-readable state strings
for use in prompts and status reporting.

OVERVIEW:
---------
State strings are natural language descriptions of the current vision detection state.
They bridge the gap between raw detection data (bounding boxes, confidence scores)
and higher-level systems like LLM agents, mission planners, and tracking algorithms.

PURPOSE OF STATE STRINGS:
--------------------------
1. **LLM Communication**: Provide readable context about what's visible in the
   camera feed for LLM-based mission planners (e.g., "3 people detected in center")

2. **Status Reporting**: Human-readable telemetry for ground control displays,
   logs, and mission summaries

3. **Tracking Integration**: Convert detection locations into relative positions
   (left/center/right) for basic tracking and navigation decisions

4. **Decision Triggers**: Enable rule-based systems to react to detection states
   without parsing raw bounding box coordinates

DETECTION STATE REPRESENTATION:
-------------------------------
State strings represent detection state through:

- **Object Counts**: "2 people", "1 vehicle", "3 unknown objects"
- **Confidence Levels**: Optional confidence scores (e.g., "87% confidence")
- **Spatial Locations**: Relative positions (left/center/right) based on
  normalized bounding box x-coordinates:
  - x_center < 0.33  -> "left"   (left third of frame)
  - 0.33 <= x_center < 0.67 -> "center" (middle third)
  - x_center >= 0.67 -> "right"  (right third)

- **Object Types**: Pluralized labels with irregular form handling
  (person->people, child->children, foot->feet, etc.)

USAGE EXAMPLES:
---------------

Basic detection summary:
    >>> detections = [{"label": "person"}, {"label": "person"}, {"label": "vehicle"}]
    >>> generate_state_string(detections)
    '2 people and 1 vehicle detected'

Empty scene:
    >>> generate_state_string([])
    'Area clear'

With confidence scores:
    >>> detections = [{"label": "person", "confidence": 0.92}]
    >>> generate_state_string(detections, include_confidence=True)
    '1 person detected (avg confidence 92%)'

With spatial locations:
    >>> detections = [{"label": "person", "bbox": [0.1, 0.2, 0.3, 0.4]}]
    >>> generate_state_string(detections, include_location=True)
    '1 person detected (located left)'

Detailed multi-line output (for debugging/detailed tracking):
    >>> detections = [
    ...     {"label": "person", "confidence": 0.95, "bbox": [0.1, 0.2, 0.2, 0.4]},
    ...     {"label": "vehicle", "confidence": 0.87, "bbox": [0.6, 0.3, 0.3, 0.3]}
    ... ]
    >>> generate_detailed_state(detections, frame_shape=(480, 640))
    '2 objects detected:\n  1. person (95% confidence) - left [64,96,128,192px]\n  2. vehicle (87% confidence) - center [384,144,192,144px]'

TRACKING INTEGRATION:
---------------------
State strings integrate with object tracking through spatial location hints:

1. **Tracking by Location**: The _bbox_to_location() function converts
   normalized bounding boxes into relative positions (left/center/right).
   This is used by the tracker to:
   - Identify which detected object corresponds to a tracked target
   - Make navigation decisions (e.g., "turn left to follow target")
   - Filter detections by region of interest

2. **Data Format Compatibility**: The module accepts both:
   - Dictionary format: {"label": "person", "confidence": 0.9, "bbox": [...]}
   - Object format: detection.label, detection.confidence, detection.bbox
   This flexibility allows it to work with YOLO output, tracker output,
   or any detection source.

3. **Frame Coordinate Conversion**: When frame_shape is provided,
   generate_detailed_state() converts normalized coordinates (0-1)
   to pixel coordinates, enabling precise tracking calculations.

Example tracking workflow:
    # 1. YOLO detects objects
    detections = yolo_model(frame)

    # 2. Convert to state string for LLM/agent
    state = generate_state_string(detections, include_location=True)
    # Returns: "2 people detected (located left and center)"

    # 3. Tracker updates based on location hints
    for det in detections:
        location = _bbox_to_location(det["bbox"])
        tracker.update(det, location_hint=location)

    # 4. Detailed state for precision tracking
    detailed = generate_detailed_state(detections, frame_shape)
    # Used for calculating movement vectors between frames

TYPICAL WORKFLOW:
-----------------
    Raw Frame -> YOLO Detection -> State String -> LLM/Agent/Tracker
                        |                              |
                        v                              v
                Detection Objects              Action Decision
                (bbox, confidence)             (follow, search, etc.)
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

    This is the primary interface for converting detection results
    into actionable state descriptions. It handles:
    - Empty scenes (returns empty_message)
    - Single vs multiple object types (different formatting)
    - Pluralization of labels
    - Optional confidence and location metadata

    Args:
        detections: List of detection objects or dictionaries.
            Each detection should have a 'label' attribute/key.
            Optionally 'confidence' and 'bbox' for extended output.
            Supports both dict format (det["label"]) and object format
            (det.label) for flexibility with different detection sources.
        include_confidence: Include confidence scores in output.
            When True, adds average confidence for single-type detections.
        include_location: Include location hints (left/center/right).
            When True, converts bbox x-center to relative position.
            Useful for tracking and navigation decisions.
        empty_message: Message to return when no detections.
            Default "Area clear" - customize for different contexts
            (e.g., "No targets found", "Search area empty").

    Returns:
        Human-readable string describing detected objects.
        Single type: "{count} {label} detected" (+ optional extras)
        Multiple types: "{count1} {label1} and {count2} {label2} detected"
        Empty: empty_message

    Example:
        >>> detections = [{"label": "person"}, {"label": "person"}, {"label": "vehicle"}]
        >>> generate_state_string(detections)
        '2 people and 1 vehicle detected'

        >>> generate_state_string([])
        'Area clear'

        >>> detections = [{"label": "person", "confidence": 0.92, "bbox": [0.2, 0.3, 0.1, 0.2]}]
        >>> generate_state_string(detections, include_confidence=True, include_location=True)
        '1 person detected (avg confidence 92%; located center)'
    """
    if not detections:
        return empty_message

    # Extract labels from detections (handle both dict and object formats)
    # This dual-format support allows the function to work with:
    # - Raw YOLO output (often as dictionaries)
    # - Tracker output (often as objects with attributes)
    # - Custom detection wrappers
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
            # Assume object with attributes (e.g., from a tracker or detector class)
            labels.append(getattr(det, "label", "unknown"))
            if include_confidence:
                confidences.append(getattr(det, "confidence", None))
            if include_location:
                bbox = getattr(det, "bbox", None)
                if bbox:
                    locations.append(_bbox_to_location(bbox))

    # Count occurrences of each label using Counter for efficient aggregation
    # This produces a mapping like: {"person": 2, "vehicle": 1}
    label_counts = Counter(labels)

    # Build the state string using appropriate formatter based on complexity
    if len(label_counts) == 1:
        # Single object type - can include detailed confidence/location info
        label = list(label_counts.keys())[0]
        count = label_counts[label]
        return _format_single_type(label, count, confidences, locations,
                                   include_confidence, include_location)
    else:
        # Multiple object types - simpler format listing counts
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

    Used when all detections are the same type (e.g., 3 people).
    Can include rich metadata like average confidence and
    location distribution since all objects share the type.

    Args:
        label: Object label (singular form, will be pluralized if count > 1).
        count: Number of objects detected.
        confidences: List of confidence scores (may contain None values).
        locations: List of location strings ("left", "center", "right").
        include_confidence: Whether to include confidence in output.
        include_location: Whether to include location in output.

    Returns:
        Formatted string for single object type with optional extras
        in parentheses: "{count} {label} detected" or
        "{count} {label} detected ({extras})"

    Example:
        >>> _format_single_type("person", 3, [0.9, 0.85, 0.92], ["left", "left", "center"], True, True)
        '3 people detected (avg confidence 89%; located left and center)'
    """
    # Pluralize the label based on count (e.g., "person" -> "people")
    plural_label = _pluralize(label, count)

    base = f"{count} {plural_label} detected"

    # Build list of extra metadata to append in parentheses
    extras = []

    if include_confidence and confidences:
        # Calculate average of non-None confidence values
        valid_conf = [c for c in confidences if c is not None]
        if valid_conf:
            avg_conf = sum(valid_conf) / len(valid_conf)
            if avg_conf > 0:
                extras.append(f"avg confidence {avg_conf:.0%}")

    if include_location and locations:
        # Deduplicate locations while preserving order
        seen = set()
        unique_locations = []
        for loc in locations:
            if loc not in seen:
                seen.add(loc)
                unique_locations.append(loc)

        if len(unique_locations) == 1:
            extras.append(f"located {unique_locations[0]}")
        else:
            extras.append(f"at {', '.join(unique_locations)}")

    # Append extras in parentheses if any exist
    if extras:
        return f"{base} ({'; '.join(extras)})"
    return base


def _format_multiple_types(
    label_counts: Counter[str],
    include_confidence: bool,
    include_location: bool
) -> str:
    """Format detection string for multiple object types.

    Used when detections contain different object types (e.g., people + vehicles).
    Provides a summary list format since detailed metadata would be too verbose.

    Format: "{count1} {label1} and {count2} {label2} detected"
    or "{count1} {label1}, {count2} {label2}, and {count3} {label3} detected"

    Args:
        label_counts: Counter of label occurrences.
        include_confidence: Whether confidence was requested (not used in
            this simplified format, but kept for API consistency).
        include_location: Whether location was requested (not used in
            this simplified format, but kept for API consistency).

    Returns:
        Formatted string listing all object types with counts,
        sorted by count (highest first).

    Example:
        >>> from collections import Counter
        >>> _format_multiple_types(Counter({"person": 3, "vehicle": 1, "dog": 2}), False, False)
        '3 people, 2 dogs, and 1 vehicle detected'
    """
    total = sum(label_counts.values())

    # Build parts for each object type, sorted by count (descending)
    # This ensures the most numerous objects appear first
    parts = []
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        plural_label = _pluralize(label, count)
        parts.append(f"{count} {plural_label}")

    # Combine with "and" for the last item for natural English
    if len(parts) == 2:
        objects_str = f"{parts[0]} and {parts[1]}"
    else:
        objects_str = ", ".join(parts[:-1]) + f", and {parts[-1]}"

    return f"{objects_str} detected"


def _pluralize(label: str, count: int) -> str:
    """Return plural form of label if count > 1.

    Handles common pluralization rules and irregular forms.
    This is a lightweight inflection function for English nouns.

    Rules applied:
    1. If count == 1, return original (singular)
    2. Check irregular plurals (person->people, child->children, etc.)
    3. Words ending in consonant + y -> ies (fly -> flies)
    4. Words ending in s, x, z, ch, sh -> es (box -> boxes)
    5. Default: add 's'

    Args:
        label: Singular form of the label.
        count: Number of objects.

    Returns:
        Pluralized label if count > 1, otherwise original.

    Examples:
        >>> _pluralize("person", 1)
        'person'
        >>> _pluralize("person", 3)
        'people'
        >>> _pluralize("city", 2)
        'cities'
        >>> _pluralize("box", 2)
        'boxes'
        >>> _pluralize("cat", 2)
        'cats'
    """
    if count == 1:
        return label

    # Common irregular plurals in detection contexts
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

    # Words ending in 'y' preceded by consonant -> 'ies'
    # Examples: city->cities, fly->flies, but day->days
    if label.endswith("y") and len(label) > 1 and label[-2] not in "aeiou":
        return label[:-1] + "ies"

    # Words ending in 's', 'x', 'z', 'ch', 'sh' -> 'es'
    # Examples: box->boxes, watch->watches, bus->buses
    if label.endswith(("s", "x", "z", "ch", "sh")):
        return label + "es"

    # Default: add 's'
    return label + "s"


def _bbox_to_location(bbox: List[float]) -> str:
    """Convert normalized bounding box to location description.

    Maps the x-coordinate of a bounding box center to a relative
    position in the frame: left, center, or right. This provides
    a simple spatial abstraction for tracking and navigation.

    Frame division (based on x-center):
    - [0.00, 0.33): left    (left third of frame)
    - [0.33, 0.67): center   (middle third)
    - [0.67, 1.00]: right    (right third)

    These divisions are chosen to provide:
    - Clear spatial distinction for navigation commands
    - Balanced coverage of typical camera FOV
    - Simple mental model for LLM reasoning

    Args:
        bbox: Normalized bounding box [x, y, width, height] where
            all values are in range [0, 1]. x and y represent the
            top-left corner of the box.

    Returns:
        Location string: "left", "center", or "right".
        Returns "unknown" if bbox is empty or invalid.

    Example:
        >>> _bbox_to_location([0.1, 0.2, 0.2, 0.3])  # Box in left area
        'left'
        >>> _bbox_to_location([0.5, 0.2, 0.2, 0.3])  # Box in center
        'center'
        >>> _bbox_to_location([0.8, 0.2, 0.2, 0.3])  # Box in right area
        'right'

    Integration with Tracking:
        This function is used by the tracker to:
        1. Associate detections with tracked objects based on predicted location
        2. Generate navigation commands ("target on the left, yaw left to center")
        3. Filter detections by region of interest (e.g., only track center objects)
    """
    if not bbox or len(bbox) < 1:
        return "unknown"

    # Calculate x-center of bounding box
    # bbox format: [x, y, width, height] in normalized coordinates
    # x_center = x + width/2
    x_center = bbox[0] + (bbox[2] / 2 if len(bbox) > 2 else 0)

    # Map x_center to location zone
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

    Provides comprehensive detection information including confidence,
    location, and optionally pixel coordinates. This is useful for:
    - Debug logging and detailed telemetry
    - Precision tracking (needs pixel coordinates)
    - LLM prompts requiring detailed spatial awareness
    - Manual inspection of detection results

    Output format:
        "{n} objects detected:
          1. {label} ({confidence}% confidence) - {location} [{x},{y},{w},{h}px]
          2. ..."

    Args:
        detections: List of detection objects or dictionaries.
            Same flexible format as generate_state_string()
            (supports both dict and object access patterns).
        frame_shape: Optional (height, width) tuple for converting
            normalized coordinates to pixel coordinates.
            If provided, adds "[x,y,w,h px]" to each detection line.
            Required for precise tracking calculations.

    Returns:
        Detailed multi-line state string with numbered detections.
        Returns "Area clear - no objects detected" if empty.

    Example:
        >>> detections = [
        ...     {"label": "person", "confidence": 0.95, "bbox": [0.1, 0.2, 0.2, 0.4]},
        ...     {"label": "vehicle", "confidence": 0.87, "bbox": [0.6, 0.3, 0.3, 0.3]}
        ... ]
        >>> generate_detailed_state(detections, frame_shape=(480, 640))
        '2 objects detected:\n  1. person (95% confidence) - left [64,96,128,192px]\n  2. vehicle (87% confidence) - center [384,144,192,144px]'

    Integration with Tracking:
        When frame_shape is provided, the pixel coordinates enable:
        1. Calculate velocity vectors between frames
        2. Predict next position using Kalman filtering
        3. Compute distance to target for approach decisions
        4. Match detections to tracked objects by position

    Typical usage in tracking pipeline:
        # Get pixel-accurate state for tracker
        detailed_state = generate_detailed_state(detections, frame_shape=(1080, 1920))
        logger.info(f"Tracking update: {detailed_state}")

        # Parse detections for tracker update
        for det in detections:
            bbox = det["bbox"]  # normalized
            pixel_bbox = [int(bbox[i] * (frame_shape[1] if i%2==0 else frame_shape[0]))
                         for i in range(4)]
            tracker.update(pixel_bbox)
    """
    if not detections:
        return "Area clear - no objects detected"

    lines = [f"{len(detections)} objects detected:"]

    for i, det in enumerate(detections, 1):
        # Extract detection properties with flexible access pattern
        if isinstance(det, dict):
            label = det.get("label", "unknown")
            conf = det.get("confidence", None)
            bbox = det.get("bbox", None)
        else:
            label = getattr(det, "label", "unknown")
            conf = getattr(det, "confidence", None)
            bbox = getattr(det, "bbox", None)

        # Build detail line for this detection
        detail = f"  {i}. {label}"

        # Add confidence if available
        if conf is not None:
            detail += f" ({conf:.0%} confidence)"

        # Add location and optionally pixel coordinates
        if bbox:
            loc = _bbox_to_location(bbox)
            detail += f" - {loc}"

            # Convert to pixel coordinates if frame dimensions provided
            if frame_shape:
                h, w = frame_shape[:2]
                # bbox: [x_norm, y_norm, w_norm, h_norm]
                # Convert to: [x_px, y_px, w_px, h_px]
                px = int(bbox[0] * w)
                py = int(bbox[1] * h)
                pw = int(bbox[2] * w)
                ph = int(bbox[3] * h)
                detail += f" [{px},{py},{pw},{ph}px]"

        lines.append(detail)

    return "\n".join(lines)
