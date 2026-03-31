export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

export type WsMessage =
  | { type: 'state'; payload: OrbState }
  | { type: 'transcript'; payload: { role: 'user' | 'jarvis'; text: string } }
  | { type: 'system'; payload: { cpu: number; mem: number; uptime: string } };

export type WsCommand =
  | { type: 'set_voice'; payload: { profile: string } }
  | { type: 'reset'; payload: null };

export interface TranscriptEntry {
  role: 'user' | 'jarvis';
  text: string;
  id: number;
}

export interface SystemStats {
  cpu: number;
  mem: number;
  uptime: string;
}
