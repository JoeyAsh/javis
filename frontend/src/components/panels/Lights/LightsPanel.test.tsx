/**
 * LightsPanel — Vitest + RTL tests.
 *
 * LightsPanel is dormant (not mounted in default HUD layout — awaiting backend #54).
 * These tests verify the mock-data rendering, toggle interaction, and prop contract.
 *
 * Tests cover:
 *   - Renders 4 default mock zones in expanded mode
 *   - Renders zone names (Living Room, Kitchen, Workshop, Bedroom)
 *   - OFF zones show "AUS" dim label
 *   - ON zones show brightness percentage
 *   - Clicking a tile toggles on/off state (local mock)
 *   - Compact mode shows zone count summary
 *   - Empty zones array shows placeholder text
 *   - External zones prop replaces mock data
 *   - onAction is called with correct args when provided
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LightsPanel } from './LightsPanel';
import type { Zone } from './types';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_ZONES: Zone[] = [
    { id: 'lr', label: 'Living Room', on: true, brightness: 72 },
    { id: 'kt', label: 'Kitchen', on: true, brightness: 45 },
    { id: 'wk', label: 'Workshop', on: false, brightness: 0 },
    { id: 'bd', label: 'Bedroom', on: false, brightness: 0 },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('LightsPanel', () => {
    it('renders 4 default mock zones in expanded mode', () => {
        render(<LightsPanel mode="expanded" />);
        // All 4 zone names should be present
        expect(screen.getByText(/living room/i)).toBeDefined();
        expect(screen.getByText(/kitchen/i)).toBeDefined();
        expect(screen.getByText(/workshop/i)).toBeDefined();
        expect(screen.getByText(/bedroom/i)).toBeDefined();
    });

    it('shows "AUS" for off zones and brightness % for on zones', () => {
        render(<LightsPanel mode="expanded" />);
        // ON zones show their brightness % (mocked: 72% and 45%)
        expect(screen.getAllByText(/72 %/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/45 %/i).length).toBeGreaterThan(0);
        // OFF zones show "AUS"
        expect(screen.getAllByText('AUS').length).toBe(2);
    });

    it('toggles an OFF zone to ON on click (local mock mode)', () => {
        render(<LightsPanel mode="expanded" />);
        // Workshop starts off — "AUS" label
        const workshopTile = screen.getByRole('button', { name: /workshop/i });
        expect(workshopTile).toBeDefined();
        // Before toggle: "AUS" in tile area
        const ausen = screen.getAllByText('AUS');
        expect(ausen.length).toBe(2);
        // Click Workshop tile to toggle on
        fireEvent.click(workshopTile);
        // After toggle: one less "AUS"
        expect(screen.getAllByText('AUS').length).toBe(1);
    });

    it('compact mode shows zone count summary row', () => {
        render(<LightsPanel mode="compact" />);
        // "ZONES" label present
        expect(screen.getByText('ZONES')).toBeDefined();
        // "ON" label present
        expect(screen.getByText('ON')).toBeDefined();
        // 4 zones total
        const zoneCount = screen.getByText('4');
        expect(zoneCount).toBeDefined();
        // 2 zones on initially
        const onCount = screen.getByText('2');
        expect(onCount).toBeDefined();
    });

    it('shows placeholder when zones is empty array', () => {
        render(<LightsPanel zones={[]} />);
        expect(screen.getByText(/no zones/i)).toBeDefined();
    });

    it('renders external zones prop instead of mock data', () => {
        const externalZones: Zone[] = [
            { id: 'x1', label: 'Garage', on: true, brightness: 80 },
            { id: 'x2', label: 'Attic', on: false, brightness: 0 },
        ];
        render(<LightsPanel zones={externalZones} />);
        expect(screen.getByText(/garage/i)).toBeDefined();
        expect(screen.getByText(/attic/i)).toBeDefined();
        // Default mock zones should NOT be present
        expect(screen.queryByText(/living room/i)).toBeNull();
    });

    it('calls onAction with toggle when tile is clicked (external handler)', () => {
        const handleAction = vi.fn();
        render(<LightsPanel zones={MOCK_ZONES} onAction={handleAction} />);
        const kitchenTile = screen.getByRole('button', { name: /kitchen/i });
        fireEvent.click(kitchenTile);
        expect(handleAction).toHaveBeenCalledWith('kt', { type: 'toggle' });
    });

    it('applies zone-tile--on class to on zones', () => {
        render(<LightsPanel zones={MOCK_ZONES} />);
        const livingRoomTile = screen.getByRole('button', { name: /living room/i });
        expect(livingRoomTile.classList.contains('zone-tile--on')).toBe(true);
        const workshopTile = screen.getByRole('button', { name: /workshop/i });
        expect(workshopTile.classList.contains('zone-tile--on')).toBe(false);
    });
});
