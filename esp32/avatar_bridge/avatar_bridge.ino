/**
 * avatar_bridge.ino — ESP32-S3 MAVLink ↔ WiFi bridge for Project Avatar
 *
 * Hardware: XIAO ESP32-S3 (Seeed Studio), 2g, 3.3V @ 300mA
 * Role:     Bidirectional MAVLink passthrough between FC UART and ground WiFi
 *           + WebSocket telemetry streaming for PWA
 *
 * Connections:
 *   ESP32 RX (GPIO44) ← FC TELEM1 TX
 *   ESP32 TX (GPIO43) → FC TELEM1 RX
 *   ESP32 GND — FC GND
 *   ESP32 3.3V ← FC BEC 3.3V
 *
 * WiFi:
 *   Mode: AP (drone creates its own network)
 *   SSID: avatar-XXXX (last 4 of MAC)
 *   Password: avatar1234
 *   IP: 192.168.4.1
 *
 * Protocol:
 *   MAVLink v2 over UART (115200 8N1) ↔ UDP port 14550
 *   WebSocket JSON telemetry on port 8080
 *
 * Project Avatar — ESP32 MAVLink WiFi Bridge
 * Board: XIAO_ESP32S3 (Tools → Board → ESP32S3 Dev Module)
 */

#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include "mavlink/common/mavlink.h"  // MAVLink v2 C library

// ---------------------------------------------------------------------------
// Pin configuration
// ---------------------------------------------------------------------------
#define UART_FC      Serial1   // UART to flight controller
#define FC_RX        44        // GPIO44 (ESP32 RX from FC TX)
#define FC_TX        43        // GPIO43 (ESP32 TX to FC RX)
#define FC_BAUD      115200

// LED
#define LED_PIN      LED_BUILTIN

// ---------------------------------------------------------------------------
// WiFi configuration
// ---------------------------------------------------------------------------
#define WIFI_SSID_BASE  "avatar-"
#define WIFI_PASSWORD   "avatar1234"

// ---------------------------------------------------------------------------
// Network configuration
// ---------------------------------------------------------------------------
#define UDP_PORT        14550       // MAVLink UDP relay port
#define WS_PORT         8080        // WebSocket telemetry port
#define TELEMETRY_RATE  100         // JSON push interval (ms) = 10Hz

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
WebSocketsServer wsServer = WebSocketsServer(WS_PORT);
WiFiUDP udp;

IPAddress broadcastIP;  // Set to 192.168.4.255 after WiFi init

unsigned long lastTelemPush = 0;
bool fcHeartbeat = false;
unsigned long lastFcHeartbeat = 0;

// Latest telemetry values (updated from MAVLink)
struct TelemetryState {
  float lat = 0, lon = 0, alt = 0;
  float heading = 0, groundspeed = 0;
  float roll = 0, pitch = 0, yaw = 0;
  float batteryV = 0, batteryPct = 0;
  uint8_t gpsFix = 0, gpsSats = 0;
  bool armed = false;
  char mode[20] = "UNKNOWN";
  uint32_t lastPosMs = 0;
} telem;

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n\n=== Project Avatar — ESP32 Bridge ===");

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // --- WiFi AP ---
  String mac = WiFi.macAddress();
  mac.replace(":", "");
  String ssid = WIFI_SSID_BASE + mac.substring(mac.length() - 4);
  WiFi.softAP(ssid.c_str(), WIFI_PASSWORD);

  IPAddress apIP(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(apIP, apIP, subnet);

  Serial.printf("WiFi AP: %s (192.168.4.1)\n", ssid.c_str());

  // Compute broadcast address
  broadcastIP = WiFi.softAPBroadcastIP();

  // --- UART to FC ---
  UART_FC.begin(FC_BAUD, SERIAL_8N1, FC_RX, FC_TX);
  Serial.println("UART: FC on Serial1 (115200 8N1)");

  // --- UDP ---
  udp.begin(UDP_PORT);
  Serial.printf("UDP: listening on port %d\n", UDP_PORT);

  // --- WebSocket ---
  wsServer.begin();
  wsServer.onEvent(wsEventHandler);
  Serial.printf("WebSocket: listening on port %d\n", WS_PORT);

  digitalWrite(LED_PIN, HIGH);
  Serial.println("Bridge ready.\n");
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------
void loop() {
  // 1. Forward FC → WiFi (UART → UDP + WebSocket)
  forwardFcToWifi();

  // 2. Forward WiFi → FC (UDP → UART)
  forwardWifiToFc();

  // 3. WebSocket housekeeping
  wsServer.loop();

  // 4. Periodic telemetry push
  unsigned long now = millis();
  if (now - lastTelemPush >= TELEMETRY_RATE) {
    pushTelemetryJSON();
    lastTelemPush = now;
  }

  // 5. Heartbeat watchdog
  if (fcHeartbeat && (now - lastFcHeartbeat > 5000)) {
    fcHeartbeat = false;
    digitalWrite(LED_PIN, LOW);
    Serial.println("WARN: FC heartbeat lost");
  }
}

// =========================================================================
// MAVLink Forwarding
// =========================================================================

void forwardFcToWifi() {
  while (UART_FC.available()) {
    uint8_t c = UART_FC.read();

    mavlink_message_t msg;
    mavlink_status_t status;

    if (mavlink_parse_char(MAVLINK_COMM_0, c, &msg, &status)) {
      // --- Send via UDP to all ground clients ---
      uint8_t buf[MAVLINK_MAX_PACKET_LEN];
      uint16_t len = mavlink_msg_to_send_buffer(buf, &msg);

      udp.beginPacket(broadcastIP, UDP_PORT);
      udp.write(buf, len);
      udp.endPacket();

      // --- Update telemetry cache ---
      updateTelemetry(&msg);

      // --- Also send to WebSocket clients (JSON path) ---
      // Handled separately in pushTelemetryJSON for rate control
    }
  }
}

void forwardWifiToFc() {
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    uint8_t buf[MAVLINK_MAX_PACKET_LEN];
    int len = udp.read(buf, MAVLINK_MAX_PACKET_LEN);
    if (len > 0) {
      UART_FC.write(buf, len);
    }
  }
}

// =========================================================================
// Telemetry parsing (extract key fields from MAVLink messages)
// =========================================================================

void updateTelemetry(mavlink_message_t *msg) {
  uint32_t now = millis();

  switch (msg->msgid) {
    case MAVLINK_MSG_ID_HEARTBEAT: {
      mavlink_heartbeat_t hb;
      mavlink_msg_heartbeat_decode(msg, &hb);
      fcHeartbeat = true;
      lastFcHeartbeat = now;
      telem.armed = (hb.base_mode & MAV_MODE_FLAG_SAFETY_ARMED) != 0;

      // Mode string
      if (hb.base_mode & MAV_MODE_FLAG_CUSTOM_MODE_ENABLED) {
        snprintf(telem.mode, sizeof(telem.mode), "CUSTOM_%d", hb.custom_mode);
      } else {
        strcpy(telem.mode, "MANUAL");
      }
      break;
    }

    case MAVLINK_MSG_ID_GLOBAL_POSITION_INT: {
      mavlink_global_position_int_t pos;
      mavlink_msg_global_position_int_decode(msg, &pos);
      telem.lat = pos.lat / 1e7;
      telem.lon = pos.lon / 1e7;
      telem.alt = pos.relative_alt / 1000.0;
      telem.heading = pos.hdg / 100.0;
      telem.lastPosMs = now;
      break;
    }

    case MAVLINK_MSG_ID_ATTITUDE: {
      mavlink_attitude_t att;
      mavlink_msg_attitude_decode(msg, &att);
      telem.roll = att.roll * 180.0 / M_PI;
      telem.pitch = att.pitch * 180.0 / M_PI;
      telem.yaw = att.yaw * 180.0 / M_PI;
      break;
    }

    case MAVLINK_MSG_ID_VFR_HUD: {
      mavlink_vfr_hud_t hud;
      mavlink_msg_vfr_hud_decode(msg, &hud);
      telem.groundspeed = hud.groundspeed;
      break;
    }

    case MAVLINK_MSG_ID_BATTERY_STATUS: {
      mavlink_battery_status_t bat;
      mavlink_msg_battery_status_decode(msg, &bat);
      if (bat.voltages[0] != UINT16_MAX) {
        telem.batteryV = bat.voltages[0] / 1000.0;
      }
      telem.batteryPct = bat.battery_remaining;
      break;
    }

    case MAVLINK_MSG_ID_GPS_RAW_INT: {
      mavlink_gps_raw_int_t gps;
      mavlink_msg_gps_raw_int_decode(msg, &gps);
      telem.gpsFix = gps.fix_type;
      telem.gpsSats = gps.satellites_visible;
      break;
    }
  }
}

// =========================================================================
// WebSocket JSON telemetry push
// =========================================================================

void pushTelemetryJSON() {
  if (wsServer.connectedClients() == 0) return;

  JsonDocument doc;

  // Telemetry
  JsonObject tel = doc["telemetry"].to<JsonObject>();
  tel["position"]["lat"] = roundf(telem.lat * 1e7) / 1e7;
  tel["position"]["lon"] = roundf(telem.lon * 1e7) / 1e7;
  tel["altitude_m"] = roundf(telem.alt * 100) / 100;
  tel["attitude"]["roll"] = roundf(telem.roll * 10) / 10;
  tel["attitude"]["pitch"] = roundf(telem.pitch * 10) / 10;
  tel["attitude"]["yaw"] = roundf(telem.yaw * 10) / 10;
  tel["attitude"]["heading"] = roundf(telem.heading * 10) / 10;
  tel["velocity"]["groundspeed"] = roundf(telem.groundspeed * 100) / 100;
  tel["velocity"]["climb"] = 0;  // Not tracked yet
  tel["battery"]["voltage"] = roundf(telem.batteryV * 100) / 100;
  tel["battery"]["current"] = 0;
  tel["battery"]["remaining_pct"] = telem.batteryPct;
  tel["state"]["armed"] = telem.armed;
  tel["state"]["mode"] = telem.mode;
  tel["state"]["gps_fix"] = telem.gpsFix;
  tel["state"]["gps_sats"] = telem.gpsSats;
  tel["link"]["heartbeat_age_s"] = fcHeartbeat ?
    roundf((millis() - lastFcHeartbeat) / 100.0) / 10 : 999;

  // Serialize
  String payload;
  serializeJson(doc, payload);

  // Broadcast to all WebSocket clients
  wsServer.broadcastTXT(payload);
}

// =========================================================================
// WebSocket event handler
// =========================================================================

void wsEventHandler(uint8_t num, WStype_t type, uint8_t *data, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.printf("WS client %d connected\n", num);
      break;

    case WStype_DISCONNECTED:
      Serial.printf("WS client %d disconnected\n", num);
      break;

    case WStype_TEXT: {
      // Parse incoming JSON commands
      JsonDocument doc;
      DeserializationError err = deserializeJson(doc, data, len);
      if (err) return;

      const char *msgType = doc["type"];
      if (msgType && strcmp(msgType, "subscribe") == 0) {
        // Acknowledge subscription
        JsonDocument ack;
        ack["type"] = "subscribed";
        ack["channels"] = doc["channels"];
        String ackStr;
        serializeJson(ack, ackStr);
        wsServer.sendTXT(num, ackStr);
        Serial.printf("WS client %d subscribed\n", num);
      }
      break;
    }

    default:
      break;
  }
}
