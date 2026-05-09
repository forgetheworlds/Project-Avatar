import type { TelemetryData } from '../hooks/useTelemetry'

interface Props {
  telemetry: TelemetryData | null
}

export function TelemetryDashboard({ telemetry }: Props) {
  if (!telemetry) {
    return (
      <div className="dashboard empty">
        <div className="spinner" />
        <p>Waiting for telemetry...</p>
      </div>
    )
  }

  const { position, altitude_m, attitude, velocity, battery, state, link } = telemetry
  const linkOk = link.heartbeat_age_s < 3
  const gpsOk = state.gps_fix >= 3
  const batteryOk = battery.remaining_pct > 20

  return (
    <div className="dashboard">
      {/* Top bar: mode + armed + link + alerts */}
      <div className="top-bar">
        <span className={`mode-badge ${state.mode.toLowerCase()}`}>
          {state.mode}
        </span>
        <span className={`armed-badge ${state.armed ? 'armed' : 'disarmed'}`}>
          {state.armed ? 'ARMED' : 'DISARMED'}
        </span>
        <span className={`link-badge ${linkOk ? 'ok' : 'bad'}`}>
          {linkOk ? `LINK ${link.heartbeat_age_s.toFixed(1)}s` : 'LINK LOST'}
        </span>
        <span className={`gps-badge ${gpsOk ? 'ok' : 'bad'}`}>
          GPS {state.gps_sats}sats {gpsOk ? '3D' : 'NO FIX'}
        </span>
      </div>

      {/* Main HUD: altitude + speed */}
      <div className="hud-main">
        <div className="hud-altitude">
          <span className="hud-value">{altitude_m.toFixed(1)}</span>
          <span className="hud-label">ALT (m)</span>
        </div>
        <div className="hud-speed">
          <span className="hud-value">{velocity.groundspeed.toFixed(1)}</span>
          <span className="hud-label">GND SPD (m/s)</span>
        </div>
        <div className="hud-climb">
          <span className="hud-value">{velocity.climb >= 0 ? '+' : ''}{velocity.climb.toFixed(1)}</span>
          <span className="hud-label">V/S (m/s)</span>
        </div>
      </div>

      {/* Attitude */}
      <div className="hud-attitude">
        <div className="att-row">
          <span>ROLL</span><span className={attitude.roll > 30 ? 'warn' : ''}>{attitude.roll.toFixed(1)}°</span>
          <span>PITCH</span><span>{attitude.pitch.toFixed(1)}°</span>
          <span>HDG</span><span>{attitude.heading.toFixed(0)}°</span>
        </div>
      </div>

      {/* Battery */}
      <div className="battery-bar">
        <div className="battery-fill" style={{ width: `${battery.remaining_pct}%` }}>
          {battery.remaining_pct > 30 && `${battery.remaining_pct}%`}
        </div>
        {battery.remaining_pct <= 30 && (
          <span className={`battery-label ${batteryOk ? '' : 'critical'}`}>
            {battery.remaining_pct}% {battery.voltage.toFixed(1)}V
          </span>
        )}
      </div>

      {/* Position */}
      <div className="position-row">
        <code>{position.lat.toFixed(6)}, {position.lon.toFixed(6)}</code>
      </div>
    </div>
  )
}
