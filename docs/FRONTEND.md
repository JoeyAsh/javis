# JARVIS — Frontend

React 18 + TypeScript (strict) + Vite + Tailwind CSS + Three.js. Single-page app with a fullscreen particle orb and floating HUD window system. Communicates with the Python backend via WebSocket.

---

## Architecture

The frontend follows a layered feature-folder structure. Every layer has a barrel file and a path alias.

```
frontend/src/
  App.tsx                 Root — 19 LOC, mounts AppProviders + AppShell
  app/                    (@app) Application shell: providers, routing, panel registry
    providers/            StoreProvider, WebSocketProvider, PanelAvailabilityProvider
    shell/                AppShell, TopBar, Dock, OrbStage, WindowHost
    store.ts              Redux store
    panels.ts             Panel registry (PanelSpec list)
  features/               (@features/*) One folder per domain feature
    agenda/               Calendar / Agenda
    conversation/         Follow-up mode + push-to-talk
    dev/                  GitHub CI, PRs, issues, Docker, local repos
    gitlab/               GitLab MRs, issues, pipelines
    lights/               Home Assistant lighting zones
    log/                  Backend log stream + turn timing
    mail/                 Gmail integration
    notifications/        HUD notification queue
    nowplaying/           Spotify now-playing
    orbState/             Orb state machine (idle/listening/thinking/speaking/working)
    selffix/              OpenClaw self-fix audit trail
    settings/             App settings (opacity, orb style, push-to-talk, etc.)
    system/               CPU / RAM / GPU / temp metrics
    transcript/           Conversation transcript
  core/                   (@core/*) Cross-cutting infrastructure
    api/                  RTK Query base + REST endpoints (locationApi, weatherApi, githubApi)
    audio/                Web Audio engine, SfxContext, useAudioEngine, useAudioAnalyser
    storage/              localStorage persistence helpers
    tauri/                Tauri IPC bridge (window events, native SFX)
    websocket/            wsClient singleton, WS message types, commands
  ui/                     (@ui) Design-system component library — see src/ui/README.md
    primitives/           Atomic stateless display components
    compositions/         Multi-primitive compositions (HUDShell, WindowManager, StatusDock…)
    orb/                  CssOrb + ThreeOrb (lazy-loaded)
    window/               Window / drag / resize system + slot grid
    showcase/             Dev-only component gallery (separate Vite entry)
  common/                 (@common/*) Shared types, hooks, utils
    types/                OrbState, AppOrbState, PanelId, PanelMode, SlotId, LocationCoords
    hooks/                useLocation, useMockTicker
    utils/                cx(), time helpers
  test/                   (@test/*) Vitest helpers (renderWithProviders, mockWsClient)
  styles/tokens.css       CSS design tokens (imported by index.css)
  index.css               Global styles + CSS variables
```

---

## Path Aliases

| Alias | Resolves to |
|---|---|
| `@app` | `src/app/index.ts` |
| `@app/*` | `src/app/*` |
| `@features/*` | `src/features/*` |
| `@core/*` | `src/core/*` |
| `@ui` | `src/ui/index.ts` |
| `@ui/*` | `src/ui/*` |
| `@common/*` | `src/common/*` |
| `@test/*` | `src/test/*` |

---

## Feature Folder Shape

```
features/<name>/
  index.ts                Public barrel — re-exports hook + types
  types.ts                All TypeScript types for this feature (interfaces defined here)
  <name>Slice.ts          Redux slice
  <name>Api.ts            RTK Query endpoint (WS subscription)
  hooks/
    use<Name>.ts           Main feature hook
    use<Name>.types.ts     Hook return type
  components/
    <Component>/
      <Component>.tsx
      <Component>.types.ts
      <Component>.module.css   (only when Tailwind is insufficient)
      index.ts
      __tests__/
        <Component>.test.tsx
```

Rules:
- `types.ts` at feature root is the canonical home for all feature types. No types in `.tsx` or hook `.ts` files.
- Slices and API files import from `./types` (relative). Components import from `../../types` (2 up from component dir = feature root).
- Consumers outside the feature import via `@features/<name>/types` or via the public `index.ts` barrel.

---

## WebSocket

`core/websocket/wsClient.ts` owns the singleton WS connection. The full typed message union lives in `core/websocket/types.ts` (imported from feature `types.ts` files). RTK Query endpoints subscribe to specific message types via `wsClient.subscribe(type, handler)`.

No component or hook calls `new WebSocket()` directly — that is strictly `wsClient`'s concern.

---

## State Management

Redux Toolkit with RTK Query. Each feature has a slice + an API file that injects endpoints into the base API.

```typescript
// Pattern: feature API subscribes to WS, dispatches slice actions
const unsub = wsClient.subscribe<{ payload: SomePayload }>('some_type', (msg) =>
  dispatch(someActionReceived(msg.payload))
);
```

---

## UI Library (@ui)

See `src/ui/README.md` for full details. Key rule: **only import via `@ui`** — never from sub-paths like `@ui/primitives/Panel`.

---

## Design System

See `docs/DESIGN.md` for the full token reference and brand signature documentation.

```css
:root {
  --bg:            #050508;
  --surface:       #0d0d14;
  --surface-raised:#12121c;
  --border:        #1a1a2e;
  --accent:        #4ca8e8;   /* orb idle */
  --accent-bright: #6ec4ff;   /* orb thinking */
  --accent-speak:  #5ab8f0;   /* orb speaking */
  --text:          #e8f4ff;
  --text-secondary:#6b8fa8;
  --text-muted:    #2a3d4f;
  --glow:          0 0 8px #4ca8e8aa;
  --glow-strong:   0 0 20px #4ca8e8cc, 0 0 40px #4ca8e844;
  --font:          'JetBrains Mono', monospace;
}
```

**Non-negotiable rules:**
- No `border-radius` > 4 px. Sharp HUD aesthetic.
- JetBrains Mono only (`var(--font)`).
- All colors via CSS variables. Never hardcode hex in components.
- Tailwind for layout/spacing. CSS variables for color/shadow/font.
- CSS Modules only for keyframes, blend-modes, complex gradients.

---

## Orb States

| State | Visual |
|---|---|
| `idle` | `--accent` steady |
| `listening` | `--accent` + pulse ring |
| `thinking` | `--accent-bright` + spin |
| `speaking` | `--accent-speak` + wave |
| `working` | amber overlay + `is-working` class on root |
| `follow_up` | muted pulse + countdown ring |

The Three.js orb engine lives at `src/ui/orb/ThreeOrb/`. Never modify the engine file. Interact only via `orb.setState()`, `orb.setAnalyser()`, `orb.destroy()`.

---

## Asset Pipeline

Sound files are not committed. They are copied at dev/build time from `assets/sounds/` → `frontend/public/sounds/` via `scripts/copy-sounds.mjs`. Run `npm run predev` manually if sounds are missing.

---

## Build Targets

- main chunk: ~85 kB gzip (hard cap 90 kB)
- ThreeOrb chunk: ~511 kB (lazy-loaded via `React.lazy`)
- Showcase: separate Vite entry (`lib-showcase.html`)

---

## Vite Dev Proxy

```typescript
'/jarvis-ws' → ws://localhost:8765   (WS)
'/voices'    → http://localhost:8766
'/api'       → http://localhost:8766
```
