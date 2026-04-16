import type { SystemMetric } from '../types';

const history = (base: number, amp: number, n = 24): number[] => {
  const out: number[] = [];
  for (let i = 0; i < n; i++) {
    const v = base + Math.sin(i * 0.6) * amp + (Math.random() - 0.5) * amp * 0.6;
    out.push(Math.max(0, Math.min(100, v)));
  }
  return out;
};

export const systemMock: SystemMetric[] = [
  {
    id: 'cpu',
    label: 'CPU',
    unit: '%',
    current: 42,
    history: history(42, 12),
  },
  {
    id: 'ram',
    label: 'RAM',
    unit: '%',
    current: 68,
    history: history(68, 4),
  },
  {
    id: 'gpu',
    label: 'GPU',
    unit: '%',
    current: 31,
    history: history(31, 18),
  },
  {
    id: 'cpuTemp',
    label: 'CPU TEMP',
    unit: '°C',
    current: 62,
    history: history(62, 6),
  },
  {
    id: 'net',
    label: 'NET',
    unit: 'Mb/s',
    current: 12.4,
    history: history(12, 6),
    secondary: 3.1,
    secondaryLabel: 'UP',
  },
  {
    id: 'disk',
    label: 'DISK',
    unit: '%',
    current: 54,
    history: history(54, 2),
  },
];
