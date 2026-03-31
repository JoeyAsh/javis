import { OrbCanvas } from './components/OrbCanvas';
import { StatusBar } from './components/StatusBar';
import { TranscriptFeed } from './components/TranscriptFeed';
import { VoiceSelector } from './components/VoiceSelector';
import { SystemStatus } from './components/SystemStatus';
import { useWebSocket } from './hooks/useWebSocket';

/**
 * Main JARVIS application component.
 */
function App() {
  const { orbState, transcript, systemStats, send, connected } = useWebSocket();

  return (
    <div
      className="min-h-screen w-screen overflow-hidden"
      style={{ backgroundColor: 'var(--bg)' }}
    >
      {/* Three.js Orb Canvas - fullscreen background */}
      <OrbCanvas orbState={orbState} />

      {/* HUD Overlays */}
      <SystemStatus systemStats={systemStats} connected={connected} />
      <VoiceSelector send={send} />
      <TranscriptFeed transcript={transcript} />
      <StatusBar orbState={orbState} />
    </div>
  );
}

export default App;
