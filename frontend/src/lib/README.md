# JARVIS Component Library

Self-contained Tailwind v4 primitive + composition set. Requires `frontend/src/styles/tokens.css` loaded globally.

## Import

```ts
import { Button, Panel, type ButtonProps } from '../lib';
// or, with path alias configured:
import { Button } from '@/lib';
```

## Primitives

| Component        | Description                                                     |
| ---------------- | --------------------------------------------------------------- |
| `Button`         | variants: primary / secondary / ghost / danger; sizes: sm / md  |
| `Pill`           | variants: default / ok / warn / err / info                      |
| `Label`          | 9px uppercase small-caps label; `dim` prop for muted color      |
| `Metric`         | 14px tabular-nums value + optional unit; `warn` for amber       |
| `Mono`           | Monospace text wrapper with size variants xs/sm/md/lg           |
| `ProgressBar`    | 2–4 px bar; value 0–1; variants accent / bright / warn          |
| `Sparkline`      | SVG sparkline; data: number[]; variants accent / warn           |
| `Panel`          | Glass shell with header slot + body slot; focused/hovered state |
| `TopBar`         | Fixed-top glass header; children slot                           |
| `CornerBrackets` | 4 absolute-positioned accent L-shapes; focused prop             |
| `Scanlines`      | Horizontal scanline overlay with optional data-sweep shimmer    |
| `GridBackground` | Fixed cyan grid underlay with radial mask; optional drift       |
| `GlowFrame`      | Box-shadow glow wrapper; breathe prop for animation             |
| `Reticle`        | Tiny crosshair glyph                                            |
| `Icon`           | lucide-react wrapper; stroke-width 1.75; sizes sm/md/lg         |
| `BrandMark`      | `J A R V I S` tracked text + optional MK XLII sub               |

## Compositions

| Component     | Description                                |
| ------------- | ------------------------------------------ |
| `GlassCard`   | Panel + CornerBrackets + accent dot header |
| `StatusBadge` | Pulsing dot + label (● LINK · SECURE)      |

## Showcase

Dev URL: `http://localhost:5173/lib-showcase.html`

Prod build entry: `frontend/lib-showcase.html` → `showcase` rollup input.
