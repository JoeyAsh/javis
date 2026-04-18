"""Unit tests for DriveClient.

All ``googleapiclient.discovery.build`` / ``GoogleOAuthService.build_service``
calls are replaced with ``MagicMock`` objects. No real OAuth flow or network
call is made.

Covers: search, get_file_content (Google Doc, plain text, non-text),
list_recent, error propagation, DriveFile parsing, singleton factory.
"""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file_dict(
    file_id: str = "file001",
    name: str = "My Document",
    mime_type: str = "application/vnd.google-apps.document",
    modified_time: str = "2024-03-15T10:00:00Z",
    web_view_link: str = "https://docs.google.com/document/d/file001/edit",
) -> dict[str, Any]:
    """Build a minimal Drive API file metadata dict."""
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "modifiedTime": modified_time,
        "webViewLink": web_view_link,
    }


def _make_mock_service(
    list_response: dict[str, Any] | None = None,
    meta_response: dict[str, Any] | None = None,
    export_bytes: bytes = b"Exported text content",
    get_media_bytes: bytes = b"Plain text file content",
) -> MagicMock:
    """Build a chainable MagicMock mimicking the Drive v3 service resource."""
    svc = MagicMock()

    # files().list().execute()
    list_resp = list_response or {"files": [_make_file_dict()]}
    svc.files.return_value.list.return_value.execute = MagicMock(return_value=list_resp)

    # files().get().execute() — metadata
    meta_resp = meta_response or _make_file_dict()
    svc.files.return_value.get.return_value.execute = MagicMock(return_value=meta_resp)

    # files().export_media().execute() — export Google Doc as text/plain
    svc.files.return_value.export_media.return_value.execute = MagicMock(
        return_value=export_bytes
    )

    # files().get_media() — raw download for plain text files
    svc.files.return_value.get_media.return_value = MagicMock()

    return svc


def _make_client(mock_service: MagicMock):
    """Construct a DriveClient with a mocked OAuth service."""
    from integrations.google.drive_client import DriveClient

    oauth = MagicMock()
    oauth.build_service = AsyncMock(return_value=mock_service)
    return DriveClient(oauth_service=oauth, scopes=["https://www.googleapis.com/auth/drive.readonly"])


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_drive_files():
    """search() returns a list of DriveFile objects from API response."""
    from integrations.google.drive_client import DriveFile

    svc = _make_mock_service(
        list_response={
            "files": [
                _make_file_dict("f1", "Report Q1", "application/vnd.google-apps.document"),
                _make_file_dict("f2", "Budget 2024", "text/plain"),
            ]
        }
    )
    client = _make_client(svc)
    results = await client.search("name contains 'Report'")

    assert len(results) == 2
    assert all(isinstance(r, DriveFile) for r in results)
    assert results[0].id == "f1"
    assert results[0].name == "Report Q1"
    assert results[1].id == "f2"


@pytest.mark.asyncio
async def test_search_empty_results():
    """search() returns empty list when Drive returns no files."""
    svc = _make_mock_service(list_response={"files": []})
    client = _make_client(svc)
    results = await client.search("fullText contains 'nonexistent'")
    assert results == []


@pytest.mark.asyncio
async def test_search_respects_max_results_cap():
    """search() caps max_results at 100 and passes it to the API."""
    svc = _make_mock_service(list_response={"files": []})
    client = _make_client(svc)
    await client.search("query", max_results=999)
    call_kwargs = svc.files.return_value.list.call_args[1]
    assert call_kwargs["pageSize"] == 100


@pytest.mark.asyncio
async def test_search_parses_modified_time():
    """search() correctly parses ISO 8601 modifiedTime into timezone-aware datetime."""
    svc = _make_mock_service(
        list_response={
            "files": [_make_file_dict("f1", modified_time="2024-06-20T14:30:00Z")]
        }
    )
    client = _make_client(svc)
    results = await client.search("q")
    assert results[0].modified_time == datetime(2024, 6, 20, 14, 30, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_search_raises_drive_client_error_on_api_failure():
    """search() raises DriveClientError when the API call throws."""
    from integrations.google.drive_client import DriveClientError

    svc = _make_mock_service()
    svc.files.return_value.list.return_value.execute.side_effect = Exception("API down")
    client = _make_client(svc)

    with pytest.raises(DriveClientError, match="Drive search failed"):
        await client.search("any query")


# ---------------------------------------------------------------------------
# get_file_content() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_content_google_doc_exports_as_text():
    """get_file_content() exports a Google Doc to text/plain."""
    svc = _make_mock_service(
        meta_response=_make_file_dict(
            "doc1", "My Doc", "application/vnd.google-apps.document"
        ),
        export_bytes=b"Hello from Google Docs",
    )
    client = _make_client(svc)
    content = await client.get_file_content("doc1")
    assert content == "Hello from Google Docs"
    svc.files.return_value.export_media.assert_called_once_with(
        fileId="doc1", mimeType="text/plain"
    )


@pytest.mark.asyncio
async def test_get_file_content_plain_text_file_downloaded():
    """get_file_content() downloads a text/plain file directly."""
    import googleapiclient.http

    svc = _make_mock_service(
        meta_response=_make_file_dict("txt1", "readme.txt", "text/plain"),
        get_media_bytes=b"Plain text content here",
    )

    # Patch MediaIoBaseDownload to behave synchronously.
    class FakeDownloader:
        def __init__(self, buf, request):
            buf.write(b"Plain text content here")

        def next_chunk(self):
            return None, True

    client = _make_client(svc)
    with patch("googleapiclient.http.MediaIoBaseDownload", FakeDownloader):
        content = await client.get_file_content("txt1")

    assert content == "Plain text content here"


@pytest.mark.asyncio
async def test_get_file_content_returns_empty_for_pdf():
    """get_file_content() returns '' for PDF files and logs a note."""
    svc = _make_mock_service(
        meta_response=_make_file_dict("pdf1", "report.pdf", "application/pdf"),
    )
    client = _make_client(svc)
    content = await client.get_file_content("pdf1")
    assert content == ""
    # export_media must NOT have been called for a PDF.
    svc.files.return_value.export_media.assert_not_called()


@pytest.mark.asyncio
async def test_get_file_content_returns_empty_for_image():
    """get_file_content() returns '' for image MIME types."""
    svc = _make_mock_service(
        meta_response=_make_file_dict("img1", "photo.jpg", "image/jpeg"),
    )
    client = _make_client(svc)
    content = await client.get_file_content("img1")
    assert content == ""


@pytest.mark.asyncio
async def test_get_file_content_raises_on_metadata_failure():
    """get_file_content() raises DriveClientError when metadata fetch fails."""
    from integrations.google.drive_client import DriveClientError

    svc = _make_mock_service()
    svc.files.return_value.get.return_value.execute.side_effect = Exception("auth error")
    client = _make_client(svc)

    with pytest.raises(DriveClientError, match="metadata"):
        await client.get_file_content("file_x")


# ---------------------------------------------------------------------------
# list_recent() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_recent_returns_drive_files():
    """list_recent() returns files ordered by modifiedTime desc (via API param)."""
    from integrations.google.drive_client import DriveFile

    svc = _make_mock_service(
        list_response={
            "files": [
                _make_file_dict("r1", "Recent Doc", modified_time="2024-11-01T08:00:00Z"),
                _make_file_dict("r2", "Older Doc", modified_time="2024-10-15T12:00:00Z"),
            ]
        }
    )
    client = _make_client(svc)
    results = await client.list_recent(max_results=5)

    assert len(results) == 2
    assert all(isinstance(r, DriveFile) for r in results)
    assert results[0].id == "r1"


@pytest.mark.asyncio
async def test_list_recent_passes_order_by():
    """list_recent() passes orderBy='modifiedTime desc' to the Drive API."""
    svc = _make_mock_service(list_response={"files": []})
    client = _make_client(svc)
    await client.list_recent(max_results=10)
    call_kwargs = svc.files.return_value.list.call_args[1]
    assert call_kwargs["orderBy"] == "modifiedTime desc"


@pytest.mark.asyncio
async def test_list_recent_raises_on_api_error():
    """list_recent() raises DriveClientError on API failure."""
    from integrations.google.drive_client import DriveClientError

    svc = _make_mock_service()
    svc.files.return_value.list.return_value.execute.side_effect = RuntimeError("quota")
    client = _make_client(svc)

    with pytest.raises(DriveClientError, match="list_recent"):
        await client.list_recent()


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def test_get_drive_client_returns_singleton():
    """get_drive_client() always returns the same instance."""
    import integrations.google.drive_client as mod

    # Reset singleton for test isolation.
    original = mod._drive_client_instance
    mod._drive_client_instance = None

    try:
        with patch("integrations.google.oauth.get_google_oauth_service", return_value=MagicMock()):
            client_a = mod.get_drive_client()
            client_b = mod.get_drive_client()
        assert client_a is client_b
    finally:
        mod._drive_client_instance = original


# ---------------------------------------------------------------------------
# DriveFile field coverage
# ---------------------------------------------------------------------------


def test_drive_file_fields_populated():
    """_parse_drive_file() correctly maps all expected fields."""
    from integrations.google.drive_client import _parse_drive_file

    raw = _make_file_dict(
        file_id="xyz",
        name="Quarterly Report",
        mime_type="text/plain",
        modified_time="2024-09-01T00:00:00Z",
        web_view_link="https://drive.google.com/file/d/xyz/view",
    )
    f = _parse_drive_file(raw)
    assert f.id == "xyz"
    assert f.name == "Quarterly Report"
    assert f.mime_type == "text/plain"
    assert f.modified_time == datetime(2024, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert "xyz" in f.web_view_link
