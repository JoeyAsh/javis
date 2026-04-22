# JARVIS Sound Assets Manifest

Alle Sounds wurden mit **ElevenLabs Sound Effects API** (via offiziellem MCP-Server) generiert.

## Lizenz
ElevenLabs Sound Effects unterliegen den ElevenLabs Terms of Service. Mit Starter-Plan ($5/Monat) oder höher: kommerzielle Nutzung erlaubt, keine Attribution erforderlich. Bei Generation auf Free-Tier: Attribution an ElevenLabs in öffentlichem Content nötig, keine Monetarisierung.

## Struktur
- Pro Event ein Unterordner unter `assets/sounds/`
- Mehrere Varianten je Event als `<event>_1.mp3`, `<event>_2.mp3`, …
- Numerierung beginnt immer bei `_1`
- Flat-Archive aller Files weiterhin in `assets/sounds/generated/` (nicht für Runtime-Use, nur Referenz)

## Inventar

### Mehr-Varianten-Events
| Event | Anzahl Varianten | Pfad |
|---|---|---|
| boot | 4 | `assets/sounds/boot/` |
| ambient | 2 | `assets/sounds/ambient/` |
| confirm | 2 | `assets/sounds/confirm/` |
| transition | 2 | `assets/sounds/transition/` |

### Single-Variant-Events
(alphabetisch sortiert)

| Event | Pfad |
|---|---|
| alert_critical | `assets/sounds/alert_critical/` |
| auth_fail | `assets/sounds/auth_fail/` |
| auth_success | `assets/sounds/auth_success/` |
| barge_in | `assets/sounds/barge_in/` |
| boot_complete | `assets/sounds/boot_complete/` |
| chart_update | `assets/sounds/chart_update/` |
| click | `assets/sounds/click/` |
| collapse | `assets/sounds/collapse/` |
| command_recognized | `assets/sounds/command_recognized/` |
| data_incoming | `assets/sounds/data_incoming/` |
| disconnect | `assets/sounds/disconnect/` |
| drag_end | `assets/sounds/drag_end/` |
| drag_start | `assets/sounds/drag_start/` |
| error | `assets/sounds/error/` |
| expand | `assets/sounds/expand/` |
| heartbeat | `assets/sounds/heartbeat/` |
| hover | `assets/sounds/hover/` |
| idle_pulse | `assets/sounds/idle_pulse/` |
| info_dismiss | `assets/sounds/info_dismiss/` |
| info_pop | `assets/sounds/info_pop/` |
| lock | `assets/sounds/lock/` |
| menu_close | `assets/sounds/menu_close/` |
| menu_open | `assets/sounds/menu_open/` |
| mic_close | `assets/sounds/mic_close/` |
| mic_open | `assets/sounds/mic_open/` |
| notification | `assets/sounds/notification/` |
| offline | `assets/sounds/offline/` |
| pin | `assets/sounds/pin/` |
| progress_complete | `assets/sounds/progress_complete/` |
| progress_tick | `assets/sounds/progress_tick/` |
| recall | `assets/sounds/recall/` |
| resize | `assets/sounds/resize/` |
| scan | `assets/sounds/scan/` |
| select | `assets/sounds/select/` |
| shutdown | `assets/sounds/shutdown/` |
| speech_end | `assets/sounds/speech_end/` |
| speech_start | `assets/sounds/speech_start/` |
| state_change | `assets/sounds/state_change/` |
| sync | `assets/sounds/sync/` |
| tab_switch | `assets/sounds/tab_switch/` |
| thinking | `assets/sounds/thinking/` |
| unlock | `assets/sounds/unlock/` |
| unpin | `assets/sounds/unpin/` |
| wake | `assets/sounds/wake/` |
| warning | `assets/sounds/warning/` |
| working | `assets/sounds/working/` |

### Loops
Folgende Events sind als seamless Loops generiert:
`progress_tick`, `scan`, `sync`, `thinking`, `working`, `idle_pulse`, `heartbeat`, `ambient`

### One-Shots
Alle übrigen Events.

## Confirmed Event Mappings (User-curated)

### Multi-variant — primary pick per category
| Event | Primary file | Notes |
|---|---|---|
| ambient (loop) | `ambient/ambient_2.mp3` | both variants kept; `_2` is primary |
| boot | `boot/boot_3.mp3` | all 4 variants kept; `_3` is primary startup |
| confirm | `confirm/confirm_1.mp3` | both variants kept; `_1` is primary |

### Window animation cues (transition pair, split assignment)
| Event | File |
|---|---|
| Window maximize | `transition/transition_1.mp3` |
| Window minimize | `transition/transition_2.mp3` |

### Open assignments
All single-variant events under `assets/sounds/<event>/<event>_1.mp3` are awaiting their final UI/orb-event-binding decision in code (folder name implies intent, but final wiring is open).

## Format
Alle Dateien: MP3, 128 kbps, 44.1 kHz, Stereo
