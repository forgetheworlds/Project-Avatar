import { useState, useCallback } from 'react'

const MCP_URL = '/mcp'  // proxied to MCP server

interface MCPResult {
  status: 'success' | 'error'
  message?: string
  [key: string]: unknown
}

export function useMCPClient() {
  const [lastResult, setLastResult] = useState<MCPResult | null>(null)
  const [loading, setLoading] = useState(false)

  const callTool = useCallback(async (tool: string, args: Record<string, unknown> = {}) => {
    setLoading(true)
    try {
      const res = await fetch(`${MCP_URL}/tools/${tool}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      })
      const data: MCPResult = await res.json()
      setLastResult(data)
      setLoading(false)
      return data
    } catch (e) {
      const err: MCPResult = { status: 'error', message: String(e) }
      setLastResult(err)
      setLoading(false)
      return err
    }
  }, [])

  // Convenience methods for common tools
  const arm = useCallback(() => callTool('arm'), [callTool])
  const disarm = useCallback(() => callTool('disarm'), [callTool])
  const takeoff = useCallback((alt: number) => callTool('takeoff', { altitude_meters: alt }), [callTool])
  const land = useCallback(() => callTool('land'), [callTool])
  const rtb = useCallback(() => callTool('rtb'), [callTool])
  const orbit = useCallback((lat: number, lon: number, radius: number, alt: number) =>
    callTool('orbit', { center_lat: lat, center_lon: lon, radius_m: radius, altitude_m: alt }),
    [callTool])
  const engageTarget = useCallback(() => callTool('engage_target'), [callTool])
  const protectMode = useCallback((lat: number, lon: number, radius: number) =>
    callTool('protect_mode', { center_lat: lat, center_lon: lon, radius_m: radius }),
    [callTool])
  const payloadCommand = useCallback((payloadId: string, action: string, params = {}) =>
    callTool('payload_command', { payload_id: payloadId, action, params }),
    [callTool])

  return {
    lastResult,
    loading,
    callTool,
    arm, disarm, takeoff, land, rtb,
    orbit, engageTarget, protectMode,
    payloadCommand,
  }
}
