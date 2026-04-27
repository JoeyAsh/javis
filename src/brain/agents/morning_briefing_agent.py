"""Morning briefing prompt builder for JARVIS.

Content composition is delegated to the OpenClaw chat path.
The sole responsibility here is building the briefing prompt that is
dispatched to OpenClaw so it composes a butler-style daily briefing using
its own tools (gog calendar, gog gmail, weather, etc.).
"""

from __future__ import annotations

from utils.logger import get_logger

logger = get_logger("morning_briefing_agent")


def build_briefing_prompt(language: str) -> str:
    """Compose the system prefix sent to OpenClaw chat for a daily briefing."""
    if language == "de":
        return (
            "Du erstellst jetzt ein kurzes Tages-Briefing für den User (Standort: Zürich, Schweiz). "
            "Decke ab: aktuelles Wetter, heutige Kalender-Termine, wichtige ungelesene Mails, "
            "aktuelle Schlagzeilen. Nutze deine verfügbaren Tools (gog calendar, gog gmail, etc.). "
            "Tonfall: butler-style, knapp, witzig. Länge: unter 60 Sekunden Sprechzeit (~150-200 Wörter). "
            "Antworte vollständig auf Deutsch. Keine Koordinaten — verwende Ortsnamen wie 'Zürich'. "
            "Keine rohen Mail-Subjects — fasse Mails sinnvoll zusammen ('drei Bestellbestätigungen, "
            "nichts Dringendes' statt einzelne Subjects vorzulesen)."
        )
    return (
        "You are now composing a brief daily briefing for the user (location: Zurich, Switzerland). "
        "Cover: current weather, today's calendar events, important unread emails, top news headlines. "
        "Use your available tools (gog calendar, gog gmail, etc.). Tone: butler-style, concise, witty. "
        "Length: under 60 seconds of speech (~150-200 words). Reply entirely in English. "
        "No coordinates — use place names like 'Zurich'. "
        "No raw mail subjects — summarise mail meaningfully ('three order confirmations, nothing urgent' "
        "instead of reading subjects verbatim)."
    )
