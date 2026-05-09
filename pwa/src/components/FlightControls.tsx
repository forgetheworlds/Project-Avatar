import { useState, useCallback } from 'react'
import { Joystick } from 'react-joystick-component'
import type { IJoystickUpdateEvent } from 'react-joystick-component/build/lib/Joystick'
import { useMCPClient } from '../hooks/useMCPClient'

type DroneMode = 'GUIDED' | 'CIRCLE' | 'LOITER' | 'RTL' | 'LAND' | 'STABILIZE'

interface Props {
  armed: boolean
  currentMode: string
}

export function FlightControls({ armed, currentMode }: Props) {
  const mcp = useMCPClient()
  const [selectedMode, setSelectedMode] = useState<DroneMode>('GUIDED')
  const [altitudeTarget, setAltitudeTarget] = useState(5)
  const [estopConfirm, setEstopConfirm] = useState(false)

  const handleJoystickMove = useCallback((e: IJoystickUpdateEvent) => {
    // x: roll (right positive), y: pitch (forward negative)
    // For now, log — in future: send MAVLink MANUAL_CONTROL
    console.log('Joystick:', { x: e.x?.toFixed(2), y: e.y?.toFixed(2), direction: e.direction })
  }, [])

  const handleJoystickStop = useCallback(() => {
    console.log('Joystick: center')
  }, [])

  const handleModeSwitch = async (mode: DroneMode) => {
    setSelectedMode(mode)
    // Send mode via MCP — uses payload_command for mode switching if available
    // or direct mode switch via MAVLink
    await mcp.callTool('set_mode', { mode })
  }

  return (
    <div className="flight-controls">
      {/* Mode selector */}
      <div className="mode-selector">
        <h3>MODE</h3>
        <div className="mode-grid">
          {(['GUIDED', 'CIRCLE', 'LOITER', 'STABILIZE', 'RTL', 'LAND'] as DroneMode[]).map(mode => (
            <button
              key={mode}
              className={`mode-btn ${selectedMode === mode ? 'active' : ''} ${currentMode === mode ? 'current' : ''}`}
              onClick={() => handleModeSwitch(mode)}
              disabled={mcp.loading}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Joystick area */}
      <div className="joystick-area">
        <div className="joystick-left">
          <Joystick
            size={120}
            baseColor="rgba(255,255,255,0.05)"
            stickColor="rgba(0,255,136,0.6)"
            move={handleJoystickMove}
            stop={handleJoystickStop}
          />
          <span className="joystick-label">THR / YAW</span>
        </div>
        <div className="joystick-right">
          <Joystick
            size={120}
            baseColor="rgba(255,255,255,0.05)"
            stickColor="rgba(0,255,136,0.6)"
            move={handleJoystickMove}
            stop={handleJoystickStop}
          />
          <span className="joystick-label">ROLL / PITCH</span>
        </div>
      </div>

      {/* Action buttons */}
      <div className="action-bar">
        {!armed ? (
          <button className="action-btn arm" onClick={mcp.arm} disabled={mcp.loading}>
            ARM
          </button>
        ) : (
          <>
            <div className="alt-input">
              <label>ALT (m)</label>
              <input
                type="number"
                value={altitudeTarget}
                onChange={e => setAltitudeTarget(Number(e.target.value))}
                min={1} max={120}
              />
            </div>
            <button className="action-btn takeoff" onClick={() => mcp.takeoff(altitudeTarget)} disabled={mcp.loading}>
              TAKEOFF
            </button>
            <button className="action-btn land" onClick={mcp.land} disabled={mcp.loading}>
              LAND
            </button>
            <button className="action-btn rtb" onClick={mcp.rtb} disabled={mcp.loading}>
              RTL
            </button>
          </>
        )}
      </div>

      {/* Emergency Stop */}
      <div className="estop-section">
        {!estopConfirm ? (
          <button className="estop-btn" onClick={() => setEstopConfirm(true)}>
            ⚠ EMERGENCY STOP
          </button>
        ) : (
          <div className="estop-confirm">
            <span>CONFIRM DISARM?</span>
            <button className="estop-yes" onClick={() => { mcp.disarm(); setEstopConfirm(false) }}>
              YES — DISARM
            </button>
            <button className="estop-no" onClick={() => setEstopConfirm(false)}>
              CANCEL
            </button>
          </div>
        )}
      </div>

      {/* Last result */}
      {mcp.lastResult && (
        <div className={`mcp-result ${mcp.lastResult.status}`}>
          {mcp.lastResult.status}: {mcp.lastResult.message || JSON.stringify(mcp.lastResult).slice(0, 100)}
        </div>
      )}
    </div>
  )
}
