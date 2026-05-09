import type { PayloadData } from '../hooks/useTelemetry'
import { useMCPClient } from '../hooks/useMCPClient'

interface Props {
  payloads: PayloadData | null
}

export function PayloadStatus({ payloads }: Props) {
  const mcp = useMCPClient()

  if (!payloads || Object.keys(payloads).length === 0) {
    return (
      <div className="payload-status empty">
        <p>No payloads detected</p>
      </div>
    )
  }

  return (
    <div className="payload-status">
      <h3>PAYLOADS</h3>
      {Object.entries(payloads).map(([id, p]) => (
        <div key={id} className={`payload-card ${p.state?.toLowerCase() || 'unknown'}`}>
          <div className="payload-header">
            <span className="payload-id">{id}</span>
            <span className="payload-type">{p.type}</span>
            <span className={`payload-state ${p.state?.toLowerCase()}`}>{p.state}</span>
          </div>

          {p.type === 'splash' && (
            <div className="splash-details">
              <div className="splash-aim">
                <span className="detail-label">AIM</span>
                <span className="detail-value">
                  P:{p.pan_deg?.toFixed(0) ?? '--'}° T:{p.tilt_deg?.toFixed(0) ?? '--'}°
                </span>
              </div>
              <div className="splash-reservoir">
                <span className="detail-label">RESERVOIR</span>
                <div className="reservoir-bar">
                  <div
                    className="reservoir-fill"
                    style={{ width: `${((p.reservoir_ml ?? 0) / 15) * 100}%` }}
                  />
                </div>
                <span className="detail-value">{p.reservoir_ml?.toFixed(1) ?? '--'}ml</span>
              </div>
              <div className="splash-stats">
                <span>Shots: {p.fire_count ?? 0}</span>
                <span>Pump: {p.pump_active ? 'ON' : 'OFF'}</span>
              </div>
              <div className="splash-actions">
                <button
                  className="payload-btn fire"
                  onClick={() => mcp.payloadCommand(id, 'fire', { duration_ms: 500 })}
                  disabled={mcp.loading || (p.reservoir_ml ?? 0) <= 0}
                >
                  FIRE
                </button>
                <button
                  className="payload-btn"
                  onClick={() => mcp.payloadCommand(id, 'center')}
                  disabled={mcp.loading}
                >
                  CENTER
                </button>
              </div>
            </div>
          )}

          {p.type !== 'splash' && (
            <div className="payload-generic">
              <pre>{JSON.stringify(p, null, 1)}</pre>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
