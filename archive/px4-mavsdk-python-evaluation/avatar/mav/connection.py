"""This module has been removed.

The avatar.mav.connection module has been removed as part of Wave 0 Task 6.
Please use the following alternatives:

1. For ConnectionConfig:
   from avatar.mav.connection_config import ConnectionConfig

2. For DroneConnection:
   - Recommended: Use ConnectionManager from avatar.mav.connection_manager
   - Backward compat: Use DroneConnection shim from avatar.mcp_server.compat

Migration Timeline:
    - v0.2.0: Compat layer introduced, deprecation warnings added
    - v0.3.0: Continued support, enhanced warnings
    - v0.4.0: avatar.mav.connection module removed (current)
"""

raise ImportError(
    "avatar.mav.connection has been removed. "
    "Use avatar.mav.connection_config for ConnectionConfig "
    "or avatar.mav.connection_manager for ConnectionManager. "
    "See avatar/mav/connection_config.py for migration guide."
)
