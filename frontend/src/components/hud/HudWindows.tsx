import { useCallback, useMemo, useRef, useState } from 'react';
import type {
  CSSProperties,
  PointerEvent as ReactPointerEvent,
  ReactElement,
  ReactNode,
} from 'react';
import { Window } from './Window';
import { SnapOverlay } from './SnapOverlay';
import { SwapOverlay } from './SwapOverlay';
import { useWindowManager } from './WindowManager';
import { useAvailabilityMap, isPanelAvailable } from './PanelAvailability';
import type { AppOrbState, PanelId, PanelMode } from '../../types';
import type { SlotId } from './SlotGrid';
import {
  AgendaPanel,
  DevPanel,
  GitLabPanel,
  LogPanel,
  MailPanel,
  NotificationsPanel,
  NowPlayingPanel,
  SelfFixPanel,
  SystemPanel,
  TranscriptPanel,
} from '../panels';

export interface HudWindowsProps {
  idle: boolean;
  paused?: boolean;
  orbState?: AppOrbState;
}

interface WindowSpec {
  id: PanelId;
  title: string;
  icon: ReactNode;
  render: (mode: PanelMode, paused: boolean) => ReactNode;
}

const Dot = (): ReactElement => (
  <span
    aria-hidden
    style={{
      display: 'inline-block',
      width: 6,
      height: 6,
      background: 'var(--accent)',
      borderRadius: '50%',
    }}
  />
);

const WINDOWS: ReadonlyArray<WindowSpec> = [
  {
    id: 'agenda',
    title: 'Agenda',
    icon: <Dot />,
    render: (mode) => <AgendaPanel mode={mode} />,
  },
  {
    id: 'mail',
    title: 'Inbox',
    icon: <Dot />,
    render: (mode) => <MailPanel mode={mode} />,
  },
  {
    id: 'notifications',
    title: 'Proactive',
    icon: <Dot />,
    render: (mode, paused) => <NotificationsPanel mode={mode} paused={paused} />,
  },
  {
    id: 'transcript',
    title: 'Transcript',
    icon: <Dot />,
    render: (mode) => <TranscriptPanel mode={mode} />,
    // NOTE: orbState is threaded in at render time below; see WINDOWS.map
  },
  {
    id: 'nowplaying',
    title: 'Now Playing',
    icon: <Dot />,
    render: (mode) => <NowPlayingPanel mode={mode} />,
  },
  {
    id: 'system',
    title: 'System',
    icon: <Dot />,
    render: (mode, paused) => <SystemPanel mode={mode} paused={paused} />,
  },
  {
    id: 'dev',
    title: 'Dev Toolkit',
    icon: <Dot />,
    render: (mode) => <DevPanel mode={mode} />,
  },
  {
    id: 'selffix',
    title: 'Self-Fix',
    icon: <Dot />,
    render: (mode) => <SelfFixPanel mode={mode} />,
  },
  {
    id: 'gitlab',
    title: 'GitLab',
    icon: <Dot />,
    render: (mode) => <GitLabPanel mode={mode} />,
  },
  {
    id: 'log',
    title: 'Console',
    icon: <Dot />,
    render: (mode) => <LogPanel mode={mode} />,
  },
];

const TITLE_BY_PANEL: Record<PanelId, string> = (() => {
  const out = {} as Record<PanelId, string>;
  for (const spec of WINDOWS) out[spec.id] = spec.title;
  return out;
})();

interface SwapState {
  sourceId: PanelId;
  sourceSlotId: SlotId;
  cursor: { x: number; y: number };
  hoveredSlotId: SlotId | null;
}

export function HudWindows({ idle, paused = false, orbState = 'idle' }: HudWindowsProps): ReactElement {
  const effectivePaused = paused || idle;
  const { windows, slotRects, clearFocus, minimize, swapSlots } = useWindowManager();
  const availabilityMap = useAvailabilityMap();

  // Live swap state lives at the HUD root so both overlay and ghost cards can
  // observe it without prop-drilling into every Window.
  const [swap, setSwap] = useState<SwapState | null>(null);
  // Capture the pointer origin on source pointerdown so the drag preview can
  // render with a stable offset (cursor-anchored, not snapping to top-left).
  const swapStartOffsetRef = useRef<{ dx: number; dy: number } | null>(null);

  // Inverse map (slotId -> panelId). Re-derived every render; 9 items, cheap.
  const residentBySlot = useMemo<Partial<Record<SlotId, PanelId>>>(() => {
    const out: Partial<Record<SlotId, PanelId>> = {};
    for (const spec of WINDOWS) {
      out[windows[spec.id].homeSlotId] = spec.id;
    }
    return out;
  }, [windows]);

  // Clicking empty HUD space clears focus. Guard on `target === currentTarget`
  // so bubbled events from children don't clear focus unexpectedly.
  const onRootPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>): void => {
      if (e.target === e.currentTarget) {
        clearFocus();
      }
    },
    [clearFocus],
  );

  // ===== Swap-drag orchestration =====
  const handleSwapStart = useCallback(
    (id: PanelId): void => {
      const w = windows[id];
      const rect = slotRects[w.homeSlotId];
      // Default offset: centered horizontally, 14 px from top so the header
      // tracks the cursor naturally. If no pointer origin stored, use this.
      swapStartOffsetRef.current = { dx: rect.w / 2, dy: 14 };
      setSwap({
        sourceId: id,
        sourceSlotId: w.homeSlotId,
        cursor: { x: rect.x + rect.w / 2, y: rect.y + 14 },
        hoveredSlotId: null,
      });
    },
    [slotRects, windows],
  );

  const handleSwapMove = useCallback(
    (clientX: number, clientY: number): void => {
      setSwap((prev) => {
        if (!prev) return prev;
        let hovered: SlotId | null = null;
        for (const slotId of Object.keys(slotRects) as SlotId[]) {
          const r = slotRects[slotId];
          if (
            clientX >= r.x &&
            clientX <= r.x + r.w &&
            clientY >= r.y &&
            clientY <= r.y + r.h
          ) {
            hovered = slotId;
            break;
          }
        }
        return {
          ...prev,
          cursor: { x: clientX, y: clientY },
          hoveredSlotId: hovered,
        };
      });
    },
    [slotRects],
  );

  const handleSwapCommit = useCallback(
    (id: PanelId, targetSlotId: SlotId | null): void => {
      // Side effects MUST stay out of the setState updater — React StrictMode
      // double-invokes updater functions in dev, which would call swapSlots()
      // twice and produce no net change (swap + swap = identity).
      if (targetSlotId !== null) {
        const sourceSlotId = windows[id].homeSlotId;
        if (targetSlotId !== sourceSlotId) {
          const resident = residentBySlot[targetSlotId];
          if (resident !== undefined && resident !== id) {
            swapSlots(id, resident);
          }
        }
      }
      setSwap(null);
    },
    [residentBySlot, swapSlots, windows],
  );

  const handleSwapCancel = useCallback((): void => {
    setSwap(null);
  }, []);

  // ===== Home-slot ghosts (rendered for every maximized window) =====
  const ghosts = useMemo(() => {
    const items: Array<{
      id: PanelId;
      slotId: SlotId;
      title: string;
    }> = [];
    for (const spec of WINDOWS) {
      const w = windows[spec.id];
      if (w.maximized && w.visible) {
        items.push({ id: spec.id, slotId: w.homeSlotId, title: spec.title });
      }
    }
    return items;
  }, [windows]);

  // ===== Swap-drag floating preview =====
  const swapPreviewStyle = useMemo<CSSProperties | null>(() => {
    if (!swap) return null;
    const source = windows[swap.sourceId];
    const sourceRect = slotRects[source.homeSlotId];
    const off = swapStartOffsetRef.current ?? {
      dx: sourceRect.w / 2,
      dy: 14,
    };
    return {
      position: 'fixed',
      left: swap.cursor.x - off.dx,
      top: swap.cursor.y - off.dy,
      width: sourceRect.w,
      height: sourceRect.h,
      zIndex: 10000,
      pointerEvents: 'none',
    };
  }, [swap, slotRects, windows]);

  return (
    <div className="hud-window-root" onPointerDown={onRootPointerDown}>
      {/* Ghost placeholders for maximized windows' home slots */}
      {ghosts.map((g) => {
        const rect = slotRects[g.slotId];
        const style: CSSProperties = {
          position: 'absolute',
          left: rect.x,
          top: rect.y,
          width: rect.w,
          height: rect.h,
        };
        return (
          <button
            key={`ghost-${g.id}`}
            type="button"
            className="slot-ghost"
            style={style}
            onClick={() => minimize(g.id)}
            aria-label={`Dock ${g.title} back to home slot`}
            title={`Dock ${g.title} back to home slot`}
          >
            <span className="slot-ghost-label">
              {g.title.toUpperCase()} — floating
            </span>
          </button>
        );
      })}

      {WINDOWS.filter((spec) => isPanelAvailable(availabilityMap, spec.id)).map((spec) => (
        <Window
          key={spec.id}
          id={spec.id}
          title={spec.title}
          icon={spec.icon}
          disabled={idle}
          onSwapStart={handleSwapStart}
          onSwapMove={handleSwapMove}
          onSwapCommit={handleSwapCommit}
          onSwapCancel={handleSwapCancel}
        >
          {(mode) =>
            spec.id === 'transcript'
              ? <TranscriptPanel mode={mode} orbState={orbState} />
              : spec.render(mode, effectivePaused)
          }
        </Window>
      ))}

      <SnapOverlay />
      <SwapOverlay
        active={swap !== null}
        slotRects={slotRects}
        hoveredSlotId={swap?.hoveredSlotId ?? null}
        sourceSlotId={swap?.sourceSlotId ?? null}
        residentBySlot={residentBySlot}
        titleByPanel={TITLE_BY_PANEL}
      />

      {/* Floating drag preview for the swapping window */}
      {swap !== null && swapPreviewStyle !== null && (
        <div className="swap-drag-preview" style={swapPreviewStyle} aria-hidden>
          <div className="swap-drag-preview-inner">
            <span className="swap-drag-preview-label">
              {TITLE_BY_PANEL[swap.sourceId].toUpperCase()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default HudWindows;
