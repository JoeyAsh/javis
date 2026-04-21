# JARVIS — Frontend

React + TypeScript + Vite + Tailwind CSS + Three.js. Single-page app with a fullscreen particle orb and floating HUD window system. Communicates with the Python backend via WebSocket.

---

## HUD Component Architecture

### File Tree

```
frontend/src/
  styles/tokens.css                         CSS design tokens (imported by index.css)
  index.css                                 Global styles + CSS variables
  App.tsx                                   Root — orb variant switch, WS, settings
  components/
    hud/
      hud.css                               Shared keyframes (winIn, etc.)
      Scene.tsx + Scene.css                 Fullscreen scene container
      Window.tsx + Window.css               Single draggable/resizable HUD window
      HudWindows.tsx                        Window registry + swap-drag orchestration
      WindowManager.tsx                     Window state machine + slot layout
      SnapOverlay.tsx                       Win11-style snap zone overlay
      SlotGrid.ts                           Slot geometry computations
      SwapOverlay.tsx                       Swap-drag target highlight overlay
      Orb.tsx + orb.css                     Hypermodern CSS orb (5 rings, RAF particles)
      OldOrb.tsx                            Classic Three.js orb wrapper
      primitives/
        HudPanel.tsx + HudPanel.css         Panel shell: corners + trace + bloom + header + body
        HudCornerBrackets.tsx + HudCornerBrackets.css   Angular L-bracket corner decorations
        HudLightTrace.tsx + HudLightTrace.css            Circumnavigating perimeter trace
        HudBloom.tsx + HudBloom.css         Radial bloom overlay (mix-blend-mode: screen)
        HudButton.tsx + HudButton.css       Styled action button with baked-in SFX
        HudIconButton.tsx + HudIconButton.css            Icon-only button with baked-in SFX
        HudDivider.tsx + HudDivider.css     Horizontal separator
        HudStatusBadge.tsx + HudStatusBadge.css          Pill-style status badge
        HudList.tsx + HudList.css           Keyed list with stable item transitions
        HudSideRails.tsx + HudSideRails.css Thin vertical edge rails on panel body
        HudViewportCorners.tsx + HudViewportCorners.css  Full-viewport corner brackets (NEW — structural-fix agent)
        Reactor.tsx + Reactor.css           Central reactor animation element (NEW — structural-fix agent)
        index.ts                            Barrel re-export
    HudTopBar.tsx + HudTopBar.css           Fixed top bar (weather, time, controls)
    HudInfoBar.tsx                          Deprecated — content inlined into HudTopBar
    SettingsOverlay.tsx                     Full-screen settings panel (z: --z-modal)
    OrbDevMenu.tsx                          Dev override for orb state + STOP button
    PushToTalkButton.tsx                    PTT button (may be subsumed by Dock.tsx)
    Dock.tsx + Dock.css                     Bottom dock for minimized panels (NEW — structural-fix agent)
    HudHint.tsx + HudHint.css               Contextual help tooltip (NEW — structural-fix agent)
    AudioMuteToggle.tsx                     SFX mute button — persists to localStorage
    panels/
      Agenda/                               AgendaPanel modular folder
      Mail/                                 MailPanel modular folder
      Transcript/                           TranscriptPanel modular folder
      System/                               SystemPanel modular folder
      Notifications/                        NotificationsPanel modular folder
      NowPlaying/                           NowPlayingPanel modular folder
      Log/                                  LogPanel modular folder
      GitLab/                               GitLabPanel modular folder
      Dev/                                  DevPanel modular folder
      Lights/                               LightsPanel modular folder (dormant — Sub-14)
        LightsPanel.tsx
        ZoneTile.tsx
        LightsPanel.css
        index.ts
        LightsPanel.test.tsx
      LightsPanel.tsx                       (flat file — superseded by Lights/ folder, retained for backward compat)
      SelfFixPanel.tsx                      (unchanged per epic #40 constraint)
      index.ts                              Barrel re-export for all panels
  lib/
    audioEngine.ts                          Web Audio API engine class
    orb.ts                                  Three.js particle orb engine (never modify)
  hooks/
    useSettings.ts                          App settings: panelOpacity, orbVariant, pushToTalk, heartbeat
    useAudioEngine.ts                       SFX state machine + StrictMode-safe engineRef
    useLocation.ts                          Geolocation for TopBar weather coords
    useTauriWindowSfx.ts                    Tauri window-event SFX bridge
    useOrb.ts                               Returns orbRef + glRef for OldOrb
    useDraggable.ts                         Pointer-event drag hook
    useResizable.ts                         Pointer-event resize hook
    useWebSocket.ts                         WS connection + typed message dispatch
    useNotifications.ts                     Notification queue state
    useTranscripts.ts                       Transcript history state
    useSystemMetrics.ts                     CPU/RAM/GPU polling
    useGitHubState.ts                       GitHub PR/issue/CI state
    useGitlabState.ts                       GitLab MR/issue/pipeline state
    useLogStream.ts                         Log line stream
    useMicStream.ts                         Raw PCM mic stream to WS
    useConversationMode.ts                  Follow-up window state + countdown
    useTurnTimings.ts                       Per-turn latency waterfall
    useSwapDrag.ts                          Swap-drag state machine
    useAudioAnalyser.ts                     AudioAnalyser node for orb waveform
    index.ts                                Barrel re-export
  hud/
    SfxContext.tsx                          SfxProvider + useSfx() context hook
```

---

### Panel Shell Composition

Every HUD panel is assembled from `HudPanel` which internally composes:

```
<HudPanel icon="◉" title="Panel Title" badge="STATUS" actions={[...]} hideDots={false}>
  ├── <HudCornerBrackets />       Angular L-brackets at each corner
  ├── <HudLightTrace />           Perimeter-circumnavigating light point
  ├── <HudBloom />                Radial bloom overlay (mix-blend-mode: screen)
  ├── <HudSideRails />            Thin vertical edge rails on body
  ├── .hud-panel__header          Header row
  │   ├── .ix                     Icon glyph (e.g. "◉")
  │   ├── .tt                     Title text
  │   ├── .dots                   Three traffic-light dots (hidden when hideDots=true)
  │   ├── .badge                  Status badge
  │   └── .hud-panel__header-actions   Slot for custom action buttons
  └── .hud-panel__body            Scrollable content area
      └── {children}
```

Props contract:
```typescript
interface HudPanelProps {
  icon?: string;           // glyph shown in header left
  title: string;
  badge?: string;          // status label in header right
  actions?: ReactNode;     // extra header-right content
  hideDots?: boolean;      // suppress traffic-light dots
  focused?: boolean;       // activates shimmer underline
  children: ReactNode;
}
```

---

### Orb Swap Pattern

`App.tsx` conditionally renders the classic or hypermodern orb based on `settings.orbVariant` from `useSettings()`:

```tsx
// settings.orbVariant: 'classic' | 'hypermodern'  (localStorage: 'jarvis.orbVariant')
{settings.orbVariant === 'hypermodern' ? (
  <Orb state={effectiveOrbState} />
) : (
  <OrbErrorBoundary>
    <OrbCanvas orbState={effectiveOrbState} analyser={analyser} mockMode={orbOverride} followUp={followUp} />
  </OrbErrorBoundary>
)}
```

The Settings overlay exposes a Display section with an `orbVariant` dropdown. Default is `'classic'`.

---

### HudButton / HudIconButton — Baked-in SFX

Both button primitives fire sound effects automatically without caller involvement:

- **Click**: plays `click_1` via `useSfx().playOneShot('click')`
- **Hover**: plays `hover_1` via `useSfx().playOneShot('hover')`, debounced 200 ms per element instance to prevent rapid-fire on fast cursor movement

Callers only need to provide `onClick` and the button label/icon. No SFX wiring required at the call site.

---

### useSfx() Context Pattern

All components that need to trigger SFX use the context hook:

```typescript
// In any component under <SfxProvider> (mounted in App.tsx):
import { useSfx } from '../hud/SfxContext';

function MyComponent() {
  const { playOneShot } = useSfx();
  return (
    <button onClick={() => { playOneShot('confirm'); doSomething(); }}>
      Confirm
    </button>
  );
}
```

`SfxProvider` is mounted at the App root and wraps `<WindowManagerProvider>`. It holds the `AudioEngine` ref and exposes:
- `playOneShot(event: SfxEvent): void` — plays a one-shot sound
- `startLoop(event: SfxEvent): void` — starts a looping sound
- `stopLoop(event: SfxEvent): void` — stops a loop
- `muted: boolean` — current mute state

---

### Asset Pipeline

Sound files are NOT committed to the frontend `public/` directory. They are copied at dev/build time:

```json
// frontend/package.json
{
  "scripts": {
    "predev": "node scripts/copy-sounds.mjs",
    "prebuild": "node scripts/copy-sounds.mjs"
  }
}
```

`scripts/copy-sounds.mjs` copies `assets/sounds/**/*.mp3` → `frontend/public/sounds/`. The `frontend/public/sounds/` directory is gitignored. If sounds are missing, run `npm run predev` manually.

---

### WindowManager

The `WindowManagerProvider` / `useWindowManager()` system owns all window layout state:

- **Slot grid** (`SlotGrid.ts`): Viewport is divided into named slots (`SlotId`). Each panel has a `homeSlotId` and defaults to being docked in that slot (`maximized: false`).
- **Docked state**: Panel geometry is derived from the slot rect. No explicit position/size stored.
- **Floating state** (`maximized: true`): Panel uses `floatingRect` (x, y, w, h). Supports drag (`useDraggable`), resize (`useResizable`), and Win11-style snap (`SnapOverlay`).
- **Swap-drag**: Header drag with swap intent (separate from maximize-drag) is orchestrated at the `HudWindows` level via `handleSwapStart/Move/Commit/Cancel`.
- **Persistence**: Window layout persisted to `localStorage['jarvis-hud-windows-v1']` with 200 ms debounce.

**Chrome ownership**: After the Legacy-Kill-Sweep, all visual chrome (border, background, box-shadow, corner decorations, header) is owned entirely by the `HudPanel` primitive. The `.window` CSS class in `index.css` is **purely structural** — it only handles:
- `position: absolute` / `position: fixed`
- `z-index` (from window state)
- `display: flex; flex-direction: column`
- The `winIn` settle animation on mount

No color, border, background, or shadow properties belong on `.window`. These live in `HudPanel`.

---

## Design System

See `docs/DESIGN.md` for the full token reference, radius cap rules, and brand signature documentation.

Quick reference:
```css
:root {
  --bg:            #050508;
  --surface:       rgba(13,13,20,0.75);
  --surface-raised:rgba(22,22,34,0.85);
  --border:        rgba(64,112,160,0.25);
  --accent:        #4ca8e8;
  --accent-bright: #7ec8ff;
  --accent-speak:  #a8e0ff;
  --text:          #e8f4ff;
  --text-secondary:#8ba9c8;
  --text-muted:    #4a6a88;
  --glow:          0 0 12px rgba(76,168,232,0.18);
  --glow-strong:   0 0 24px rgba(76,168,232,0.35);
  --font:          'JetBrains Mono', ui-monospace, monospace;
  --r-0: 0px;  --r-1: 2px;  --r-2: 4px;  /* hard cap: never exceed --r-2 */
}
```

Rules: No `border-radius` > 4 px. JetBrains Mono only. All colors via CSS variables. Tailwind for layout/spacing only. Overlay panels: `background: var(--surface)`, `backdrop-filter: var(--panel-blur)`, `border: 1px solid var(--border)`.

---

## Orb States

| State | Particle color | UI accent |
|---|---|---|
| `idle` | `--accent` | `--accent` |
| `listening` | `--accent` | `--accent` + pulse ring |
| `thinking` | `--accent-bright` | `--accent-bright` + spin |
| `speaking` | `--accent-speak` | `--accent-speak` + wave |
| `working` | `--warning` (amber) | `.is-working` class on root |
| `follow_up` | `--accent` | muted pulse + countdown ring |

Only interact with `lib/orb.ts` via `orb.setState()`, `orb.setAnalyser()`, `orb.destroy()`. Never modify the orb engine itself.

---

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

---

## Hooks

```typescript
useOrb(canvasRef): { orbRef: RefObject<Orb | null>; glRef: RefObject<WebGLRenderingContext | null> }
useWebSocket(): { orbState, audioQueue, consumeAudio, wsRef, sendCancelTurn, ... }
useAudioAnalyser(): { analyser, isSpeaking, enqueue, stopAll }
useSettings(): { settings, setPanelOpacity, setAutoSpeakClaude, setPushToTalk, setMicDeviceId }
useConversationMode(): { active, secondsRemaining }
useDraggable(ref, opts): { isDragging, position }
useResizable(ref, opts): { isResizing, size }
```

---

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
