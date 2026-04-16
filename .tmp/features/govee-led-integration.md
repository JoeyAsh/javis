# Feature Spec: Govee LED Integration

## Summary
Integrate Govee LED lights for ambient lighting control. Users can control lights via voice ("turn on the office lights", "set the lights to cozy mode", "dim the lights to 50%") and quick-toggle scenes from the LightsPanel. The integration uses the Govee Developer API (REST) for cloud control.

## Goals
- Enable voice-controlled Govee LED operations: on/off, brightness, color, scenes
- Display device states and quick-action buttons in LightsPanel
- Support configurable scenes (cozy, focus, movie, alarm) mapped to brightness/color presets
- Poll device states to keep UI in sync
- Extend existing SmartHomeAgent rather than creating a separate agent

## Non-Goals
- ~~Govee LAN API~~ — NOW IN SCOPE (see Revision 2)
- Alexa/Google Home skill integration (we're replacing that dependency)
- iCUE/Corsair integration (separate ecosystem)
- DIY/custom LED strip protocols
- Music sync / reactive lighting

## Prerequisites
- **Govee Developer API key** — obtained from Govee mobile app (Settings → About → Apply for API Key)
- Govee devices registered in the Govee app
- Internet connectivity (cloud API)

---

## Architecture

### Backend Components

```
src/integrations/govee/
  __init__.py
  client.py           # GoveeClient - REST API wrapper
```

### Frontend Components

```
frontend/src/
  components/panels/
    LightsPanel.tsx
  hooks/
    useGovee.ts
```

---

## Govee Developer API Overview

### Endpoints
- Base URL: `https://developer-api.govee.com`
- Auth: `Govee-API-Key` header
- Rate limit: 10,000 requests/day, 100 requests/min

### Key Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/devices` | GET | List all devices |
| `/v1/devices/control` | PUT | Control a device |
| `/v1/devices/state` | GET | Get device state |

### Device Control Payload
```json
{
  "device": "device_mac_address",
  "model": "device_model",
  "cmd": {
    "name": "turn",
    "value": "on"
  }
}
```

### Available Commands
| Command | Values |
|---------|--------|
| `turn` | `"on"`, `"off"` |
| `brightness` | `0-100` |
| `color` | `{"r": 0-255, "g": 0-255, "b": 0-255}` |
| `colorTem` | `2000-9000` (Kelvin) |

---

## Govee Client (`src/integrations/govee/client.py`)

### Interface

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class GoveeDevice:
    """Govee device information."""
    device_id: str        # MAC address
    model: str
    name: str
    controllable: bool
    retrievable: bool
    support_cmds: list[str]  # ["turn", "brightness", "color", "colorTem"]

@dataclass
class GoveeDeviceState:
    """Current state of a Govee device."""
    device_id: str
    model: str
    name: str
    online: bool
    power_state: bool     # True = on, False = off
    brightness: int       # 0-100
    color: str            # "#RRGGBB" hex
    color_temp: int | None  # Kelvin, if supported

class GoveeClient:
    """Async Govee Developer API client."""

    def __init__(self, api_key: str, config: dict[str, Any]) -> None:
        """Initialize client.

        Args:
            api_key: Govee Developer API key
            config: Govee section from config.yaml
        """
        ...

    async def initialize(self) -> None:
        """Verify API key and fetch device list.

        Raises:
            GoveeAuthError: If API key is invalid
        """
        ...

    async def get_devices(self) -> list[GoveeDevice]:
        """Get all registered devices."""
        ...

    async def get_device_state(self, device_id: str, model: str) -> GoveeDeviceState | None:
        """Get current state of a device.

        Args:
            device_id: Device MAC address
            model: Device model number

        Returns:
            Device state, or None if not retrievable
        """
        ...

    async def get_all_states(self) -> list[GoveeDeviceState]:
        """Get states of all retrievable devices."""
        ...

    async def turn_on(self, device_id: str, model: str) -> bool:
        """Turn device on."""
        ...

    async def turn_off(self, device_id: str, model: str) -> bool:
        """Turn device off."""
        ...

    async def set_brightness(self, device_id: str, model: str, brightness: int) -> bool:
        """Set brightness (0-100)."""
        ...

    async def set_color(self, device_id: str, model: str, r: int, g: int, b: int) -> bool:
        """Set RGB color."""
        ...

    async def set_color_temp(self, device_id: str, model: str, kelvin: int) -> bool:
        """Set color temperature (2000-9000K)."""
        ...

    async def apply_scene(self, scene_name: str) -> bool:
        """Apply a configured scene to all devices.

        Args:
            scene_name: Scene key from config (cozy, focus, movie, alarm)

        Returns:
            True if all devices were updated successfully
        """
        ...


class GoveeAuthError(Exception):
    """Raised when Govee API authentication fails."""
    pass


class GoveeApiError(Exception):
    """Raised when Govee API request fails."""
    pass
```

### Implementation

```python
import httpx
import asyncio
from utils.logger import get_logger

logger = get_logger("govee_client")

BASE_URL = "https://developer-api.govee.com"

class GoveeClient:
    def __init__(self, api_key: str, config: dict[str, Any]) -> None:
        self._api_key = api_key
        self._config = config
        self._devices: list[GoveeDevice] = []
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Govee-API-Key": self._api_key},
            timeout=10.0,
        )

        # Verify API key by fetching devices
        try:
            await self._fetch_devices()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise GoveeAuthError("Invalid Govee API key")
            raise GoveeApiError(f"Failed to initialize Govee: {e}")

        logger.info(f"Govee client initialized with {len(self._devices)} devices")

    async def _fetch_devices(self) -> None:
        """Fetch and cache device list."""
        response = await self._client.get("/v1/devices")
        response.raise_for_status()
        data = response.json()

        self._devices = [
            GoveeDevice(
                device_id=d["device"],
                model=d["model"],
                name=d["deviceName"],
                controllable=d.get("controllable", False),
                retrievable=d.get("retrievable", False),
                support_cmds=d.get("supportCmds", []),
            )
            for d in data.get("data", {}).get("devices", [])
        ]

    async def get_devices(self) -> list[GoveeDevice]:
        if not self._devices:
            await self._fetch_devices()
        return self._devices

    async def get_device_state(self, device_id: str, model: str) -> GoveeDeviceState | None:
        try:
            response = await self._client.get(
                "/v1/devices/state",
                params={"device": device_id, "model": model},
            )
            response.raise_for_status()
            data = response.json().get("data", {})

            # Find device name
            device = next((d for d in self._devices if d.device_id == device_id), None)
            name = device.name if device else device_id

            # Parse properties
            props = data.get("properties", [])
            power = next((p["value"] for p in props if p.get("powerState")), "off")
            brightness = next((p.get("brightness") for p in props if "brightness" in p), 100)
            color = next((p.get("color") for p in props if "color" in p), {"r": 255, "g": 255, "b": 255})

            return GoveeDeviceState(
                device_id=device_id,
                model=model,
                name=name,
                online=data.get("online", True),
                power_state=power == "on",
                brightness=brightness,
                color=f"#{color['r']:02x}{color['g']:02x}{color['b']:02x}",
                color_temp=None,  # Parse if present
            )
        except httpx.HTTPError as e:
            logger.error(f"Failed to get state for {device_id}: {e}")
            return None

    async def get_all_states(self) -> list[GoveeDeviceState]:
        states = []
        for device in self._devices:
            if device.retrievable:
                state = await self.get_device_state(device.device_id, device.model)
                if state:
                    states.append(state)
                # Rate limit: small delay between requests
                await asyncio.sleep(0.1)
        return states

    async def _send_command(self, device_id: str, model: str, cmd: dict) -> bool:
        try:
            response = await self._client.put(
                "/v1/devices/control",
                json={
                    "device": device_id,
                    "model": model,
                    "cmd": cmd,
                },
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to send command to {device_id}: {e}")
            return False

    async def turn_on(self, device_id: str, model: str) -> bool:
        return await self._send_command(device_id, model, {"name": "turn", "value": "on"})

    async def turn_off(self, device_id: str, model: str) -> bool:
        return await self._send_command(device_id, model, {"name": "turn", "value": "off"})

    async def set_brightness(self, device_id: str, model: str, brightness: int) -> bool:
        brightness = max(0, min(100, brightness))
        return await self._send_command(device_id, model, {"name": "brightness", "value": brightness})

    async def set_color(self, device_id: str, model: str, r: int, g: int, b: int) -> bool:
        return await self._send_command(
            device_id, model,
            {"name": "color", "value": {"r": r, "g": g, "b": b}}
        )

    async def set_color_temp(self, device_id: str, model: str, kelvin: int) -> bool:
        kelvin = max(2000, min(9000, kelvin))
        return await self._send_command(device_id, model, {"name": "colorTem", "value": kelvin})

    async def apply_scene(self, scene_name: str) -> bool:
        scenes = self._config.get("scenes", {})
        scene = scenes.get(scene_name)
        if not scene:
            logger.warning(f"Scene '{scene_name}' not found in config")
            return False

        brightness = scene.get("brightness", 100)
        color_hex = scene.get("color", "#ffffff")

        # Parse hex color
        color_hex = color_hex.lstrip("#")
        r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

        success = True
        for device in self._devices:
            if device.controllable:
                # Turn on, set brightness, set color
                await self.turn_on(device.device_id, device.model)
                await asyncio.sleep(0.1)
                await self.set_brightness(device.device_id, device.model, brightness)
                await asyncio.sleep(0.1)
                if "color" in device.support_cmds:
                    await self.set_color(device.device_id, device.model, r, g, b)
                await asyncio.sleep(0.1)

        return success
```

---

## SmartHomeAgent Extension

**Decision:** Extend existing `SmartHomeAgent` rather than creating separate `GoveeAgent`

**Rationale:**
- Govee devices are lights — fits the "smart home" domain
- Avoids proliferation of single-purpose agents
- Intent parser already routes `SMART_HOME` for lights
- Future lighting brands (Philips Hue, LIFX) can use the same pattern

### Updates to `src/brain/agents/smart_home_agent.py`

```python
class SmartHomeAgent(BaseAgent):
    """Agent for smart home control including Govee lights."""

    def __init__(
        self,
        home_assistant_client: HomeAssistantClient | None,
        govee_client: GoveeClient | None,
    ) -> None:
        super().__init__()
        self._ha_client = home_assistant_client
        self._govee_client = govee_client

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        domain = params.get("domain", "light")
        action = params.get("action", "unknown")

        # Route to appropriate handler
        if domain == "light":
            return await self._handle_light(task, params, language)
        elif domain == "climate":
            return await self._handle_climate(task, params, language)
        # ... other domains ...

    async def _handle_light(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        action = params.get("action")

        # Check for scene request
        scene = params.get("scene")
        if scene and self._govee_client:
            success = await self._govee_client.apply_scene(scene)
            return AgentResult(
                spoken_response=self._format_scene_response(scene, success, language),
                success=success,
            )

        # Determine target device(s)
        room = params.get("room")
        device_name = params.get("device")

        if self._govee_client:
            devices = await self._govee_client.get_devices()
            target_devices = self._filter_devices(devices, room, device_name)

            if not target_devices:
                return AgentResult(
                    spoken_response=self._no_device_response(room or device_name, language),
                    success=False,
                )

            # Execute action on all target devices
            for device in target_devices:
                await self._execute_govee_action(device, action, params)

            return AgentResult(
                spoken_response=self._format_light_response(action, params, language),
                success=True,
            )

        # Fallback to Home Assistant if no Govee client
        if self._ha_client:
            # ... existing HA logic ...
            pass

        return AgentResult(
            spoken_response=self._no_integration_response(language),
            success=False,
        )

    async def _execute_govee_action(
        self,
        device: GoveeDevice,
        action: str,
        params: dict,
    ) -> bool:
        if action == "turn_on":
            return await self._govee_client.turn_on(device.device_id, device.model)
        elif action == "turn_off":
            return await self._govee_client.turn_off(device.device_id, device.model)
        elif action == "dim":
            brightness = params.get("brightness", 50)
            return await self._govee_client.set_brightness(device.device_id, device.model, brightness)
        elif action == "set_color":
            color = params.get("color")
            if color:
                r, g, b = self._parse_color(color)
                return await self._govee_client.set_color(device.device_id, device.model, r, g, b)
        return False

    def _filter_devices(
        self,
        devices: list[GoveeDevice],
        room: str | None,
        device_name: str | None,
    ) -> list[GoveeDevice]:
        """Filter devices by room or name."""
        if not room and not device_name:
            # Control all devices
            return [d for d in devices if d.controllable]

        # Match by name (fuzzy)
        target = (room or device_name or "").lower()
        return [
            d for d in devices
            if d.controllable and target in d.name.lower()
        ]

    def _parse_color(self, color: str) -> tuple[int, int, int]:
        """Parse color name or hex to RGB."""
        color_map = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "white": (255, 255, 255),
            "warm": (255, 180, 100),
            "cool": (200, 220, 255),
            "orange": (255, 140, 0),
            "purple": (128, 0, 128),
            "pink": (255, 105, 180),
            "yellow": (255, 255, 0),
        }
        if color.lower() in color_map:
            return color_map[color.lower()]
        # Try hex
        if color.startswith("#"):
            color = color[1:]
        if len(color) == 6:
            return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
        return (255, 255, 255)  # Default white
```

---

## Intent Parser Updates

Update `src/brain/intent_parser.py`:

### Scene Keywords

```python
INTENT_KEYWORDS[Intent.SMART_HOME]["en"].extend([
    r"\b(cozy|focus|movie|alarm)\s+(mode|scene|lighting)\b",
    r"\bset\s+(the\s+)?lights?\s+to\s+(cozy|focus|movie|alarm)\b",
    r"\b(cozy|focus|movie|alarm)\s+lights?\b",
])

INTENT_KEYWORDS[Intent.SMART_HOME]["de"].extend([
    r"\b(gemütlich|fokus|film|alarm)\s+(modus|szene|beleuchtung)\b",
    r"\bstell(e)?\s+(die\s+)?lichter?\s+auf\s+(gemütlich|fokus|film|alarm)\b",
    r"\b(gemütliche?|fokus|film|alarm)\s+beleuchtung\b",
])
```

### Scene Parameter Extraction

```python
def _extract_smart_home_params(self, text: str) -> dict[str, Any]:
    # ... existing logic ...

    # Check for scene
    scene_map = {
        "cozy": "cozy", "gemütlich": "cozy",
        "focus": "focus", "fokus": "focus",
        "movie": "movie", "film": "movie",
        "alarm": "alarm",
    }
    for keyword, scene in scene_map.items():
        if keyword in text:
            params["scene"] = scene
            params["action"] = "scene"
            break

    # Check for color
    color_keywords = [
        "red", "green", "blue", "white", "warm", "cool",
        "orange", "purple", "pink", "yellow",
        "rot", "grün", "blau", "weiß", "warm", "kalt",
        "orange", "lila", "rosa", "gelb",
    ]
    for color in color_keywords:
        if color in text:
            params["color"] = color
            params["action"] = "set_color"
            break

    return params
```

---

## State Broadcast Loop

Add to `src/api/ws_server.py`:

```python
# Global
_govee_client: GoveeClient | None = None

async def _govee_state_loop() -> None:
    """Background task to broadcast Govee device states."""
    global _govee_client

    if not _govee_client:
        return

    poll_interval = 10  # seconds, from config

    while True:
        try:
            states = await _govee_client.get_all_states()
            devices = [
                {
                    "id": s.device_id,
                    "name": s.name,
                    "on": s.power_state,
                    "brightness": s.brightness,
                    "color": s.color,
                }
                for s in states
            ]

            # Determine active scene (if all devices match a scene config)
            active_scene = _detect_active_scene(states)

            await _broadcast(json.dumps({
                "type": "govee_state",
                "payload": {
                    "devices": devices,
                    "active_scene": active_scene,
                },
            }))
        except Exception as e:
            logger.error(f"Error polling Govee state: {e}")

        await asyncio.sleep(poll_interval)

def _detect_active_scene(states: list[GoveeDeviceState]) -> str | None:
    """Detect if current state matches a configured scene."""
    # Implementation: compare brightness/color to scene configs
    # Return scene name if match, None otherwise
    return None
```

### Command Handler

```python
async def _handle_govee_command(data: dict[str, Any]) -> None:
    """Handle govee_cmd WebSocket message."""
    global _govee_client

    if not _govee_client:
        return

    payload = data.get("payload", {})
    device_id = payload.get("device_id")
    action = payload.get("action")
    value = payload.get("value")

    # Find device model
    devices = await _govee_client.get_devices()
    device = next((d for d in devices if d.device_id == device_id), None)
    if not device:
        return

    if action == "on":
        await _govee_client.turn_on(device_id, device.model)
    elif action == "off":
        await _govee_client.turn_off(device_id, device.model)
    elif action == "brightness":
        await _govee_client.set_brightness(device_id, device.model, int(value))
    elif action == "color":
        # value is hex string
        r, g, b = int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
        await _govee_client.set_color(device_id, device.model, r, g, b)
    elif action == "scene":
        await _govee_client.apply_scene(value)
```

---

## LightsPanel (`frontend/src/components/panels/LightsPanel.tsx`)

```typescript
import { PanelBase } from './PanelBase';
import { useGovee } from '../../hooks/useGovee';

export function LightsPanel() {
  const { state, loading, error, sendCommand } = useGovee();

  return (
    <PanelBase title="LIGHTS" icon={<LightbulbIcon />} loading={loading} error={error}>
      {/* Scene buttons */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '8px',
          marginBottom: '16px',
        }}
      >
        {['cozy', 'focus', 'movie', 'alarm'].map((scene) => (
          <SceneButton
            key={scene}
            scene={scene}
            active={state?.active_scene === scene}
            onClick={() => sendCommand({ action: 'scene', value: scene })}
          />
        ))}
      </div>

      {/* Device list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {state?.devices.map((device) => (
          <DeviceRow
            key={device.id}
            device={device}
            onToggle={() => sendCommand({
              device_id: device.id,
              action: device.on ? 'off' : 'on',
            })}
            onBrightness={(value) => sendCommand({
              device_id: device.id,
              action: 'brightness',
              value,
            })}
          />
        ))}
      </div>
    </PanelBase>
  );
}

interface SceneButtonProps {
  scene: string;
  active: boolean;
  onClick: () => void;
}

function SceneButton({ scene, active, onClick }: SceneButtonProps) {
  const colors: Record<string, string> = {
    cozy: '#ff8c42',
    focus: '#ffffff',
    movie: '#1a1a2e',
    alarm: '#ff0000',
  };

  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 12px',
        background: active ? 'var(--accent)' : 'transparent',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--panel-border)'}`,
        borderRadius: '4px',
        color: active ? 'var(--bg)' : 'var(--text)',
        fontSize: '11px',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '1px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
      }}
    >
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '2px',
          background: colors[scene],
        }}
      />
      {scene}
    </button>
  );
}

interface DeviceRowProps {
  device: { id: string; name: string; on: boolean; brightness: number; color: string };
  onToggle: () => void;
  onBrightness: (value: number) => void;
}

function DeviceRow({ device, onToggle, onBrightness }: DeviceRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '8px 0',
        borderBottom: '1px solid var(--panel-border)',
      }}
    >
      {/* Color indicator */}
      <span
        style={{
          width: '12px',
          height: '12px',
          borderRadius: '2px',
          background: device.on ? device.color : 'var(--text-muted)',
          opacity: device.on ? 1 : 0.3,
        }}
      />

      {/* Name */}
      <span
        style={{
          flex: 1,
          fontSize: '12px',
          color: device.on ? 'var(--text)' : 'var(--text-muted)',
        }}
      >
        {device.name}
      </span>

      {/* Brightness slider (only when on) */}
      {device.on && (
        <input
          type="range"
          min="1"
          max="100"
          value={device.brightness}
          onChange={(e) => onBrightness(parseInt(e.target.value))}
          style={{
            width: '60px',
            accentColor: 'var(--accent)',
          }}
        />
      )}

      {/* Power toggle */}
      <button
        onClick={onToggle}
        style={{
          width: '32px',
          height: '20px',
          borderRadius: '10px',
          border: 'none',
          background: device.on ? 'var(--accent)' : 'var(--panel-border)',
          cursor: 'pointer',
          position: 'relative',
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: '2px',
            left: device.on ? '14px' : '2px',
            width: '16px',
            height: '16px',
            borderRadius: '8px',
            background: 'var(--text)',
            transition: 'left 150ms',
          }}
        />
      </button>
    </div>
  );
}

function LightbulbIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.9V17h8v-2.1A7 7 0 0 0 12 2z" />
    </svg>
  );
}

export default LightsPanel;
```

---

## useGovee Hook (`frontend/src/hooks/useGovee.ts`)

```typescript
import { useState, useEffect, useCallback } from 'react';
import { GoveeState } from '../types';

interface GoveeCommand {
  device_id?: string;
  action: 'on' | 'off' | 'brightness' | 'color' | 'scene';
  value?: unknown;
}

interface UseGoveeResult {
  state: GoveeState | null;
  loading: boolean;
  error: string | null;
  sendCommand: (cmd: GoveeCommand) => void;
}

export function useGovee(wsRef: React.RefObject<WebSocket | null>): UseGoveeResult {
  const [state, setState] = useState<GoveeState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ws = wsRef.current;
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'govee_state') {
          setState(msg.payload);
          setLoading(false);
          setError(null);
        }
      } catch {
        // Ignore binary messages
      }
    };

    ws.addEventListener('message', handleMessage);
    return () => ws.removeEventListener('message', handleMessage);
  }, [wsRef]);

  const sendCommand = useCallback(
    (cmd: GoveeCommand) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      ws.send(JSON.stringify({
        type: 'govee_cmd',
        payload: cmd,
      }));
    },
    [wsRef]
  );

  return { state, loading, error, sendCommand };
}
```

---

## Configuration

### config.yaml

```yaml
govee:
  enabled: false              # Enable after API key setup
  api_mode: "cloud"           # Only "cloud" supported in MVP
  poll_interval_seconds: 10   # How often to fetch device states
  scenes:
    cozy:
      brightness: 40
      color: "#ff8c42"        # Warm orange
    focus:
      brightness: 80
      color: "#ffffff"        # Bright white
    movie:
      brightness: 15
      color: "#1a1a2e"        # Dim blue
    alarm:
      brightness: 100
      color: "#ff0000"        # Bright red
      blink: true             # Future: blink effect
```

### .env.example

```bash
# Govee Developer API
# Obtain from Govee mobile app: Settings → About → Apply for API Key
GOVEE_API_KEY=your_govee_api_key
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | GoveeClient initializes with valid API key | Unit test with mocked API |
| 2 | "Turn on the lights" turns on all Govee devices | Integration test |
| 3 | "Turn off office lights" targets devices with "office" in name | Integration test |
| 4 | "Set lights to cozy" applies cozy scene config | Integration test |
| 5 | "Dim the lights to 50%" sets brightness to 50 | Integration test |
| 6 | "Set lights to red" sets RGB color | Integration test |
| 7 | LightsPanel displays all devices with correct states | Visual inspection |
| 8 | Scene buttons work from panel | Visual inspection |
| 9 | Device toggle works from panel | Visual inspection |
| 10 | Brightness slider updates device | Visual inspection |
| 11 | German voice commands work | Integration test |
| 12 | govee_state WS message broadcasts every 10s | Unit test |
| 13 | No crash when Govee API key missing | Integration test |
| 14 | Rate limiting respected (100 req/min) | Unit test |
| 15 | Offline devices shown as offline in panel | Visual inspection |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/integrations/govee/__init__.py` | Package init |
| `src/integrations/govee/client.py` | GoveeClient |
| `frontend/src/components/panels/LightsPanel.tsx` | Panel component |
| `frontend/src/hooks/useGovee.ts` | Govee state hook |
| `tests/integrations/govee/test_client.py` | Client tests |

## Files Modified

| File | Change |
|------|--------|
| `src/brain/agents/smart_home_agent.py` | Add Govee integration |
| `src/brain/intent_parser.py` | Add scene keywords |
| `src/api/ws_server.py` | Add govee_state_loop, govee_cmd handler |
| `src/main.py` | Initialize GoveeClient |
| `config/config.yaml` | Add govee section |
| `.env.example` | Add GOVEE_API_KEY |

---

## Dependencies

### pip packages
```
httpx>=0.24.0  # Already in requirements.txt
```

No new packages required.

---

## Implementation Plan

### Batch 1 — Backend client
1. `code` → Create `src/integrations/govee/__init__.py`
2. `code` → Create `src/integrations/govee/client.py`
3. `test` → Create `tests/integrations/govee/test_client.py`
4. `review` → Review batch 1

### Batch 2 — Agent integration
5. `code` → Update `src/brain/agents/smart_home_agent.py` with Govee support
6. `code` → Update `src/brain/intent_parser.py` with scene keywords
7. `test` → Update SmartHomeAgent tests
8. `review` → Review batch 2

### Batch 3 — WS integration
9. `code` → Update `src/api/ws_server.py` with state loop and command handler
10. `code` → Update `src/main.py` to initialize GoveeClient
11. `code` → Add config section
12. `test` → Integration tests
13. `review` → Review batch 3

### Batch 4 — Frontend
14. `design` → Create `frontend/src/hooks/useGovee.ts`
15. `design` → Create `frontend/src/components/panels/LightsPanel.tsx`
16. `test` → Frontend tests
17. `review` → Final review

---

## Rejected Alternatives

### Alexa Smart Home Skill
- Requires AWS Lambda deployment
- Adds cloud dependency and latency
- User currently uses Alexa — we want to replace, not proxy

### iCUE/Corsair SDK
- C++ only, no Python bindings
- Only controls Corsair devices, not Govee
- Would require separate integration

~~### Govee LAN API~~ — NOW IN SCOPE (see Revision 2)

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision adds Govee LAN API support alongside Cloud API in MVP with transparent fallback logic.

### API Strategy: Cloud Primary + LAN Preferred

MVP supports BOTH Govee Cloud API AND LAN API:

- **Cloud API**: Primary path, always available
- **LAN API**: Preferred low-latency path when device/firmware supports it
- **Transparent fallback**: If LAN fails or device doesn't support it, fall back to Cloud automatically

### Firmware Support Detection

On initialization, `GoveeClient` queries each device for LAN capability:

```python
@dataclass
class GoveeDevice:
    device_id: str
    model: str
    name: str
    controllable: bool
    retrievable: bool
    support_cmds: list[str]
    supports_lan: bool = False  # NEW: LAN capability flag
    lan_ip: str | None = None   # NEW: Device IP for LAN control
```

Detection logic:
1. Query Cloud API for device list
2. Attempt LAN discovery via UDP multicast
3. Match discovered LAN devices to Cloud device list by MAC
4. Set `supports_lan=True` for matched devices

### Fallback Logic

```python
async def _send_command(self, device: GoveeDevice, cmd: dict) -> bool:
    """Send command with LAN-preferred fallback to Cloud."""
    if device.supports_lan and self._config.get("api_mode") != "cloud":
        try:
            return await self._send_lan_command(device, cmd)
        except (LanTimeoutError, LanUnavailableError) as e:
            logger.warning(f"LAN failed for {device.name}: {e}, falling back to Cloud")
    
    return await self._send_cloud_command(device, cmd)
```

### LAN API Implementation

#### Protocol
- UDP multicast discovery on port 4001
- Device control via UDP on port 4003
- JSON payloads similar to Cloud API

#### Discovery
```python
async def discover_lan_devices(self, timeout: float = 2.0) -> list[LanDevice]:
    """Discover Govee devices on local network via UDP multicast.
    
    Args:
        timeout: Seconds to wait for responses
        
    Returns:
        List of discovered LAN devices
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    
    # Send discovery packet
    discovery_msg = json.dumps({
        "msg": {
            "cmd": "scan",
            "data": {"account_topic": "reserve"}
        }
    }).encode()
    sock.sendto(discovery_msg, ("239.255.255.250", 4001))
    
    # Collect responses
    devices = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(1024)
            device_info = json.loads(data.decode())
            devices.append(LanDevice(
                ip=addr[0],
                device_id=device_info["msg"]["data"]["device"],
                model=device_info["msg"]["data"]["sku"],
            ))
        except socket.timeout:
            break
    
    return devices
```

#### LAN Command Format
```json
{
  "msg": {
    "cmd": "turn",
    "data": {
      "value": 1
    }
  }
}
```

### Config — Updated

```yaml
govee:
  enabled: false
  api_mode: "auto"  # "auto" (LAN preferred, Cloud fallback) | "cloud" | "lan"
  lan_timeout_ms: 500  # timeout before falling back to cloud
  lan_discovery_on_startup: true  # discover LAN devices at startup
  poll_interval_seconds: 10
  scenes:
    cozy:
      brightness: 40
      color: "#ff8c42"
    focus:
      brightness: 80
      color: "#ffffff"
    movie:
      brightness: 15
      color: "#1a1a2e"
    alarm:
      brightness: 100
      color: "#ff0000"
```

### GoveeClient — Extended Methods

```python
class GoveeClient:
    # ... existing methods ...

    async def _send_lan_command(self, device: GoveeDevice, cmd: dict) -> bool:
        """Send command via LAN API.
        
        Args:
            device: Target device with lan_ip set
            cmd: Command payload
            
        Returns:
            True if successful
            
        Raises:
            LanTimeoutError: If device doesn't respond
            LanUnavailableError: If LAN not available for device
        """
        if not device.lan_ip:
            raise LanUnavailableError(f"No LAN IP for {device.name}")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self._config.get("lan_timeout_ms", 500) / 1000)
        
        msg = json.dumps({"msg": cmd}).encode()
        sock.sendto(msg, (device.lan_ip, 4003))
        
        try:
            response, _ = sock.recvfrom(1024)
            return True
        except socket.timeout:
            raise LanTimeoutError(f"LAN timeout for {device.name}")


class LanTimeoutError(Exception):
    """Raised when LAN command times out."""
    pass


class LanUnavailableError(Exception):
    """Raised when LAN is not available for device."""
    pass
```

### Acceptance Criteria — Extended

| # | Criterion | Verification |
|---|-----------|--------------|
| 16 | LAN discovery finds local Govee devices | Integration test |
| 17 | LAN command succeeds when device supports it | Integration test |
| 18 | Cloud fallback triggers on LAN timeout | Unit test |
| 19 | api_mode: "cloud" skips LAN entirely | Unit test |
| 20 | api_mode: "lan" fails if no LAN support | Unit test |

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — Full OpenClaw Adoption (2026-04-16)

### Decisions Applied
1. **OpenClaw as full backbone WHERE IT HAS COVERAGE** — Govee has NO OpenClaw skill
2. **JARVIS-native implementation required** — Full GoveeClient retained

### Integration Assessment
**This spec is FULLY JARVIS-native — OpenClaw has NO Govee integration.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| Govee Cloud API | No built-in skill | None |
| Govee LAN API | No built-in skill | None |
| Device control | No built-in skill | None |
| Scene application | No built-in skill | None |
| Device state polling | No equivalent | None |

### What JARVIS-Native Implements (Full Spec)
- **GoveeClient** — Cloud + LAN API wrapper (complete implementation)
- **SmartHomeAgent (Govee extension)** — Voice command handling
- **LightsPanel** — HUD visualization of device states
- **State polling loop** — Real-time device sync for frontend
- **Scene system** — config.yaml scene definitions
- **Intent parsing** — SMART_HOME intent with Govee routing

### Voice Command Routing
Despite OpenClaw being the backbone, Govee commands stay JARVIS-native:
```
Voice: "Turn on the office lights"
       ↓
[Intent Parser] → SMART_HOME intent, domain=light
       ↓
[Orchestrator] → Routes to SmartHomeAgent (JARVIS-native)
       ↓
[SmartHomeAgent] → GoveeClient.turn_on()
       ↓
[LightsPanel] → Updated via govee_state WS message
```

### Files Created — FULL SPEC
| File | Purpose | Status |
|------|---------|--------|
| `src/integrations/govee/__init__.py` | Package init | KEEP |
| `src/integrations/govee/client.py` | GoveeClient (Cloud + LAN) | KEEP |
| `frontend/src/components/panels/LightsPanel.tsx` | Panel component | KEEP |
| `frontend/src/hooks/useGovee.ts` | Govee state hook | KEEP |
| `tests/integrations/govee/test_client.py` | Client tests | KEEP |

### Files Modified — FULL SPEC
| File | Change | Status |
|------|--------|--------|
| `src/brain/agents/smart_home_agent.py` | Add Govee integration | KEEP |
| `src/brain/intent_parser.py` | Add scene keywords | KEEP |
| `src/api/ws_server.py` | govee_state_loop, govee_cmd handler | KEEP |
| `config/config.yaml` | Add govee section | KEEP |

### Implementation Reduction
**Original estimate:** 6-8 hours
**With OpenClaw:** 6-8 hours (no reduction — fully native)
**Reduction:** 0%

### Future: Optional OpenClaw Skill Contribution
Consider contributing a Govee skill to ClawHub in Phase B:
- Wraps JARVIS GoveeClient
- Enables OpenClaw-native routing
- Not MVP scope

### Prerequisites
- None (standalone JARVIS-native implementation)

### Cross-References
- `openclaw-integration.md` — OpenClaw backbone, but Govee is exception
- `hud-panel-framework.md` — LightsPanel integration
