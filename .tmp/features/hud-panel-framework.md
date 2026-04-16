# Feature Spec: HUD Panel Framework

## Summary
Build the frontend panel system that enables the Iron Man-style HUD interface. This spec covers the panel grid layout, shared PanelBase component, responsive breakpoints, panel lifecycle management, and the opacity fade behavior when JARVIS speaks. Individual panel implementations (Spotify, Govee, Dev, etc.) are covered in their own specs.

## Goals
- Create a cinematic, symmetrical panel layout around the central orb
- Implement shared PanelBase component with consistent styling
- Support responsive layouts: desktop (3-column), tablet (2-column), mobile (drawer)
- Implement panel opacity fade during orb speaking state
- Establish hooks and patterns for panel-specific data subscriptions

## Non-Goals
- Drag-and-drop panel rearrangement (deferred to Phase B)
- Panel minimize/maximize (deferred)
- Panel-specific implementations (separate specs)
- Custom panel themes beyond the JARVIS design system

---

## Design System Extensions

### New CSS Variables

Add to `frontend/src/index.css`:

```css
:root {
  /* Existing variables preserved */
  --bg: #050508;
  --accent: #0ea5e9;

  /* HUD Panel System */
  --panel-bg: rgba(13, 13, 20, 0.75);
  --panel-border: rgba(26, 26, 46, 0.8);
  --panel-glow: 0 0 20px rgba(76, 168, 232, 0.15);
  --panel-header-color: #2a3d4f;
  --panel-content-color: #e8f4ff;

  /* Semantic colors */
  --danger: #e84c4c;
  --warning: #e8a84c;
  --success: #4ce88a;
  --info: #4ca8e8;

  /* Panel dimensions */
  --panel-min-width: 240px;
  --panel-max-width: 360px;
  --panel-gap: 16px;
  --panel-padding: 16px;

  /* Animation */
  --panel-fade-duration: 300ms;
  --panel-opacity-idle: 1;
  --panel-opacity-speaking: 0.3;
}
```

### JetBrains Mono Import

Ensure JetBrains Mono is loaded. Add to `index.html` or `index.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --font: 'JetBrains Mono', monospace;
}
```

---

## Layout Architecture

### Desktop Layout (viewport >= 1280px)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌──────────────┐                                        ┌──────────────┐  │
│  │ SystemPanel  │                                        │NotifPanel    │  │
│  └──────────────┘                                        └──────────────┘  │
│                                                                             │
│  ┌──────────────┐                                        ┌──────────────┐  │
│  │ AgendaPanel  │              [ ORB ]                   │ DevPanel     │  │
│  └──────────────┘              center                    │   (tall)     │  │
│  ┌──────────────┐              40% reserved              │              │  │
│  │ MailPanel    │                                        └──────────────┘  │
│  └──────────────┘                                                          │
│                                                                             │
│  ┌──────────────┐                                        ┌──────────────┐  │
│  │ LightsPanel  │                                        │NowPlayingPanel│ │
│  └──────────────┘                                        └──────────────┘  │
│  ┌──────────────┐                                        ┌──────────────┐  │
│  │TranscriptPanel│            [ status text ]            │SelfFixPanel  │  │
│  └──────────────┘                                        └──────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### CSS Grid Structure

```css
.hud-layout {
  display: grid;
  grid-template-columns: var(--panel-max-width) 1fr var(--panel-max-width);
  grid-template-rows: auto 1fr auto;
  grid-template-areas:
    "left-top    center-top    right-top"
    "left-middle center-middle right-middle"
    "left-bottom center-bottom right-bottom";
  gap: var(--panel-gap);
  padding: var(--panel-gap);
  position: fixed;
  inset: 0;
  z-index: 10;
  pointer-events: none; /* Allow click-through to orb */
}

.hud-layout > * {
  pointer-events: auto; /* Re-enable for panels */
}

/* Center column reserved for orb - no panels */
.hud-center {
  grid-area: center-middle;
  pointer-events: none;
}
```

### Tablet Layout (768px <= viewport < 1280px)

```css
@media (max-width: 1279px) and (min-width: 768px) {
  .hud-layout {
    grid-template-columns: var(--panel-max-width) 1fr var(--panel-max-width);
    grid-template-rows: auto 1fr auto;
  }

  /* Panels stack vertically in left/right columns */
  .hud-left { grid-area: 1 / 1 / 4 / 2; }
  .hud-right { grid-area: 1 / 3 / 4 / 4; }
}
```

### Mobile Layout (viewport < 768px)

```css
@media (max-width: 767px) {
  .hud-layout {
    display: none; /* Panels hidden by default */
  }

  .hud-layout.drawer-open {
    display: flex;
    flex-direction: column;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    max-height: 60vh;
    overflow-y: auto;
    background: var(--panel-bg);
    backdrop-filter: blur(12px);
    border-top: 1px solid var(--panel-border);
    padding: var(--panel-gap);
    gap: var(--panel-gap);
    z-index: 20;
  }
}
```

---

## Component Architecture

### HudLayout.tsx

```typescript
// frontend/src/components/HudLayout.tsx

import { ReactNode, useEffect, useState } from 'react';
import { OrbState } from '../types';

interface HudLayoutProps {
  orbState: OrbState;
  children: ReactNode;
}

export function HudLayout({ orbState, children }: HudLayoutProps) {
  const [opacity, setOpacity] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Fade panels when orb is speaking
  useEffect(() => {
    if (orbState === 'speaking') {
      setOpacity(0.3);
    } else {
      setOpacity(1);
    }
  }, [orbState]);

  return (
    <div
      className={`hud-layout ${drawerOpen ? 'drawer-open' : ''}`}
      style={{
        opacity,
        transition: `opacity var(--panel-fade-duration) ease-in-out`,
      }}
    >
      {children}
    </div>
  );
}

export default HudLayout;
```

### PanelBase.tsx

```typescript
// frontend/src/components/panels/PanelBase.tsx

import { ReactNode } from 'react';

interface PanelBaseProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  loading?: boolean;
  error?: string | null;
  offline?: boolean;
}

export function PanelBase({
  title,
  icon,
  children,
  className = '',
  loading = false,
  error = null,
  offline = false,
}: PanelBaseProps) {
  return (
    <div
      className={`panel-base ${className}`}
      style={{
        background: 'var(--panel-bg)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid var(--panel-border)',
        borderRadius: '4px',
        boxShadow: 'var(--panel-glow)',
        padding: 'var(--panel-padding)',
        fontFamily: 'var(--font)',
        minWidth: 'var(--panel-min-width)',
        maxWidth: 'var(--panel-max-width)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px',
        }}
      >
        {icon && (
          <span style={{ color: 'var(--accent)', opacity: 0.8 }}>
            {icon}
          </span>
        )}
        <span
          style={{
            fontSize: '10px',
            fontWeight: 600,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            color: 'var(--panel-header-color)',
          }}
        >
          {title}
        </span>
        {offline && (
          <span
            style={{
              fontSize: '9px',
              color: 'var(--warning)',
              marginLeft: 'auto',
            }}
          >
            OFFLINE
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{ color: 'var(--panel-content-color)' }}>
        {loading ? (
          <PanelSkeleton />
        ) : error ? (
          <PanelError message={error} />
        ) : (
          children
        )}
      </div>
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div style={{ opacity: 0.3 }}>
      <div
        style={{
          height: '14px',
          background: 'var(--panel-border)',
          borderRadius: '2px',
          marginBottom: '8px',
          width: '80%',
        }}
      />
      <div
        style={{
          height: '14px',
          background: 'var(--panel-border)',
          borderRadius: '2px',
          width: '60%',
        }}
      />
    </div>
  );
}

function PanelError({ message }: { message: string }) {
  return (
    <div style={{ color: 'var(--danger)', fontSize: '12px' }}>
      {message}
    </div>
  );
}

export default PanelBase;
```

### Panel Position Components

```typescript
// frontend/src/components/panels/PanelPositions.tsx

import { ReactNode } from 'react';

interface PositionProps {
  children: ReactNode;
}

export function LeftTopPanel({ children }: PositionProps) {
  return (
    <div style={{ gridArea: 'left-top', alignSelf: 'start' }}>
      {children}
    </div>
  );
}

export function LeftMiddlePanel({ children }: PositionProps) {
  return (
    <div
      style={{
        gridArea: 'left-middle',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--panel-gap)',
      }}
    >
      {children}
    </div>
  );
}

export function LeftBottomPanel({ children }: PositionProps) {
  return (
    <div
      style={{
        gridArea: 'left-bottom',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--panel-gap)',
        alignSelf: 'end',
      }}
    >
      {children}
    </div>
  );
}

export function RightTopPanel({ children }: PositionProps) {
  return (
    <div style={{ gridArea: 'right-top', alignSelf: 'start' }}>
      {children}
    </div>
  );
}

export function RightMiddlePanel({ children }: PositionProps) {
  return (
    <div
      style={{
        gridArea: 'right-middle',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--panel-gap)',
      }}
    >
      {children}
    </div>
  );
}

export function RightBottomPanel({ children }: PositionProps) {
  return (
    <div
      style={{
        gridArea: 'right-bottom',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--panel-gap)',
        alignSelf: 'end',
      }}
    >
      {children}
    </div>
  );
}
```

---

## Panel Data Hook Pattern

Each panel has a dedicated hook that subscribes to relevant WS message types.

### usePanelData Hook Template

```typescript
// frontend/src/hooks/usePanelData.ts (example pattern)

import { useState, useEffect, useCallback } from 'react';

interface UsePanelDataOptions<T> {
  wsMessageType: string;
  initialState: T;
  transform?: (payload: unknown) => T;
}

export function usePanelData<T>({
  wsMessageType,
  initialState,
  transform,
}: UsePanelDataOptions<T>) {
  const [data, setData] = useState<T>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === wsMessageType) {
          const transformed = transform
            ? transform(msg.payload)
            : (msg.payload as T);
          setData(transformed);
          setLoading(false);
          setError(null);
          setOffline(false);
        }
      } catch (e) {
        // Ignore parse errors for binary messages
      }
    },
    [wsMessageType, transform]
  );

  // Hook into existing WebSocket from useWebSocket
  // Implementation depends on how WS is exposed globally

  return { data, loading, error, offline };
}
```

### WebSocket Message Type Extensions

Update `frontend/src/types.ts`:

```typescript
export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

// === Incoming messages (FROM backend) ===

export interface SpotifyState {
  playing: boolean;
  track: string;
  artist: string;
  album: string;
  album_art_url: string;
  progress_ms: number;
  duration_ms: number;
  device: string;
}

export interface GoveeDevice {
  id: string;
  name: string;
  on: boolean;
  brightness: number;
  color: string;
}

export interface GoveeState {
  devices: GoveeDevice[];
  active_scene: string | null;
}

export interface AgendaEvent {
  id: string;
  title: string;
  start: string; // ISO8601
  end: string;
  calendar: string;
  location?: string;
}

export interface MailMessage {
  id: string;
  from: string;
  subject: string;
  snippet: string;
  date: string; // ISO8601
  is_vip: boolean;
}

export interface RepoStatus {
  path: string;
  branch: string;
  dirty: boolean;
  ahead: number;
  behind: number;
}

export interface DockerContainer {
  id: string;
  name: string;
  status: string;
  cpu: number;
  mem: number;
}

export interface CIBuild {
  repo: string;
  workflow: string;
  status: 'success' | 'failure' | 'pending' | 'running';
  url: string;
}

export interface DevToolkitState {
  github: {
    notifications: number;
    prs_to_review: number;
  };
  repos: RepoStatus[];
  docker: DockerContainer[];
  ci: CIBuild[];
}

export interface Notification {
  id: string;
  message: string;
  severity: 'info' | 'warning' | 'urgent';
  spoken: boolean;
  timestamp: string; // ISO8601
}

export interface SystemMetrics {
  cpu: number;
  mem: number;
  uptime: string;
  gpu_util?: number;
  gpu_temp?: number;
  cpu_temp?: number;
  network_up: number;
  network_down: number;
}

// Union type for all incoming WS messages
export type WsIncoming =
  | { type: 'audio'; data: string; text: string }
  | { type: 'status'; state: OrbState }
  | { type: 'text'; text: string }
  | { type: 'system'; payload: SystemMetrics }
  | { type: 'transcript'; payload: { role: 'user' | 'jarvis'; text: string } }
  | { type: 'spotify_state'; payload: SpotifyState }
  | { type: 'govee_state'; payload: GoveeState }
  | { type: 'agenda'; payload: { events: AgendaEvent[] } }
  | { type: 'mail'; payload: { unread_count: number; messages: MailMessage[] } }
  | { type: 'dev_toolkit'; payload: DevToolkitState }
  | { type: 'notification'; payload: Notification }
  | { type: 'self_fix_started'; payload: { trigger: string; complaint: string; timestamp: string } }
  | { type: 'self_fix_progress'; payload: { stage: string; detail: string; files_touched: string[] } }
  | { type: 'self_fix_done'; payload: { success: boolean; commit_sha?: string; branch?: string; diff_summary?: string; reason?: string } };

// === Outgoing messages (TO backend) ===

export type WsOutgoing =
  | { type: 'transcript'; text: string; isFinal: boolean }
  | { type: 'reset' }
  | { type: 'spotify_cmd'; payload: { action: 'play' | 'pause' | 'next' | 'prev' | 'volume'; value?: number } }
  | { type: 'govee_cmd'; payload: { device_id: string; action: 'on' | 'off' | 'brightness' | 'color' | 'scene'; value?: unknown } }
  | { type: 'dismiss_notification'; payload: { id: string } };
```

---

## App.tsx Integration

```typescript
// frontend/src/App.tsx (updated)

import { useEffect, useState } from 'react';
import { OrbCanvas } from './components/OrbCanvas';
import { OrbErrorBoundary } from './components/OrbErrorBoundary';
import { HudLayout } from './components/HudLayout';
import {
  LeftTopPanel,
  LeftMiddlePanel,
  LeftBottomPanel,
  RightTopPanel,
  RightMiddlePanel,
  RightBottomPanel,
} from './components/panels/PanelPositions';
// Individual panels imported as they're implemented
import { SystemPanel } from './components/panels/SystemPanel';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioAnalyser } from './hooks/useAudioAnalyser';
import { useMicStream } from './hooks/useMicStream';

export function App() {
  const [muted, setMuted] = useState(false);
  const { orbState, setOrbState, audioQueue, consumeAudio, wsRef } = useWebSocket();
  const { analyser, isSpeaking, enqueue } = useAudioAnalyser();

  useMicStream({ wsRef, paused: muted || isSpeaking });

  useEffect(() => {
    if (audioQueue.length > 0) {
      enqueue(audioQueue[0]);
      consumeAudio();
    }
  }, [audioQueue, enqueue, consumeAudio]);

  useEffect(() => {
    if (!isSpeaking && orbState === 'speaking') {
      setOrbState('idle');
    }
  }, [isSpeaking, orbState, setOrbState]);

  const statusLabel =
    orbState === 'listening'
      ? 'listening...'
      : orbState === 'thinking'
        ? 'thinking...'
        : orbState === 'speaking'
          ? 'speaking...'
          : '';

  return (
    <div className="fixed inset-0 w-screen h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Orb canvas - z-index 0 */}
      <OrbErrorBoundary>
        <OrbCanvas orbState={orbState} analyser={analyser} />
      </OrbErrorBoundary>

      {/* HUD Panel Layer - z-index 10 */}
      <HudLayout orbState={orbState}>
        <LeftTopPanel>
          <SystemPanel />
        </LeftTopPanel>
        <LeftMiddlePanel>
          {/* AgendaPanel, MailPanel - when implemented */}
        </LeftMiddlePanel>
        <LeftBottomPanel>
          {/* LightsPanel, TranscriptPanel - when implemented */}
        </LeftBottomPanel>
        <RightTopPanel>
          {/* NotificationsPanel - when implemented */}
        </RightTopPanel>
        <RightMiddlePanel>
          {/* DevPanel - when implemented */}
        </RightMiddlePanel>
        <RightBottomPanel>
          {/* NowPlayingPanel, SelfFixPanel - when implemented */}
        </RightBottomPanel>
      </HudLayout>

      {/* Mute button - z-index 20 */}
      <button
        onClick={() => setMuted((m) => !m)}
        aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
        style={{
          position: 'fixed',
          top: 20,
          right: 20,
          width: 36,
          height: 36,
          zIndex: 20,
          /* ... existing styles ... */
        }}
      >
        {/* ... existing icon ... */}
      </button>

      {/* Status text - z-index 10 */}
      <div
        style={{
          position: 'fixed',
          bottom: 40,
          left: 0,
          right: 0,
          zIndex: 10,
          /* ... existing styles ... */
        }}
      >
        {/* ... existing content ... */}
      </div>
    </div>
  );
}

export default App;
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | HudLayout renders with CSS grid structure | Visual inspection |
| 2 | Panels fade to 30% opacity when orbState = 'speaking' | Visual inspection |
| 3 | Panels restore to 100% opacity after 300ms when orbState != 'speaking' | Visual inspection |
| 4 | PanelBase displays title with correct styling | Visual inspection |
| 5 | PanelBase shows loading skeleton when loading=true | Storybook/manual test |
| 6 | PanelBase shows error message when error is set | Storybook/manual test |
| 7 | PanelBase shows OFFLINE badge when offline=true | Storybook/manual test |
| 8 | Desktop layout shows 3-column grid at 1920x1080 | Visual inspection |
| 9 | Tablet layout shows 2-column at 1024x768 | Visual inspection |
| 10 | Mobile layout hides panels by default at 375px | Visual inspection |
| 11 | JetBrains Mono font loads and applies to all panel text | Visual inspection |
| 12 | All CSS variables are defined in index.css | Code review |
| 13 | Panel border-radius never exceeds 4px | Code review |
| 14 | No hardcoded colors in panel components | Code review |
| 15 | WsIncoming type includes all new message types | TypeScript compile check |

---

## Files Created

| File | Purpose |
|------|---------|
| `frontend/src/components/HudLayout.tsx` | Grid orchestrator with opacity fade |
| `frontend/src/components/panels/PanelBase.tsx` | Shared panel wrapper |
| `frontend/src/components/panels/PanelPositions.tsx` | Grid area components |
| `frontend/src/components/panels/index.ts` | Panel exports |

## Files Modified

| File | Change |
|------|--------|
| `frontend/src/index.css` | Add HUD CSS variables, JetBrains Mono import |
| `frontend/src/types.ts` | Add all new WS message type definitions |
| `frontend/src/App.tsx` | Integrate HudLayout, panel positions |

---

## Implementation Plan

### Batch 1 — Foundation
1. `design` → Update `frontend/src/index.css` with HUD CSS variables
2. `design` → Create `frontend/src/components/HudLayout.tsx`
3. `design` → Create `frontend/src/components/panels/PanelBase.tsx`
4. `design` → Create `frontend/src/components/panels/PanelPositions.tsx`
5. `test` → Create tests for HudLayout opacity transitions
6. `review` → Review batch 1

### Batch 2 — Types and Integration
7. `design` → Update `frontend/src/types.ts` with all new WS message types
8. `design` → Update `frontend/src/App.tsx` to integrate HudLayout
9. `design` → Create `frontend/src/components/panels/SystemPanel.tsx` (basic, uses existing system metrics)
10. `test` → Create tests for SystemPanel
11. `review` → Review batch 2

### Batch 3 — Responsive
12. `design` → Add tablet breakpoint styles to HudLayout
13. `design` → Add mobile drawer implementation
14. `test` → Responsive layout tests
15. `review` → Final review

---

## Dependencies

### NPM Packages
No new packages required. Framework uses:
- React 18 (existing)
- TypeScript strict (existing)
- Tailwind CSS (existing, for layout utilities only)

### External
- JetBrains Mono font (Google Fonts CDN)

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision implements drag-and-drop panel layout and multi-monitor support per user decisions.

### Layout Library — CHANGED
**Switch to `react-grid-layout`** for drag-and-drop panel arrangement.

#### NPM Dependencies (Updated)
```
react-grid-layout>=1.4.0
@types/react-grid-layout  # devDependency
```

#### HudLayout.tsx — Updated Implementation
```typescript
import { Responsive, WidthProvider, Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

interface HudLayoutProps {
  orbState: OrbState;
  children: ReactNode;
}

const DEFAULT_LAYOUT: Layout[] = [
  { i: 'system', x: 0, y: 0, w: 1, h: 2 },
  { i: 'agenda', x: 0, y: 2, w: 1, h: 3 },
  { i: 'mail', x: 0, y: 5, w: 1, h: 2 },
  { i: 'lights', x: 0, y: 7, w: 1, h: 2 },
  { i: 'transcript', x: 0, y: 9, w: 1, h: 2 },
  { i: 'notifications', x: 3, y: 0, w: 1, h: 2 },
  { i: 'dev', x: 3, y: 2, w: 1, h: 4 },
  { i: 'nowplaying', x: 3, y: 6, w: 1, h: 3 },
  { i: 'selffix', x: 3, y: 9, w: 1, h: 2 },
];

export function HudLayout({ orbState, children }: HudLayoutProps) {
  const [layouts, setLayouts] = usePersistedLayout();
  const [opacity, setOpacity] = useState(1);

  // Fade panels when orb is speaking
  useEffect(() => {
    setOpacity(orbState === 'speaking' ? 0.3 : 1);
  }, [orbState]);

  const handleLayoutChange = (layout: Layout[], allLayouts: Layouts) => {
    setLayouts(allLayouts);
    persistLayout(allLayouts);
  };

  return (
    <div style={{ opacity, transition: 'opacity var(--panel-fade-duration) ease-in-out' }}>
      <ResponsiveGridLayout
        className="hud-layout"
        layouts={layouts}
        breakpoints={{ lg: 1280, md: 768, sm: 480 }}
        cols={{ lg: 4, md: 2, sm: 1 }}
        rowHeight={80}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".panel-header"
        margin={[16, 16]}
        containerPadding={[16, 16]}
      >
        {children}
      </ResponsiveGridLayout>
    </div>
  );
}
```

### Multi-Monitor Support — ADDED
Panels can be assigned to specific monitors; layout persists per monitor.

#### Per-Monitor Layout Persistence Schema
```typescript
interface MonitorLayout {
  monitorId: string;  // e.g., "1920x1080-0" or screen identifier hash
  layouts: Layouts;   // react-grid-layout Layouts object
}

interface PersistedLayouts {
  monitors: MonitorLayout[];
  activeMonitor: string;
}

function getMonitorId(): string {
  const { width, height, availLeft } = window.screen;
  return `${width}x${height}-${availLeft}`;
}

function usePersistedLayout(): [Layouts, (layouts: Layouts) => void] {
  const monitorId = getMonitorId();
  const storageKey = `jarvis-hud-layout-${monitorId}`;
  
  const [layouts, setLayouts] = useState<Layouts>(() => {
    const stored = localStorage.getItem(storageKey);
    return stored ? JSON.parse(stored) : { lg: DEFAULT_LAYOUT };
  });

  const persistLayout = useCallback((newLayouts: Layouts) => {
    localStorage.setItem(storageKey, JSON.stringify(newLayouts));
  }, [storageKey]);

  return [layouts, persistLayout];
}
```

#### Config
```yaml
hud:
  multi_monitor: true
  layout_persistence: "local_storage"  # or "server" for future sync
```

### Non-Goals — Updated
Remove from Non-Goals:
- ~~Drag-and-drop panel rearrangement (deferred to Phase B)~~ — NOW IN SCOPE

### Files Modified (Updated)
| File | Change |
|------|--------|
| `package.json` | Add react-grid-layout dependency |
| `frontend/src/components/HudLayout.tsx` | Use ResponsiveGridLayout |

---

**Status:** Planned — awaiting implementation authorization

---

## OpenClaw Leverage (Revision 3 — 2026-04-16)

### Integration Assessment
**OpenClaw provides NO coverage for HUD Panel Framework.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| React frontend | OpenClaw is backend-only | None |
| Panel grid layout | No OpenClaw equivalent | None |
| PanelBase component | No OpenClaw equivalent | None |
| Responsive breakpoints | No OpenClaw equivalent | None |
| Orb opacity fade | No OpenClaw equivalent | None |
| WebSocket message types | OpenClaw uses different protocol | None |
| CSS design system | No OpenClaw equivalent | None |
| react-grid-layout | No OpenClaw equivalent | None |

### Key Architectural Point
OpenClaw is a **backend agent platform**. It has no frontend capabilities:
- No React components
- No CSS/styling system
- No WebSocket frontend protocol
- No HUD visualization

The HUD Panel Framework is 100% frontend code (React + TypeScript + CSS), which OpenClaw cannot address.

### What Stays JARVIS-Native (100%)
- **HudLayout.tsx** — grid orchestrator with opacity fade
- **PanelBase.tsx** — shared panel wrapper
- **PanelPositions.tsx** — grid area components
- **All CSS variables** — design system
- **All WS message types** — frontend protocol
- **react-grid-layout integration** — drag-and-drop panels
- **Multi-monitor support** — per-monitor layout persistence

### Data Flow With OpenClaw (If Option A Adopted)
Even if OpenClaw handles backend operations, the frontend remains unchanged:
```
OpenClaw backend → JARVIS bridge → WebSocket → HUD frontend
                                       │
                                       └─► All panel rendering JARVIS-native
```

### Recommendation
- **Keep 100% JARVIS-native**: No OpenClaw leverage possible
- **Frontend is independent**: Backend changes (OpenClaw) don't affect HUD

### Verdict
This spec is **FULLY JARVIS-native** — OpenClaw is backend-only and cannot replace any frontend functionality.
