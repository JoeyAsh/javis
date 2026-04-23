# @ui — JARVIS UI Library

Headless, design-system-native component primitives and compositions consumed by the app layer.

## Structure

```
src/ui/
├── index.ts            # Single barrel — import everything from '@ui'
├── ui.css              # Global design-token overrides (loaded once by App)
├── primitives/         # Atomic, stateless display components
├── compositions/       # Multi-primitive components (HUDShell, WindowManager, StatusDock…)
├── orb/                # CssOrb + ThreeOrb (lazy-loaded via React.lazy)
├── window/             # Window/drag/resize system + slot grid
└── showcase/           # Dev-only component gallery (separate Vite entry)
```

## Barrel layout

All public exports surface via `src/ui/index.ts`. Consumers import from the `@ui` path alias only:

```ts
// Correct
import { Panel, Pill, StatusLabel } from '@ui';

// Wrong — never import from sub-paths directly
import { Panel } from '@ui/primitives/Panel';
```

The only exception is `@ui/window/*` when window hooks are needed inside the window subsystem itself.

## Rules

- **One component per file.** Each primitive lives in its own folder with a `.types.ts` sibling.
- **No inline styles for color or font.** Use CSS variables from `src/index.css`.
- **CSS Modules only for keyframes / blend-modes / multi-layer backdrop-filter.** Everything else is Tailwind utility classes.
- **No `border-radius` above 4 px.** Sharp HUD aesthetic.
- **All colors via `var(--token)`.** Never hardcode hex values.
- **JetBrains Mono only.** `font-family: var(--font)`.

## Adding a new primitive

1. Create `src/ui/primitives/MyThing/MyThing.tsx` + `MyThing.types.ts` + `index.ts`.
2. Export from `src/ui/index.ts`.
3. Add tests at `MyThing/__tests__/MyThing.test.tsx`.
4. Justify any `.module.css` file with a comment explaining why Tailwind alone is insufficient.

See `docs/FRONTEND.md` for the full architecture and path-alias reference.
