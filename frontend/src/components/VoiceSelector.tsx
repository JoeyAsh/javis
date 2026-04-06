import { useEffect, useState } from 'react';
import type { WsCommand } from '../types';

interface VoiceSelectorProps {
  send: (cmd: WsCommand) => void;
}

/**
 * Voice profile selector dropdown.
 */
export function VoiceSelector({ send }: VoiceSelectorProps) {
  const [voices, setVoices] = useState<string[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchVoices() {
      try {
        const response = await fetch('/voices');
        if (response.ok) {
          const data = await response.json();
          setVoices(data);
          if (data.length > 0) {
            // Default to jarvis.wav if available
            const defaultVoice = data.find((v: string) =>
              v.toLowerCase().includes('jarvis')
            );
            setSelectedVoice(defaultVoice || data[0]);
          }
        }
      } catch (error) {
        console.error('Failed to fetch voices:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchVoices();
  }, []);

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const profile = event.target.value;
    setSelectedVoice(profile);

    // Send command to backend
    send({
      type: 'set_voice',
      payload: { profile: profile.replace('.wav', '') },
    });
  };

  if (loading || voices.length === 0) {
    return null;
  }

  return (
    <div className="glass-panel fixed top-6 right-6 z-10 p-3">
      <label
        className="block text-xs font-medium mb-2"
        style={{ color: 'var(--text-secondary)' }}
      >
        VOICE PROFILE
      </label>
      <select
        value={selectedVoice}
        onChange={handleChange}
        className="w-full px-3 py-2 text-sm font-medium cursor-pointer focus:outline-none focus:ring-1"
        style={{
          backgroundColor: 'var(--surface)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: '2px',
        }}
      >
        {voices.map((voice) => (
          <option key={voice} value={voice}>
            {voice.replace('.wav', '').toUpperCase()}
          </option>
        ))}
      </select>
    </div>
  );
}

export default VoiceSelector;
