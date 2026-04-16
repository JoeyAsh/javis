export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

// Messages received FROM the backend
export type WsIncoming =
  | { type: 'audio'; data: string; text: string }
  | { type: 'status'; state: OrbState }
  | { type: 'text'; text: string }
  | { type: 'system'; payload: { cpu: number; mem: number; uptime: string } };

// Messages sent TO the backend
export type WsOutgoing =
  | { type: 'transcript'; text: string; isFinal: boolean }
  | { type: 'reset' };
