"""Kontur Talk MCP server -- recordings, transcripts, summaries, meetings, chat.

Two interchangeable auth modes (see client.py): ``api_key`` (X-Auth-Token,
scope-limited) or ``session`` (browser Session token, sees whatever the
logged-in user sees). Which one is active is decided once at startup from
the environment -- see README.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastmcp import FastMCP

from ktalk_mcp_apikey.client import KtalkAPIError, client_from_env

# Loaded here (not just in scripts/) so `uv run ktalk-mcp-apikey` and the
# Claude Code .mcp.json entry both pick up .env without extra plumbing.
load_dotenv()

log = logging.getLogger("ktalk_mcp_apikey")
log.setLevel(os.environ.get("KTALK_LOG_LEVEL", "INFO").upper())
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
    log.addHandler(_h)

client = client_from_env()

mcp = FastMCP(
    "ktalk-apikey",
    instructions=(
        "Kontur Talk (ktalk.ru) tools for recordings, transcripts, summaries, meetings "
        "and chat. Auth mode is fixed at startup (api_key or session -- see auth_status). "
        "In api_key mode, a 403 on recordings/meetings endpoints usually means the key's "
        "scope doesn't cover them (personal keys in particular often can't reach recordings "
        "at all -- see docs/api-reference.md). session mode has no such scope limit but the "
        "token expires roughly every 30 days and must be re-extracted from the browser."
    ),
)


def _err_to_json(e: Exception) -> str:
    if isinstance(e, KtalkAPIError):
        return json.dumps({"error": "api_error", "status": e.status, "message": str(e)}, ensure_ascii=False)
    return json.dumps({"error": "unexpected", "message": str(e)}, ensure_ascii=False)


def _pick_quality_url(detail: dict) -> str | None:
    """Highest-quality ``qualities[].fileUrl`` from a recording detail."""
    best_url, best_score = None, -1
    for q in (detail or {}).get("qualities") or []:
        url = q.get("fileUrl") or q.get("url")
        if not url:
            continue
        raw_score = q.get("height") or q.get("width") or q.get("quality") or 0
        try:
            score = int(raw_score)
        except (TypeError, ValueError):
            score = 0
        if score >= best_score:
            best_url, best_score = url, score
    if not best_url:
        best_url = (detail or {}).get("fileUrl") or (detail or {}).get("downloadUrl")
    return best_url


# ---------------------------------------------------------------------------
# Recordings
# ---------------------------------------------------------------------------

@mcp.tool(
    annotations={
        "title": "List Recordings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def list_recordings(limit: int = 30, offset: int = 0, query: str | None = None) -> str:
    """List recordings.

    In session mode: your own recordings (GET /api/recordings), the same list
    Talk's web UI shows you. In api_key mode: the whole space's recordings
    (GET /api/Domain/recordings/v2) -- requires a *domain* key with the
    "Просмотр списка записей" scope; a personal key gets a 403 here.

    Args:
        limit: page size.
        offset: how many to skip (newest first).
        query: title search substring.
    """
    if client.auth_mode == "session":
        params: dict = {"skip": offset, "top": limit}
        if query:
            params["query"] = query
        path = "/recordings"
    else:
        params = {"skip": offset, "top": limit}
        if query:
            params["query"] = query
        path = "/Domain/recordings/v2"
    try:
        data = await client.request("GET", path, params=params)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "Get Recording",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_recording(recording_key: str) -> str:
    """Recording detail: title, author, date, duration, participants, download qualities.

    session mode: GET /api/recordings/{key}. api_key mode: GET
    /api/Domain/recordings/{key} (domain scope required).

    Args:
        recording_key: the recording's id, from its Talk URL or from list_recordings.
    """
    path = f"/recordings/{recording_key}" if client.auth_mode == "session" else f"/Domain/recordings/{recording_key}"
    try:
        data = await client.request("GET", path)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "Get Recording Transcript",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_transcript(recording_key: str) -> str:
    """Speech-to-text transcript of a recording, by speaker (GET /api/recordings/{key}/transcript).

    Same path in both auth modes. Returns the API's raw JSON (speaker turns,
    timecodes) -- not reshaped here.

    Args:
        recording_key: the recording's id, from its Talk URL or from list_recordings.
    """
    try:
        data = await client.request("GET", f"/recordings/{recording_key}/transcript")
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "Get Recording Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_summary(recording_key: str, summary_type: str | None = None) -> str:
    """Meeting summary: short recap and/or protocol. Same paths in both auth modes.

    Without summary_type, calls GET /api/recordings/v2/{key}/summary (protocol +
    short summary + transcript together). With summary_type set to
    "shortSummary" or "protocol", calls GET /api/recordings/{key}/summary/{type}
    instead.

    Args:
        recording_key: the recording's id, from its Talk URL or from list_recordings.
        summary_type: "shortSummary" | "protocol" | None (both, via the v2 endpoint).
    """
    path = (
        f"/recordings/{recording_key}/summary/{summary_type}"
        if summary_type
        else f"/recordings/v2/{recording_key}/summary"
    )
    try:
        data = await client.request("GET", path)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "Download Recording File",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def download_recording(recording_key: str, target_path: str, quality: str | None = None) -> str:
    """Download a recording's video file to disk. An existing file at target_path is overwritten.

    session mode: fetches the recording detail, picks the best (or the named)
    quality from qualities[].fileUrl, downloads that. api_key mode: calls
    GET /api/Recordings/{key}/file/{quality} directly -- quality is then
    required (see get_recording's qualities list for valid names).

    Args:
        recording_key: the recording's id.
        target_path: destination file path.
        quality: quality name (e.g. "900p"); omitted in session mode -> best available.
    """
    os.makedirs(os.path.dirname(os.path.abspath(target_path)) or ".", exist_ok=True)
    try:
        if client.auth_mode == "session":
            detail = await client.request("GET", f"/recordings/{recording_key}")
            detail = detail if isinstance(detail, dict) else {}
            if quality:
                file_url = next(
                    (q.get("fileUrl") for q in detail.get("qualities") or [] if q.get("quality") == quality or q.get("height") == quality),
                    None,
                )
            else:
                file_url = _pick_quality_url(detail)
            if not file_url:
                return json.dumps(
                    {"error": "no_file_url", "message": "No qualities[].fileUrl in recording detail", "recording_id": recording_key},
                    ensure_ascii=False,
                )
            name = os.path.basename(urlparse(file_url).path) or f"{recording_key}.mp4"
            dest = target_path if os.path.splitext(target_path)[1] else os.path.join(target_path, name)
            path, size = await client.download(absolute_url=file_url, dest_path=dest)
        else:
            if not quality:
                return json.dumps(
                    {"error": "missing_argument", "message": "quality is required in api_key mode"},
                    ensure_ascii=False,
                )
            path, size = await client.download(path=f"/Recordings/{recording_key}/file/{quality}", dest_path=target_path)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps({"ok": True, "path": path, "bytes": size}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Meetings + chat (session mode only -- no working api_key equivalent found)
# ---------------------------------------------------------------------------

@mcp.tool(
    annotations={
        "title": "List Past Meetings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def list_meetings(limit: int = 30, offset: int = 0, query: str | None = None) -> str:
    """Your past meetings, newest first (GET /api/conferencesHistory/).

    Only confirmed working in session mode -- in api_key mode this is very
    likely a 403 (no domain scope for it was found in scripts/probe_scopes.py).
    A meeting's recording_ids (under artifacts.content) link it to
    get_recording / get_transcript / get_summary.

    Args:
        limit: page size.
        offset: how many to skip.
        query: title search substring.
    """
    params: dict = {"skip": offset, "top": limit, "includeUnfinished": "true"}
    if query:
        params["query"] = query
    try:
        data = await client.request("GET", "/conferencesHistory/", params=params)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "Get Meeting",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_meeting(conference_key: str) -> str:
    """One meeting's detail incl. full participant list (GET /api/conferencesHistory/{key}).

    Args:
        conference_key: from list_meetings, or a recording's conferenceKey.
    """
    try:
        data = await client.request("GET", f"/conferencesHistory/{conference_key}")
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "Get Meeting Chat",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def get_chat_messages(conference_key: str, channel: str | None = None, limit: int = 2000) -> str:
    """Meeting chat messages (GET /api/conferencesHistory/{key}/chat/messages).

    Args:
        conference_key: the meeting's conference_key (from list_meetings or a recording detail).
        channel: fetch only this channel; omitted -> the meeting's default/main channel.
        limit: max messages returned.
    """
    params: dict = {"limit": limit}
    if channel:
        params["channel"] = channel
    try:
        data = await client.request("GET", f"/conferencesHistory/{conference_key}/chat/messages", params=params)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

@mcp.tool(
    annotations={
        "title": "Auth Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def auth_status() -> str:
    """Probe the configured credentials against a harmless request, and report which auth mode is active.

    api_key mode probes GET /api/Recordings/00000000-.../access. session mode
    probes GET /api/recordings with top=1. A 401 means the credential itself
    is missing/invalid/expired. A 403/404 means it authenticates but the
    specific probe target doesn't exist or isn't scoped -- both still count
    as a working credential. No parameters.
    """
    result = {
        "space_url": client.space_url,
        "auth_mode": client.auth_mode,
        "api_key_set": bool(client.api_key),
        "session_token_set": bool(client.session_token),
    }
    try:
        if client.auth_mode == "session":
            await client.request("GET", "/recordings", params={"top": 1})
        else:
            await client.request("GET", "/Recordings/00000000-0000-0000-0000-000000000000/access")
        result["status"] = "authenticated"
    except KtalkAPIError as e:
        if e.status == 401:
            result["status"] = "invalid_or_expired"
        elif e.status in (403, 404):
            result["status"] = "authenticated"
            result["note"] = f"probe returned {e.status}, which still requires a valid credential"
        else:
            result["status"] = "unknown"
            result["detail"] = str(e)
    return json.dumps(result, ensure_ascii=False)


def main():
    if not client.space_url:
        log.error("KTALK_SPACE_URL is not set. Point it at your Talk space, e.g. https://<your-space>.ktalk.ru")
        sys.exit(2)
    if client.auth_mode == "session" and not client.session_token:
        log.error("KTALK_AUTH_MODE=session but KTALK_SESSION_TOKEN is not set.")
        sys.exit(2)
    if client.auth_mode == "api_key" and not client.api_key:
        log.error("KTALK_API_KEY is not set.")
        sys.exit(2)
    log.info("space=%s auth_mode=%s", client.space_url, client.auth_mode)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    kwargs: dict = {}
    if transport in ("sse", "streamable-http"):
        kwargs["host"] = os.environ.get("MCP_HOST", "127.0.0.1")
        kwargs["port"] = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
