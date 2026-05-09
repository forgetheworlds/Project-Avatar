import type { AlertData } from '../hooks/useTelemetry'

interface Props {
  alerts: AlertData[]
}

const SEVERITY_ICONS: Record<string, string> = {
  info: 'ℹ',
  warning: '⚠',
  critical: '🚨',
}

export function AlertBanner({ alerts }: Props) {
  const criticalAlerts = alerts.filter(a => a.severity === 'critical')
  const latestAlerts = alerts.slice(-5).reverse()

  if (alerts.length === 0) return null

  return (
    <div className="alert-banner">
      {criticalAlerts.length > 0 && (
        <div className="alert-critical-flash">
          {criticalAlerts[criticalAlerts.length - 1].message}
        </div>
      )}
      <div className="alert-list">
        {latestAlerts.map((alert, i) => (
          <div key={i} className={`alert-item ${alert.severity}`}>
            <span className="alert-icon">{SEVERITY_ICONS[alert.severity] || '•'}</span>
            <span className="alert-msg">{alert.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
