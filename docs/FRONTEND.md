# JARVIS — Frontend

React + TypeScript + Vite + Tailwind CSS + Three.js. Single-page app with a fullscreen particle orb and minimal HUD overlays. Communicates with the Python backend via WebSocket.

## Layout
```
┌────────────────────────────────────┐
│ [SystemStatus]      [VoiceSelector]│  ← fixed top
│                                    │
│         [ THREE.JS ORB ]           │  ← fullscreen canvas z:0
│                                    │
│ [TranscriptFeed]                   │  ← fixed bottom-left
│ [StatusBar]                        │
└────────────────────────────────────┘
```

## Design System
```css
:root {
  --bg:            #050508;
  --surface:       #0d0d14;
  --surface-raised:#12121c;
  --border:        #1a1a2e;
  --accent:        #4ca8e8;   /* idle */
  --accent-bright: #6ec4ff;   /* thinking */
  --accent-speak:  #5ab8f0;   /* speaking */
  --text:          #e8f4ff;
  --text-secondary:#6b8fa8;
  --text-muted:    #2a3d4f;
  --glow:          0 0 8px #4ca8e8aa;
  --glow-strong:   0 0 20px #4ca8e8cc, 0 0 40px #4ca8e844;
  --font:          'JetBrains Mono', monospace;
}
```
Rules: No `border-radius` > 4px. JetBrains Mono only. All colors via CSS variables. Tailwind for layout/spacing only. Overlay panels: `background: rgba(13,13,20,0.75)`, `backdrop-filter: blur(12px)`, `border: 1px solid var(--border)`.

## Orb States
| State | Particle color | UI accent |
|---|---|---|
| idle | #4ca8e8 | --accent |
| listening | #4ca8e8 | --accent + pulse ring |
| thinking | #6ec4ff | --accent-bright + spin |
| speaking | #5ab8f0 | --accent-speak + wave |

Only interact with `src/lib/orb.ts` via `orb.setState()`, `orb.setAnalyser()`, `orb.destroy()`. Never modify the orb engine itself.

## WebSocket Protocol (`ws://localhost:8765`)
```typescript
type WsMessage =
  | { type: 'state';      payload: OrbState }
  | { type: 'transcript'; payload: { role: 'user' | 'jarvis'; text: string } }
  | { type: 'system';     payload: { cpu: number; mem: number; uptime: string } }

type WsCommand =
  | { type: 'set_voice'; payload: { profile: string } }
  | { type: 'reset';     payload: null }
```

```yaml
api:
  ws_port: 8765
  http_port: 8766
  cors_origins: ["http://localhost:5173"]
```

## Components
- **OrbCanvas**: `<canvas>` 100vw×100vh, `position:fixed z:0`. Mounts via `useOrb`, passes `AnalyserNode` from `useAudioAnalyser`. Calls `orb.destroy()` on unmount.
- **StatusBar**: `fixed bottom-6 left-6 z:10`. State label + language indicator (DE/EN). 300ms fade on state change.
- **TranscriptFeed**: `fixed bottom-20 left-6 z:10`, max-width 420px. Last 6 exchanges. User: right-aligned `--accent` prefix `›`. JARVIS: left-aligned `--text` prefix `J.`. 150ms fade-in.
- **VoiceSelector**: `fixed top-6 right-6 z:10`. Fetches profiles via `GET /voices`. Sends `set_voice` on select.
- **SystemStatus**: `fixed top-6 left-6 z:10`. CPU%, MEM%, UPTIME updated every 5s. Shows `--` until first message.

## Hooks
```typescript
useOrb(canvasRef): RefObject<Orb | null>
useWebSocket(): { orbState, transcript, systemStats, send, connected }
useAudioAnalyser(): AnalyserNode | null
```

## Vite Dev Proxy
```typescript
server: {
  proxy: {
    '/voices': 'http://localhost:8766',
    '/ws': { target: 'ws://localhost:8765', ws: true },
  }
}
```

> **RPi**: Frontend runs on developer's PC only. RPi runs Python backend. Connect to `ws://<rpi-ip>:8765`.
