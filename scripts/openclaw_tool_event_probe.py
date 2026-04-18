"""
OpenClaw Tool-Event Probe.

Connects to the gateway, subscribes to BOTH session-message events
(``sessions.messages.subscribe`` → ``chat`` events) AND global session
lifecycle events (``sessions.subscribe`` → ``sessions.changed`` AND
``session.tool`` events).  Then fires a query that definitely triggers
tool use so we can capture the exact WS envelope shape of tool events.

Run:
    PYTHONPATH=src .venv/bin/python scripts/openclaw_tool_event_probe.py

Findings are printed to stdout.  Copy the relevant section into
``.tmp/openclaw-ws-protocol.md``.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from websockets.asyncio.client import connect

# ── Config ─────────────────────────────────────────────────────────────────────
GATEWAY_URL = "ws://127.0.0.1:18789"
import time as _time_mod
SESSION_ID = f"jarvis-tool-probe-{int(_time_mod.time())}"
SESSION_KEY = f"agent:main:explicit:{SESSION_ID}"

# This prompt forces file-reading and search tool calls.
MESSAGE = (
    "Bitte führe den folgenden Bash-Befehl aus und zeige mir die vollständige Ausgabe: "
    "`echo PROBE_TOKEN_12345 && date && hostname`"
)

CLIENT_ID = "gateway-client"
CLIENT_MODE = "backend"
CLIENT_VERSION = "probe/1.0"

OPERATOR_SCOPES = [
    "operator.admin",
    "operator.read",
    "operator.write",
    "operator.approvals",
    "operator.pairing",
    "operator.talk.secrets",
]

_OPENCLAW_STATE_DIR = Path.home() / ".openclaw"
_DEVICE_FILE = _OPENCLAW_STATE_DIR / "identity" / "device.json"
_CONFIG_FILE = _OPENCLAW_STATE_DIR / "openclaw.json"
_PROTOCOL_VERSION = 3
_ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


# ── Crypto helpers ──────────────────────────────────────────────────────────────
def _b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _public_key_raw_b64url(public_key_pem: str) -> str:
    """Extract the 32-byte raw Ed25519 public key from PEM and return as base64url."""
    key: Ed25519PublicKey = serialization.load_pem_public_key(public_key_pem.encode())  # type: ignore[assignment]
    spki = key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    raw = spki[len(_ED25519_SPKI_PREFIX):] if spki[:len(_ED25519_SPKI_PREFIX)] == _ED25519_SPKI_PREFIX else spki
    return _b64url_encode(raw)


def _sign_device_payload(private_key_pem: str, payload: str) -> str:
    """Sign a UTF-8 payload with an Ed25519 private key and return base64url signature."""
    key: Ed25519PrivateKey = serialization.load_pem_private_key(private_key_pem.encode(), password=None)  # type: ignore[assignment]
    return _b64url_encode(key.sign(payload.encode()))


def _build_device_auth_payload_v3(
    *,
    device_id: str,
    client_id: str,
    client_mode: str,
    role: str,
    scopes: list[str],
    signed_at_ms: int,
    token: str,
    nonce: str,
    platform: str,
    device_family: str = "",
) -> str:
    """Build the v3 device signature payload string."""
    return "|".join([
        "v3", device_id, client_id, client_mode, role,
        ",".join(scopes), str(signed_at_ms), token, nonce, platform, device_family,
    ])


def load_device_identity() -> dict[str, Any]:
    """Load device identity from ~/.openclaw/identity/device.json."""
    return json.loads(_DEVICE_FILE.read_text())


def load_gateway_token() -> str:
    """Load the shared gateway auth token from ~/.openclaw/openclaw.json."""
    try:
        cfg = json.loads(_CONFIG_FILE.read_text())
        token: str | None = cfg.get("gateway", {}).get("auth", {}).get("token")
        return token if token else ""
    except Exception:
        return ""


def make_request(method: str, params: dict[str, Any]) -> tuple[str, str]:
    """Build a gateway request frame; return (frame_json, request_id)."""
    req_id = str(uuid.uuid4())
    frame = {"type": "req", "id": req_id, "method": method, "params": params}
    return json.dumps(frame), req_id


async def recv_until(ws: Any, target_id: str) -> dict[str, Any]:
    """Drain WS messages until the response for target_id arrives."""
    async for raw in ws:
        msg = json.loads(raw)
        if msg.get("id") == target_id:
            return msg
        event = msg.get("event", "")
        if event not in ("tick",):
            print(f"  [pre-recv] event={event!r}  keys={list(msg.keys())}")
    raise RuntimeError(f"WS closed before response to {target_id}")


# ── Main probe ──────────────────────────────────────────────────────────────────
async def probe() -> None:
    """Connect, subscribe to session + session.tool events, fire a tool-triggering turn."""
    identity = load_device_identity()
    device_id: str = identity["deviceId"]
    private_key_pem: str = identity["privateKeyPem"]
    public_key_pem: str = identity["publicKeyPem"]
    public_key_raw = _public_key_raw_b64url(public_key_pem)
    gateway_token = load_gateway_token()

    print(f"[probe] device_id={device_id[:16]}…  token={'set' if gateway_token else 'none'}")
    print(f"[probe] connecting to {GATEWAY_URL} …")

    async with connect(GATEWAY_URL) as ws:
        # Step 1: challenge
        raw = await ws.recv()
        challenge = json.loads(raw)
        assert challenge.get("event") == "connect.challenge"
        nonce: str = challenge["payload"]["nonce"]
        print(f"[probe] got connect.challenge  nonce={nonce[:8]}…")

        # Step 2: connect
        role = "operator"
        signed_at_ms = int(time.time() * 1000)
        payload_str = _build_device_auth_payload_v3(
            device_id=device_id, client_id=CLIENT_ID, client_mode=CLIENT_MODE,
            role=role, scopes=OPERATOR_SCOPES, signed_at_ms=signed_at_ms,
            token=gateway_token, nonce=nonce, platform="linux",
        )
        signature = _sign_device_payload(private_key_pem, payload_str)

        connect_params: dict[str, Any] = {
            "minProtocol": _PROTOCOL_VERSION, "maxProtocol": _PROTOCOL_VERSION,
            "client": {"id": CLIENT_ID, "version": CLIENT_VERSION, "mode": CLIENT_MODE, "platform": "linux"},
            # "tool-events" cap tells the gateway to include this connection in toolEventRecipients
            # so it receives agent events with stream="tool" directly.
            "caps": ["tool-events"], "role": role, "scopes": OPERATOR_SCOPES,
            "device": {
                "id": device_id, "publicKey": public_key_raw,
                "signature": signature, "signedAt": signed_at_ms, "nonce": nonce,
            },
        }
        if gateway_token:
            connect_params["auth"] = {"token": gateway_token}

        frame, connect_id = make_request("connect", connect_params)
        await ws.send(frame)
        resp = await recv_until(ws, connect_id)
        if not resp.get("ok"):
            raise RuntimeError(f"connect rejected: {resp}")
        print(f"[probe] connected OK  protocol={resp.get('payload', {}).get('protocol', '?')}")

        # Step 3: sessions.subscribe — subscribes this connection to session.tool events
        frame, sub1_id = make_request("sessions.subscribe", {})
        await ws.send(frame)
        sub1_resp = await recv_until(ws, sub1_id)
        print(f"[probe] sessions.subscribe → {sub1_resp.get('ok')} {sub1_resp.get('payload', {})}")

        # Step 4: sessions.messages.subscribe — subscribes to chat events for our session
        frame, sub2_id = make_request("sessions.messages.subscribe", {"key": SESSION_KEY})
        await ws.send(frame)
        sub2_resp = await recv_until(ws, sub2_id)
        print(f"[probe] sessions.messages.subscribe → {sub2_resp.get('ok')}")

        # Step 5: fire agent turn
        idempotency_key = str(uuid.uuid4())
        frame, agent_id = make_request("agent", {
            "message": MESSAGE,
            "sessionId": SESSION_ID,
            "idempotencyKey": idempotency_key,
        })
        print(f"\n[probe] firing tool-triggering agent turn …")
        print(f"        sessionId={SESSION_ID}")
        print(f"        message={MESSAGE!r}")
        t0 = time.monotonic()
        await ws.send(frame)

        # Step 6: stream ALL events — log everything verbosely
        tool_events_seen: list[dict[str, Any]] = []
        chat_events_seen: int = 0
        done = False

        async for raw in ws:
            msg = json.loads(raw)

            event_name = msg.get("event")
            msg_type = msg.get("type")

            # Skip ticks
            if event_name == "tick":
                continue

            # Response frame for agent RPC
            if msg.get("id") == agent_id:
                if msg.get("ok"):
                    run_id = msg.get("payload", {}).get("runId", "?")
                    elapsed = (time.monotonic() - t0) * 1000
                    print(f"[probe] turn accepted  runId={run_id}  ({elapsed:.0f}ms)")
                else:
                    print(f"[probe] turn REJECTED: {msg}")
                    break
                continue

            # ── session.tool events ──────────────────────────────────────────
            if event_name == "session.tool":
                payload = msg.get("payload", {})
                elapsed = (time.monotonic() - t0) * 1000
                print(f"\n{'='*60}")
                print(f"[SESSION.TOOL EVENT] at {elapsed:.0f}ms")
                print(f"  Full payload (pretty):")
                print(json.dumps(payload, indent=2)[:2000])
                print(f"{'='*60}")
                tool_events_seen.append(payload)
                continue

            # ── chat events ──────────────────────────────────────────────────
            if event_name == "chat":
                payload = msg.get("payload", {})
                state = payload.get("state", "?")
                seq = payload.get("seq", "?")
                session_key = payload.get("sessionKey", "")
                if session_key and SESSION_KEY not in session_key:
                    continue

                chat_events_seen += 1

                if state == "delta":
                    content = (payload.get("message") or {}).get("content") or []
                    text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                    # Also check for non-text content blocks (tool_use)
                    non_text = [b for b in content if b.get("type") != "text"]
                    if non_text:
                        print(f"\n[CHAT DELTA non-text blocks] seq={seq}")
                        for b in non_text:
                            print(f"  block: {json.dumps(b)[:300]}")
                    sys.stdout.write(f"\r  [chat delta seq={seq}] {text[:80]!r:<85}")
                    sys.stdout.flush()

                elif state == "final":
                    elapsed = (time.monotonic() - t0) * 1000
                    content = (payload.get("message") or {}).get("content") or []
                    text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                    non_text = [b for b in content if b.get("type") != "text"]
                    print(f"\n\n[CHAT FINAL] at {elapsed:.0f}ms  seq={seq}  len={len(text)}")
                    if non_text:
                        print(f"  Non-text content blocks in FINAL:")
                        for b in non_text:
                            print(f"    {json.dumps(b)[:400]}")
                    print(f"  text[:200]: {text[:200]!r}")
                    done = True
                    break

                elif state == "error":
                    print(f"\n[CHAT ERROR] {payload}")
                    break

                continue

            # ── agent events — log ALL including tool stream ──────────────────
            if event_name == "agent":
                payload = msg.get("payload", {})
                stream = payload.get("stream", "?")
                run_id_ev = payload.get("runId", "?")
                seq_ev = payload.get("seq", "?")
                data_ev = payload.get("data", {})
                elapsed = (time.monotonic() - t0) * 1000
                print(f"\n[AGENT stream={stream!r} seq={seq_ev} t={elapsed:.0f}ms]")
                print(f"  runId={run_id_ev}")
                print(f"  data keys: {list(data_ev.keys()) if isinstance(data_ev, dict) else type(data_ev)}")
                print(f"  data: {json.dumps(data_ev)[:400]}")
                continue

            # ── All other events ─────────────────────────────────────────────
            if event_name not in ("sessions.changed",):
                print(f"\n[OTHER event={event_name!r} type={msg_type!r}] keys={list(msg.keys())}")
                if event_name:
                    payload = msg.get("payload", {})
                    if payload:
                        print(f"  payload: {json.dumps(payload)[:500]}")

        # Summary
        print(f"\n{'='*60}")
        print(f"[SUMMARY]")
        print(f"  Tool events seen: {len(tool_events_seen)}")
        print(f"  Chat events seen: {chat_events_seen}")
        if tool_events_seen:
            print(f"\n[FIRST TOOL EVENT FULL SHAPE]:")
            print(json.dumps(tool_events_seen[0], indent=2))
        else:
            print("  !! NO session.tool events received — tool events may be")
            print("  embedded in chat content blocks or require a different subscription.")
        print(f"{'='*60}")

        print("\n[probe] done — closing cleanly")


if __name__ == "__main__":
    asyncio.run(probe())
