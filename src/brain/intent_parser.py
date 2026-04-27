"""Intent parser for JARVIS.

Classifies user intents using keyword matching without LLM calls.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from utils.logger import get_logger

logger = get_logger("intent_parser")


class Intent(Enum):
    """User intent categories."""

    CHAT = "chat"
    PC_CONTROL = "pc_control"
    SMART_HOME = "smart_home"
    WEB_SEARCH = "web_search"
    SYSTEM = "system"
    EMAIL_READ = "email_read"
    EMAIL_SEARCH = "email_search"
    EMAIL_COMPOSE = "email_compose"
    SPOTIFY_PLAY = "spotify_play"
    SPOTIFY_PAUSE = "spotify_pause"
    SPOTIFY_NEXT = "spotify_next"
    SPOTIFY_PREV = "spotify_prev"
    SPOTIFY_VOLUME = "spotify_volume"
    CALENDAR_LIST = "calendar_list"
    CALENDAR_CREATE = "calendar_create"
    CALENDAR_UPDATE = "calendar_update"
    CALENDAR_DELETE = "calendar_delete"
    DRIVE_SEARCH = "drive_search"
    SPOTIFY_SEARCH = "spotify_search"
    SPOTIFY_QUEUE = "spotify_queue"
    SPOTIFY_PLAY_CONTEXT = "spotify_play_context"
    GREETING = "greeting"
    MORNING_BRIEFING = "morning_briefing"
    QUIET_MODE_ON = "quiet_mode_on"
    QUIET_MODE_OFF = "quiet_mode_off"


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: Intent
    confidence: float
    params: dict[str, Any] = field(default_factory=dict)
    original_text: str = ""
    language: str = "en"


# Keyword patterns for intent classification
INTENT_KEYWORDS: dict[Intent, dict[str, list[str]]] = {
    Intent.PC_CONTROL: {
        "en": [
            r"\bopen\b",
            r"\blaunch\b",
            r"\bstart\b",
            r"\bclose\b",
            r"\bquit\b",
            r"\bkill\b",
            r"\bvolume\b",
            r"\bmute\b",
            r"\bunmute\b",
            r"\bscreenshot\b",
            r"\btype\b",
            r"\bbrightness\b",
            r"\bshutdown\s+computer\b",
            r"\brestart\s+computer\b",
            r"\block\s+screen\b",
        ],
        "de": [
            r"\böffne\b",
            r"\bstarte\b",
            r"\bschließe?\b",
            r"\bbeende\b",
            r"\blautstärke\b",
            r"\bstumm\b",
            r"\bscreenshot\b",
            r"\bbildschirmfoto\b",
            r"\bhelligkeit\b",
            r"\bcomputer\s+herunterfahren\b",
        ],
    },
    Intent.SMART_HOME: {
        "en": [
            r"\blights?\b",
            r"\bthermostat\b",
            r"\btemperature\b",
            r"\block\b",
            r"\bunlock\b",
            r"\bgarage\b",
            r"\bdoor\b",
            r"\bswitch\b",
            r"\bturn\s+on\b",
            r"\bturn\s+off\b",
            r"\bdim\b",
            r"\bbright(en|er)?\b",
        ],
        "de": [
            r"\blicht(er)?\b",
            r"\blampe(n)?\b",
            r"\bthermostat\b",
            r"\btemperatur\b",
            r"\bheizung\b",
            r"\bschloss\b",
            r"\btür\b",
            r"\bein(schalten)?\b",
            r"\baus(schalten)?\b",
            r"\bdimmen\b",
        ],
    },
    Intent.WEB_SEARCH: {
        "en": [
            r"\bsearch\s+(for\s+)?\b",
            r"\blook\s+up\b",
            r"\bfind\s+(out|information)\b",
            r"\bwhat\s+is\b",
            r"\bwho\s+is\b",
            r"\bwhen\s+(was|is|did)\b",
            r"\bwhere\s+is\b",
            r"\bhow\s+(to|do|does|many|much)\b",
            r"\bwhy\s+(is|do|does|did)\b",
            r"\bgoogle\b",
            r"\blook\s+it\s+up\b",
            r"\bweb\b",
            r"\bonline\b",
        ],
        "de": [
            r"\bsuche?\b",
            r"\brecherchiere\b",
            r"\bfinde\b",
            r"\bwas\s+ist\b",
            r"\bwer\s+ist\b",
            r"\bwann\s+(war|ist)\b",
            r"\bwo\s+ist\b",
            r"\bwie\s+(viel|viele|geht)\b",
            r"\bwarum\b",
            r"\bgoogle\b",
            r"\bim\s+web\b",
            r"\bonline\b",
        ],
    },
    Intent.SYSTEM: {
        "en": [
            r"\bshutdown\s+jarvis\b",
            r"\bturn\s+off\s+jarvis\b",
            r"\bstop\s+jarvis\b",
            r"\bchange\s+(your\s+)?voice\b",
            r"\bswitch\s+voice\b",
            r"\breset\s+(conversation|memory|chat)\b",
            r"\bclear\s+(conversation|memory|chat)\b",
            r"\bforget\s+everything\b",
            r"\blist\s+voices\b",
            r"\bwhat\s+voices\b",
            r"\bavailable\s+voices\b",
        ],
        "de": [
            r"\bjarvis\s+(aus|beenden|stopp)\b",
            r"\bstimme\s+(ändern|wechseln)\b",
            r"\bwechsel(e|n)?\s+(die\s+)?stimme\b",
            r"\bgespräch\s+(zurücksetzen|löschen)\b",
            r"\bvergiss\s+alles\b",
            r"\bspeicher\s+löschen\b",
            r"\bwelche\s+stimmen\b",
        ],
    },
    Intent.EMAIL_READ: {
        "en": [
            r"\bcheck\s+(my\s+)?email(s)?\b",
            r"\bread\s+(my\s+)?email(s)?\b",
            r"\bshow\s+(my\s+)?email(s)?\b",
            r"\bany\s+(new\s+)?email(s)?\b",
            r"\bdo\s+i\s+have\s+(any\s+)?(new\s+)?email(s)?\b",
            r"\bunread\s+email(s)?\b",
            r"\bmy\s+inbox\b",
        ],
        "de": [
            r"\bzeig(e)?\s+(mir\s+)?(meine\s+)?e-?mails?\b",
            r"\bprüfe?\s+(meine\s+)?e-?mails?\b",
            r"\blies(e)?\s+(meine\s+)?e-?mails?\b",
            r"\be-?mails?\s+(lesen|prüfen|anzeigen)\b",
            r"\bposteingang\b",
            r"\bungelesene\s+e-?mails?\b",
            r"\bnachricht(en)?\s+(prüfen|lesen|anzeigen)\b",
        ],
    },
    Intent.EMAIL_SEARCH: {
        "en": [
            r"\bemail(s)?\s+from\b",
            r"\bemail(s)?\s+about\b",
            r"\bany\s+email(s)?\s+from\b",
            r"\bdo\s+i\s+have\s+(any\s+)?email(s)?\s+from\b",
            r"\bsearch\s+(my\s+)?email(s)?\b",
            r"\bfind\s+(an?\s+)?email\b",
            r"\blook\s+for\s+(an?\s+)?email\b",
        ],
        "de": [
            r"\be-?mails?\s+von\b",
            r"\be-?mails?\s+(über|zu|betreff)\b",
            r"\be-?mails?\s+suchen\b",
            r"\be-?mails?\s+von\s+\w+\s+suchen\b",
            r"\bsuche?\s+(nach\s+)?e-?mails?\b",
            r"\bnachrichten\s+von\b",
        ],
    },
    Intent.EMAIL_COMPOSE: {
        "en": [
            r"\bsend\s+(an?\s+)?email\b",
            r"\bwrite\s+(an?\s+)?email\b",
            r"\bcompose\s+(an?\s+)?email\b",
            r"\bdraft\s+(an?\s+)?email\b",
            r"\bemail\s+\w+\s+about\b",
            r"\bsend\s+a\s+message\s+to\b",
        ],
        "de": [
            r"\be-?mail\s+(schreiben|senden|verfassen|schicken)\b",
            r"\bschreibe?\s+(eine\s+)?e-?mail\b",
            r"\bsende?\s+(eine\s+)?e-?mail\b",
            r"\bverfasse?\s+(eine\s+)?e-?mail\b",
            r"\bnachricht\s+schreiben\s+an\b",
            r"\bnachricht\s+senden\s+an\b",
            # Covers "E-Mail an <person> schreiben" (object first)
            r"\be-?mail\s+an\s+\S+\s+(schreiben|senden|verfassen|schicken)\b",
        ],
    },
    # ------------------------------------------------------------------
    # Spotify intents — each maps to a dedicated control action.
    # Patterns are intentionally narrow so they don't clash with PC
    # control (which also has "open spotify" via app alias).
    # ------------------------------------------------------------------
    Intent.SPOTIFY_PLAY: {
        "en": [
            r"\bplay\s+(music|spotify|song|track|the\s+music)\b",
            r"\bresume\s+(music|spotify|playback)\b",
            r"\bstart\s+(playing|music|spotify)\b",
            r"\bplay\s+it\b",
            r"\bplay\s+again\b",
        ],
        "de": [
            r"\babspielen\b",
            r"\bwiedergabe\s+(starten|fortsetzen)\b",
            r"\bmusik\s+(abspielen|starten|spielen)\b",
            r"\bspiele?\s+(musik|spotify|den\s+song|weiter)\b",
            r"\bfortsetzen\b",
        ],
    },
    Intent.SPOTIFY_PAUSE: {
        "en": [
            r"\bpause\s*(the\s+)?(music|spotify|song|playback|it)?\b",
            r"\bstop\s+(the\s+)?(music|spotify|song|playback)\b",
            r"\bstop\s+playing\b",
        ],
        "de": [
            r"\bpausiere?\s*(die\s+)?(musik|spotify|wiedergabe)?\b",
            r"\bmusik\s+pausieren\b",
            r"\bwiedergabe\s+pausieren\b",
            r"\bstoppiere?\s*(die\s+)?(musik|spotify)?\b",
            r"\banhalten\b",
        ],
    },
    Intent.SPOTIFY_NEXT: {
        "en": [
            r"\bnext\s+(song|track|title)\b",
            r"\bskip\s*(this)?\s*(song|track|title)\b",
            r"\bskip\s+(this\s+)?one\b",
            r"\bforward\s+(song|track)\b",
            r"\bplay\s+next\b",
        ],
        "de": [
            r"\bnächste(r|s|n)?\s*(song|titel|track|lied)?\b",
            r"\büberspringen\b",
            r"\bweiter\s*(schalten|springen)?\b",
            r"\bnächster\s+titel\b",
            r"\bskippen\b",
        ],
    },
    Intent.SPOTIFY_PREV: {
        "en": [
            r"\bprevious\s*(song|track|title)?\b",
            r"\bback\s+(to\s+(the\s+)?last|to\s+previous)?\s*(song|track|title)?\b",
            r"\breplay\b",
            r"\bplay\s+(it\s+)?again\b",
            r"\blast\s+(song|track|title)\b",
        ],
        "de": [
            r"\bvorheriger?\s*(song|titel|track|lied)?\b",
            r"\bzurück\s*(zum\s+(letzten|vorherigen))?\s*(song|titel|track)?\b",
            r"\bwieder(holen|spielen)?\b",
            r"\bletzter?\s+(titel|song|track|lied)\b",
        ],
    },
    Intent.SPOTIFY_VOLUME: {
        "en": [
            r"\bspotify\s+volume\b",
            r"\bmusic\s+volume\b",
            r"\bvolume\s+(up|down|\d+)\b",
            r"\bturn\s+(up|down)\s+(the\s+)?music\b",
            r"\blouder\b",
            r"\bquieter\b",
        ],
        "de": [
            r"\bspotify\s+lautstärke\b",
            r"\bmusik\s+lautstärke\b",
            r"\blauter\s*(machen|stellen)?\b",
            r"\bleiser\s*(machen|stellen)?\b",
            r"\blautstärke\s+(hoch|runter|\d+)\b",
        ],
    },
    # ------------------------------------------------------------------
    # Calendar intents — list, create, update, delete.
    # ------------------------------------------------------------------
    Intent.CALENDAR_LIST: {
        "en": [
            r"\b(what'?s?|what\s+is)\s+(on|in)\s+(my\s+)?calendar\b",
            r"\b(show|list|check)\s+(my\s+)?calendar\b",
            r"\bwhat\s+do\s+i\s+have\s+(today|tomorrow|this\s+week)\b",
            r"\bany\s+(events?|appointments?|meetings?)\s+(today|tomorrow)\b",
            r"\bschedule\s+for\s+(today|tomorrow|this\s+week)\b",
            r"\bdo\s+i\s+have\s+(anything|any\s+(meetings?|events?))\s+(today|tomorrow)?\b",
            r"\bagenda\s+(for\s+)?(today|tomorrow|this\s+week)?\b",
        ],
        "de": [
            r"\bwas\s+(steht|habe\s+ich)\s+(heute|morgen|diese\s+woche)\b",
            r"\bwas\s+steht\s+(morgen|heute)\s+an\b",
            r"\b(zeig|zeige)\s+(mir\s+)?(mein(en?)?\s+)?kalender\b",
            r"\b(meine?\s+)(termine?|meetings?|verabredungen?)\s+(heute|morgen|anzeigen)\b",
            r"\bkalender\s+(prüfen|anzeigen|lesen)\b",
            r"\bhabe\s+ich\s+(heute|morgen)\s+(termine?|meetings?)?\b",
            r"\bplan\s+(für\s+)?(heute|morgen|diese\s+woche)\b",
        ],
    },
    Intent.CALENDAR_CREATE: {
        "en": [
            r"\b(schedule|create|add|set\s+up)\s+(a\s+)?(meeting|event|appointment|call|standup)\b",
            r"\badd\s+(\w+\s+){1,3}(appointment|meeting|event)\b",
            r"\badd\s+\w+\s+(appointment|meeting|event)\b",
            r"\bblock\s+(off\s+)?time\b",
            r"\bput\s+(a\s+)?(meeting|event|appointment)\s+(in|on)\s+(my\s+)?calendar\b",
            r"\badd\s+(to|in)\s+(my\s+)?calendar\b",
            r"\bschedule\s+.+\s+(at|on)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)\b",
            r"\bschedule\s+.+\s+(at|for)\s+\d+\s*(am|pm)?\b",
            r"\bremind\s+me\s+(to|about)\b",
            r"\bcreate\s+(a\s+)?(meeting|event|appointment|call|standup)\b",
        ],
        "de": [
            r"\b(termin|meeting|besprechung|anruf)\s+(erstellen|anlegen|hinzufügen|planen|eintragen)\b",
            r"\b(erstelle?|trage?\s+ein|plane?)\s+(einen?\s+)?(termin|meeting|besprechung)\b",
            r"\bfüge?\b.{0,30}\b(termin|meeting|besprechung)\b",
            r"\b(termin|meeting|besprechung)\b.{0,20}\bhinzu\b",
            r"\bplane?\s+(ein\s+)?(meeting|termin|besprechung|anruf)\b",
            r"\bplane\s+ein\b",
            r"\bim\s+kalender\s+(eintragen|speichern|anlegen)\b",
            r"\btermin\s+(morgen|heute|am\s+\w+)\s+(um\s+\d+)\b",
            r"\bverpasse?\s+nicht\b",
            r"\berinnere?\s+(mich)\b",
        ],
    },
    Intent.CALENDAR_UPDATE: {
        "en": [
            r"\b(move|reschedule|change|update)\s+(the\s+)?(meeting|event|appointment|call)\b",
            r"\breschedule\s+the\b",
            r"\breschedule\b.{0,40}\b(meeting|standup|appointment|call|event)\b",
            r"\bchange\s+(my|the)\s+.+\s+(meeting|event|appointment)\b",
            r"\bpush\s+(back|forward)\s+(the\s+)?(meeting|event|appointment)\b",
            r"\bshift\s+(the\s+)?(meeting|event|appointment)\b",
        ],
        "de": [
            r"\b(verschiebe?|verlege?|ändere?|aktualisiere?)\s+(den?\s+)?(termin|meeting|besprechung)\b",
            r"\btermin\s+verschieben\b",
            r"\bneue?\s+uhrzeit\s+für\b",
        ],
    },
    Intent.CALENDAR_DELETE: {
        "en": [
            r"\b(cancel|delete|remove)\s+(the\s+)?(meeting|event|appointment|call|standup)\b",
            r"\bcancel\s+(my\s+)?(\w+\s+)?(meeting|event|appointment|standup|call)\b",
            r"\bcancel\s+(my\s+)?\d+(am|pm)?\s+(meeting|event|appointment|standup|call)\b",
            r"\bdelete\s+(the\s+)?meeting\b",
            r"\bdelete\s+(from\s+)?(my\s+)?calendar\b",
            r"\bremove\s+(from\s+)?(my\s+)?calendar\b",
        ],
        "de": [
            r"\b(absage?|lösche?|entferne?|streiche?)\s+(den?\s+)?(termin|meeting|besprechung)\b",
            r"\btermin\s+(absagen|löschen|stornieren|entfernen)\b",
            r"\baus\s+(dem\s+)?kalender\s+(löschen|entfernen)\b",
        ],
    },
    # ------------------------------------------------------------------
    # Drive intent — voice-triggered read-only search.
    # Patterns are kept distinct from web search / file explorer control.
    # ------------------------------------------------------------------
    Intent.DRIVE_SEARCH: {
        "en": [
            r"\b(search|find|look\s+for)\s+(in\s+)?drive\b",
            r"\bdrive\s+(search|find)\b",
            r"\bopen\s+(doc|document|file)\b",
            r"\bfind\s+(the\s+)?(doc|document|file)\b",
            r"\b(show|list)\s+(my\s+)?drive\s+(files?|docs?|documents?)\b",
            r"\brecent\s+(drive\s+)?(files?|docs?|documents?)\b",
            r"\bdrive\b.{0,30}\b(file|doc|document|spreadsheet)\b",
        ],
        "de": [
            r"\bsuche?\s+in\s+drive\b",
            r"\bdrive\s+suchen?\b",
            r"\bfinde?\s+(das\s+)?(dokument|datei|doc)\b",
            r"\bzeig(e)?\s+(mir\s+)?(meine?\s+)?drive\s+(dateien?|docs?|dokumente?)\b",
            r"\bdrive\b.{0,30}\b(datei|dokument|tabelle)\b",
            r"\bletzten?\s+(drive\s+)?(dateien?|docs?|dokumente?)\b",
            r"\böffne?\s+(das\s+)?(dokument|datei|doc)\b",
        ],
    },
    # ------------------------------------------------------------------
    # Spotify extended intents — search, queue, context play.
    #
    # SPOTIFY_SEARCH requires an explicit Spotify anchor to disambiguate
    # from WEB_SEARCH.  Anchors:
    #   EN: "on spotify", "von <artist>" / "by <artist>" after a search verb
    #   DE: "auf spotify", "von <artist>"
    # A bare "search for X" in English still routes to WEB_SEARCH.
    # ------------------------------------------------------------------
    Intent.SPOTIFY_SEARCH: {
        "en": [
            r"\bsearch\s+(for\s+)?.+\s+on\s+spotify\b",
            r"\bfind\s+.+\s+on\s+spotify\b",
            r"\bspotify\s+search\b",
            r"\bsearch\s+spotify\s+for\b",
            # "search for X by <artist>" — artist anchor makes it Spotify-specific
            r"\bsearch\s+(for\s+)?.+\s+by\s+\w",
            r"\bplay\s+.+\s+by\s+\w.+\s+on\s+spotify\b",
        ],
        "de": [
            r"\bsuche?\s+.+\s+auf\s+spotify\b",
            r"\bspotify\s+suche?\b",
            r"\bspotify\s+suchen\b",
            r"\bfinde?\s+.+\s+auf\s+spotify\b",
            # "suche X von <artist>" — artist anchor
            r"\bsuche?\s+.+\s+von\s+\w",
        ],
    },
    Intent.SPOTIFY_QUEUE: {
        "en": [
            r"\badd\s+.+\s+to\s+(the\s+)?queue\b",
            r"\bqueue\s+(up\s+)?.+\b",
            r"\bnext\s+up\s+.+\b",
            r"\badd\s+.+\s+to\s+(my\s+)?playlist\b",
            r"\benqueue\b",
        ],
        "de": [
            r"\bzur\s+warteschlange\s+hinzufügen\b",
            r"\bwarteschlange\b.{0,20}\b(hinzufügen|hinzu|ergänzen)\b",
            r"\b(füge?|hinzufügen)\b.{0,30}\bzur\s+warteschlange\b",
            r"\bals\s+nächstes\s+spielen\b",
            r"\benqueue\b",
        ],
    },
    Intent.SPOTIFY_PLAY_CONTEXT: {
        "en": [
            r"\bplay\s+(the\s+)?(playlist|album|artist)\b",
            r"\bstart\s+(the\s+)?(playlist|album)\b",
            r"\bplay\s+(playlist|album)\s+.+\b",
            r"\bput\s+on\s+(the\s+)?(playlist|album)\b",
            r"\bplay\s+.+\s+(playlist|album)\b",
        ],
        "de": [
            r"\bspiele?\s+(die\s+)?(playlist|album|wiedergabeliste)\b",
            r"\bstarte?\s+(die\s+)?(playlist|album|wiedergabeliste)\b",
            r"\b(playlist|album|wiedergabeliste)\s+.+\s+(spielen|abspielen|starten)\b",
            r"\bmach\s+(die\s+)?(playlist|album)\s+an\b",
            r"\bspiele?\s+.+\s+(playlist|album)\b",
        ],
    },
    # ------------------------------------------------------------------
    # Greeting intents — morning and general greetings.
    # Word-boundary anchored; optional comma + name suffix tolerated.
    # ------------------------------------------------------------------
    Intent.GREETING: {
        "en": [
            r"\bgood\s+morning\b",
            r"\bmorning\s+jarvis\b",
            r"\bhello\s+jarvis\b",
            r"\bhi\s+jarvis\b",
            r"\bhey\s+jarvis\b",
        ],
        "de": [
            r"\bguten\s+morgen\b",
            r"\bmorgen\s+jarvis\b",
            r"\bhallo\s+jarvis\b",
            r"\bhi\s+jarvis\b",
            r"\bhey\s+jarvis\b",
            r"\bservus\s+jarvis\b",
            r"\bgrüß\s+dich\b",
        ],
    },
    # ------------------------------------------------------------------
    # Morning-briefing intent — explicit request for the daily briefing.
    # ------------------------------------------------------------------
    Intent.MORNING_BRIEFING: {
        "en": [
            r"\bmorning\s+briefing\b",
            r"\bdaily\s+briefing\b",
            r"\bbrief\s+me\b",
            r"\bgive\s+me\s+my\s+briefing\b",
        ],
        "de": [
            r"\btages\s*briefing\b",
            r"\bmorgen\s*briefing\b",
            r"\bbriefe?\s+mich\b",
            r"\bmein\s+briefing\b",
        ],
    },
    # ------------------------------------------------------------------
    # Quiet-mode intents (#93 Phase 2) — language-tolerant word-boundary
    # patterns. The canonical fast-path below catches STT variants.
    # ------------------------------------------------------------------
    Intent.QUIET_MODE_ON: {
        "en": [
            r"\bbe\s+quiet\b",
            r"\bgo\s+quiet\b",
            r"\bquiet\s+mode\b",
            r"\bstop\s+talking\b",
            r"\bsilent\s+mode\b",
        ],
        "de": [
            r"\bleise\s+arbeiten\b",
            r"\bsei\s+leise\b",
            r"\bruhig\s+sein\b",
            r"\bstille\s+modus\b",
            r"\bquiet\s+mode\b",
        ],
    },
    Intent.QUIET_MODE_OFF: {
        "en": [
            r"\bspeak\s+again\b",
            r"\bstop\s+quiet\b",
            r"\bleave\s+quiet\s+mode\b",
            r"\bback\s+(to\s+)?normal\b",
            r"\byou\s+can\s+talk\s+again\b",
        ],
        "de": [
            r"\bwieder\s+reden\b",
            r"\brede\s+wieder\b",
            r"\bquiet\s+mode\s+(aus|off)\b",
            r"\bstille\s+modus\s+(aus|off)\b",
            r"\bnormal\s+(modus|mode)\b",
        ],
    },
}

# ---------------------------------------------------------------------------
# Language-tolerant canonical greeting phrases.
# Checked BEFORE language-specific pattern matching so that short utterances
# with STT language mis-detection (e.g. "Guten Morgen!" classified as lang=sv)
# still route to INTENT.GREETING.
# ---------------------------------------------------------------------------
_CANONICAL_GREETING_PHRASES: tuple[str, ...] = (
    "guten morgen",
    "guten tag",
    "guten abend",
    "guten",
    "morgen jarvis",
    # NOTE: bare "morgen" (German "tomorrow") intentionally excluded — it false-matches
    # calendar phrases like "Was steht morgen an?" or "plane ein Meeting morgen".
    # The GREETING pattern \bguten\s+morgen\b and "morgen jarvis" cover legitimate greetings.
    "good morning",
    "good afternoon",
    "good evening",
    # NOTE: bare "morning" intentionally excluded — "morning jarvis" covers the greeting case.
    # Standalone "morning" is too common in calendar/scheduling utterances.
    "hello jarvis",
    "hi jarvis",
    "hey jarvis",
    "godten morgen",  # observed STT mis-classification (Swedish-like)
)

# ---------------------------------------------------------------------------
# Language-tolerant canonical briefing phrases.
# Checked BEFORE language-specific pattern matching so that short briefing
# triggers with STT language mis-detection or Whisper-mangled transcriptions
# (e.g. "Tages-Briefing" heard as "target briefing" with lang=en) still
# route to INTENT.MORNING_BRIEFING.
# ---------------------------------------------------------------------------
_CANONICAL_BRIEFING_PHRASES: tuple[str, ...] = (
    # German canonical
    "tages briefing",
    "tagesbriefing",
    "tages-briefing",
    "morgen briefing",
    "morgenbriefing",
    "morgen-briefing",
    "morgen-routine",
    "morgen routine",
    "morgenroutine",
    "brief mich",
    "brief mich bitte",
    # English canonical
    "morning briefing",
    "daily briefing",
    "morning routine",
    "brief me",
    "brief me please",
    "give me my briefing",
    "the briefing",
    # Observed STT misclassifications (Whisper hears "Tages" as English-ish)
    "target briefing",
    "tasse briefing",
    "tasches briefing",
    "tag's briefing",
    "tarches briefing",
)


# ---------------------------------------------------------------------------
# Language-tolerant canonical quiet-mode phrases (#93 Phase 2).
# Checked BEFORE language-specific pattern matching to catch STT mis-detection.
# ---------------------------------------------------------------------------
_CANONICAL_QUIET_ON_PHRASES: tuple[str, ...] = (
    # German canonical
    "leise arbeiten",
    "sei leise",
    "ruhig sein",
    "stille modus",
    "leiser modus",
    # English canonical
    "be quiet",
    "go quiet",
    "quiet mode",
    "silent mode",
    "stop talking",
)

_CANONICAL_QUIET_OFF_PHRASES: tuple[str, ...] = (
    # German canonical
    "wieder reden",
    "rede wieder",
    "quiet mode aus",
    "quiet mode off",
    "stille modus aus",
    # English canonical
    "speak again",
    "stop quiet",
    "leave quiet mode",
    "back to normal",
    "you can talk again",
)


def _is_canonical_quiet_on(text: str) -> bool:
    """Match a canonical quiet-mode-ON phrase via word-boundary regex."""
    norm = text.lower().strip().rstrip(".,!?;:")
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", norm) is not None
        for phrase in _CANONICAL_QUIET_ON_PHRASES
    )


def _is_canonical_quiet_off(text: str) -> bool:
    """Match a canonical quiet-mode-OFF phrase via word-boundary regex."""
    norm = text.lower().strip().rstrip(".,!?;:")
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", norm) is not None
        for phrase in _CANONICAL_QUIET_OFF_PHRASES
    )


def _is_canonical_greeting(text: str) -> bool:
    """Match a canonical greeting phrase anywhere in the utterance via word-boundary regex.

    Args:
        text: Raw user text (any case, any trailing punctuation).

    Returns:
        True when a canonical greeting phrase is found at a word boundary.
    """
    norm = text.lower().strip().rstrip(".,!?;:")
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", norm) is not None
        for phrase in _CANONICAL_GREETING_PHRASES
    )


def _is_canonical_briefing(text: str) -> bool:
    """Match a canonical briefing-trigger phrase anywhere in the utterance via word-boundary regex."""
    norm = text.lower().strip().rstrip(".,!?;:")
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", norm) is not None
        for phrase in _CANONICAL_BRIEFING_PHRASES
    )


# App name aliases for PC control
APP_ALIASES: dict[str, str] = {
    # English
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "spotify": "spotify",
    "music": "spotify",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "terminal": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "microsoft teams": "teams",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    # German
    "rechner": "calc",
    "taschenrechner": "calc",
    "editor": "notepad",
    "musik": "spotify",
    "dateien": "explorer",
    "datei-explorer": "explorer",
}


class IntentParser:
    """Parser for classifying user intents."""

    def __init__(self) -> None:
        """Initialize the intent parser."""
        self._compiled_patterns: dict[Intent, dict[str, list[re.Pattern[str]]]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        for intent, lang_patterns in INTENT_KEYWORDS.items():
            self._compiled_patterns[intent] = {}
            for lang, patterns in lang_patterns.items():
                self._compiled_patterns[intent][lang] = [
                    re.compile(p, re.IGNORECASE) for p in patterns
                ]

    async def classify_intent(
        self, text: str, language: str = "en"
    ) -> IntentResult:
        """Classify user intent from text.

        Args:
            text: User input text
            language: Detected language (en, de)

        Returns:
            IntentResult with intent, confidence, and parameters
        """
        text_lower = text.lower().strip()

        if not text_lower:
            return IntentResult(
                intent=Intent.CHAT,
                confidence=0.0,
                original_text=text,
                language=language,
            )

        # Language-tolerant fast paths: canonical phrases bypass language-specific
        # regex patterns. STT sometimes mis-classifies short German utterances as
        # English/Swedish — these catches cover those cases.
        path_label = "language-pattern"

        if _is_canonical_greeting(text_lower):
            path_label = "greeting-fast"
            logger.debug(
                f"🌅 [BRIEFING-DIAG] IntentParser: text={text!r} language={language}"
                f" → intent=greeting (path={path_label})"
            )
            return IntentResult(
                intent=Intent.GREETING,
                confidence=0.85,
                params={},
                original_text=text,
                language=language,
            )

        if _is_canonical_briefing(text_lower):
            path_label = "briefing-fast"
            logger.debug(
                f"🌅 [BRIEFING-DIAG] IntentParser: text={text!r} language={language}"
                f" → intent=morning_briefing (path={path_label})"
            )
            return IntentResult(
                intent=Intent.MORNING_BRIEFING,
                confidence=0.90,
                params={"manual": True},
                original_text=text,
                language=language,
            )

        # Quiet-mode fast-paths: OFF must be checked before ON so that
        # "wieder reden" doesn't partially match a quiet-on phrase.
        if _is_canonical_quiet_off(text_lower):
            path_label = "quiet-off-fast"
            logger.debug(
                f"IntentParser: text={text!r} language={language}"
                f" → intent=quiet_mode_off (path={path_label})"
            )
            return IntentResult(
                intent=Intent.QUIET_MODE_OFF,
                confidence=0.90,
                params={"action": "off"},
                original_text=text,
                language=language,
            )

        if _is_canonical_quiet_on(text_lower):
            path_label = "quiet-on-fast"
            logger.debug(
                f"IntentParser: text={text!r} language={language}"
                f" → intent=quiet_mode_on (path={path_label})"
            )
            return IntentResult(
                intent=Intent.QUIET_MODE_ON,
                confidence=0.90,
                params={"action": "on"},
                original_text=text,
                language=language,
            )

        # Check each intent category
        best_intent = Intent.CHAT
        best_confidence = 0.0
        params: dict[str, Any] = {}

        for intent in [
            Intent.SYSTEM,
            Intent.QUIET_MODE_OFF,
            Intent.QUIET_MODE_ON,
            Intent.MORNING_BRIEFING,
            Intent.GREETING,
            Intent.PC_CONTROL,
            Intent.SMART_HOME,
            Intent.EMAIL_COMPOSE,
            Intent.EMAIL_SEARCH,
            Intent.EMAIL_READ,
            Intent.WEB_SEARCH,
            Intent.SPOTIFY_PLAY,
            Intent.SPOTIFY_PAUSE,
            Intent.SPOTIFY_NEXT,
            Intent.SPOTIFY_PREV,
            Intent.SPOTIFY_VOLUME,
            Intent.SPOTIFY_SEARCH,
            Intent.SPOTIFY_QUEUE,
            Intent.SPOTIFY_PLAY_CONTEXT,
            Intent.CALENDAR_LIST,
            Intent.CALENDAR_CREATE,
            Intent.CALENDAR_UPDATE,
            Intent.CALENDAR_DELETE,
            Intent.DRIVE_SEARCH,
        ]:
            confidence, extracted_params = self._match_intent(
                text_lower, intent, language
            )
            if confidence > best_confidence:
                best_confidence = confidence
                best_intent = intent
                params = extracted_params

        # If no strong match, default to CHAT
        if best_confidence < 0.3:
            best_intent = Intent.CHAT
            best_confidence = 1.0 - best_confidence  # Higher confidence for chat
            path_label = "chat-fallback"

        logger.debug(
            f"🌅 [BRIEFING-DIAG] IntentParser: text={text!r} language={language}"
            f" → intent={best_intent.value} (path={path_label})"
        )
        logger.debug(
            f"Intent: {best_intent.value} (conf={best_confidence:.2f}) "
            f"params={params}"
        )

        return IntentResult(
            intent=best_intent,
            confidence=best_confidence,
            params=params,
            original_text=text,
            language=language,
        )

    def _match_intent(
        self, text: str, intent: Intent, language: str
    ) -> tuple[float, dict[str, Any]]:
        """Match text against intent patterns.

        Args:
            text: Lowercase user text
            intent: Intent to check
            language: Language code

        Returns:
            Tuple of (confidence, extracted_params)
        """
        patterns = self._compiled_patterns.get(intent, {})
        lang_patterns = patterns.get(language, [])
        en_patterns = patterns.get("en", [])  # Fallback to English

        all_patterns = lang_patterns + (en_patterns if language != "en" else [])

        match_count = 0
        params: dict[str, Any] = {}

        for pattern in all_patterns:
            if pattern.search(text):
                match_count += 1

        if match_count == 0:
            return 0.0, params

        # Email intents have a higher base confidence because their keyword
        # patterns are highly specific (e.g. "check my email" is unambiguous).
        _EMAIL_INTENT_BASE = 0.75
        _SPOTIFY_INTENT_BASE = 0.75
        _CALENDAR_INTENT_BASE = 0.75
        _DRIVE_INTENT_BASE = 0.75
        _GREETING_INTENT_BASE = 0.85
        _BRIEFING_INTENT_BASE = 0.85
        _SPOTIFY_INTENTS = (
            Intent.SPOTIFY_PLAY,
            Intent.SPOTIFY_PAUSE,
            Intent.SPOTIFY_NEXT,
            Intent.SPOTIFY_PREV,
            Intent.SPOTIFY_VOLUME,
            Intent.SPOTIFY_SEARCH,
            Intent.SPOTIFY_QUEUE,
            Intent.SPOTIFY_PLAY_CONTEXT,
        )
        _CALENDAR_INTENTS = (
            Intent.CALENDAR_LIST,
            Intent.CALENDAR_CREATE,
            Intent.CALENDAR_UPDATE,
            Intent.CALENDAR_DELETE,
        )
        _QUIET_MODE_INTENT_BASE = 0.85
        if intent in (Intent.QUIET_MODE_ON, Intent.QUIET_MODE_OFF):
            confidence = min(1.0, _QUIET_MODE_INTENT_BASE + (match_count * 0.05))
        elif intent in (Intent.EMAIL_READ, Intent.EMAIL_SEARCH, Intent.EMAIL_COMPOSE):
            confidence = min(1.0, _EMAIL_INTENT_BASE + (match_count * 0.1))
        elif intent in _SPOTIFY_INTENTS:
            confidence = min(1.0, _SPOTIFY_INTENT_BASE + (match_count * 0.1))
        elif intent in _CALENDAR_INTENTS:
            confidence = min(1.0, _CALENDAR_INTENT_BASE + (match_count * 0.1))
        elif intent == Intent.DRIVE_SEARCH:
            confidence = min(1.0, _DRIVE_INTENT_BASE + (match_count * 0.1))
        elif intent == Intent.GREETING:
            confidence = min(1.0, _GREETING_INTENT_BASE + (match_count * 0.05))
        elif intent == Intent.MORNING_BRIEFING:
            confidence = min(1.0, _BRIEFING_INTENT_BASE + (match_count * 0.05))
        else:
            confidence = min(1.0, 0.4 + (match_count * 0.2))

        # Extract parameters based on intent
        if intent == Intent.QUIET_MODE_ON:
            params = {"action": "on"}
        elif intent == Intent.QUIET_MODE_OFF:
            params = {"action": "off"}
        elif intent == Intent.PC_CONTROL:
            params = self._extract_pc_params(text)
        elif intent == Intent.SMART_HOME:
            params = self._extract_smart_home_params(text)
        elif intent == Intent.WEB_SEARCH:
            params = self._extract_search_params(text)
        elif intent == Intent.SYSTEM:
            params = self._extract_system_params(text)
        elif intent in (Intent.EMAIL_READ, Intent.EMAIL_SEARCH, Intent.EMAIL_COMPOSE):
            params = self._extract_email_params(text, intent)
        elif intent in (
            Intent.CALENDAR_LIST,
            Intent.CALENDAR_CREATE,
            Intent.CALENDAR_UPDATE,
            Intent.CALENDAR_DELETE,
        ):
            params = self._extract_calendar_params(text, intent)
        elif intent == Intent.DRIVE_SEARCH:
            params = self._extract_drive_params(text)
        elif intent in (
            Intent.SPOTIFY_SEARCH,
            Intent.SPOTIFY_QUEUE,
            Intent.SPOTIFY_PLAY_CONTEXT,
        ):
            params = self._extract_spotify_params(text, intent)

        return confidence, params

    def _extract_pc_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for PC control intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {"action": "unknown"}

        # Detect action type
        if re.search(r"\b(open|launch|start|öffne|starte)\b", text):
            params["action"] = "open_app"
            # Extract app name
            for alias, app in APP_ALIASES.items():
                if alias in text:
                    params["app"] = app
                    params["app_display"] = alias
                    break

        elif re.search(r"\b(close|quit|kill|schließe?|beende)\b", text):
            params["action"] = "close_app"
            for alias, app in APP_ALIASES.items():
                if alias in text:
                    params["app"] = app
                    break

        elif re.search(r"\b(volume|lautstärke)\b", text):
            params["action"] = "set_volume"
            # Extract volume level
            match = re.search(r"(\d+)\s*(%|percent|prozent)?", text)
            if match:
                params["level"] = int(match.group(1))
            elif re.search(r"\b(up|höher|lauter)\b", text):
                params["direction"] = "up"
            elif re.search(r"\b(down|niedriger|leiser)\b", text):
                params["direction"] = "down"

        elif re.search(r"\b(mute|stumm)\b", text):
            params["action"] = "mute_toggle"

        elif re.search(r"\b(screenshot|bildschirmfoto)\b", text):
            params["action"] = "screenshot"

        elif re.search(r"\btype\b", text):
            params["action"] = "type_text"
            # Extract text to type (everything after "type")
            match = re.search(r"\btype\s+(.+)", text)
            if match:
                params["text"] = match.group(1)

        return params

    def _extract_smart_home_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for smart home intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {"action": "unknown", "domain": "light"}

        # Detect domain
        if re.search(r"\b(lights?|licht|lampe)\b", text):
            params["domain"] = "light"
        elif re.search(r"\b(thermostat|temperature|temperatur|heizung)\b", text):
            params["domain"] = "climate"
        elif re.search(r"\b(lock|schloss)\b", text):
            params["domain"] = "lock"

        # Detect action
        if re.search(r"\b(turn\s+on|ein(schalten)?|an)\b", text):
            params["action"] = "turn_on"
        elif re.search(r"\b(turn\s+off|aus(schalten)?)\b", text):
            params["action"] = "turn_off"
        elif re.search(r"\b(toggle|umschalten)\b", text):
            params["action"] = "toggle"
        elif re.search(r"\b(dim|dimmen)\b", text):
            params["action"] = "dim"
            match = re.search(r"(\d+)\s*(%|percent|prozent)?", text)
            if match:
                params["brightness"] = int(match.group(1))
        elif re.search(r"\b(lock|abschließen)\b", text):
            params["action"] = "lock"
        elif re.search(r"\b(unlock|aufschließen)\b", text):
            params["action"] = "unlock"
        elif re.search(r"\b(set|stelle?)\s*(to|auf)?\s*(\d+)", text):
            params["action"] = "set_temperature"
            match = re.search(r"(\d+)", text)
            if match:
                params["temperature"] = int(match.group(1))

        # Try to extract room/entity name
        room_patterns = [
            r"(living\s*room|wohnzimmer)",
            r"(bedroom|schlafzimmer)",
            r"(kitchen|küche)",
            r"(bathroom|bad|badezimmer)",
            r"(office|büro|arbeitszimmer)",
            r"(garage|garage)",
            r"(hall|flur)",
        ]
        for pattern in room_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params["room"] = match.group(1).lower().replace(" ", "_")
                break

        return params

    def _extract_search_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for web search intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {}

        # Remove common search prefixes
        query = text
        prefixes = [
            r"^(search\s+(for\s+)?)",
            r"^(look\s+up\s+)",
            r"^(find\s+(out\s+)?)",
            r"^(what\s+is\s+(a\s+|an\s+|the\s+)?)",
            r"^(who\s+is\s+)",
            r"^(suche?\s+(nach\s+)?)",
            r"^(was\s+ist\s+(ein\s+|eine\s+)?)",
            r"^(wer\s+ist\s+)",
            r"^(google\s+)",
        ]
        for prefix in prefixes:
            query = re.sub(prefix, "", query, flags=re.IGNORECASE)

        params["query"] = query.strip()
        return params

    def _extract_email_params(self, text: str, intent: Intent) -> dict[str, Any]:
        """Extract parameters for email intents.

        Args:
            text: Lowercase user text.
            intent: The specific email intent variant.

        Returns:
            Extracted parameters with keys ``sender``, ``subject``, ``to``
            (any may be absent when not found in the text).
        """
        params: dict[str, Any] = {}

        # Extract sender for EMAIL_SEARCH (e.g. "emails from Sarah")
        sender_match = re.search(
            r"\b(?:from|von)\s+([A-Za-zÄäÖöÜüß][A-Za-zÄäÖöÜüß\s]{1,30}?)(?:\s*[,?.]|$)",
            text,
            re.IGNORECASE,
        )
        if sender_match:
            params["sender"] = sender_match.group(1).strip()

        # Extract recipient hint for EMAIL_COMPOSE (e.g. "email to John", "an John")
        to_match = re.search(
            r"\b(?:to|an)\s+([A-Za-zÄäÖöÜüß][A-Za-zÄäÖöÜüß\s]{1,30}?)(?:\s+(?:about|über|betreff|re:|:)|[,?.]|$)",
            text,
            re.IGNORECASE,
        )
        if to_match:
            params["to"] = to_match.group(1).strip()

        # Extract subject hint (e.g. "about the meeting", "über das Treffen")
        subject_match = re.search(
            r"\b(?:about|über|betreff|subject|re:)\s+(.+?)(?:[.?!]|$)",
            text,
            re.IGNORECASE,
        )
        if subject_match:
            params["subject"] = subject_match.group(1).strip()

        return params

    def _extract_calendar_params(self, text: str, intent: Intent) -> dict[str, Any]:
        """Extract parameters for calendar intents.

        Args:
            text: Lowercase user text.
            intent: Specific calendar intent variant.

        Returns:
            Extracted parameters with keys ``title``, ``date_expr``,
            ``time_expr`` (any may be absent when not found in text).
        """
        params: dict[str, Any] = {}

        # Extract title / event name (everything between action verb and time/date)
        title_match = re.search(
            r"\b(?:schedule|create|add|cancel|delete|move|reschedule|"
            r"erstelle?|plane?|füge?\s+hinzu|lösche?|absage?|verschiebe?)\s+"
            r"(?:a\s+|an?\s+|einen?\s+|eine?\s+)?"
            r"(?:meeting\s+with\s+|besprechung\s+mit\s+)?"
            r"([A-Za-zÄäÖöÜüß][A-Za-zÄäÖöÜüß0-9\s,\-']{1,60}?)"
            r"\s+(?:at|on|um|am|for|für|tomorrow|today|morgen|heute|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|\d)",
            text,
            re.IGNORECASE,
        )
        if title_match:
            params["title"] = title_match.group(1).strip()

        # Extract raw date expression (the rest of the sentence after action)
        params["raw_text"] = text

        # Detect time expression (e.g. "at 2pm", "um 14 Uhr")
        time_match = re.search(
            r"\b(?:at|um)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|uhr)?)\b",
            text,
            re.IGNORECASE,
        )
        if time_match:
            params["time_expr"] = time_match.group(1).strip()

        return params

    def _extract_drive_params(self, text: str) -> dict[str, Any]:
        """Extract a query hint from a Drive search utterance.

        Args:
            text: Lowercase user text.

        Returns:
            Dict with optional ``query`` key containing the search hint.
        """
        params: dict[str, Any] = {}

        # Try to capture what the user is searching for after key trigger words.
        # E.g. "find the doc budget report" -> "budget report"
        #      "suche in drive nach Quartalsbericht" -> "Quartalsbericht"
        patterns = [
            r"\b(?:find|open|finde?|öffne?)\s+(?:the\s+)?(?:doc|document|file|datei|dokument)\s+(.+?)(?:[.?!]|$)",
            r"\b(?:search|find)\s+(?:in\s+)?drive\s+(?:for\s+)?(.+?)(?:[.?!]|$)",
            r"\bsuche?\s+(?:in\s+drive\s+)?(?:nach\s+)?(.+?)(?:[.?!]|$)",
            r"\b(?:show|list)\s+(?:my\s+)?drive\s+(?:files?|docs?|documents?)\s+(?:about\s+|named?\s+|called\s+)?(.+?)(?:[.?!]|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                hint = m.group(1).strip()
                if hint:
                    params["query"] = hint
                    break

        return params

    def _extract_spotify_params(self, text: str, intent: Intent) -> dict[str, Any]:
        """Extract query and optional artist from Spotify extended intents.

        Strips well-known command prefixes so ``params["query"]`` contains
        the music subject, and populates ``params["artist"]`` when an
        "by <artist>" / "von <artist>" anchor is present.

        Args:
            text: Lowercase user text.
            intent: One of SPOTIFY_SEARCH, SPOTIFY_QUEUE, SPOTIFY_PLAY_CONTEXT.

        Returns:
            Dict with ``query`` and (optionally) ``artist`` keys.
        """
        params: dict[str, Any] = {}

        query = text

        # Strip leading trigger phrases.
        strip_patterns = [
            # EN
            r"^(?:search\s+(?:for\s+)?(?:spotify\s+for\s+)?)",
            r"^(?:find\s+(?:on\s+spotify\s+)?(?:for\s+)?)",
            r"^(?:spotify\s+search\s+(?:for\s+)?)",
            r"^(?:add\s+)",
            r"^(?:queue\s+(?:up\s+)?)",
            r"^(?:enqueue\s+)",
            r"^(?:play\s+(?:the\s+)?(?:playlist\s+|album\s+)?)",
            r"^(?:start\s+(?:the\s+)?(?:playlist\s+|album\s+)?)",
            r"^(?:put\s+on\s+(?:the\s+)?(?:playlist\s+|album\s+)?)",
            # DE
            r"^(?:suche?\s+(?:nach\s+)?(?:auf\s+spotify\s+)?)",
            r"^(?:finde?\s+(?:auf\s+spotify\s+)?)",
            r"^(?:spiele?\s+(?:die\s+)?(?:playlist\s+|album\s+|wiedergabeliste\s+)?)",
            r"^(?:starte?\s+(?:die\s+)?(?:playlist\s+|album\s+)?)",
            r"^(?:füge?\s+)",
            r"^(?:zur\s+warteschlange\s+hinzufügen\s+)",
        ]
        for pat in strip_patterns:
            query = re.sub(pat, "", query, flags=re.IGNORECASE).strip()

        # Remove trailing "on spotify" / "auf spotify" / "to the queue" anchors.
        trail_patterns = [
            r"\s+on\s+spotify$",
            r"\s+auf\s+spotify$",
            r"\s+to\s+(?:the\s+)?(?:my\s+)?queue$",
            r"\s+zur\s+warteschlange$",
            r"\s+(?:playlist|album|wiedergabeliste)$",
        ]
        for pat in trail_patterns:
            query = re.sub(pat, "", query, flags=re.IGNORECASE).strip()

        # Extract "by <artist>" / "von <artist>" anchor.
        artist_match = re.search(
            r"\b(?:by|von)\s+([A-Za-zÄäÖöÜüß0-9][A-Za-zÄäÖöÜüß0-9\s\-&'.]{1,40}?)(?:\s+on\s+spotify|\s+auf\s+spotify|[,?!]|$)",
            query,
            re.IGNORECASE,
        )
        if artist_match:
            artist = artist_match.group(1).strip()
            params["artist"] = artist
            # Remove the "by/von <artist>" clause from the query so it isn't duplicated.
            query = re.sub(
                r"\s+(?:by|von)\s+" + re.escape(artist), "", query, flags=re.IGNORECASE
            ).strip()

        params["query"] = query.strip()
        return params

    def _extract_system_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for system intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {"action": "unknown"}

        if re.search(r"\b(shutdown|turn\s+off|stop|beenden|aus)\s+jarvis\b", text):
            params["action"] = "shutdown"
        elif re.search(r"\b(change|switch|wechsel|änder)\s*(your\s+|die\s+)?voice|stimme\b", text):
            params["action"] = "change_voice"
            # Try to extract voice name
            match = re.search(r"\bto\s+(\w+)", text) or re.search(r"\bzu\s+(\w+)", text)
            if match:
                params["voice"] = match.group(1)
        elif re.search(r"\b(reset|clear|löschen|zurücksetzen|vergiss)\b", text):
            params["action"] = "reset_memory"
        elif re.search(r"\b(list|what|available|welche)\s*(voices?|stimmen)\b", text):
            params["action"] = "list_voices"

        return params


# Global parser instance
_parser: IntentParser | None = None


def get_intent_parser() -> IntentParser:
    """Get the global intent parser instance.

    Returns:
        IntentParser instance
    """
    global _parser
    if _parser is None:
        _parser = IntentParser()
    return _parser
