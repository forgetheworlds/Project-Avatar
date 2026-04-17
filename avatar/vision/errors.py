"""Vision provider error types and error codes.

This module defines error types specific to vision provider operations,
including camera capture errors, detector inference errors, and provider
initialization failures.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class VisionErrorCode(Enum):
    """Error codes for vision provider operations.

    These codes provide machine-readable error classification for
    programmatic error handling and logging categorization.
    """

    # Camera provider errors
    CAMERA_NOT_CONNECTED = "camera_not_connected"
    CAMERA_CONNECTION_FAILED = "camera_connection_failed"
    CAMERA_TIMEOUT = "camera_timeout"
    CAMERA_FRAME_CAPTURE_FAILED = "camera_frame_capture_failed"
    CAMERA_INVALID_CONFIG = "camera_invalid_config"
    CAMERA_SDK_NOT_AVAILABLE = "camera_sdk_not_available"

    # Detector provider errors
    DETECTOR_NOT_INITIALIZED = "detector_not_initialized"
    DETECTOR_MODEL_LOAD_FAILED = "detector_model_load_failed"
    DETECTOR_INFERENCE_FAILED = "detector_inference_failed"
    DETECTOR_INVALID_BACKEND = "detector_invalid_backend"
    DETECTOR_INVALID_FRAME = "detector_invalid_frame"

    # Provider registry errors
    PROVIDER_NOT_REGISTERED = "provider_not_registered"
    PROVIDER_ALREADY_REGISTERED = "provider_already_registered"
    PROVIDER_INIT_FAILED = "provider_init_failed"

    # General errors
    UNKNOWN_ERROR = "unknown_error"


class VisionProviderError(Exception):
    """Base exception for vision provider errors.

    All vision-related errors inherit from this base class for
    unified error handling and catching.

    Attributes:
        code: Machine-readable error code for classification.
        message: Human-readable error description.
        backend: Optional backend name where the error occurred.
        cause: Optional underlying exception that caused this error.

    Example:
        >>> try:
        ...     frame = await camera.capture_frame()
        ... except VisionProviderError as e:
        ...     if e.code == VisionErrorCode.CAMERA_TIMEOUT:
        ...         logger.warning(f"Camera timeout: {e.message}")
        ...     else:
        ...         raise
    """

    def __init__(
        self,
        code: VisionErrorCode,
        message: str,
        backend: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.backend = backend
        self.cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        """Return formatted error message with code and backend."""
        parts = [f"[{self.code.value}]"]
        if self.backend:
            parts.append(f"({self.backend})")
        parts.append(self.message)
        return " ".join(parts)

    def to_dict(self) -> dict:
        """Convert error to dictionary for serialization.

        Returns:
            Dictionary with code, message, backend, and optional cause info.
        """
        result = {
            "code": self.code.value,
            "message": self.message,
            "backend": self.backend,
        }
        if self.cause:
            result["cause"] = str(self.cause)
        return result


class CameraError(VisionProviderError):
    """Error specific to camera provider operations.

    Raised when camera operations fail (connection, capture, configuration).

    Example:
        >>> raise CameraError(
        ...     VisionErrorCode.CAMERA_CONNECTION_FAILED,
        ...     "Failed to connect to RTSP stream",
        ...     backend="rtsp",
        ... )
    """

    pass


class DetectorError(VisionProviderError):
    """Error specific to detector provider operations.

    Raised when detector operations fail (initialization, inference,
    model loading).

    Example:
        >>> raise DetectorError(
        ...     VisionErrorCode.DETECTOR_MODEL_LOAD_FAILED,
        ...     "Failed to load YOLO model weights",
        ...     backend="yolo",
        ... )
    """

    pass


class ProviderRegistryError(VisionProviderError):
    """Error specific to provider registry operations.

    Raised when provider registration/lookup operations fail.

    Example:
        >>> raise ProviderRegistryError(
        ...     VisionErrorCode.PROVIDER_NOT_REGISTERED,
        ...     "No provider registered for 'realsense'",
        ... )
    """

    pass
