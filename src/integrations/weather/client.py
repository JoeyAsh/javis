"""Open-Meteo weather adapter for JARVIS.

No API key required — Open-Meteo is a free, open-source weather API.
WMO weather-code mapping covers the most common conditions in DE/EN.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from utils.logger import get_logger

logger = get_logger("weather_client")

# ---------------------------------------------------------------------------
# WMO weather-code → (German, English) short condition string.
# Groups follow https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------

_WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("klar", "clear"),
    1: ("überwiegend klar", "mainly clear"),
    2: ("teilweise bewölkt", "partly cloudy"),
    3: ("bedeckt", "cloudy"),
    45: ("Nebel", "fog"),
    48: ("Nebel mit Reif", "icy fog"),
    51: ("leichter Nieselregen", "light drizzle"),
    53: ("Nieselregen", "drizzle"),
    55: ("starker Nieselregen", "heavy drizzle"),
    56: ("gefrierender Nieselregen", "freezing drizzle"),
    57: ("starker gefrierender Nieselregen", "heavy freezing drizzle"),
    61: ("leichter Regen", "light rain"),
    63: ("Regen", "rain"),
    65: ("starker Regen", "heavy rain"),
    66: ("gefrierender Regen", "freezing rain"),
    67: ("starker gefrierender Regen", "heavy freezing rain"),
    71: ("leichter Schneefall", "light snow"),
    73: ("Schneefall", "snow"),
    75: ("starker Schneefall", "heavy snow"),
    77: ("Schneegriesel", "snow grains"),
    80: ("leichte Regenschauer", "light rain showers"),
    81: ("Regenschauer", "rain showers"),
    82: ("starke Regenschauer", "heavy rain showers"),
    85: ("Schneeschauer", "snow showers"),
    86: ("starke Schneeschauer", "heavy snow showers"),
    95: ("Gewitter", "thunderstorm"),
    96: ("Gewitter mit Hagel", "thunderstorm with hail"),
    99: ("Gewitter mit starkem Hagel", "thunderstorm with heavy hail"),
}

_OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,weather_code"
    "&daily=temperature_2m_max,temperature_2m_min,weather_code"
    "&timezone=auto"
    "&forecast_days=1"
)


class WeatherClient:
    """Async Open-Meteo weather adapter.

    Uses ``aiohttp`` for HTTP calls — no API key, no extra dependencies.
    """

    async def get_current_and_today(
        self,
        lat: float,
        lon: float,
        language: str = "de",
    ) -> dict[str, Any] | None:
        """Fetch current conditions and today's high/low from Open-Meteo.

        Args:
            lat: Latitude of the target location.
            lon: Longitude of the target location.
            language: ``"de"`` for German condition strings, ``"en"`` for English.

        Returns:
            Dict with keys ``location``, ``condition``, ``currentTemp``,
            ``high``, ``low``; or ``None`` on HTTP/network error.
        """
        url = _OPEN_METEO_URL.format(lat=lat, lon=lon)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"Open-Meteo returned HTTP {resp.status} for lat={lat} lon={lon}"
                        )
                        return None
                    data: dict[str, Any] = await resp.json()
        except aiohttp.ClientError as exc:
            logger.warning(f"Open-Meteo request failed: {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Unexpected error fetching weather: {exc}")
            return None

        try:
            current = data.get("current", {})
            daily = data.get("daily", {})

            current_temp: float = float(current.get("temperature_2m", 0))
            weather_code: int = int(current.get("weather_code", 0))

            daily_max_list: list[float] = daily.get("temperature_2m_max", [])
            daily_min_list: list[float] = daily.get("temperature_2m_min", [])

            high: float = float(daily_max_list[0]) if daily_max_list else current_temp
            low: float = float(daily_min_list[0]) if daily_min_list else current_temp

            condition_pair = _WMO_CODES.get(weather_code, ("unbekannt", "unknown"))
            condition = condition_pair[0] if language == "de" else condition_pair[1]

            location_label = f"{lat:.2f}°N {lon:.2f}°E"

            return {
                "location": location_label,
                "condition": condition,
                "currentTemp": round(current_temp, 1),
                "high": round(high, 1),
                "low": round(low, 1),
            }
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(f"Failed to parse Open-Meteo response: {exc}")
            return None
