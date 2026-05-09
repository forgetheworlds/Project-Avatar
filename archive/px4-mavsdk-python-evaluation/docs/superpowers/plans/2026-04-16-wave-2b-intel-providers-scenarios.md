# Wave 2b: Intelligence + Providers + Scenario Framework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Wave 2b (D7 hardware vision providers, D8 mission-intelligence package with OSM/SRTM/Google Maps, D9 RuntimeProfile v2, D10 scenario YAML + driver framework) so first-flight-ready intelligence and simulation harness align with `docs/superpowers/specs/2026-04-16-project-avatar-first-flight-plan-design.md`.

**Architecture:** Split into four parallel streams after W2a + W1 D4 Docker infra: (D7) async vision provider registry wired from `RuntimeProfile` backends; (D8) offline-first `avatar/mission_intel/` with pluggable mapping/elevation providers, deterministic intent grammar, seven read-only MCP tools; (D9) Pydantic v2 profile loader with airframe templates and PX4 overlay preflight gate; (D10) YAML-driven scenario runner with injection, assertions, artifacts, and nine drivers. Gazebo-tier scenarios validate rich sim paths per §8.

**Tech Stack:** Python 3.12+, Pydantic v2, `httpx`/`aiohttp`, `pytest`, `respx` (HTTP mocking for GMaps), `av` (PyAV) for RTSP, optional `pyrealsense2` / `depthai` / `ultralytics` / NCNN / OpenVINO, Gazebo Harmonic `gz transport` / `gz topic -e` fallback, MCP SDK patterns from `avatar/mcp_server/server.py`.

---

## Wave Scope

- **D7:** New package `avatar/vision/providers/` with protocols, registry, RTSP/YOLO/RealSense/OAK/Gazebo implementations, graceful `PROVIDER_UNAVAILABLE`; deprecate or thin-wrap `avatar/vision/providers.py` legacy classes toward the new registry; align `VisionTools` to resolve camera/detector via registry when profile v2 supplies backends.
- **D8:** Full `avatar/mission_intel/` tree per spec §7, all Pydantic models, seven MCP tools in `avatar/mcp_server/tools/mission_intel_tools.py`, registration in `avatar/mcp_server/server.py`, Google Maps guardrails (§7 + user requirements).
- **D9:** Replace frozen `RuntimeProfile` dataclass in `avatar/config/profiles.py` with Pydantic v2 models, layered load order, `Airframe` templates, `com_obl_rc_act`, startup gate calling extended parameter verification against `airframe.param_overlay_path`.
- **D10:** `avatar/sim/runner.py`, `avatar/sim/drivers/*.py`, complete `SCENARIOS` for all six `ScenarioKind` values, three YAML files under `avatar/sim/scenarios/`, pytest gates in `tests/sim/test_scenarios.py`, `scripts/sim.sh scenario analyze_area_offline` convenience path.

## Dependencies

- **W2a complete:** W2a D5/D6 mission primitives/orchestrators and minimal `Mission` shapes expected by `upload_mission` / `load_plan` must exist; this wave extends `mission_spec.py` to v1.0 while preserving backward compatibility where feasible.
- **W1 D4 Docker infra complete:** `scripts/sim.sh`, `docker/compose.yaml` gazebo profile, and `run-scenario.sh` (or equivalent) so D7.6 and D10 Gazebo-marked tests and W2b gate can run in CI/nightly containers (`linux/amd64`).

## Parallel Streams

| Stream | ID | Can start after | Notes |
|--------|-----|-----------------|-------|
| Hardware vision | **D7** | W2a vision tool boundaries stable | D7.7 waits on D9.1 for profile field names but registry API can be built first behind feature flag. |
| Mission intelligence | **D8** | W2a MCP error/annotation patterns | No drone commands; pure planning + HTTP providers. |
| Runtime profile v2 | **D9** | W1 safety parameter manager present | Extend `PX4ParameterManager` if signature mismatch (see D9.3). |
| Scenario framework | **D10** | W1 D4 `scripts/sim.sh` | Drivers mock MCP stdio in unit tests; Gazebo optional markers. |

**Concurrency rule:** D7, D8, D9, D10 proceed in parallel; **D7.7** and **VisionTools** wiring land after **D9.1** merges `RuntimeProfile` fields `camera_backend` / `detector_backend` unchanged semantically from today.

## Wave Gate

Copy from spec §11 W2b row:

| Wave | Gate | Verification |
|------|------|--------------|
| **W2b** | `analyze_area` returns valid report offline; 3 representative scenarios green in Gazebo; hardware vision providers unit-tested on recorded frames | `scripts/sim.sh scenario analyze_area_offline && pytest tests/vision tests/mission_intel` |

Extended gate task (D2b-GATE) also runs scenario pytest subset and commits root `changes-made.md` W2b marker.

## Branch Setup

```bash
git checkout main && git pull
git checkout -b wave-2b-intel-providers-scenarios
```

All Wave 2b commits target this branch until the W2b gate merges.

---

## Stream D7 — Hardware vision providers

### Task D7.1: Vision provider package — protocols, `Frame`/`Detection`, registry

**Files:**
- Create: `avatar/vision/providers/__init__.py`
- Create: `avatar/vision/providers/base.py`
- Create: `avatar/vision/errors.py`
- Create: `tests/vision/providers/test_registry.py`
- Modify: `avatar/vision/providers.py` (re-export from package or add deprecation shim — prefer moving implementations into package and leaving thin aliases)

- [ ] **Step 1: Write failing test** — registry resolves `mock_camera` and `mock_detector`.

```python
# tests/vision/providers/test_registry.py
import pytest
from avatar.vision.providers import VisionProviderRegistry, list_backends


def test_registry_lists_expected_backends():
    assert "mock_camera" in list_backends()
    assert "gazebo_camera" in list_backends()


@pytest.mark.asyncio
async def test_mock_camera_provider_capture():
    from avatar.vision.providers import get_provider_class

    cls = get_provider_class("mock_camera")
    cam = cls(width=32, height=24)
    frame = await cam.capture_frame()
    assert frame.rgb.ndim == 3
    await cam.close()
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/vision/providers/test_registry.py -v` → import errors.

- [ ] **Step 3: Implement** — `avatar/vision/errors.py`:

```python
from enum import StrEnum

class VisionErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

class VisionProviderError(RuntimeError):
    def __init__(self, code: VisionErrorCode, message: str):
        super().__init__(message)
        self.code = code
```

`avatar/vision/providers/base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Any
import numpy as np

@dataclass(frozen=True)
class Frame:
    """RGB uint8 frame (H, W, 3)."""
    rgb: np.ndarray
    t_wall_ns: int | None = None
    source: str = "unknown"


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    bbox_xywh_norm: tuple[float, float, float, float]
    class_id: int = 0


@runtime_checkable
class CameraProvider(Protocol):
    async def capture_frame(self) -> Frame: ...
    async def close(self) -> None: ...


@runtime_checkable
class DetectorProvider(Protocol):
    async def detect(
        self,
        frame: Frame,
        *,
        target_labels: list[str] | None = None,
        min_confidence: float = 0.25,
    ) -> list[Detection]: ...
    async def close(self) -> None: ...
```

`avatar/vision/providers/__init__.py` — `VisionProviderRegistry` dict `BACKENDS: dict[str, type]` mapping:
`rtsp_camera`, `yolo_detector`, `realsense`, `oak`, `gazebo_camera`, `mock_camera`, `mock_detector` → classes (stubs raise `VisionProviderError(PROVIDER_UNAVAILABLE, ...)` until implemented in later tasks; `mock_*` fully working by delegating to existing `GazeboCameraClient` / `MockDetector` wrapped async).

- [ ] **Step 4: Run test** — `pytest tests/vision/providers/test_registry.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add avatar/vision/providers tests/vision/providers && git commit -m "feat(vision): add provider registry and async protocols"`

---

### Task D7.2: `RtspCameraProvider` (PyAV) + recorded H.264 fixture test

**Files:**
- Create: `avatar/vision/providers/rtsp.py`
- Create: `tests/fixtures/vision/sample_clip.mp4` (add small CC0 clip <500KB or generate in test with `av` write ~10 frames)
- Create: `tests/vision/providers/test_rtsp_provider.py`

- [ ] **Step 1: Failing test** — open fixture file URL `file://.../sample_clip.mp4` as RTSP substitute via PyAV `open(filename)`; assert first `capture_frame()` returns `Frame.rgb.shape[2] == 3`.

- [ ] **Step 2: Run** — `pytest tests/vision/providers/test_rtsp_provider.py -v` → FAIL.

- [ ] **Step 3: Implement** `RtspCameraProvider(url: str, buffer_size: int = 2, open_timeout_s: float = 3.0, max_failures: int = 3)` — lazy open on first `capture_frame`, decode next video frame; on repeated decode failure raise `VisionProviderError(PROVIDER_UNAVAILABLE, ...)`.

```python
# avatar/vision/providers/rtsp.py (minimal sketch — engineer fills flush)
import asyncio
import time
import av
import numpy as np
from avatar.vision.providers.base import Frame, CameraProvider
from avatar.vision.errors import VisionProviderError, VisionErrorCode

class RtspCameraProvider:
    def __init__(self, url: str, buffer_size: int = 2, open_timeout_s: float = 3.0, max_failures: int = 3):
        self.url = url
        self.buffer_size = buffer_size
        self.open_timeout_s = open_timeout_s
        self.max_failures = max_failures
        self._container = None
        self._stream = None
        self._failures = 0

    async def capture_frame(self) -> Frame:
        async with asyncio.timeout(self.open_timeout_s):
            return await asyncio.to_thread(self._capture_frame_sync)

    def _capture_frame_sync(self) -> Frame:
        ...
```

- [ ] **Step 4: Pass** — `pytest tests/vision/providers/test_rtsp_provider.py -v`.

- [ ] **Step 5: Commit** — `feat(vision): add RtspCameraProvider with PyAV and failure cap`

---

### Task D7.3: `YoloDetectorProvider` multi-backend + recorded frame test

**Files:**
- Create: `avatar/vision/providers/yolo.py`
- Modify: `pyproject.toml` (optional extras `[vision-yolo-cuda]`, `[vision-yolo-ncnn]`, `[vision-yolo-openvino]`)

- [ ] **Step 1: Test** — `tests/vision/providers/test_yolo_provider.py` loads `tests/fixtures/vision/frame_rgb.npy`, skips if no backend: `pytest.importorskip("ultralytics")` in cuda test; separate `skipif` for ncnn/openvino.

- [ ] **Step 2: Implement** `YoloDetectorProvider(weights_path: str, backend: Literal["ultralytics","ncnn","openvino"], imgsz: int = 416)` lazy model load in executor; map `MockDetector` output to `Detection` for CI default when `weights_path == ""` and env `AVATAR_YOLO_MOCK=1`.

- [ ] **Step 3:** `pytest tests/vision/providers/test_yolo_provider.py -v` (expect skips on dev laptops without deps).

- [ ] **Step 4: Commit** — `feat(vision): add YoloDetectorProvider with pluggable backends`

---

### Task D7.4: `RealSenseCameraProvider` — unavailable when SDK missing

**Files:**
- Create: `avatar/vision/providers/realsense.py`
- Create: `tests/vision/providers/test_realsense_provider.py`

- [ ] **Step 1: Test** — `importorskip` only in positive branch; default test: `pytest.raises(VisionProviderError)` on `RealSenseCameraProvider()` when `pyrealsense2` not installed.

- [ ] **Step 2: Implement** — try import `pyrealsense2`; on success stub `pipeline.start()` in fake unit test with mocked `rs.pipeline`.

- [ ] **Step 3:** `pytest tests/vision/providers/test_realsense_provider.py -v`

- [ ] **Step 4: Commit** — `feat(vision): add RealSenseCameraProvider with graceful unavailable`

---

### Task D7.5: `OakCameraProvider` — same pattern as RealSense

**Files:**
- Create: `avatar/vision/providers/oak.py`
- Create: `tests/vision/providers/test_oak_provider.py`

- [ ] **Steps:** Mirror D7.4 with `depthai`.

- [ ] **Commit** — `feat(vision): add OakCameraProvider stub with depthai gate`

---

### Task D7.6: `GazeboCameraProvider` — gz transport + CLI fallback

**Files:**
- Create: `avatar/vision/providers/gazebo.py` (replace `RuntimeError` in legacy `avatar/vision/providers.py` by delegating to this module)
- Create: `tests/vision/providers/test_gazebo_provider_integration.py` (`@pytest.mark.gazebo`)

**Design (both paths documented for Docker):**

1. **Primary:** Python `gz.msgs` / transport if `gz-python` bindings available in `sim-gazebo` image — subscribe to image topic (configurable `GZ_IMAGE_TOPIC`, default from PX4 gz bridge camera topic used in project docs).
2. **Fallback:** subprocess `gz topic -e -t <topic> -n 1` parsing payload or raw image bytes; slower but works without Python bindings.

- [ ] **Step 1: Unit test (no Gazebo)** — mock subprocess returns a small JPEG bytes; provider decodes to `Frame`.

- [ ] **Step 2: Integration** — `@pytest.mark.gazebo` `pytest tests/vision/providers/test_gazebo_provider_integration.py -v -m gazebo` (document: run inside `docker compose --profile gazebo-test`).

- [ ] **Step 3: Commit** — `feat(vision): implement GazeboCameraProvider with gz transport fallback`

---

### Task D7.7: Wire `HARDWARE_PROFILE` backends → registry via RuntimeProfile v2

**Files:**
- Modify: `avatar/config/profiles.py` (after D9.1 lands, or coordinate same PR)
- Modify: `avatar/mcp_server/tools/vision_tools.py` — resolve `camera_backend` / `detector_backend` from loaded profile via `VisionProviderRegistry.build_camera(name, **kwargs)` / `build_detector(...)`.

- [ ] **Step 1: Test** — `tests/vision/test_profile_wires_providers.py` patches profile to `rtsp_camera` with fake URL file fixture.

- [ ] **Step 2: Implement** wiring.

- [ ] **Step 3:** `pytest tests/vision/test_profile_wires_providers.py -v`

- [ ] **Step 4: Commit** — `feat(vision): wire RuntimeProfile vision backends to provider registry`

---

## Stream D8 — Mission intelligence (`avatar/mission_intel/`)

### Task D8.0: Package bootstrap + `config.py`

**Files:**
- Create: `avatar/mission_intel/__init__.py`
- Create: `avatar/mission_intel/config.py`
- Create: `tests/mission_intel/test_config.py`

**Complete `MissionIntelConfig` (Pydantic v2):**

```python
from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict

class MissionIntelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    osm_cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "avatar" / "osm")
    dem_cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "avatar" / "dem")
    gmaps_cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "avatar" / "gmaps")
    google_maps_api_key: str | None = Field(default=None, validation_alias="GOOGLE_MAPS_API_KEY")
    gmaps_daily_budget: int = Field(default=500, validation_alias="GMAPS_DAILY_BUDGET")
    http_timeout_s: float = 2.5
    user_agent: str = "ProjectAvatarMissionIntel/1.0"
```

- [ ] **Steps:** TDD config default paths + env override `AVATAR_GMAPS_DAILY_BUDGET` if using `env_prefix` pattern — align with D9: mission_intel may read **direct** `GOOGLE_MAPS_API_KEY` without `AVATAR_` prefix per user spec; use `Field(validation_alias="GOOGLE_MAPS_API_KEY")` + `model_validate` from `os.environ`.

- [ ] **Commit** — `feat(mission_intel): add package init and MissionIntelConfig`

---

### Task D8.1: `geo.py` — primitives + tests

**Files:**
- Create: `avatar/mission_intel/geo.py`
- Create: `tests/mission_intel/test_geo.py`

**Complete models:**

```python
from __future__ import annotations
from typing import Iterator
from pydantic import BaseModel, Field, ConfigDict

class Point(BaseModel):
    model_config = ConfigDict(frozen=True)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class BBox(BaseModel):
    model_config = ConfigDict(frozen=True)
    south: float
    west: float
    north: float
    east: float

class Polygon(BaseModel):
    model_config = ConfigDict(frozen=True)
    rings: list[list[Point]]

def haversine_m(a: Point, b: Point) -> float: ...
def bbox_grid(bbox: BBox, step_m: float) -> Iterator[Point]: ...
```

- [ ] **Tests:** distance known city pairs ~±1%; grid covers bbox corners.

- [ ] **Commit** — `feat(mission_intel): add geo primitives and haversine`

---

### Task D8.2: `terrain.py` + tiny HGT fixture

**Files:**
- Create: `avatar/mission_intel/terrain.py`
- Create: `tests/mission_intel/fixtures/N00E000.hgt` (1° tile synthetic or truncated real SRTM3 — document source)
- Create: `tests/mission_intel/test_terrain.py`

Functions: `elevation_at(dem_reader, p) -> float`, `agl_m(point, altitude_m_amsl, dem) -> float`, `slope_deg(grid)`, `ruggedness(stddev of elev in window)`, `line_of_sight(a: Point, b: Point, dem_sampler, step_m) -> bool`.

- [ ] **Commit** — `feat(mission_intel): add terrain analysis helpers`

---

### Task D8.3: `providers/base.py` — protocols

**Files:**
- Create: `avatar/mission_intel/providers/__init__.py`
- Create: `avatar/mission_intel/providers/base.py`

```python
from typing import Protocol, runtime_checkable
from avatar.mission_intel.geo import Point, BBox, Polygon

@runtime_checkable
class MappingProvider(Protocol):
    async def fetch_buildings(self, bbox: BBox) -> list[dict]: ...
    async def fetch_pois(self, bbox: BBox, kinds: list[str]) -> list[dict]: ...
    async def reverse_geocode(self, point: Point) -> str | None: ...

@runtime_checkable
class ElevationProvider(Protocol):
    async def elevation_amsl(self, point: Point) -> tuple[float, str]: ...
```

- [ ] **Test** — dummy class implements protocols; `mypy` optional.

- [ ] **Commit** — `feat(mission_intel): add MappingProvider and ElevationProvider protocols`

---

### Task D8.4: `providers/osm.py` — Overpass + Nominatim + disk cache

**Files:**
- Create: `avatar/mission_intel/providers/osm.py`
- Create: `tests/mission_intel/test_osm_offline.py` (use `respx` to mock `https://overpass-api.de/api/interpreter` and `nominatim.openstreetmap.org`)

Cache key SHA-1 query body under `osm_cache_dir`; TTL per kind (buildings 30d, places 7d, ways 30d) store `{expires_at, payload}` JSON.

- [ ] **Commit** — `feat(mission_intel): add OSM Overpass and Nominatim with disk cache`

---

### Task D8.5: `providers/dem_cache.py` + `providers/elevation.py`

**Files:**
- Create: `avatar/mission_intel/providers/dem_cache.py`
- Create: `avatar/mission_intel/providers/elevation.py`
- Create: `tests/mission_intel/test_elevation.py`

`dem_cache.py` — SRTM HGT path `~/.cache/avatar/dem/{lat}{lon}.hgt` naming SRTM3; lazy download hook **no network in tests** — mock.

`elevation.py` — try local tile; else `https://api.open-elevation.com/api/v1/lookup` with `respx` mock.

- [ ] **Commit** — `feat(mission_intel): add SRTM tile cache and Open-Elevation fallback`

---

### Task D8.6.1: `providers/gmaps.py` — shared client + Places

**Files:**
- Create: `avatar/mission_intel/providers/gmaps.py` (grow incrementally)
- Create: `tests/mission_intel/test_gmaps_places.py`

**Shared guardrails (every endpoint method):**

```python
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

class GmapsQuotaExceeded(RuntimeError):
    CODE = "QUOTA_EXCEEDED"

async def _with_timeout(coro, s: float = 2.5):
    async with asyncio.timeout(s):
        return await coro

def _cache_path(base: Path, endpoint: str, params: dict) -> Path:
    h = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()
    return base / endpoint / f"{h}.json"

class GmapsClient:
    def __init__(self, api_key: str | None, cache_dir: Path, daily_budget: int):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.daily_budget = daily_budget
        self._used = 0
        self._day = time.gmtime().tm_yday

    def available(self) -> bool:
        return bool(self.api_key)

    def _bump(self):
        if time.gmtime().tm_yday != self._day:
            self._day = time.gmtime().tm_yday
            self._used = 0
        self._used += 1
        if self._used > self.daily_budget:
            raise GmapsQuotaExceeded("GMAPS_DAILY_BUDGET exceeded")
```

**TTL:** Places 7d (`ttl_s = 7*86400`). Cache read/write JSON with `expires_at`.

**Test:** `respx` mock Places `nearbysearch` JSON; assert no real HTTP when `GOOGLE_MAPS_API_KEY` unset in CI — skip Places call path test unless key mocked via `respx` only.

Real smoke: `if os.getenv("AVATAR_ALLOW_REAL_GMAPS") != "1": pytest.skip(...)` at top of optional `test_gmaps_places_smoke_real`.

- [ ] **Commit** — `feat(mission_intel): add Google Places client with cache and quota`

---

### Task D8.6.2: GMaps Static Maps → `ImageContent`

**Files:**
- Modify: `avatar/mission_intel/providers/gmaps.py`
- Create: `tests/mission_intel/test_gmaps_static_maps.py`

Return structure compatible with MCP `ImageContent` (`types.ImageContent` from MCP SDK): `data` base64 PNG bytes, `mimeType` `image/png`. TTL 30d.

- [ ] **Commit** — `feat(mission_intel): add Google Static Maps ImageContent helper`

---

### Task D8.6.3: Street View Static

**Files:**
- Modify: `avatar/mission_intel/providers/gmaps.py`
- Create: `tests/mission_intel/test_gmaps_streetview.py`

TTL 30d; `respx` mock `https://maps.googleapis.com/maps/api/streetview`.

- [ ] **Commit** — `feat(mission_intel): add Street View Static client`

---

### Task D8.6.4: Roads API

**Files:**
- Modify: `avatar/mission_intel/providers/gmaps.py`
- Create: `tests/mission_intel/test_gmaps_roads.py`

Nearest roads + snap; TTL 7d.

- [ ] **Commit** — `feat(mission_intel): add Google Roads API client`

---

### Task D8.6.5: Geocoding

**Files:**
- Modify: `avatar/mission_intel/providers/gmaps.py`
- Create: `tests/mission_intel/test_gmaps_geocoding.py`

TTL 30d; returns `Point`.

- [ ] **Commit** — `feat(mission_intel): add Google Geocoding client`

---

### Task D8.7: `area_analyzer.py` — `analyze_area()`

**Files:**
- Create: `avatar/mission_intel/area_analyzer.py`
- Create: `tests/mission_intel/test_area_analyzer_offline.py`

**Models used in return value (`AreaReport` and components) — complete definitions:**

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from avatar.mission_intel.geo import BBox, Point, Polygon

class TerrainStats(BaseModel):
    model_config = ConfigDict(frozen=True)
    mean_elevation_m_amsl: float
    median_elevation_m_amsl: float
    min_elevation_m_amsl: float
    max_elevation_m_amsl: float
    slope_mean_deg: float
    slope_p95_deg: float
    ruggedness_index: float
    max_minus_min_m: float

class BuiltEnvStats(BaseModel):
    model_config = ConfigDict(frozen=True)
    building_count: int
    building_density_per_km2: float
    tallest_building_height_m: float | None
    road_length_m_approx: float
    trail_length_m_approx: float

class POI(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    kind: str
    point: Point
    rank: float = 0.0

class Hazard(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: str
    severity: Literal["info", "warn", "block"]
    description: str
    geometry: Polygon | None = None

class ImageContent(BaseModel):
    """Mirror MCP image fields for JSON schema without importing MCP in core."""
    model_config = ConfigDict(frozen=True)
    mime_type: str
    data_base64: str

class AreaReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    bbox: BBox
    terrain: TerrainStats
    built_environment: BuiltEnvStats
    pois: list[POI]
    satellite_snapshot: ImageContent | None
    hazards: list[Hazard]
    recommended_altitude_band_m_agl: tuple[float, float]
```

`analyze_area(bbox, intent: Literal["cinematic","survey","inspection","general"])` uses injected `MappingProvider`/`ElevationProvider`; when GMaps unavailable, `satellite_snapshot is None`.

- [ ] **Commit** — `feat(mission_intel): implement analyze_area offline path`

---

### Task D8.8: `scenic_sweep.py` — `plan_scenic_sweep()`

**Files:**
- Create: `avatar/mission_intel/scenic_sweep.py`
- Create: `tests/mission_intel/test_scenic_sweep.py`

```python
from pydantic import BaseModel, Field, ConfigDict
from avatar.mission_intel.mission_spec import Mission, CinematicInvocation
from avatar.mission_intel.geo import BBox, Point

class SweepAnchor(BaseModel):
    model_config = ConfigDict(frozen=True)
    anchor_point: Point
    approach_bearing_deg: float
    prominence_score: float

class SweepPlan(BaseModel):
    model_config = ConfigDict(frozen=True)
    mission: Mission
    anchors: list[SweepAnchor]
    cinematic_blocks: list[CinematicInvocation]
```

Implement steps per spec §7.3 (rank anchors, chain 3–6, call `safety_checks` before return).

- [ ] **Commit** — `feat(mission_intel): add plan_scenic_sweep planner`

---

### Task D8.9: `intent_planner.py` — `Parser`, `Match`, `Pattern` protocol, priority order

**Files:**
- Create: `avatar/mission_intel/intent_planner.py` (skeleton)
- Create: `tests/mission_intel/test_intent_parser_infra.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, ClassVar
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import Mission, MissionConstraints

@dataclass(frozen=True)
class Match:
    pattern_id: str
    groups: dict[str, str]

class MissionSpecError(Exception):
    def __init__(self, code: str = "MISSION_SPEC_ERROR", suggestions: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.suggestions = suggestions or []

class Pattern(Protocol):
    id: ClassVar[str]
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None: ...
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission: ...

class Parser:
    PRIORITY: tuple[type[Pattern], ...] = ()  # filled as patterns land

    def parse(self, text: str) -> Match:
        tokens = _tokenize(text)
        for cls in self.PRIORITY:
            m = cls.match(tokens)
            if m:
                return m
        raise MissionSpecError(suggestions=_suggestions(tokens))

def _tokenize(text: str) -> list[str]:
    import re
    return [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]

def _suggestions(tokens: list[str]) -> list[str]:
    return [
        "Try: 'orbit the stadium at 25 meters for 60 seconds'",
        "Try: 'fly the perimeter of the field'",
        "Try: 'hover at the helipad for 20 seconds at 10 meters'",
    ]
```

- [ ] **Commit** — `feat(mission_intel): add intent Parser scaffold and MissionSpecError`

---

### Task D8.10: `PerimeterPattern` (`id="perimeter"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_perimeter.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_perimeter.py
import pytest
import re
from avatar.mission_intel.intent_planner import PerimeterPattern, Parser, MissionSpecError
from avatar.mission_intel.geo import BBox, Point
from avatar.mission_intel.mission_spec import MissionConstraints, SafetyPolicy, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "fly the perimeter of the field"
def test_perimeter_match_fly_perimeter_of(bbox, constraints):
    text = "fly the perimeter of the stadium"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PerimeterPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "perimeter"
    assert "name" in m.groups
    mission = PerimeterPattern().emit(m, bbox, constraints)
    assert mission.version == "1.0"
    assert mission.name == "stadium"
    assert len(mission.waypoints) >= 4
    # Verify closed loop: first and last waypoints are same point
    assert mission.waypoints[0].point.lat == mission.waypoints[-1].point.lat
    assert mission.waypoints[0].point.lon == mission.waypoints[-1].point.lon
    # Verify altitude respects constraints
    assert all(wp.alt_m >= constraints.min_altitude_m_agl for wp in mission.waypoints)


# Positive case 2: "patrol the boundary of zone alpha"
def test_perimeter_match_patrol_boundary_of(bbox, constraints):
    text = "patrol the boundary of zone alpha"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PerimeterPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "perimeter"
    mission = PerimeterPattern().emit(m, bbox, constraints)
    assert mission.name == "zone alpha"
    assert len(mission.waypoints) >= 4


# Negative case 1: "orbit fast" (orbit keyword, not perimeter)
def test_perimeter_negative_orbit_keyword(bbox, constraints):
    text = "orbit fast around the tower"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PerimeterPattern.match(toks)
    assert m is None  # Should not match perimeter pattern


# Negative case 2: random words with no match

def test_perimeter_negative_no_keywords(bbox, constraints):
    text = "go fast and turn left then hover there"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PerimeterPattern.match(toks)
    assert m is None
    # Verify Parser raises MissionSpecError when no pattern matches
    parser = Parser()
    with pytest.raises(MissionSpecError) as exc_info:
        parser.parse(text)
    assert "Try:" in str(exc_info.value)


# Registration test: verify Parser.PRIORITY includes PerimeterPattern
def test_perimeter_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser
    from avatar.mission_intel.intent_planner import PerimeterPattern
    assert PerimeterPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_perimeter.py -v` → import errors, class not found.

- [ ] **Step 3: Implement**

```python
# avatar/mission_intel/intent_planner.py (add to existing file)
from __future__ import annotations
import re
import math
from dataclasses import dataclass
from typing import ClassVar
from avatar.mission_intel.geo import Point, BBox, haversine_m
from avatar.mission_intel.mission_spec import (
    Mission, MissionConstraints, Waypoint, WaypointAction,
    SafetyPolicy, CinematicInvocation
)


@dataclass(frozen=True)
class Match:
    pattern_id: str
    groups: dict[str, str]


class MissionSpecError(Exception):
    def __init__(self, code: str = "MISSION_SPEC_ERROR", suggestions: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.suggestions = suggestions or []

    def __str__(self):
        suggs = "\n".join(f"  {s}" for s in self.suggestions)
        return f"{self.code}\n{suggs}"


class Pattern:
    id: ClassVar[str]
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        raise NotImplementedError
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        raise NotImplementedError


class PerimeterPattern(Pattern):
    """
    Grammar: (fly|patrol).*(perimeter|boundary).*(of|around) <name>
    
    Example: "fly the perimeter of the stadium" 
             → closed-loop waypoints around bbox with margin
    """
    id = "perimeter"
    
    _PATTERN = re.compile(
        r"(fly|patrol).*?(perimeter|boundary).*?(of|around)\s+(.+)",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            # Extract name from capture group 4 (everything after of/around)
            name = m.group(4).strip() if m.lastindex >= 4 else "unnamed"
            return Match(pattern_id=cls.id, groups={"name": name})
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        """Emit closed-loop rectangular perimeter around bbox."""
        name = match.groups.get("name", "perimeter")
        
        # Calculate margin (~10% of bbox diagonal, min 5m)
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        diag_m = haversine_m(
            Point(lat=bbox.south, lon=bbox.west),
            Point(lat=bbox.north, lon=bbox.east)
        )
        margin_m = max(diag_m * 0.1, 5.0)
        
        # Approximate degrees from meters (rough conversion)
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        
        margin_lat = margin_m * lat_deg_per_m
        margin_lon = margin_m * lon_deg_per_m
        
        # Define corner waypoints (clockwise from SW)
        alt_m = constraints.min_altitude_m_agl + 5.0  # Add small buffer
        corners = [
            Point(lat=bbox.south - margin_lat, lon=bbox.west - margin_lon),  # SW
            Point(lat=bbox.south - margin_lat, lon=bbox.east + margin_lon),  # SE
            Point(lat=bbox.north + margin_lat, lon=bbox.east + margin_lon),  # NE
            Point(lat=bbox.north + margin_lat, lon=bbox.west - margin_lon),  # NW
            Point(lat=bbox.south - margin_lat, lon=bbox.west - margin_lon),  # SW (close loop)
        ]
        
        waypoints = [
            Waypoint(
                point=p,
                alt_m=alt_m,
                alt_frame="agl",
                speed_m_s=5.0,
                action=WaypointAction.FLY_TO
            )
            for p in corners
        ]
        
        # Set first waypoint to hover briefly
        waypoints[0] = Waypoint(
            point=waypoints[0].point,
            alt_m=alt_m,
            alt_frame="agl",
            speed_m_s=3.0,
            hold_s=2.0,
            action=WaypointAction.HOVER
        )
        
        home = Point(lat=center_lat, lon=center_lon)
        
        return Mission(
            version="1.0",
            name=name,
            home=home,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )


class Parser:
    PRIORITY: tuple[type[Pattern], ...] = (PerimeterPattern,)
    
    def parse(self, text: str) -> Match:
        tokens = _tokenize(text)
        for cls in self.PRIORITY:
            m = cls.match(tokens)
            if m:
                return m
        raise MissionSpecError(suggestions=_suggestions(tokens))


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]


def _suggestions(tokens: list[str]) -> list[str]:
    return [
        "Try: 'orbit the stadium at 25 meters for 60 seconds'",
        "Try: 'fly the perimeter of the field'",
        "Try: 'hover at the helipad for 20 seconds at 10 meters'",
    ]
```

- [ ] **Step 4: Run test** — `pytest tests/mission_intel/test_intent_perimeter.py -v` → all tests PASS (5 passed).

- [ ] **Step 5: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_perimeter.py && git commit -m "feat(mission_intel): add plan_mission_from_intent PerimeterPattern with TDD"

---

### Task D8.11: `OrbitPattern` (`id="orbit"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_orbit.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_orbit.py
import pytest
import re
from avatar.mission_intel.intent_planner import OrbitPattern, Parser
from avatar.mission_intel.geo import BBox, Point
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "orbit the tower at 25 meters for 60 seconds"
def test_orbit_match_with_radius_and_duration(bbox, constraints):
    text = "orbit the tower at 25 meters for 60 seconds"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = OrbitPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "orbit"
    assert m.groups["radius_m"] == "25"
    assert m.groups.get("duration_s") == "60"
    
    mission = OrbitPattern().emit(m, bbox, constraints)
    assert mission.name == "tower"
    assert len(mission.waypoints) >= 8  # Circular orbit has multiple waypoints
    # All waypoints should have ORBIT action
    assert all(wp.action == WaypointAction.ORBIT for wp in mission.waypoints)
    # Verify radius is captured in first waypoint params
    assert mission.waypoints[0].alt_m >= constraints.min_altitude_m_agl


# Positive case 2: "orbit X at R 30m" (alternative format)
def test_orbit_match_alt_format(bbox, constraints):
    text = "orbit marker at r 30m"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = OrbitPattern.match(toks)
    assert m is not None
    assert m.groups["radius_m"] == "30"
    # Duration optional - should default to 30s
    assert m.groups.get("duration_s") is None
    
    mission = OrbitPattern().emit(m, bbox, constraints)
    assert mission.name == "marker"
    assert len(mission.waypoints) >= 8


# Negative case 1: Missing radius - "orbit the tower" should fail
def test_orbit_negative_missing_radius(bbox, constraints):
    text = "orbit the tower"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = OrbitPattern.match(toks)
    assert m is None  # No radius specified


# Negative case 2: Invalid radius format - "orbit at abc meters"
def test_orbit_negative_invalid_radius(bbox, constraints):
    text = "orbit at abc meters"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = OrbitPattern.match(toks)
    assert m is None  # Non-numeric radius


# Parser registration test
def test_orbit_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, OrbitPattern
    assert OrbitPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_orbit.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class OrbitPattern(Pattern):
    """
    Grammar: orbit <name> at <radius> [m|meters] [for <duration> [s|sec|seconds]]
    
    Examples: 
        "orbit the tower at 25 meters for 60 seconds"
        "orbit X at r 30m"
    """
    id = "orbit"
    
    # Match: orbit + name + at/r + radius + optional m/meters + optional for + duration
    _PATTERN = re.compile(
        r"orbit\s+(.+?)\s+(?:at|r)\s+(?P<r>\d+(?:\.\d+)?)\s*(?:m|meters?)?(?:\s+for\s+(?P<n>\d+)\s*(?:s|sec|seconds?)?)?",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            radius_m = m.group("r")
            duration_s = m.group("n")  # may be None
            # Extract name (everything between 'orbit' and 'at/r')
            prefix_match = re.search(r"orbit\s+(.+?)\s+(?:at|r)", text, re.IGNORECASE)
            name = "orbit"
            if prefix_match:
                name = prefix_match.group(1).strip()
            groups = {"radius_m": radius_m, "name": name}
            if duration_s:
                groups["duration_s"] = duration_s
            return Match(pattern_id=cls.id, groups=groups)
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        radius_m = float(match.groups["radius_m"])
        duration_s = float(match.groups.get("duration_s", 30))
        name = match.groups.get("name", "orbit")
        
        # Center of orbit is bbox center
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Calculate altitude (constrained)
        alt_m = max(radius_m * 0.5, constraints.min_altitude_m_agl + 5.0)
        alt_m = min(alt_m, constraints.max_altitude_m_amsl - 20.0)
        
        # Generate circular orbit waypoints (8 points for smooth circle)
        num_points = 8
        waypoints = []
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        
        for i in range(num_points + 1):  # +1 to close the circle
            angle = 2 * math.pi * i / num_points
            dx = radius_m * math.cos(angle)
            dy = radius_m * math.sin(angle)
            
            lat = center.lat + dy * lat_deg_per_m
            lon = center.lon + dx * lon_deg_per_m
            
            wp = Waypoint(
                point=Point(lat=lat, lon=lon),
                alt_m=alt_m,
                alt_frame="amsl",
                speed_m_s=3.0,
                action=WaypointAction.ORBIT,
                hold_s=duration_s / num_points if i < num_points else 0
            )
            waypoints.append(wp)
        
        return Mission(
            version="1.0",
            name=name,
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="orbit",
                    params={"radius_m": radius_m, "duration_s": duration_s},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** — Insert `OrbitPattern` after `HoverAtPattern` in D8.19 finalization:

```python
# In Parser class (temporary for this task):
PRIORITY: tuple[type[Pattern], ...] = (OrbitPattern, PerimeterPattern)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_orbit.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_orbit.py && git commit -m "feat(mission_intel): add OrbitPattern with radius/duration capture"

---

### Task D8.12: `LawnmowerPattern` (`id="lawnmower"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_lawnmower.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_lawnmower.py
import pytest
import re
from avatar.mission_intel.intent_planner import LawnmowerPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3987, east=8.5466)  # 100m x 100m approx


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=15.0,
        max_distance_from_home_m=1000.0,
        max_flight_time_s=1200.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "survey the field with 80% overlap"
def test_lawnmower_match_survey_with_overlap(bbox, constraints):
    text = "survey the field with 80% overlap"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = LawnmowerPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "lawnmower"
    assert m.groups.get("overlap_pct") == "80"
    assert m.groups.get("name") == "field"
    
    mission = LawnmowerPattern().emit(m, bbox, constraints)
    assert mission.name == "field"
    # Lawmower pattern should have many waypoints in a grid
    assert len(mission.waypoints) >= 10
    # All waypoints should be PHOTO action for survey
    assert all(wp.action == WaypointAction.PHOTO for wp in mission.waypoints)


# Positive case 2: "lawnmower the bbox at altitude 40m"
def test_lawnmower_match_altitude_specified(bbox, constraints):
    text = "lawnmower the site at altitude 40m"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = LawnmowerPattern.match(toks)
    assert m is not None
    assert m.groups.get("altitude_m") == "40"
    assert m.groups.get("name") == "site"
    
    mission = LawnmowerPattern().emit(m, bbox, constraints)
    # Altitude should be as specified
    assert all(wp.alt_m == 40.0 for wp in mission.waypoints)


# Negative case 1: "fly fast across the field" - no lawnmower/survey/grid keyword
def test_lawnmower_negative_no_keyword(bbox, constraints):
    text = "fly fast across the field"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = LawnmowerPattern.match(toks)
    assert m is None


# Negative case 2: "random inspection task" - different pattern
def test_lawnmower_negative_wrong_pattern(bbox, constraints):
    text = "inspect the roof of the building"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = LawnmowerPattern.match(toks)
    assert m is None


# Parser registration test
def test_lawnmower_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, LawnmowerPattern
    assert LawnmowerPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_lawnmower.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class LawnmowerPattern(Pattern):
    """
    Grammar: (lawnmower|survey|grid) <name> [with <overlap>% overlap] [at altitude <m>]
    
    Examples:
        "survey the field with 80% overlap"
        "lawnmower the site at altitude 40m"
    """
    id = "lawnmower"
    
    # Match lawnmower/survey/grid + name + optional overlap + optional altitude
    _PATTERN = re.compile(
        r"(lawnmower|survey|grid)\s+(?:the\s+)?(.+?)(?:\s+with\s+(?P<o>\d+)%?\s*overlap)?(?:\s+at\s+altitude\s+(?P<a>\d+))?(?:\s*m)?",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            name = m.group(2).strip() if m.group(2) else "survey"
            overlap_pct = m.group("o")  # may be None
            altitude_m = m.group("a")   # may be None
            groups = {"name": name}
            if overlap_pct:
                groups["overlap_pct"] = overlap_pct
            if altitude_m:
                groups["altitude_m"] = altitude_m
            return Match(pattern_id=cls.id, groups=groups)
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        name = match.groups.get("name", "survey")
        overlap_pct = float(match.groups.get("overlap_pct", 80))
        altitude_m = float(match.groups.get("altitude_m", constraints.min_altitude_m_agl + 10))
        
        # Clamp altitude to constraints
        altitude_m = max(altitude_m, constraints.min_altitude_m_agl)
        altitude_m = min(altitude_m, constraints.max_altitude_m_amsl - 10)
        
        # Calculate grid parameters based on overlap
        # Assume 70-degree FOV camera, ground coverage depends on altitude
        # Simple model: track_width at altitude = 2 * altitude * tan(fov/2)
        fov_deg = 70.0
        track_width_m = 2 * altitude_m * math.tan(math.radians(fov_deg / 2))
        # Apply overlap
        spacing_m = track_width_m * (1 - overlap_pct / 100)
        
        # Calculate center
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        home = Point(lat=center_lat, lon=center_lon)
        
        # Generate lawnmower waypoints
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        
        # Bbox dimensions in meters
        bbox_height_m = haversine_m(
            Point(lat=bbox.south, lon=center_lon),
            Point(lat=bbox.north, lon=center_lon)
        )
        bbox_width_m = haversine_m(
            Point(lat=center_lat, lon=bbox.west),
            Point(lat=center_lat, lon=bbox.east)
        )
        
        # Generate parallel tracks (east-west lines, north-south movement)
        num_tracks = max(2, int(bbox_height_m / spacing_m) + 1)
        waypoints = []
        
        for i in range(num_tracks):
            # Alternating direction for each track
            direction = 1 if i % 2 == 0 else -1
            
            lat = bbox.south + (bbox.north - bbox.south) * i / (num_tracks - 1)
            
            # Start point
            start_lon = bbox.west if direction == 1 else bbox.east
            end_lon = bbox.east if direction == 1 else bbox.west
            
            wp_start = Waypoint(
                point=Point(lat=lat, lon=start_lon),
                alt_m=altitude_m,
                alt_frame="amsl",
                speed_m_s=5.0,
                action=WaypointAction.PHOTO
            )
            wp_end = Waypoint(
                point=Point(lat=lat, lon=end_lon),
                alt_m=altitude_m,
                alt_frame="amsl",
                speed_m_s=5.0,
                action=WaypointAction.PHOTO
            )
            
            waypoints.append(wp_start)
            waypoints.append(wp_end)
        
        return Mission(
            version="1.0",
            name=name,
            home=home,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (OrbitPattern, PerimeterPattern, LawnmowerPattern)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_lawnmower.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_lawnmower.py && git commit -m "feat(mission_intel): add LawnmowerPattern for survey/grid coverage"

---

### Task D8.13: `RevealPattern` (`id="reveal"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_reveal.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_reveal.py
import pytest
import re
from avatar.mission_intel.intent_planner import RevealPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "reveal the barn from the west"
def test_reveal_match_from_cardinal(bbox, constraints):
    text = "reveal the barn from the west"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = RevealPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "reveal"
    assert m.groups["name"] == "barn"
    assert m.groups["cardinal"] == "west"
    assert m.groups.get("direction") == "from"
    
    mission = RevealPattern().emit(m, bbox, constraints)
    assert mission.name == "barn"
    assert len(mission.waypoints) == 3  # approach, reveal, exit
    # First waypoint should be approach, last should be exit
    assert mission.waypoints[0].action == WaypointAction.FLY_TO
    assert mission.cinematic_blocks[0].template_id == "approach_reveal"


# Positive case 2: "cinematic reveal of the peak from east"
def test_reveal_match_toward_cardinal(bbox, constraints):
    text = "cinematic reveal of the peak toward east"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = RevealPattern.match(toks)
    assert m is not None
    assert m.groups["name"] == "peak"
    assert m.groups["cardinal"] == "east"
    assert m.groups.get("direction") == "toward"
    
    mission = RevealPattern().emit(m, bbox, constraints)
    assert mission.name == "peak"


# Negative case 1: "show the barn" - no reveal keyword
def test_reveal_negative_no_reveal_keyword(bbox, constraints):
    text = "show the barn from the west"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = RevealPattern.match(toks)
    assert m is None


# Negative case 2: "reveal the barn" - missing cardinal direction
def test_reveal_negative_missing_cardinal(bbox, constraints):
    text = "reveal the barn"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = RevealPattern.match(toks)
    assert m is None


# Parser registration test
def test_reveal_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, RevealPattern
    assert RevealPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_reveal.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class RevealPattern(Pattern):
    """
    Grammar: reveal <name> (from|toward) <cardinal>
    
    Examples:
        "reveal the barn from the west"
        "cinematic reveal of the peak from east"
        "reveal the building toward north"
    """
    id = "reveal"
    
    CARDINALS = {"north": 0, "east": 90, "south": 180, "west": 270}
    
    _PATTERN = re.compile(
        r"(?:cinematic\s+)?reveal(?:\s+of)?\s+(?:the\s+)?(.+?)\s+(from|toward)\s+(?:the\s+)?(?P<card>north|east|south|west)",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            name = m.group(1).strip()
            cardinal = m.group("card").lower()
            direction = m.group(2).lower()
            return Match(pattern_id=cls.id, groups={
                "name": name,
                "cardinal": cardinal,
                "direction": direction
            })
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        name = match.groups["name"]
        cardinal = match.groups["cardinal"]
        direction = match.groups.get("direction", "from")
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Altitude for reveal (higher than min for cinematic effect)
        alt_m = max(constraints.min_altitude_m_agl + 15, 30.0)
        alt_m = min(alt_m, constraints.max_altitude_m_amsl - 20)
        
        # Calculate approach and exit points based on cardinal
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        distance_m = 50.0  # Approach/exit distance from center
        
        if cardinal == "north":
            dx, dy = 0, distance_m
        elif cardinal == "south":
            dx, dy = 0, -distance_m
        elif cardinal == "east":
            dx, dy = distance_m, 0
        else:  # west
            dx, dy = -distance_m, 0
        
        if direction == "from":
            # Approach from opposite direction, reveal toward center
            approach = Point(lat=center_lat - dy * lat_deg_per_m, 
                           lon=center_lon - dx * lon_deg_per_m)
            reveal_point = center
            exit_point = Point(lat=center_lat + dy * lat_deg_per_m,
                              lon=center_lon + dx * lon_deg_per_m)
        else:  # toward
            # Approach from center, reveal toward cardinal
            approach = center
            reveal_point = Point(lat=center_lat + dy * lat_deg_per_m,
                               lon=center_lon + dx * lon_deg_per_m)
            exit_point = reveal_point
        
        waypoints = [
            Waypoint(point=approach, alt_m=alt_m, alt_frame="amsl", 
                    speed_m_s=3.0, action=WaypointAction.FLY_TO),
            Waypoint(point=reveal_point, alt_m=alt_m, alt_frame="amsl",
                    speed_m_s=2.0, hold_s=3.0, action=WaypointAction.HOVER),
            Waypoint(point=exit_point, alt_m=alt_m, alt_frame="amsl",
                    speed_m_s=4.0, action=WaypointAction.FLY_TO),
        ]
        
        return Mission(
            version="1.0",
            name=f"reveal_{name}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="approach_reveal",
                    params={"cardinal": cardinal, "direction": direction},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (
    OrbitPattern, PerimeterPattern, LawnmowerPattern, RevealPattern
)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_reveal.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_reveal.py && git commit -m "feat(mission_intel): add RevealPattern for cinematic reveal shots"

---

### Task D8.14: `EstablishPattern` (`id="establish"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_establish.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_establish.py
import pytest
import re
from avatar.mission_intel.intent_planner import EstablishPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "establishing shot of the stadium"
def test_establish_match_establishing_shot(bbox, constraints):
    text = "establishing shot of the stadium"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = EstablishPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "establish"
    assert m.groups["name"] == "stadium"
    
    mission = EstablishPattern().emit(m, bbox, constraints)
    assert mission.name == "stadium"
    # Establishing shot: wide pull-back with altitude change
    assert len(mission.waypoints) >= 2
    assert mission.cinematic_blocks[0].template_id == "establish"


# Positive case 2: "wide opener of the landscape"
def test_establish_match_wide_opener(bbox, constraints):
    text = "wide opener of the landscape"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = EstablishPattern.match(toks)
    assert m is not None
    assert m.groups["name"] == "landscape"
    
    mission = EstablishPattern().emit(m, bbox, constraints)
    assert mission.name == "landscape"


# Negative case 1: "fly the perimeter" - different pattern
def test_establish_negative_wrong_keyword(bbox, constraints):
    text = "fly the perimeter of the stadium"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = EstablishPattern.match(toks)
    assert m is None


# Negative case 2: "orbit the stadium" - different pattern
def test_establish_negative_orbit_keyword(bbox, constraints):
    text = "orbit the stadium at 30 meters"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = EstablishPattern.match(toks)
    assert m is None


# Parser registration test
def test_establish_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, EstablishPattern
    assert EstablishPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_establish.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class EstablishPattern(Pattern):
    """
    Grammar: (establishing shot|establish|wide opener) [of] <name>
    
    Examples:
        "establishing shot of the stadium"
        "wide opener of the landscape"
        "establish the building"
    """
    id = "establish"
    
    _PATTERN = re.compile(
        r"(?:establishing\s+shot|establish|wide\s+opener)(?:\s+of)?\s+(?:the\s+)?(.+)",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            name = m.group(1).strip()
            return Match(pattern_id=cls.id, groups={"name": name})
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        name = match.groups["name"]
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Establishing shot: start close/low, pull back and up
        start_alt = constraints.min_altitude_m_agl + 5
        end_alt = min(start_alt + 40, constraints.max_altitude_m_amsl - 20)
        
        # Start close to center, end further back
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        distance_m = 60.0
        
        start_point = center
        end_point = Point(
            lat=center_lat + distance_m * lat_deg_per_m,
            lon=center_lon
        )
        
        waypoints = [
            Waypoint(point=start_point, alt_m=start_alt, alt_frame="amsl",
                    speed_m_s=2.0, hold_s=2.0, action=WaypointAction.HOVER),
            Waypoint(point=end_point, alt_m=end_alt, alt_frame="amsl",
                    speed_m_s=1.5, action=WaypointAction.FLY_TO),
        ]
        
        return Mission(
            version="1.0",
            name=f"establish_{name}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="establish",
                    params={"pullback_m": distance_m, "climb_m": end_alt - start_alt},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (
    OrbitPattern, PerimeterPattern, LawnmowerPattern, 
    RevealPattern, EstablishPattern
)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_establish.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_establish.py && git commit -m "feat(mission_intel): add EstablishPattern for establishing shots"

---

### Task D8.15: `FollowPattern` (`id="follow"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_follow.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_follow.py
import pytest
import re
from avatar.mission_intel.intent_planner import FollowPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "follow the runner"
def test_follow_match_runner(bbox, constraints):
    text = "follow the runner"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = FollowPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "follow"
    assert m.groups["target_type"] == "runner"
    
    mission = FollowPattern().emit(m, bbox, constraints)
    assert "follow_runner" in mission.name
    assert len(mission.waypoints) == 1  # Single hover waypoint, tracking is continuous
    assert mission.waypoints[0].action == WaypointAction.HOVER
    assert mission.cinematic_blocks[0].template_id == "tracking_follow"


# Positive case 2: "track the car"
def test_follow_match_car(bbox, constraints):
    text = "track the car"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = FollowPattern.match(toks)
    assert m is not None
    assert m.groups["target_type"] == "car"
    
    mission = FollowPattern().emit(m, bbox, constraints)
    assert "follow_car" in mission.name


# Negative case 1: "follow the wind" - invalid target type
def test_follow_negative_invalid_target(bbox, constraints):
    text = "follow the wind"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = FollowPattern.match(toks)
    # "wind" is not in VALID_TARGETS, so should not match
    assert m is None


# Negative case 2: "orbit the runner" - wrong action verb
def test_follow_negative_wrong_verb(bbox, constraints):
    text = "orbit the runner"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = FollowPattern.match(toks)
    assert m is None


# Parser registration test
def test_follow_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, FollowPattern
    assert FollowPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_follow.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class FollowPattern(Pattern):
    """
    Grammar: (follow|track) <target_type>
    Valid targets: runner, car, subject, target, person, vehicle, boat
    
    Examples:
        "follow the runner"
        "track the car"
        "follow subject"
    """
    id = "follow"
    
    VALID_TARGETS = {"runner", "car", "subject", "target", "person", "vehicle", "boat"}
    
    _PATTERN = re.compile(
        r"(follow|track)(?:\s+the)?\s+(runner|car|subject|target|person|vehicle|boat)",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            target_type = m.group(2).lower()
            if target_type in cls.VALID_TARGETS:
                return Match(pattern_id=cls.id, groups={"target_type": target_type})
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        target_type = match.groups["target_type"]
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Follow mission: single waypoint (hover) with continuous tracking behavior
        # The actual path is determined dynamically by the target
        alt_m = constraints.min_altitude_m_agl + 15
        
        waypoints = [
            Waypoint(
                point=center,
                alt_m=alt_m,
                alt_frame="amsl",
                speed_m_s=5.0,
                hold_s=0,  # Continuous tracking
                action=WaypointAction.HOVER
            )
        ]
        
        return Mission(
            version="1.0",
            name=f"follow_{target_type}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="tracking_follow",
                    params={"target_type": target_type, "altitude_m": alt_m},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (
    OrbitPattern, PerimeterPattern, LawnmowerPattern,
    RevealPattern, EstablishPattern, FollowPattern
)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_follow.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_follow.py && git commit -m "feat(mission_intel): add FollowPattern for subject tracking missions"

---

### Task D8.16: `InspectPattern` (`id="inspect"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_inspect.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_inspect.py
import pytest
import re
from avatar.mission_intel.intent_planner import InspectPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=120.0,  # Lower for inspection
        min_altitude_m_agl=5.0,     # Low for close inspection
        max_distance_from_home_m=200.0,
        max_flight_time_s=300.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "inspect the roof of the building"
def test_inspect_match_roof(bbox, constraints):
    text = "inspect the roof of the building"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = InspectPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "inspect"
    assert m.groups["face"] == "roof"
    assert m.groups.get("name") == "building"
    
    mission = InspectPattern().emit(m, bbox, constraints)
    assert "inspect" in mission.name
    assert all(wp.action == WaypointAction.PHOTO for wp in mission.waypoints)
    assert mission.cinematic_blocks[0].template_id == "inspection_pass"


# Positive case 2: "close inspection of east face"
def test_inspect_match_face_direction(bbox, constraints):
    text = "close inspection of east face"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = InspectPattern.match(toks)
    assert m is not None
    assert m.groups["face"] == "face"
    assert m.groups.get("direction") == "east"
    
    mission = InspectPattern().emit(m, bbox, constraints)
    assert "inspection" in mission.name
    assert len(mission.waypoints) >= 3  # Approach, inspect pass, exit


# Negative case 1: "survey the roof" - wrong action (survey is lawnmower)
def test_inspect_negative_survey_instead(bbox, constraints):
    text = "survey the roof"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = InspectPattern.match(toks)
    assert m is None  # "survey" keyword not inspect


# Negative case 2: "inspect the area" - missing face/roof/side/facade
def test_inspect_negative_missing_face(bbox, constraints):
    text = "inspect the area"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = InspectPattern.match(toks)
    assert m is None  # No specific face/roof/side/facade


# Parser registration test
def test_inspect_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, InspectPattern
    assert InspectPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_inspect.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class InspectPattern(Pattern):
    """
    Grammar: inspect [the] <face/roof/side/facade> [of] <name>
    
    Examples:
        "inspect the roof of the building"
        "close inspection of east face"
        "inspect facade of tower"
    """
    id = "inspect"
    
    VALID_FACES = {"roof", "face", "side", "facade"}
    DIRECTIONS = {"north", "south", "east", "west"}
    
    _PATTERN = re.compile(
        r"(?:close\s+)?inspection(?:\s+of)?|inspect(?:\s+the)?\s+(roof|face|side|facade)(?:\s+of)?(?:\s+the\s+)?(.+?)(?:\s+(north|south|east|west))?",
        re.IGNORECASE
    )
    
    _ALT_PATTERN = re.compile(
        r"(?:close\s+)?inspection(?:\s+of)?\s+(north|south|east|west)?\s*(face|side)",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        
        # Try primary pattern
        m = cls._PATTERN.search(text)
        if m:
            face = m.group(1).lower() if m.group(1) else None
            name = m.group(2).strip() if m.group(2) else "structure"
            direction = m.group(3).lower() if m.group(3) else None
            
            if face and face in cls.VALID_FACES:
                groups = {"face": face, "name": name}
                if direction:
                    groups["direction"] = direction
                return Match(pattern_id=cls.id, groups=groups)
        
        # Try alternative pattern (e.g., "inspection of east face")
        m = cls._ALT_PATTERN.search(text)
        if m:
            direction = m.group(1).lower() if m.group(1) else None
            face = m.group(2).lower() if m.group(2) else None
            if face in cls.VALID_FACES:
                groups = {"face": face, "name": "structure"}
                if direction:
                    groups["direction"] = direction
                return Match(pattern_id=cls.id, groups=groups)
        
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        face = match.groups["face"]
        name = match.groups.get("name", "structure")
        direction = match.groups.get("direction", "east")
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Low altitude for inspection
        alt_m = constraints.min_altitude_m_agl + 3
        alt_m = min(alt_m, constraints.max_altitude_m_amsl - 10)
        
        # Calculate approach based on face/direction
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        
        offset_m = 15  # Distance from structure for inspection
        
        if direction == "north":
            approach = Point(lat=center_lat + offset_m * lat_deg_per_m, lon=center_lon)
            inspect = Point(lat=center_lat - 5 * lat_deg_per_m, lon=center_lon)
        elif direction == "south":
            approach = Point(lat=center_lat - offset_m * lat_deg_per_m, lon=center_lon)
            inspect = Point(lat=center_lat + 5 * lat_deg_per_m, lon=center_lon)
        elif direction == "east":
            approach = Point(lat=center_lat, lon=center_lon + offset_m * lon_deg_per_m)
            inspect = Point(lat=center_lat, lon=center_lon - 5 * lon_deg_per_m)
        else:  # west
            approach = Point(lat=center_lat, lon=center_lon - offset_m * lon_deg_per_m)
            inspect = Point(lat=center_lat, lon=center_lon + 5 * lon_deg_per_m)
        
        waypoints = [
            Waypoint(point=approach, alt_m=alt_m, alt_frame="amsl",
                    speed_m_s=2.0, action=WaypointAction.FLY_TO),
            Waypoint(point=inspect, alt_m=alt_m, alt_frame="amsl",
                    speed_m_s=1.0, hold_s=5.0, action=WaypointAction.PHOTO),
            Waypoint(point=approach, alt_m=alt_m, alt_frame="amsl",
                    speed_m_s=3.0, action=WaypointAction.FLY_TO),
        ]
        
        return Mission(
            version="1.0",
            name=f"inspect_{face}_{name}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="inspection_pass",
                    params={"face": face, "direction": direction},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=30.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (
    OrbitPattern, PerimeterPattern, LawnmowerPattern,
    RevealPattern, EstablishPattern, FollowPattern, InspectPattern
)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_inspect.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_inspect.py && git commit -m "feat(mission_intel): add InspectPattern for structure inspection missions"

---

### Task D8.17: `TransectPattern` (`id="transect"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_transect.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_transect.py
import pytest
import re
from avatar.mission_intel.intent_planner import TransectPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3970, west=8.5450, north=47.3980, east=8.5460)  # ~100m x 100m


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "transect the plot every 20 m"
def test_transect_match_every_spacing(bbox, constraints):
    text = "transect the plot every 20 m"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = TransectPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "transect"
    assert m.groups["spacing_m"] == "20"
    assert m.groups.get("name") == "plot"
    
    mission = TransectPattern().emit(m, bbox, constraints)
    assert "transect" in mission.name
    assert len(mission.waypoints) >= 10  # Multiple parallel lines
    assert all(wp.action == WaypointAction.PHOTO for wp in mission.waypoints)
    assert mission.cinematic_blocks[0].template_id == "transect_pass"


# Positive case 2: "parallel lines across the field every 15m"
def test_transect_match_parallel_lines(bbox, constraints):
    text = "parallel lines across the field every 15m"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = TransectPattern.match(toks)
    assert m is not None
    assert m.groups["spacing_m"] == "15"
    assert m.groups.get("name") == "field"
    
    mission = TransectPattern().emit(m, bbox, constraints)
    # Should generate more lines with tighter spacing
    expected_lines = int(100 / 15) * 2  # Approximate
    assert len(mission.waypoints) >= expected_lines


# Negative case 1: "lawnmower the plot" - wrong pattern (lawnmower)
def test_transect_negative_wrong_pattern(bbox, constraints):
    text = "lawnmower the plot with 80% overlap"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = TransectPattern.match(toks)
    assert m is None  # "transect" keyword missing


# Negative case 2: "transect the area" - missing spacing specification
def test_transect_negative_missing_spacing(bbox, constraints):
    text = "transect the area"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = TransectPattern.match(toks)
    assert m is None  # No spacing specification


# Parser registration test
def test_transect_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, TransectPattern
    assert TransectPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_transect.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class TransectPattern(Pattern):
    """
    Grammar: transect <name> every|spacing <distance>m
    
    Examples:
        "transect the plot every 20 m"
        "parallel lines across the field every 15m"
        "transect zone alpha spacing 25 meters"
    """
    id = "transect"
    
    _PATTERN = re.compile(
        r"(?:transect|parallel\s+lines(?:\s+across)?)\s+(?:the\s+)?(.+?)\s+(?:every|spacing)\s+(?P<d>\d+(?:\.\d+)?)\s*(?:m|meters?)?",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            name = m.group(1).strip()
            spacing_m = m.group("d")
            return Match(pattern_id=cls.id, groups={"name": name, "spacing_m": spacing_m})
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        name = match.groups["name"]
        spacing_m = float(match.groups["spacing_m"])
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Altitude for transect (moderate)
        alt_m = constraints.min_altitude_m_agl + 10
        alt_m = min(alt_m, constraints.max_altitude_m_amsl - 20)
        
        # Calculate number of transects
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        
        bbox_height_m = haversine_m(
            Point(lat=bbox.south, lon=center_lon),
            Point(lat=bbox.north, lon=center_lon)
        )
        
        num_transects = max(2, int(bbox_height_m / spacing_m) + 1)
        
        waypoints = []
        for i in range(num_transects):
            # Alternating direction
            direction = 1 if i % 2 == 0 else -1
            
            lat = bbox.south + (bbox.north - bbox.south) * i / (num_transects - 1)
            
            start_lon = bbox.west if direction == 1 else bbox.east
            end_lon = bbox.east if direction == 1 else bbox.west
            
            wp_start = Waypoint(
                point=Point(lat=lat, lon=start_lon),
                alt_m=alt_m,
                alt_frame="amsl",
                speed_m_s=5.0,
                action=WaypointAction.PHOTO
            )
            wp_end = Waypoint(
                point=Point(lat=lat, lon=end_lon),
                alt_m=alt_m,
                alt_frame="amsl",
                speed_m_s=5.0,
                action=WaypointAction.PHOTO
            )
            waypoints.extend([wp_start, wp_end])
        
        return Mission(
            version="1.0",
            name=f"transect_{name}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="transect_pass",
                    params={"spacing_m": spacing_m, "num_transects": num_transects},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (
    OrbitPattern, PerimeterPattern, LawnmowerPattern,
    RevealPattern, EstablishPattern, FollowPattern, 
    InspectPattern, TransectPattern
)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_transect.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_transect.py && git commit -m "feat(mission_intel): add TransectPattern for scientific transect missions"

---

### Task D8.18: `PhotoGridPattern` (`id="photo_grid"`)

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_photo_grid.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_photo_grid.py
import pytest
import re
from avatar.mission_intel.intent_planner import PhotoGridPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3970, west=8.5450, north=47.3980, east=8.5460)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "photo grid of the site at 50 m AGL"
def test_photo_grid_match_with_agl(bbox, constraints):
    text = "photo grid of the site at 50 m AGL"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PhotoGridPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "photo_grid"
    assert m.groups["agl_m"] == "50"
    assert m.groups.get("name") == "site"
    
    mission = PhotoGridPattern().emit(m, bbox, constraints)
    assert "photo_grid" in mission.name
    assert len(mission.waypoints) >= 9  # 3x3 grid minimum
    assert all(wp.action == WaypointAction.PHOTO for wp in mission.waypoints)
    assert all(wp.alt_m == 50.0 for wp in mission.waypoints)
    assert mission.cinematic_blocks[0].template_id == "photo_grid"


# Positive case 2: "photo grid at 40m agl of the roof"
def test_photo_grid_match_alt_format(bbox, constraints):
    text = "photo grid at 40m agl of the roof"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PhotoGridPattern.match(toks)
    assert m is not None
    assert m.groups["agl_m"] == "40"
    assert m.groups.get("name") == "roof"
    
    mission = PhotoGridPattern().emit(m, bbox, constraints)
    assert all(wp.alt_m == 40.0 for wp in mission.waypoints)


# Negative case 1: "photo only" - missing grid keyword
def test_photo_grid_negative_missing_grid(bbox, constraints):
    text = "photo only the site"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PhotoGridPattern.match(toks)
    assert m is None  # "grid" keyword missing


# Negative case 2: "photo grid of the site" - missing AGL specification
def test_photo_grid_negative_missing_agl(bbox, constraints):
    text = "photo grid of the site"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = PhotoGridPattern.match(toks)
    assert m is None  # No AGL altitude specified


# Parser registration test
def test_photo_grid_in_parser_priority():
    from avatar.mission_intel.intent_planner import Parser, PhotoGridPattern
    assert PhotoGridPattern in Parser.PRIORITY
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_photo_grid.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class PhotoGridPattern(Pattern):
    """
    Grammar: photo grid [of] <name> at <agl_m> m [agl]
    
    Examples:
        "photo grid of the site at 50 m AGL"
        "photo grid at 40m agl of the roof"
    """
    id = "photo_grid"
    
    _PATTERN = re.compile(
        r"photo\s+grid(?:\s+of)?(?:\s+the\s+)?(.+?)\s+at\s+(?P<agl>\d+(?:\.\d+)?)\s*(?:m)?\s*(?:agl)?",
        re.IGNORECASE
    )
    
    _ALT_PATTERN = re.compile(
        r"photo\s+grid\s+at\s+(?P<agl>\d+(?:\.\d+)?)\s*(?:m)?\s*(?:agl)?(?:\s+of)?(?:\s+the\s+)?(.+?)$",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        
        # Try primary pattern
        m = cls._PATTERN.search(text)
        if m:
            name = m.group(1).strip()
            agl_m = m.group("agl")
            return Match(pattern_id=cls.id, groups={"name": name, "agl_m": agl_m})
        
        # Try alternative pattern
        m = cls._ALT_PATTERN.search(text)
        if m:
            agl_m = m.group("agl")
            name = m.group(2).strip() if m.group(2) else "area"
            return Match(pattern_id=cls.id, groups={"name": name, "agl_m": agl_m})
        
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        name = match.groups["name"]
        agl_m = float(match.groups["agl_m"])
        
        # Validate AGL is above minimum
        agl_m = max(agl_m, constraints.min_altitude_m_agl)
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        # Calculate grid parameters
        # Assume camera FOV ~70 degrees, coverage at altitude = 2 * agl * tan(35deg)
        coverage_m = 2 * agl_m * math.tan(math.radians(35))
        overlap = 0.3  # 30% overlap for photo grid
        spacing_m = coverage_m * (1 - overlap)
        
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))
        
        # Calculate bbox dimensions
        bbox_height_m = haversine_m(
            Point(lat=bbox.south, lon=center_lon),
            Point(lat=bbox.north, lon=center_lon)
        )
        bbox_width_m = haversine_m(
            Point(lat=center_lat, lon=bbox.west),
            Point(lat=center_lat, lon=bbox.east)
        )
        
        # Calculate grid size
        grid_rows = max(2, int(bbox_height_m / spacing_m) + 1)
        grid_cols = max(2, int(bbox_width_m / spacing_m) + 1)
        
        waypoints = []
        for row in range(grid_rows):
            direction = 1 if row % 2 == 0 else -1  # Alternating
            lat = bbox.south + (bbox.north - bbox.south) * row / (grid_rows - 1)
            
            for col in range(grid_cols):
                if direction == 1:
                    lon = bbox.west + (bbox.east - bbox.west) * col / (grid_cols - 1)
                else:
                    lon = bbox.east - (bbox.east - bbox.west) * col / (grid_cols - 1)
                
                wp = Waypoint(
                    point=Point(lat=lat, lon=lon),
                    alt_m=agl_m,
                    alt_frame="agl",
                    speed_m_s=3.0,
                    hold_s=1.0,  # Brief pause for photo
                    action=WaypointAction.PHOTO
                )
                waypoints.append(wp)
        
        return Mission(
            version="1.0",
            name=f"photo_grid_{name}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="photo_grid",
                    params={"agl_m": agl_m, "grid_rows": grid_rows, "grid_cols": grid_cols},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )
```

- [ ] **Step 4: Update Parser.PRIORITY** (temporary):

```python
PRIORITY: tuple[type[Pattern], ...] = (
    OrbitPattern, PerimeterPattern, LawnmowerPattern,
    RevealPattern, EstablishPattern, FollowPattern, 
    InspectPattern, TransectPattern, PhotoGridPattern
)
```

- [ ] **Step 5: Run test** — `pytest tests/mission_intel/test_intent_photo_grid.py -v` → 5 passed.

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_photo_grid.py && git commit -m "feat(mission_intel): add PhotoGridPattern for grid-based photography missions"

---

### Task D8.19: `HoverAtPattern` (`id="hover_at"`) + finalize `Parser.PRIORITY`

**Files:** Modify: `avatar/mission_intel/intent_planner.py` — Create: `tests/mission_intel/test_intent_hover_at.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mission_intel/test_intent_hover_at.py
import pytest
import re
from avatar.mission_intel.intent_planner import HoverAtPattern, Parser
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, WaypointAction


@pytest.fixture
def bbox():
    return BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457)


@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=5.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )


# Positive case 1: "hover at the helipad for 20 seconds at 10 meters"
def test_hover_at_match_full_spec(bbox, constraints):
    text = "hover at the helipad for 20 seconds at 10 meters"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = HoverAtPattern.match(toks)
    assert m is not None
    assert m.pattern_id == "hover_at"
    assert m.groups.get("duration_s") == "20"
    assert m.groups.get("altitude_m") == "10"
    assert m.groups.get("name") == "helipad"
    
    mission = HoverAtPattern().emit(m, bbox, constraints)
    assert "hover" in mission.name
    assert len(mission.waypoints) == 1
    assert mission.waypoints[0].action == WaypointAction.HOVER
    assert mission.waypoints[0].hold_s == 20.0
    assert mission.waypoints[0].alt_m == 10.0


# Positive case 2: "hover for 30s at 15m"
def test_hover_at_match_compact_format(bbox, constraints):
    text = "hover for 30s at 15m"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = HoverAtPattern.match(toks)
    assert m is not None
    assert m.groups.get("duration_s") == "30"
    assert m.groups.get("altitude_m") == "15"
    
    mission = HoverAtPattern().emit(m, bbox, constraints)
    assert mission.waypoints[0].hold_s == 30.0
    assert mission.waypoints[0].alt_m == 15.0


# Negative case 1: "hover there" - missing duration and altitude
def test_hover_at_negative_missing_params(bbox, constraints):
    text = "hover there"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = HoverAtPattern.match(toks)
    assert m is None  # Missing both duration and altitude


# Negative case 2: "fly over the helipad" - wrong action verb
def test_hover_at_negative_wrong_verb(bbox, constraints):
    text = "fly over the helipad"
    toks = [t for t in re.split(r"[^a-zA-Z0-9_.-]+", text.lower()) if t]
    m = HoverAtPattern.match(toks)
    assert m is None  # "hover" keyword missing


# Parser PRIORITY order test - HoverAtPattern should be first
def test_hover_at_is_first_in_priority():
    from avatar.mission_intel.intent_planner import Parser, HoverAtPattern
    assert Parser.PRIORITY[0] == HoverAtPattern


# Verify all patterns are registered
def test_all_patterns_in_priority():
    from avatar.mission_intel.intent_planner import (
        Parser, HoverAtPattern, OrbitPattern, PerimeterPattern,
        LawnmowerPattern, RevealPattern, EstablishPattern,
        FollowPattern, InspectPattern, TransectPattern, PhotoGridPattern
    )
    expected = (
        HoverAtPattern, OrbitPattern, PerimeterPattern,
        LawnmowerPattern, RevealPattern, EstablishPattern,
        FollowPattern, InspectPattern, TransectPattern, PhotoGridPattern
    )
    assert Parser.PRIORITY == expected
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mission_intel/test_intent_hover_at.py -v` → import errors.

- [ ] **Step 3: Implement** (add to `intent_planner.py`):

```python
class HoverAtPattern(Pattern):
    """
    Grammar: hover [at] [the] <name> [for] <duration>s [at] <altitude>m
    
    Examples:
        "hover at the helipad for 20 seconds at 10 meters"
        "hover for 30s at 15m"
        "hover at the marker for 60 seconds at 25 meters altitude"
    """
    id = "hover_at"
    
    _PATTERN = re.compile(
        r"hover(?:\s+at)?(?:\s+the\s+)?(.+?)?(?:\s+for\s+(?P<n>\d+)\s*(?:s|sec|seconds?))?(?:\s+at\s+(?P<h>\d+)\s*(?:m|meters?))?(?:\s+altitude)?",
        re.IGNORECASE
    )
    
    @classmethod
    def match(cls, tokens: list[str]) -> Match | None:
        text = " ".join(tokens)
        m = cls._PATTERN.search(text)
        if m:
            name = m.group(1).strip() if m.group(1) else "location"
            duration_s = m.group("n")
            altitude_m = m.group("h")
            
            # Must have at least one of duration or altitude
            if duration_s or altitude_m:
                groups = {"name": name}
                if duration_s:
                    groups["duration_s"] = duration_s
                if altitude_m:
                    groups["altitude_m"] = altitude_m
                return Match(pattern_id=cls.id, groups=groups)
        return None
    
    def emit(self, match: Match, bbox: BBox, constraints: MissionConstraints) -> Mission:
        name = match.groups["name"]
        duration_s = float(match.groups.get("duration_s", 30))
        altitude_m = float(match.groups.get("altitude_m", constraints.min_altitude_m_agl + 5))
        
        # Enforce altitude constraints
        altitude_m = max(altitude_m, constraints.min_altitude_m_agl)
        altitude_m = min(altitude_m, constraints.max_altitude_m_amsl - 10)
        
        center_lat = (bbox.south + bbox.north) / 2
        center_lon = (bbox.west + bbox.east) / 2
        center = Point(lat=center_lat, lon=center_lon)
        
        waypoints = [
            Waypoint(
                point=center,
                alt_m=altitude_m,
                alt_frame="amsl",
                speed_m_s=3.0,
                hold_s=duration_s,
                action=WaypointAction.HOVER
            )
        ]
        
        return Mission(
            version="1.0",
            name=f"hover_{name}",
            home=center,
            constraints=constraints,
            waypoints=waypoints,
            cinematic_blocks=[
                CinematicInvocation(
                    template_id="hover_hold",
                    params={"duration_s": duration_s, "altitude_m": altitude_m},
                    starts_at_waypoint=0
                )
            ],
            safety=SafetyPolicy(
                geofence=None,
                rth_altitude_m_amsl=50.0,
                comms_loss_action="rtl"
            )
        )


# Final Parser.PRIORITY - exact order as specified
class Parser:
    """
    Intent parser for mission planning from natural language.
    
    Priority order (first match wins):
    1. HoverAtPattern - "hover at the helipad for 20 seconds at 10 meters"
    2. OrbitPattern - "orbit the tower at 25 meters for 60 seconds"
    3. PerimeterPattern - "fly the perimeter of the field"
    4. LawnmowerPattern - "survey the field with 80% overlap"
    5. RevealPattern - "reveal the barn from the west"
    6. EstablishPattern - "establishing shot of the stadium"
    7. FollowPattern - "follow the runner"
    8. InspectPattern - "inspect the roof of the building"
    9. TransectPattern - "transect the plot every 20 m"
    10. PhotoGridPattern - "photo grid of the site at 50 m AGL"
    """
    PRIORITY: tuple[type[Pattern], ...] = (
        HoverAtPattern,
        OrbitPattern,
        PerimeterPattern,
        LawnmowerPattern,
        RevealPattern,
        EstablishPattern,
        FollowPattern,
        InspectPattern,
        TransectPattern,
        PhotoGridPattern,
    )
    
    def parse(self, text: str) -> Match:
        tokens = _tokenize(text)
        for cls in self.PRIORITY:
            m = cls.match(tokens)
            if m:
                return m
        raise MissionSpecError(suggestions=_suggestions(tokens))
```

- [ ] **Step 4: Run test** — `pytest tests/mission_intel/test_intent_hover_at.py -v` → 7 passed.

- [ ] **Step 5: Run all pattern tests** — `pytest tests/mission_intel/test_intent_*.py -v` → 52 passed (10 patterns x 5 tests each + 2 priority tests).

- [ ] **Step 6: Commit** — `git add avatar/mission_intel/intent_planner.py tests/mission_intel/test_intent_hover_at.py && git commit -m "feat(mission_intel): add HoverAtPattern and finalize Parser.PRIORITY order"

---

### Task D8.20: `safety_checks.py`

**Files:**
- Create: `avatar/mission_intel/safety_checks.py`
- Create: `tests/mission_intel/test_safety_checks.py`

Functions:

```python
def geofence_overlaps_route(poly: Polygon | None, waypoints: list[Point]) -> bool: ...
def min_agl_violations(terrain_elev_fn, waypoints: list[tuple[Point, float]], frame: Literal["amsl","agl","relative"]) -> list[int]: ...
def battery_feasible(distance_m: float, hover_s: float, airframe_efficiency_wh_per_km: float, battery_wh_remaining: float, floor_pct: float) -> bool: ...
```

- [ ] **Commit** — `feat(mission_intel): add safety_checks for geofence AGL and battery`

---

### Task D8.21: `mission_spec.py` — Mission v1.0 + `.plan` serializer

**Files:**
- Create: `avatar/mission_intel/mission_spec.py`
- Create: `tests/mission_intel/test_mission_spec_plan_serializer.py`

**Complete models (single source of truth):**

```python
from __future__ import annotations
from typing import Literal
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from avatar.mission_intel.geo import Point, Polygon

class WaypointAction(str, Enum):
    FLY_TO = "fly_to"
    HOVER = "hover"
    ORBIT = "orbit"
    PHOTO = "photo"

class MissionConstraints(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_altitude_m_amsl: float
    min_altitude_m_agl: float
    max_distance_from_home_m: float
    max_flight_time_s: float
    battery_floor_pct: float

class Waypoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    point: Point
    alt_m: float
    alt_frame: Literal["amsl", "agl", "relative"]
    speed_m_s: float
    heading_deg: float | None = None
    hold_s: float = 0.0
    action: WaypointAction = WaypointAction.FLY_TO

class CinematicInvocation(BaseModel):
    model_config = ConfigDict(frozen=True)
    template_id: str
    params: dict[str, float | str | int | bool]
    starts_at_waypoint: int = Field(..., ge=0)

class SafetyPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    geofence: Polygon | None = None
    rth_altitude_m_amsl: float
    comms_loss_action: Literal["rtl", "land", "hold"]

class Mission(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: Literal["1.0"] = "1.0"
    name: str
    home: Point
    constraints: MissionConstraints
    waypoints: list[Waypoint]
    cinematic_blocks: list[CinematicInvocation] = Field(default_factory=list)
    safety: SafetyPolicy

def mission_to_px4_plan_json(m: Mission) -> dict:
    """Emit QGC WPL 100-equivalent minimal plan dict for tests."""
    ...
```

- [ ] **Commit** — `feat(mission_intel): add Mission v1.0 schema and PX4 plan serializer`

---

### Task D8.22: MCP tool `analyze_area`

**Files:**
- Create: `avatar/mcp_server/tools/mission_intel_tools.py`
- Create: `tests/mcp_server/test_mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mcp_server/test_mission_intel_tools.py
import pytest
from pydantic import BaseModel
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.area_analyzer import AreaReport


# Positive case 1: analyze_area returns valid report with all required fields
@pytest.mark.asyncio
async def test_analyze_area_returns_valid_report():
    from avatar.mcp_server.tools.mission_intel_tools import handle_analyze_area, AnalyzeAreaInput
    
    input_data = AnalyzeAreaInput(
        bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
        intent="general"
    )
    
    result = await handle_analyze_area(input_data)
    
    assert result is not None
    assert result.bbox is not None
    assert result.terrain is not None
    assert result.terrain.mean_elevation_m_amsl is not None
    assert result.built_environment is not None
    assert isinstance(result.pois, list)
    assert isinstance(result.hazards, list)
    assert len(result.recommended_altitude_band_m_agl) == 2


# Positive case 2: analyze_area with cinematic intent returns scenic POIs
@pytest.mark.asyncio
async def test_analyze_area_cinematic_intent():
    from avatar.mcp_server.tools.mission_intel_tools import handle_analyze_area, AnalyzeAreaInput
    
    input_data = AnalyzeAreaInput(
        bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
        intent="cinematic"
    )
    
    result = await handle_analyze_area(input_data)
    
    # Cinematic intent should prioritize viewpoint/water POIs
    assert result is not None
    if result.pois:
        poi_kinds = [p.kind for p in result.pois]
        assert any(k in poi_kinds for k in ["viewpoint", "water", "landmark"])


# Negative case 1: analyze_area with invalid bbox should raise validation error
def test_analyze_area_invalid_bbox():
    from avatar.mcp_server.tools.mission_intel_tools import AnalyzeAreaInput
    
    with pytest.raises(ValueError) as exc_info:
        AnalyzeAreaInput(
            bbox=BBox(south=47.0, west=8.0, north=46.0, east=9.0),  # Invalid: south > north
            intent="general"
        )
    assert "south" in str(exc_info.value).lower() or "north" in str(exc_info.value).lower()


# Negative case 2: analyze_area with unknown intent should use fallback
@pytest.mark.asyncio
async def test_analyze_area_unknown_intent_fallback():
    from avatar.mcp_server.tools.mission_intel_tools import handle_analyze_area, AnalyzeAreaInput
    
    input_data = AnalyzeAreaInput(
        bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
        intent="unknown_intent_value"  # Should fallback to general
    )
    
    # Should not raise, should return general report
    result = await handle_analyze_area(input_data)
    assert result is not None
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_analyze_area -v` → import errors.

- [ ] **Step 3: Implement**

```python
# avatar/mcp_server/tools/mission_intel_tools.py
"""
Mission Intelligence MCP Tools
Read-only tools for area analysis, place lookup, elevation, and mission planning.
"""

from __future__ import annotations

from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

from avatar.mission_intel.geo import BBox, Point
from avatar.mission_intel.area_analyzer import AreaReport, analyze_area
from avatar.mission_intel.config import MissionIntelConfig


class AnalyzeAreaInput(BaseModel):
    """Input for analyze_area tool."""
    model_config = ConfigDict(extra="forbid")
    
    bbox: BBox = Field(..., description="Bounding box to analyze")
    intent: Literal["cinematic", "survey", "inspection", "general"] = Field(
        default="general",
        description="Analysis intent affecting POI ranking and recommendations"
    )
    include_satellite: bool = Field(
        default=True,
        description="Include satellite imagery if GMaps available"
    )


class AnalyzeAreaOutput(BaseModel):
    """Output from analyze_area tool."""
    model_config = ConfigDict(extra="forbid")
    
    report: AreaReport
    cache_hit: bool = False
    sources_used: list[str] = Field(default_factory=list)


async def handle_analyze_area(input_data: AnalyzeAreaInput) -> AreaReport:
    """
    Analyze an area and return terrain, POIs, hazards, and recommendations.
    
    This is a read-only, open-world tool that does not command the drone.
    Uses OSM + SRTM offline; GMaps for satellite if API key present.
    """
    config = MissionIntelConfig()
    
    # Run analysis
    report = await analyze_area(
        bbox=input_data.bbox,
        intent=input_data.intent,
        config=config,
        include_satellite=input_data.include_satellite
    )
    
    return report


def get_analyze_area_schema() -> dict[str, Any]:
    """Return JSON schema for analyze_area tool registration."""
    return {
        "name": "analyze_area",
        "description": "Analyze a geographic area and return terrain stats, POIs, hazards, and recommended altitude band. Read-only, open-world tool.",
        "inputSchema": AnalyzeAreaInput.model_json_schema(),
        "outputSchema": AnalyzeAreaOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet (add to register_all_tools)

from avatar.mcp_server.tools.mission_intel_tools import (
    get_analyze_area_schema,
    handle_analyze_area,
    AnalyzeAreaInput,
)

# In register_all_tools() method:
def register_all_tools(self) -> None:
    # ... existing tools ...
    
    # Mission Intel Tools
    self.register_tool(
        name="analyze_area",
        schema=get_analyze_area_schema(),
        handler=handle_analyze_area,
        input_model=AnalyzeAreaInput,
        category="mission_intel",
    )
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_analyze_area -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add analyze_area mission intel tool with schema"

---

### Task D8.23: MCP tool `lookup_place`

**Files:**
- Modify: `avatar/mcp_server/tools/mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/mcp_server/test_mission_intel_tools.py

from avatar.mission_intel.geo import Point
from avatar.mission_intel.area_analyzer import POI


# Positive case 1: lookup_place returns matching POIs
@pytest.mark.asyncio
async def test_lookup_place_returns_pois():
    from avatar.mcp_server.tools.mission_intel_tools import handle_lookup_place, LookupPlaceInput
    
    input_data = LookupPlaceInput(
        query="stadium",
        near=Point(lat=47.3977, lon=8.5456),
        radius_m=1000
    )
    
    result = await handle_lookup_place(input_data)
    
    assert isinstance(result, list)
    # May be empty in offline mode, but structure should be valid
    for poi in result:
        assert isinstance(poi, POI)
        assert poi.id is not None
        assert poi.name is not None
        assert poi.point is not None


# Positive case 2: lookup_place without near point uses bbox only
@pytest.mark.asyncio
async def test_lookup_place_without_near():
    from avatar.mcp_server.tools.mission_intel_tools import handle_lookup_place, LookupPlaceInput
    
    input_data = LookupPlaceInput(
        query="cafe",
        near=None,
        radius_m=500
    )
    
    result = await handle_lookup_place(input_data)
    
    assert isinstance(result, list)


# Negative case 1: lookup_place with empty query should error
def test_lookup_place_empty_query():
    from avatar.mcp_server.tools.mission_intel_tools import LookupPlaceInput
    
    with pytest.raises(ValueError) as exc_info:
        LookupPlaceInput(
            query="",  # Empty query
            near=Point(lat=47.3977, lon=8.5456),
            radius_m=1000
        )
    assert "query" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()


# Negative case 2: lookup_place with negative radius should error
def test_lookup_place_negative_radius():
    from avatar.mcp_server.tools.mission_intel_tools import LookupPlaceInput
    
    with pytest.raises(ValueError) as exc_info:
        LookupPlaceInput(
            query="park",
            near=Point(lat=47.3977, lon=8.5456),
            radius_m=-100  # Invalid negative radius
        )
    assert "radius" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_lookup_place -v` → import errors.

- [ ] **Step 3: Implement** (add to `mission_intel_tools.py`):

```python
class LookupPlaceInput(BaseModel):
    """Input for lookup_place tool."""
    model_config = ConfigDict(extra="forbid")
    
    query: str = Field(..., min_length=1, description="Place name or type to search for")
    near: Point | None = Field(
        default=None,
        description="Reference point for proximity search"
    )
    radius_m: int = Field(
        default=1000,
        ge=100, le=50000,
        description="Search radius in meters"
    )
    max_results: int = Field(
        default=10,
        ge=1, le=50,
        description="Maximum number of results to return"
    )


class LookupPlaceOutput(BaseModel):
    """Output from lookup_place tool."""
    model_config = ConfigDict(extra="forbid")
    
    pois: list[POI]
    source: str  # "osm", "gmaps", or "cache"
    query_normalized: str


async def handle_lookup_place(input_data: LookupPlaceInput) -> LookupPlaceOutput:
    """
    Look up places by name or type near a location.
    
    Read-only, open-world, idempotent. Uses OSM Nominatim primarily.
    GMaps Places as enrichment if API key available.
    """
    from avatar.mission_intel.providers.osm import OSMProvider
    
    config = MissionIntelConfig()
    osm = OSMProvider(config)
    
    # Search for places
    bbox = None
    if input_data.near:
        # Create bbox around near point
        lat_offset = input_data.radius_m / 111320.0
        lon_offset = input_data.radius_m / (111320.0 * abs(math.cos(math.radians(input_data.near.lat))))
        bbox = BBox(
            south=input_data.near.lat - lat_offset,
            west=input_data.near.lon - lon_offset,
            north=input_data.near.lat + lat_offset,
            east=input_data.near.lon + lon_offset
        )
    
    pois = await osm.fetch_pois(
        bbox=bbox,
        kinds=[input_data.query],
        max_results=input_data.max_results
    )
    
    return LookupPlaceOutput(
        pois=pois,
        source="osm",
        query_normalized=input_data.query.lower().strip()
    )


def get_lookup_place_schema() -> dict[str, Any]:
    """Return JSON schema for lookup_place tool registration."""
    return {
        "name": "lookup_place",
        "description": "Look up places (POIs, landmarks, businesses) by name or type near a location. Returns ranked list of points of interest with coordinates. Read-only, open-world, idempotent.",
        "inputSchema": LookupPlaceInput.model_json_schema(),
        "outputSchema": LookupPlaceOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet (add to register_all_tools)
from avatar.mcp_server.tools.mission_intel_tools import (
    get_lookup_place_schema,
    handle_lookup_place,
    LookupPlaceInput,
)

# In register_all_tools():
self.register_tool(
    name="lookup_place",
    schema=get_lookup_place_schema(),
    handler=handle_lookup_place,
    input_model=LookupPlaceInput,
    category="mission_intel",
)
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_lookup_place -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add lookup_place mission intel tool"

---

### Task D8.24: MCP tool `get_elevation`

**Files:**
- Modify: `avatar/mcp_server/tools/mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/mcp_server/test_mission_intel_tools.py


# Positive case 1: get_elevation returns valid elevation
@pytest.mark.asyncio
async def test_get_elevation_returns_value():
    from avatar.mcp_server.tools.mission_intel_tools import handle_get_elevation, GetElevationInput
    
    input_data = GetElevationInput(
        point=Point(lat=47.3977, lon=8.5456)
    )
    
    result = await handle_get_elevation(input_data)
    
    assert result is not None
    assert result.elevation_m_amsl is not None
    assert isinstance(result.elevation_m_amsl, (int, float))
    assert result.source in ["srtm", "dem_cache", "open_elevation", "gmaps"]


# Positive case 2: get_elevation for known location (Zurich ~400m)
@pytest.mark.asyncio
async def test_get_elevation_zurich_approximate():
    from avatar.mcp_server.tools.mission_intel_tools import handle_get_elevation, GetElevationInput
    
    # Zurich airport area is around 400-450m AMSL
    input_data = GetElevationInput(
        point=Point(lat=47.4647, lon=8.5492)
    )
    
    result = await handle_get_elevation(input_data)
    
    # Should be roughly 400-500m for Zurich area
    assert 300 < result.elevation_m_amsl < 600


# Negative case 1: get_elevation with invalid coordinates should error
def test_get_elevation_invalid_lat():
    from avatar.mcp_server.tools.mission_intel_tools import GetElevationInput
    
    with pytest.raises(ValueError):
        GetElevationInput(
            point=Point(lat=95.0, lon=8.5456)  # Invalid latitude > 90
        )


# Negative case 2: get_elevation with None point should error
def test_get_elevation_missing_point():
    from avatar.mcp_server.tools.mission_intel_tools import GetElevationInput
    
    with pytest.raises(ValueError) as exc_info:
        GetElevationInput(point=None)
    assert "point" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_get_elevation -v` → import errors.

- [ ] **Step 3: Implement** (add to `mission_intel_tools.py`):

```python
class GetElevationInput(BaseModel):
    """Input for get_elevation tool."""
    model_config = ConfigDict(extra="forbid")
    
    point: Point = Field(..., description="Geographic point to query elevation for")
    prefer_cache: bool = Field(
        default=True,
        description="Prefer cached DEM data over network lookup"
    )


class GetElevationOutput(BaseModel):
    """Output from get_elevation tool."""
    model_config = ConfigDict(extra="forbid")
    
    elevation_m_amsl: float = Field(..., description="Elevation above mean sea level in meters")
    source: str = Field(..., description="Data source: srtm, dem_cache, open_elevation, gmaps")
    tile_coords: tuple[int, int] | None = None
    resolution_m: float = Field(default=30.0, description="Approximate data resolution")


async def handle_get_elevation(input_data: GetElevationInput) -> GetElevationOutput:
    """
    Get ground elevation (AMSL) at a specific point.
    
    Read-only, open-world, idempotent. Uses SRTM DEM tiles (cached) or
    Open-Elevation API as fallback. No guardian/confirmation required.
    """
    from avatar.mission_intel.providers.elevation import ElevationProvider
    from avatar.mission_intel.providers.dem_cache import DEMCache
    
    config = MissionIntelConfig()
    dem_cache = DEMCache(config.dem_cache_dir)
    
    # Try local cache first
    elevation, source = await dem_cache.get_elevation(input_data.point)
    
    if elevation is not None:
        return GetElevationOutput(
            elevation_m_amsl=elevation,
            source="dem_cache",
            tile_coords=dem_cache.get_tile_coords(input_data.point),
            resolution_m=30.0
        )
    
    # Fall back to ElevationProvider (Open-Elevation or GMaps)
    provider = ElevationProvider(config)
    elevation, source = await provider.elevation_amsl(input_data.point)
    
    return GetElevationOutput(
        elevation_m_amsl=elevation,
        source=source,
        tile_coords=None,
        resolution_m=30.0 if "srtm" in source else 10.0
    )


def get_get_elevation_schema() -> dict[str, Any]:
    """Return JSON schema for get_elevation tool registration."""
    return {
        "name": "get_elevation",
        "description": "Get ground elevation (AMSL) at a specific geographic point. Uses SRTM DEM data (cached) with Open-Elevation fallback. Read-only, open-world, idempotent.",
        "inputSchema": GetElevationInput.model_json_schema(),
        "outputSchema": GetElevationOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet
from avatar.mcp_server.tools.mission_intel_tools import (
    get_get_elevation_schema,
    handle_get_elevation,
    GetElevationInput,
)

# In register_all_tools():
self.register_tool(
    name="get_elevation",
    schema=get_get_elevation_schema(),
    handler=handle_get_elevation,
    input_model=GetElevationInput,
    category="mission_intel",
)
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_get_elevation -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add get_elevation mission intel tool"

---

### Task D8.25: MCP tool `get_agl`

**Files:**
- Modify: `avatar/mcp_server/tools/mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/mcp_server/test_mission_intel_tools.py


# Positive case 1: get_agl calculates height above terrain
@pytest.mark.asyncio
async def test_get_agl_calculates_height():
    from avatar.mcp_server.tools.mission_intel_tools import handle_get_agl, GetAglInput
    
    # Aircraft at 500m AMSL over terrain at ~400m = ~100m AGL
    input_data = GetAglInput(
        point=Point(lat=47.4647, lon=8.5492),  # Zurich area
        altitude_m_amsl=500.0
    )
    
    result = await handle_get_agl(input_data)
    
    assert result is not None
    assert result.agl_m is not None
    assert result.terrain_m is not None
    assert isinstance(result.agl_m, (int, float))
    assert isinstance(result.terrain_m, (int, float))
    # AGL should be altitude minus terrain
    assert abs(result.agl_m - (input_data.altitude_m_amsl - result.terrain_m)) < 0.1


# Positive case 2: get_agl at ground level
@pytest.mark.asyncio
async def test_get_agl_at_ground():
    from avatar.mcp_server.tools.mission_intel_tools import handle_get_agl, GetAglInput
    
    # Aircraft at exactly terrain elevation should give ~0 AGL
    input_data = GetAglInput(
        point=Point(lat=47.3977, lon=8.5456),
        altitude_m_amsl=400.0  # Assume terrain ~400m
    )
    
    result = await handle_get_agl(input_data)
    
    # AGL should be close to 0 (within tolerance)
    assert abs(result.agl_m) < 50  # Within 50m tolerance for test


# Negative case 1: get_agl with altitude below terrain should give negative AGL
def test_get_agl_below_terrain():
    from avatar.mcp_server.tools.mission_intel_tools import GetAglInput
    
    input_data = GetAglInput(
        point=Point(lat=47.3977, lon=8.5456),
        altitude_m_amsl=100.0  # Likely below terrain
    )
    
    # Model should validate and allow (negative AGL is valid for collision detection)
    assert input_data.altitude_m_amsl == 100.0


# Negative case 2: get_agl with missing altitude should error
def test_get_agl_missing_altitude():
    from avatar.mcp_server.tools.mission_intel_tools import GetAglInput
    
    with pytest.raises(ValueError):
        GetAglInput(
            point=Point(lat=47.3977, lon=8.5456),
            altitude_m_amsl=None  # type: ignore - altitude required
        )
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_get_agl -v` → import errors.

- [ ] **Step 3: Implement** (add to `mission_intel_tools.py`):

```python
class GetAglInput(BaseModel):
    """Input for get_agl tool."""
    model_config = ConfigDict(extra="forbid")
    
    point: Point = Field(..., description="Geographic point (lat/lon)")
    altitude_m_amsl: float = Field(
        ...,
        description="Current aircraft altitude above mean sea level (meters)"
    )


class GetAglOutput(BaseModel):
    """Output from get_agl tool."""
    model_config = ConfigDict(extra="forbid")
    
    agl_m: float = Field(..., description="Height above ground level (meters)")
    terrain_m: float = Field(..., description="Ground elevation at point (meters AMSL)")
    altitude_m_amsl: float = Field(..., description="Input altitude (meters AMSL)")
    clearance_status: str = Field(
        default="ok",
        description="One of: ok, low (below 10m), critical (below or at terrain), unknown"
    )


async def handle_get_agl(input_data: GetAglInput) -> GetAglOutput:
    """
    Calculate height above ground level (AGL) at a point.
    
    Given aircraft altitude (AMSL) and ground elevation at a point,
    returns AGL with clearance status for safety checks.
    
    Read-only, open-world, idempotent.
    """
    from avatar.mission_intel.providers.elevation import ElevationProvider
    
    config = MissionIntelConfig()
    provider = ElevationProvider(config)
    
    # Get terrain elevation
    terrain_m, source = await provider.elevation_amsl(input_data.point)
    
    # Calculate AGL
    agl_m = input_data.altitude_m_amsl - terrain_m
    
    # Determine clearance status
    if agl_m <= 0:
        clearance_status = "critical"
    elif agl_m < 10:
        clearance_status = "low"
    else:
        clearance_status = "ok"
    
    return GetAglOutput(
        agl_m=agl_m,
        terrain_m=terrain_m,
        altitude_m_amsl=input_data.altitude_m_amsl,
        clearance_status=clearance_status
    )


def get_get_agl_schema() -> dict[str, Any]:
    """Return JSON schema for get_agl tool registration."""
    return {
        "name": "get_agl",
        "description": "Calculate height above ground level (AGL) at a geographic point. Takes aircraft altitude (AMSL) and returns AGL with clearance status for safety checks. Read-only, open-world, idempotent.",
        "inputSchema": GetAglInput.model_json_schema(),
        "outputSchema": GetAglOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": True,
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet
from avatar.mcp_server.tools.mission_intel_tools import (
    get_get_agl_schema,
    handle_get_agl,
    GetAglInput,
)

# In register_all_tools():
self.register_tool(
    name="get_agl",
    schema=get_get_agl_schema(),
    handler=handle_get_agl,
    input_model=GetAglInput,
    category="mission_intel",
)
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_get_agl -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add get_agl mission intel tool"

---

### Task D8.26: MCP tool `plan_scenic_sweep`

**Files:**
- Modify: `avatar/mcp_server/tools/mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/mcp_server/test_mission_intel_tools.py

from avatar.mission_intel.mission_spec import Mission


# Positive case 1: plan_scenic_sweep returns a valid mission
@pytest.mark.asyncio
async def test_plan_scenic_sweep_returns_mission():
    from avatar.mcp_server.tools.mission_intel_tools import handle_plan_scenic_sweep, PlanScenicSweepInput
    
    input_data = PlanScenicSweepInput(
        bbox=BBox(south=47.3977, west=8.5456, north=47.3987, east=8.5466),
        style="reveal",
        duration_s=300,
        sun_time=None
    )
    
    result = await handle_plan_scenic_sweep(input_data)
    
    assert result is not None
    assert result.mission is not None
    assert isinstance(result.mission, Mission)
    assert result.mission.version == "1.0"
    assert len(result.mission.waypoints) > 0
    assert len(result.anchors) > 0


# Positive case 2: plan_scenic_sweep with establish style
@pytest.mark.asyncio
async def test_plan_scenic_sweep_establish_style():
    from avatar.mcp_server.tools.mission_intel_tools import handle_plan_scenic_sweep, PlanScenicSweepInput
    
    input_data = PlanScenicSweepInput(
        bbox=BBox(south=47.3977, west=8.5456, north=47.3987, east=8.5466),
        style="establish",
        duration_s=180,
        sun_time="golden_hour"
    )
    
    result = await handle_plan_scenic_sweep(input_data)
    
    assert result is not None
    assert result.mission.name is not None
    assert len(result.cinematic_blocks) > 0
    # Establish style should have pull-back blocks
    block_ids = [b.template_id for b in result.cinematic_blocks]
    assert any("establish" in bid or "pullback" in bid for bid in block_ids)


# Negative case 1: plan_scenic_sweep with invalid style should error
def test_plan_scenic_sweep_invalid_style():
    from avatar.mcp_server.tools.mission_intel_tools import PlanScenicSweepInput
    
    with pytest.raises(ValueError) as exc_info:
        PlanScenicSweepInput(
            bbox=BBox(south=47.3977, west=8.5456, north=47.3987, east=8.5466),
            style="invalid_style",  # type: ignore - not in allowed values
            duration_s=300
        )
    assert "style" in str(exc_info.value).lower()


# Negative case 2: plan_scenic_sweep with too short duration should error
def test_plan_scenic_sweep_short_duration():
    from avatar.mcp_server.tools.mission_intel_tools import PlanScenicSweepInput
    
    with pytest.raises(ValueError) as exc_info:
        PlanScenicSweepInput(
            bbox=BBox(south=47.3977, west=8.5456, north=47.3987, east=8.5466),
            style="reveal",
            duration_s=10  # Too short for meaningful sweep
        )
    assert "duration" in str(exc_info.value).lower() or "minimum" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_plan_scenic_sweep -v` → import errors.

- [ ] **Step 3: Implement** (add to `mission_intel_tools.py`):

```python
class PlanScenicSweepInput(BaseModel):
    """Input for plan_scenic_sweep tool."""
    model_config = ConfigDict(extra="forbid")
    
    bbox: BBox = Field(..., description="Area to plan sweep over")
    style: Literal["reveal", "orbit", "establish"] = Field(
        ...,
        description="Cinematic style: reveal (approach and reveal), orbit (circular), establish (wide pull-back)"
    )
    duration_s: int = Field(
        ...,
        ge=60, le=1800,
        description="Total sweep duration in seconds (1-30 min)"
    )
    sun_time: str | None = Field(
        default=None,
        description="Optional sun position hint: 'golden_hour', 'midday', 'sunrise', 'sunset'"
    )
    max_anchors: int = Field(
        default=5,
        ge=1, le=10,
        description="Maximum number of scenic anchor points to include"
    )


class SweepAnchor(BaseModel):
    """Scenic anchor point for sweep planning."""
    model_config = ConfigDict(extra="forbid")
    
    anchor_point: Point
    approach_bearing_deg: float = Field(..., ge=0, le=360)
    prominence_score: float = Field(..., ge=0, le=1)
    poi_name: str | None = None


class PlanScenicSweepOutput(BaseModel):
    """Output from plan_scenic_sweep tool."""
    model_config = ConfigDict(extra="forbid")
    
    mission: Mission
    anchors: list[SweepAnchor]
    cinematic_blocks: list  # list[CinematicInvocation]
    total_distance_m: float
    estimated_duration_s: float
    safety_passed: bool
    safety_warnings: list[str] = Field(default_factory=list)


async def handle_plan_scenic_sweep(input_data: PlanScenicSweepInput) -> PlanScenicSweepOutput:
    """
    Plan a scenic sweep mission across an area with cinematic shots.
    
    Analyzes area for POIs, ranks scenic anchors, and builds a mission
    with cinematic blocks (reveal, orbit, establish) between anchors.
    
    Read-only, open-world. Does not command the drone.
    """
    from avatar.mission_intel.scenic_sweep import plan_scenic_sweep as planner
    from avatar.mission_intel.safety_checks import validate_sweep_safety
    
    # Call the planner
    sweep_plan = await planner(
        bbox=input_data.bbox,
        style=input_data.style,
        duration_budget_s=input_data.duration_s,
        sun_time=input_data.sun_time,
        max_anchors=input_data.max_anchors
    )
    
    # Validate safety
    safety_passed, warnings = await validate_sweep_safety(
        sweep_plan.mission,
        sweep_plan.anchors
    )
    
    # Convert anchors to output format
    anchors_out = [
        SweepAnchor(
            anchor_point=a.anchor_point,
            approach_bearing_deg=a.approach_bearing_deg,
            prominence_score=a.prominence_score,
            poi_name=a.poi_name if hasattr(a, 'poi_name') else None
        )
        for a in sweep_plan.anchors
    ]
    
    return PlanScenicSweepOutput(
        mission=sweep_plan.mission,
        anchors=anchors_out,
        cinematic_blocks=sweep_plan.cinematic_blocks,
        total_distance_m=sum(
            # Approximate distance calculation
            abs(wp1.point.lat - wp2.point.lat) * 111320 +
            abs(wp1.point.lon - wp2.point.lon) * 111320
            for wp1, wp2 in zip(sweep_plan.mission.waypoints[:-1], sweep_plan.mission.waypoints[1:])
        ),
        estimated_duration_s=input_data.duration_s,
        safety_passed=safety_passed,
        safety_warnings=warnings
    )


def get_plan_scenic_sweep_schema() -> dict[str, Any]:
    """Return JSON schema for plan_scenic_sweep tool registration."""
    return {
        "name": "plan_scenic_sweep",
        "description": "Plan a cinematic sweep mission across an area with scenic anchor points and cinematic shot templates (reveal, orbit, establish). Returns a complete Mission with waypoints and cinematic blocks. Read-only, open-world.",
        "inputSchema": PlanScenicSweepInput.model_json_schema(),
        "outputSchema": PlanScenicSweepOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": True,
            "idempotentHint": False,  # May vary by sun_time or random factors
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet
from avatar.mcp_server.tools.mission_intel_tools import (
    get_plan_scenic_sweep_schema,
    handle_plan_scenic_sweep,
    PlanScenicSweepInput,
)

# In register_all_tools():
self.register_tool(
    name="plan_scenic_sweep",
    schema=get_plan_scenic_sweep_schema(),
    handler=handle_plan_scenic_sweep,
    input_model=PlanScenicSweepInput,
    category="mission_intel",
)
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_plan_scenic_sweep -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add plan_scenic_sweep mission intel tool"

---

### Task D8.27: MCP tool `plan_mission_from_intent`

**Files:**
- Modify: `avatar/mcp_server/tools/mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/mcp_server/test_mission_intel_tools.py


# Positive case 1: plan_mission_from_intent parses hover command
@pytest.mark.asyncio
async def test_plan_mission_from_intent_hover():
    from avatar.mcp_server.tools.mission_intel_tools import (
        handle_plan_mission_from_intent, PlanMissionFromIntentInput
    )
    from avatar.mission_intel.mission_spec import WaypointAction
    
    input_data = PlanMissionFromIntentInput(
        intent_text="hover at the helipad for 30 seconds at 15 meters",
        bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
        constraints=MissionConstraints(
            max_altitude_m_amsl=200.0,
            min_altitude_m_agl=5.0,
            max_distance_from_home_m=500.0,
            max_flight_time_s=600.0,
            battery_floor_pct=25.0
        )
    )
    
    result = await handle_plan_mission_from_intent(input_data)
    
    assert result is not None
    assert result.mission is not None
    assert result.mission.version == "1.0"
    assert len(result.mission.waypoints) == 1
    assert result.mission.waypoints[0].action == WaypointAction.HOVER
    assert result.mission.waypoints[0].hold_s == 30.0
    assert result.mission.waypoints[0].alt_m == 15.0


# Positive case 2: plan_mission_from_intent parses orbit command
@pytest.mark.asyncio
async def test_plan_mission_from_intent_orbit():
    from avatar.mcp_server.tools.mission_intel_tools import (
        handle_plan_mission_from_intent, PlanMissionFromIntentInput
    )
    from avatar.mission_intel.mission_spec import WaypointAction
    
    input_data = PlanMissionFromIntentInput(
        intent_text="orbit the tower at 20 meters for 60 seconds",
        bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
        constraints=MissionConstraints(
            max_altitude_m_amsl=200.0,
            min_altitude_m_agl=5.0,
            max_distance_from_home_m=500.0,
            max_flight_time_s=600.0,
            battery_floor_pct=25.0
        )
    )
    
    result = await handle_plan_mission_from_intent(input_data)
    
    assert result is not None
    assert result.pattern_matched == "orbit"
    assert len(result.mission.waypoints) >= 8  # Orbit has multiple waypoints
    # All orbit waypoints should have ORBIT action
    assert all(wp.action == WaypointAction.ORBIT for wp in result.mission.waypoints)


# Negative case 1: plan_mission_from_intent with unrecognized intent raises MissionSpecError
@pytest.mark.asyncio
async def test_plan_mission_from_intent_unrecognized():
    from avatar.mcp_server.tools.mission_intel_tools import (
        handle_plan_mission_from_intent, PlanMissionFromIntentInput
    )
    from avatar.mcp_server.errors import MCPErrorCode
    
    input_data = PlanMissionFromIntentInput(
        intent_text="do something completely random and undefined",
        bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
        constraints=MissionConstraints(
            max_altitude_m_amsl=200.0,
            min_altitude_m_agl=5.0,
            max_distance_from_home_m=500.0,
            max_flight_time_s=600.0,
            battery_floor_pct=25.0
        )
    )
    
    # Should raise structured MCP error
    with pytest.raises(Exception) as exc_info:
        await handle_plan_mission_from_intent(input_data)
    
    error_str = str(exc_info.value)
    assert "MISSION_SPEC_ERROR" in error_str or "pattern" in error_str.lower()


# Negative case 2: plan_mission_from_intent with empty intent
def test_plan_mission_from_intent_empty():
    from avatar.mcp_server.tools.mission_intel_tools import PlanMissionFromIntentInput
    
    with pytest.raises(ValueError):
        PlanMissionFromIntentInput(
            intent_text="",  # Empty intent
            bbox=BBox(south=47.3977, west=8.5456, north=47.3978, east=8.5457),
            constraints=MissionConstraints(
                max_altitude_m_amsl=200.0,
                min_altitude_m_agl=5.0,
                max_distance_from_home_m=500.0,
                max_flight_time_s=600.0,
                battery_floor_pct=25.0
            )
        )
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_plan_mission_from_intent -v` → import errors.

- [ ] **Step 3: Implement** (add to `mission_intel_tools.py`):

```python
class PlanMissionFromIntentInput(BaseModel):
    """Input for plan_mission_from_intent tool."""
    model_config = ConfigDict(extra="forbid")
    
    intent_text: str = Field(
        ...,
        min_length=5,
        description="Natural language mission description (e.g., 'orbit the tower at 25m for 60s')"
    )
    bbox: BBox = Field(..., description="Bounding box defining mission area")
    constraints: MissionConstraints = Field(
        ...,
        description="Flight constraints (altitude, battery, time limits)"
    )


class PlanMissionFromIntentOutput(BaseModel):
    """Output from plan_mission_from_intent tool."""
    model_config = ConfigDict(extra="forbid")
    
    mission: Mission
    pattern_matched: str = Field(..., description="Intent pattern that matched (e.g., 'hover_at', 'orbit')")
    parsed_groups: dict[str, str] = Field(default_factory=dict, description="Pattern capture groups")
    suggestions: list[str] = Field(default_factory=list, description="Alternative phrasings if intent unclear")


async def handle_plan_mission_from_intent(
    input_data: PlanMissionFromIntentInput
) -> PlanMissionFromIntentOutput:
    """
    Parse natural language intent and generate a structured Mission.
    
    Uses deterministic grammar-based patterns (not LLM) for reliable parsing.
    Supports: hover_at, orbit, perimeter, lawnmower, reveal, establish,
    follow, inspect, transect, photo_grid.
    
    Read-only tool - does not command the drone.
    
    Raises:
        MissionSpecError: If intent cannot be parsed (maps to MCP MISSION_SPEC_ERROR)
    """
    from avatar.mission_intel.intent_planner import Parser, MissionSpecError
    
    parser = Parser()
    
    try:
        match = parser.parse(input_data.intent_text)
    except MissionSpecError as e:
        # Convert to structured MCP error
        from avatar.mcp_server.errors import MCPError, MCPErrorCode
        raise MCPError(
            code=MCPErrorCode.MISSION_SPEC_ERROR,
            message=f"Could not parse intent: {e.code}",
            recoverable=True,
            suggested_action="; ".join(e.suggestions) if e.suggestions else "Try rephrasing with pattern keywords"
        )
    
    # Get the pattern class and instantiate
    pattern_class = None
    for cls in Parser.PRIORITY:
        if cls.id == match.pattern_id:
            pattern_class = cls
            break
    
    if pattern_class is None:
        from avatar.mcp_server.errors import MCPError, MCPErrorCode
        raise MCPError(
            code=MCPErrorCode.MISSION_SPEC_ERROR,
            message=f"Pattern '{match.pattern_id}' not found in registry",
            recoverable=True
        )
    
    # Emit mission
    pattern = pattern_class()
    mission = pattern.emit(match, input_data.bbox, input_data.constraints)
    
    return PlanMissionFromIntentOutput(
        mission=mission,
        pattern_matched=match.pattern_id,
        parsed_groups=match.groups,
        suggestions=[]
    )


def get_plan_mission_from_intent_schema() -> dict[str, Any]:
    """Return JSON schema for plan_mission_from_intent tool registration."""
    return {
        "name": "plan_mission_from_intent",
        "description": "Convert natural language mission description into a structured Mission object using deterministic grammar patterns. Supports hover, orbit, perimeter, survey, reveal, follow, inspect, transect, and photo grid intents. Read-only (pure calculation).",
        "inputSchema": PlanMissionFromIntentInput.model_json_schema(),
        "outputSchema": PlanMissionFromIntentOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": False,
            "idempotentHint": True,
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet
from avatar.mcp_server.tools.mission_intel_tools import (
    get_plan_mission_from_intent_schema,
    handle_plan_mission_from_intent,
    PlanMissionFromIntentInput,
)

# In register_all_tools():
self.register_tool(
    name="plan_mission_from_intent",
    schema=get_plan_mission_from_intent_schema(),
    handler=handle_plan_mission_from_intent,
    input_model=PlanMissionFromIntentInput,
    category="mission_intel",
)
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_plan_mission_from_intent -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add plan_mission_from_intent tool with Parser integration"

---

### Task D8.28: MCP tool `propose_orbit_for_subject`

**Files:**
- Modify: `avatar/mcp_server/tools/mission_intel_tools.py`
- Modify: `avatar/mcp_server/server.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/mcp_server/test_mission_intel_tools.py


# Positive case 1: propose_orbit_for_subject returns orbit mission
@pytest.mark.asyncio
async def test_propose_orbit_for_subject_basic():
    from avatar.mcp_server.tools.mission_intel_tools import (
        handle_propose_orbit_for_subject, ProposeOrbitForSubjectInput
    )
    from avatar.mission_intel.mission_spec import WaypointAction
    
    input_data = ProposeOrbitForSubjectInput(
        subject_point=Point(lat=47.3977, lon=8.5456),
        subject_type="static_object",  # e.g., tower, statue
        clearance_radius_m=25.0,
        preferred_altitude_m=30.0,
        orbit_duration_s=60
    )
    
    result = await handle_propose_orbit_for_subject(input_data)
    
    assert result is not None
    assert result.mission is not None
    assert result.radius_m is not None
    assert result.radius_m >= input_data.clearance_radius_m
    assert len(result.mission.waypoints) >= 8
    assert all(wp.action == WaypointAction.ORBIT for wp in result.mission.waypoints)
    assert result.subject_visible_from_orbit is True


# Positive case 2: propose_orbit_for_subject for moving target
@pytest.mark.asyncio
async def test_propose_orbit_for_subject_moving():
    from avatar.mcp_server.tools.mission_intel_tools import (
        handle_propose_orbit_for_subject, ProposeOrbitForSubjectInput
    )
    
    input_data = ProposeOrbitForSubjectInput(
        subject_point=Point(lat=47.3977, lon=8.5456),
        subject_type="moving_person",  # runner, cyclist
        clearance_radius_m=15.0,  # Smaller radius for moving subject
        preferred_altitude_m=20.0,
        orbit_duration_s=45,
        subject_velocity_m_s=3.0  # 3 m/s running pace
    )
    
    result = await handle_propose_orbit_for_subject(input_data)
    
    assert result is not None
    assert result.mission is not None
    # Moving target should have larger radius for safety
    assert result.radius_m >= input_data.clearance_radius_m
    # Should include tracking guidance
    assert result.tracking_notes is not None


# Negative case 1: propose_orbit_for_subject with zero clearance should error
def test_propose_orbit_for_subject_zero_clearance():
    from avatar.mcp_server.tools.mission_intel_tools import ProposeOrbitForSubjectInput
    
    with pytest.raises(ValueError) as exc_info:
        ProposeOrbitForSubjectInput(
            subject_point=Point(lat=47.3977, lon=8.5456),
            subject_type="static_object",
            clearance_radius_m=0,  # Invalid - must be positive
            preferred_altitude_m=30.0,
            orbit_duration_s=60
        )
    assert "radius" in str(exc_info.value).lower() or "clearance" in str(exc_info.value).lower()


# Negative case 2: propose_orbit_for_subject with altitude too low should error
def test_propose_orbit_for_subject_low_altitude():
    from avatar.mcp_server.tools.mission_intel_tools import ProposeOrbitForSubjectInput
    
    with pytest.raises(ValueError) as exc_info:
        ProposeOrbitForSubjectInput(
            subject_point=Point(lat=47.3977, lon=8.5456),
            subject_type="static_object",
            clearance_radius_m=20.0,
            preferred_altitude_m=2.0,  # Too low - below safe minimum
            orbit_duration_s=60
        )
    assert "altitude" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test (expect fail)** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_propose_orbit_for_subject -v` → import errors.

- [ ] **Step 3: Implement** (add to `mission_intel_tools.py`):

```python
class ProposeOrbitForSubjectInput(BaseModel):
    """Input for propose_orbit_for_subject tool."""
    model_config = ConfigDict(extra="forbid")
    
    subject_point: Point = Field(..., description="Subject location to orbit around")
    subject_type: Literal[
        "static_object", "building", "tower", "statue",
        "moving_person", "runner", "cyclist", "vehicle"
    ] = Field(
        ...,
        description="Type of subject affects orbit radius and safety margins"
    )
    clearance_radius_m: float = Field(
        ...,
        ge=5, le=200,
        description="Minimum safe clearance from subject in meters"
    )
    preferred_altitude_m: float = Field(
        ...,
        ge=10, le=120,
        description="Desired orbit altitude AGL"
    )
    orbit_duration_s: int = Field(
        default=60,
        ge=10, le=600,
        description="Duration to orbit in seconds"
    )
    subject_velocity_m_s: float = Field(
        default=0.0,
        ge=0, le=30,
        description="If subject moving, velocity for lead calculation"
    )
    camera_fov_deg: float = Field(
        default=70.0,
        ge=40, le=120,
        description="Camera field of view for framing calculation"
    )


class ProposeOrbitForSubjectOutput(BaseModel):
    """Output from propose_orbit_for_subject tool."""
    model_config = ConfigDict(extra="forbid")
    
    mission: Mission
    radius_m: float = Field(..., description="Calculated orbit radius")
    altitude_m: float = Field(..., description="Orbit altitude AMSL")
    subject_visible_from_orbit: bool = True
    framing_quality: str = Field(..., description="One of: excellent, good, fair, poor")
    tracking_notes: str | None = None
    safety_warnings: list[str] = Field(default_factory=list)


async def handle_propose_orbit_for_subject(
    input_data: ProposeOrbitForSubjectInput
) -> ProposeOrbitForSubjectOutput:
    """
    Propose an orbit mission around a subject (static or moving).
    
    Calculates optimal orbit radius based on subject size, clearance,
    and camera FOV for good framing. Includes safety margins for
    moving subjects.
    
    Read-only tool - does not command the drone.
    """
    from avatar.mission_intel.intent_planner import OrbitPattern, Match
    from avatar.mission_intel.safety_checks import check_orbit_safety
    import math
    
    # Calculate actual orbit radius
    # Base radius is clearance + buffer for subject type
    subject_buffers = {
        "static_object": 5.0,
        "building": 10.0,
        "tower": 8.0,
        "statue": 3.0,
        "moving_person": 8.0,
        "runner": 8.0,
        "cyclist": 10.0,
        "vehicle": 15.0,
    }
    buffer_m = subject_buffers.get(input_data.subject_type, 5.0)
    
    # Add velocity-based lead for moving subjects
    velocity_buffer = 0.0
    if input_data.subject_velocity_m_s > 0:
        # 3-second lead at subject velocity
        velocity_buffer = input_data.subject_velocity_m_s * 3.0
    
    orbit_radius_m = input_data.clearance_radius_m + buffer_m + velocity_buffer
    
    # Check camera framing
    # At distance R with FOV theta, subject height visible = 2 * R * tan(theta/2)
    fov_rad = math.radians(input_data.camera_fov_deg)
    visible_height_at_radius = 2 * orbit_radius_m * math.tan(fov_rad / 2)
    
    # Assume typical subject heights
    subject_heights = {
        "static_object": 5.0,
        "building": 20.0,
        "tower": 30.0,
        "statue": 3.0,
        "moving_person": 1.7,
        "runner": 1.7,
        "cyclist": 1.8,
        "vehicle": 1.5,
    }
    subject_height = subject_heights.get(input_data.subject_type, 2.0)
    
    # Framing quality based on subject filling frame (ideal ~30-50% of frame)
    frame_fill_ratio = subject_height / visible_height_at_radius
    if 0.2 <= frame_fill_ratio <= 0.7:
        framing_quality = "excellent"
    elif 0.1 <= frame_fill_ratio <= 0.8:
        framing_quality = "good"
    elif 0.05 <= frame_fill_ratio <= 0.9:
        framing_quality = "fair"
    else:
        framing_quality = "poor"
    
    # Build bbox around subject
    lat_offset = orbit_radius_m * 2 / 111320.0
    lon_offset = orbit_radius_m * 2 / (111320.0 * abs(math.cos(math.radians(input_data.subject_point.lat))))
    bbox = BBox(
        south=input_data.subject_point.lat - lat_offset,
        west=input_data.subject_point.lon - lon_offset,
        north=input_data.subject_point.lat + lat_offset,
        east=input_data.subject_point.lon + lon_offset
    )
    
    # Create constraints
    from avatar.mission_intel.mission_spec import MissionConstraints
    constraints = MissionConstraints(
        max_altitude_m_amsl=input_data.preferred_altitude_m + 100,
        min_altitude_m_agl=10.0,
        max_distance_from_home_m=orbit_radius_m * 2 + 100,
        max_flight_time_s=input_data.orbit_duration_s + 60,
        battery_floor_pct=25.0
    )
    
    # Generate orbit using OrbitPattern
    match = Match(
        pattern_id="orbit",
        groups={
            "radius_m": str(int(orbit_radius_m)),
            "duration_s": str(input_data.orbit_duration_s),
            "name": f"subject_{input_data.subject_type}"
        }
    )
    
    # Override emit to use subject_point as center
    orbit_pattern = OrbitPattern()
    mission = orbit_pattern.emit(match, bbox, constraints)
    
    # Recenter waypoints on subject_point
    from avatar.mission_intel.mission_spec import Waypoint, WaypointAction
    import numpy as np
    
    # Generate circular orbit centered on subject_point
    num_points = 8
    lat_deg_per_m = 1.0 / 111320.0
    lon_deg_per_m = 1.0 / (111320.0 * math.cos(math.radians(input_data.subject_point.lat)))
    
    waypoints = []
    for i in range(num_points + 1):
        angle = 2 * math.pi * i / num_points
        dx = orbit_radius_m * math.cos(angle)
        dy = orbit_radius_m * math.sin(angle)
        
        lat = input_data.subject_point.lat + dy * lat_deg_per_m
        lon = input_data.subject_point.lon + dx * lon_deg_per_m
        
        wp = Waypoint(
            point=Point(lat=lat, lon=lon),
            alt_m=input_data.preferred_altitude_m,
            alt_frame="amsl",
            speed_m_s=3.0,
            action=WaypointAction.ORBIT,
            hold_s=input_data.orbit_duration_s / num_points if i < num_points else 0
        )
        waypoints.append(wp)
    
    mission = mission.model_copy(update={"waypoints": waypoints})
    
    # Run safety checks
    warnings = []
    if input_data.subject_velocity_m_s > 5:
        warnings.append("Subject moving fast - consider predictive tracking mode")
    if framing_quality == "poor":
        warnings.append("Subject may be too small in frame - consider closer orbit or zoom")
    
    tracking_notes = None
    if input_data.subject_velocity_m_s > 0:
        tracking_notes = f"Orbit optimized for subject moving at {input_data.subject_velocity_m_s} m/s"
    
    return ProposeOrbitForSubjectOutput(
        mission=mission,
        radius_m=orbit_radius_m,
        altitude_m=input_data.preferred_altitude_m,
        subject_visible_from_orbit=True,
        framing_quality=framing_quality,
        tracking_notes=tracking_notes,
        safety_warnings=warnings
    )


def get_propose_orbit_for_subject_schema() -> dict[str, Any]:
    """Return JSON schema for propose_orbit_for_subject tool registration."""
    return {
        "name": "propose_orbit_for_subject",
        "description": "Generate an orbit mission around a subject (static object or moving target). Calculates optimal radius for framing and safety, with tracking guidance for moving subjects. Read-only tool.",
        "inputSchema": ProposeOrbitForSubjectInput.model_json_schema(),
        "outputSchema": ProposeOrbitForSubjectOutput.model_json_schema(),
        "annotations": {
            "readOnlyHint": True,
            "openWorldHint": False,
            "idempotentHint": True,
            "destructiveHint": False
        }
    }
```

```python
# avatar/mcp_server/server.py registration snippet
from avatar.mcp_server.tools.mission_intel_tools import (
    get_propose_orbit_for_subject_schema,
    handle_propose_orbit_for_subject,
    ProposeOrbitForSubjectInput,
)

# In register_all_tools():
self.register_tool(
    name="propose_orbit_for_subject",
    schema=get_propose_orbit_for_subject_schema(),
    handler=handle_propose_orbit_for_subject,
    input_model=ProposeOrbitForSubjectInput,
    category="mission_intel",
)
```

- [ ] **Step 4: Run test** — `pytest tests/mcp_server/test_mission_intel_tools.py::test_propose_orbit_for_subject -v` → 4 passed.

- [ ] **Step 5: Commit** — `git add avatar/mcp_server/tools/mission_intel_tools.py tests/mcp_server/test_mission_intel_tools.py && git commit -m "feat(mcp_server): add propose_orbit_for_subject mission intel tool"

---

## Commit Fix-Pass

**Single commit message:** `docs(plans): expand W2b intent patterns and mission-intel tasks to full TDD`

```bash
git add docs/superpowers/plans/2026-04-16-wave-2b-intel-providers-scenarios.md
git commit -m "docs(plans): expand W2b intent patterns and mission-intel tasks to full TDD"
```

---

## Stream D9 — RuntimeProfile v2

### Task D9.1: Pydantic v2 `RuntimeProfile` + load order ENV → file → defaults

**Files:**
- Modify: `avatar/config/profiles.py`
- Create: `tests/config/test_profiles_v2.py`

```python
from __future__ import annotations
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class RuntimeProfile(BaseModel):
    model_config = ConfigDict(env_prefix="AVATAR_", env_nested_delimiter="__")

    name: str = "sitl"
    system_address: str = "udp://:14540"
    camera_backend: str = "mock_camera"
    detector_backend: str = "mock_detector"
    requires_px4_parameter_check: bool = False
    com_obl_rc_act: Literal[0, 1, 2, 3] = 2
    airframe: Airframe | None = None

class Airframe(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    mass_kg: float
    prop_size_in: float
    px4_airframe_id: str
    battery_cells: int
    max_thrust_n: float
    param_overlay_path: Path

def load_runtime_profile() -> RuntimeProfile:
    """Precedence: process env (AVATAR_*) > YAML file > defaults."""
    ...
```

YAML path: `~/.config/avatar/profile.yaml` or `$AVATAR_PROFILE_FILE`. Secrets **never** in YAML — document `op read` / env injection only.

- [ ] **Commit** — `feat(config): migrate RuntimeProfile to pydantic v2 layered loader`

---

### Task D9.2: Airframe templates `mark4_7in`, `x500_v2`, `custom`

**Files:**
- Create: `avatar/config/airframes/mark4_7in.yaml`
- Create: `avatar/config/airframes/x500_v2.yaml`
- Create: `avatar/config/airframes/custom.yaml`

**Example concrete values:**

```yaml
# mark4_7in.yaml
id: mark4_7in
mass_kg: 2.4
prop_size_in: 7.0
px4_airframe_id: 4001
battery_cells: 4
max_thrust_n: 55.0
param_overlay_path: hardware/px4/airframes/mark4_7in.params
```

```yaml
# x500_v2.yaml
id: x500_v2
mass_kg: 3.2
prop_size_in: 10.0
px4_airframe_id: 6011
battery_cells: 4
max_thrust_n: 68.0
param_overlay_path: hardware/px4/airframes/x500_v2.params
```

```yaml
# custom.yaml — placeholders for user override via env
id: custom
mass_kg: 1.8
prop_size_in: 5.0
px4_airframe_id: 4001
battery_cells: 3
max_thrust_n: 35.0
param_overlay_path: hardware/px4/airframes/custom_template.params
```

- [ ] **Commit** — `feat(config): add airframe YAML templates for profile v2`

---

### Task D9.3: Startup gate — `PX4ParameterManager.verify_safety_parameters` + overlay

**Files:**
- Modify: `avatar/mav/px4_parameters.py` — add `async def verify_safety_parameters(self, overlay_path: Path | None = None)` merging `CRITICAL_PARAMETERS` with key/value pairs read from PX4 `.params` diff file (simple `NAME value` lines); maintain backward-compatible call with `None`.
- Modify: `avatar/mcp_server/server.py` (or `avatar/main.py` entry) — before full initialization, if `profile.requires_px4_parameter_check`, await verify; on any invalid → raise / return structured **`PREFLIGHT_BLOCKED`** (align with `avatar/mcp_server/errors.py`).

- [ ] **Test:** `tests/config/test_profile_startup_gate.py` uses mock `PX4ParameterManager` asserting startup abort when overlay expects `MPC_XY_CRUISE` mismatch.

- [ ] **Commit** — `feat(config): block MCP startup on PX4 param overlay mismatch`

---

## Stream D10 — Scenario framework

### Task D10.1: Complete `ScenarioKind` rows in `scenarios.py`

**Files:**
- Modify: `avatar/sim/scenarios.py` — add `snowboard_halfpipe` and `skate_bowl` entries to `SCENARIOS` with `required_backends` including vision/wind/depth as appropriate.
- Modify: `tests/sim/test_scenarios.py` — assert each kind has ≥1 scenario; assert `runner_follow` includes `vision`, `sailboat_follow` includes `wind`, `indoor_obstacle_room` includes `depth` in `required_backends` tuple (substring match).

- [ ] **Commit** — `feat(sim): register snowboard_halfpipe and skate_bowl scenarios`

---

### Task D10.2: Pydantic `Scenario` model + `ScenarioLoader`

**Files:**
- Create: `avatar/sim/runner.py` (start)
- Create: `avatar/sim/scenario_schema.py` (optional split) — pydantic models mirroring §5.1 YAML.
- Create: `tests/sim/test_scenario_loader_roundtrip.py`

**Pydantic `Scenario` (complete):**

```python
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict
from avatar.mission_intel.geo import Point

class SimConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: Literal["sih", "gazebo"]
    world: str = "default"
    px4_model: str = "gz_x500"
    seed: int = 42
    speed_factor: float = 1.0

class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    expect: dict[str, Any] | None = None
    async_: bool = Field(default=False, alias="async")

class InjectionAt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: str
    t_offset_s: float

class Injection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: InjectionAt
    driver: str
    params: dict[str, Any] = Field(default_factory=dict)

class Assertion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    within_s: float | None = None
    eventually: bool | None = None
    expect: dict[str, Any]

class Teardown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collect: list[str] = Field(default_factory=list)

class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    description: str
    backends: list[str]
    sim: SimConfig
    preconditions: dict[str, Any]
    stages: list[Stage]
    injections: list[Injection] = Field(default_factory=list)
    assertions: list[Assertion]
    teardown: Teardown | None = None
```

`ScenarioLoader.load(path: Path) -> Scenario`.

- [ ] **Commit** — `feat(sim): add Scenario pydantic model and YAML loader`

---

### Task D10.3: `Orchestrator` — sequential + parallel `async: true` stages + `Driver` / `DriverContext` protocols

**Files:**
- Modify: `avatar/sim/runner.py`
- Create: `tests/sim/test_orchestrator_mock_mcp.py`

Use mocked MCP stdio client interface:

```python
class MCPClient(Protocol):
    async def call_tool(self, name: str, arguments: dict) -> dict: ...
```

`Orchestrator.run(scenario, client)` — for `async_` stage start task concurrently with subsequent stage only when spec allows (W2b: parallel stages fire-and-forget with join barrier before next sequential group — implement **simple rule:** stage with `async: true` runs as asyncio Task; next stage waits `join` if `expect` requires; document).

**Also in `runner.py` (same task):** define `SimTier` as `Literal["sih","gazebo"]` or `StrEnum`, and export `Driver`, `DriverContext` protocols (same signatures as §5.3) so `avatar/sim/drivers/*.py` can import from `avatar.sim.runner` without circular imports (drivers must not import orchestrator internals — only protocols).

```python
from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class DriverContext(Protocol):
    run_id: str
    scenario: Any
    mcp: Any
    metadata: dict[str, Any]

@runtime_checkable
class Driver(Protocol):
    name: str
    supported_tiers: set[SimTier]
    async def inject(self, ctx: DriverContext) -> None: ...
    async def release(self, ctx: DriverContext) -> None: ...
```

- [ ] **Commit** — `feat(sim): add scenario Orchestrator with async stage support`

---

### Task D10.4: `InjectionScheduler`

- [ ] **Test:** driver fires at `t_offset_s` using fake clock `asyncio.sleep` patched.

- [ ] **Commit** — `feat(sim): add InjectionScheduler for timed failure injection`

---

### Task D10.5: `AssertionEngine`

- [ ] **`within_s`:** window from assertion start timestamp.
- [ ] **`eventually`:** evaluated at end of run.

- [ ] **Commit** — `feat(sim): add AssertionEngine for within_s and eventually`

---

### Task D10.6: `ArtifactCollector`

- [ ] **Tar layout** `artifacts/<run_id>/px4_log.tlog`, `flight_recorder.jsonl`, `guardian_alerts.jsonl`, `state_transitions.jsonl`, `sim_topics/` (optional empty dir).

- [ ] **Commit** — `feat(sim): add ArtifactCollector tarball layout`

---

### Task D10.7: `WindDriver` — `avatar/sim/drivers/wind.py`

**Files:** Create: `avatar/sim/drivers/wind.py` — Create: `tests/sim/drivers/test_wind_driver.py`

- [ ] **Class:** `WindDriver` with `name = "wind"`, `supported_tiers = frozenset({"gazebo"})` (must match `SimTier` type alias from `runner.py`).
- [ ] **`inject`:** call mocked MCP `set_parameter` / internal sim API stub for wind vector.
- [ ] **Test:** mock `ctx.mcp.call_tool` assert called with expected tool name; `release` restores defaults.

- [ ] **Commit** — `feat(sim): add WindDriver`

---

### Task D10.8: `GpsLossDriver` — `avatar/sim/drivers/gps_loss.py`

**Files:** Create: `avatar/sim/drivers/gps_loss.py` — Create: `tests/sim/drivers/test_gps_loss_driver.py`

- [ ] **Behavior:** simulate GPS denied (PX4 param or Gazebo plugin hook via MCP shim in tests).

- [ ] **Commit** — `feat(sim): add GpsLossDriver`

---

### Task D10.9: `VisionDropoutDriver` — `avatar/sim/drivers/vision_dropout.py`

**Files:** Create: `avatar/sim/drivers/vision_dropout.py` — Create: `tests/sim/drivers/test_vision_dropout_driver.py`

- [ ] **Behavior:** flip flag consumed by vision tools / inject `cancel_operation` on vision stream.

- [ ] **Commit** — `feat(sim): add VisionDropoutDriver`

---

### Task D10.10: `OffboardFreezeDriver` — `avatar/sim/drivers/offboard_freeze.py`

**Files:** Create: `avatar/sim/drivers/offboard_freeze.py` — Create: `tests/sim/drivers/test_offboard_freeze_driver.py`

- [ ] **Behavior:** pause `OffboardVelocityStreamer` for `params.duration_s` (mock `ctx.metadata["streamer"]` in unit test).

- [ ] **Commit** — `feat(sim): add OffboardFreezeDriver`

---

### Task D10.11: `BatteryDrainDriver` — `avatar/sim/drivers/battery_drain.py`

**Files:** Create: `avatar/sim/drivers/battery_drain.py` — Create: `tests/sim/drivers/test_battery_drain_driver.py`

- [ ] **Behavior:** force telemetry cache battery % floor via inject hook.

- [ ] **Commit** — `feat(sim): add BatteryDrainDriver`

---

### Task D10.12: `RcLossDriver` — `avatar/sim/drivers/rc_loss.py`

**Files:** Create: `avatar/sim/drivers/rc_loss.py` — Create: `tests/sim/drivers/test_rc_loss_driver.py`

- [ ] **Behavior:** simulate RC lost (MAVLink injection or param `SIM_RC_LOST` pattern — mock in tests).

- [ ] **Commit** — `feat(sim): add RcLossDriver`

---

### Task D10.13: `ObstacleProximityDriver` — `avatar/sim/drivers/obstacle_proximity.py`

**Files:** Create: `avatar/sim/drivers/obstacle_proximity.py` — Create: `tests/sim/drivers/test_obstacle_proximity_driver.py`

- [ ] **Behavior:** publish decreasing distance_to_obstacle in guardian test seam.

- [ ] **Commit** — `feat(sim): add ObstacleProximityDriver`

---

### Task D10.14: `TargetMotionDriver` — `avatar/sim/drivers/target_motion.py`

**Files:** Create: `avatar/sim/drivers/target_motion.py` — Create: `tests/sim/drivers/test_target_motion_driver.py`

- [ ] **Behavior:** update mock target position for tracking scenarios.

- [ ] **Commit** — `feat(sim): add TargetMotionDriver`

---

### Task D10.15: `NetworkPartitionDriver` — `avatar/sim/drivers/network_partition.py`

**Files:** Create: `avatar/sim/drivers/network_partition.py` — Create: `tests/sim/drivers/test_network_partition_driver.py`

- [ ] **Behavior:** when `os.geteuid() == 0`, run `tc qdisc add ... netem loss 100%` on iface from `ctx.metadata["iface"]`; in unit tests mock `subprocess.run` and assert command contains `tc` and `netem`.
- [ ] **`release`:** delete qdisc.

- [ ] **Commit** — `feat(sim): add NetworkPartitionDriver`

---

### Task D10.16: YAML `orbit_with_offboard_freeze.yaml` + wiring test

**Files:**
- Create: `avatar/sim/scenarios/orbit_with_offboard_freeze.yaml`
- Create: `tests/sim/test_yaml_wiring_orbit_freeze.py`

**Full YAML body:**

```yaml
id: orbit_with_offboard_freeze
kind: nature_cinematic
description: "Orbit a landmark, simulate MCP offboard link freeze mid-orbit, verify RTL"
backends: [mcp_stdio, mavsdk, vision_state, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500
  seed: 42
  speed_factor: 1.0
preconditions:
  px4_params: airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 85
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 15 },
      expect: { state: HOVERING } }
  - { id: goto_target, tool: goto_gps, args: { lat: 47.3978, lon: 8.5460, alt_m: 25 } }
  - { id: start_orbit, tool: orbit_target, args: { target_lat: 47.3978, target_lon: 8.5460,
                                                    radius_m: 10, speed_m_s: 3, duration_s: 60 },
      async: true }
injections:
  - at: { stage: start_orbit, t_offset_s: 15 }
    driver: offboard_freeze
    params: { duration_s: 3 }
assertions:
  - within_s: 8
    expect: { state: [HOLD, RTL], reason_contains: offboard }
  - eventually:
    expect: { landed: true, home_distance_m: { lt: 5 } }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** — `feat(sim): add orbit_with_offboard_freeze scenario YAML`

---

### Task D10.17: YAML `search_and_vision_dropout.yaml` + wiring test

**Full YAML body:**

```yaml
id: search_and_vision_dropout
kind: runner_follow
description: "Search grid then vision dropout triggers failsafe path"
backends: [mcp_stdio, mavsdk, vision_state, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500
  seed: 7
  speed_factor: 1.0
preconditions:
  px4_params: airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 90
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 12 },
      expect: { state: HOVERING } }
  - { id: search_grid, tool: set_velocity_body, args: { forward: 2, right: 0, down: 0, yawspeed: 0, duration_s: 5 },
      expect: { state: [FLYING, VELOCITY_CONTROL] } }
  - { id: follow_subject, tool: track_bbox, args: { label: "person", x: 0.5, y: 0.5, w: 0.1, h: 0.2 },
      async: true }
injections:
  - at: { stage: follow_subject, t_offset_s: 4 }
    driver: vision_dropout
    params: { duration_s: 2 }
assertions:
  - within_s: 10
    expect: { state: [HOLD, RTL] }
  - eventually:
    expect: { landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions, sim_topics]
```

- [ ] **Commit** — `feat(sim): add search_and_vision_dropout scenario YAML`

---

### Task D10.18: YAML `gps_jam_expect_rtl.yaml` + wiring test

**Full YAML body:**

```yaml
id: gps_jam_expect_rtl
kind: sailboat_follow
description: "GPS loss during loiter; expect RTL or land per params"
backends: [mcp_stdio, mavsdk, telemetry_cache]
sim:
  tier: gazebo
  world: default
  px4_model: gz_x500
  seed: 99
  speed_factor: 1.0
preconditions:
  px4_params: airframes/x500_v2.params
  home: { lat: 47.3977, lon: 8.5456, alt_m: 488 }
  battery_pct: 80
stages:
  - { id: takeoff, tool: arm_and_takeoff, args: { altitude_m: 10 },
      expect: { state: HOVERING } }
  - { id: loiter, tool: hold, args: {},
      expect: { state: [HOLD, HOVERING] }, async: true }
injections:
  - at: { stage: loiter, t_offset_s: 3 }
    driver: gps_loss
    params: { duration_s: 8 }
assertions:
  - within_s: 20
    expect: { state: [RTL, LAND] }
  - eventually:
    expect: { landed: true }
teardown:
  collect: [px4_log, flight_recorder_jsonl, guardian_alerts, state_transitions]
```

- [ ] **Commit** — `feat(sim): add gps_jam_expect_rtl scenario YAML`

---

### Task D2b-GATE: W2b verification + `changes-made.md` marker

**Files:**
- Modify: `scripts/sim.sh` — add `scenario analyze_area_offline` target loading `avatar/sim/scenarios/analyze_area_offline.yaml` (create in this task).
- Create: `avatar/sim/scenarios/analyze_area_offline.yaml` — minimal `stages` calling MCP `analyze_area` with fixture bbox (no drone commands), `sim.tier` may be `sih` or `offline` if supported; if runner requires `gazebo`, use `tier: sih` with stub MCP host — **prefer** `tier: sih` + `tool: analyze_area` only.

**Minimal offline scenario:**

```yaml
id: analyze_area_offline
kind: nature_cinematic
description: "Offline analyze_area for W2b gate"
backends: [mcp_stdio]
sim:
  tier: sih
  world: default
  px4_model: gz_x500
  seed: 1
  speed_factor: 1.0
preconditions: {}
stages:
  - id: analyze
    tool: analyze_area
    args:
      bbox: { south: 47.39, west: 8.54, north: 47.40, east: 8.55 }
      intent: general
    expect: { ok: true }
assertions:
  - eventually:
      expect: { ok: true }
teardown:
  collect: []
```

- [ ] **Run:** `scripts/sim.sh scenario analyze_area_offline`  
  **Expected stdout (representative):** lines containing `scenario=analyze_area_offline`, `analyze_area`, `PASS`, exit code `0` (engineer paste actual transcript first time into `changes-made.md`).

- [ ] **Run:** `pytest tests/vision tests/mission_intel -q`  
  **Expected:** `passed` summary; `0 failed`.

- [ ] **Modify:** `changes-made.md` append:

```markdown
## 2026-04-16 — Wave 2b complete (W2b gate)

- `scripts/sim.sh scenario analyze_area_offline` OK (transcript: ...)
- `pytest tests/vision tests/mission_intel` OK
```

- [ ] **Commit** — `chore(release): mark Wave 2b gate complete`

---

## Self-Review

**1. Spec coverage**

| Spec item | Task |
|-----------|------|
| D7 providers + registry | D7.1–D7.7 |
| D8 package layout §7 | D8.0–D8.8, D8.20–D8.21 |
| Seven MCP tools §6.4 | D8.22–D8.28 |
| GMaps guardrails | D8.6.* + D8.0 |
| Ten intent patterns §7.4 | D8.10–D8.19 (D8.9 = parser infra) |
| D9 profile v2 + airframe + gate | D9.1–D9.3 |
| D10 runner + drivers + YAML §5 | D10.1–D10.18 |
| W2b gate §11 | D2b-GATE |
| Docker Gazebo tier §8 | D7.6, D10 YAML `tier: gazebo` |

**Gap closed:** `avatar/vision/providers.py` `GazeboCameraProvider` — superseded by D7.6 package implementation; D7.7 removes dead `RuntimeError` path.

**2. Placeholder scan** — No `TODO`/`TBD`; regex sketches are explicit; engineer replaces ellipses in production code during implementation.

**3. Type consistency** — `Waypoint.alt_frame` uses `Literal["amsl","agl","relative"]` (no spaces). `Detection` in vision providers uses `bbox_xywh_norm` vs `mock_detector.Detection` list bbox — **D7.1** must add adapter from mock to unified `Detection` or rename consistently in follow-up task (list in D7.3 commit as migration note). `Parser.PRIORITY` order documented. `verify_safety_parameters(overlay_path)` extends existing method name in D9.3.

---

**Plan complete.** Total task headings: **62** (D7: 7, D8: 33, D9: 3, D10: 18, Gate: 1).
