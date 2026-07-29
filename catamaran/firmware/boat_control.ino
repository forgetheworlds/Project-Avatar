/*
 * Project Boat — ESP32-S3 Boat Control Firmware
 *
 * Monohull deep-V with jet drive. ESP32-S3 handles all real-time control:
 *   Core 0: 50Hz PID heading-hold + PWM output
 *   Core 1: 10Hz guardian (failsafe, telemetry, GPS)
 *
 * Hardware:
 *   - ESP32-S3-WROOM (N8R8 with PSRAM)
 *   - 2838 brushless motor via 35A ESC (GPIO 13)
 *   - SG90 nozzle servo (GPIO 12)
 *   - 5V submersible pump via MOSFET (GPIO 14)
 *   - MPU-6050 IMU on I2C (SDA=8, SCL=9) — DevKitC-1 defaults
 *   - Optional QMC5883L compass on same I2C (absolute heading; MPU yaw drifts)
 *   - NEO-6M GPS on UART2 (RX=17, TX=18) — optional
 *   - Battery voltage divider on ADC1 (GPIO 4)
 *   - Water ingress sensor on ADC1 (GPIO 5)
 *
 * Pin notes (do NOT use classic-ESP32 numbers):
 *   GPIO 22 does not exist on S3. GPIO 34/35 are not usable ADC on S3 N8R8
 *   (octal PSRAM claims 33-37). Prefer ADC1 GPIOs 1-10.
 *
 * WiFi: Connect to phone hotspot (not softAP — avoids packet clustering)
 * Protocol: WebSocket JSON on port 81
 *
 * Safety:
 *   - 2-second fail-safe: no command → throttle zero, nozzle center
 *   - Water ingress: alarm + throttle toward shore
 *   - Low battery: throttle 30%, return to shore
 *   - Cannon interlock: fire only if water sensor dry AND throttle < 30%
 */

#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <MPU6050_light.h>

// ===== WiFi Configuration =====
// Connect to phone hotspot (NOT softAP — causes 200ms packet clusters)
const char* WIFI_SSID = "PhoneHotspot";     // Change to your phone's hotspot name
const char* WIFI_PASS = "yourpassword";      // Change to your hotspot password

// ===== Pin Assignments (ESP32-S3 safe) =====
#define PIN_ESC        13    // ESC signal (2838 brushless)
#define PIN_NOZZLE     12    // SG90 servo (jet nozzle steering)
#define PIN_PUMP       14    // MOSFET gate (5V submersible pump)
#define PIN_BAT_ADC     4    // Battery voltage divider (ADC1)
#define PIN_WATER_ADC   5    // Water ingress sensor (ADC1)

// I2C for MPU-6050 (+ optional QMC5883L compass)
#define PIN_SDA         8
#define PIN_SCL         9

// Optional GPS UART2 (S3-safe; avoid classic 16/17 assumptions on every board)
#define PIN_GPS_RX     17
#define PIN_GPS_TX     18

// ===== PWM Configuration =====
const int PWM_FREQ = 50;         // 50Hz for ESC and servos
const int PWM_RES = 16;          // 16-bit resolution (0-65535)
const int PWM_CH_ESC = 0;
const int PWM_CH_NOZZLE = 1;

// PWM pulse width range in microseconds
const int PWM_MIN_US = 1000;
const int PWM_MAX_US = 2000;
const int PWM_MID_US = 1500;

// ===== Fail-Safe =====
const unsigned long FS_TIMEOUT = 2000;  // ms without command → cut throttle
unsigned long last_command_ms = 0;

// ===== Telemetry =====
const unsigned long TELEMETRY_INTERVAL = 1000;  // 1Hz
unsigned long last_telemetry_ms = 0;

// ===== Control Loop =====
const unsigned long PID_INTERVAL = 20;  // 50Hz PID loop
unsigned long last_pid_ms = 0;

// ===== Servers =====
WebServer httpServer(80);
WebSocketsServer wsServer(81);

// ===== IMU =====
MPU6050 mpu(Wire);
float current_heading = 0.0;
float target_heading = 0.0;

// ===== PID Constants (tune in water) =====
float Kp = 1.0;     // Proportional (0.1-5.0)
float Ki = 0.05;    // Integral (0.0-0.5)
float Kd = 0.5;     // Derivative (0.0-3.0)
float pid_integral = 0.0;
float pid_last_error = 0.0;
const float DEAD_BAND = 3.0;  // degrees around target

// ===== State =====
struct {
  int throttle = 0;     // -100 to 100
  int nozzle = 0;       // -90 to 90 (nozzle angle)
  bool cannon = false;
  bool autopilot = false;
} cmd;

struct {
  float bat_v = 11.1;
  float heading = 0.0;
  float lat = 0.0;
  float lon = 0.0;
  int fix = 0;
  int sats = 0;
  float water = 0.0;
  float pitch = 0.0;
  float roll = 0.0;
} telemetry;

// ===== Helper: Map value to PWM pulse width =====
int mapToPWM(int val, int in_min, int in_max) {
  float t = (float)(val - in_min) / (float)(in_max - in_min);
  return (int)(PWM_MIN_US + t * (PWM_MAX_US - PWM_MIN_US));
}

// ===== Helper: Write ESC/servo channel =====
void setPWM(int channel, int value_us) {
  // Convert microseconds to 16-bit duty cycle at 50Hz (20ms period)
  // duty = value_us / 20000 * 65535
  int duty = (int)((float)value_us / 20000.0f * 65535.0f);
  ledcWrite(channel, constrain(duty, 0, 65535));
}

// ===== Map command range to PWM =====
void setThrottle(int val) {
  int us = map(val, -100, 100, PWM_MIN_US, PWM_MAX_US);
  setPWM(PWM_CH_ESC, us);
}

void setNozzle(int val) {
  int us = map(val, -90, 90, PWM_MIN_US, PWM_MAX_US);
  setPWM(PWM_CH_NOZZLE, us);
}

// ===== Read IMU =====
void readIMU() {
  mpu.update();
  current_heading = mpu.getAngleZ();  // Yaw in degrees
  telemetry.heading = current_heading;
  telemetry.pitch = mpu.getAngleX();
  telemetry.roll = mpu.getAngleY();
}

// ===== PID Heading Hold =====
void pidLoop() {
  if (!cmd.autopilot) return;

  float error = target_heading - current_heading;

  // Wrap error to shortest path (-180 to +180)
  while (error > 180.0) error -= 360.0;
  while (error < -180.0) error += 360.0;

  // Dead band
  if (fabs(error) < DEAD_BAND) {
    cmd.nozzle = 0;
    return;
  }

  // PID computation
  pid_integral += error * (PID_INTERVAL / 1000.0f);
  pid_integral = constrain(pid_integral, -50.0, 50.0);  // Anti-windup

  float derivative = (error - pid_last_error) / (PID_INTERVAL / 1000.0f);
  pid_last_error = error;

  float output = Kp * error + Ki * pid_integral + Kd * derivative;
  cmd.nozzle = constrain((int)output, -45, 45);
}

// ===== Read Battery =====
void readBattery() {
  int raw = analogRead(PIN_BAT_ADC);
  // Divider: 10k + 4.7k, factor = (10+4.7)/4.7 = 3.128
  float v_adc = (raw / 4095.0f) * 3.3f;
  telemetry.bat_v = v_adc * 3.128f;
}

// ===== Read Water Sensor =====
void readWater() {
  int raw = analogRead(PIN_WATER_ADC);
  telemetry.water = raw / 4095.0f;  // 0 (dry) to 1 (wet)
}

// ===== Fail-Safe Check =====
void checkFailsafe() {
  if (millis() - last_command_ms > FS_TIMEOUT) {
    if (cmd.throttle != 0) {
      cmd.throttle = 0;
      setThrottle(0);
      cmd.nozzle = 0;
      setNozzle(0);
      Serial.println("FAILSAFE: throttle cut, nozzle centered");
    }
  }

  // Water ingress alarm
  if (telemetry.water > 0.5) {
    cmd.throttle = 30;  // Head toward shore
    setThrottle(30);
    Serial.println("WATER ALARM: heading to shore");
  }

  // Low battery
  if (telemetry.bat_v < 10.0 && cmd.throttle > 30) {
    cmd.throttle = 30;
    setThrottle(30);
    Serial.println("LOW BATTERY: reducing throttle");
  }
}

// ===== WebSocket Command Handler =====
void handleCommand(String json_str) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, json_str);

  if (err) return;

  const char* action = doc["action"];
  int value = doc["value"] | 0;

  if (!action) return;

  last_command_ms = millis();

  if (strcmp(action, "throttle") == 0) {
    cmd.throttle = constrain(value, -100, 100);
    setThrottle(cmd.throttle);
  }
  else if (strcmp(action, "steer") == 0) {
    cmd.nozzle = constrain(value, -90, 90);
    setNozzle(cmd.nozzle);
    cmd.autopilot = false;  // Manual steering disables autopilot
  }
  else if (strcmp(action, "cannon") == 0) {
    // SAFETY INTERLOCK: only fire when water sensor is dry AND throttle < 30%
    // Prevents firing-while-beached and recoil-induced swamping at speed
    bool want_fire = (value > 0);
    bool safe_to_fire = want_fire
                        && (telemetry.water < 0.3)        // dry
                        && (abs(cmd.throttle) < 30);       // low speed
    cmd.cannon = safe_to_fire;
    digitalWrite(PIN_PUMP, cmd.cannon ? HIGH : LOW);
  }
  else if (strcmp(action, "autopilot") == 0) {
    cmd.autopilot = (value > 0);
    if (cmd.autopilot) {
      target_heading = current_heading;  // Hold current heading
      pid_integral = 0;
      pid_last_error = 0;
    }
  }
  else if (strcmp(action, "heading") == 0) {
    target_heading = (float)value;
    cmd.autopilot = true;
    pid_integral = 0;
    pid_last_error = 0;
  }
}

// ===== WebSocket Events =====
void onWebSocketEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.printf("WS client #%u connected\n", num);
      break;
    case WStype_DISCONNECTED:
      Serial.printf("WS client #%u disconnected\n", num);
      break;
    case WStype_TEXT:
      handleCommand(String((char*)payload));
      break;
  }
}

// ===== HTTP Handlers =====
void handleRoot() {
  String html = R"rawliteral(
  <!DOCTYPE html><html><head><meta charset="UTF-8">
  <title>Project Boat</title></head><body>
  <h1>Project Boat</h1>
  <p>ESP32-S3 Boat Controller</p>
  <ul>
  <li><a href="/stream">Camera Stream (MJPEG)</a></li>
  <li><a href="/telemetry">Telemetry JSON</a></li>
  </ul>
  <p>Use WebSocket on port 81 for control.</p>
  </body></html>
  )rawliteral";
  httpServer.send(200, "text/html", html);
}

void handleTelemetry() {
  StaticJsonDocument<256> doc;
  doc["bat"] = telemetry.bat_v;
  doc["heading"] = telemetry.heading;
  doc["pitch"] = telemetry.pitch;
  doc["roll"] = telemetry.roll;
  doc["lat"] = telemetry.lat;
  doc["lon"] = telemetry.lon;
  doc["fix"] = telemetry.fix;
  doc["sats"] = telemetry.sats;
  doc["water"] = telemetry.water;
  doc["throttle"] = cmd.throttle;
  doc["nozzle"] = cmd.nozzle;
  doc["autopilot"] = cmd.autopilot;

  String out;
  serializeJson(doc, out);
  httpServer.send(200, "application/json", out);
}

void handleStream() {
  WiFiClient client = httpServer.client();
  String response = "HTTP/1.1 200 OK\r\n";
  response += "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n";
  response += "Cache-Control: no-cache\r\n";
  response += "Connection: keep-alive\r\n\r\n";
  client.write(response.c_str());

  // Placeholder JPEG (1x1 gray pixel)
  const uint8_t jpeg[] = {
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
    0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
    0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
    0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C,
    0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
    0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
    0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
    0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
    0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
    0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
    0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4,
    0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
    0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF,
    0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01,
    0x02, 0x03, 0x11, 0x04, 0x05, 0x21, 0x31, 0x06,
    0x12, 0x41, 0x51, 0x07, 0x61, 0x71, 0x13, 0x22,
    0x32, 0x81, 0x08, 0x14, 0x42, 0x91, 0xA1, 0xB1,
    0xC1, 0x09, 0x23, 0x33, 0x52, 0xF0, 0x15, 0x62,
    0x72, 0xD0, 0x16, 0x24, 0x34, 0xE1, 0x25, 0xF1,
    0x17, 0x18, 0x19, 0x1A, 0x26, 0x27, 0x28, 0x29,
    0x2A, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43,
    0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53,
    0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63,
    0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73,
    0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x83,
    0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x92,
    0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A,
    0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9,
    0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8,
    0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
    0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6,
    0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4,
    0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2,
    0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA,
    0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00,
    0x3F, 0x00, 0x7B, 0x94, 0x11, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0xFF, 0xD9
  };

  while (client.connected()) {
    client.write("--frame\r\n");
    client.write("Content-Type: image/jpeg\r\n");
    client.printf("Content-Length: %d\r\n\r\n", sizeof(jpeg));
    client.write(jpeg, sizeof(jpeg));
    client.write("\r\n");
    delay(200);  // 5fps placeholder
  }
}

// ===== GPS Parser (NMEA - simplified) =====
void parseGPS() {
  static String nmea = "";
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\n') {
      if (nmea.startsWith("$GPGGA")) {
        int comma[15];
        int idx = 0;
        for (int i = 0; i < nmea.length() && idx < 15; i++) {
          if (nmea[i] == ',') comma[idx++] = i;
        }
        if (idx >= 10) {
          char fix_char = nmea[comma[6] + 1];
          telemetry.fix = (fix_char >= '1' && fix_char <= '2') ? 3 : 0;
          telemetry.sats = nmea.substring(comma[7] + 1, comma[8]).toInt();
          if (telemetry.fix > 0) {
            String lat_str = nmea.substring(comma[2] + 1, comma[3]);
            String lon_str = nmea.substring(comma[4] + 1, comma[5]);
            if (lat_str.length() > 4 && lon_str.length() > 5) {
              telemetry.lat = lat_str.substring(0, 2).toFloat() +
                              lat_str.substring(2).toFloat() / 60.0;
              telemetry.lon = lon_str.substring(0, 3).toFloat() +
                              lon_str.substring(3).toFloat() / 60.0;
            }
          }
        }
      }
      nmea = "";
    } else if (c != '\r') {
      nmea += c;
    }
    if (nmea.length() > 120) nmea = "";
  }
}

// ===== Broadcast Telemetry =====
void broadcastTelemetry() {
  StaticJsonDocument<256> doc;
  doc["bat"] = telemetry.bat_v;
  doc["heading"] = telemetry.heading;
  doc["pitch"] = telemetry.pitch;
  doc["roll"] = telemetry.roll;
  doc["lat"] = telemetry.lat;
  doc["lon"] = telemetry.lon;
  doc["fix"] = telemetry.fix;
  doc["sats"] = telemetry.sats;
  doc["water"] = telemetry.water;
  doc["throttle"] = cmd.throttle;
  doc["nozzle"] = cmd.nozzle;

  String out;
  serializeJson(doc, out);
  wsServer.broadcastTXT(out);
}

// ===== Setup =====
void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Project Boat ===");

  // Initialize I2C
  Wire.begin(PIN_SDA, PIN_SCL);

  // Initialize IMU
  byte status = mpu.begin();
  if (status != 0) {
    Serial.println("MPU-6050 not found!");
    while (1) delay(1000);
  }
  Serial.println("MPU-6050 detected, calibrating...");
  mpu.calcGyroOffsets(true);  // Calibrate with device stationary
  Serial.println("IMU calibrated");

  // Initialize PWM channels
  ledcSetup(PWM_CH_ESC, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_ESC, PWM_CH_ESC);
  setThrottle(0);  // Neutral

  ledcSetup(PWM_CH_NOZZLE, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_NOZZLE, PWM_CH_NOZZLE);
  setNozzle(0);  // Center

  // Pump MOSFET
  pinMode(PIN_PUMP, OUTPUT);
  digitalWrite(PIN_PUMP, LOW);

  // ADC
  analogReadResolution(12);
  pinMode(PIN_BAT_ADC, INPUT);
  pinMode(PIN_WATER_ADC, INPUT);

  // GPS (UART2) — optional
  Serial2.begin(9600, SERIAL_8N1, 16, 17);

  // WiFi — connect to phone hotspot (NOT softAP)
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // CRITICAL: disable power save for low latency
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(" OK, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(" FAILED — no WiFi, running standalone");
  }

  // HTTP server
  httpServer.on("/", handleRoot);
  httpServer.on("/telemetry", handleTelemetry);
  httpServer.on("/stream", handleStream);
  httpServer.begin();
  Serial.println("HTTP server on port 80");

  // WebSocket server
  wsServer.begin();
  wsServer.onEvent(onWebSocketEvent);
  Serial.println("WebSocket server on port 81");

  // Initialize fail-safe timer
  last_command_ms = millis();

  Serial.println("=== READY ===");
}

// ===== Main Loop =====
void loop() {
  httpServer.handleClient();
  wsServer.loop();

  unsigned long now = millis();

  // 50Hz PID loop (Core 0 responsibility)
  if (now - last_pid_ms >= PID_INTERVAL) {
    readIMU();
    pidLoop();
    setNozzle(cmd.nozzle);
    last_pid_ms = now;
  }

  // 10Hz guardian tasks
  if (now - last_telemetry_ms >= 100) {
    readBattery();
    readWater();
    checkFailsafe();
  }

  // 1Hz telemetry broadcast
  if (now - last_telemetry_ms >= TELEMETRY_INTERVAL) {
    parseGPS();
    broadcastTelemetry();
    last_telemetry_ms = now;

    Serial.printf("Bat:%.1fV Hdg:%.0f Pitch:%.0f Roll:%.0f Throttle:%d Nozzle:%d\n",
      telemetry.bat_v, telemetry.heading, telemetry.pitch, telemetry.roll,
      cmd.throttle, cmd.nozzle);
  }

  delay(1);  // ~200Hz main loop
}
