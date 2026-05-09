import { useTelemetry } from './hooks/useTelemetry'
import { TelemetryDashboard } from './components/TelemetryDashboard'
import { FlightControls } from './components/FlightControls'
import { PayloadStatus } from './components/PayloadStatus'
import { AlertBanner } from './components/AlertBanner'

export default function App() {
  const { telemetry, payloads, alerts, connected, error } = useTelemetry()

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <h1>AVATAR</h1>
        <div className="connection-status">
          <span className={`conn-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span>{connected ? 'LIVE' : 'DISCONNECTED'}</span>
        </div>
      </header>

      {/* Alert banner at top */}
      <AlertBanner alerts={alerts} />

      {/* Error */}
      {error && <div className="global-error">{error}</div>}

      {/* Main grid */}
      <main className="app-main">
        <section className="panel telemetry-panel">
          <TelemetryDashboard telemetry={telemetry} />
        </section>

        <section className="panel controls-panel">
          <FlightControls
            armed={telemetry?.state.armed ?? false}
            currentMode={telemetry?.state.mode ?? 'UNKNOWN'}
          />
        </section>

        <section className="panel payload-panel">
          <PayloadStatus payloads={payloads} />
        </section>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <span>Project Avatar v1.0.0</span>
        <span>{telemetry ? `${telemetry.battery.remaining_pct}% batt` : '—'}</span>
      </footer>
    </div>
  )
}
