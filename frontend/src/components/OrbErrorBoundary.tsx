import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * Error boundary that catches Three.js / WebGL initialisation failures so the
 * rest of the JARVIS HUD continues to render even when the orb cannot start.
 */
export class OrbErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error: unknown): State {
    const message =
      error instanceof Error ? error.message : 'Unknown orb error';
    return { hasError: true, message };
  }

  override render(): ReactNode {
    if (this.state.hasError) {
      // Render a silent dark fallback — the HUD overlays remain visible.
      return (
        <div
          className="fixed inset-0 w-screen h-screen"
          style={{ zIndex: 0, backgroundColor: 'var(--bg)' }}
          aria-hidden="true"
        />
      );
    }
    return this.props.children;
  }
}

export default OrbErrorBoundary;
