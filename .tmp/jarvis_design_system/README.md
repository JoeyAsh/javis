# JARVIS Design System

**"Just A Rather Very Intelligent System"** — a voice-activated AI assistant inspired by Tony Stark's JARVIS. This design system captures the holographic HUD aesthetic of Iron Man's lab: a dark, deep-blue command surface, a glowing particle orb at the center, and floating panels of crisp monospace data.

The project is a working voice assistant (wake-word → STT → Claude → TTS) with a fullscreen Three.js orb and draggable/snappable HUD panels. This design system preserves that look as a reusable kit — and pushes it further into "more sci-fi, more animation, more bling-bling" territory as requested.

---

## Sources

- **Repo:** [JoeyAsh/javis](https://github.com/JoeyAsh/javis) @ `main`
- **Design spec:** `docs/DESIGN.md` and `docs/FRONTEND.md` in that repo
- **Tech:** React + TypeScript + Vite + Tailwind + Three.js (frontend), Python + aiohttp WS + Claude API (backend)
- **Languages in UI:** German (primary, de-DE, Europe/Vienna) + English, mixed naturally

---

## Products / Surfaces

1. **JARVIS Web UI** — fullscreen holographic HUD with centered orb, floating windows for System, Now Playing, Transcript, Notifications, Mail, Lights, Agenda, GitLab, Self-Fix, Log, Dev.
2. **Controller (Tauri)** — system-tray native launcher. Same visual language, smaller surface.

---

## Index

```
README.md                  ← you are here
SKILL.md                   ← agent-skill manifest
colors_and_type.css        ← CSS variables (colors + type + semantics)
preview/                   ← design-system preview cards (registered assets)
assets/                    ← logos, favicons, brand marks
fonts/                     ← JetBrains Mono (OFL)
ui_kits/
  jarvis-hud/              ← fullscreen HUD recreation — the "lab" view
    index.html             ← interactive prototype
    *.jsx                  ← orb, windows, panels, infobar, push-to-talk
```

---

## Content Fundamentals

The JARVIS voice never says more than it needs to. It's a butler, not a chatbot.

- **Voice**: second-person (*"Sir, …"*), understated, dry, often German. The system itself uses tight terminal labels in English (`CPU`, `NET`, `UPTIME`, `LISTENING…`). Mixed de/en is natural — UI labels are German (*"VERBINDEN"*, *"Nicht verbunden"*, *"Heute"*), state machine is English.
- **Tone**: confident, spartan, technical. No exclamation marks. No emoji (except as weather glyphs `☀ ☁ 🌫 🌧`). No apologetic padding.
- **Casing**: ALL CAPS for system labels and state (`LISTENING`, `IDLE`, `NO ACTIVE PLAYBACK`), Title Case for panel titles, lowercase for transient state (`listening…`, `thinking…`, `speaking…`).
- **Letter-spacing**: aggressive on labels (`letterSpacing: 6px` for the JARVIS mark, `1px` for small-caps system text).
- **Numbers**: always padded (`09:04:17`, `CPU 42%`, `12.3 Mb/s`). Monospace everywhere.
- **Brevity**: the on-screen word budget is tiny. Prefer a glyph + number over a sentence.

**Examples from the real UI:**

| Where | Copy |
|---|---|
| bottom-center status | `listening...` / `thinking...` / `speaking...` / `follow-up...` |
| brand mark | `J A R V I S` (tracked 6px) |
| empty Spotify | `SPOTIFY — NICHT VERBUNDEN` → button `VERBINDEN` |
| empty transcript | `Kein Transcript` |
| system tiles | `CPU`, `RAM`, `GPU`, `CPU TEMP`, `NET`, `DISK` |
| unit sub-caps | `Mb/s`, `°C`, `%` |
| idle-mode toggle | `LIVE` / `IDLE` |
| weather line | `09:04:17 · Mittwoch, 20. April 2026 · ☀ 14°C Wien` |

---

## Visual Foundations

### Palette

The entire system lives on **3 near-black backgrounds** + **3 blue accents** + **3 text tiers**. This is non-negotiable.

```
--bg:             #050508   deep space
--surface:        #0d0d14   panel body
--surface-raised: #12121c   hover / focused panel
--border:         #1a1a2e   hairline separator
--accent:         #4ca8e8   orb idle, primary actions   ← THE color
--accent-bright:  #6ec4ff   orb thinking, hover glow
--accent-speak:   #5ab8f0   orb speaking
--text:           #e8f4ff   primary text (cool white)
--text-secondary: #6b8fa8   labels, secondary copy
--text-muted:     #2a3d4f   inactive, placeholder
--warning:        #e8b24c   CPU > 85%, temp > 80°C (amber)
```

No pastels. No green. No purple. One red-adjacent amber for warnings only.

### Typography

**JetBrains Mono** — one family, the whole UI. Weights 400/500/700 + italic. Substituted from Google Fonts in this kit; flagged below.

- **Display** (brand mark): 9px, uppercase, letter-spacing 6px, `var(--text-muted)` — whispered, not shouted.
- **H1 / panel title**: 12px, `var(--text)`, regular
- **Body**: 12px, `var(--text)`, line-height 1.5
- **Label**: 9–10px, uppercase, letter-spacing 1px, `var(--text-secondary)`
- **Metric value**: 12–14px, `var(--accent-bright)`, tabular-nums
- **Status (transient)**: 11px, lowercase, letter-spacing 0.1em, `var(--text-secondary)`

### Shape language

- **Border-radius: max 4px.** Usually `2px`. Sharp, geometric, never pill-shaped.
- **Borders**: 1px hairlines in `var(--border)`. On focus, border goes to `var(--accent)`.
- **Protection**: panels use backdrop blur — never a solid colored surface over the orb.
- **No drop shadows.** Instead, **glow shadows** in the accent color:
  - `--glow:        0 0 8px #4ca8e8aa` (subtle — interactive hover)
  - `--glow-strong: 0 0 20px #4ca8e8cc, 0 0 40px #4ca8e844` (the orb, primary CTAs)

### Backgrounds & layering

- Root background is `var(--bg)` — the orb is the hero, it sits on pure darkness.
- Panels float via `background: rgba(13,13,20,0.75)` + `backdrop-filter: blur(12px)` + 1px border. Translucent so the orb glow bleeds through.
- **Optional sci-fi layers** (the "bling-bling" push): thin horizontal scanlines over panels, animated corner brackets around focused panels, a faint grid underlay, holographic rings around the orb. See `preview/06-hud-embellishments.html`.
- No gradients on surfaces. Gradients *only* appear as radial glows inside the orb and around the push-to-talk button.

### Motion

- **Crossfades**: 200–300ms, opacity only, ease default.
- **Glow pulses**: 1.4s infinite (orb), 0.9s infinite (active indicator).
- **Data-stream sweeps**: 2–4s linear, looping — used on scanlines and ring accents.
- **Entrance**: panels and overlay text slide in 8px on Y + fade, 200ms ease-out.
- **No bounces. No springy easing.** Sci-fi motion is *machined*, not playful.
- **Hover**: border → `var(--accent)`, box-shadow → `var(--glow)`. No scale, no translate.
- **Press**: shift text to `var(--accent-bright)`. No shrink.

### Iconography

See the [Iconography](#iconography) section below.

### Layout rules

- Fullscreen root (`100vw × 100vh`), `position: fixed; overflow: hidden`. The app does not scroll.
- The **orb canvas** is `z: 0`, fullscreen, unclickable.
- **Floating panels** are `z: 10`. They snap to a 4-quadrant slot grid and can be maximized into free-floating drag-resize windows.
- **Top bar** is `z: 30`: left cluster = clock/date/weather (`HudInfoBar`), right cluster = reset-layout / settings / idle toggle.
- **Bottom center** is `z: 20`: current orb status (`listening…`) + `JARVIS` mark.
- **Settings overlay** is `z: 50`.

---

## Iconography

- **All icons are inline SVG** with `stroke: currentColor`, `stroke-width: 1.75–2`, `fill: none`, 12–14px square. Rounded caps/joins. Geometric — pulled from the **Feather / Lucide** lineage.
- **No icon font.** No emoji in the chrome (weather glyphs are the only exception, and they're Unicode symbols, not colored emoji).
- **Brand mark**: the favicon — a radial blue glow with a white-hot core. See `assets/favicon.svg`. There is no wordmark beyond the letter-spaced `JARVIS` text.
- **Reusable glyphs** shipped in `assets/icons/`:
  - `power.svg`, `mic.svg`, `mic-mute.svg`, `settings.svg`, `reset.svg`, `play.svg`, `pause.svg`, `prev.svg`, `next.svg`, `maximize.svg`, `minimize.svg`, `close.svg`, `cpu.svg`, `ram.svg`, `network.svg`, `volume.svg`, `check.svg`, `warning.svg`, `bolt.svg`, `orb-ring.svg`, `crosshair.svg`, `bracket-corner.svg`, `scanline.svg`, `waveform.svg`.
- **Where icons are taken**: The live codebase inlines SVGs inside components (e.g. the mic and settings icons in `HudTopBar.tsx`). In this kit they're extracted into standalone files plus a `lucide` CDN link for anything new.

---

## Font Substitution — ⚠️ Flag

The repo references `'JetBrains Mono'` by name but does **not** ship the font files. This kit pulls JetBrains Mono from Google Fonts (same family, OFL). Visual match is 1:1 since JetBrains ships the same binaries on GF.

👉 **Ask:** If you have a preferred self-hosted copy of JetBrains Mono (specific subset, hinting tweaks, licensed variant), drop the `.woff2` files into `fonts/` and remove the `<link rel="preconnect">` block from the kit's `index.html`.
