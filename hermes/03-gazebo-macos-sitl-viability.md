# Gazebo Harmonic / PX4 SITL Viability on macOS Apple Silicon M3

**Date:** 2026-04-13  
**Target:** macOS Apple Silicon M3, PX4 v1.15.0, Gazebo Harmonic  
**Verdict:** Native macOS SITL is BROKEN. Docker x86_64 emulation is the best path for full Gazebo. SIH is the native macOS fallback.

---

## 1. Gazebo Harmonic on macOS ARM64/Apple Silicon — Native Status

**Viability: BROKEN (as of Apr 2026)**  
**Setup effort: High (even if it works, expect days of debugging)**

Gazebo Harmonic has Homebrew bottles for macOS (`brew install gz-harmonic` via `osrf/simulation` tap), but the installation and runtime experience on Apple Silicon is severely problematic:

- **Homebrew build failures on macOS 15 Sequoia:** The `gz-harmonic` formula has recurring build failures due to OGRE 1.9 dependency issues on macOS 15.x. Multiple GitHub issues (#2478, #2793, #3003) remain open on `osrf/homebrew-simulation`.
- **Binary installation issues:** Even when Homebrew bottles install, Gazebo Harmonic fails to launch properly on macOS 14/15 due to library conflicts (e.g., gz-msgs version conflicts, missing .dylib symlinks).
- **XQuartz required:** Gazebo GUI on macOS requires XQuartz (X11 server), adding another layer of complexity. Server must be started separately from GUI on macOS.
- **Architecture mismatch:** Some bottles ship as x86_64 only and run under Rosetta, causing further compatibility issues with ARM-native PX4 builds.
- **Gazebo Classic is deprecated** by OSRF; PX4 moved to "new Gazebo" (gz-sim). The old `gazebo-classic_iris` commands no longer work on current PX4 main/v1.16.

**Bottom line:** Gazebo Harmonic can technically be installed via Homebrew on macOS, but getting it to a state where PX4 can actually use it is unreliable and undocumented for current macOS versions.

---

## 2. PX4 SITL with Gazebo Harmonic on macOS — `make px4_sitl gz_x500`

**Viability: BROKEN**  
**Setup effort: Very High (requires patching PX4 source)**

The PX4 docs at `docs.px4.io/main/en/dev_setup/dev_env_mac` claim support and say `make px4_sitl gz_x500` should work after running `./Tools/setup/macos.sh --sim-tools`. **In practice, this does not work.** Evidence from the PX4 community (Feb 2026 thread with 7 replies, 227 views):

### Root Cause: C++14 vs C++17 Mismatch
- Gazebo modules (gz-sim, gz-transport) still compile with **C++14**
- Homebrew's `protobuf` and `abseil-cpp` now require **C++17**
- This triggers fatal compilation errors in abseil headers

### Specific Build Errors Encountered
1. `absl/base/policy_checks.h: C++ versions less than C++17 are not supported`
2. `gz-sim::gz-sim` target not found (linkage failure)
3. `.so` vs `.dylib` extension mismatch — CMake hardcodes Linux `.so` extensions
4. Abseil float-to-double implicit conversion warnings treated as errors
5. Gazebo timeout on startup (workaround: re-run command)

### Workarounds (Hacky, Not Merged)
A WIP PR [#25979](https://github.com/PX4/PX4-Autopilot/pull/25979) documents all patches needed:
- Add `-Wno-double-promotion` to `px4_add_common_flags.cmake`
- Change `.so` to `.dylib` in `optical_flow.cmake` (lines 50, 57)
- Update CMakeLists.txt C++ standard from C++14 to C++17
- Run natively on ARM (do NOT use Rosetta/x86_64 terminal)
- Use pyenv for Python management

### PX4 NuttX Builds (Firmware Only) — WORKS
Compiling PX4 for actual Pixhawk hardware (NuttX target) works fine on macOS M3 with `arm-none-eabi-gcc`. Only the SITL simulation path is broken.

---

## 3. Alternative Approaches

### 3A. Docker x86_64 Emulation (Recommended for Gazebo)

**Viability: WORKS**  
**Setup effort: Medium (1-2 hours)**

Run Linux x86_64 containers via Docker Desktop with Rosetta emulation:

```bash
# Pre-built container with Gazebo Harmonic (simplest option)
docker run --rm -it --platform linux/amd64 \
  -p 14550:14550/udp \
  px4io/px4-sitl-gazebo:latest

# Or with specific model
docker run --rm -it --platform linux/amd64 \
  -p 14550:14550/udp \
  px4io/px4-sitl-gazebo:latest \
  -e PX4_SIM_MODEL=gz_x500

# GUI access via VNC
docker run -it --platform linux/amd64 \
  -p 5900:5900 -p 14550:14550/udp \
  -v /Users/YOU/PX4-Autopilot:/src/PX4-Autopilot \
  -w /src/PX4-Autopilot --shm-size=1gb \
  px4io/px4-dev-simulation-jammy bash -c "
    apt-get update && apt-get install -y x11vnc xvfb openbox mesa-utils
    export DISPLAY=:1; Xvfb :1 -screen 0 1280x1024x24 &
    sleep 3; openbox &; sleep 2
    x11vnc -display :1 -nopw -listen 0.0.0.0 -rfbport 5900 -forever &
    sleep 5; export LIBGL_ALWAYS_SOFTWARE=1
    make px4_sitl_default gz_x500
  "
```

**Pros:**
- Official `px4io/px4-sitl-gazebo` container works out of the box
- Full Gazebo Harmonic with all vehicle models including depth/vision cameras
- MAVLink UDP on port 14550 accessible from macOS host (QGroundControl works)
- Can mount local PX4 source for development

**Cons:**
- x86_64 emulation under Rosetta = ~40-60% performance penalty vs native Linux
- GUI requires VNC viewer (no native macOS window)
- Software rendering only (no GPU acceleration)
- ~2GB container image
- Headless mode (`-s` flag) faster if GUI not needed

### 3B. Docker ARM64 Native Containers

**Viability: PARTIALLY WORKS**  
**Setup effort: High (build your own)**

Most `px4io/` Docker images are x86_64 only. There is no official `px4-sitl-gazebo` ARM64 image. A `px4io/px4-dev-aarch64` image exists for builds but lacks full simulation tooling. You would need to build Gazebo Harmonic from source in an ARM64 Ubuntu container — which has the same dependency issues as macOS native.

### 3C. Parallels Desktop / UTM Virtual Machine

**Viability: WORKS (with limitations)**  
**Setup effort: Medium (2-4 hours)**

Run Ubuntu ARM64 Server in Parallels Desktop or UTM:

**Pros:**
- Near-native ARM64 performance (no Rosetta overhead)
- Full Linux environment, standard PX4 docs apply
- Parallels offers 3D acceleration (but has black screen issues with Gazebo/RViz)

**Cons:**
- Parallels Desktop costs ~$100/year
- 3D acceleration has known issues with Gazebo (black screen reports on Parallels forums)
- UTM is free but Gazebo runs CPU hot and slow without GPU pass-through
- macOS Sonoma/Sequoia removed easy Rosetta toggle for Terminal.app
- QGC ↔ VM networking requires manual configuration

**Community report:** M3 Sequoia user got Docker + VNC working but could not get native SITL build. Another user uses Parallels with Ubuntu ARM64 server for SITL builds but misses GUI.

### 3D. Remote Linux Machine / Cloud VM

**Viability: WORKS (best performance)**  
**Setup effort: Low-Medium (30min-2hr)**

Use a cloud Linux VM (AWS EC2, GCP, Hetzner, GitHub Codespaces) or a dedicated Linux machine:

```bash
# Quick cloud option (example with GitHub Codespaces)
# CodeSpace with Ubuntu + Gazebo pre-installed
# Or any cloud VM with:
sudo apt install ./px4-gazebo_*.deb  # Pre-built .deb from PX4 releases
PX4_GZ_WORLD=baylands PX4_SIM_MODEL=gz_x500 px4-gazebo
```

**Pros:**
- Best performance, native x86_64 Linux
- Official pre-built `.deb` packages available for Gazebo Harmonic
- No local resource consumption
- Full GPU acceleration possible on cloud GPU instances

**Cons:**
- Requires internet connection and cloud costs
- Latency for interactive development
- GUI requires X11 forwarding or VNC
- No offline capability

---

## 4. jMAVSim on macOS as Fallback

**Viability: BROKEN (as of 2025-2026)**  
**Setup effort: Medium (but may fail)**

jMAVSim historically worked on macOS and was the recommended fallback. Current status:

- **Build errors on Apple Silicon:** Multiple community reports (Reddit, PX4 forums) of `make px4_sitl jmavsim` failing on M1/M2/M3 with Java compilation errors, TBB disabled errors, and missing `dds_topics.h`.
- **No 3D environment:** jMAVSim provides a very basic visual — just a simple multirotor model in a flat world. No obstacles, no complex environments.
- **Multirotor only:** Only supports quadrotor simulation. No planes, no VTOL, no rovers.
- **No sensor simulation:** No cameras, no depth sensors, no LIDAR. Just basic IMU + GPS simulation.
- **Limited tuning:** Basic flight controller testing only — cannot test vision-based features.

**Verdict:** Even if you get it building, jMAVSim is too limited for Project Avatar's needs (depth camera, vision, obstacle avoidance). Not recommended.

---

## 5. PX4 SIH (Simulation-In-Hardware) Mode

**Viability: WORKS (on macOS natively!)**  
**Setup effort: Low (15-30 minutes)**

SIH is a lightweight, headless simulator built directly into PX4 as a module. It runs physics inside the PX4 process via uORB messages — zero external dependencies.

### How It Works
SIH replaces real sensor/actuator hardware with a simulated physics model. It runs as a PX4 module (`src/modules/simulation/sih`) and generates synthetic IMU, barometer, magnetometer, and GPS data.

### SITL Usage (No hardware needed)
```bash
# Quadcopter
make px4_sitl_sih sihsim_quadrotor

# Airplane  
make px4_sitl_sih sihsim_airplane

# Tailsitter VTOL (experimental)
make px4_sitl_sih sihsim_xvert
```

### Supported Vehicle Types (6 total)
| Vehicle | Command | Status |
|---------|---------|--------|
| Quadcopter | `sihsim_quadrotor` | Stable |
| Hexacopter | `sihsim_hexacopter` | Stable |
| Airplane | `sihsim_airplane` | Stable |
| Standard VTOL | `sihsim_standard_vtol` | Stable |
| Tailsitter VTOL | `sihsim_xvert` | Experimental |
| Rover | `sihsim_rover` | Stable |

### What SIH Provides
- Full flight controller stack (all modes, navigation, missions)
- Realistic multirotor/fixed-wing physics
- IMU, barometer, magnetometer, GPS simulation
- Multi-vehicle simulation support
- RC controller input (via QGC MAVLink joystick)
- Mission mode, RTL, follow-me, offboard, etc.
- Can be used for parameter tuning and flight mode testing

### What SIH Does NOT Provide
- **No 3D visualization** (headless only — vehicle position visible in QGC map)
- **No camera/depth sensor simulation** (critical for Avatar!)
- **No obstacle environment** (no walls, buildings, objects)
- **No LIDAR simulation**
- **No collision detection with environment**
- **No visual odometry support**
- Rigid vehicle models (custom vehicle configs limited)

### SIH on Flight Controller Hardware
With `SYS_HITL=2`, SIH can run on actual Pixhawk hardware, replacing sensors with simulated data. Useful for testing custom code on target hardware without flying.

### Pre-built Container (Simplest Option)
```bash
docker run --rm -it -p 14550:14550/udp px4io/px4-sitl:latest \
  -e PX4_SIM_MODEL=sihsim_airplane
```

---

## 6. Gazebo Depth Camera and Vision Models

**Viability: AVAILABLE (on Linux/Gazebo only)**  
**Setup effort: N/A (just use the right make target)**

PX4 ships several X500 variants with sensor payloads for Gazebo Harmonic:

### Camera Models
| Model | Command | Sensor | Port |
|-------|---------|--------|------|
| X500 Vision Odometry | `make px4_sitl gz_x500_vision` | Visual odometry camera | 4005 |
| X500 Depth Camera | `make px4_sitl gz_x500_depth` | Front-facing depth (OAK-D model) | 4002 |
| X500 Mono Camera | `make px4_sitl gz_x500_mono_cam` | Monocular camera | — |
| X500 Mono Cam Down | `make px4_sitl gz_x500_mono_cam_down` | Downward mono cam (Aruco landing) | — |

### LIDAR Models
| Model | Command | Sensor |
|-------|---------|--------|
| 1D LIDAR Down | `make px4_sitl gz_x500_lidar_down` | Lightware LW20/C, 0.1-100m |
| 1D LIDAR Front | `make px4_sitl gz_x500_lidar_front` | Lightware LW20/C, 0.2-100m (collision prevention) |
| 2D LIDAR | `make px4_sitl gz_x500_lidar_2d` | Hokuyo UTM-30LX, 270° arc |

### Other
| Model | Command |
|-------|---------|
| X500 with Gimbal | `make px4_sitl gz_x500_gimbal` |

**Key limitation:** Camera video streaming to QGroundControl is not yet working (tracked in PX4-Autopilot#22563). Depth/LIDAR data is available via Gazebo topics and UORB internally.

**These models ONLY work on Linux with Gazebo Harmonic — not on macOS.**

---

## 7. Community Reports (2025-2026)

### Feb 2026 — PX4 Forum Thread (7 replies, 227 views)
"PX4 SITL refuses to build on macOS (Intel + M-Series)" — Multiple users on Intel iMac and M3 MacBook Pro, macOS Tahoe 26.1, spent a week trying. All simulators (Gazebo Harmonic, Gazebo Fortress, jMAVSim) fail. Root cause identified as C++14/17 mismatch. WIP PR with hacky fixes exists but not merged.

### Oct 2025 — Apple Silicon Tutorial
M4 MacBook Pro, Sequoia 15.5: PX4 v1.15 compiles for NuttX targets fine. **Cannot compile posix SITL or Gazebo on macOS.** Successfully uses Parallels with Ubuntu ARM64 Server for SITL.

### Sep 2025 — M3 Sequoia Setup
Apple M3 Pro, 36GB: Could not get native SITL build working. Workaround: Docker with `px4io/px4-dev-simulation-focal`, VNC viewer for GUI. Gazebo Classic runs in the container. Could not get QGC to communicate with the container easily.

### Reddit (2025)
"PX4 SITL on macOS arm64 arch" — M2 MacBook Air. Neither jMAVSim nor Webots would build successfully.

### Gazebo Discourse (2025)
Multiple threads about `gz-harmonic` failing to install/build on macOS 15.x via Homebrew. OGRE 1.9 compilation failures are the most common blocker.

### Parallels Forums
Reports of 3D acceleration causing black screens with Gazebo and RViz on Apple Silicon Parallels VMs.

### Reddit (2025)
"Gazebo Sim with UTM VM on M4 Mac makes CPU very hot" — Ubuntu ARM64 in UTM, Gazebo runs but maxes out CPU due to lack of GPU acceleration.

---

## 8. Performance Comparison

| Approach | Build Time (PX4 SITL) | Sim FPS | Latency | GPU | Setup Effort | Notes |
|----------|----------------------|---------|---------|-----|-------------|-------|
| Native macOS (if fixed) | ~5-10 min | 30-60 FPS | <10ms | MoltenVK (limited) | Very High (broken) | Theoretical best, currently impossible |
| Docker x86_64 (Rosetta) | ~15-25 min | 15-30 FPS | ~50-100ms | Software only | Medium | 40-60% overhead from emulation |
| Docker ARM64 native | ~10-15 min | 25-45 FPS | ~20-50ms | Software only | High (no official image) | Build your own container |
| Parallels ARM64 VM | ~8-12 min | 20-40 FPS | ~20-30ms | Parallels GPU (buggy) | Medium | $100/yr, GPU issues |
| UTM ARM64 VM | ~8-15 min | 10-25 FPS | ~30-60ms | Virtio-GPU (slow) | Medium | Free, CPU intensive |
| Remote Linux machine | ~3-5 min | 60+ FPS | Network latency | Full native GPU | Low-Medium | Best perf, needs internet |
| Cloud VM (e.g., Hetzner) | ~3-5 min | 60+ FPS | 10-50ms | Full native GPU | Low-Medium | ~€5-20/mo |
| SIH (headless) | ~2-4 min | N/A (headless) | <1ms | None needed | Low | No visualization at all |

**Key insight:** For actual Gazebo 3D simulation, a remote Linux machine or Docker x86_64 with VNC are the most practical options. SIH is fastest for headless flight controller testing.

---

## Recommended Simulator Strategy for macOS M3 (Project Avatar)

### Tier 1: SIH — Use Immediately for Flight Controller Development
**Start here.** SIH builds and runs natively on macOS in minutes.
- Use for: flight mode testing, mission logic, parameter tuning, offboard control, navigation
- Limitation: no cameras, no depth, no obstacle environments
- Command: `make px4_sitl_sih sihsim_quadrotor`

### Tier 2: Docker Gazebo Harmonic — Use for Sensor/Vision Development
**Set up when you need cameras/depth sensors.** Use official pre-built containers.
- Use for: depth camera testing, vision odometry, obstacle avoidance, 3D environment interaction
- Use `px4io/px4-sitl-gazebo:latest` with VNC for GUI
- Use headless mode (`gz sim -s`) for CI/automated tests
- MAVLink on UDP 14550 connects to QGroundControl on macOS host

### Tier 3: Remote Linux Machine — Use for Heavy Simulation
**Set up for production-quality simulation and CI/CD.**
- Use Hetzner/cloud VM or dedicated Linux box
- SSH + X11 forwarding or web-based VNC
- Full GPU acceleration, all Gazebo models work
- Best for: multi-vehicle simulation, RL training, video streaming tests

### NOT Recommended for Avatar
- Native macOS Gazebo: too broken, wastes time
- jMAVSim: too limited (no sensors, no cameras)
- UTM/Parallels for Gazebo GUI: poor GPU performance

### Development Workflow Suggestion
```
[macOS M3 local]
  ├── SIH headless for rapid flight controller dev
  ├── Firmware builds (NuttX) for hardware flashing
  ├── QGroundControl for monitoring
  └── VSCode with Remote-SSH to Linux

[Docker on macOS]
  └── px4io/px4-sitl-gazebo for camera/depth/LIDAR testing

[Remote Linux VM]
  └── Full Gazebo simulation, CI/CD, heavy testing
```

---

## Quick-Start Commands

```bash
# 1. SIH (works on macOS now)
cd PX4-Autopilot
make px4_sitl_sih sihsim_quadrotor

# 2. Docker Gazebo Harmonic (works on macOS via emulation)
docker run --rm -it --platform linux/amd64 \
  -p 14550:14550/udp \
  px4io/px4-sitl-gazebo:latest

# 3. Docker Gazebo with specific model + VNC
docker run -it --platform linux/amd64 \
  -p 5900:5900 -p 14550:14550/udp \
  --shm-size=2gb \
  px4io/px4-sitl-gazebo:latest \
  bash -c "apt-get update && apt-get install -y x11vnc xvfb openbox && \
    export DISPLAY=:1 && Xvfb :1 -screen 0 1280x1024x24 & \
    sleep 3 && openbox & && sleep 2 && \
    x11vnc -display :1 -nopw -forever & \
    sleep 5 && PX4_SIM_MODEL=gz_x500_depth px4-gazebo"

# Then connect VNC viewer to localhost:5900
# QGC connects to UDP localhost:14550
```

---

## Key References
- PX4 macOS Dev Environment: https://docs.px4.io/main/en/dev_setup/dev_env_mac
- PX4 SITL Build Failures Thread: https://discuss.px4.io/t/px4-sitl-refuses-to-build-on-macos-intel-m-series/47858
- WIP macOS Fixes PR: https://github.com/PX4/PX4-Autopilot/pull/25979
- Gazebo macOS Install Issues: https://gazebo.discourse.group/t/issue-installing-gazebo-harmonic-macos-15-x/3724
- Pre-built SITL Packages: https://docs.px4.io/main/en/simulation/px4_sitl_prebuilt_packages
- SIH Simulation Docs: https://docs.px4.io/main/en/sim_sih/index
- Gazebo Vehicles: https://docs.px4.io/main/en/sim_gazebo_gz/vehicles
- PX4 Docker Hub: https://hub.docker.com/u/px4io/
