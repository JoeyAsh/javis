# Offene Fixes — Follow-up-Runde

**Erstellt:** 2026-04-17 ~22:57 (Voice-Session)
**Vorgängerversion:** siehe git history (zwei bereits umgesetzte Fixes:
Barge-in-Sensitivity 150 → 400 ms, Stream-Timeouts aufgesplittet in
time-to-first-token=60s / inter-delta=20s). Beide sind **im Code, Server
läuft, verifiziert in `logs/jarvis.log` ab 22:53:48**.

---

## Problem 1 — Barge-in reagiert jetzt gar nicht mehr

### Beobachtung

Mit `barge_in_sensitivity_ms: 400` (aktueller Stand in
`config/config.yaml`) werden Fehlauslösungen durch Atem/Tastatur
vermieden — **aber echte Unterbrechungen greifen nicht mehr**. Der
Nutzer hat im Live-Test versucht, JARVIS mitten im Satz zu stoppen,
und das System spricht unbeirrt weiter.

### Verdacht

1. **400 ms ist zu hoch** — echte Barge-ins sind oft ein kurzes
   "Stopp", "Moment", "Nein" von 200–350 ms; 400 ms verpasst die.
2. **RMS-Schwelle ist das eigentliche Gate** — `RMSVAD` in
   `src/audio/barge_in.py:182` nutzt `threshold: float = 0.02`. Wenn
   das Mikrofon-Gain des Nutzers niedriger ist als angenommen,
   erreicht die Stimme die 0,02 gar nicht, und der 400-ms-Timer läuft
   nie los.

### Vorschlag

1. **Sensitivity zurückdrehen:** `barge_in_sensitivity_ms` auf **250**
   oder **300** ms setzen. Das ist der Sweet-Spot zwischen
   Atem-Fehlalarmen und echten Unterbrechungen.
2. **RMS-Schwelle konfigurierbar machen und kalibrieren:**
   - Neuer YAML-Key `voice.barge_in_vad_rms_threshold` (Default
     weiterhin 0.02, damit nichts bricht).
   - Das Mikrofon-Gain des Nutzers auf diesem Setup messen (kurzes
     Spoken-Sample während TTS loggen, RMS-Peak notieren) und Default
     ggf. auf 0.01 oder 0.015 senken.
3. **Silero-VAD statt reinem RMS** (mittelfristig): RMS reagiert auf
   jedes Geräusch, Silero erkennt *Sprache*. Würde sowohl
   Fehlalarme **als auch** False-Negatives reduzieren. Bleibt auf der
   Backlog-Liste aus der letzten Runde — jetzt aber mit mehr
   Dringlichkeit.
4. **Diagnose-Log:** Während Barge-in-Monitoring jede Sekunde das
   RMS-Maximum im `debug`-Level loggen. Ohne diese Telemetrie ist
   jede weitere Tuning-Runde Rätselraten.

### Dateien

- `config/config.yaml` — `voice.barge_in_sensitivity_ms`,
  neu: `voice.barge_in_vad_rms_threshold`
- `src/audio/barge_in.py` — `RMSVAD.__init__` (Zeile ~180–215),
  Threshold aus Config lesen statt Default
- `src/api/ws_server.py` — Durchleitung der neuen Config an `RMSVAD`

### Testplan

1. Server mit `sensitivity_ms=300` und unverändertem RMS-Threshold
   neu starten. Live-Test: Nutzer unterbricht zwei Mal mit "Stopp"
   und zwei Mal mit einem normalen Zwischenruf. Beides muss greifen.
2. Regression: Atem- und Tastaturgeräusche dürfen weiterhin nicht
   triggern (das war der Grund für den ersten Fix).
3. Falls (1) immer noch nichts greift, RMS-Threshold auf 0.015
   senken und wiederholen.

---

## Problem 2 — Orb-/Status-Anzeige bleibt hinter tatsächlicher Backend-Aktivität zurück

### Beobachtung (vom Nutzer konkretisiert)

*"Der Status vom Orb und von JARVIS selber passt nicht zu dem, was am
Backend passiert. Vor allem wenn Claude Code gerade etwas macht, z.B.
Dateien schreibt."*

Konkret: Während der Agent im Hintergrund Tools aufruft (File-Reads,
`Write`, `Bash`, `Grep`, Skill-Calls), zeigt der Orb entweder den
alten Zustand weiter oder springt auf `idle`, obwohl das Backend
aktiv arbeitet. Der Nutzer sieht nicht, dass JARVIS gerade etwas
tut — bis die fertige Antwort kommt. Visuell wirkt es, als würde nichts
passieren.

### Verdacht

Die Orb-States `idle / listening / thinking / speaking / follow_up`
bilden den Voice-Pipeline-Zustand ab, aber **nicht die Tool-Call- und
Agent-Aktivität** des OpenClaw-Gateways. Wenn JARVIS' Antwort ein Tool
aufruft, bleibt der Orb sichtbar untätig, obwohl am Gateway gerade
etwas läuft.

Der OpenClaw-WS-Stream liefert laut Protokoll Events für Tool-Calls
(siehe `.tmp/openclaw-ws-protocol.md`), aber die werden im Frontend
offenbar nicht in einen sichtbaren Zustand gemappt.

### Vorschlag

1. **Neuer Orb-Zustand `working` (oder `tool_call`)** für die Dauer
   laufender Backend-Aktivität zwischen `thinking` und `speaking`.
   Visuell: z.B. pulsierender Ring in einer anderen Farbe als Thinking
   (Thinking = Nachdenken vor erstem Token; Working = Aktion in der
   Welt, z.B. File schreiben, Shell-Kommando).
2. **Tool-Event-Passthrough im Backend:** In
   `src/integrations/openclaw/ws_client.py` beim Streaming nicht nur
   Text-Deltas weiterreichen, sondern auch Tool-Start- und Tool-End-
   Events als separate WS-Frame-Typen (`tool.started`, `tool.finished`
   mit Tool-Name). `src/api/ws_server.py` leitet die an den Browser
   weiter.
3. **Frontend-Mapping:** Der Orb-Controller abonniert die neuen Frames
   und schaltet auf `working`, solange Tool-Calls offen sind. Optional
   ein kurzer Text im HUD ("Schreibe Datei …", "Suche im Code …") —
   das erdet die Wartezeit für den Nutzer.
4. **Transcript-Panel:** Sollte Tool-Aufrufe ebenfalls als dezente
   Zeilen zeigen (z.B. grau, kleiner), damit nachvollziehbar ist,
   was JARVIS getan hat. Heute sieht man nur Text-Turns.

### Zusatzsymptom — Orb fällt während des Sprechens zurück auf `idle`

Vom Nutzer gemeldet: Wenn JARVIS eine längere Antwort ausgibt (mehrere
Sätze), springt der Orb visuell bereits auf `idle` zurück, obwohl die
TTS-Wiedergabe noch läuft und der Nutzer weiter zuhört. Das ist
derselbe Klasse-Bug wie das Tool-Call-Thema: der Orb zeigt den
Voice-Pipeline-End-Zustand, nicht den tatsächlichen Audio-Wiedergabe-
Zustand.

**Vorschlag:** Den Orb-Zustand `speaking` nicht am Ende der
TTS-Synthese beenden, sondern am Ende der **Playback-Queue** im
Browser (letzter Audio-Chunk tatsächlich abgespielt). Das Frontend
weiss über den `<audio>`-Element- oder AudioBuffer-Zustand, wann die
Wiedergabe real durch ist. Backend schickt `speaking_started`, Frontend
setzt `speaking_ended` selbst — oder der Orb-State bleibt lokal an der
Audio-Queue-Länge hängen.

**Dateien:** `frontend/src/lib/orb.ts`, der Audio-Player-Hook (vermutlich
in `frontend/src/hooks/`), und die Orb-State-Logik in `App.tsx`.

### Optionale Nebenentdeckung — WS-Reconnect-Thrashing

In `logs/jarvis.log` um `22:54:05` zwei Disconnect/Connect-Paare in
unter 100 ms:

```
22:54:05 Client connected. Total clients: 1
22:54:05 Follow-up window closed (cleanup)
22:54:05 Failed to send to client: Cannot write to closing transport
22:54:05 Client disconnected.
22:54:05 Client connected. Total clients: 1
22:54:05 Client connected. Total clients: 2
```

Möglicherweise eine doppelte Browser-Tab-Session oder ein
Reconnect-Handler, der ohne Backoff neu verbindet. Nicht blockierend,
aber wert, im selben PR gegenzuprüfen.

### Dateien (potenziell betroffen)

- `src/integrations/openclaw/ws_client.py` — Tool-Events aus dem
  OpenClaw-Stream herausfiltern und exponieren
- `src/api/ws_server.py` — neue Frame-Typen an Browser weiterleiten
- `frontend/` — Orb-Controller (neuer State `working`), Transcript-
  Panel (Tool-Zeilen), optional HUD-Text-Indikator
- `.tmp/openclaw-ws-protocol.md` — Referenz, welche Tool-Events das
  Gateway sendet

### Testplan

1. Prompt stellen, der mehrere Tool-Calls auslöst (z.B. "Lies Datei X
   und fasse zusammen"). Während der Ausführung muss der Orb sichtbar
   in `working` bleiben, nicht auf `idle` zurückspringen.
2. Prompt ohne Tool-Calls (reine Konversation): Orb geht wie gehabt
   direkt von `thinking` nach `speaking` — keine Regression.
3. Fehlerfall: Tool-Call schlägt fehl. Orb muss sauber aus `working`
   rauskommen und nicht hängenbleiben.

---

## Problem 3 — End-of-Utterance schneidet den Nutzer zu früh ab

### Beobachtung (vom Nutzer gemeldet)

*"Wenn ich spreche — beim Follow-up oder initial — wird nach einer
gewissen Zeit einfach abgebrochen. Es soll aber warten, bis ich zu
Ende gesprochen habe, und erst dann abgeschickt werden."*

Konkret belegbar im Log-Trace `22:51 – 22:52`: Der Nutzer hat
eine längere Frage zum Zoo-Wetter gestellt und wurde mitten im Satz
abgeschnitten. STT-Ergebnis endete auf *"… wie lange ich von mir, von
meinem Jetz,"* — klassisches Pre-mature-end-of-utterance.

### Verdacht

`config/config.yaml` hat heute drei relevante Schwellen:

- `audio.silence_duration_ms: 1500` — initiale Aufnahme-Stille
- `voice.silence_threshold_ms: 800` — Turn-Detection-Stille
- `voice.backchannel_silence_threshold_ms: 1200` — Backchannel-Trigger

Der **800-ms-Turn-Detection-Wert** ist vermutlich der Übeltäter:
natürliche Denkpausen beim Sprechen ("… und dann möchte ich … äh …
wissen, wie …") sind oft länger als 800 ms. Das System hält die Pause
für das Ende der Äusserung, startet die Pipeline, und die zweite
Hälfte des Satzes geht verloren.

### Vorschlag

1. **Silence-Threshold anheben:** `voice.silence_threshold_ms` von
   800 auf **1500** ms. Das ist ein robuster Wert für natürliche
   Sprechpausen und liegt exakt auf Höhe der initialen
   `audio.silence_duration_ms`. Konsistenz ist Bonus.
2. **Backchannel-Threshold nachziehen:** Wenn End-of-Utterance bei
   1500 ms liegt, muss der Backchannel-Trigger
   (`backchannel_silence_threshold_ms: 1200`) **unter** diesem Wert
   bleiben, damit JARVIS während der Pause noch einen
   Hmm/Mhm-Backchannel abgeben kann, bevor die Pipeline feuert.
   Aktuell: 1200 < 1500 ✓, also weiter passen lassen.
3. **Prosodic Hints aktivieren** (Option): `voice.use_prosodic_hints`
   ist heute `false`. Mit prosodischer Analyse (Tonfall-Fall am
   Satzende) kann der Turn-Detector früher feuern, wenn der Satz
   tatsächlich beendet klingt — und länger warten, wenn die
   Intonation "offen" bleibt. Aufwand höher, Ergebnis natürlicher.
4. **Max-duration-Cap behalten:** Es sollte weiterhin eine harte
   obere Grenze geben (z.B. 30 s), damit eine versehentlich offen
   gelassene Mikro-Session nicht ewig aufzeichnet. Aber nicht
   unter 15 s — sonst werden lange Fragen systematisch abgeschnitten.

### Dateien

- `config/config.yaml` — `voice.silence_threshold_ms`,
  ggf. `voice.use_prosodic_hints`
- `src/audio/` — Turn-Detektor (suchen nach `silence_threshold_ms`)
- ggf. `src/brain/conversation_mode.py` — Follow-up-Fenster-Logik

### Testplan

1. Frage mit eingebauter Denkpause stellen: *"Ich möchte morgen …
   [2 Sekunden Pause] … in den Zoo."* Darf **nicht** nach der Pause
   abgeschickt werden; muss den ganzen Satz erfassen.
2. Kurze einfache Frage ("Wie spät ist es?") darf nicht durch die
   erhöhte Schwelle träger werden — zwischen Ende der Äusserung und
   Antwort sollte gefühlt <2 s Latenz liegen.
3. Edge-Case: Nutzer sagt nichts, Mikro bleibt offen — das
   Max-duration-Cap muss greifen.

---

## Feature-Wunsch 4 — Gesprochene Status-Updates während langer Tool-Ausführung

### Beobachtung (vom Nutzer gewünscht)

Wenn JARVIS einen Auftrag bekommt, der über Claude Code / OpenClaw
längere Tool-Aufrufe startet (Dateien schreiben, Shell-Kommandos,
Code-Analyse, Skill-Aufrufe), möchte der Nutzer **während der
Ausführung** laufend akustische Status-Updates hören — damit er weiss,
dass etwas passiert, ohne den Bildschirm ansehen zu müssen.

### Abgrenzung

- **Vorzulesen** (menschlich formulierte Status-Texte, Fortschritt,
  Meldungen): *"Backend läuft seit 3 Minuten 39, wurde mit Fix
  gestartet."*, *"Ich lese gerade die Konfigdatei."*, *"Der Test ist
  durchgelaufen."*
- **Nicht vorzulesen** (technische Fragmente, die im TTS nur Lärm
  erzeugen): Shell-Kommandos (*"Bash kill -9 3832"*), Hashes, Raw
  JSON, Log-IDs, Stack-Traces, Dateipfade als reine Strings.

### Vorschlag

1. **Event-Kanal vom Gateway auswerten:** Der OpenClaw-Stream liefert
   bereits Tool-Events (siehe Feature-Wunsch 2). Für jedes Event eine
   kurze, sprechbare deutsche Zusammenfassung erzeugen — entweder
   vom Agenten selbst ("say-thought"-ähnlich) oder aus einer
   Mapping-Tabelle (Tool-Name → Satzbaustein).
2. **Filter / Allowlist:** Nur Texte mit einem Minimum an Sprach-
   Charakter durchlassen (Regex-Heuristik: mindestens x Wörter,
   keine zusammenhängenden Sonderzeichen-Blöcke). Technisches
   Logging-Rauschen wird unterdrückt.
3. **Throttle:** Maximal ein gesprochenes Update alle 10–15
   Sekunden, damit JARVIS nicht ins Dauersenden gerät. Zwischenzeit
   visuell im Transcript, nicht akustisch.
4. **Abschaltbar:** Toggle in `config.yaml`
   (`voice.narrate_tool_progress: true/false`), damit der Modus
   für kurze Turns abgeschaltet werden kann.
5. **Kurze Formulierungen, nicht vollständige Sätze vom Agenten:**
   "Lese Logs...", "Schreibe Fix in `.tmp`-Datei...", "Fertig." — TTS-
   Latenz bleibt klein, der Nutzer hört nur die Essenz.

### Dateien (potenziell betroffen)

- `src/integrations/openclaw/ws_client.py` — Tool-Events exponieren
- `src/api/ws_server.py` — neuer Event-Typ `narration` broadcasten
- `src/audio/` — Narration-Pipeline (Queue + TTS + Throttle)
- `config/config.yaml` — neuer Toggle
- `frontend/` — optional Narrations-Einblendung im HUD als Begleitung

### Testplan

1. Langer Task mit mehreren Tool-Aufrufen (z.B. "Prüfe die letzten
   Logs und fasse zusammen"): Nutzer hört alle ~10 s einen kurzen
   Status, **kein** Shell-Kommando-Lärm.
2. Schneller Task (Chat-Antwort ohne Tools): keine Narration,
   direkt zur Hauptantwort — keine Regression.
3. Toggle ausschalten: komplett still bis zur Hauptantwort.

---

## Priorität

1. **Problem 1 (Barge-in-Re-Tuning)** — blockt die Voice-UX spürbar;
   der Nutzer kann mich aktuell nicht stoppen. Zuerst.
2. **Problem 3 (End-of-Utterance)** — blockt den Nutzer in die
   andere Richtung: wird mitten im Satz abgeschnitten. Gleich
   wichtig wie #1, Ein-Parameter-Fix.
3. **Feature 4 (Gesprochene Status-Updates)** — neuer Nutzer-Wunsch,
   reicht mittelfristig; hängt teilweise an Feature 2.
4. **Feature 2 (Orb-Status)** — Komfort-Feature, grösserer Scope
   (Frontend + Backend), hat Zeit bis nach #1 und #3. Liefert
   gleich die Event-Infrastruktur, auf der #4 aufsetzen kann.

#1 und #3 sind je ein Ein-Parameter-Fix in `config.yaml` plus
Telemetrie — können zusammen in einem PR. #2 und #4 hängen am
selben Event-Kanal und sollten in einem grösseren PR kommen.
