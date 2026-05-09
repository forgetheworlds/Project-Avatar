---
name: avatar-vision-targeting
description: Use when the Project Avatar flight deck operator circles or references camera content, asks to follow a person/object, lock onto a target, inspect a region, or use drone camera/video context.
---

# Avatar Vision Targeting

## Annotation Contract
Dashboard camera messages can include normalized percentages, pixel center, pixel radius, bounding box, frame size, telemetry, heading, and mode. Treat this as a region of interest, not proof of identity.

## Target Lock Flow
1. Use the annotation as a visual hint.
2. Ask vision/detection tools for objects in the current frame when available.
3. Match detections to the annotation bbox by overlap/center distance.
4. If confidence is weak, ask for a tighter annotation or another frame.
5. Use tracking/orchestrator tools to follow only after target identity is stable.

## Best Practices
- Describe the selected target back to the operator before moving.
- Keep follow distance, altitude, and speed conservative.
- If the target leaves frame, hold or widen search rather than guessing.
- For people/vehicles/boats, preserve a stable target ID when the tracker supports it.

## Common Mistakes
- Do not treat a circle as permission to fly into/over people.
- Do not infer hidden obstacles from a single frame.
- Do not lock onto a new target without telling the operator.

