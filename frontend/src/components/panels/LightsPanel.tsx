import { useState } from 'react';
import type { ReactElement } from 'react';
import { lightsMock } from '../../mock/lightsMock';
import type { LightsState, LightScene, LightDevice, PanelMode } from '../../types';

export interface LightsPanelProps {
  initial?: LightsState;
  mode?: PanelMode;
}

const SCENES: LightScene[] = ['Cozy', 'Focus', 'Movie', 'Alert'];

function LightsCompact({
  state,
  onScene,
}: {
  state: LightsState;
  onScene: (s: LightScene) => void;
}): ReactElement {
  const total = state.devices.length;
  const on = state.devices.filter((d) => d.on).length;
  return (
    <>
      <div className="window-compact-row">
        <span style={{ color: 'var(--accent-bright)', fontWeight: 500 }}>{total}</span>
        <span className="mono-small">Geräte</span>
        <span style={{ color: 'var(--text-muted)' }}>·</span>
        <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{on}</span>
        <span className="mono-small">an</span>
        {state.activeScene && (
          <span className="mono-small" style={{ marginLeft: 'auto', color: 'var(--accent)' }}>
            {state.activeScene}
          </span>
        )}
      </div>
      <div
        className="window-compact-row"
        data-no-drag
        style={{ gap: 4, marginTop: 6, flexWrap: 'wrap' }}
      >
        {SCENES.map((scene) => {
          const active = scene === state.activeScene;
          const isAlert = scene === 'Alert';
          return (
            <button
              key={scene}
              type="button"
              onClick={() => onScene(scene)}
              style={{
                flex: 1,
                minWidth: 0,
                padding: '3px 4px',
                fontSize: 9,
                letterSpacing: 1,
                textTransform: 'uppercase',
                fontFamily: 'var(--font)',
                background: active ? 'var(--accent)' : 'transparent',
                color: active
                  ? 'var(--bg)'
                  : isAlert
                    ? 'var(--danger)'
                    : 'var(--text-secondary)',
                border: `1px solid ${
                  active
                    ? 'var(--accent-bright)'
                    : isAlert
                      ? 'rgba(232,76,76,0.4)'
                      : 'var(--border)'
                }`,
                borderRadius: 2,
                cursor: 'pointer',
                transition: 'all 150ms',
              }}
            >
              {scene}
            </button>
          );
        })}
      </div>
    </>
  );
}

function LightsExpanded({
  state,
  onToggle,
  onBrightness,
  onScene,
}: {
  state: LightsState;
  onToggle: (id: string) => void;
  onBrightness: (id: string, v: number) => void;
  onScene: (s: LightScene) => void;
}): ReactElement {
  return (
    <>
      {state.devices.map((dev) => (
        <DeviceRow
          key={dev.id}
          device={dev}
          onToggle={() => onToggle(dev.id)}
          onBrightness={(v) => onBrightness(dev.id, v)}
        />
      ))}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 6,
          marginTop: 8,
        }}
      >
        {SCENES.map((scene) => {
          const active = scene === state.activeScene;
          const isAlert = scene === 'Alert';
          return (
            <button
              key={scene}
              type="button"
              onClick={() => onScene(scene)}
              style={{
                padding: '8px 6px',
                fontSize: 10,
                letterSpacing: 2,
                textTransform: 'uppercase',
                fontFamily: 'var(--font)',
                background: active ? 'var(--accent)' : 'transparent',
                color: active
                  ? 'var(--bg)'
                  : isAlert
                    ? 'var(--danger)'
                    : 'var(--text-secondary)',
                border: `1px solid ${
                  active
                    ? 'var(--accent-bright)'
                    : isAlert
                      ? 'rgba(232,76,76,0.4)'
                      : 'var(--border)'
                }`,
                borderRadius: 2,
                cursor: 'pointer',
                transition: 'all 150ms',
              }}
            >
              {scene}
            </button>
          );
        })}
      </div>
    </>
  );
}

interface DeviceRowProps {
  device: LightDevice;
  onToggle: () => void;
  onBrightness: (value: number) => void;
}

function DeviceRow({ device, onToggle, onBrightness }: DeviceRowProps): ReactElement {
  return (
    <div
      className="list-item"
      data-no-drag
      style={{ display: 'flex', alignItems: 'center', gap: 8 }}
    >
      <button
        type="button"
        aria-label={`Toggle ${device.name}`}
        onClick={onToggle}
        style={{
          width: 28,
          height: 16,
          borderRadius: 2,
          background: device.on ? 'var(--accent)' : 'var(--surface-raised)',
          border: `1px solid ${device.on ? 'var(--accent-bright)' : 'var(--border)'}`,
          position: 'relative',
          cursor: 'pointer',
          flexShrink: 0,
          padding: 0,
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 1,
            left: device.on ? 13 : 1,
            width: 12,
            height: 12,
            background: device.on ? 'var(--bg)' : 'var(--text-muted)',
            borderRadius: 1,
            transition: 'left 150ms',
          }}
        />
      </button>

      <div
        style={{
          width: 12,
          height: 12,
          background: device.color,
          border: '1px solid var(--border)',
          flexShrink: 0,
        }}
        aria-hidden
      />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 11,
            color: device.on ? 'var(--text)' : 'var(--text-muted)',
            marginBottom: 4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {device.name}
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={device.brightness}
          onChange={(e) => onBrightness(Number(e.target.value))}
          disabled={!device.on}
          aria-label={`${device.name} brightness`}
          style={{
            width: '100%',
            accentColor: 'var(--accent)',
            opacity: device.on ? 1 : 0.4,
          }}
        />
      </div>

      <span
        className="mono-small"
        style={{ flexShrink: 0, width: 28, textAlign: 'right' }}
      >
        {device.brightness}%
      </span>
    </div>
  );
}

export function LightsPanel({
  initial = lightsMock,
  mode = 'expanded',
}: LightsPanelProps): ReactElement {
  const [state, setState] = useState<LightsState>(initial);

  const toggle = (id: string): void => {
    setState((s) => ({
      ...s,
      devices: s.devices.map((d) => (d.id === id ? { ...d, on: !d.on } : d)),
    }));
  };

  const setBrightness = (id: string, value: number): void => {
    setState((s) => ({
      ...s,
      devices: s.devices.map((d) => (d.id === id ? { ...d, brightness: value } : d)),
    }));
  };

  const applyScene = (scene: LightScene): void => {
    setState((s) => ({ ...s, activeScene: scene }));
  };

  return mode === 'compact' ? (
    <LightsCompact state={state} onScene={applyScene} />
  ) : (
    <LightsExpanded
      state={state}
      onToggle={toggle}
      onBrightness={setBrightness}
      onScene={applyScene}
    />
  );
}

export default LightsPanel;
