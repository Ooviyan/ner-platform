import React from 'react'
import { hardReset } from '../recovery.js'

/**
 * Last line of defence. Without this, any render-time throw leaves the driver
 * staring at a blank white screen with nothing to act on — the worst possible
 * outcome for an app someone is relying on at the roadside.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[NER Driver] render failure', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div
        style={{
          minHeight: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          background: '#07211f',
          color: '#f2fbfa',
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        <div style={{ maxWidth: 420, width: '100%' }}>
          <div style={{ fontSize: 40, marginBottom: 10 }} aria-hidden>
            ⚠️
          </div>
          <h1 style={{ fontSize: 19, margin: '0 0 8px' }}>NER Driver could not start</h1>
          <p style={{ fontSize: 13.5, color: '#93b8b4', margin: '0 0 14px', lineHeight: 1.5 }}>
            The app hit an error while loading. Your saved reports and any active SOS are
            still stored on this device and will not be lost by restarting.
          </p>
          <pre
            style={{
              fontSize: 11,
              background: '#0f2e2c',
              border: '1px solid #1f524e',
              borderRadius: 10,
              padding: 10,
              overflowX: 'auto',
              color: '#fbbf24',
              margin: '0 0 14px',
            }}
          >
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <button
            onClick={() => hardReset()}
            style={{
              width: '100%',
              minHeight: 48,
              borderRadius: 12,
              border: 'none',
              background: '#2dd4bf',
              color: '#04201d',
              fontWeight: 700,
              fontSize: 15,
              cursor: 'pointer',
            }}
          >
            Clear cache and restart
          </button>
          <button
            onClick={() => window.location.reload()}
            style={{
              width: '100%',
              minHeight: 44,
              marginTop: 8,
              borderRadius: 12,
              border: '1px solid #1f524e',
              background: 'transparent',
              color: '#f2fbfa',
              fontWeight: 600,
              fontSize: 14,
              cursor: 'pointer',
            }}
          >
            Just reload
          </button>
        </div>
      </div>
    )
  }
}
