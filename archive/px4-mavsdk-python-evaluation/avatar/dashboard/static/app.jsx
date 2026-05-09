const { useEffect, useMemo, useRef, useState } = React;

const initialTelemetry = {
  timestamp: Date.now() / 1000,
  mode: "BOOTING",
  connected: false,
  source: "loading",
  lat: 47.397742,
  lon: 8.545594,
  alt_m: 0,
  rel_alt_m: 0,
  heading_deg: 0,
  battery_pct: null,
  groundspeed_m_s: 0,
  armed: null,
  in_air: null,
  safety_state: "unknown",
  note: "Waiting for telemetry stream",
};

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return Number(value).toFixed(digits);
}

function useTelemetry() {
  const [telemetry, setTelemetry] = useState(initialTelemetry);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const events = new EventSource("/events");
    events.onmessage = (event) => {
      const next = JSON.parse(event.data);
      setTelemetry(next);
      setHistory((points) => {
        const updated = [...points, [next.lat, next.lon]];
        return updated.slice(-800);
      });
    };
    events.onerror = () => {
      fetch("/api/telemetry")
        .then((response) => response.json())
        .then(setTelemetry)
        .catch(() => {});
    };
    return () => events.close();
  }, []);

  return { telemetry, history };
}

function FlightMap({ telemetry, history }) {
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const pathRef = useRef(null);
  const fenceRef = useRef(null);

  useEffect(() => {
    if (mapRef.current) return;
    const map = L.map("flight-map", {
      zoomControl: false,
      maxZoom: 22,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      wheelPxPerZoomLevel: 36,
    }).setView([telemetry.lat, telemetry.lon], 18);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    const satellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        attribution: "Tiles: Esri, Maxar, Earthstar Geographics",
        maxZoom: 22,
        maxNativeZoom: 19,
        detectRetina: true,
      }
    );
    const streets = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "OpenStreetMap contributors",
      maxZoom: 22,
      maxNativeZoom: 19,
      detectRetina: true,
    });
    satellite.addTo(map);
    L.control.layers({ Satellite: satellite, Streets: streets }, {}, { position: "bottomleft" }).addTo(map);
    markerRef.current = L.marker([telemetry.lat, telemetry.lon], {
      icon: L.divIcon({
        className: "drone-marker",
        html: `<div class="drone-body"><span></span></div>`,
        iconSize: [38, 38],
      }),
    }).addTo(map);
    pathRef.current = L.polyline([], { color: "#d18a22", weight: 4, opacity: 0.95 }).addTo(map);
    fenceRef.current = L.circle([telemetry.lat, telemetry.lon], {
      radius: 130,
      color: "#74806a",
      weight: 1,
      fillColor: "#74806a",
      fillOpacity: 0.08,
    }).addTo(map);
    mapRef.current = map;
  }, []);

  useEffect(() => {
    if (!mapRef.current || !markerRef.current || !pathRef.current || !fenceRef.current) return;
    const position = [telemetry.lat, telemetry.lon];
    markerRef.current.setLatLng(position);
    markerRef.current.getElement()?.style.setProperty("--heading", `${telemetry.heading_deg}deg`);
    pathRef.current.setLatLngs(history);
    fenceRef.current.setLatLng(position);
    mapRef.current.panTo(position, { animate: true, duration: 0.45 });
  }, [telemetry, history]);

  return <div id="flight-map" aria-label="Satellite flight map" />;
}

function GpsPanel({ telemetry, history }) {
  const points = history.slice(-80);
  const polyline = points
    .map(([lat, lon]) => {
      const lats = points.map((p) => p[0]);
      const lons = points.map((p) => p[1]);
      const minLat = Math.min(...lats, telemetry.lat);
      const maxLat = Math.max(...lats, telemetry.lat);
      const minLon = Math.min(...lons, telemetry.lon);
      const maxLon = Math.max(...lons, telemetry.lon);
      const latRange = Math.max(0.00001, maxLat - minLat);
      const lonRange = Math.max(0.00001, maxLon - minLon);
      const x = 8 + ((lon - minLon) / lonRange) * 84;
      const y = 92 - ((lat - minLat) / latRange) * 84;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <section className="gps-panel" aria-label="GPS path panel">
      <div className="panel-title">
        <span>GPS Path</span>
        <b>map renderer disabled</b>
      </div>
      <div className="gps-canvas">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Local GPS trail">
          <defs>
            <pattern id="gps-grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(233,226,210,.16)" strokeWidth=".35" />
            </pattern>
          </defs>
          <rect width="100" height="100" fill="url(#gps-grid)" />
          {points.length > 1 ? <polyline points={polyline} fill="none" stroke="#c2761c" strokeWidth="1.8" vectorEffect="non-scaling-stroke" /> : null}
          <circle cx="50" cy="50" r="2.5" fill="#e9e2d2" />
        </svg>
        <div className="gps-readout">
          <strong>{formatNumber(telemetry.lat, 6)}, {formatNumber(telemetry.lon, 6)}</strong>
          <span>Alt {formatNumber(telemetry.rel_alt_m)} m AGL · Heading {formatNumber(telemetry.heading_deg, 0)} deg</span>
          <small>GPS data is live from MAVSDK when connected. Tile maps are intentionally disabled for now.</small>
        </div>
      </div>
    </section>
  );
}

function StatCard({ label, value, detail }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function CameraPanel({ onSendAnnotation }) {
  const [annotation, setAnnotation] = useState(null);
  const [draft, setDraft] = useState("");
  const wrapRef = useRef(null);
  const dragStart = useRef(null);

  function relativePoint(event) {
    const rect = wrapRef.current.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * 100,
      y: ((event.clientY - rect.top) / rect.height) * 100,
    };
  }

  function onPointerDown(event) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStart.current = relativePoint(event);
    setAnnotation({ ...dragStart.current, r: 6 });
  }

  function onPointerMove(event) {
    if (!dragStart.current) return;
    const point = relativePoint(event);
    const dx = point.x - dragStart.current.x;
    const dy = point.y - dragStart.current.y;
    setAnnotation({
      x: dragStart.current.x,
      y: dragStart.current.y,
      r: Math.max(4, Math.min(42, Math.hypot(dx, dy))),
    });
  }

  function onPointerUp() {
    dragStart.current = null;
  }

  function submit() {
    if (!draft.trim() && !annotation) return;
    onSendAnnotation(draft, annotation);
    setDraft("");
  }

  return (
    <section className="camera-panel">
      <div className="panel-title">
        <span>Drone Camera</span>
        <b>draw circle + send intent</b>
      </div>
      <div
        className="camera-frame"
        ref={wrapRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        <img
          src="/camera/stream"
          alt="Drone camera feed"
          width="1280"
          height="720"
          fetchPriority="high"
          draggable="false"
        />
        <div className="reticle" />
        {annotation ? (
          <i
            className="annotation-ring"
            style={{
              left: `${annotation.x}%`,
              top: `${annotation.y}%`,
              width: `${annotation.r * 2}%`,
              height: `${annotation.r * 2}%`,
            }}
          />
        ) : null}
      </div>
      <div className="annotation-controls">
        <label className="sr-only" htmlFor="camera-intent">Camera Intent</label>
        <input
          id="camera-intent"
          name="camera-intent"
          type="text"
          autoComplete="off"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Example: follow the person I circled, keep 12m distance…"
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
          }}
        />
        <button onClick={submit}>Send</button>
      </div>
    </section>
  );
}

function AgentTerminal() {
  const terminalRef = useRef(null);
  const termInstance = useRef(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    if (!terminalRef.current || !window.Terminal || termInstance.current) return;
    const term = new window.Terminal({
      cursorBlink: true,
      convertEol: true,
      fontFamily: '"SF Mono", Menlo, Monaco, monospace',
      fontSize: 13,
      lineHeight: 1.25,
      theme: {
        background: "#090b09",
        foreground: "#e9e2d2",
        cursor: "#c2761c",
        selectionBackground: "#6f5b35",
      },
    });
    term.open(terminalRef.current);
    term.focus();
    term.write("\x1b[38;5;214mConnecting to local Project Avatar PTY…\x1b[0m\r\n");
    term.onData((data) => {
      fetch("/api/terminal/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data }),
      }).catch(() => {});
    });
    termInstance.current = term;
    connectTerminalStream(term);

    const resize = () => {
      const frame = terminalRef.current;
      if (!frame) return;
      const cellWidth = 8.2;
      const cellHeight = 17.0;
      const cols = Math.max(48, Math.floor((frame.clientWidth - 20) / cellWidth));
      const rows = Math.max(10, Math.floor((frame.clientHeight - 20) / cellHeight));
      term.resize(cols, rows);
      fetch("/api/terminal/resize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cols, rows }),
      }).catch(() => {});
    };
    const scheduleResize = () => {
      resize();
      requestAnimationFrame(resize);
      setTimeout(resize, 120);
      setTimeout(resize, 500);
    };
    scheduleResize();
    const observer = new ResizeObserver(resize);
    observer.observe(terminalRef.current);
    window.addEventListener("resize", resize);
    return () => {
      eventSourceRef.current?.close();
      observer.disconnect();
      window.removeEventListener("resize", resize);
      term.dispose();
      termInstance.current = null;
    };
  }, []);

  function connectTerminalStream(term) {
    eventSourceRef.current?.close();
    const events = new EventSource("/terminal/events");
    events.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      term.write(payload.data);
    };
    events.onerror = () => {
      term.write("\r\n\x1b[31m[dashboard] terminal stream disconnected\x1b[0m\r\n");
    };
    eventSourceRef.current = events;
  }

  async function restartTerminal() {
    await fetch("/api/terminal/restart", { method: "POST" });
    if (termInstance.current) {
      termInstance.current.reset();
      termInstance.current.write("\x1b[38;5;214m[dashboard] restarted terminal session\x1b[0m\r\n");
      connectTerminalStream(termInstance.current);
      requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    }
  }

  async function stopTerminal() {
    await fetch("/api/terminal/stop", { method: "POST" });
    if (termInstance.current) {
      termInstance.current.write("\r\n\x1b[33m[dashboard] terminal session stopped. Press Restart to launch a new agent.\x1b[0m\r\n");
    }
  }

  return (
    <section className="terminal-panel" aria-label="Local Agent Terminal">
      <div className="panel-title">
        <div>
          <span>Agent Terminal</span>
          <b>isolated Claude + Avatar MCP</b>
        </div>
        <div className="terminal-actions">
          <button type="button" onClick={stopTerminal}>Quit</button>
          <button type="button" onClick={restartTerminal}>Restart</button>
        </div>
      </div>
      <div className="terminal-frame" ref={terminalRef} />
      <p className="terminal-help">
        Real local PTY. Default launch is bare Claude with normal slash skills disabled and only the Avatar MCP config loaded.
      </p>
    </section>
  );
}

function Timeline({ history }) {
  const density = Math.min(history.length / 800, 1);
  return (
    <section className="timeline">
      <div>
        <span>Path Recorder</span>
        <strong>{history.length} samples</strong>
      </div>
      <div className="track">
        <i style={{ width: `${Math.max(8, density * 100)}%` }} />
      </div>
    </section>
  );
}

function App() {
  const { telemetry, history } = useTelemetry();
  const ageMs = useMemo(() => Math.max(0, Date.now() - telemetry.timestamp * 1000), [telemetry.timestamp]);
  const live = ageMs < 2500;

  async function sendAgentMessage(text, annotation) {
    const response = await fetch("/api/agent/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, annotation, telemetry }),
    });
    const payload = await response.json();
    if (!payload.accepted) console.warn("Dashboard message was not accepted", payload);
  }

  return (
    <main className="shell" id="main">
      <section className="topbar">
        <div>
          <p className="eyebrow">Project Avatar</p>
          <h1>Flight Deck</h1>
        </div>
        <div className={`status-pill ${live ? "live" : "stale"}`}>
          <b>{live ? "LIVE" : "STALE"}</b>
          <span>{telemetry.source}</span>
        </div>
      </section>

      <section className="deck-grid">
        <GpsPanel telemetry={telemetry} history={history} />

        <aside className="instrument-panel">
          <div className="callsign">
            <span>AV-01</span>
            <strong>{telemetry.connected ? "MAVSDK linked" : "simulation/demo"}</strong>
          </div>
          <div className="stats">
            <StatCard label="Relative Alt" value={`${formatNumber(telemetry.rel_alt_m)} m`} detail={`AMSL ${formatNumber(telemetry.alt_m)} m`} />
            <StatCard label="Ground Speed" value={`${formatNumber(telemetry.groundspeed_m_s)} m/s`} detail={`Heading ${formatNumber(telemetry.heading_deg, 0)} deg`} />
            <StatCard label="Battery" value={telemetry.battery_pct === null ? "--" : `${formatNumber(telemetry.battery_pct)}%`} detail="normalized MAVSDK value" />
            <StatCard label="Safety" value={telemetry.safety_state} detail={telemetry.in_air ? "airborne" : "not airborne"} />
          </div>
          <Timeline history={history} />
          {telemetry.note ? <p className="note">{telemetry.note}</p> : null}
        </aside>

        <CameraPanel onSendAnnotation={sendAgentMessage} />
        <AgentTerminal />
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
