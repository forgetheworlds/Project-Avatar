/**
 * Project Catamaran — Phone Control PWA
 * Connects to ESP32 via WebSocket port 81 + MJPEG stream on port 80.
 */

const state = {
  ip: "192.168.4.1",
  ws: null,
  connected: false,
  telemetry: {},
  cmd: { throttle: 0, rudder: 0, cannon: false },
  joystick: { active: false, touchId: null }
};
const STEERING_LIMIT_DEG = 18; // Commissioning limit; mechanical stop is ±25°.

function connect() {
  const input = document.getElementById("boat-ip");
  if (input) state.ip = input.value;

  document.getElementById("connect").style.display = "none";
  const cam = document.getElementById("cam-img");
  if (cam) cam.src = `http://${state.ip}/stream`;

  if (state.ws) state.ws.close();
  state.ws = new WebSocket(`ws://${state.ip}:81`);

  state.ws.onopen = () => {
    state.connected = true;
    document.getElementById("status").className = "ok";
  };
  state.ws.onclose = () => {
    state.connected = false;
    document.getElementById("status").className = "";
  };
  state.ws.onmessage = (e) => {
    try {
      state.telemetry = JSON.parse(e.data);
      updateHUD(state.telemetry);
    } catch(_) {}
  };
}

function send(a, v) {
  if (state.ws && state.connected)
    state.ws.send(JSON.stringify({ action: a, value: v }));
}

function updateHUD(t) {
  const bat = document.getElementById("h-bat");
  const hdg = document.getElementById("h-hdg");
  const gps = document.getElementById("h-gps");
  if (bat) bat.textContent = (t.bat || 0).toFixed(1) + "V";
  if (hdg) hdg.textContent = (t.heading || 0).toFixed(0) + "°";
  if (gps) gps.textContent = (t.fix ? (t.sats||0)+"s" : "No fix");
}

// Joystick
function setupJoy() {
  const base = document.getElementById("joy-base");
  const knob = document.getElementById("joy-knob");
  if (!base) return;

  function pos(cx, cy) {
    const r = base.getBoundingClientRect();
    const dx = cx - (r.left + r.width/2);
    const dy = cy - (r.top + r.height/2);
    const maxR = r.width/2 - 28;
    const d = Math.hypot(dx, dy);
    const c = Math.min(d, maxR);
    const a = Math.atan2(dy, dx);
    return { x: Math.cos(a)*c, y: Math.sin(a)*c,
             nx: Math.cos(a)*(c/maxR), ny: Math.sin(a)*(c/maxR) };
  }

  function move(cx, cy) {
    const p = pos(cx, cy);
    knob.style.transform = `translate(${p.x-25}px,${p.y-25}px)`;
    // Dead zone
    if (Math.abs(p.nx) < 0.08) p.nx = 0;
    if (Math.abs(p.ny) < 0.08) p.ny = 0;
    state.cmd.throttle = Math.round(-p.ny * 100);
    state.cmd.rudder = Math.round(p.nx * STEERING_LIMIT_DEG);
    send("throttle", state.cmd.throttle);
    send("steer", state.cmd.rudder);
  }

  function reset() {
    knob.style.transform = "";
    state.cmd.throttle = 0; state.cmd.rudder = 0;
    send("throttle", 0); send("steer", 0);
  }

  base.addEventListener("touchstart", e => {
    e.preventDefault();
    const t = e.changedTouches[0];
    state.joystick.touchId = t.identifier;
    move(t.clientX, t.clientY);
  });
  base.addEventListener("touchmove", e => {
    e.preventDefault();
    for (const t of e.changedTouches)
      if (t.identifier === state.joystick.touchId) move(t.clientX, t.clientY);
  });
  base.addEventListener("touchend", e => {
    for (const t of e.changedTouches)
      if (t.identifier === state.joystick.touchId) reset();
  });
  base.addEventListener("touchcancel", reset);
}

// Fire button
function setupFire() {
  const btn = document.getElementById("fire-btn");
  btn.addEventListener("touchstart", e => { e.preventDefault(); btn.classList.add("on"); send("cannon",1); });
  btn.addEventListener("touchend", () => { btn.classList.remove("on"); send("cannon",0); });
  btn.addEventListener("touchcancel", () => { btn.classList.remove("on"); send("cannon",0); });
  btn.addEventListener("mousedown", () => { btn.classList.add("on"); send("cannon",1); });
  btn.addEventListener("mouseup", () => { btn.classList.remove("on"); send("cannon",0); });
  btn.addEventListener("mouseleave", () => { btn.classList.remove("on"); send("cannon",0); });
}

// RTB button
function setupRTB() {
  document.getElementById("rtb-btn").addEventListener("click", () => {
    send("throttle", 50);
    setTimeout(() => send("throttle", 0), 4000);
  });
}

// Keyboard
document.addEventListener("keydown", e => {
  switch(e.key) {
    case "w": case "ArrowUp": send("throttle", Math.min(100, (state.cmd.throttle||0)+20)); break;
    case "s": case "ArrowDown": send("throttle", Math.max(-100, (state.cmd.throttle||0)-20)); break;
    case "a": case "ArrowLeft": send("steer", -STEERING_LIMIT_DEG); break;
    case "d": case "ArrowRight": send("steer", STEERING_LIMIT_DEG); break;
    case " ": e.preventDefault(); send("cannon",1); break;
  }
});
document.addEventListener("keyup", e => {
  if (["w","s","ArrowUp","ArrowDown"].includes(e.key)) send("throttle",0);
  if (["a","d","ArrowLeft","ArrowRight"].includes(e.key)) send("steer",0);
  if (e.key === " ") send("cannon",0);
});

document.addEventListener("DOMContentLoaded", () => { setupJoy(); setupFire(); setupRTB(); });
