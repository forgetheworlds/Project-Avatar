const nodeDetails = {
  agent: {
    title: "Any MCP-compatible AI agent",
    body: "Claude Code, OpenCode, Hermes, or future agents can connect through the standard Model Context Protocol instead of a custom interface.",
    bullets: ["Natural-language mission requests", "Tool discovery through MCP", "Confirmation workflows for risky actions"],
  },
  ground: {
    title: "MacBook ground station",
    body: "The local ground station hosts the drone MCP server, Kimi K2.5 planning path, YOLO real-time detection, and map-assisted preflight planning.",
    bullets: ["Kimi K2.5 cloud planning", "YOLOv8-nano local detection", "Runtime profiles for SITL and hardware"],
  },
  safety: {
    title: "Guardian safety layer",
    body: "Commands are validated before they reach PX4, with failsafe callbacks wired to recovery actions like RTL, Land, and Hold.",
    bullets: ["Geofence and altitude constraints", "Failsafe escalation", "Server-owned FlightTools boundary"],
  },
  flight: {
    title: "PX4 SITL first, hardware later",
    body: "Phase 0.5 validates the complete software stack in PX4 simulation before moving to Pixhawk and companion-computer hardware.",
    bullets: ["Docker SIH smoke scenarios", "PX4 SITL + Gazebo path", "MAVLink parity for hardware migration"],
  },
};

const shots = [
  ["orbit_close", "general", "Tight 8m radius orbit for close cinematic movement."],
  ["orbit_wide", "general", "Wide 20m orbit that preserves terrain and context."],
  ["follow_close", "general", "6m close follow for action shots."],
  ["follow_wide", "general", "15m follow with more environmental framing."],
  ["reveal_hero", "general", "Rising reveal shot for subject introduction."],
  ["height_locked_jump", "snowboard", "Exact altitude tracking for jumps."],
  ["snowboard_halfpipe", "snowboard", "Height-locked transitions at 8 m/s."],
  ["snowboard_powder", "snowboard", "Wide powder framing at 10 m/s."],
  ["skate_ledge_gap", "skate", "Close technical follow at 6 m/s."],
  ["skate_bowl", "skate", "Height-locked tracking for bowl transitions."],
  ["motocross_jump", "moto", "High-speed jump tracking at 12 m/s."],
  ["trail_running", "general", "Smooth runner-pace following at 5 m/s."],
  ["fpv_dynamic", "general", "Aggressive FPV-style motion."],
  ["pass_by_low", "general", "Low lateral pass for profile movement."],
  ["top_down_dynamic", "general", "Overhead subject tracking."],
];

const detail = document.querySelector("#node-detail");
const nodeButtons = [...document.querySelectorAll(".node")];
const shotGrid = document.querySelector("#shot-grid");
const shotButtons = [...document.querySelectorAll(".shot-toolbar button")];
const drone = document.querySelector("#drone-icon");
const altitude = document.querySelector("#altitude");
const speed = document.querySelector("#speed");
const battery = document.querySelector("#battery");
const copyButton = document.querySelector("#copy-command");

function renderNode(key) {
  const item = nodeDetails[key];
  detail.innerHTML = `
    <h3>${item.title}</h3>
    <p>${item.body}</p>
    <ul>${item.bullets.map((bullet) => `<li>${bullet}</li>`).join("")}</ul>
  `;
  nodeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.node === key);
  });
}

function renderShots(filter = "all") {
  const filtered = filter === "all" ? shots : shots.filter((shot) => shot[1] === filter);
  shotGrid.innerHTML = filtered
    .map(([name, sport, description]) => {
      const label = name.replaceAll("_", " ");
      return `
        <article class="shot-card" data-sport="${sport}">
          <span>${sport}</span>
          <h3>${label}</h3>
          <p>${description}</p>
          <strong>${sport === "moto" ? "12" : sport === "snowboard" ? "8-10" : "5-6"} m/s envelope</strong>
        </article>
      `;
    })
    .join("");
}

function updateTelemetry() {
  const elapsed = Date.now() / 1000;
  const x = 350 + Math.cos(elapsed / 2.6) * 210;
  const y = 248 + Math.sin(elapsed / 2.6) * 92;
  const heading = (elapsed * 28) % 360;
  drone.style.transform = `translate(${x}px, ${y}px) rotate(${heading}deg)`;
  altitude.textContent = (22 + Math.sin(elapsed / 2) * 1.8).toFixed(1);
  speed.textContent = (4.8 + Math.cos(elapsed / 3) * 0.7).toFixed(1);
  battery.textContent = Math.max(82, 96 - ((elapsed / 6) % 14)).toFixed(0);
}

nodeButtons.forEach((button) => {
  button.addEventListener("click", () => renderNode(button.dataset.node));
});

shotButtons.forEach((button) => {
  button.addEventListener("click", () => {
    shotButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    renderShots(button.dataset.filter);
  });
});

copyButton.addEventListener("click", async () => {
  const command = "./scripts/sim.sh sih\n./scripts/sim.sh scenario smoke_failsafe_rtl\n./scripts/sim.sh down";
  await navigator.clipboard.writeText(command);
  copyButton.textContent = "Copied";
  window.setTimeout(() => {
    copyButton.textContent = "Copy";
  }, 1400);
});

renderNode("agent");
renderShots();
updateTelemetry();
window.setInterval(updateTelemetry, 220);
