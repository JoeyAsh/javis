# JARVIS — Design System

React + TypeScript + Vite + Tailwind CSS + Three.js. Single-page app with a fullscreen particle orb and minimal HUD overlays. Communicates with the Python backend via WebSocket.

---

## Design Language — Hypermodern HUD

### Core Principles

| Principle | Rule |
|---|---|
| **Font** | JetBrains Mono exclusively — never switch to another typeface |
| **Borders** | Hairline 1 px only — no `border-width` above 1 px in component chrome |
| **Radius** | Hard cap at `var(--r-2)` (4 px) everywhere; `var(--r-1)` (2 px) preferred; `var(--r-0)` (0) for structural elements |
| **Shadow** | Glow via `box-shadow: var(--glow)` — no `drop-shadow` or `filter: blur()` for chrome |
| **Palette** | Dark-only — no light mode, no adaptive color scheme |
| **Color source** | All colors via CSS variables — no hardcoded hex in components or Tailwind arbitrary values |
| **Layout vs color** | Tailwind for layout and spacing; CSS variables for color, shadow, font |
| **Overlay panels** | `position: fixed`, `z-index: var(--z-panel)+`, `background: rgba(13,13,20,0.75)`, `backdrop-filter: blur(12px)`, `border: 1px solid var(--border)` |
| **Entry animation** | `winIn` — 500 ms clip-path reveal from top edge |
| **State transitions** | Opacity crossfade 300 ms (`var(--dur-base)`) |

### Token Reference

All tokens live in `frontend/src/styles/tokens.css` (imported from `frontend/src/index.css`).

#### Colors

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#050508` | Page / canvas background |
| `--surface` | `rgba(13,13,20,0.75)` | Panel background with 75 % opacity |
| `--surface-raised` | `rgba(22,22,34,0.85)` | Elevated surface — header rows, hover states |
| `--border` | `rgba(64,112,160,0.25)` | Default border on panels, separators |
| `--border-bright` | `rgba(76,168,232,0.55)` | Active / focused border (accent-tinted hairline) |
| `--accent` | `#4ca8e8` | Primary interactive accent — orb idle, links |
| `--accent-bright` | `#7ec8ff` | Brighter accent — orb thinking, active labels |
| `--accent-speak` | `#a8e0ff` | Soft accent — orb speaking state |
| `--accent-dim` | `rgba(76,168,232,0.35)` | Dimmed accent for inactive / ghost elements |
| `--text` | `#e8f4ff` | Primary body text |
| `--text-secondary` | `#8ba9c8` | Labels, metadata, secondary info |
| `--text-muted` | `#4a6a88` | Placeholders, timestamps, disabled text |
| `--warning` | `#e8a84c` | Amber warning — also used for `working` orb state |
| `--error` | `#e84c4c` | Error / destructive action |
| `--success` | `#4ce88a` | Success confirmation |

#### Glow

| Token | Value | Usage |
|---|---|---|
| `--glow` | `0 0 12px rgba(76,168,232,0.18)` | Default interactive hover shadow |
| `--glow-strong` | `0 0 24px rgba(76,168,232,0.35)` | Focused panel, active drag target |
| `--glow-inner` | (inset variant defined in tokens.css) | Active state on tiles (e.g. zone tiles in LightsPanel) |
| `--glow-warn` | `0 0 12px rgba(232,168,76,0.35)` | Warning-state glow |
| `--glow-error` | `0 0 12px rgba(232,76,76,0.35)` | Error-state glow |

#### Panel

| Token | Value | Usage |
|---|---|---|
| `--panel-bg` | Same as `--surface` | Canonical alias for panel background |
| `--panel-blur` | `blur(12px)` | `backdrop-filter` on overlay panels |
| `--panel-opacity` | `1.0` (runtime override via Settings slider) | Applied as a CSS var on `#root` so all `.window` elements inherit it |

#### Typography

| Token | Value | Usage |
|---|---|---|
| `--font` | `'JetBrains Mono', ui-monospace, monospace` | Applied to `html, body` and inherited everywhere |

#### Radii

| Token | Value | Usage |
|---|---|---|
| `--r-0` | `0px` | Zero radius — structural containers, canvas borders |
| `--r-1` | `2px` | Preferred HUD radius — buttons, badges, zone tiles |
| `--r-2` | `4px` | Maximum allowed anywhere in the UI |

#### Spacing

| Token | Value | Usage |
|---|---|---|
| `--s-1` | `4px` | Tightest gap — icon-to-label, badge padding |
| `--s-2` | `8px` | Default inline gap — header items, grid gaps |
| `--s-3` | `12px` | Panel inner padding (horizontal) |
| `--s-4` | `16px` | Section separator, panel header height ≈ |
| `--s-5` | `20px` | Larger section gap |
| `--s-6` | `24px` | Panel outer margin |
| `--s-7` | `32px` | Large layout gap (between major sections) |

#### Z-index

| Token | Value | Usage |
|---|---|---|
| `--z-orb` | `0` | Three.js canvas — sits behind everything |
| `--z-panel` | `10` | Floating HUD windows |
| `--z-status` | `20` | Status text, bottom center label |
| `--z-topbar` | `30` | Top bar — always on top of panels |
| `--z-dev` | `40` | Dev menu, mute button, orb override controls |
| `--z-modal` | `50` | Settings overlay, confirmation dialogs |

#### Motion

| Token | Value | Usage |
|---|---|---|
| `--ease` | `cubic-bezier(0.25,0,0.1,1)` | Default easing for all transitions |
| `--dur-fast` | `150ms` | Micro-interactions — hover color, badge flash |
| `--dur-base` | `300ms` | Standard UI transitions — opacity, border-color |
| `--dur-slow` | `500ms` | Entry/exit animations (`winIn`) |
| `--dur-ambient` | `4000ms` | Ambient loops — light trace circumnavigation |

---

### Brand Signatures

#### Corner Brackets — `.hud-corner` / `HudCornerBrackets`

Angular L-shaped decorations placed at each corner of a panel. Rendered by the `HudCornerBrackets` primitive component inside `HudPanel`. The viewport-level version uses the `.hud-corner` CSS class directly on corner elements in `HudViewportCorners` (added by structural-fix agent).

Usage in panel composition:
```tsx
<HudPanel icon="◉" title="Panel Title" badge="STATUS">
  {/* HudCornerBrackets is rendered internally by HudPanel */}
  <YourContent />
</HudPanel>
```

#### Circumnavigating Light Trace — `HudLightTrace`

A single bright point that travels around the full perimeter of a panel at `--dur-ambient` speed (4 s loop). Implemented in `HudLightTrace.tsx` using a CSS animation on a pseudo-element. Applied per-panel by `HudPanel` primitive.

#### Panel Bloom — `HudBloom`

A soft radial gradient overlay rendered with `mix-blend-mode: screen` to give panels a subtle glow from within. Does not affect layout. Applied per-panel by `HudPanel` primitive.

```css
/* Conceptual — actual values in HudBloom.css */
mix-blend-mode: screen;
pointer-events: none;
```

#### Shimmer Underline

Focused panels display an animated shimmer on their bottom border — a bright point sweeping left to right at `--dur-ambient` speed. Activated by the `.focused` class on the panel.

#### Side Rails — `HudSideRails`

Thin vertical lines (1 px, `--accent-dim` color) on the left and right edges of a panel body, creating a data-terminal frame aesthetic.

---

### Entry Animation

All panels use the `winIn` keyframe defined in `hud/hud.css`:

```css
@keyframes winIn {
  from {
    clip-path: inset(0 0 100% 0);
    opacity: 0;
  }
  to {
    clip-path: inset(0 0 0% 0);
    opacity: 1;
  }
}
```

Duration: 500 ms (`--dur-slow`). Applied to `.window` on mount via the settle animation system in `WindowManager`.

---

### Radius Cap

**Never exceed `var(--r-2)` (4 px) anywhere in the UI.** Specifically:
- `border-radius: 0` for structural containers, canvas borders, separators
- `border-radius: var(--r-1)` (2 px) for buttons, tiles, badges — preferred default
- `border-radius: var(--r-2)` (4 px) maximum — use sparingly for pill-like elements only
- `border-radius: 50%` is forbidden except for purely decorative dot indicators

---

## Orb Variants

JARVIS ships two distinct orb implementations. The active variant is selected at runtime via the `jarvis.orbVariant` key in `localStorage` (default: `'classic'`), exposed as a dropdown in **Settings → Display**.

### Classic Orb

**Component chain:** `OldOrb.tsx` → `OrbCanvas.tsx` → `frontend/src/lib/orb.ts`

The Three.js particle orb. The engine in `lib/orb.ts` manages a particle system, shader-based glow, and state-driven color transitions. The `alpha` parameter controls particle opacity (added in the hud-rework branch for the `working` overlay).

Public API (the only way to interact with the engine):
```typescript
orb.setState(state: OrbState)   // drive particle color + animation preset
orb.setAnalyser(node: AnalyserNode)  // feed mic/TTS audio for waveform response
orb.destroy()                    // teardown on unmount
```

Never modify `lib/orb.ts`.

### Hypermodern CSS Orb

**Component chain:** `Orb.tsx` + `orb.css`

A fully CSS + RAF-driven orb rendered in a `<div>` — no WebGL, no canvas. Structure:

- **5 concentric rings** — varying opacity and border-width for depth
- **36 tick marks** on the outermost ring — evenly spaced radial dashes
- **3 pulse rings** — expand-fade-reset loop, staggered offsets
- **6 orbiting particles** — RAF-driven `transform: rotate() translateX()` animation
- `is-working` class on the app root tints rings, particles, and pulse rings amber (`var(--warning)`) during tool execution (`AppOrbState === 'working'`)

OrbState → visual behavior:
| State | Color | Animation |
|---|---|---|
| `idle` | `--accent` | Slow ambient pulse |
| `listening` | `--accent` | Active pulse ring expansion |
| `thinking` | `--accent-bright` | Spin + accelerated particle orbit |
| `speaking` | `--accent-speak` | Wave oscillation on rings |
| `working` | `--warning` (amber) | Tool-execution tint via `.is-working` class |

### Runtime Variant Selection

`App.tsx` reads `settings.orbVariant` from `useSettings` and conditionally renders:

```tsx
{settings.orbVariant === 'classic' ? (
  <OrbErrorBoundary>
    <OrbCanvas orbState={effectiveOrbState} analyser={analyser} ... />
  </OrbErrorBoundary>
) : (
  <Orb state={effectiveOrbState} />
)}
```

The Settings overlay Display section exposes a `<select>` that calls `setOrbVariant()`, persisting the choice to `localStorage['jarvis.orbVariant']`.

---

## Sound Design

### Asset Pipeline

51 sound assets generated with ElevenLabs Sound Effects API. Organized under `assets/sounds/<event>/<event>_N.mp3`. Copied to `frontend/public/sounds/` at dev/build time via `npm run predev` script (gitignored destination).

Runtime path convention: `/sounds/<event>/<event>_N.mp3`

### Single Source of Truth

`frontend/src/config/audio.ts` is the sole registry for all SFX mappings. No hardcoded file paths elsewhere in the codebase. Every `SfxEvent` entry specifies its file path, type (oneshot/loop), volume, and duck behavior.

### Mute Toggle

`AudioMuteToggle` component writes to `localStorage['jarvis.sfx.muted']`. Mutes all SFX; does NOT affect TTS voice playback. State is read on boot before the first sound plays.

### Duck Behavior

The following loops automatically reduce to their ducked volume within 200 ms when `orbState` is `listening` or `speaking`:

| Loop | Normal | Ducked |
|---|---|---|
| `ambient_2` | 25% | 5% |
| `scan_1` | 40% | 10% |
| `thinking_1` | 35% | 8% |
| `working_1` | 35% | 8% |
| `idle_pulse_1` | 15% | 3% |
| `heartbeat_1` | 15% | 3% |
| `progress_tick_1` | 40% | 10% |
| `sync_1` | 35% | 8% |

One-shots are never duckable.

### Multi-Variant Events

Events with multiple generated files use a single confirmed primary pick:

| Event | Primary File | Alternates |
|---|---|---|
| `ambient` (loop) | `ambient/ambient_2.mp3` | `ambient_1.mp3` |
| `boot` | `boot/boot_3.mp3` | `boot_1`, `boot_2`, `boot_4` |
| `confirm` | `confirm/confirm_1.mp3` | `confirm_2.mp3` |
| `window maximize` | `transition/transition_1.mp3` | — |
| `window minimize` | `transition/transition_2.mp3` | — |

Alternate files are kept in `assets/sounds/` as future-selectable variants but are not loaded at runtime. See `audio.ts` top-of-file comment for the full deferred/unused inventory.

### Child Issue Mapping

Full event inventory across 5 themed child issues:
- **#34** — JARVIS lifecycle, orb states, ambient loops
- **#35** — Window and panel interactions
- **#36** — User input feedback (clicks, hovers, selects, toasts)
- **#37** — Acknowledgements and alerts
- **#38** — Notifications, data events, progress

---

## Orb States

| State | Particle color | UI accent |
|---|---|---|
| `idle` | `--accent` | `--accent` |
| `listening` | `--accent` | `--accent` + pulse ring |
| `thinking` | `--accent-bright` | `--accent-bright` + spin |
| `speaking` | `--accent-speak` | `--accent-speak` + wave |
| `working` | `--warning` (amber) | amber tint via `.is-working` |
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
