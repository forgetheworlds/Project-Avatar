"""
Avatar Utils Package - Shared Test and Runtime Utilities
=======================================================

WHAT IS __INIT__.PY?
--------------------
__init__.py marks a directory as a Python package, allowing imports like:
    from avatar.utils import FlightRecorder

It can also define what gets imported with "from avatar.utils import *".

PACKAGE ORGANIZATION:
---------------------
The utils package contains helper functions and classes used across
Project Avatar for both production code and testing.

IMPORT STRUCTURE:
-----------------
This __init__.py uses explicit __all__ to control what gets imported
with wildcard imports. This is a best practice for package APIs.

CURRENT UTILITIES:
------------------
- FlightRecorder: Records telemetry and events during flights for analysis
- TelemetrySnapshot: Single point-in-time telemetry data structure
- FlightEvent: Event recording (takeoff, landing, waypoint reached, etc.)
- MissionStats: Aggregated mission statistics

UNDERSTANDING PYTHON PACKAGES:
-------------------------------

DIRECTORY STRUCTURE:
    avatar/
    ├── __init__.py          # Makes avatar a package
    └── utils/
        ├── __init__.py      # This file - makes utils a subpackage
        └── flight_recorder.py  # The actual implementation

IMPORT PATHS:
    # Absolute import (recommended)
    from avatar.utils import FlightRecorder

    # Relative import (within package)
    from .flight_recorder import FlightRecorder

    # Direct module import
    from avatar.utils.flight_recorder import FlightRecorder

WHY USE __ALL__?
----------------
__all__ defines the public API when using "from module import *".
Without it, Python imports everything not starting with underscore.

Benefits:
1. Explicitly declares public interface
2. Prevents accidental import of internal helpers
3. Better IDE autocomplete
4. Clearer documentation of intended usage

ADDING NEW UTILITIES:
---------------------
To add a new utility to this package:

1. Create the module file (e.g., avatar/utils/new_utility.py)
2. Import it in this __init__.py
3. Add it to __all__ list

Example:
    from .new_utility import MyUtility
    __all__ = [..., "MyUtility"]

Then users can import:
    from avatar.utils import MyUtility
"""

# Import specific classes from the flight_recorder module
# The dot (.) indicates relative import from the same package
from .flight_recorder import FlightRecorder, TelemetrySnapshot, FlightEvent, MissionStats

# __all__ controls what gets imported with: from avatar.utils import *
# This is the PUBLIC API of this package - only these names are exposed
__all__ = [
    # Main flight recording class - records telemetry throughout mission
    "FlightRecorder",
    # Data structures for telemetry and events
    "TelemetrySnapshot",  # Single point-in-time telemetry
    "FlightEvent",        # Event recording (takeoff, landing, etc.)
    "MissionStats",       # Aggregated mission statistics
]

# NOTE: If you add new utilities to flight_recorder.py or create new
# modules in this package, remember to:
# 1. Import them above
# 2. Add them to __all__ list
# 3. Update this docstring to document the new utility
