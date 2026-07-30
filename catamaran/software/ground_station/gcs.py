"""
Project Catamaran — Ground Station (MacBook)

Usage:
    python gcs.py --boat 192.168.4.1

Controls:
    W/↑ = throttle FWD    S/↓ = throttle REV
    A/← = turn left       D/→ = turn right
    Space = fire cannon (hold)
    R = return to base (5s forward)
    Q = quit

Phase 2: --llm flag enables LLM agent loop (future)
"""

import argparse, asyncio, json, time, sys

HAS_CV = False
try:
    import cv2; HAS_CV = True
except ImportError:
    pass

HAS_WS = False
try:
    import websockets; HAS_WS = True
except ImportError:
    pass


class BoatConnection:
    def __init__(self, host="192.168.4.1", ws_port=81, mjpeg_port=80):
        self.host = host
        self.ws_port = ws_port
        self.mjpeg_port = mjpeg_port
        self.ws = None
        self.connected = False
        self.telemetry = {}
        self.running = True

    async def connect(self):
        if not HAS_WS:
            print("[WS] websockets not installed")
            return False
        try:
            uri = f"ws://{self.host}:{self.ws_port}"
            self.ws = await websockets.connect(uri, ping_interval=3)
            self.connected = True
            print(f"[WS] Connected to {uri}")
            return True
        except Exception as e:
            print(f"[WS] Failed: {e}")
            return False

    async def send(self, action, value=0):
        if self.ws and self.connected:
            try:
                await self.ws.send(json.dumps({"action": action, "value": value}))
            except:
                self.connected = False

    async def recv_loop(self):
        while self.running and self.ws:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=1)
                self.telemetry = json.loads(msg)
            except asyncio.TimeoutError:
                continue
            except:
                self.connected = False
                break

    def stop(self):
        self.running = False


def show_camera(host, port):
    """OpenCV camera viewer (runs in thread)."""
    if not HAS_CV:
        print("[CAM] OpenCV not available")
        return
    cap = cv2.VideoCapture(f"http://{host}:{port}/stream")
    if not cap.isOpened():
        print(f"[CAM] Stream failed")
        return
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.2); continue
        # Overlay
        cv2.putText(frame, "Catamaran", (10,25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,212,255), 2)
        cv2.putText(frame, "[WASD] Drive [Space] Fire [R]TB [Q]uit",
                    (10, frame.shape[0]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100,200,100), 1)
        cv2.imshow("Catamaran", frame)
        if cv2.waitKey(30) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()


async def keyboard_loop(conn):
    loop = asyncio.get_event_loop()
    while conn.running:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            line = line.strip().lower()
            if not line: continue
            if line == "q":
                conn.running = False; break
            elif line == "f":
                await conn.send("cannon", 1)
                await asyncio.sleep(0.3)
                await conn.send("cannon", 0)
            elif line == "r":
                await conn.send("throttle", 50)
                await asyncio.sleep(4)
                await conn.send("throttle", 0)
            elif line.startswith("t"):
                await conn.send("throttle", int(line[1:]))
            elif line.startswith("rudder"):
                await conn.send("steer", int(line[6:]))
            elif line == "s":
                print(json.dumps(conn.telemetry, indent=2))
        except (EOFError, KeyboardInterrupt):
            break


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--boat", default="192.168.4.1")
    p.add_argument("--no-camera", action="store_true")
    p.add_argument("--llm", action="store_true", help="Phase 2 LLM mode")
    return p.parse_args()


async def main():
    args = parse_args()
    conn = BoatConnection(args.boat)

    print("="*50)
    print("Project Catamaran — Ground Station")
    print(f"  Boat: {args.boat}")
    print(f"  WebSocket: ws://{args.boat}:81")
    print(f"  Camera: http://{args.boat}:80/stream")
    print(f"  LLM Mode: {'ON' if args.llm else 'OFF (Phase 1)'}")
    print("="*50)

    await conn.connect()

    if not args.no_camera:
        import threading
        t = threading.Thread(target=show_camera, args=(args.boat, 80), daemon=True)
        t.start()

    tasks = [
        asyncio.create_task(conn.recv_loop()),
        asyncio.create_task(keyboard_loop(conn)),
    ]
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        pass
    finally:
        conn.stop()
        print("Done")


if __name__ == "__main__":
    asyncio.run(main())
