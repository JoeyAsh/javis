# Handoff: JARVIS HUD (Hypermodern)

## Overview

A full-screen "Iron Man HUD"–style desktop dashboard: a central **Orb** surrounded by concentric rings, with a top app-bar, a grid of fixed-position glass **panels** (System Vitals, Transcript, Agenda, Mail, GitLab, Now Playing, Lights, Notifications), an animated background scene (grid + scanlines + stars + vignette), and user-tweakable visuals (hue, glow, toggles).

The design language is "sci-fi precision": JetBrains Mono, hairline borders, **2 px max radius**, glow instead of drop-shadow, cyan/blue accent palette tunable by hue, corner-bracket chrome on every panel, and a **circumnavigating light trace** that runs around every panel + the topbar as an ambient animation.

## About the Design Files

The files in `reference/` are **design references created as a single-file HTML prototype** (React + Babel + inline JSX). They demonstrate the intended look and behavior — **they are not production code to copy directly**. Your task is to **recreate this design in the target codebase's existing environment** (React + Vite + TypeScript) using its established patterns: split components into proper files, replace inline Babel with regular TSX, keep CSS modular, and wire the state to whatever store / context the app already uses.

- `reference/JARVIS HUD Hypermodern.html` — the full prototype (open in browser to see it running)
- `reference/design-system/colors_and_type.css` — the foundational token + utility CSS (import this into the app)
- `reference/design-system/orb.mp4` — original video-orb asset (used by the "old" orb if you need it)
- `reference/design-system/favicon.svg` — favicon

## Fidelity

**High-fidelity.** Colors, typography, spacing, radii, animations, and interactions are final. Recreate pixel-perfectly.

## Target stack

- **React 18 + Vite + TypeScript**
- **No Tailwind assumed.** The design uses plain CSS with CSS custom properties. If the app already uses Tailwind / styled-components / CSS Modules, translate the provided CSS into that system — but **keep the variable names** (`--accent`, `--glow`, etc.) as a single source of truth on `:root`.
- **No extra runtime deps needed.** Everything is CSS + React. If the codebase already uses `framer-motion`, you can port the `@keyframes` if desired, but straight CSS animations are fine.

---

## ⚡ Critical requirement: Orb is swappable

The user wants to **toggle between the new Orb and the existing (old) Orb** at runtime. Architect it as:

```tsx
// A simple prop or context switch
<DesktopHUD orbVariant="new" />   // new animated CSS orb
<DesktopHUD orbVariant="old" />   // whatever the existing orb was

// Inside DesktopHUD, render the chosen orb:
const OrbComponent = orbVariant === 'new' ? NewOrb : OldOrb;
<OrbComponent state={state} rings={rings} particles={particles} />
```

Deliverables you must produce:

- `src/components/hud/Orb.tsx` — the **new** orb, isolated. Exports a default `Orb` component taking `{ state: 'idle'|'listening'|'thinking'|'speaking'|'working', rings: boolean, particles: boolean }`.
- `src/components/hud/orb.css` — orb-only styles (`.orb`, `.ring`, `.ring-ticks`, `.pulse`, `.particle`, `.reactor`, orb state keyframes). **Do not bleed these into hud.css** — the app needs to swap the orb cleanly.
- `src/components/hud/DesktopHUD.tsx` — the HUD shell (scene, topbar, panels). **Does not import Orb.css or Orb directly**; instead takes the orb as a prop or child so the parent can mount old/new orb and the HUD stays agnostic.

Example:

```tsx
interface DesktopHUDProps {
  orb: React.ReactNode; // mounted by parent
}
<DesktopHUD orb={<Orb state={state} rings particles/>} />
```

---

## Screens / Views

There is exactly **one screen** — the full-viewport desktop HUD. It consists of six concurrent regions:

### 1. Scene (background, `z-index: 0`, non-interactive)
- Fixed full-screen layered backdrop:
  - **Radial bg**: `radial-gradient(ellipse at 50% 52%, #0a1220 0%, #05080f 45%, #020206 100%)`
  - **Grid**: 44×44 px cyan grid lines (`rgba(76,168,232,0.055)`), masked with a centered radial so edges fade, animated drifting (`@keyframes gridDrift` — 28s linear).
  - **Scanlines**: 3 px repeating horizontal lines, `mix-blend: screen`, opacity .7.
  - **Noise**: SVG turbulence data-URI, opacity .06, `mix-blend: overlay`.
  - **Horizon**: bottom 38% gradient `rgba(76,168,232,.08) → transparent`.
  - **Stars**: 60 randomly placed white dots, each with its own twinkle delay.
  - **Vignette**: radial black fade at edges.
- Toggles: `grid`, `stars`, `scan` can be turned off via the Tweaks panel.

### 2. TopBar (fixed top, `z-index: 30`, 40 px tall)
- `position: fixed; top:10; left:10; right:10; height:40; background: rgba(13,13,20,.55); backdrop-filter: blur(14px); border: 1px solid var(--border); border-radius: 2px;`
- **Four corner brackets** (`.c-bl`, `.c-br`, plus `::before` and `::after` on the bar itself) — 12×12 px, 1 px accent-colored L-shapes offset by −2 px so they hang just outside the border. Each breathes via `tbCornerBreath` (3.4s, staggered delays around the bar so it wavs around).
- **Circumnavigating trace**: a `<span class="trace">` child with two pseudo-elements (top+bottom) and two `<i>` children (left+right). Each runs an accent-bright gradient strip along one edge at offset animation times, creating the illusion of a single light running around the bar:
  - Top strip: left → right (5.2s linear)
  - Bottom strip: right → left (delay −2.6s)
  - Left strip: top → bottom (delay −3.9s)
  - Right strip: bottom → top (delay −1.3s)
- **Content** (left→right):
  - `<span class="tag">● LINK · SECURE</span>` — pulsing green dot
  - Time (HH:MM:SS, `de-DE`, tabular-nums)
  - Long date
  - Weather: `☁ 14°C · Wien`
  - Coords: `N 48.21 · E 16.37`
  - Center: brand `J A R V I S / MK XLII`
  - Right: 4 icon buttons — Idle, Reset layout, Tweaks, Settings (28×28, hollow stroke SVGs, hover = accent-bright + glow)

### 3. Orb cluster (centered, `z-index: 0`)
Covered by `Orb.tsx` (see separate spec below). Sits visually behind the panels.

### 4. Panels (fixed positions, `z-index: 10`)
**Eight panels, absolute positions on a 1440×900 reference viewport.** All share the same `<Panel>` shell: glass background, hairline border, 4 corner brackets (`.ck`), two side rails (`.rail`), trace (`.trace`), 26 px header with `ix` glyph + title + 3 dots + optional pill badge, then body.

Positions (all `position: fixed`):

| Panel | Position | Size |
|---|---|---|
| System Vitals | `left:24, top:66` | `316 × 300` |
| Now Playing | `left:24, top:386` | `316 × 184` |
| Lights | `left:24, top:588` | `316 × 172` |
| Agenda | `right:408, top:66` | `344 × 224` |
| Mail | `right:408, top:308` | `344 × 224` |
| GitLab | `right:408, top:550` | `344 × 210` |
| Transcript | `right:24, top:66` | `368 × 466` |
| Notifications | `right:24, top:552` | `368 × 208` |

Panel shell styles:
```css
.panel {
  position: fixed; z-index: 10;
  background: rgba(13,13,20,.72);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 2px;
  display: flex; flex-direction: column;
  overflow: hidden;
  animation: winIn .5s var(--ease) both;
  transition: border-color .25s, box-shadow .25s;
}
@keyframes winIn {
  0%   { opacity:0; transform: translateY(8px) scale(.985); clip-path: inset(46% 0 46% 0); }
  60%  { clip-path: inset(0 0 0 0); opacity:1; }
  100% { transform:none; }
}
```

**Corner brackets `.ck`** on each panel (4×, one per corner):
```css
.panel .ck {
  position: absolute; width:10px; height:10px;
  border-color: var(--accent); border-style: solid;
  opacity: .7;
  transition: width .3s var(--ease), height .3s var(--ease),
              opacity .25s, border-color .25s;
}
.panel .ck.tl { top:-2px; left:-2px;  border-width:1px 0 0 1px; }
.panel .ck.tr { top:-2px; right:-2px; border-width:1px 1px 0 0; }
.panel .ck.bl { bottom:-2px; left:-2px;  border-width:0 0 1px 1px; }
.panel .ck.br { bottom:-2px; right:-2px; border-width:0 1px 1px 0; }
.panel:hover .ck         { width:14px; height:14px; opacity:.85; border-color: var(--accent-bright); }
.panel.focused .ck       { width:20px; height:20px; opacity:1;   border-color: var(--accent-bright); animation: cornerBreath 2.6s ease-in-out infinite; }
@keyframes cornerBreath {
  0%,100% { width:18px; height:18px; border-color: var(--accent); }
  50%     { width:22px; height:22px; border-color: var(--accent-bright); }
}
```

**Focus/hover bloom (NOT drop-shadow)** — a `::after` radial-gradient overlay with `mix-blend-mode: screen` lights the card from inside:
```css
.panel::after {
  content:''; position:absolute; inset:0; pointer-events:none; border-radius:2px;
  background:
    radial-gradient(120% 70% at 50% 0%,   color-mix(in srgb, var(--accent) 16%, transparent) 0%, transparent 55%),
    radial-gradient(120% 70% at 50% 100%, color-mix(in srgb, var(--accent) 10%, transparent) 0%, transparent 55%);
  mix-blend-mode: screen;
  opacity: 0; transition: opacity .3s ease;
}
.panel:hover::after    { opacity:.55; animation: panelBloom 3s   ease-in-out infinite; }
.panel.focused::after  { opacity:1;   animation: panelBloom 2.6s ease-in-out infinite; }
@keyframes panelBloom {
  0%,100% { filter: brightness(.85); }
  50%     { filter: brightness(1.25); }
}
```

**Circumnavigating trace** on every panel — same system as TopBar (see CSS in `hud.css`):
```html
<span class="trace"><i class="l"/><i class="r"/></span>
```
Four strips (top ltr, bottom rtl, left ttb, right btt), each `animation: 6s linear infinite` with staggered negative delays so they chase each other around the card. Opacity goes .55 → .9 (hover) → 1 (focused).

**Panel header**:
```css
.panel .hdr {
  height: 26px; padding: 0 10px;
  display: flex; align-items: center; gap: 8px;
  border-bottom: 1px solid var(--border);
  font-size: 9px; letter-spacing: 2px; text-transform: uppercase;
  color: var(--text-secondary);
  background: rgba(76,168,232,.04);
}
.hdr .ix   { color: var(--accent-bright); }
.hdr .tt   { color: var(--text); }
.hdr .dots i { width:3px; height:3px; background: var(--text-muted); border-radius:50%; display:inline-block; margin: 0 1px; }
.hdr .badge{ margin-left:auto; font-size:8px; padding:1px 6px; border:1px solid var(--accent-dim); color: var(--accent); letter-spacing:2px; }
```

#### Panel content specs

- **System Vitals** — 2-col grid of 6 "tiles", each with `{label, value+unit, sparkline, sub?}`. Sparkline is a 100×28 viewBox SVG with a filled area + stroke path. Values tick every 1.4 s; CPU-temp tile is `warn` (amber `var(--warning)` stroke). See `SystemPanel` in the reference.

- **Now Playing** — 72×72 album-art block (styled with `AC / DC` text), meta column (title/artist/album, waveform strip), progress bar, prev/play/next buttons.

- **Lights** — 4 toggleable zones. Each: `name + indicator dot`, progress bar showing dim level, `"72 %"` / `"AUS"` label. Click toggles on/off; when off, dim=0.

- **Agenda** — 4 events: `{time, name, sub, pill}`. `NOW` pill = accent-bright bg; others = muted.

- **Mail** — 3 unread messages: `{time (accent-bright if unread), subject, from, NEU pill}`.

- **GitLab** — 3 pipelines: `{time, project, branch (muted), status}`. `passed` = green pill, `running` = amber.

- **Transcript** — chat-style turns. Bubbles have a left border tint that differs for `jarvis` (accent) vs `user` (speak). Auto-scroll to bottom on new turns. `thinking` state adds a blinking-dots bubble.

- **Notifications** — 4 items: `{source, time, text}`. `t: 'warn'` items get amber left border.

### 5. Reactor (centered bottom, `z-index: 0`)
Giant radial-gradient semicircle sitting below the orb, 900×900 px, 360 px offset below viewport. Optional decorative arc on top via `::before`. Non-interactive.

### 6. Dev/chrome overlays (`z-index: 40+`)
- **Tweaks panel** (bottom-right, toggled by Tweaks button in topbar) — contains slider for `hue` (0–360), slider for `glow` (0–100), checkboxes for `scan`, `grid`, `stars`, `rings`, `particles`, `idleDim`. Values are stored in component state and applied to `:root` via `useTweakApply` (see below).
- **Settings panel** — similar shell, different content (not critical for MVP).

---

## Orb spec (separate component)

File: `src/components/hud/Orb.tsx` + `src/components/hud/orb.css`

### Props
```ts
interface OrbProps {
  state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'working';
  rings?: boolean;     // default true
  particles?: boolean; // default true
}
```

### Structure
```jsx
<div className="orb-wrap">
  {rings && <>
    <div className="ring r5"/>
    <div className="ring r4"/>
    <div className="ring r3"/>
    <div className="ring r2"/>
    <div className="ring-ticks">{/* 36× <i/> at 10° increments */}</div>
    <div className="ring r1"/>
  </>}
  <div className={`orb state-${state}`}/>
  <div className="pulse d1"/><div className="pulse d2"/><div className="pulse d3"/>
  {particles && /* 6 orbiting particles, animated via RAF + useState tick */}
</div>
```

### Orb core
- **Size**: roughly 170 px (set via parent or explicit width/height in `.orb`). In prototype the orb sits centered absolute at 50/50 of viewport.
- **Base style**:
  ```css
  .orb {
    width: 170px; height: 170px; border-radius: 50%;
    background: radial-gradient(circle at 48% 42%,
      #ffffff 0%, #e8f4ff 6%, #6ec4ff 18%, #4ca8e8 34%,
      rgba(76,168,232,.4) 58%, rgba(76,168,232,0) 82%);
    box-shadow: 0 0 70px #5ab8f0cc, 0 0 180px #5ab8f066, inset 0 0 50px #e8f4ff33;
    animation: orbFloat 6.5s ease-in-out infinite;
  }
  .orb::before { content:''; position:absolute; inset:28%; border-radius:50%; background: radial-gradient(...); box-shadow: 0 0 28px #e8f4ffcc; }
  .orb::after  { content:''; position:absolute; inset:44%; border-radius:50%; background:#fff; box-shadow: 0 0 14px #fffc, 0 0 28px #a8e0ff99; }
  ```
- **States**:
  - `idle` → only `orbFloat`
  - `thinking` → `orbFloat + orbThink` (2.6s linear, hue-rotate 8°)
  - `speaking` → `orbFloat + orbSpeak` (0.6s, pulses box-shadow strength)
  - `listening` → `orbFloat + orbListen` (1.4s, scale 1 ↔ 1.03); ALSO `.pulse` rings become active (`animation: pulse 1.8s ease-out infinite` at delays 0 / .6s / 1.1s)
  - `working` → amber-tinted background + `orbWork`. When root has `.is-working` class, rings/pulse/particles turn amber (`var(--warning)`).

### Rings
```css
.ring { position:absolute; left:50%; top:50%; border-radius:50%; transform:translate(-50%,-50%); pointer-events:none; }
.ring.r1 { width:360px; height:360px; border:1px dashed rgba(76,168,232,.55); animation: spin 32s linear infinite; }
.ring.r2 { width:460px; height:460px; border:1px solid rgba(76,168,232,.35); animation: spin 48s linear infinite reverse; }
.ring.r3 { width:580px; height:580px; border:1px dotted rgba(110,196,255,.35); animation: spin 70s linear infinite; }
.ring.r4 { width:740px; height:740px; border:1px solid rgba(76,168,232,.15); animation: spin 120s linear infinite reverse; }
.ring.r5 { width:920px; height:920px; border:1px dashed rgba(110,196,255,.1); animation: spin 180s linear infinite; }
@keyframes spin { to { transform: translate(-50%,-50%) rotate(360deg); } }
.ring-ticks { width:460px; height:460px; animation: spin 110s linear infinite; }
.ring-ticks i { position:absolute; left:50%; top:0; width:1px; height:8px; background: var(--accent); box-shadow: 0 0 4px var(--accent); transform-origin: 0 230px; }
```

### Particles (orbiting)
6 particles at radii 180 / 210 / 240 / 265 / 295 / 330 px, alternating direction, 10–28 s orbit periods. Driven by RAF:
```tsx
const [tick, setTick] = useState(0);
useEffect(() => {
  let raf:number;
  const loop = (t:number) => { setTick(t/1000); raf = requestAnimationFrame(loop); };
  raf = requestAnimationFrame(loop);
  return () => cancelAnimationFrame(raf);
}, []);
// x = cos((tick * 2π / dur) * dir + i*1.05) * r;  y = sin(...) * r;
```

---

## Interactions & behavior

- **Click panel** → sets it as `focused` (one focused at a time). Focused panels show the bloom + breathing corners + brighter trace.
- **Orb state cycling** — in prototype, there's a demo that cycles through states. In the real app, wire `state` to the actual voice/assistant pipeline.
- **Idle mode** — if `idleDim` is on and no interaction for ~30 s, dim panels to opacity .5. Any mouse move resets.
- **Tweaks** — hue/glow sliders update CSS vars live on `:root` via a `useTweakApply` effect:
  ```tsx
  function useTweakApply(t: { hue:number; glow:number }) {
    useEffect(() => {
      const r = document.documentElement;
      const l = 0.72, c = 0.14;
      r.style.setProperty('--accent',        `oklch(${l} ${c} ${t.hue})`);
      r.style.setProperty('--accent-bright', `oklch(${l+0.1} ${c+0.02} ${t.hue})`);
      r.style.setProperty('--accent-speak',  `oklch(${l+0.05} ${c+0.01} ${t.hue})`);
      r.style.setProperty('--accent-dim',    `oklch(${l-0.2} ${c-0.04} ${t.hue})`);
      r.style.setProperty('--glow',
        `0 0 ${6 + t.glow*0.1}px oklch(${l} ${c} ${t.hue} / ${0.4 + t.glow*0.005})`);
    }, [t]);
  }
  ```
- **Now Playing** — progress ticks locally every 700 ms while `playing`; prev/next are stubs; play button toggles state.
- **Lights** — click toggle flips `on` + resets `d` to 60 or 0. (Add a slider inside if the real app wants dimmer control.)
- **Transcript** — auto-scrolls to bottom on new turns (`ref.scrollTop = ref.scrollHeight`).

## State management

Top-level HUD owns:
```ts
type Orbstate = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working';
interface Tweaks { hue:number; glow:number; scan:boolean; grid:boolean; stars:boolean; rings:boolean; particles:boolean; idleDim:boolean; }
interface HUDState {
  state: Orbstate;
  focusedPanel: string | null;
  tweaks: Tweaks;
  idle: boolean;
  turns: Turn[];  // transcript
  now: Date;      // clock tick
}
```
If the app already has a store (Redux/Zustand/context), mount under `ui.hud`.

---

## Design tokens

**Already defined in `reference/design-system/colors_and_type.css`.** Copy that file into `src/styles/tokens.css` and import from `main.tsx`.

Key variables (don't rename — animations and gradients reference them):

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#050508` | Page background |
| `--surface` | `#0d0d14` | Panel solid (pre-alpha) |
| `--border` | `#1a1a2e` | Hairline borders, idle |
| `--accent` | `#4ca8e8` (overridden by hue tweak) | Primary blue, corners, glow |
| `--accent-bright` | `#6ec4ff` | Hover/focus, dominant glow |
| `--accent-speak` | `#5ab8f0` | Orb speaking tint |
| `--accent-dim` | `#2d6aa1` | Inactive/idle accents |
| `--text` | `#e8f4ff` | Primary text |
| `--text-secondary` | `#6b8fa8` | Labels |
| `--text-muted` | `#2a3d4f` | Disabled / tertiary |
| `--warning` | `#e8b24c` | Amber (working state, warn tiles) |
| `--success` | `#4ce8a8` | Green (pipeline passed, link-secure dot) |
| `--error` | `#e85a5a` | Red |
| `--glow` | `0 0 8px #4ca8e8aa` | Standard focus glow |
| `--glow-strong` | `0 0 20px #4ca8e8cc, 0 0 40px #4ca8e844` | Strong (buttons pressed) |
| `--r-1` | `2px` | **Default radius — never exceed `--r-2` (4px)** |
| `--s-1..7` | 4 / 8 / 12 / 16 / 24 / 32 / 48 | Spacing scale |
| `--font` | `'JetBrains Mono', ui-monospace, ...` | **Entire UI is JetBrains Mono** |
| `--ease` | `cubic-bezier(.4, 0, .2, 1)` | Default easing |

## Assets

- **Font**: JetBrains Mono (Google Fonts import at top of `colors_and_type.css`)
- **Orb legacy asset**: `design-system/orb.mp4` (if user wants `<OldOrb>` to be the video)
- **Favicon**: `design-system/favicon.svg`
- No raster images. All icons are inline SVG (stroke-width 1.75, `round` linecap/join).

## Files in this bundle

```
design_handoff_jarvis_hud/
├── README.md                                  ← this file
└── reference/
    ├── JARVIS HUD Hypermodern.html            ← runnable prototype (open in browser)
    └── design-system/
        ├── colors_and_type.css                ← paste into src/styles/tokens.css
        ├── orb.mp4                            ← legacy orb video (for OldOrb)
        └── favicon.svg
```

## Suggested file layout in target repo

```
src/
├── styles/
│   └── tokens.css                             ← copy of colors_and_type.css
├── components/
│   └── hud/
│       ├── DesktopHUD.tsx                     ← shell: scene + topbar + panels, takes `orb` prop
│       ├── hud.css                            ← all panel/topbar/trace/scene CSS
│       ├── Orb.tsx                            ← NEW orb (swappable)
│       ├── orb.css                            ← orb-only CSS (rings, states, particles)
│       ├── OldOrb.tsx                         ← wrapper around existing orb asset/impl
│       ├── TopBar.tsx
│       ├── Scene.tsx
│       └── panels/
│           ├── Panel.tsx                      ← shared shell (corners, trace, header)
│           ├── SystemPanel.tsx
│           ├── NowPlayingPanel.tsx
│           ├── LightsPanel.tsx
│           ├── AgendaPanel.tsx
│           ├── MailPanel.tsx
│           ├── GitlabPanel.tsx
│           ├── TranscriptPanel.tsx
│           └── NotificationsPanel.tsx
└── hooks/
    └── useTweakApply.ts
```

## Implementation order (recommended)

1. Drop in tokens.css + install JetBrains Mono.
2. Build `Panel.tsx` shell (chrome only — corners, trace, header, bloom) and verify on a blank test page.
3. Build `TopBar.tsx` (chrome animations are the distinctive sig).
4. Build `Scene.tsx` (background layers).
5. Build `DesktopHUD.tsx` composing the above, with an `orb` **slot prop**.
6. Build `Orb.tsx` + `orb.css` separately, wire it as `<DesktopHUD orb={<Orb ...>}/>`.
7. Wrap the existing orb as `<OldOrb>` that matches the same props interface — now you can swap with a single state flag.
8. Fill in panel content components one by one; all share Panel.
9. Wire the Tweaks panel + `useTweakApply` hook.
10. Wire real data sources (assistant state, transcript, system metrics) last.

## Notes & gotchas

- **Radius cap**: never exceed 2 px anywhere (pills may use pill radius, but no rounded cards).
- **Glow, never drop-shadow**: `.panel::after` bloom uses `mix-blend-mode: screen`, not `filter: drop-shadow` or outer `box-shadow`. Keep it that way — the user explicitly rejected drop-shadow-style glow.
- **Corner brackets + trace are the brand signature**: apply them to any new HUD surface you add later.
- **`color-mix()` + `oklch()` required** — target evergreen browsers; otherwise fall back to pre-computed hex.
- **Panel positions are viewport-absolute** on the 1440×900 reference. For real app: either keep fixed positions (if display resolution is controlled) or migrate to a CSS grid with named areas — but the user's current design is fixed-px, and that matches the sci-fi vibe.
- **`backdrop-filter: blur()`** on panels and topbar — required for the glass look.
