# Boat-control firmware

Target: ESP32-S3 using Arduino-ESP32 3.3.11.

Pinned libraries:

- ArduinoJson 7.4.3
- WebSockets 2.7.2
- MPU6050_light 1.2.1

Install and compile with Arduino CLI:

```bash
arduino-cli config add board_manager.additional_urls \
  https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32@3.3.11
arduino-cli lib install \
  "ArduinoJson@7.4.3" "WebSockets@2.7.2" "MPU6050_light@1.2.1"
arduino-cli compile --fqbn esp32:esp32:esp32s3 .
```

Before upload, set the hotspot credentials in `boat_control.ino`, verify the
installed ESP32-S3 board variant, calibrate battery and water-sensor ADC
thresholds, and perform the steering endpoint/current commissioning described
in the main engineering release checklist.
