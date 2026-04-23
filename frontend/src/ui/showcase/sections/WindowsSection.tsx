import { useState, type ReactElement } from 'react';
import { WindowManager } from '../../compositions/WindowManager';
import type { ManagedWindow, PanelMode } from '../../compositions/WindowManager';
import type { PanelContentRenderProps } from '../../window/Window';
import type { SlotId } from '../../window/slotGrid';
import { Mono } from '../../primitives/Mono';
import { Label } from '../../primitives/Label';

// ── Compact view stub ─────────────────────────────────────────────────────────

function CompactContent({ label }: { label: string }): ReactElement {
    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                padding: 8,
                gap: 6,
            }}
        >
            <span
                style={{
                    fontSize: 8,
                    letterSpacing: 3,
                    textTransform: 'uppercase',
                    color: 'var(--text-muted)',
                }}
            >
                DOCKED
            </span>
            <Label dim>{label}</Label>
        </div>
    );
}

// ── Expanded view stub ────────────────────────────────────────────────────────

function ExpandedContent({ label }: { label: string }): ReactElement {
    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                padding: 16,
                gap: 10,
            }}
        >
            <span
                style={{
                    fontSize: 8,
                    letterSpacing: 3,
                    textTransform: 'uppercase',
                    color: 'var(--accent)',
                }}
            >
                UNDOCKED
            </span>
            <Label>{label}</Label>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)', textAlign: 'center' }}>
                Drag header to move · resize via edges and corners · click ⊞ in header to dock back
            </span>
        </div>
    );
}

// ── ItemRenderer factory ──────────────────────────────────────────────────────

function makeRenderer(label: string): (props: PanelContentRenderProps) => ReactElement {
    return function Renderer({ mode }: PanelContentRenderProps): ReactElement {
        if (mode === 'expanded') return <ExpandedContent label={label} />;
        return <CompactContent label={label} />;
    };
}

// ── Window definitions ────────────────────────────────────────────────────────

const MANAGED_WINDOWS: ManagedWindow[] = [
    {
        id: 'win-system',
        title: 'SYSTEM',
        ix: '◈',
        itemRenderer: makeRenderer('SYSTEM'),
    },
    {
        id: 'win-transcript',
        title: 'TRANSCRIPT',
        ix: '▸',
        itemRenderer: makeRenderer('TRANSCRIPT'),
    },
    {
        id: 'win-agenda',
        title: 'AGENDA',
        ix: '▦',
        itemRenderer: makeRenderer('AGENDA'),
    },
    {
        id: 'win-nowplaying',
        title: 'NOW PLAYING',
        ix: '♫',
        itemRenderer: makeRenderer('NOW PLAYING'),
    },
];

const INITIAL_ASSIGNMENTS: Record<string, SlotId> = {
    'win-system': 'L1',
    'win-transcript': 'R1',
    'win-agenda': 'R2',
    'win-nowplaying': 'B1',
};

// ── Section ───────────────────────────────────────────────────────────────────

export function WindowsSection(): ReactElement {
    const [assignments, setAssignments] = useState<Record<string, SlotId>>(INITIAL_ASSIGNMENTS);
    const [focusedId, setFocusedId] = useState<string | null>(null);
    const [modes, setModes] = useState<Record<string, PanelMode>>({});

    const currentModesDisplay = Object.entries(INITIAL_ASSIGNMENTS)
        .map(([id]) => {
            const mode = modes[id] ?? 'compact';
            return `${id.replace('win-', '')} → ${mode}`;
        })
        .join('  ·  ');

    return (
        <section id="windows" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">WINDOWS</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Dual-mode windows — compact (docked in slot) and expanded (free-floating).
                    Drag headers to swap slots in compact mode. Click the dock/undock button (⊞/⊟)
                    or double-click the header to toggle mode. In expanded mode: drag to move,
                    drag edges to resize.
                </p>
            </div>

            {/* Interaction hint */}
            <div
                style={{
                    fontSize: 10,
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font)',
                    letterSpacing: '0.5px',
                }}
            >
                Compact: drag header to snap/swap slots · Reset (↺) restores home slot and docks.
                Expanded: drag to move · resize via edges/corners · ⊟ to dock back.
            </div>

            {/* Assignment readout */}
            <div
                style={{
                    border: '1px solid var(--border)',
                    padding: '8px 12px',
                    background: 'rgba(13,13,20,0.6)',
                }}
            >
                <div
                    style={{
                        fontSize: 9,
                        letterSpacing: 2,
                        textTransform: 'uppercase',
                        color: 'var(--text-secondary)',
                        marginBottom: 4,
                    }}
                >
                    Current Assignments
                </div>
                <Mono size="sm" secondary>
                    {Object.entries(assignments)
                        .map(([wId, sId]) => `${wId.replace('win-', '')} → ${sId}`)
                        .join('  ·  ')}
                </Mono>
                <div
                    style={{
                        fontSize: 9,
                        letterSpacing: 2,
                        textTransform: 'uppercase',
                        color: 'var(--text-secondary)',
                        marginBottom: 4,
                        marginTop: 8,
                    }}
                >
                    Current Modes
                </div>
                <Mono size="sm" secondary>
                    {currentModesDisplay}
                </Mono>
                <div
                    style={{
                        fontSize: 8,
                        color: 'var(--text-muted)',
                        marginTop: 6,
                        letterSpacing: 1,
                    }}
                >
                    Drag compact window header to another slot to move · drag onto occupied slot to swap
                </div>
            </div>

            {/* Scoped stage */}
            <div
                style={{
                    position: 'relative',
                    height: 860,
                    width: '100%',
                    border: '1px solid var(--border)',
                    background: 'rgba(5,5,8,0.9)',
                    overflow: 'hidden',
                }}
            >
                <WindowManager
                    windows={MANAGED_WINDOWS}
                    assignments={assignments}
                    onAssignmentsChange={setAssignments}
                    focusedId={focusedId}
                    onFocusChange={setFocusedId}
                    modes={modes}
                    onModesChange={setModes}
                />
            </div>
        </section>
    );
}

export default WindowsSection;
