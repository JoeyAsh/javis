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
import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@test/renderWithProviders';
import { LightsPanel } from '../components/LightsPanel';
import lightsReducer from '../lightsSlice';
import type { Zone } from '../types';

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
        renderWithProviders(<LightsPanel mode="expanded" />, {
            reducers: { lights: lightsReducer },
        });
        expect(screen.getByText(/living room/i)).toBeDefined();
        expect(screen.getByText(/kitchen/i)).toBeDefined();
        expect(screen.getByText(/workshop/i)).toBeDefined();
        expect(screen.getByText(/bedroom/i)).toBeDefined();
    });

    it('shows "AUS" for off zones and brightness % for on zones', () => {
        renderWithProviders(<LightsPanel mode="expanded" />, {
            reducers: { lights: lightsReducer },
        });
        expect(screen.getAllByText(/72 %/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/45 %/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText('AUS').length).toBe(2);
    });

    it('toggles an OFF zone to ON on click (local mock mode)', () => {
        renderWithProviders(<LightsPanel mode="expanded" />, {
            reducers: { lights: lightsReducer },
        });
        const workshopTile = screen.getByRole('button', { name: /workshop/i });
        expect(workshopTile).toBeDefined();
        const ausen = screen.getAllByText('AUS');
        expect(ausen.length).toBe(2);
        fireEvent.click(workshopTile);
        expect(screen.getAllByText('AUS').length).toBe(1);
    });

    it('compact mode shows zone count summary row', () => {
        renderWithProviders(<LightsPanel mode="compact" />, {
            reducers: { lights: lightsReducer },
        });
        expect(screen.getByText('ZONES')).toBeDefined();
        expect(screen.getByText('ON')).toBeDefined();
        expect(screen.getByText('4')).toBeDefined();
        expect(screen.getByText('2')).toBeDefined();
    });

    it('shows placeholder when zones is empty array', () => {
        renderWithProviders(<LightsPanel zones={[]} />, {
            reducers: { lights: lightsReducer },
        });
        expect(screen.getByText(/no zones/i)).toBeDefined();
    });

    it('renders external zones prop instead of mock data', () => {
        const externalZones: Zone[] = [
            { id: 'x1', label: 'Garage', on: true, brightness: 80 },
            { id: 'x2', label: 'Attic', on: false, brightness: 0 },
        ];
        renderWithProviders(<LightsPanel zones={externalZones} />, {
            reducers: { lights: lightsReducer },
        });
        expect(screen.getByText(/garage/i)).toBeDefined();
        expect(screen.getByText(/attic/i)).toBeDefined();
        expect(screen.queryByText(/living room/i)).toBeNull();
    });

    it('calls onAction with toggle when tile is clicked (external handler)', () => {
        const handleAction = vi.fn();
        renderWithProviders(<LightsPanel zones={MOCK_ZONES} onAction={handleAction} />, {
            reducers: { lights: lightsReducer },
        });
        const kitchenTile = screen.getByRole('button', { name: /kitchen/i });
        fireEvent.click(kitchenTile);
        expect(handleAction).toHaveBeenCalledWith('kt', { type: 'toggle' });
    });
});
