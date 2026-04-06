"""Smart home control via Home Assistant for JARVIS."""

import asyncio
from typing import Any

import httpx

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("smart_home")


async def execute_home_action(params: dict[str, Any]) -> str:
    """Execute a smart home action via Home Assistant.

    Args:
        params: Action parameters including domain, action, room, etc.

    Returns:
        Result message
    """
    cfg = get_config()

    # Check if smart home is enabled
    if not cfg.get("smart_home.enabled", False):
        return "Smart home not configured"

    # Get Home Assistant configuration
    ha_url = cfg.get("home_assistant_url", "")
    ha_token = cfg.get("home_assistant_token", "")

    if not ha_url or not ha_token:
        return "Smart home credentials not configured"

    domain = params.get("domain", "light")
    action = params.get("action", "toggle")
    room = params.get("room", "")

    try:
        # Build entity_id
        entity_id = _build_entity_id(domain, room)

        # Map action to Home Assistant service
        service = _map_action_to_service(domain, action)

        # Build service data
        service_data = _build_service_data(params, entity_id)

        # Call Home Assistant API
        result = await _call_home_assistant(
            ha_url, ha_token, domain, service, service_data
        )

        if result:
            logger.info(f"Smart home action: {domain}/{service} -> {entity_id}")
            return f"Action completed: {domain} {action}"
        else:
            return "Smart home action failed"

    except httpx.HTTPStatusError as e:
        logger.error(f"Home Assistant HTTP error: {e}")
        return f"Smart home error: {e.response.status_code}"
    except httpx.RequestError as e:
        logger.error(f"Home Assistant connection error: {e}")
        return "Smart home is unavailable"
    except Exception as e:
        logger.error(f"Smart home error: {e}")
        return f"Smart home error: {e}"


def _build_entity_id(domain: str, room: str) -> str:
    """Build Home Assistant entity ID.

    Args:
        domain: Device domain (light, climate, lock)
        room: Room name (optional)

    Returns:
        Entity ID string
    """
    if room:
        # Normalize room name
        room_normalized = room.lower().replace(" ", "_").replace("-", "_")
        return f"{domain}.{room_normalized}"
    else:
        # Use generic group or first device
        if domain == "light":
            return "light.all_lights"
        elif domain == "climate":
            return "climate.thermostat"
        elif domain == "lock":
            return "lock.front_door"
        else:
            return f"{domain}.default"


def _map_action_to_service(domain: str, action: str) -> str:
    """Map action to Home Assistant service name.

    Args:
        domain: Device domain
        action: Action name

    Returns:
        Service name
    """
    action_mapping = {
        "turn_on": "turn_on",
        "turn_off": "turn_off",
        "toggle": "toggle",
        "dim": "turn_on",  # With brightness parameter
        "lock": "lock",
        "unlock": "unlock",
        "set_temperature": "set_temperature",
    }

    return action_mapping.get(action, "toggle")


def _build_service_data(params: dict[str, Any], entity_id: str) -> dict[str, Any]:
    """Build service data for Home Assistant API call.

    Args:
        params: Action parameters
        entity_id: Target entity ID

    Returns:
        Service data dictionary
    """
    data: dict[str, Any] = {"entity_id": entity_id}

    # Add brightness for dim action
    if params.get("action") == "dim":
        brightness = params.get("brightness", 50)
        # Home Assistant uses 0-255 for brightness
        data["brightness"] = int(brightness * 2.55)

    # Add temperature for climate
    if params.get("action") == "set_temperature":
        temperature = params.get("temperature")
        if temperature:
            data["temperature"] = temperature

    return data


async def _call_home_assistant(
    base_url: str,
    token: str,
    domain: str,
    service: str,
    service_data: dict[str, Any],
) -> bool:
    """Call Home Assistant REST API.

    Args:
        base_url: Home Assistant base URL
        token: Long-lived access token
        domain: Service domain
        service: Service name
        service_data: Service data

    Returns:
        True if successful, False otherwise
    """
    url = f"{base_url.rstrip('/')}/api/services/{domain}/{service}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, headers=headers, json=service_data)
        response.raise_for_status()

        logger.debug(f"Home Assistant response: {response.status_code}")
        return response.status_code == 200


async def get_home_assistant_states(
    entity_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Get current states from Home Assistant.

    Args:
        entity_filter: Optional entity ID prefix filter

    Returns:
        List of entity states
    """
    cfg = get_config()

    ha_url = cfg.get("home_assistant_url", "")
    ha_token = cfg.get("home_assistant_token", "")

    if not ha_url or not ha_token:
        return []

    try:
        url = f"{ha_url.rstrip('/')}/api/states"
        headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            states = response.json()

            if entity_filter:
                states = [s for s in states if s["entity_id"].startswith(entity_filter)]

            return states

    except Exception as e:
        logger.error(f"Failed to get Home Assistant states: {e}")
        return []
