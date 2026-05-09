import { useState, useEffect, useRef, useCallback } from 'react'

export interface TelemetryData {
  position: { lat: number; lon: number }
  altitude_m: number
  attitude: { roll: number; pitch: number; yaw: number; heading: number }
  velocity: { groundspeed: number; climb: number }
  battery: { voltage: number; current: number; remaining_pct: number }
  state: { armed: boolean; mode: string; gps_fix: number; gps_sats: number }
  link: { heartbeat_age_s: number }
}

export interface PayloadData {
  [id: string]: {
    state: string
    type: string
    pan_deg?: number
    tilt_deg?: number
    pump_active?: boolean
    reservoir_ml?: number
    fire_count?: number
    deadzone_px?: number
  }
}

export interface AlertData {
  severity: 'info' | 'warning' | 'critical'
  message: string
}

interface TelemetryState {
  telemetry: TelemetryData | null
  payloads: PayloadData | null
  alerts: AlertData[]
  connected: boolean
  error: string | null
}

const WS_URL = `ws://${window.location.hostname}:8888/telemetry`

export function useTelemetry() {
  const [state, setState] = useState<TelemetryState>({
    telemetry: null,
    payloads: null,
    alerts: [],
    connected: false,
    error: null,
  })
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setState(s => ({ ...s, connected: true, error: null }))
        ws.send(JSON.stringify({
          type: 'subscribe',
          channels: ['telemetry', 'payloads', 'alerts'],
        }))
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          setState(s => {
            switch (msg.type) {
              case 'telemetry':
                return { ...s, telemetry: msg.data, error: null }
              case 'payloads':
                return { ...s, payloads: msg.data }
              case 'alerts':
                return { ...s, alerts: [...s.alerts.slice(-19), msg.data] }
              default:
                return s
            }
          })
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        setState(s => ({ ...s, connected: false }))
        wsRef.current = null
        reconnectTimer.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        setState(s => ({ ...s, error: 'WebSocket connection failed' }))
        ws.close()
      }
    } catch (e) {
      setState(s => ({ ...s, error: String(e) }))
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return state
}
