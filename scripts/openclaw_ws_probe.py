"""
OpenClaw Gateway WebSocket Probe.

Connects to the persistent gateway at ws://127.0.0.1:18789, performs the
connect.challenge handshake with Ed25519 device identity signing, subscribes to
session message events, fires a single agent turn on session 'jarvis-ws-probe',
and prints every incoming chat event incrementally until the final event.

Run:
    PYTHONPATH=src .venv/bin/python scripts/openclaw_ws_probe.py
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
SESSION_ID = "jarvis-ws-probe"
SESSION_KEY = f"agent:main:explicit:{SESSION_ID}"

# Long message — ensures multi-second response so we can observe streaming.
MESSAGE = (
    "List exactly 20 fruits, each with a one-sentence description of its taste. "
    "Number them 1–20."
)

CLIENT_ID = "gateway-client"
CLIENT_MODE = "backend"
CLIENT_VERSION = "probe/1.0"

# Scopes must be in this exact order (matches CLI_DEFAULT_OPERATOR_SCOPES in TS source).
# Order is preserved in the device signature payload — do NOT sort.
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

# Current gateway protocol version (verified in server source: minProtocol=3, maxProtocol=3).
_PROTOCOL_VERSION = 3


# ── Crypto helpers ──────────────────────────────────────────────────────────────
def _b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


# The 12-byte SPKI prefix wrapping an Ed25519 raw public key in DER SPKI format.
_ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


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
    """Build the v3 device signature payload string.

    Matches the TS ``buildDeviceAuthPayloadV3`` exactly.  Scopes must be in the
    same order as the ``scopes`` array sent in the connect frame — the server
    re-builds the payload from the frame and verifies.  Do NOT sort here.
    """
    return "|".join([
        "v3",
        device_id,
        client_id,
        client_mode,
        role,
        ",".join(scopes),
        str(signed_at_ms),
        token,
        nonce,
        platform,
        device_family,
    ])


# ── Config loaders ──────────────────────────────────────────────────────────────
def load_device_identity() -> dict[str, Any]:
    """Load device identity from ~/.openclaw/identity/device.json."""
    return json.loads(_DEVICE_FILE.read_text())


def load_gateway_token() -> str | None:
    """Load the shared gateway auth token from ~/.openclaw/openclaw.json."""
    try:
        cfg = json.loads(_CONFIG_FILE.read_text())
        token: str | None = cfg.get("gateway", {}).get("auth", {}).get("token")
        return token if token else None
    except Exception:
        return None


# ── Protocol helpers ────────────────────────────────────────────────────────────
def make_request(method: str, params: dict[str, Any]) -> tuple[str, str]:
    """Build a gateway request frame; return (frame_json, request_id)."""
    req_id = str(uuid.uuid4())
    frame = {"type": "req", "id": req_id, "method": method, "params": params}
    return json.dumps(frame), req_id


async def recv_until(ws: Any, target_id: str, label: str = "?") -> dict[str, Any]:
    """Drain WS messages until the response for target_id arrives; log other events."""
    async for raw in ws:
        msg = json.loads(raw)
        if msg.get("id") == target_id:
            return msg
        event = msg.get("event", "")
        if event not in ("tick",):
            print(f"[probe] pre-{label} event: {event}")
    raise RuntimeError(f"WS closed before {label} response")


# ── Main probe ──────────────────────────────────────────────────────────────────
async def probe() -> None:
    """Connect to the gateway, subscribe to chat events, and stream one agent turn."""
    identity = load_device_identity()
    device_id: str = identity["deviceId"]
    private_key_pem: str = identity["privateKeyPem"]
    public_key_pem: str = identity["publicKeyPem"]
    public_key_raw = _public_key_raw_b64url(public_key_pem)

    gateway_token = load_gateway_token() or ""
    print(f"[probe] device_id={device_id[:16]}…  gateway_token={'set' if gateway_token else 'none'}")
    print(f"[probe] connecting to {GATEWAY_URL} …")

    async with connect(GATEWAY_URL) as ws:
        # ── Step 1: receive connect.challenge ────────────────────────────────
        raw = await ws.recv()
        challenge = json.loads(raw)
        assert challenge.get("event") == "connect.challenge", (
            f"Expected connect.challenge, got: {challenge}"
        )
        nonce: str = challenge["payload"]["nonce"]
        print(f"[probe] connect.challenge received  nonce={nonce[:8]}…")

        # ── Step 2: build Ed25519 device signature and send connect ──────────
        # The signature payload includes the gateway token so it cannot be swapped.
        # Token order in payload: auth.token ?? auth.deviceToken ?? auth.bootstrapToken ?? null.
        role = "operator"
        signed_at_ms = int(time.time() * 1000)

        payload_str = _build_device_auth_payload_v3(
            device_id=device_id,
            client_id=CLIENT_ID,
            client_mode=CLIENT_MODE,
            role=role,
            scopes=OPERATOR_SCOPES,
            signed_at_ms=signed_at_ms,
            token=gateway_token,
            nonce=nonce,
            platform="linux",
        )
        signature = _sign_device_payload(private_key_pem, payload_str)

        connect_params: dict[str, Any] = {
            "minProtocol": _PROTOCOL_VERSION,
            "maxProtocol": _PROTOCOL_VERSION,
            "client": {
                "id": CLIENT_ID,
                "version": CLIENT_VERSION,
                "mode": CLIENT_MODE,
                "platform": "linux",
            },
            "caps": [],
            "role": role,
            "scopes": OPERATOR_SCOPES,
            "device": {
                "id": device_id,
                "publicKey": public_key_raw,
                "signature": signature,
                "signedAt": signed_at_ms,
                "nonce": nonce,
            },
        }
        if gateway_token:
            connect_params["auth"] = {"token": gateway_token}

        frame, connect_id = make_request("connect", connect_params)
        await ws.send(frame)

        # ── Step 3: await connect response ───────────────────────────────────
        resp = await recv_until(ws, connect_id, "connect")
        if not resp.get("ok"):
            raise RuntimeError(f"connect rejected: {resp}")
        conn_payload = resp.get("payload", {})
        protocol = conn_payload.get("protocol", "?")
        print(f"[probe] connected OK  protocol={protocol}")

        # ── Step 4: subscribe to session message events ──────────────────────
        # This causes the server to push "chat" notifications for our session key.
        frame, sub_id = make_request("sessions.messages.subscribe", {"key": SESSION_KEY})
        await ws.send(frame)
        sub_resp = await recv_until(ws, sub_id, "sessions.messages.subscribe")
        if not sub_resp.get("ok"):
            raise RuntimeError(f"sessions.messages.subscribe failed: {sub_resp}")
        print(f"[probe] subscribed to {SESSION_KEY}")

        # ── Step 5: fire agent turn ──────────────────────────────────────────
        idempotency_key = str(uuid.uuid4())
        agent_params: dict[str, Any] = {
            "message": MESSAGE,
            "sessionId": SESSION_ID,
            "idempotencyKey": idempotency_key,
        }
        frame, agent_id = make_request("agent", agent_params)
        print(f"\n[probe] firing agent turn …")
        print(f"        sessionId={SESSION_ID}")
        print(f"        idempotencyKey={idempotency_key}")
        t0 = time.monotonic()
        await ws.send(frame)

        # ── Step 6: stream events ────────────────────────────────────────────
        # Responses:  {type:"res", id:..., ok:..., payload:{status:"accepted", runId:...}}
        # Delta events: {event:"chat", payload:{state:"delta", runId, sessionKey, seq,
        #                 message:{role:"assistant", content:[{type:"text", text:"..."}]}}}
        # Final event:  {event:"chat", payload:{state:"final", runId, sessionKey, seq,
        #                 message:{...full text...}}}
        # Error event:  {event:"chat", payload:{state:"error", runId, sessionKey, seq,
        #                 errorMessage:"...", errorKind:"..."}}
        first_delta_at: float | None = None

        async for raw in ws:
            msg = json.loads(raw)

            # Response frame for our agent RPC — confirms the turn was accepted.
            if msg.get("id") == agent_id:
                if msg.get("ok"):
                    run_id = msg.get("payload", {}).get("runId", "?")
                    elapsed = (time.monotonic() - t0) * 1000
                    print(f"[probe] turn accepted  runId={run_id}  ({elapsed:.0f}ms)")
                else:
                    print(f"[probe] turn REJECTED: {msg}")
                    break
                continue

            event_name = msg.get("event")
            if event_name != "chat":
                if event_name not in ("tick",):
                    print(f"[probe] [{event_name}] (skipped)")
                continue

            payload: dict[str, Any] = msg.get("payload", {})
            state: str = payload.get("state", "?")

            # Filter to our session only.
            event_session_key: str | None = payload.get("sessionKey")
            if event_session_key and event_session_key != SESSION_KEY:
                continue

            if state == "delta":
                if first_delta_at is None:
                    first_delta_at = time.monotonic()
                    elapsed_first = (first_delta_at - t0) * 1000
                    print(f"\n[probe] first delta  ({elapsed_first:.0f}ms after send)\n")

                message_obj = payload.get("message") or {}
                content = message_obj.get("content") or []
                text = "".join(
                    blk.get("text", "") for blk in content if blk.get("type") == "text"
                )
                seq = payload.get("seq", "?")
                preview = text[:100].replace("\n", " ")
                sys.stdout.write(f"\r  [seq={seq:>3}] {preview!r:<105}")
                sys.stdout.flush()

            elif state == "final":
                elapsed_total = (time.monotonic() - t0) * 1000
                print(f"\n\n[probe] FINAL  ({elapsed_total:.0f}ms total)")
                message_obj = payload.get("message") or {}
                content = message_obj.get("content") or []
                final_text = "".join(
                    blk.get("text", "") for blk in content if blk.get("type") == "text"
                )
                run_id_final = payload.get("runId")
                seq_final = payload.get("seq")
                print(f"[probe] runId={run_id_final}  seq={seq_final}")
                print(f"[probe] final text: {len(final_text)} chars")
                print(f"\n--- first 400 chars ---")
                print(final_text[:400])
                print("---")
                break

            elif state == "error":
                print(f"\n[probe] ERROR event: {payload}")
                break

        print("\n[probe] done — closing cleanly")


if __name__ == "__main__":
    asyncio.run(probe())
