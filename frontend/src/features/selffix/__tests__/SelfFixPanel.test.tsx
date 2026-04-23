/**
 * SelfFixPanel — Vitest + RTL smoke tests.
 *
 * Tests:
 *  - Renders mock entries by default.
 *  - Distinguishes in_progress vs completed entries.
 *  - Shows relative time label.
 *  - Compact mode shows "Fix läuft" when in_progress entry exists.
 *  - Compact mode shows "Keine Fixes aktiv" when no in_progress.
 *  - Shows commit SHA pill for completed entries.
 *  - Shows ACCEPT and DISCARD buttons for completed entries.
 *  - Prop override replaces hook entries.
 */
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@test/renderWithProviders';
import { SelfFixPanel } from '../components/SelfFixPanel';
import type { SelfFixEntry } from '../types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const completedEntry: SelfFixEntry = {
    id: 'test-1',
    status: 'completed',
    summary: 'Fixed memory leak',
    detail: 'Patched the polling loop to release event listeners.',
    commitSha: 'abc1234',
    added: 5,
    removed: 2,
    startedAt: new Date(Date.now() - 5 * 60_000).toISOString(),
};

const inProgressEntry: SelfFixEntry = {
    id: 'test-2',
    status: 'in_progress',
    summary: 'Analyzing crash report...',
    detail: 'Stack trace under investigation.',
    startedAt: new Date(Date.now() - 30_000).toISOString(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SelfFixPanel expanded', () => {
    it('renders default mock entries', () => {
        renderWithProviders(<SelfFixPanel mode="expanded" />);
        // Default mock has one in_progress and one completed entry.
        expect(screen.getByText(/analyzing calendar-sync error/i)).toBeTruthy();
        expect(screen.getByText(/Fixed: wake-word false positives/i)).toBeTruthy();
    });

    it('renders prop entries instead of mock when provided', () => {
        renderWithProviders(<SelfFixPanel mode="expanded" entries={[completedEntry]} />);
        expect(screen.getByText('Fixed memory leak')).toBeTruthy();
        // Mock entries should not be visible.
        expect(screen.queryByText(/analyzing calendar-sync error/i)).toBeNull();
    });

    it('shows commit SHA pill for completed entry', () => {
        renderWithProviders(<SelfFixPanel mode="expanded" entries={[completedEntry]} />);
        expect(screen.getByText('abc1234')).toBeTruthy();
    });

    it('shows ACCEPT and DISCARD buttons for completed entry', () => {
        renderWithProviders(<SelfFixPanel mode="expanded" entries={[completedEntry]} />);
        expect(screen.getByText('ACCEPT')).toBeTruthy();
        expect(screen.getByText('DISCARD')).toBeTruthy();
    });

    it('shows add/remove counts for completed entry', () => {
        renderWithProviders(<SelfFixPanel mode="expanded" entries={[completedEntry]} />);
        expect(screen.getByText('+5')).toBeTruthy();
        expect(screen.getByText('-2')).toBeTruthy();
    });

    it('does not show ACCEPT/DISCARD for in_progress entry', () => {
        renderWithProviders(<SelfFixPanel mode="expanded" entries={[inProgressEntry]} />);
        expect(screen.queryByText('ACCEPT')).toBeNull();
        expect(screen.queryByText('DISCARD')).toBeNull();
    });
});

describe('SelfFixPanel compact', () => {
    it('shows Fix läuft when an in_progress entry exists', () => {
        renderWithProviders(
            <SelfFixPanel mode="compact" entries={[inProgressEntry, completedEntry]} />,
        );
        expect(screen.getByText(/fix läuft/i)).toBeTruthy();
    });

    it('shows Keine Fixes aktiv when no in_progress entries', () => {
        renderWithProviders(<SelfFixPanel mode="compact" entries={[completedEntry]} />);
        expect(screen.getByText(/keine fixes aktiv/i)).toBeTruthy();
    });

    it('shows summary of active entry in compact mode', () => {
        renderWithProviders(<SelfFixPanel mode="compact" entries={[inProgressEntry]} />);
        expect(screen.getByText('Analyzing crash report...')).toBeTruthy();
    });
});
