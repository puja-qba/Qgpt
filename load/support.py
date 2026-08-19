"""Shared helpers for the load rig: auth, file generation, stream parsing, metrics.

These sit between the raw Locust client and the scenario tasks. The streaming
and metric helpers are what let the rig capture the capacity-calculator
quantities (held-stream duration, output tokens, MCP calls) per request rather
than only Locust's default latency/RPS.
"""

import json
import os
import time

from load import api, settings


# --- Auth -------------------------------------------------------------------
def authenticate(client):
    """Establish an authenticated session on a Locust client.

    session mode -> POST credentials; the returned cookie rides on the client's
    cookie jar automatically. api_key mode -> set a static bearer header.
    Returns True on success. TODO CONFIRM login shape against staging.
    """
    if settings.AUTH_MODE == "api_key":
        if not settings.API_KEY:
            return False
        client.headers.update({"Authorization": f"Bearer {settings.API_KEY}"})
        return True

    # session mode
    if not settings.USERNAME or not settings.PASSWORD:
        return False
    with client.post(
        settings.LOGIN_PATH,
        data={"username": settings.USERNAME, "password": settings.PASSWORD},
        name="auth:login",
        catch_response=True,
    ) as resp:
        if resp.status_code in (200, 204):
            resp.success()
            return True
        resp.failure(f"login failed: HTTP {resp.status_code}")
        return False


# --- Synthetic files (S04 / S05 ingestion) ----------------------------------
def make_file(size_bytes, tag="light"):
    """Return (filename, bytes) of the requested size, generated in memory.

    Avoids committing large binaries; content is incompressible-ish so the
    ingestion pipeline can't cheat via trivial compression.
    """
    filename = f"loadtest_{tag}_{size_bytes}.bin"
    return filename, os.urandom(size_bytes)


# --- Token estimation -------------------------------------------------------
def estimate_tokens(text):
    """Rough token count (~4 chars/token).

    Good enough for capacity ratios (S02/S03/S08/S09). Swap in a real tokenizer
    if you need billing-grade precision.
    """
    return max(1, len(text) // 4)


# --- Streaming (S08 held-stream duration, output tokens, MCP calls) ---------
def consume_stream(response):
    """Drain an Onyx-style newline-delimited-JSON stream, collecting metrics.

    Returns a dict:
        answer          concatenated answer text
        output_tokens   estimated tokens in the answer
        tool_calls      count of tool/MCP invocations seen in the stream
        hold_seconds    wall-clock the stream was held open
        first_token_s   time to first answer token (None if none arrived)

    TODO CONFIRM packet shape. Onyx has historically emitted packets with
    'answer_piece' (text tokens) and tool packets carrying 'tool_name' /
    'action'. Adjust the keys below once a real stream is captured.
    """
    start = time.time()
    first_token_s = None
    pieces = []
    tool_calls = 0

    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        try:
            packet = json.loads(line)
        except (ValueError, TypeError):
            continue

        if "answer_piece" in packet and packet["answer_piece"]:
            if first_token_s is None:
                first_token_s = time.time() - start
            pieces.append(packet["answer_piece"])

        # MCP / tool activity (S06/S07). Keys are best-guess; confirm & extend.
        if packet.get("tool_name") or packet.get("action") or "tool_result" in packet:
            tool_calls += 1

    answer = "".join(pieces)
    return {
        "answer": answer,
        "output_tokens": estimate_tokens(answer),
        "tool_calls": tool_calls,
        "hold_seconds": time.time() - start,
        "first_token_s": first_token_s,
    }


# --- Custom metrics ---------------------------------------------------------
def record_metric(name, value):
    """Log a derived capacity metric so it shows up in Locust's stats.

    Fired as a zero-failure pseudo-request whose 'response_time' carries the
    value, so Locust aggregates min/max/median/percentiles for free. Read the
    'metric:*' rows in the Locust stats/CSV as the calculator inputs, e.g.
    metric:output_tokens -> S08, metric:mcp_calls -> S06/S07,
    metric:stream_hold_ms -> S08, metric:ingest_ms -> S04/S05.

    Import lazily so this module stays importable without a running Locust env.
    """
    from locust import events

    events.request.fire(
        request_type="METRIC",
        name=f"metric:{name}",
        response_time=value,
        response_length=0,
        exception=None,
        context={},
    )
