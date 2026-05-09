# HITL/SITL Simulation Research for Safe Drone Testing

**Document Version:** 1.0  
**Date:** 2026-04-09  
**Purpose:** Research on Hardware-in-the-Loop (HITL) and Software-in-the-Loop (SITL) simulation for safe autonomous drone testing.

---

## Table of Contents

1. [Introduction](#introduction)
2. [SITL Simulation](#sitl-simulation)
   - [jMAVSim Setup](#jmavsim-setup)
   - [Gazebo SITL Configuration](#gazebo-sitl-configuration)
   - [MAVSDK with SITL](#mavsdk-with-sitl)
   - [QGroundControl Integration](#qgroundcontrol-integration)
3. [HITL Simulation](#hitl-simulation)
   - [HITL Configuration](#hitl-configuration)
   - [Flight Controller Setup](#flight-controller-setup)
   - [Serial Connection](#serial-connection)
4. [Testing Workflows](#testing-workflows)
   - [SITL for Algorithm Development](#sitl-for-algorithm-development)
   - [HITL for Hardware Validation](#hitl-for-hardware-validation)
   - [CI/CD Integration](#cicd-integration)
   - [Automated Test Scenarios](#automated-test-scenarios)
5. [Safety in Simulation](#safety-in-simulation)
   - [Simulation vs Reality](#simulation-vs-reality)
   - [Sensor Noise Modeling](#sensor-noise-modeling)
   - [Wind and Disturbance Injection](#wind-and-disturbance-injection)
   - [Vision Simulation Limitations](#vision-simulation-limitations)
6. [Quick Reference](#quick-reference)
7. [References](#references)

---

## Introduction

Hardware-in-the-Loop (HITL) and Software-in-the-Loop (SITL) simulation are essential tools for safe autonomous drone development. These simulation modes allow developers to test flight code, algorithms, and mission planning without risking physical hardware or human safety.

**SITL (Software-in-the-Loop):** Runs the complete flight stack in simulation on a desktop computer, interacting with a simulated vehicle physics model.

**HITL (Hardware-in-the-Loop):** Runs the standard PX4 firmware on actual flight controller hardware connected to a simulator providing sensor data.

**SIH (Simulation-In-Hardware):** A hybrid mode where simulation runs on the flight controller itself using simulated sensors.

---

## SITL Simulation

### jMAVSim Setup

jMAVSim is a lightweight simulator primarily for multicopter testing. It is the fastest way to start testing PX4 autopilot code.

**Basic jMAVSim Launch:**

```bash
cd <PX4-Autopilot_clone>
make px4_sitl jmavsim
```

**Default Configuration:**
- Vehicle: iris quadrotor (default)
- UDP connection on port 14580
- MAVLink telemetry on port 14570

**Environment Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `PX4_SIM_MODEL` | Vehicle model to simulate | iris |
| `PX4_NO_SIM` | Disable simulation mode | 0 |

**HITL Mode with jMAVSim:**

```bash
./Tools/simulation/jmavsim/jmavsim_run.sh -q -s -d /dev/ttyACM0 -b 921600 -r 250
```

Parameters:
- `-d /dev/ttyACM0`: Serial device for flight controller connection
- `-b 921600`: Baud rate
- `-r 250`: Refresh rate in Hz
- `-q`: Quiet mode
- `-s`: Connect to serial device

---

### Gazebo SITL Configuration

Gazebo offers more realistic physics, sensor simulation, and 3D visualization than jMAVSim. It supports complex environments, cameras, depth sensors, and various vehicle types.

**Gazebo Classic (ROS1):**

```bash
cd <PX4-Autopilot_clone>
DONT_RUN=1 make px4_sitl_default gazebo-classic
source ~/catkin_ws/devel/setup.bash    # (optional)
source Tools/simulation/gazebo-classic/setup_gazebo.bash $(pwd) $(pwd)/build/px4_sitl_default
export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:$(pwd)
export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:$(pwd)/Tools/simulation/gazebo-classic/sitl_gazebo-classic
roslaunch px4 posix_sitl.launch
```

**Gazebo Sim (GZ/Garden/Ionic):**

```bash
# Basic launch
make px4_sitl_default gz

# Standalone mode with specific world
PX4_GZ_STANDALONE=1 \
PX4_SYS_AUTOSTART=4001 \
PX4_SIM_MODEL=gz_x500 \
PX4_GZ_WORLD=windy \
./build/px4_sitl_default/bin/px4
```

**Common Vehicle Models:**

| Command | Description |
|---------|-------------|
| `make px4_sitl gz_x500` | X500 quadrotor |
| `make px4_sitl gz_x500_depth` | X500 with OAK-D depth camera |
| `make px4_sitl gazebo-classic_iris_depth_camera` | Iris with depth camera (ROS) |
| `make px4_sitl gz_plane` | Fixed-wing aircraft |
| `make px4_sitl gz_tailsitter` | Tailsitter VTOL |

**World Configuration (SDF):**

```xml
<?xml version="1.0" ?>
<sdf version="1.10">
    <world name="drone_world">
        <physics name="1ms" type="ignored">
            <max_step_size>0.001</max_step_size>
            <real_time_factor>1.0</real_time_factor>
        </physics>
        <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"></plugin>
        <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"></plugin>
        <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"></plugin>

        <light type="directional" name="sun">
            <cast_shadows>true</cast_shadows>
            <pose>0 0 10 0 0 0</pose>
            <diffuse>0.8 0.8 0.8 1</diffuse>
            <specular>0.2 0.2 0.2 1</specular>
            <direction>-0.5 0.1 -0.9</direction>
        </light>

        <model name="ground_plane">
            <static>true</static>
            <link name="link">
                <collision name="collision">
                    <geometry>
                        <plane><normal>0 0 1</normal></plane>
                    </geometry>
                </collision>
                <visual name="visual">
                    <geometry>
                        <plane><normal>0 0 1</normal><size>100 100</size></plane>
                    </geometry>
                </visual>
            </link>
        </model>
    </world>
</sdf>
```

---

### MAVSDK with SITL

MAVSDK provides high-level APIs for controlling drones via MAVLink. It is ideal for automated testing and mission development.

**Building PX4 SITL for MAVSDK:**

```bash
cd path/to/Firmware/
make px4_sitl gazebo
```

**Running MAVSDK Integration Tests with Autostart:**

```bash
cd path/to/MAVSDK/
AUTOSTART_SITL=1 ./build/debug/src/integration_tests/integration_tests_runner
```

**Headless CI Testing:**

```bash
AUTOSTART_SITL=1 HEADLESS=1 ./build/debug/src/integration_tests/integration_tests_runner
```

**Filter Telemetry Tests Only:**

```bash
./build/default/src/integration_tests/integration_tests_runner --gtest_filter="SitlTest.Telemetry*"
```

**MAVSDK C++ Mission Example:**

```cpp
#include <mavsdk/mavsdk.h>
#include <mavsdk/plugins/mission/mission.h>
#include <mavsdk/plugins/action/action.h>

int main() {
    mavsdk::Mavsdk mavsdk;
    mavsdk::ConnectionResult connection_result = mavsdk.add_udp_connection(5600);

    if (connection_result != mavsdk::ConnectionResult::Success) {
        std::cerr << "Connection failed" << std::endl;
        return 1;
    }

    auto prom = mavsdk.all_systems_detected();
    prom.wait_for([](mavsdk::Mavsdk::SystemsDetectedState state) {
        return state == mavsdk::Mavsdk::SystemsDetectedState::Success;
    });

    auto system = mavsdk.systems().at(0);
    auto mission = std::make_shared<mavsdk::Mission>(system);
    auto action = std::make_shared<mavsdk::Action>(system);

    // Create mission
    mavsdk::Mission::MissionPlan mission_plan;
    mission_plan.mission_items.push_back(mavsdk::Mission::MissionItem{});
    mission_plan.mission_items.back().latitude_deg = 47.397742;
    mission_plan.mission_items.back().longitude_deg = 8.545594;
    mission_plan.mission_items.back().relative_altitude_m = 10.0f;

    // Upload and execute
    mission->upload_mission_async(mission_plan, [](mavsdk::Mission::Result result) {
        std::cout << "Upload: " << (result == mavsdk::Mission::Result::Success ? "Success" : "Failed") << std::endl;
    });

    action->arm_async([](mavsdk::Action::Result result) {
        std::cout << "Arm: " << (result == mavsdk::Action::Result::Success ? "Success" : "Failed") << std::endl;
    });

    return 0;
}
```

**MAVSDK Offboard Control:**

```cpp
mavsdk::Offboard offboard(system.value());

// Set velocity command
mavsdk::Offboard::VelocityNed velocity_ned{0.0f, 0.0f, 0.0f, 0.0f};
offboard.set_velocity_ned(velocity_ned);

// Start offboard mode
auto result_start = offboard.start();

// Move north at 5 m/s for 10 seconds
velocity_ned.north_m_s = 5.0f;
for (int i = 0; i < 100; ++i) {
    offboard.set_velocity_ned(velocity_ned);
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}

offboard.stop();
```

---

### QGroundControl Integration

QGroundControl (QGC) serves as the ground control station for simulation, providing mission planning, parameter configuration, and flight monitoring.

**Enable Virtual Joystick:**

1. Click the 'Q' icon in the top toolbar
2. Select 'Application Settings'
3. Navigate to 'General' tab
4. Check the 'Virtual Joystick' option

**Joystick Configuration:**

1. Connect physical joystick or gamepad via USB
2. Select the **Gear** icon (Vehicle Configuration)
3. Select **Joystick** from the sidebar
4. Select your joystick from the 'Active Joystick' dropdown
5. Navigate to **Calibrate** tab and click **Start**
6. Follow on-screen calibration instructions
7. Test axis and button monitors in the **General** tab

**Enable Joystick Support in PX4:**

Set parameter `COM_RC_IN_MODE` to `1` (Joystick).

**MAVLink Connection:**

QGC automatically connects to SITL on UDP port 14570 (or 14550 depending on configuration).

**Note:** Virtual joystick control may be less responsive than physical RC due to MAVLink transmission latency. Use a USB joystick for better sensitivity.

---

## HITL Simulation

### HITL Configuration

HITL runs PX4 firmware on actual flight controller hardware while receiving simulated sensor data from Gazebo or jMAVSim.

**Supported Configurations:**
- Multicopters: jMAVSim or Gazebo Classic
- VTOL aircraft: Gazebo Classic only

**Enable HITL/SIH:**

```bash
# For HITL mode (flight controller + simulator)
param set SYS_HITL 1

# For SIH mode (simulation on flight controller)
param set-default SYS_HITL 2
```

**Airframe Configuration:**

Set appropriate SYS_AUTOSTART parameter for your vehicle type:

```
SYS_AUTOSTART = 4001    # X500 Quadrotor
SYS_AUTOSTART = 2100    # Generic Standard Plane
SYS_AUTOSTART = 13000   # Generic Tailsitter VTOL
```

---

### Flight Controller Setup

**Requirements:**
- Flight controller (Pixhawk, Cube, etc.) with USB or UART connection
- USB-to-serial adapter for some configurations
- Gazebo or jMAVSim simulator on host computer

**UART/Serial Configuration:**

For STM32-based flight controllers, UART ports are defined in `nsh/defconfig`:

```c
#define CONFIG_STM32F7_UART4=y
#define CONFIG_STM32F7_UART7=y
#define CONFIG_STM32F7_USART1=y
#define CONFIG_STM32F7_USART2=y
#define CONFIG_STM32F7_USART3=y
#define CONFIG_STM32F7_USART6=y
```

Device names map to `/dev/ttyS0`, `/dev/ttyS1`, etc.

**Enable UART on Linux Companion Computers:**

```bash
sudo vi /boot/config.txt
# Ensure enable_uart is set to 1:
enable_uart=1
```

Reboot after modification.

---

### Serial Connection

**jMAVSim HITL Connection:**

```bash
./Tools/simulation/jmavsim/jmavsim_run.sh -q -s -d /dev/ttyACM0 -b 921600 -r 250
```

**Connection Flow:**
1. Connect flight controller to computer via USB
2. Identify serial port (e.g., `/dev/ttyACM0` on Linux, `/dev/tty.usbmodemXXX` on macOS, `COM3` on Windows)
3. Ensure flight controller is configured for HITL mode (SYS_HITL=1)
4. Launch simulator with appropriate serial device and baud rate

**MAVSDK-Python Serial Connection:**

```python
await drone.connect(system_address="serial:///dev/ttyTHS1:921600")
```

---

## Testing Workflows

### SITL for Algorithm Development

SITL is the primary tool for developing and testing flight control algorithms, path planning, and mission logic.

**Recommended Workflow:**

1. **Algorithm Development Phase:**
   ```bash
   # Start SITL for rapid iteration
   make px4_sitl gz_x500
   ```

2. **MAVSDK Test Script Development:**
   ```python
   # Python test with MAVSDK
   from mavsdk import System
   
   drone = System()
   await drone.connect(system_address="udp://:14540")
   
   # Test custom algorithm
   await drone.action.arm()
   await drone.action.takeoff()
   # ... algorithm testing
   ```

3. **Parameterized Testing:**
   - Test with varying wind conditions
   - Simulate sensor failures
   - Validate edge cases (low battery, GPS loss)

**Key Metrics to Monitor:**
- Position hold accuracy
- Path tracking error
- State estimation convergence
- Controller stability margins

---

### HITL for Hardware Validation

HITL validates that flight code behaves correctly on actual flight controller hardware.

**Use Cases:**
- Hardware-specific timing verification
- Sensor driver validation
- Memory and CPU usage profiling
- Timing jitter analysis

**HITL Test Sequence:**

1. Configure flight controller for HITL
2. Connect to simulator
3. Execute automated test missions
4. Monitor resource usage on flight controller
5. Validate timing constraints

---

### CI/CD Integration

PX4 uses GitHub Actions for continuous integration with automated simulation testing.

**CI Configuration:**

```cmake
# CMakeLists.txt - Enable testing for SITL builds
option(CMAKE_TESTING "Configure test targets" OFF)
if(${PX4_CONFIG} STREQUAL "px4_sitl_test")
    set(CMAKE_TESTING ON)
endif()
if(CMAKE_TESTING)
    include(CTest)
endif()
```

**Running MAVSDK Tests in CI:**

```bash
test/mavsdk_tests/mavsdk_test_runner.py test/mavsdk_tests/configs/sitl.json --speed-factor 10
```

**Headless Testing:**

```bash
AUTOSTART_SITL=1 HEADLESS=1 ./integration_tests_runner
```

**Test Categories:**
- Unit tests (GTest): `px4_add_unit_gtest(SRC TestFile.cpp)`
- Integration tests (MAVSDK/Catch2): Full flight scenarios
- ROS/MAVROS tests: ROS integration validation

**GitHub Actions Workflow:**

Integration tests run automatically on every pull request to ensure code quality and prevent regressions.

---

### Automated Test Scenarios

**Mission Testing with MAVSDK:**

```bash
# Run all SITL integration tests
test/mavsdk_tests/mavsdk_test_runner.py test/mavsdk_tests/configs/sitl.json --speed-factor 10

# Run specific model test
test/mavsdk_tests/mavsdk_test_runner.py test/mavsdk_tests/configs/sitl.json \
    --speed-factor 10 --model tailsitter --case 'Fly VTOL mission'
```

**C++ Test Case Structure (Catch2):**

```cpp
#include "catch.hpp"
#include "autopilot_tester.h"

TEST_CASE("Fly VTOL mission", "[tailsitter]") {
    AutopilotTester tester;
    tester.connect();
    tester.takeoff(10);
    tester.fly_to_location({10, 0, -5});
    REQUIRE(tester.is_landed() == false);
    tester.return_to_launch();
    REQUIRE(tester.is_landed() == true);
}
```

**ROS Integration Test Template:**

```python
#!/usr/bin/env python
PKG = 'px4'

import unittest
import rospy
from sensor_msgs.msg import NavSatFix

class MavrosMissionTest(unittest.TestCase):
    def setUp(self):
        rospy.init_node('test_node', anonymous=True)
        rospy.wait_for_service('mavros/cmd/arming', 30)
        rospy.Subscriber("mavros/global_position/global", NavSatFix, self.position_callback)
        self.has_global_pos = False
        self.rate = rospy.Rate(10)

    def position_callback(self, data):
        self.has_global_pos = True

    def test_mission(self):
        while not self.has_global_pos:
            self.rate.sleep()
        # Execute mission test

if __name__ == '__main__':
    import rostest
    rostest.rosrun(PKG, 'mission_test', MavrosMissionTest)
```

**Test Scenarios Matrix:**

| Scenario | SITL | HITL | Purpose |
|----------|------|------|---------|
| Basic takeoff/land | ✓ | ✓ | Core flight control |
| Waypoint mission | ✓ | ✓ | Navigation accuracy |
| Offboard control | ✓ | ✓ | Custom controller validation |
| GPS failure | ✓ | ✓ | Failsafe testing |
| Low battery RTL | ✓ | ✓ | Safety behavior |
| Geofence violation | ✓ | ✓ | Boundary enforcement |
| Wind compensation | ✓ | Limited | Control robustness |
| Vision-based nav | ✓ | Limited | Perception algorithms |

---

## Safety in Simulation

### Simulation vs Reality

**When Simulation Diverges from Reality:**

1. **Physics Model Limitations:**
   - Simplified aerodynamics (no blade flapping, ground effect)
   - Idealized rigid body dynamics
   - Perfect actuators (no motor lag, no ESC latency)

2. **Sensor Modeling Gaps:**
   - Perfect GPS (no multi-path, no urban canyon)
   - Ideal IMU (no vibration-induced noise)
   - Perfect camera (no lens distortion, no motion blur)

3. **Environmental Factors:**
   - Simplified wind (constant or simple turbulence models)
   - No temperature effects on sensors
   - No electromagnetic interference

**Risk Mitigation:**

| Simulation Result | Real-World Action |
|-------------------|-------------------|
| Algorithm works perfectly | Test with 50% reduced gains first |
| Margins are tight | Increase safety bounds by 2x |
| Edge cases pass | Add additional real-world validation |
| New feature | Graduated rollout with telemetry monitoring |

**Graduated Testing Protocol:**

1. SITL (hours of testing)
2. HITL (flight controller validation)
3. Tethered flight (physical constraints)
4. Open-field with safety pilot
5. Autonomous operations

---

### Sensor Noise Modeling

PX4 SITL provides configurable sensor noise parameters to improve realism.

**IMU Noise Parameters (EKF2):**

```
EKF2_ACC_NOISE: 0.35       # Accelerometer noise (m/s^2)
EKF2_ACC_B_NOISE: 0.003    # Accelerometer bias noise (m/s^2)
EKF2_GYR_NOISE: 0.015      # Gyroscope noise (rad/s)
EKF2_GYR_B_NOISE: 0.001    # Gyroscope bias noise (rad/s)
```

**Simulated Sensor Offsets:**

```
SIM_BARO_OFF_P: 0.0         # Barometer pressure offset (Pa)
SIM_BARO_OFF_T: 0.0         # Barometer temperature offset (C)
SIM_GPS_USED: 10            # Number of GPS satellites
SIM_MAG_OFFSET_X: 0.0       # Magnetometer X offset (gauss)
SIM_MAG_OFFSET_Y: 0.0       # Magnetometer Y offset (gauss)
SIM_MAG_OFFSET_Z: 0.0       # Magnetometer Z offset (gauss)
```

**Drag Model Noise:**

```
EKF2_DRAG_NOISE: 2.5        # Observation noise variance
# Higher values = slower wind estimate adjustment
```

**Failure Injection for Testing:**

```
SIM_ARSPD_FAIL: 0/1         # Airspeed sensor failure simulation
```

Command: `VEHICLE_CMD_INJECT_FAILURE (420)` for runtime failure injection.

**Realistic Noise Model Implementation:**

To improve simulation fidelity, add these effects:
1. Vibration noise on IMU (frequency-dependent)
2. GPS position drift (random walk)
3. Barometer altitude noise (pressure fluctuations)
4. Magnetometer interference (motor current effects)

---

### Wind and Disturbance Injection

Gazebo supports wind field simulation for testing control robustness.

**Wind Configuration:**

```bash
# Launch with windy world
make px4_sitl gz_x500 PX4_GZ_WORLD=windy
```

**Wind-Related Parameters:**

```
COM_WIND_MAX: 12.0          # High wind failsafe threshold (m/s)
COM_WIND_WARN: 10.0         # Wind speed warning threshold (m/s)
COM_WIND_MAX_ACT: 1         # Action on high wind (0=none, 1=RTL, 2=land)
```

**External Wind Estimate:**

Command: `VEHICLE_CMD_EXTERNAL_WIND_ESTIMATE (43004)` for feeding external wind data.

**FT Technologies Wind Sensor (Physical):**

```bash
# Start physical wind sensor driver
ft_technologies_serial start -d /dev/ttyS1
```

**Gazebo Force Field Plugin:**

System plugins can apply external forces to models for disturbance testing:

```cpp
// Apply force to entity
void ApplyForce(const gz::sim::Entity &_entity,
                gz::sim::EntityComponentManager &_ecm,
                const gz::math::Vector3d &_force) {
    auto link = gz::sim::Link(_entity);
    link.EnableVelocityChecks(_ecm, true);
    link.AddWorldForce(_ecm, _force);
}
```

**Disturbance Test Scenarios:**

| Test | Wind Speed | Duration | Pass Criteria |
|------|------------|----------|---------------|
| Hover stability | 0 m/s | 60s | Position hold < 0.5m |
| Light wind | 5 m/s | 60s | Position hold < 1.0m |
| Moderate wind | 10 m/s | 60s | No failsafe trigger |
| Gust response | 0-15 m/s | 30s | Recovery < 5s |
| Crosswind flight | 8 m/s | 60s | Path tracking < 2m |

---

### Vision Simulation Limitations

Computer vision simulation has inherent limitations that require careful consideration.

**Current Capabilities:**

```bash
# Depth camera simulation
make px4_sitl gz_x500_depth

# Obstacle distance message format
ObstacleDistance:
  - timestamp
  - frame (coordinate frame)
  - sensor_type
  - distances[72] (cm, 0 = directly in front)
  - increment (degrees)
  - min_distance
  - max_distance
  - angle_offset
```

**Limitations of Simulated Vision:**

| Aspect | Simulation | Reality Gap |
|--------|------------|-------------|
| Lighting | Perfect, static | Variable, dynamic shadows |
| Texture | Procedural/synthetic | Complex real-world textures |
| Motion blur | Minimal | Significant at high speeds |
| Lens effects | Simplified | Chromatic aberration, distortion |
| Occlusions | Clean edges | Partial occlusion, transparency |
| Depth accuracy | Perfect | Noise, missing values at edges |
| Object variety | Limited models | Infinite real-world variation |

**Mitigation Strategies:**

1. **Domain Randomization:**
   - Randomize textures, lighting, camera parameters
   - Add noise to depth data
   - Vary simulation physics parameters

2. **Sim-to-Real Transfer:**
   - Use GANs or style transfer to make synthetic images more realistic
   - Fine-tune vision models on real data

3. **Conservative Planning:**
   - Add larger safety margins when using vision-based navigation
   - Maintain redundant navigation methods (GPS + vision + inertial)

4. **Hardware-in-the-Loop Vision:**
   - Stream simulated camera feed through actual companion computer
   - Process with real vision algorithms before sending commands

**Safe Vision Testing Protocol:**

```
Stage 1: Pure simulation (algorithm validation)
Stage 2: Recorded real data playback (sensor validation)
Stage 3: Indoor motion capture (controlled testing)
Stage 4: Outdoor with safety pilot (real-world validation)
```

---

## Quick Reference

### Command Cheat Sheet

```bash
# Start SITL - jMAVSim
make px4_sitl jmavsim

# Start SITL - Gazebo Classic
make px4_sitl gazebo-classic

# Start SITL - Gazebo Sim (Garden/Ionic)
make px4_sitl gz
make px4_sitl gz_x500

# HITL with jMAVSim
./Tools/simulation/jmavsim/jmavsim_run.sh -q -s -d /dev/ttyACM0 -b 921600 -r 250

# MAVSDK test runner
test/mavsdk_tests/mavsdk_test_runner.py test/mavsdk_tests/configs/sitl.json --speed-factor 10

# Headless CI testing
AUTOSTART_SITL=1 HEADLESS=1 ./integration_tests_runner

# Enable HITL mode
param set SYS_HITL 1

# Enable SIH mode
param set SYS_HITL 2
```

### Key Parameters

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| SYS_HITL | HITL/SIH mode | 0 | 0-2 |
| SYS_AUTOSTART | Airframe type | 4001 | Varies |
| EKF2_ACC_NOISE | Accel noise | 0.35 | 0.01-1.0 |
| EKF2_GYR_NOISE | Gyro noise | 0.015 | 0.001-0.1 |
| SIM_BARO_OFF_P | Baro pressure offset | 0 | - |
| SIM_GPS_USED | GPS satellites | 10 | 0-50 |
| COM_WIND_MAX | Wind failsafe threshold | 12.0 | m/s |
| COM_RC_IN_MODE | RC input mode | 0 | 0-3 |

### File Locations

| Component | Path |
|-----------|------|
| SITL configs | `Tools/simulation/` |
| Gazebo worlds | `Tools/simulation/gz/worlds/` |
| MAVSDK tests | `test/mavsdk_tests/` |
| Test configs | `test/mavsdk_tests/configs/` |
| Airframe definitions | `ROMFS/px4fmu_common/init.d/airframes/` |

---

## References

### Documentation

1. **PX4 Autopilot Documentation:** https://docs.px4.io/main/en/simulation/
2. **PX4 HITL Guide:** https://docs.px4.io/main/en/simulation/hitl.html
3. **Gazebo Documentation:** https://gazebosim.org/docs
4. **MAVSDK Documentation:** https://mavsdk.mavlink.io/main/en/
5. **QGroundControl User Guide:** https://docs.qgroundcontrol.com/master/en/

### Repositories

1. **PX4 Autopilot:** https://github.com/PX4/PX4-Autopilot
2. **MAVSDK:** https://github.com/mavlink/MAVSDK
3. **Gazebo:** https://github.com/gazebosim/gz-sim
4. **QGroundControl:** https://github.com/mavlink/qgroundcontrol

### Related Standards

1. **MAVLink Protocol:** https://mavlink.io/en/
2. **SDF (Simulation Description Format):** http://sdformat.org/
3. **ROS2 Integration:** https://docs.px4.io/main/en/ros2/

---

## Summary

SITL and HITL simulation provide essential safety layers for autonomous drone development:

1. **SITL** enables rapid algorithm iteration with simulated physics and sensors
2. **HITL** validates flight code on actual hardware before flight
3. **Automated testing** with MAVSDK enables regression testing in CI/CD
4. **Safety awareness** of simulation limitations prevents dangerous assumptions

**Best Practices:**
- Always start with SITL for new algorithms
- Progress through HITL before any physical flight
- Use parameterized noise models to improve simulation fidelity
- Maintain safety margins when transferring from simulation to reality
- Document all simulation assumptions and limitations

---

*Document generated from Context7 PX4 Autopilot, MAVSDK, Gazebo, and QGroundControl documentation.*
