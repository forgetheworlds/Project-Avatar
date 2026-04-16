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

- [ ] **Grammar:** joined-token regex `r"(fly|patrol).*(perimeter|boundary).*(of|around)"` on ` " ".join(tokens)`; optional free-text tail tokens become mission `name`.
- [ ] **Emit:** closed-loop waypoints around `bbox` margin at `constraints.min_altitude_m_agl` as relative AGL above bbox center ground reference.
- [ ] **Tests:** 2 positive (`"fly the perimeter of the field"`, `"patrol the boundary of zone alpha"`); 2 negative (`"orbit fast"`, `"random words"` → `MissionSpecError` or no match falling through to Parser).
- [ ] **Register** in `Parser.PRIORITY` after this task (order: hover_at first — add stub if not yet present, or append and resort in D8.19).

```python
# tests/mission_intel/test_intent_perimeter.py (skeleton)
import pytest
from avatar.mission_intel.intent_planner import PerimeterPattern, MissionSpecError
from avatar.mission_intel.geo import BBox
from avatar.mission_intel.mission_spec import MissionConstraints, SafetyPolicy, Point

@pytest.fixture
def bbox():
    return BBox(south=47.39, west=8.54, north=47.40, east=8.55)

@pytest.fixture
def constraints():
    return MissionConstraints(
        max_altitude_m_amsl=200.0,
        min_altitude_m_agl=5.0,
        max_distance_from_home_m=500.0,
        max_flight_time_s=600.0,
        battery_floor_pct=25.0,
    )

def test_perimeter_match_fly_perimeter_of(bbox, constraints):
    toks = "fly the perimeter of the stadium".lower().split()
    m = PerimeterPattern.match(toks)
    assert m is not None
    mission = PerimeterPattern().emit(m, bbox, constraints)
    assert mission.version == "1.0"
    assert len(mission.waypoints) >= 4

def test_perimeter_negative_no_keyword(bbox, constraints):
    toks = "go fast and turn left".split()
    assert PerimeterPattern.match(toks) is None
```

- [ ] **Commit** — `feat(mission_intel): add plan_mission_from_intent PerimeterPattern`

---

### Task D8.11: `OrbitPattern` (`id="orbit"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_orbit.py`

- [ ] **Grammar:** `r"\borbit\b"` + radius `(?P<r>\d+)\s*(m|meters)?` + optional duration `(?P<n>\d+)\s*(s|sec|seconds)?`.
- [ ] **Tests:** 2 positive (`"orbit the tower at 25 meters for 60 seconds"`, `"orbit X at R 30m"`); 2 negative (missing radius; negative radius string).

- [ ] **Commit** — `feat(mission_intel): add OrbitPattern`

---

### Task D8.12: `LawnmowerPattern` (`id="lawnmower"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_lawnmower.py`

- [ ] **Grammar:** `r"(lawnmower|survey|grid)"` + optional `r"(?P<o>\d+)\s*%?\s*overlap"` default overlap 0.8 + optional `r"at altitude\s*(?P<a>\d+)"`.
- [ ] **Tests:** 2 positive (`"survey the field with 80% overlap"`, `"lawnmower the bbox at altitude 40"`); 2 negative.

- [ ] **Commit** — `feat(mission_intel): add LawnmowerPattern`

---

### Task D8.13: `RevealPattern` (`id="reveal"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_reveal.py`

- [ ] **Grammar:** `r"reveal"` + `r"(from|toward).*(?P<card>north|south|east|west)"`.
- [ ] **Tests:** 2 positive (`"reveal the barn from the west"`, `"cinematic reveal of the peak from east"`); 2 negative.

- [ ] **Commit** — `feat(mission_intel): add RevealPattern`

---

### Task D8.14: `EstablishPattern` (`id="establish"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_establish.py`

- [ ] **Grammar:** `r"(establishing shot|establish|wide opener)"`.
- [ ] **Tests:** 2 positive; 2 negative.

- [ ] **Commit** — `feat(mission_intel): add EstablishPattern`

---

### Task D8.15: `FollowPattern` (`id="follow"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_follow.py`

- [ ] **Grammar:** `r"follow"` + `r"(runner|car|subject|target)"`.
- [ ] **Tests:** 2 positive (`"follow the runner"`, `"track the car"`); 2 negative.

- [ ] **Commit** — `feat(mission_intel): add FollowPattern`

---

### Task D8.16: `InspectPattern` (`id="inspect"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_inspect.py`

- [ ] **Grammar:** `r"inspect"` + `r"(roof|face|side|facade)"`.
- [ ] **Tests:** 2 positive (`"inspect the roof of the building"`, `"close inspection of east face"`); 2 negative.

- [ ] **Commit** — `feat(mission_intel): add InspectPattern`

---

### Task D8.17: `TransectPattern` (`id="transect"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_transect.py`

- [ ] **Grammar:** `r"transect"` + `r"(every|spacing).*(?P<d>\d+)\s*m"`.
- [ ] **Tests:** 2 positive (`"transect the plot every 20 m"`, `"parallel lines across the field every 15m"`); 2 negative.

- [ ] **Commit** — `feat(mission_intel): add TransectPattern`

---

### Task D8.18: `PhotoGridPattern` (`id="photo_grid"`)

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_photo_grid.py`

- [ ] **Grammar:** `r"photo grid"` + `r"(?P<agl>\d+)\s*m\s*agl"`.
- [ ] **Tests:** 2 positive (`"photo grid of the site at 50 m AGL"`, `"photo grid at 40m agl of the roof"`); 2 negative (missing AGL clause; `"photo only"`).

- [ ] **Commit** — `feat(mission_intel): add PhotoGridPattern`

---

### Task D8.19: `HoverAtPattern` (`id="hover_at"`) + finalize `Parser.PRIORITY`

**Files:** Modify: `intent_planner.py` — Create: `tests/mission_intel/test_intent_hover_at.py`

- [ ] **Grammar:** `r"hover"` + `r"(for|duration).*(?P<n>\d+)\s*(s|sec|seconds)?"` + `r"(at|height|altitude).*(?P<h>\d+)\s*m"`.
- [ ] **Tests:** 2 positive (`"hover at the helipad for 20 seconds at 10 meters"`); 2 negative.
- [ ] **Finalize** `Parser.PRIORITY` tuple **exact order (first match wins):**  
  `HoverAtPattern, OrbitPattern, PerimeterPattern, LawnmowerPattern, RevealPattern, EstablishPattern, FollowPattern, InspectPattern, TransectPattern, PhotoGridPattern`  
  Document in module docstring with English examples per spec.

- [ ] **Commit** — `feat(mission_intel): add HoverAtPattern and finalize Parser priority`

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
- Create: `avatar/mcp_server/tools/mission_intel_tools.py` (start file)
- Modify: `avatar/mcp_server/server.py` — register tool with `readOnlyHint=True`, `openWorldHint=True`, `outputSchema` from `MissionIntelJSONSchema`.

- [ ] **Test:** `tests/mcp_server/test_mission_intel_tools.py::test_analyze_area_schema_and_offline`

- [ ] **Commit** — `feat(mcp_server): add analyze_area mission intel tool`

---

### Task D8.23: MCP tool `lookup_place`

- [ ] **Implement** args `query: str`, `near: Point | None`; result `list[POI]`; annotations `readOnly`, `openWorld`, `idempotent`.

- [ ] **Commit** — `feat(mcp_server): add lookup_place tool`

---

### Task D8.24: MCP tool `get_elevation`

- [ ] **Result** `{elevation_m_amsl: float, source: str}`

- [ ] **Commit** — `feat(mcp_server): add get_elevation tool`

---

### Task D8.25: MCP tool `get_agl`

- [ ] **Result** `{agl_m: float, terrain_m: float}`

- [ ] **Commit** — `feat(mcp_server): add get_agl tool`

---

### Task D8.26: MCP tool `plan_scenic_sweep`

- [ ] **Args** `bbox`, `style: Literal["reveal","orbit","establish"]`, `duration_s`, optional `sun_time: str | None`

- [ ] **Commit** — `feat(mcp_server): add plan_scenic_sweep tool`

---

### Task D8.27: MCP tool `plan_mission_from_intent`

- [ ] **Uses** `Parser` + patterns; returns `Mission`; structured `MissionSpecError` → MCP error `MISSION_SPEC_ERROR`.

- [ ] **Commit** — `feat(mission_intel): add plan_mission_from_intent MCP tool`

---

### Task D8.28: MCP tool `propose_orbit_for_subject`

- [ ] **Result** `{mission: Mission, radius_m: float}`

- [ ] **Commit** — `feat(mcp_server): add propose_orbit_for_subject tool`

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
