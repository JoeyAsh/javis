// ================================================================
// JARVIS Component Library — barrel exports
// Usage: import { Button, Panel, type ButtonProps } from '@/lib'
//        or   import { Button } from '../lib'
// ================================================================

// Import all keyframes so any consumer of the lib gets them automatically
import './lib.css';

// Primitives
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
export type {
    ProgressBarProps,
    ProgressBarVariant,
    ProgressBarHeight,
} from './primitives/ProgressBar';

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

// Chrome primitives
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

// Orb primitive
export { Orb } from './primitives/Orb/Orb';
export type { OrbProps, OrbState } from './primitives/Orb/Orb';

// Interactive chrome primitives
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

// Dev overlay primitives
export { StateSimulator } from './primitives/StateSimulator';
export type { StateSimulatorProps } from './primitives/StateSimulator';

export { Tweaks, TWEAKS_DEFAULTS, useTweakApply } from './primitives/Tweaks';
export type { TweaksProps, TweaksState } from './primitives/Tweaks';

// Layout
export {
    computeSlot,
    computeAllSlots,
    slotAtPoint,
    SLOT_IDS,
    TOP_BAR_HEIGHT,
    SLOT_MARGIN,
    COLUMN_WIDTH,
    BOTTOM_STRIP_HEIGHT,
} from './layout/SlotGrid';
export type { SlotId, SlotRect } from './layout/SlotGrid';

// Hooks
export { useDraggable } from './hooks/useDraggable';
export type { DragState, UseDraggableOptions } from './hooks/useDraggable';

export { useSlotDrag } from './hooks/useSlotDrag';
export type { SlotDragState, UseSlotDragOptions, WindowId } from './hooks/useSlotDrag';

export { useResizable } from './hooks/useResizable';
export type { ResizeDir, ResizeState, UseResizableOptions } from './hooks/useResizable';

// Window primitives
export { Window } from './primitives/Window';
export type {
    WindowProps,
    WindowState,
    PanelMode,
    PanelContentRenderProps,
} from './primitives/Window';

export { SnapOverlay } from './primitives/SnapOverlay';
export type { SnapOverlayProps } from './primitives/SnapOverlay';

export { SwapOverlay } from './primitives/SwapOverlay';
export type { SwapOverlayProps } from './primitives/SwapOverlay';

export { SlotGhost } from './primitives/SlotGhost';
export type { SlotGhostProps } from './primitives/SlotGhost';

// Audio infrastructure
export { SfxProvider, useSfx, SfxContext } from './audio/SfxContext';
export type { SfxContextValue, SfxProviderProps } from './audio/SfxContext';
export { useAudioEngine } from './audio/useAudioEngine';
export type { UseAudioEngineReturn } from './audio/useAudioEngine';
export { useTauriWindowSfx } from './audio/useTauriWindowSfx';
export { AudioEngine } from './audio/audioEngine';
export { SFX_CONFIG, DUCK_VOLUME, DUCK_RAMP_MS } from './audio/config';
export type { SfxEvent, SfxEntry } from './audio/config';
export { useClickSfx, useHoverSfx } from './audio/hooks';
export type { HoverSfxTarget, UseHoverSfxOptions } from './audio/hooks';

// Compositions
export { GlassCard } from './compositions/GlassCard';
export type { GlassCardProps } from './compositions/GlassCard';

export { StatusBadge } from './compositions/StatusBadge';
export type { StatusBadgeProps, StatusBadgeState } from './compositions/StatusBadge';

export { StatusDock } from './compositions/StatusDock';
export type { StatusDockProps } from './compositions/StatusDock';

export { HUDShell } from './compositions/HUDShell';
export type { HUDShellProps } from './compositions/HUDShell';

export { WindowManager } from './compositions/WindowManager';
export type {
    ManagedWindow,
    WindowManagerProps,
    ExpandedRect,
} from './compositions/WindowManager';
