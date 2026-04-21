import { useState, type ReactElement } from 'react';
import { WindowManager } from '../../compositions/WindowManager';
import type { ManagedWindow } from '../../compositions/WindowManager';
import type { SlotId } from '../../layout/SlotGrid';
import { Mono } from '../../primitives/Mono';
import { Label } from '../../primitives/Label';

const EMPTY_WINDOWS: ManagedWindow[] = [
    {
        id: 'win-system',
        title: 'SYSTEM',
        ix: '◈',
        content: (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: 8,
                }}
            >
                <Label dim>SYSTEM</Label>
            </div>
        ),
    },
    {
        id: 'win-transcript',
        title: 'TRANSCRIPT',
        ix: '▸',
        content: (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: 8,
                }}
            >
                <Label dim>TRANSCRIPT</Label>
            </div>
        ),
    },
    {
        id: 'win-agenda',
        title: 'AGENDA',
        ix: '▦',
        content: (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: 8,
                }}
            >
                <Label dim>AGENDA</Label>
            </div>
        ),
    },
    {
        id: 'win-nowplaying',
        title: 'NOW PLAYING',
        ix: '♫',
        content: (
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    height: '100%',
                    padding: 8,
                }}
            >
                <Label dim>NOW PLAYING</Label>
            </div>
        ),
    },
];

const INITIAL_ASSIGNMENTS: Record<string, SlotId> = {
    'win-system': 'L1',
    'win-transcript': 'R1',
    'win-agenda': 'R2',
    'win-nowplaying': 'B1',
};

export function WindowsSection(): ReactElement {
    const [assignments, setAssignments] = useState<Record<string, SlotId>>(INITIAL_ASSIGNMENTS);
    const [focusedId, setFocusedId] = useState<string | null>(null);

    return (
        <section id="windows" className="flex flex-col gap-4">
            <div>
                <h2 className="text-[12px] text-text font-mono mb-1">WINDOWS</h2>
                <p className="text-[10px] text-text-secondary font-mono">
                    Draggable slot-grid windows — snap preview · swap · controlled assignments. Drag
                    within this stage is proof-of-concept; in production the stage is fullscreen.
                </p>
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
                        marginBottom: 6,
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
                        fontSize: 8,
                        color: 'var(--text-muted)',
                        marginTop: 6,
                        letterSpacing: 1,
                    }}
                >
                    Drag a window header to another slot to move · drag onto occupied slot to swap
                </div>
            </div>

            {/* Scoped stage */}
            <div
                style={{
                    position: 'relative',
                    height: 760,
                    width: '100%',
                    border: '1px solid var(--border)',
                    background: 'rgba(5,5,8,0.9)',
                    overflow: 'hidden',
                }}
            >
                <WindowManager
                    windows={EMPTY_WINDOWS}
                    assignments={assignments}
                    onAssignmentsChange={setAssignments}
                    focusedId={focusedId}
                    onFocusChange={setFocusedId}
                />
            </div>
        </section>
    );
}

export default WindowsSection;
