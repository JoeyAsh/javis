"""Unit tests for api/mcp_tools/smart_home_tools.py.

Mocks at the actions.smart_home boundary.
No live Home Assistant calls are made.

Covered:
- smart_home_list_entities: happy path (with/without domain filter), empty list,
  HTTPStatusError, RequestError, missing credentials.
- smart_home_call_service: happy path, entity_id merging, HTTPStatusError,
  RequestError.
- smart_home_get_state: happy path, 404 → entity-not-found RuntimeError,
  other HTTPStatusError, RequestError.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Credential helper
# ---------------------------------------------------------------------------


def _mock_credentials(ha_url: str = "http://ha.local:8123", ha_token: str = "tok"):
    """Patch _get_ha_credentials to return deterministic values."""
    return patch(
        "api.mcp_tools.smart_home_tools._get_ha_credentials",
        return_value=(ha_url, ha_token),
    )


# ---------------------------------------------------------------------------
# smart_home_list_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_home_list_entities_happy_path_no_filter():
    """smart_home_list_entities returns all entities when no domain filter given."""
    fake_states = [
        {"entity_id": "light.living_room", "state": "on", "attributes": {"friendly_name": "Living Room"}},
        {"entity_id": "switch.fan", "state": "off", "attributes": {}},
    ]

    with patch(
        "api.mcp_tools.smart_home_tools.get_home_assistant_states",
        new=AsyncMock(return_value=fake_states),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_list_entities

        result = await smart_home_list_entities(domain=None)

    assert result["total"] == 2
    assert result["entities"][0]["entity_id"] == "light.living_room"
    assert result["entities"][0]["state"] == "on"
    assert result["entities"][0]["friendly_name"] == "Living Room"
    assert result["entities"][1]["friendly_name"] == ""


@pytest.mark.asyncio
async def test_smart_home_list_entities_with_domain_filter():
    """smart_home_list_entities passes domain prefix filter to get_home_assistant_states."""
    with patch(
        "api.mcp_tools.smart_home_tools.get_home_assistant_states",
        new=AsyncMock(return_value=[]),
    ) as mock_get_states:
        from api.mcp_tools.smart_home_tools import smart_home_list_entities

        await smart_home_list_entities(domain="light")

    mock_get_states.assert_called_once_with(entity_filter="light.")


@pytest.mark.asyncio
async def test_smart_home_list_entities_empty_list():
    """smart_home_list_entities returns empty entities list gracefully."""
    with patch(
        "api.mcp_tools.smart_home_tools.get_home_assistant_states",
        new=AsyncMock(return_value=[]),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_list_entities

        result = await smart_home_list_entities()

    assert result == {"entities": [], "total": 0}


@pytest.mark.asyncio
async def test_smart_home_list_entities_http_status_error_raises_runtime():
    """smart_home_list_entities wraps httpx.HTTPStatusError in RuntimeError."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    exc = httpx.HTTPStatusError("500 error", request=MagicMock(), response=mock_response)

    with patch(
        "api.mcp_tools.smart_home_tools.get_home_assistant_states",
        new=AsyncMock(side_effect=exc),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_list_entities

        with pytest.raises(RuntimeError, match="HTTP 500"):
            await smart_home_list_entities()


@pytest.mark.asyncio
async def test_smart_home_list_entities_request_error_raises_runtime():
    """smart_home_list_entities wraps httpx.RequestError in RuntimeError."""
    exc = httpx.ConnectError("connection refused")

    with patch(
        "api.mcp_tools.smart_home_tools.get_home_assistant_states",
        new=AsyncMock(side_effect=exc),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_list_entities

        with pytest.raises(RuntimeError, match="unreachable"):
            await smart_home_list_entities()


# ---------------------------------------------------------------------------
# smart_home_call_service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_home_call_service_happy_path():
    """smart_home_call_service returns success status dict."""
    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools._call_home_assistant",
        new=AsyncMock(return_value=True),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_call_service

        result = await smart_home_call_service(
            domain="light",
            service="turn_on",
            entity_id="light.living_room",
        )

    assert result["success"] is True
    assert result["domain"] == "light"
    assert result["service"] == "turn_on"
    assert result["entity_id"] == "light.living_room"


@pytest.mark.asyncio
async def test_smart_home_call_service_passes_entity_id_in_service_data():
    """smart_home_call_service injects entity_id into service_data."""
    call_recorder: list[Any] = []

    async def _record(*args: Any, **kwargs: Any) -> bool:
        call_recorder.append(args)
        return True

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools._call_home_assistant", new=_record
    ):
        from api.mcp_tools.smart_home_tools import smart_home_call_service

        await smart_home_call_service(
            domain="switch",
            service="turn_off",
            entity_id="switch.fan",
        )

    # args: (ha_url, ha_token, domain, service, service_data)
    service_data = call_recorder[0][4]
    assert service_data.get("entity_id") == "switch.fan"


@pytest.mark.asyncio
async def test_smart_home_call_service_data_dict_merged():
    """smart_home_call_service merges the data param with entity_id."""
    call_recorder: list[Any] = []

    async def _record(*args: Any, **kwargs: Any) -> bool:
        call_recorder.append(args)
        return True

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools._call_home_assistant", new=_record
    ):
        from api.mcp_tools.smart_home_tools import smart_home_call_service

        await smart_home_call_service(
            domain="light",
            service="turn_on",
            entity_id="light.bedroom",
            data={"brightness": 200},
        )

    service_data = call_recorder[0][4]
    assert service_data["brightness"] == 200
    assert service_data["entity_id"] == "light.bedroom"


@pytest.mark.asyncio
async def test_smart_home_call_service_missing_credentials_raises_runtime():
    """smart_home_call_service raises RuntimeError when HA is not configured."""
    with patch(
        "api.mcp_tools.smart_home_tools._get_ha_credentials",
        side_effect=RuntimeError("Home Assistant credentials are not configured"),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_call_service

        with pytest.raises(RuntimeError, match="credentials"):
            await smart_home_call_service(domain="light", service="turn_on")


@pytest.mark.asyncio
async def test_smart_home_call_service_http_status_error_raises_runtime():
    """smart_home_call_service wraps httpx.HTTPStatusError in RuntimeError."""
    mock_response = MagicMock()
    mock_response.status_code = 422
    exc = httpx.HTTPStatusError("422 Unprocessable", request=MagicMock(), response=mock_response)

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools._call_home_assistant",
        new=AsyncMock(side_effect=exc),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_call_service

        with pytest.raises(RuntimeError, match="HTTP 422"):
            await smart_home_call_service(domain="light", service="turn_on")


@pytest.mark.asyncio
async def test_smart_home_call_service_request_error_raises_runtime():
    """smart_home_call_service wraps httpx.RequestError in RuntimeError."""
    exc = httpx.ConnectError("cannot connect")

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools._call_home_assistant",
        new=AsyncMock(side_effect=exc),
    ):
        from api.mcp_tools.smart_home_tools import smart_home_call_service

        with pytest.raises(RuntimeError, match="unreachable"):
            await smart_home_call_service(domain="light", service="turn_on")


# ---------------------------------------------------------------------------
# smart_home_get_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_home_get_state_happy_path():
    """smart_home_get_state returns entity state dict with all expected fields."""
    fake_data = {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {"brightness": 255, "friendly_name": "Living Room"},
        "last_changed": "2025-01-01T10:00:00Z",
        "last_updated": "2025-01-01T10:01:00Z",
    }
    mock_response = MagicMock()
    mock_response.json.return_value = fake_data
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools.httpx.AsyncClient", return_value=mock_client
    ):
        from api.mcp_tools.smart_home_tools import smart_home_get_state

        result = await smart_home_get_state(entity_id="light.living_room")

    assert result["entity_id"] == "light.living_room"
    assert result["state"] == "on"
    assert result["attributes"]["brightness"] == 255
    assert result["last_changed"] == "2025-01-01T10:00:00Z"


@pytest.mark.asyncio
async def test_smart_home_get_state_404_raises_entity_not_found():
    """smart_home_get_state raises RuntimeError('Entity ... not found') on HTTP 404."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    def _raise_for_status():
        raise httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

    mock_response.raise_for_status = _raise_for_status

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools.httpx.AsyncClient", return_value=mock_client
    ):
        from api.mcp_tools.smart_home_tools import smart_home_get_state

        with pytest.raises(RuntimeError, match="not found"):
            await smart_home_get_state(entity_id="light.nonexistent")


@pytest.mark.asyncio
async def test_smart_home_get_state_other_http_error_raises_runtime():
    """smart_home_get_state wraps non-404 HTTPStatusError in RuntimeError."""
    mock_response = MagicMock()
    mock_response.status_code = 503

    def _raise_for_status():
        raise httpx.HTTPStatusError(
            "503 Unavailable", request=MagicMock(), response=mock_response
        )

    mock_response.raise_for_status = _raise_for_status

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools.httpx.AsyncClient", return_value=mock_client
    ):
        from api.mcp_tools.smart_home_tools import smart_home_get_state

        with pytest.raises(RuntimeError, match="HTTP 503"):
            await smart_home_get_state(entity_id="light.living_room")


@pytest.mark.asyncio
async def test_smart_home_get_state_request_error_raises_runtime():
    """smart_home_get_state wraps httpx.RequestError in RuntimeError."""
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with _mock_credentials(), patch(
        "api.mcp_tools.smart_home_tools.httpx.AsyncClient", return_value=mock_client
    ):
        from api.mcp_tools.smart_home_tools import smart_home_get_state

        with pytest.raises(RuntimeError, match="unreachable"):
            await smart_home_get_state(entity_id="light.living_room")


@pytest.mark.asyncio
async def test_smart_home_get_state_builds_correct_url():
    """smart_home_get_state builds the HA states API URL correctly."""
    fake_data = {
        "entity_id": "sensor.temp",
        "state": "21.5",
        "attributes": {},
        "last_changed": "",
        "last_updated": "",
    }
    mock_response = MagicMock()
    mock_response.json.return_value = fake_data
    mock_response.raise_for_status = MagicMock()

    url_calls: list[str] = []

    async def _get(url: str, **kwargs: Any):
        url_calls.append(url)
        return mock_response

    mock_client = MagicMock()
    mock_client.get = _get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "api.mcp_tools.smart_home_tools._get_ha_credentials",
        return_value=("http://ha.local:8123", "tok"),
    ), patch("api.mcp_tools.smart_home_tools.httpx.AsyncClient", return_value=mock_client):
        from api.mcp_tools.smart_home_tools import smart_home_get_state

        await smart_home_get_state(entity_id="sensor.temp")

    assert len(url_calls) == 1
    assert url_calls[0] == "http://ha.local:8123/api/states/sensor.temp"
