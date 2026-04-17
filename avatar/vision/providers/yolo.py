"""YOLO detector provider with multi-backend support.

This module provides YoloDetectorProvider for object detection using YOLO
models, supporting multiple inference backends: ultralytics, ncnn, and OpenVINO.

Backend Selection:
-----------------
- ultralytics: Python-based, easiest to use, requires PyTorch
- ncnn: Mobile-optimized, good for edge devices, requires ncnn package
- openvino: Intel-optimized, good for x86 CPUs, requires openvino package

Example:
    >>> provider = YoloDetectorProvider(model="yolov8n", backend="ultralytics")
    >>> await provider.initialize()
    >>> detections = await provider.detect(frame)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from avatar.vision.errors import DetectorError, VisionErrorCode
from avatar.vision.providers.base import Detection, DetectorConfig, Frame

logger = logging.getLogger(__name__)

# Backend availability checks
_ULTRALYTICS_AVAILABLE = False
_NCNN_AVAILABLE = False
_OPENVINO_AVAILABLE = False

_yolo = None
_ncnn = None
_openvino = None

try:
    from ultralytics import YOLO

    _ULTRALYTICS_AVAILABLE = True
    _yolo = YOLO
except ImportError:
    logger.debug("ultralytics not available")

try:
    import ncnn

    _NCNN_AVAILABLE = True
    _ncnn = ncnn
except ImportError:
    logger.debug("ncnn not available")

try:
    import openvino as ov

    _OPENVINO_AVAILABLE = True
    _openvino = ov
except ImportError:
    logger.debug("openvino not available")


# COCO class names (default for YOLO models)
COCO_CLASSES = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]


class YoloDetectorProvider:
    """YOLO detector provider with multi-backend support.

    Supports multiple inference backends for different deployment scenarios:
    - ultralytics: Easy development and prototyping
    - ncnn: Mobile and embedded devices
    - openvino: Intel CPUs and accelerators

    Backend Selection Logic:
    -----------------------
    1. If backend specified in config, use that
    2. Fall back to first available backend
    3. Raise error if no backend available

    Attributes:
        backend_name: Provider identifier ("yolo").
        model: Model name or path.
        inference_backend: Active inference backend name.
        is_initialized: Whether detector is ready.

    Example:
        >>> # Using ultralytics (default)
        >>> provider = YoloDetectorProvider(model="yolov8n")
        >>> await provider.initialize()
        >>> detections = await provider.detect(frame)

        >>> # Using ncnn for edge deployment
        >>> provider = YoloDetectorProvider(
        ...     model="yolov8n_int8",
        ...     backend="ncnn"
        ... )
    """

    backend_name = "yolo"

    def __init__(
        self,
        model: str = "yolov8n",
        config: Optional[DetectorConfig] = None,
        backend: Optional[str] = None,
        confidence_threshold: float = 0.5,
        classes: Optional[List[str]] = None,
    ) -> None:
        """Initialize YOLO detector provider.

        Args:
            model: Model name (e.g., "yolov8n") or path to weights.
            config: Optional detector configuration.
            backend: Inference backend ("ultralytics", "ncnn", "openvino").
            confidence_threshold: Minimum confidence for detections.
            classes: Optional list of classes to detect.
        """
        self._model = model
        self._config = config or DetectorConfig(
            model=model,
            confidence_threshold=confidence_threshold,
            backend=backend or "ultralytics",
            classes=classes,
        )

        # Determine backend
        self._inference_backend = self._select_backend(backend)

        # Model instance (lazy loaded)
        self._model_instance: Optional[Any] = None
        self._initialized = False

        # Class names for detection labels
        self._class_names: List[str] = COCO_CLASSES

    def _select_backend(self, requested_backend: Optional[str]) -> str:
        """Select inference backend based on availability and request.

        Args:
            requested_backend: User-requested backend name.

        Returns:
            Selected backend name.

        Raises:
            DetectorError: If requested backend not available or no backend available.
        """
        if requested_backend:
            if requested_backend == "ultralytics" and _ULTRALYTICS_AVAILABLE:
                return "ultralytics"
            elif requested_backend == "ncnn" and _NCNN_AVAILABLE:
                return "ncnn"
            elif requested_backend == "openvino" and _OPENVINO_AVAILABLE:
                return "openvino"
            elif requested_backend:
                # User requested specific backend that's not available
                available = []
                if _ULTRALYTICS_AVAILABLE:
                    available.append("ultralytics")
                if _NCNN_AVAILABLE:
                    available.append("ncnn")
                if _OPENVINO_AVAILABLE:
                    available.append("openvino")

                raise DetectorError(
                    VisionErrorCode.DETECTOR_INVALID_BACKEND,
                    f"Requested backend '{requested_backend}' not available. "
                    f"Available backends: {available}",
                    backend=self.backend_name,
                )

        # Auto-select first available
        if _ULTRALYTICS_AVAILABLE:
            return "ultralytics"
        elif _NCNN_AVAILABLE:
            return "ncnn"
        elif _OPENVINO_AVAILABLE:
            return "openvino"
        else:
            raise DetectorError(
                VisionErrorCode.DETECTOR_INVALID_BACKEND,
                "No YOLO inference backend available. "
                "Install one of: ultralytics, ncnn, or openvino",
                backend=self.backend_name,
            )

    @property
    def inference_backend(self) -> str:
        """Return the active inference backend name."""
        return self._inference_backend

    @property
    def is_initialized(self) -> bool:
        """Check if detector is initialized and ready."""
        return self._initialized and self._model_instance is not None

    @property
    def class_names(self) -> List[str]:
        """Return list of class names this detector can detect."""
        return self._class_names

    async def initialize(self) -> bool:
        """Initialize detector by loading model weights.

        Returns:
            True if initialization successful.

        Raises:
            DetectorError: If model loading fails.
        """
        try:
            logger.info(
                f"Initializing YOLO detector with backend: {self._inference_backend}"
            )

            if self._inference_backend == "ultralytics":
                return await self._init_ultralytics()
            elif self._inference_backend == "ncnn":
                return await self._init_ncnn()
            elif self._inference_backend == "openvino":
                return await self._init_openvino()
            else:
                raise DetectorError(
                    VisionErrorCode.DETECTOR_INVALID_BACKEND,
                    f"Unknown backend: {self._inference_backend}",
                    backend=self.backend_name,
                )

        except DetectorError:
            raise
        except Exception as e:
            raise DetectorError(
                VisionErrorCode.DETECTOR_MODEL_LOAD_FAILED,
                f"Failed to initialize YOLO detector: {e}",
                backend=self.backend_name,
                cause=e,
            )

    async def _init_ultralytics(self) -> bool:
        """Initialize Ultralytics YOLO backend."""
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()

        def _load():
            model = _yolo(self._model)  # type: ignore[misc]
            # Warm-up inference
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            model(dummy, verbose=False)
            return model

        self._model_instance = await loop.run_in_executor(None, _load)
        self._initialized = True
        logger.info(f"Ultralytics YOLO model loaded: {self._model}")
        return True

    async def _init_ncnn(self) -> bool:
        """Initialize NCNN YOLO backend.

        Note: Requires pre-converted NCNN model files (.param and .bin).
        This is a stub implementation that sets up the structure.
        """
        logger.warning(
            "NCNN backend requires pre-converted model files. "
            "Use ultralytics backend for automatic model loading."
        )
        # NCNN requires manually converted models
        # This is a placeholder for the actual implementation
        self._initialized = False
        raise DetectorError(
            VisionErrorCode.DETECTOR_MODEL_LOAD_FAILED,
            "NCNN backend requires pre-converted .param/.bin model files. "
            "Convert your YOLO model using pnnx or similar tools.",
            backend=self.backend_name,
        )

    async def _init_openvino(self) -> bool:
        """Initialize OpenVINO YOLO backend.

        Note: Requires OpenVINO IR model files (.xml and .bin).
        This is a stub implementation that sets up the structure.
        """
        logger.warning(
            "OpenVINO backend requires pre-converted IR model files. "
            "Use ultralytics backend for automatic model loading."
        )
        # OpenVINO requires IR format models
        # This is a placeholder for the actual implementation
        self._initialized = False
        raise DetectorError(
            VisionErrorCode.DETECTOR_MODEL_LOAD_FAILED,
            "OpenVINO backend requires pre-converted .xml/.bin IR files. "
            "Convert your YOLO model using OpenVINO Model Optimizer.",
            backend=self.backend_name,
        )

    async def detect(self, frame: Frame) -> List[Detection]:
        """Detect objects in the given frame.

        Args:
            frame: Frame object containing image data.

        Returns:
            List of Detection objects, sorted by confidence (highest first).

        Raises:
            DetectorError: If detection fails or detector not initialized.
        """
        if not self.is_initialized:
            raise DetectorError(
                VisionErrorCode.DETECTOR_NOT_INITIALIZED,
                "Detector not initialized. Call initialize() first.",
                backend=self.backend_name,
            )

        if frame.data.size == 0:
            raise DetectorError(
                VisionErrorCode.DETECTOR_INVALID_FRAME,
                "Frame data is empty",
                backend=self.backend_name,
            )

        try:
            if self._inference_backend == "ultralytics":
                return await self._detect_ultralytics(frame)
            elif self._inference_backend == "ncnn":
                return await self._detect_ncnn(frame)
            elif self._inference_backend == "openvino":
                return await self._detect_openvino(frame)
            else:
                raise DetectorError(
                    VisionErrorCode.DETECTOR_INVALID_BACKEND,
                    f"Unknown backend: {self._inference_backend}",
                    backend=self.backend_name,
                )

        except DetectorError:
            raise
        except Exception as e:
            raise DetectorError(
                VisionErrorCode.DETECTOR_INFERENCE_FAILED,
                f"Detection failed: {e}",
                backend=self.backend_name,
                cause=e,
            )

    async def _detect_ultralytics(self, frame: Frame) -> List[Detection]:
        """Run detection using Ultralytics backend."""
        loop = asyncio.get_event_loop()

        def _infer():
            results = self._model_instance(
                frame.data,
                conf=self._config.confidence_threshold,
                verbose=False,
            )
            return results[0] if results else None

        result = await loop.run_in_executor(None, _infer)

        if result is None:
            return []

        detections = []
        for box in result.boxes:
            # Get class info
            class_id = int(box.cls[0])
            class_name = self._class_names[class_id]

            # Filter by requested classes
            if self._config.classes and class_name not in self._config.classes:
                continue

            # Get bbox in normalized format
            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = xyxy

            # Convert to normalized [x, y, w, h]
            h, w = frame.height, frame.width
            norm_x = float(x1 / w)
            norm_y = float(y1 / h)
            norm_w = float((x2 - x1) / w)
            norm_h = float((y2 - y1) / h)

            # Clamp to valid range
            bbox = [
                max(0.0, min(1.0, norm_x)),
                max(0.0, min(1.0, norm_y)),
                max(0.0, min(1.0, norm_w)),
                max(0.0, min(1.0, norm_h)),
            ]

            detection = Detection(
                label=class_name,
                confidence=float(box.conf[0]),
                bbox=bbox,
                class_id=class_id,
                metadata={"backend": "ultralytics"},
            )
            detections.append(detection)

        # Sort by confidence
        return sorted(detections, key=lambda d: d.confidence, reverse=True)

    async def _detect_ncnn(self, frame: Frame) -> List[Detection]:
        """Run detection using NCNN backend (stub)."""
        raise DetectorError(
            VisionErrorCode.DETECTOR_INFERENCE_FAILED,
            "NCNN inference not implemented. Use ultralytics backend.",
            backend=self.backend_name,
        )

    async def _detect_openvino(self, frame: Frame) -> List[Detection]:
        """Run detection using OpenVINO backend (stub)."""
        raise DetectorError(
            VisionErrorCode.DETECTOR_INFERENCE_FAILED,
            "OpenVINO inference not implemented. Use ultralytics backend.",
            backend=self.backend_name,
        )

    def get_info(self) -> Dict[str, Any]:
        """Get detector information and configuration.

        Returns:
            Dictionary with backend info and model details.
        """
        return {
            "backend": self.backend_name,
            "inference_backend": self._inference_backend,
            "model": self._model,
            "initialized": self._initialized,
            "confidence_threshold": self._config.confidence_threshold,
            "classes": self._config.classes,
            "num_classes": len(self._class_names),
            "backend_availability": {
                "ultralytics": _ULTRALYTICS_AVAILABLE,
                "ncnn": _NCNN_AVAILABLE,
                "openvino": _OPENVINO_AVAILABLE,
            },
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"YoloDetectorProvider(model={self._model!r}, "
            f"backend={self._inference_backend!r}, "
            f"initialized={self._initialized})"
        )
