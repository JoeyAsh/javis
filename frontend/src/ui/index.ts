// ================================================================
// JARVIS UI Library — barrel exports
// Usage: import { Button, Panel, type ButtonProps } from '@ui'
// ================================================================

// Import keyframes and shared CSS so any consumer gets them
import './ui.css';
// Import all component stylesheets (BEM global classes) — aggregated here
// so individual component files don't need `import './Foo.css'`.
import './components.css';

// ── Primitives ────────────────────────────────────────────────────────────────

export { Button } from './primitives/Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './primitives/Button';

export { Pill } from './primitives/Pill';
export type { PillProps, PillVariant } from './primitives/Pill';

export { Label } from './primitives/Label';
export type { LabelProps } from './primitives/Label';

export { Metric } from './primitives/Metric';
export type { MetricProps } from './primitives/Metric';

export { Mono } from './primitives/Mono';
export type { MonoProps, MonoSize } from './primitives/Mono';

export { ProgressBar } from './primitives/ProgressBar';
export type { ProgressBarProps, ProgressBarVariant, ProgressBarHeight } from './primitives/ProgressBar';

export { Sparkline } from './primitives/Sparkline';
export type { SparklineProps, SparklineVariant } from './primitives/Sparkline';

export { Panel } from './primitives/Panel';
export type { PanelProps } from './primitives/Panel';

export { TopBar } from './primitives/TopBar';
export type { TopBarProps } from './primitives/TopBar';

export { CornerBrackets } from './primitives/CornerBrackets';
export type { CornerBracketsProps } from './primitives/CornerBrackets';

export { Scanlines } from './primitives/Scanlines';
export type { ScanlinesProps } from './primitives/Scanlines';

export { GridBackground } from './primitives/GridBackground';
export type { GridBackgroundProps } from './primitives/GridBackground';

export { GlowFrame } from './primitives/GlowFrame';
export type { GlowFrameProps } from './primitives/GlowFrame';

export { Reticle } from './primitives/Reticle';
export type { ReticleProps } from './primitives/Reticle';

export { Icon } from './primitives/Icon';
export type { IconProps, IconSize } from './primitives/Icon';

export { BrandMark } from './primitives/BrandMark';
export type { BrandMarkProps } from './primitives/BrandMark';

export { LightTrace } from './primitives/LightTrace';
export type { LightTraceProps } from './primitives/LightTrace';

export { PanelBloom } from './primitives/PanelBloom';
export type { PanelBloomProps } from './primitives/PanelBloom';

export { PanelRails } from './primitives/PanelRails';
export type { PanelRailsProps } from './primitives/PanelRails';

export { ViewportCorners } from './primitives/ViewportCorners';
export type { ViewportCornersProps } from './primitives/ViewportCorners';

export { StarField } from './primitives/StarField';
export type { StarFieldProps } from './primitives/StarField';

export { Reactor } from './primitives/Reactor';
export type { ReactorProps } from './primitives/Reactor';

export { Scene } from './primitives/Scene';
export type { SceneProps } from './primitives/Scene';

export { PushToTalkButton } from './primitives/PushToTalkButton';
export type { PushToTalkButtonProps } from './primitives/PushToTalkButton';

export { WaveformMeter } from './primitives/WaveformMeter';
export type { WaveformMeterProps } from './primitives/WaveformMeter';

export { WaveStrip } from './primitives/WaveStrip';
export type { WaveStripProps } from './primitives/WaveStrip';

export { StatusLabel } from './primitives/StatusLabel';
export type { StatusLabelProps } from './primitives/StatusLabel';

export { Hint } from './primitives/Hint';
export type { HintProps, HintKeyProps } from './primitives/Hint';

export { StateSimulator } from './primitives/StateSimulator';
export type { StateSimulatorProps } from './primitives/StateSimulator';

export { Tweaks, TWEAKS_DEFAULTS, useTweakApply } from './primitives/Tweaks';
export type { TweaksProps, TweaksState } from './primitives/Tweaks';

// ── Orb ───────────────────────────────────────────────────────────────────────
// Only CssOrb is included here — it is a tiny, synchronous CSS-only primitive
// safe for the main bundle. ThreeOrb, createOrb, and OrbEngine are intentionally
// omitted: consumers that need them must import from '@ui/orb' directly so
// the Three.js payload stays in its own lazy chunk.

export { CssOrb } from './orb/CssOrb';
export type { CssOrbProps } from './orb/CssOrb';

// ── Window subsystem ─────────────────────────────────────────────────────────

export { Window } from './window/Window';
export type { WindowProps, WindowState, PanelMode, PanelContentRenderProps } from './window/Window';

export { SnapOverlay } from './window/SnapOverlay';
export type { SnapOverlayProps } from './window/SnapOverlay';

export { SwapOverlay } from './window/SwapOverlay';
export type { SwapOverlayProps } from './window/SwapOverlay';

export { SlotGhost } from './window/SlotGhost';
export type { SlotGhostProps } from './window/SlotGhost';

export {
    computeSlot,
    computeAllSlots,
    slotAtPoint,
    SLOT_IDS,
    TOP_BAR_HEIGHT,
    SLOT_MARGIN,
    COLUMN_WIDTH,
    BOTTOM_STRIP_HEIGHT,
} from './window/slotGrid';
export type { SlotId, SlotRect } from './window/slotGrid';

export { useDraggable } from './window/hooks/useDraggable';
export type { DragState, UseDraggableOptions } from './window/hooks/useDraggable';

export { useSlotDrag } from './window/hooks/useSlotDrag';
export type { SlotDragState, UseSlotDragOptions, WindowId } from './window/hooks/useSlotDrag';

export { useResizable } from './window/hooks/useResizable';
export type { ResizeDir, ResizeState, UseResizableOptions } from './window/hooks/useResizable';

// ── Compositions ─────────────────────────────────────────────────────────────

export { GlassCard } from './compositions/GlassCard';
export type { GlassCardProps } from './compositions/GlassCard';

export { StatusBadge } from './compositions/StatusBadge';
export type { StatusBadgeProps, StatusBadgeState } from './compositions/StatusBadge';

export { StatusDock } from './compositions/StatusDock';
export type { StatusDockProps } from './compositions/StatusDock';

export { HUDShell } from './compositions/HUDShell';
export type { HUDShellProps } from './compositions/HUDShell';

export { WindowManager } from './compositions/WindowManager';
export type { ManagedWindow, WindowManagerProps, ExpandedRect } from './compositions/WindowManager';
