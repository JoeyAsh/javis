# Feature Spec: JARVIS HUD Epic

## Summary
Transform JARVIS from a voice-only assistant into a full Iron Man-style HUD OS tailored for a software engineer. The orb remains the visual centerpiece, but panels float around it providing real-time information: calendar, email, Spotify playback, Govee lighting, GitHub notifications, Docker containers, system metrics, and proactive JARVIS interjections.

## Goals
- Deliver an immersive, cinematic HUD experience reminiscent of Tony Stark's JARVIS interface
- Integrate Spotify for music control and ambient awareness
- Integrate Govee LEDs for ambient lighting control and scene automation
- Provide developer-centric panels: GitHub, Docker, CI builds, system monitoring
- Implement Iron Man JARVIS persona: British butler register, dry wit, proactive, respectful pushback
- Maintain async-first architecture and clean separation of concerns
- Support desktop-first layout with graceful tablet/phone fallback

## Non-Goals
- "Werkstatt" (workshop) or weapons systems from the movies — civilian/SE focus only
- Mobile-native app (web PWA is acceptable)
- Real-time video/camera feeds
- Multi-user session isolation (JARVIS is single-user)
- VR/AR headset integration (future epic)

---

## Design Language

### HUD Aesthetic
The interface follows the existing JARVIS design system with these HUD-specific extensions:

```css
/* Extend existing CSS variables in index.css */
--panel-bg:        rgba(13,13,20,0.75);
--panel-border:    rgba(26,26,46,0.8);
--panel-glow:      0 0 20px rgba(76,168,232,0.15);
--danger:          #e84c4c;
--warning:         #e8a84c;
--success:         #4ce88a;
--info:            #4ca8e8;
```

### Panel Base Styling
All panels share these visual properties:
- Background: `var(--panel-bg)` with `backdrop-filter: blur(12px)`
- Border: `1px solid var(--panel-border)`
- Border-radius: `4px` (never exceed)
- Box-shadow: `var(--panel-glow)` (subtle, not overwhelming)
- Font: JetBrains Mono throughout
- Headers: uppercase, letter-spacing 2px, font-size 10px, color `var(--text-muted)`
- Content: font-size 12-14px, color `var(--text)`
- Minimum touch target: 44px for interactive elements

### Orb-Panel Relationship
- Orb remains fullscreen canvas at z-index 0
- Panels float at z-index 10-20, positioned around the orb
- Panels never obscure the orb center (reserved 40% viewport center)
- Panels fade to 30% opacity when orb is in `speaking` state (attention focus)
- Panels restore full opacity after 300ms crossfade when orb returns to `idle`

---

## Panel System Architecture

### Layout Strategy
**Decision: Fixed opinionated layout** (not user-draggable for MVP)

**Rationale:**
- Simpler implementation; no `react-grid-layout` dependency
- Guarantees cinematic balance (panels arranged symmetrically around orb)
- Consistent experience across sessions
- Drag-and-drop can be Phase B enhancement

**Desktop Layout (>1280px):**
```
┌──────────────────────────────────────────────────────────────────┐
│ [SystemPanel]                                     [NotifPanel]   │
│                                                                  │
│ [AgendaPanel]            [ ORB CENTER ]           [DevPanel]     │
│ [MailPanel]                                       [DevPanel]     │
│                                                                  │
│ [LightsPanel]                                     [NowPlaying]   │
│ [TranscriptPanel]                    [StatusText] [SelfFixPanel] │
└──────────────────────────────────────────────────────────────────┘
```

**Tablet Layout (768-1280px):**
- Left column: SystemPanel, AgendaPanel, MailPanel, LightsPanel
- Right column: NotifPanel, DevPanel, NowPlayingPanel
- Orb scales to 60% of viewport width
- TranscriptPanel moves below orb

**Mobile Layout (<768px):**
- Orb fullscreen, panels hidden by default
- Swipe-up drawer reveals panel stack (vertical scroll)
- Only essential panels shown: SystemPanel, NowPlayingPanel, NotifPanel

### Panel Lifecycle
Each panel:
1. Mounts lazily when its data source is available
2. Subscribes to its specific WS message type(s)
3. Shows skeleton/loading state until first data arrives
4. Gracefully handles disconnection (shows "offline" badge)
5. Unmounts cleanly, unsubscribing from WS

---

## WebSocket Message Types (New)

All new messages use the existing `{"type": <str>, "payload": <dict>}` envelope.

### From Backend to Frontend

| Type | Payload | Source |
|------|---------|--------|
| `spotify_state` | `{ playing: bool, track: string, artist: string, album: string, album_art_url: string, progress_ms: number, duration_ms: number, device: string }` | SpotifyAgent polling |
| `govee_state` | `{ devices: [{ id: string, name: string, on: bool, brightness: number, color: string }], active_scene: string \| null }` | GoveeAgent polling |
| `agenda` | `{ events: [{ id: string, title: string, start: ISO8601, end: ISO8601, calendar: string, location?: string }] }` | CalendarAgent (personal-assistant-epic) |
| `mail` | `{ unread_count: number, messages: [{ id: string, from: string, subject: string, snippet: string, date: ISO8601, is_vip: bool }] }` | EmailAgent (personal-assistant-epic) |
| `dev_toolkit` | `{ github: { notifications: number, prs_to_review: number }, repos: [{ path: string, branch: string, dirty: bool, ahead: number, behind: number }], docker: [{ id: string, name: string, status: string, cpu: number, mem: number }], ci: [{ repo: string, workflow: string, status: string, url: string }] }` | DevToolkitAgent |
| `notification` | `{ id: string, message: string, severity: "info" \| "warning" \| "urgent", spoken: bool, timestamp: ISO8601 }` | ProactiveScheduler |
| `transcript` | (existing) `{ role: "user" \| "jarvis", text: string }` | ws_server |
| `system` | (existing) `{ cpu: number, mem: number, uptime: string }` + new fields `{ gpu_util?: number, gpu_temp?: number, cpu_temp?: number, network_up: number, network_down: number }` | ws_server extended |
| `self_fix_*` | (from claude-code-integration.md) | SelfDebugAgent |

### From Frontend to Backend

| Type | Payload | Handler |
|------|---------|---------|
| `spotify_cmd` | `{ action: "play" \| "pause" \| "next" \| "prev" \| "volume", value?: number }` | SpotifyAgent |
| `govee_cmd` | `{ device_id: string, action: "on" \| "off" \| "brightness" \| "color" \| "scene", value?: any }` | GoveeAgent |
| `dismiss_notification` | `{ id: string }` | ProactiveScheduler |

**Total new WS message types: 9 incoming, 3 outgoing = 12 new types**

---

## Cross-Cutting Dependencies

### Integration Layer
The HUD epic shares the `src/integrations/` directory established by personal-assistant-epic:

```
src/integrations/
  __init__.py
  # google/ — REMOVED (OpenClaw handles Gmail + Calendar)
  # icloud/ — REMOVED (iCloud dropped entirely)
  # calendar/ — REMOVED (OpenClaw handles)
  openclaw/         # NEW - OpenClaw client
    __init__.py
    client.py       # OpenClaw gateway client
  spotify/          # NEW - state polling only (control via OpenClaw)
    __init__.py
    client.py       # spotipy wrapper (read-only state)
  govee/            # NEW - JARVIS-native (no OpenClaw skill)
    __init__.py
    client.py       # httpx REST client + LAN UDP
  # github/ — REMOVED (OpenClaw handles)
  docker/           # NEW - JARVIS-native (local monitoring)
    __init__.py
    client.py       # docker-py wrapper
  system/           # NEW - JARVIS-native (local metrics)
    __init__.py
    metrics.py      # psutil + GPUtil collector
```

### Agents
```
src/brain/agents/
  # spotify_agent.py — REMOVED (OpenClaw handles control)
  # govee_agent.py — REMOVED (extend SmartHomeAgent instead)
  dev_toolkit_agent.py  # NEW - local operations only (Docker, repos, metrics)
  smart_home_agent.py   # MODIFIED - add Govee support
```

### Persona and Proactive System
```
src/brain/
  # persona.py — REMOVED (SOUL.md in OpenClaw workspace)
  salutation.py         # NEW - runtime salutation selection
  proactive.py          # NEW - event scheduler + interjection logic
```

### Event Bus
```
src/utils/
  events.py             # NEW - asyncio pub/sub for proactive triggers
```

### Frontend
```
frontend/src/
  components/
    panels/             # NEW directory
      PanelBase.tsx     # Shared panel wrapper
      AgendaPanel.tsx
      MailPanel.tsx
      NowPlayingPanel.tsx
      LightsPanel.tsx
      SystemPanel.tsx
      DevPanel.tsx
      NotificationsPanel.tsx
      TranscriptPanel.tsx  # Restore deleted component
      SelfFixPanel.tsx     # (from claude-code-integration.md)
    HudLayout.tsx       # Panel grid orchestrator
  hooks/
    useSpotify.ts
    useGovee.ts
    useAgenda.ts
    useMail.ts
    useDevToolkit.ts
    useNotifications.ts
    useSelfFix.ts       # (from claude-code-integration.md)
```

---

## Configuration Schema

### config.yaml additions
```yaml
hud:
  enabled: true
  layout: "desktop"           # desktop | tablet | mobile | auto
  panel_opacity_idle: 1.0
  panel_opacity_speaking: 0.3
  panel_fade_duration_ms: 300

persona:
  enabled: true
  salutation: "Sir"           # "Sir" | user's first name | custom string
  style: "jarvis"             # jarvis | formal | casual
  proactive_interjections: true
  language_style:
    en: british_formal
    de: formal_sie            # use "Sie" form in German

spotify:
  enabled: false              # requires user setup
  poll_interval_seconds: 5
  show_album_art: true

govee:
  enabled: false              # requires user setup
  api_mode: "cloud"           # cloud | lan (lan requires firmware support)
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
      blink: true

dev_toolkit:
  enabled: true
  github:
    enabled: false            # requires GITHUB_TOKEN
    poll_interval_seconds: 60
    watched_repos: []         # ["owner/repo", ...] or empty for all
  repo_watcher:
    enabled: true
    poll_interval_seconds: 30
    watched_paths: []         # ["/path/to/repo", ...] configured by user
  docker:
    enabled: true
    poll_interval_seconds: 15
  system_monitor:
    enabled: true
    poll_interval_seconds: 5
    show_gpu: true
    show_network: true
    show_temps: true

proactive:
  enabled: true
  triggers:
    meeting_reminder:
      enabled: true
      advance_minutes: [10, 5]  # remind at 10min and 5min before
      voice: true
    vip_mail:
      enabled: true
      vip_contacts: []          # ["boss@example.com", ...] — empty = disabled
      voice: true
    dirty_repo:
      enabled: true
      idle_minutes: 30          # warn if uncommitted changes after N min idle
      voice: false              # notification only, no voice
    system_alert:
      enabled: true
      cpu_threshold: 90
      gpu_temp_threshold: 85
      voice: true
```

### .env.example additions
```bash
# Spotify OAuth
SPOTIFY_CLIENT_ID=...
SPOTIFY_REDIRECT_URI=http://localhost:8766/callback/spotify
# Note: SPOTIFY_CLIENT_SECRET optional with PKCE flow
# Token cache stored at ~/.jarvis/spotify_token.json

# Govee Developer API
GOVEE_API_KEY=...              # obtain from Govee mobile app

# GitHub Personal Access Token
GITHUB_TOKEN=ghp_...           # scopes: notifications, repo, read:user
```

---

## Dependencies Between Sub-Specs

```
jarvis-persona.md
       |
       +---> (applies to all voice responses via ChatAgent system prompt)

hud-panel-framework.md
       |
       +---> spotify-integration.md
       |           |
       |           +---> NowPlayingPanel (depends on panel framework)
       |
       +---> govee-led-integration.md
       |           |
       |           +---> LightsPanel (depends on panel framework)
       |
       +---> dev-toolkit-panels.md
                   |
                   +---> DevPanel, SystemPanel (depends on panel framework)

personal-assistant-epic.md (existing, parallel track)
       |
       +---> AgendaPanel, MailPanel (consume calendar/email data layers)

claude-code-integration.md (existing, parallel track)
       |
       +---> SelfFixPanel (integrated into HUD layout)
```

**Implementation Order:**
1. `jarvis-persona.md` — can start immediately (no dependencies)
2. `hud-panel-framework.md` — can start immediately (no dependencies)
3. `spotify-integration.md` — after panel framework base is ready
4. `govee-led-integration.md` — after panel framework base is ready
5. `dev-toolkit-panels.md` — after panel framework base is ready
6. HUD integration of AgendaPanel/MailPanel — after personal-assistant-epic completes
7. HUD integration of SelfFixPanel — after claude-code-integration completes

Steps 3, 4, 5 can run in parallel once step 2 completes.

---

## Acceptance Criteria (Epic Level)

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | JARVIS responds in British butler register with dry wit when persona.enabled: true | Manual test: ask a question, verify response style |
| 2 | JARVIS uses configured salutation ("Sir" or custom) | Manual test: verify greeting |
| 3 | All HUD panels render on desktop with correct layout | Visual inspection at 1920x1080 |
| 4 | Panels fade to 30% opacity when orb enters speaking state | Visual inspection |
| 5 | Spotify NowPlayingPanel shows current track with album art | Integration test with mocked Spotify API |
| 6 | Spotify play/pause/next/prev controls work from panel | Integration test |
| 7 | Govee LightsPanel shows device states and toggles work | Integration test with mocked Govee API |
| 8 | Govee scene buttons apply configured color/brightness | Integration test |
| 9 | DevPanel shows GitHub notification count | Integration test with mocked GitHub API |
| 10 | DevPanel shows local repo dirty/clean status | Integration test with mocked git commands |
| 11 | DevPanel shows Docker container list and status | Integration test with mocked docker-py |
| 12 | SystemPanel shows extended metrics (GPU, temps, network) | Unit test for metric collection |
| 13 | Proactive meeting reminder triggers 10 min before event | Unit test for proactive scheduler |
| 14 | VIP mail notification appears in NotificationsPanel | Integration test |
| 15 | All new WS message types are handled without frontend crash | Unit tests for WS message parsing |
| 16 | Tablet layout collapses to 2-column correctly | Visual inspection at 1024x768 |
| 17 | German language persona maintains formal register | Manual test with language=de |
| 18 | All panels show "offline" state gracefully on WS disconnect | Integration test |

---

## Files Modified (Epic Level)

| File | Change |
|------|--------|
| `src/brain/intent_parser.py` | Add SPOTIFY, GOVEE, DEV_TOOLKIT intents |
| `src/brain/orchestrator.py` | Register new agents |
| `src/brain/agents/chat_agent.py` | Load persona prompt |
| `src/api/ws_server.py` | Add broadcast functions for new message types |
| `src/main.py` | Initialize proactive scheduler |
| `config/config.yaml` | Add hud, persona, spotify, govee, dev_toolkit, proactive sections |
| `.env.example` | Add Spotify, Govee, GitHub credentials |
| `requirements.txt` | Add spotipy, docker, PyGithub, GPUtil/pynvml |
| `frontend/src/index.css` | Add HUD CSS variables |
| `frontend/src/types.ts` | Add new WS message types |
| `frontend/src/App.tsx` | Integrate HudLayout |
| `frontend/src/hooks/useWebSocket.ts` | Handle new message types |

## Files Created (Epic Level)

| File | Purpose |
|------|---------|
| `src/brain/persona.py` | Persona prompt + voice style |
| `src/brain/proactive.py` | Proactive event scheduler |
| `src/utils/events.py` | Asyncio pub/sub event bus |
| `src/integrations/spotify/__init__.py` | Spotify package |
| `src/integrations/spotify/client.py` | Spotipy wrapper |
| `src/integrations/govee/__init__.py` | Govee package |
| `src/integrations/govee/client.py` | Govee REST client |
| `src/integrations/github/__init__.py` | GitHub package |
| `src/integrations/github/client.py` | PyGithub wrapper |
| `src/integrations/docker/__init__.py` | Docker package |
| `src/integrations/docker/client.py` | docker-py wrapper |
| `src/brain/agents/spotify_agent.py` | Spotify agent |
| `src/brain/agents/govee_agent.py` | Govee agent |
| `src/brain/agents/dev_toolkit_agent.py` | Dev toolkit agent |
| `frontend/src/components/panels/PanelBase.tsx` | Shared panel wrapper |
| `frontend/src/components/panels/*.tsx` | Individual panels (8 files) |
| `frontend/src/components/HudLayout.tsx` | Panel grid orchestrator |
| `frontend/src/hooks/use*.ts` | Panel data hooks (6 files) |

---

## Open Questions for User

1. **HUD layout preference:** Fixed opinionated layout (spec default) or user-arrangeable drag-and-drop panels? Drag-and-drop adds `react-grid-layout` dependency and implementation complexity.

2. **HUD visibility mode:** Always-on (panels always visible), or wake-on-voice (orb-only idle state, panels fade in on activation)?

3. **Multi-monitor support:** If yes, should specific panels be assignable to secondary monitors? Or single-viewport only for MVP?

4. **Preferred salutation:** "Sir" (default), your first name, or a custom salutation? Should JARVIS ever deviate from this (e.g., "Boss" in casual mode)?

5. **Spotify Premium:** Do you have Spotify Premium? Playback control requires Premium + an active device. If not, the panel becomes read-only (no play/pause controls).

6. **Govee API path:** Cloud Developer API (default, recommended for MVP) or also LAN API path (faster, but requires device/firmware support and more complex setup)?

7. **Dev-toolkit scope for MVP:** Which of the following are must-haves vs. nice-to-haves?
   - GitHub notifications
   - PR review counter
   - Local repo watcher (dirty/ahead/behind)
   - Docker container list
   - CI build status (GitHub Actions)
   - System monitor with GPU/temps
   
8. **Proactive interjections:** Which triggers should be default-on vs. opt-in?
   - Meeting reminders (default-on?)
   - VIP mail alerts (opt-in?)
   - Dirty repo warnings (opt-in?)
   - CPU/GPU/temp alerts (default-on?)

9. **TranscriptPanel:** Should the deleted TranscriptPanel be restored as a HUD panel, or is the current minimal status text sufficient?

10. **SE-specific features:** Are there specific languages/frameworks that should get first-class support (e.g., Python package CVE alerts, NPM audit warnings), or keep the dev toolkit generic for now?

---

## Child Specs

- `.tmp/features/jarvis-persona.md` — Iron Man JARVIS personality, proactive scheduler
- `.tmp/features/hud-panel-framework.md` — Frontend grid, panel base, responsive rules
- `.tmp/features/spotify-integration.md` — Backend client + agent + NowPlayingPanel
- `.tmp/features/govee-led-integration.md` — Backend client + agent + LightsPanel
- `.tmp/features/dev-toolkit-panels.md` — GitHub + Docker + CI + SystemPanel + DevPanel

---

## Estimated Implementation Time

| Spec | Backend | Frontend | Tests | Total |
|------|---------|----------|-------|-------|
| jarvis-persona.md | 2h | — | 1h | 3h |
| hud-panel-framework.md | — | 4h | 2h | 6h |
| spotify-integration.md | 3h | 2h | 2h | 7h |
| govee-led-integration.md | 2h | 1.5h | 1.5h | 5h |
| dev-toolkit-panels.md | 4h | 3h | 2h | 9h |
| Integration + polish | 2h | 2h | 1h | 5h |
| **Total** | **13h** | **12.5h** | **9.5h** | **35h**

---

## Revision 2 — 2026-04-16

### Summary of Changes
This revision incorporates user decisions on all 10 open questions plus cross-spec coordination.

### Layout Strategy — CHANGED
**Decision REVERSED:** User chose drag-and-drop with `react-grid-layout` instead of fixed layout.

- Library: `react-grid-layout` (add to npm dependencies)
- Panels are user-arrangeable within grid constraints
- Layout persists per user in localStorage
- Rationale update: User values customization over initial simplicity

### Visibility Mode — DECIDED
**Wake-on-voice:** Orb-only when idle; panels fade in on voice activation.

- Idle state: Only orb visible at center
- On wake word / voice input: panels fade in (300ms transition)
- Panels fade out after 30s of inactivity (configurable)
- Config: `hud.visibility_mode: "wake_on_voice"` (default)

### Multi-Monitor Support — ADDED
**Supported in MVP.** Panels assignable to specific monitors; layout persists per monitor.

- Detection via `window.screen` API or Electron `screen` module
- Layout stored with monitor identifier key
- Config: `hud.multi_monitor: true`
- See `hud-panel-framework.md` Revision 2 for implementation details

### TranscriptPanel — RESTORED
TranscriptPanel is restored as a HUD panel (was previously deleted).

- Location: `frontend/src/components/panels/TranscriptPanel.tsx`
- Position: Left-bottom in default layout
- Shows conversation history as scrollable list

### New WebSocket Message Types (Gmail Send Flow)
Add to the WebSocket Message Types table:

| Type | Direction | Payload | Source |
|------|-----------|---------|--------|
| `email_draft_preview` | BE → FE | `{ draft_id: string, to: string, subject: string, body_preview: string, created_at: ISO8601 }` | EmailAgent |
| `email_send_request_confirmed` | FE → BE | `{ draft_id: string }` | Frontend user confirmation |
| `email_send_done` | BE → FE | `{ draft_id: string, success: bool, message_id?: string, error?: string }` | EmailAgent |

**Updated total: 12 incoming, 4 outgoing = 16 new types**

### Open Questions — ALL RESOLVED

1. **HUD layout preference:** ✓ RESOLVED — Drag-and-drop with `react-grid-layout`
2. **HUD visibility mode:** ✓ RESOLVED — Wake-on-voice (orb-only when idle)
3. **Multi-monitor support:** ✓ RESOLVED — Yes, supported in MVP
4. **Preferred salutation:** ✓ RESOLVED — Random per interaction between "Sir" and "Johannes" (see `jarvis-persona.md`)
5. **Spotify Premium:** ✓ RESOLVED — Yes, user has Premium
6. **Govee API path:** ✓ RESOLVED — Cloud AND LAN in MVP with transparent fallback
7. **Dev-toolkit scope:** ✓ RESOLVED — See `dev-toolkit-panels.md` for MVP/Phase B split
8. **Proactive interjections:** ✓ RESOLVED — See `jarvis-persona.md` for default-on/off list
9. **TranscriptPanel:** ✓ RESOLVED — Restored as HUD panel
10. **SE-specific features:** ✓ RESOLVED — Generic for MVP, SE-specific deferred to Phase B

### Cross-Spec Dependencies Updated
- `openclaw-integration.md` — PREREQUISITE: OpenClaw as backbone
- `jarvis-memory-db.md` — NEW spec for long-term memory (reduced scope: UI state only)
- Gmail send flow WS types must be reflected in `hud-panel-framework.md` types
- ~~`icloud-calendar-integration.md`~~ — DELETED (iCloud dropped)
- ~~`google-oauth-shared.md`~~ — SKIP (OpenClaw handles OAuth)

---

**Status:** Planned — awaiting implementation authorization

---

## OpenClaw Leverage (Revision 3 — 2026-04-16)

### Integration Assessment
**OpenClaw provides PARTIAL coverage for HUD Epic as a whole.**

### OpenClaw Coverage Summary
| Child Spec | OpenClaw Coverage | Notes |
|------------|-------------------|-------|
| jarvis-persona.md | Partial | SOUL.md for persona; proactive stays native |
| hud-panel-framework.md | None | 100% frontend, OpenClaw is backend-only |
| spotify-integration.md | Partial | Control via OpenClaw; state polling may need native |
| govee-led-integration.md | None | No OpenClaw Govee skill |
| dev-toolkit-panels.md | Partial | GitHub via OpenClaw; local monitoring stays native |

### Epic-Level Analysis

**What OpenClaw Could Replace:**
- Spotify playback control (built-in Spotify skill)
- GitHub notifications, PRs, CI status (built-in GitHub skill)
- Persona system prompt (SOUL.md)

**What Remains JARVIS-Native:**
- All HUD frontend panels and layout
- Local system monitoring (CPU, GPU, temps, network)
- Local git repository watcher
- Docker container monitoring
- Govee LED integration (no OpenClaw skill)
- Proactive interjection system (event-driven TTS)
- WebSocket protocol and message types

### Net Implementation Reduction Estimate
| Area | Reduction | Reasoning |
|------|-----------|-----------|
| Backend agents | ~35% | Spotify + GitHub replaced |
| Backend integrations | ~20% | Spotify client + GitHub client eliminated |
| Frontend | 0% | No OpenClaw equivalent |
| Proactive system | 0% | JARVIS-specific runtime |
| **Overall Epic** | **~15-20%** | Frontend dominates effort |

### Architecture With OpenClaw (Option A)
```
Voice Input
    │
    ▼
JARVIS Wake Word + STT (native)
    │
    ▼
OpenClaw Orchestrator
    ├─► spotify skill → Spotify API
    ├─► github skill → GitHub API
    ├─► gmail skill → Gmail API
    ├─► calendar skill → Google Calendar API
    └─► JARVIS bridge skill
            ├─► Govee (native GoveeClient)
            ├─► Docker (native DockerClient)
            ├─► System metrics (native collector)
            └─► Local repos (native RepoWatcher)
    │
    ▼
WebSocket → HUD Frontend (100% native)
```

### Cross-Spec OpenClaw Migration Summary
| Spec | Status |
|------|--------|
| personal-assistant-epic.md | FULL replacement possible |
| gmail-integration.md | FULL replacement |
| google-calendar-integration.md | FULL replacement |
| ~~icloud-calendar-integration.md~~ | DELETED (iCloud dropped) |
| google-oauth-shared.md | Conditional (skip if OpenClaw handles all Google) |
| spotify-integration.md | PARTIAL replacement |
| govee-led-integration.md | NONE (no OpenClaw skill) |
| dev-toolkit-panels.md | PARTIAL (GitHub yes, local no) |
| jarvis-memory-db.md | MOSTLY native |
| claude-code-integration.md | NONE (architectural mismatch) |
| jarvis-persona.md | PARTIAL (persona yes, proactive no) |
| hud-panel-framework.md | NONE (frontend) |

### Recommendation
Adopt **Option A (OpenClaw as backbone)** for maximum leverage:
- Gmail, Calendar, Spotify, GitHub → OpenClaw skills
- Govee, Docker, System, Repos → JARVIS native via bridge
- All frontend → JARVIS native
- Wake word + STT + TTS → JARVIS native

**Estimated work reduction: 30-40% for backend, 0% for frontend, ~20% overall.**

### Verdict
The HUD Epic is **PARTIALLY replaceable** — backend agent logic benefits from OpenClaw; all frontend and local monitoring remains JARVIS-native.
