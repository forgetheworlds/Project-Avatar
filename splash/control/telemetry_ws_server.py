"""
telemetry_ws_server.py — WebSocket telemetry streamer for PWA frontend.

Runs alongside the MCP server. Reads telemetry from the MavlinkBridge
and streams it as JSON over WebSocket to connected PWA clients.

Protocol:
    Client connects → ws://localhost:8888/telemetry
    Sends: {"type": "subscribe", "channels": ["telemetry", "payloads", "alerts"]}
    Receives: JSON telemetry push at configured rate

Channels:
    telemetry  — Position, attitude, velocity, battery, state (10Hz)
    payloads   — Payload pan/tilt, pump, reservoir status (2Hz)
    alerts     — Battery warnings, link loss, mode changes, faults

Dependencies:
    pip install websockets

Usage:
    python telemetry_ws_server.py                    # Default: ws://0.0.0.0:8888
    TELEM_WS_PORT=9000 python telemetry_ws_server.py  # Custom port
    python telemetry_ws_server.py --with-mavlink      # Connect to MAVLink directly

Project Avatar — Telemetry streaming for PWA.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional, Set

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Project-Avatar/
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("ERROR: websockets not installed. Run: pip install websockets")
    sys.exit(1)

logger = logging.getLogger("splash.telem-ws")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WS_HOST = os.environ.get("TELEM_WS_HOST", "0.0.0.0")
WS_PORT = int(os.environ.get("TELEM_WS_PORT", "8888"))
PUSH_RATE_HZ = float(os.environ.get("TELEM_PUSH_RATE", "10.0"))  # Hz
PAYLOAD_PUSH_RATE_HZ = 2.0   # Hz (payloads change slower)
ALERT_CHECK_RATE_HZ = 1.0    # Hz

# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------
BATTERY_WARN_PCT = 20
BATTERY_CRIT_PCT = 10
HEARTBEAT_WARN_S = 3.0
HEARTBEAT_LOST_S = 5.0
GPS_FIX_MIN = 3


# =========================================================================
# Telemetry Streamer
# =========================================================================

class TelemetryStreamer:
    """Reads telemetry from MavlinkBridge and streams to WebSocket clients.

    Can run standalone (with its own MAVLink connection) or import the
    bridge from the MCP server process.
    """

    def __init__(
        self,
        bridge=None,
        payload_registry=None,
        host: str = WS_HOST,
        port: int = WS_PORT,
    ):
        self.bridge = bridge
        self.payload_registry = payload_registry
        self.host = host
        self.port = port

        # Connected clients and their subscriptions
        self._clients: Set[WebSocketServerProtocol] = set()
        self._subscriptions: dict[WebSocketServerProtocol, set[str]] = {}

        # Alert state (track previous values to avoid duplicate alerts)
        self._last_battery_pct: Optional[int] = None
        self._last_mode: Optional[str] = None
        self._last_armed: Optional[bool] = None
        self._alerts_sent: set[str] = set()  # Dedup: "battery_warn", etc.

        # Server
        self._server: Optional[websockets.WebSocketServer] = None
        self._stop = asyncio.Event()

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    async def _handle_client(self, ws: WebSocketServerProtocol):
        """Handle a single WebSocket client connection."""
        self._clients.add(ws)
        self._subscriptions[ws] = {"telemetry"}  # default subscription
        client_ip = ws.remote_address[0] if ws.remote_address else "unknown"
        logger.info(f"Client connected: {client_ip} (total: {len(self._clients)})")

        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(ws, data)
                except json.JSONDecodeError:
                    logger.debug(f"Invalid JSON from {client_ip}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)
            self._subscriptions.pop(ws, None)
            logger.info(f"Client disconnected: {client_ip} (total: {len(self._clients)})")

    async def _handle_message(self, ws: WebSocketServerProtocol, data: dict):
        """Process incoming client message."""
        msg_type = data.get("type", "")

        if msg_type == "subscribe":
            channels = set(data.get("channels", ["telemetry"]))
            valid = {"telemetry", "payloads", "alerts"}
            self._subscriptions[ws] = channels & valid
            logger.debug(f"Client subscribed to: {self._subscriptions[ws]}")

        elif msg_type == "ping":
            await ws.send(json.dumps({"type": "pong", "timestamp": time.time()}))

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, msg_type: str, data: dict):
        """Send a message to all clients subscribed to msg_type."""
        if not self._clients:
            return

        payload = json.dumps({
            "type": msg_type,
            "timestamp": time.time(),
            "data": data,
        })

        dead: list[WebSocketServerProtocol] = []
        for ws in self._clients:
            if msg_type not in self._subscriptions.get(ws, set()):
                continue
            try:
                await ws.send(payload)
            except websockets.exceptions.ConnectionClosed:
                dead.append(ws)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._clients.discard(ws)
            self._subscriptions.pop(ws, None)

    # ------------------------------------------------------------------
    # Telemetry push loop
    # ------------------------------------------------------------------

    async def _telemetry_loop(self):
        """Push telemetry at configured rate."""
        interval = 1.0 / PUSH_RATE_HZ
        logger.info(f"Telemetry push started @ {PUSH_RATE_HZ}Hz (every {interval:.0f}ms)")

        while not self._stop.is_set():
            try:
                if self.bridge and self.bridge.connected:
                    t = self.bridge.get_telemetry()
                    telemetry_data = {
                        "position": {
                            "lat": round(t.lat, 7),
                            "lon": round(t.lon, 7),
                        },
                        "altitude_m": round(t.alt, 2),
                        "attitude": {
                            "roll": round(t.roll, 1),
                            "pitch": round(t.pitch, 1),
                            "yaw": round(t.yaw, 1),
                            "heading": round(t.heading, 1),
                        },
                        "velocity": {
                            "groundspeed": round(t.groundspeed, 2),
                            "climb": round(t.climb, 2),
                        },
                        "battery": {
                            "voltage": round(t.battery_voltage, 2),
                            "current": round(t.battery_current, 2),
                            "remaining_pct": t.battery_remaining,
                        },
                        "state": {
                            "armed": t.armed,
                            "mode": t.mode,
                            "gps_fix": t.gps_fix,
                            "gps_sats": t.gps_sats,
                        },
                        "link": {
                            "heartbeat_age_s": round(t.heartbeat_age_s, 1),
                        },
                    }
                    await self.broadcast("telemetry", telemetry_data)

                    # Update alert state
                    self._last_battery_pct = t.battery_remaining
                    self._last_mode = t.mode
                    self._last_armed = t.armed

            except Exception as e:
                logger.debug(f"Telemetry read skipped: {e}")

            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Payload status push loop
    # ------------------------------------------------------------------

    async def _payload_loop(self):
        """Push payload status at lower rate."""
        interval = 1.0 / PAYLOAD_PUSH_RATE_HZ
        logger.info(f"Payload push started @ {PAYLOAD_PUSH_RATE_HZ}Hz")

        while not self._stop.is_set():
            try:
                if self.payload_registry:
                    status = self.payload_registry.health_status_all()
                    if status:
                        # Simplify: just the payload-specific data
                        simplified = {}
                        for pid, info in status.items():
                            health = info.get("health", {})
                            simplified[pid] = {
                                "state": info.get("state", "UNKNOWN"),
                                "type": info.get("type", "unknown"),
                                **health.get("payload_specific", {}),
                            }
                        await self.broadcast("payloads", simplified)
            except Exception as e:
                logger.debug(f"Payload read skipped: {e}")

            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Alert check loop
    # ------------------------------------------------------------------

    async def _alert_loop(self):
        """Check thresholds and push alerts."""
        interval = 1.0 / ALERT_CHECK_RATE_HZ
        logger.info(f"Alert check started @ {ALERT_CHECK_RATE_HZ}Hz")

        while not self._stop.is_set():
            try:
                if not self.bridge or not self.bridge.connected:
                    await asyncio.sleep(interval)
                    continue

                t = self.bridge.get_telemetry()

                # Battery alerts
                bp = t.battery_remaining
                if bp <= BATTERY_CRIT_PCT and "battery_crit" not in self._alerts_sent:
                    await self._push_alert("critical",
                        f"Battery CRITICAL: {bp}% — forcing land")
                    self._alerts_sent.add("battery_crit")
                elif bp <= BATTERY_WARN_PCT and "battery_warn" not in self._alerts_sent:
                    await self._push_alert("warning",
                        f"Battery low: {bp}% — consider RTB")
                    self._alerts_sent.add("battery_warn")
                elif bp > BATTERY_WARN_PCT:
                    self._alerts_sent.discard("battery_warn")
                    self._alerts_sent.discard("battery_crit")

                # Heartbeat alerts
                hb_age = t.heartbeat_age_s
                if hb_age > HEARTBEAT_LOST_S and "link_lost" not in self._alerts_sent:
                    await self._push_alert("critical",
                        f"Link LOST: no heartbeat for {hb_age:.0f}s")
                    self._alerts_sent.add("link_lost")
                elif hb_age > HEARTBEAT_WARN_S and "link_warn" not in self._alerts_sent:
                    await self._push_alert("warning",
                        f"Link degraded: heartbeat {hb_age:.0f}s old")
                    self._alerts_sent.add("link_warn")
                elif hb_age <= HEARTBEAT_WARN_S:
                    self._alerts_sent.discard("link_warn")
                    self._alerts_sent.discard("link_lost")

                # GPS alerts
                if t.gps_fix < GPS_FIX_MIN and t.armed and "gps_lost" not in self._alerts_sent:
                    await self._push_alert("warning",
                        f"GPS fix lost (fix_type={t.gps_fix}) — position hold degraded")
                    self._alerts_sent.add("gps_lost")
                elif t.gps_fix >= GPS_FIX_MIN:
                    self._alerts_sent.discard("gps_lost")

                # Mode change alert
                if self._last_mode and t.mode != self._last_mode \
                   and "mode_change" not in self._alerts_sent:
                    await self._push_alert("info",
                        f"Mode changed: {self._last_mode} → {t.mode}")

            except Exception as e:
                logger.debug(f"Alert check skipped: {e}")

            await asyncio.sleep(interval)

    async def _push_alert(self, severity: str, message: str):
        """Send an alert to all alert subscribers."""
        await self.broadcast("alerts", {
            "severity": severity,
            "message": message,
        })
        logger.info(f"ALERT [{severity}]: {message}")

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Start the WebSocket server and all push loops."""
        logger.info(f"Starting telemetry WebSocket server on {self.host}:{self.port}")

        self._server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
        )

        # Start push loops
        loops = [
            asyncio.create_task(self._telemetry_loop()),
            asyncio.create_task(self._payload_loop()),
            asyncio.create_task(self._alert_loop()),
        ]

        logger.info(f"Telemetry WS server ready: ws://{self.host}:{self.port}/telemetry")
        logger.info(f"Push rates: telemetry={PUSH_RATE_HZ}Hz, payloads={PAYLOAD_PUSH_RATE_HZ}Hz, alerts={ALERT_CHECK_RATE_HZ}Hz")

        try:
            await self._stop.wait()
        finally:
            for task in loops:
                task.cancel()
            self._server.close()
            await self._server.wait_closed()
            logger.info("Telemetry WS server stopped.")

    def stop(self):
        """Signal the server to stop."""
        self._stop.set()


# =========================================================================
# CLI Entry Point
# =========================================================================

def main():
    """Run standalone with its own MAVLink connection.

    Usage:
        python telemetry_ws_server.py
        python telemetry_ws_server.py --with-mavlink
        TELEM_WS_PORT=9000 python telemetry_ws_server.py
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 55)
    print("  Project Avatar — Telemetry WebSocket Server")
    print("=" * 55)
    print(f"  Host:      {WS_HOST}:{WS_PORT}")
    print(f"  Telemetry: {PUSH_RATE_HZ}Hz push rate")
    print(f"  Payloads:  {PAYLOAD_PUSH_RATE_HZ}Hz push rate")
    print(f"  Alerts:    {ALERT_CHECK_RATE_HZ}Hz check rate")
    print("=" * 55)
    print()

    # Import bridge if --with-mavlink flag
    bridge = None
    if "--with-mavlink" in sys.argv:
        from splash.control.mavlink_bridge import MavlinkBridge
        sim_mode = os.environ.get("SIM_MODE", "true").lower() in ("1", "true", "yes")
        bridge = MavlinkBridge(sim_mode=sim_mode)
        bridge.connect()
        print("MAVLink connected. Streaming telemetry...")
        print()

    streamer = TelemetryStreamer(bridge=bridge)

    # Graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown():
        logger.info("Shutting down...")
        streamer.stop()
        if bridge:
            bridge.disconnect()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass  # Windows

    try:
        loop.run_until_complete(streamer.start())
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
        loop.close()


if __name__ == "__main__":
    main()
