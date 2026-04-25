---
description: "Full frontend migration: rewrite all views to use only src/lib components. Delete all legacy code in src/components/."
---

# Frontend Migration — Legacy → src/lib Component Library

You are performing a **complete frontend rewrite** of the JARVIS voice assistant UI.
The goal: every UI element comes from `src/lib`. The `src/components/` directory and
all legacy code in `App.tsx` are replaced and ultimately deleted.

## Current Architecture

### src/lib/ (KEEP — single source of truth)
The canonical component library. Contains all primitives, compositions, hooks, and audio infra:

**Primitives:** Button, Label, Metric, Mono, Pill, Icon, Panel, TopBar, ProgressBar,
Sparkline, CornerBrackets, Scanlines, GridBackground, GlowFrame, Reticle, BrandMark,
LightTrace, PanelBloom, PanelRails, ViewportCorners, StarField, Reactor, Scene, Orb,
PushToTalkButton, WaveformMeter, WaveStrip, StatusLabel, Hint, Window, SnapOverlay,
SwapOverlay, SlotGhost, StateSimulator, Tweaks

**Compositions:** GlassCard, StatusBadge, StatusDock, HUDShell, WindowManager

**Layout:** SlotGrid (computeSlot, computeAllSlots, slotAtPoint, SLOT_IDS, etc.)

**Hooks:** useDraggable, useSlotDrag, useResizable

**Audio:** SfxProvider, useAudioEngine, useTauriWindowSfx, AudioEngine, useClickSfx, useHoverSfx

Barrel export: `import { X } from './lib'`

### src/components/ (LEGACY — to be deleted)
Old code that duplicates or wraps lib components with inconsistent patterns:

**HUD chrome (replace with lib equivalents):**
- `hud/HudWindows.tsx` → replace with lib `WindowManager` + `Window`
- `hud/Window.tsx` → replace with lib `Window`
- `hud/WindowManager.tsx` → replace with lib `WindowManager`
- `hud/SlotGrid.ts` → replace with lib `SlotGrid`
- `hud/SnapOverlay.tsx` → replace with lib `SnapOverlay`
- `hud/SwapOverlay.tsx` → replace with lib `SwapOverlay`
- `hud/Scene.tsx` → replace with lib `Scene`
- `hud/PanelAvailability.tsx` → evaluate: context provider, may need to keep or migrate
- `hud/primitives/*` (HudButton, HudPanel, HudBloom, HudCornerBrackets, HudDivider,
  HudIconButton, HudLightTrace, HudList, HudStatusBadge, HudViewportCorners)
  → replace with lib Button, Panel, PanelBloom, CornerBrackets, LightTrace, StatusBadge, ViewportCorners

**Top-level components (replace with lib equivalents):**
- `HudTopBar.tsx` → replace with lib `TopBar`
- `HudHint.tsx` → replace with lib `Hint`
- `Dock.tsx` → replace with lib `StatusDock` + `PushToTalkButton` + `WaveformMeter` + `StatusLabel` + `BrandMark`
- `AudioMuteToggle.tsx` → inline into TopBar using lib `Button` + `Icon`
- `SettingsOverlay.tsx` → rewrite using lib `Panel` + `GlassCard` + `Button`

**Panels (rewrite internals to use lib primitives):**
- `panels/System/SystemPanel.tsx` → rewrite using lib `Panel`, `Metric`, `Sparkline`, `ProgressBar`
- `panels/Transcript/TranscriptPanel.tsx` → rewrite using lib `Panel`, `Label`, `Mono`
- `panels/Agenda/AgendaPanel.tsx` → rewrite using lib `Panel`, `Label`, `Pill`
- `panels/NowPlaying/NowPlayingPanel.tsx` → rewrite using lib `Panel`, `Label`, `ProgressBar`
- `panels/Mail/MailPanel.tsx` → rewrite using lib `Panel`, `Label`, `Pill`
- `panels/Dev/DevPanel.tsx` → rewrite using lib `Panel`, `Mono`, `Label`
- `panels/Log/LogPanel.tsx` → rewrite using lib `Panel`, `Mono`
- `panels/GitLab/GitLabPanel.tsx` → rewrite using lib `Panel`, `Label`, `StatusBadge`
- `panels/Lights/LightsPanel.tsx` → rewrite using lib `Panel`, `Button`, `Label`
- `panels/Notifications/NotificationsPanel.tsx` → rewrite using lib `Panel`, `Label`, `Pill`
- `panels/SelfFixPanel.tsx` → rewrite using lib `Panel`, `Mono`, `Button`

### src/hooks/ (KEEP — business logic hooks)
These are data/logic hooks, not UI. Keep them all:
useWebSocket, useAudioAnalyser, useMicStream, useConversationMode, useSettings,
useLocation, useSystemMetrics, useTranscripts, useLogStream, useGitHubState,
useGitlabState, useNotifications, usePushToTalk, useSwapDrag, useTurnTimings

Note: `useDraggable.ts` and `useResizable.ts` in src/hooks/ are legacy duplicates
of lib versions — delete them after migration.

### src/App.tsx (REWRITE)
Current state mixes legacy and lib imports. Rewrite to use only lib exports.
Keep all hook wiring intact. Remove dead state variables and placeholder JSX.

## Migration Order

### Phase 1: App shell
1. **App.tsx** — rewrite. Remove all `src/components/` imports. Use lib `HUDShell`
   as the root layout, lib `Scene` + `Reactor` for background, lib `Orb` for the orb,
   lib `TopBar` for the header, lib `StatusDock` for the bottom dock, lib `Hint` for
   the keyboard hint, lib `ViewportCorners` for the corner brackets. Keep all hooks.

### Phase 2: Window management
2. **WindowManager wiring** — use lib `WindowManager` composition directly.
   Migrate `PanelAvailability` context if needed or replace with lib's built-in slot system.

### Phase 3: Panel content
3. **SystemPanel** → new file `src/views/SystemView.tsx` using lib primitives
4. **TranscriptPanel** → `src/views/TranscriptView.tsx`
5. **AgendaPanel** → `src/views/AgendaView.tsx`
6. **NowPlayingPanel** → `src/views/NowPlayingView.tsx`
7. **MailPanel** → `src/views/MailView.tsx`
8. **DevPanel** → `src/views/DevView.tsx`
9. **LogPanel** → `src/views/LogView.tsx`
10. **GitLabPanel** → `src/views/GitLabView.tsx`
11. **LightsPanel** → `src/views/LightsView.tsx`
12. **NotificationsPanel** → `src/views/NotificationsView.tsx`

### Phase 4: Overlays
13. **SettingsOverlay** → `src/views/SettingsView.tsx` using lib `GlassCard` + `Panel`

### Phase 5: Cleanup
14. Delete entire `src/components/` directory
15. Delete duplicate hooks from `src/hooks/` (useDraggable, useResizable)
16. Update `src/components/index.ts` barrel → remove or redirect to new views
17. Verify no remaining imports from `src/components/` anywhere

## New File Structure (after migration)
```
frontend/src/
  App.tsx                    # Root — only lib imports + hooks
  views/                     # Panel/overlay content (new directory)
    SystemView.tsx
    TranscriptView.tsx
    AgendaView.tsx
    NowPlayingView.tsx
    MailView.tsx
    DevView.tsx
    LogView.tsx
    GitLabView.tsx
    LightsView.tsx
    NotificationsView.tsx
    SettingsView.tsx
  hooks/                     # Business logic hooks (unchanged)
    useWebSocket.ts
    useAudioAnalyser.ts
    ...
  lib/                       # Component library (DO NOT MODIFY)
    primitives/
    compositions/
    hooks/
    audio/
    layout/
    index.ts
  types.ts                   # Shared types (keep)
  index.css                  # Global styles (keep)
```

## Rules
- **Only import UI from `src/lib`** — barrel: `import { X } from './lib'`
- **Never modify anything in `src/lib/`** — it's the stable design system
- **Keep all business logic hooks** from `src/hooks/` — they wire data, not UI
- **Strict TypeScript** — no `any`, no `!`, explicit interfaces for all props
- **CSS variables for color** — no hardcoded hex. Tailwind for layout only.
- **JetBrains Mono** font. `border-radius` ≤ 4px.
- **Named + default export** on every component
- **Preserve all runtime behavior** — WS, mic, audio, orb state, SFX, settings

