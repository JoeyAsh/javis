import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TopBar } from '../TopBar';

describe('TopBar', () => {
    it('renders left slot', () => {
        render(<TopBar left={<span>clock</span>} />);
        expect(screen.getByText('clock')).toBeDefined();
    });

    it('renders center slot', () => {
        render(<TopBar center={<span>JARVIS</span>} />);
        expect(screen.getByText('JARVIS')).toBeDefined();
    });

    it('renders right slot', () => {
        render(<TopBar right={<span>settings</span>} />);
        expect(screen.getByText('settings')).toBeDefined();
    });

    it('renders all three slots simultaneously', () => {
        render(
            <TopBar
                left={<span>left</span>}
                center={<span>center</span>}
                right={<span>right</span>}
            />,
        );
        expect(screen.getByText('left')).toBeDefined();
        expect(screen.getByText('center')).toBeDefined();
        expect(screen.getByText('right')).toBeDefined();
    });

    it('renders as a div with lib-topbar class', () => {
        const { container } = render(<TopBar />);
        expect(container.querySelector('.lib-topbar')).toBeDefined();
    });

    it('has bottom corner bracket elements', () => {
        const { container } = render(<TopBar />);
        expect(container.querySelector('.lib-topbar__c-bl')).toBeDefined();
        expect(container.querySelector('.lib-topbar__c-br')).toBeDefined();
    });

    it('has trace element with l and r strips', () => {
        const { container } = render(<TopBar />);
        const trace = container.querySelector('.lib-topbar__trace');
        expect(trace).toBeDefined();
        expect(trace?.querySelector('.lib-topbar__trace-l')).toBeDefined();
        expect(trace?.querySelector('.lib-topbar__trace-r')).toBeDefined();
    });

    it('className merges on root', () => {
        const { container } = render(<TopBar className="my-topbar" />);
        const root = container.querySelector('.lib-topbar');
        expect(root?.classList.contains('my-topbar')).toBe(true);
    });

    it('left/center/right slots render in their containers', () => {
        const { container } = render(
            <TopBar left={<span>L</span>} center={<span>C</span>} right={<span>R</span>} />,
        );
        expect(container.querySelector('.lib-topbar__left')?.textContent).toBe('L');
        expect(container.querySelector('.lib-topbar__center')?.textContent).toBe('C');
        expect(container.querySelector('.lib-topbar__right')?.textContent).toBe('R');
    });
});
