"""MCP tool registrations for the ``smart_home.*`` namespace.

Thin wrappers over :mod:`actions.smart_home`.  Each handler calls the
existing Home Assistant helpers and returns JSON-serialisable dicts.

Registered tools (3):
- ``smart_home_list_entities``
- ``smart_home_call_service``
- ``smart_home_get_state``
"""

from __future__ import annotations

from typing import Any

import httpx

from actions.smart_home import _call_home_assistant, get_home_assistant_states
from api.mcp_server import register_tool
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("mcp_tools.smart_home")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_ha_credentials() -> tuple[str, str]:
    """Return (ha_url, ha_token), raising RuntimeError if not configured."""
    cfg = get_config()
    ha_url: str = cfg.get("home_assistant_url", "")
    ha_token: str = cfg.get("home_assistant_token", "")
    if not ha_url or not ha_token:
        raise RuntimeError(
            "Home Assistant credentials are not configured. "
            "Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in .env."
        )
    return ha_url, ha_token


# ---------------------------------------------------------------------------
# smart_home_list_entities
# ---------------------------------------------------------------------------


@register_tool(
    name="smart_home_list_entities",
    description=(
        "List Home Assistant entities. Optionally filter by domain "
        "(e.g. 'light', 'switch', 'climate', 'lock', 'sensor')."
    ),
    schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": (
                    "Optional HA entity domain prefix to filter by "
                    "(e.g. 'light', 'switch'). Omit to list all entities."
                ),
            },
        },
        "required": [],
    },
)
async def smart_home_list_entities(
    domain: str | None = None,
) -> dict[str, Any]:
    """Return a list of Home Assistant entities, optionally filtered by domain."""
    try:
        states = await get_home_assistant_states(
            entity_filter=f"{domain}." if domain else None
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Home Assistant returned HTTP {exc.response.status_code}: {exc}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Home Assistant is unreachable: {exc}") from exc

    entities = [
        {
            "entity_id": s.get("entity_id", ""),
            "state": s.get("state", ""),
            "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
        }
        for s in states
    ]
    logger.debug(
        f"smart_home_list_entities(domain={domain!r}): {len(entities)} entities"
    )
    return {"entities": entities, "total": len(entities)}


# ---------------------------------------------------------------------------
# smart_home_call_service
# ---------------------------------------------------------------------------


@register_tool(
    name="smart_home_call_service",
    description=(
        "Call a Home Assistant service. For example: domain='light', "
        "service='turn_on', entity_id='light.living_room'."
    ),
    schema={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "HA service domain (e.g. 'light', 'switch', 'climate').",
            },
            "service": {
                "type": "string",
                "description": "Service name within the domain (e.g. 'turn_on').",
            },
            "entity_id": {
                "type": "string",
                "description": "Target entity ID (e.g. 'light.living_room'). Optional.",
            },
            "data": {
                "type": "object",
                "description": (
                    "Additional service-call data (e.g. brightness, temperature). "
                    "Optional. entity_id from this field takes precedence if present."
                ),
            },
        },
        "required": ["domain", "service"],
    },
)
async def smart_home_call_service(
    domain: str,
    service: str,
    entity_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call a Home Assistant service and return success status."""
    ha_url, ha_token = _get_ha_credentials()

    service_data: dict[str, Any] = dict(data) if data else {}
    if entity_id:
        service_data.setdefault("entity_id", entity_id)

    try:
        success = await _call_home_assistant(
            ha_url, ha_token, domain, service, service_data
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Home Assistant returned HTTP {exc.response.status_code}: {exc}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Home Assistant is unreachable: {exc}") from exc

    logger.debug(
        f"smart_home_call_service({domain}/{service}, "
        f"entity_id={entity_id!r}): success={success}"
    )
    return {
        "success": success,
        "domain": domain,
        "service": service,
        "entity_id": entity_id,
    }


# ---------------------------------------------------------------------------
# smart_home_get_state
# ---------------------------------------------------------------------------


@register_tool(
    name="smart_home_get_state",
    description="Return the current state and attributes of a Home Assistant entity.",
    schema={
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "Full entity ID to query (e.g. 'light.living_room').",
            },
        },
        "required": ["entity_id"],
    },
)
async def smart_home_get_state(entity_id: str) -> dict[str, Any]:
    """Return the current state of a single Home Assistant entity."""
    ha_url, ha_token = _get_ha_credentials()
    url = f"{ha_url.rstrip('/')}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise RuntimeError(f"Entity '{entity_id}' not found in Home Assistant") from exc
        raise RuntimeError(
            f"Home Assistant returned HTTP {exc.response.status_code}: {exc}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Home Assistant is unreachable: {exc}") from exc

    result: dict[str, Any] = {
        "entity_id": data.get("entity_id", entity_id),
        "state": data.get("state", ""),
        "attributes": data.get("attributes", {}),
        "last_changed": data.get("last_changed", ""),
        "last_updated": data.get("last_updated", ""),
    }
    logger.debug(
        f"smart_home_get_state({entity_id!r}): state={result['state']!r}"
    )
    return result
