import type { DevToolkitMock } from '../types';

export const devMock: DevToolkitMock = {
  prs: [
    {
      id: 'pr-1',
      repo: 'jarvis/core',
      title: 'feat: Fish Audio TTS streaming',
      author: '@joey',
      age: '2h',
    },
    {
      id: 'pr-2',
      repo: 'jarvis/integrations',
      title: 'Govee LAN fallback client',
      author: '@sarah',
      age: '6h',
    },
    {
      id: 'pr-3',
      repo: 'openclaw/skills',
      title: 'fix(calendar): timezone drift on recurring',
      author: '@elena',
      age: '1d',
    },
  ],
  notifications: [
    {
      id: 'nf-1',
      repo: 'jarvis/core',
      reason: 'mention',
      title: 'Re: panel grid snap-to-grid question',
      age: '18m',
    },
    {
      id: 'nf-2',
      repo: 'anthropic/claude-sdk',
      reason: 'subscribed',
      title: 'Release v0.34.0',
      age: '3h',
    },
  ],
  repos: [
    {
      id: 'rp-1',
      name: 'jarvis',
      branch: 'feature/fish-audio-rebuild',
      status: 'dirty',
      ahead: 3,
      behind: 0,
      uncommitted: 12,
    },
    {
      id: 'rp-2',
      name: 'openclaw',
      branch: 'main',
      status: 'clean',
      ahead: 0,
      behind: 0,
      uncommitted: 0,
    },
    {
      id: 'rp-3',
      name: 'homelab',
      branch: 'main',
      status: 'behind',
      ahead: 0,
      behind: 4,
      uncommitted: 0,
    },
    {
      id: 'rp-4',
      name: 'dotfiles',
      branch: 'develop',
      status: 'ahead',
      ahead: 2,
      behind: 0,
      uncommitted: 0,
    },
  ],
  docker: [
    { id: 'dk-1', name: 'jarvis-backend', image: 'jarvis:dev', status: 'running', cpu: 14, mem: 38 },
    { id: 'dk-2', name: 'postgres', image: 'postgres:16', status: 'running', cpu: 3, mem: 22 },
    { id: 'dk-3', name: 'redis', image: 'redis:7-alpine', status: 'running', cpu: 1, mem: 6 },
    { id: 'dk-4', name: 'openclaw', image: 'openclaw:1.2', status: 'running', cpu: 9, mem: 28 },
    { id: 'dk-5', name: 'home-assistant', image: 'ha:stable', status: 'restarting', cpu: 0, mem: 0 },
  ],
  ci: [
    { id: 'ci-1', repo: 'jarvis', status: 'success', ranAt: new Date(Date.now() - 22 * 60_000).toISOString(), duration: '3m 18s' },
    { id: 'ci-2', repo: 'openclaw', status: 'failure', ranAt: new Date(Date.now() - 48 * 60_000).toISOString(), duration: '1m 42s' },
    { id: 'ci-3', repo: 'homelab', status: 'running', ranAt: new Date(Date.now() - 2 * 60_000).toISOString(), duration: '— —' },
    { id: 'ci-4', repo: 'dotfiles', status: 'success', ranAt: new Date(Date.now() - 4 * 3600_000).toISOString(), duration: '0m 48s' },
  ],
};
