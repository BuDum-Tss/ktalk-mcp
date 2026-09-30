"""Kontur Talk MCP server -- recordings, transcripts, summaries.

Auth is a Talk API key (personal or domain), sent as ``X-Auth-Token``. See
README.md for how to issue one and which scope each tool needs.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from fastmcp import FastMCP

from ktalk_mcp_apikey.client import KtalkAPIError, client_from_env

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
        "Kontur Talk (ktalk.ru) tools for recordings, transcripts and summaries, "
        "authenticated with an API key (X-Auth-Token) instead of a browser session. "
        "Every recording_key is the id from a Talk recording URL or from list_recordings. "
        "A 403 from any tool means the key is valid but lacks the required scope -- "
        "check the key's scopes in Talk settings, see README.md."
    ),
)


def _err_to_json(e: Exception) -> str:
    if isinstance(e, KtalkAPIError):
        return json.dumps({"error": "api_error", "status": e.status, "message": str(e)}, ensure_ascii=False)
    return json.dumps({"error": "unexpected", "message": str(e)}, ensure_ascii=False)


@mcp.tool(
    annotations={
        "title": "List Space Recordings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def list_recordings(
    top: int = 30,
    page_token: str | None = None,
    query: str | None = None,
    start_from: str | None = None,
    start_to: str | None = None,
) -> str:
    """List recordings in the whole space (GET /api/Domain/recordings/v2).

    Requires a *domain* API key with the "Просмотр списка записей"
    (readDomainRecordings) scope -- a personal key will get a 403 here even if
    it can read individual recordings. If you only have a personal key, get
    recording_key values from Talk's own UI / recording URLs instead and call
    get_recording / get_transcript / get_summary directly.

    Args:
        top: page size.
        page_token: pagination token from a previous call's response, if any.
        query: title search substring.
        start_from: ISO-8601 window start.
        start_to: ISO-8601 window end.
    """
    params: dict = {"top": top}
    if page_token:
        params["pageTokenString"] = page_token
    if query:
        params["query"] = query
    if start_from:
        params["startFrom"] = start_from
    if start_to:
        params["startTo"] = start_to
    try:
        data = await client.request("GET", "/Domain/recordings/v2", params=params)
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
    """Recording detail: title, author, date, duration, participants (GET /api/Recordings/{key}).

    Args:
        recording_key: the recording's id, from its Talk URL or from list_recordings.
    """
    try:
        data = await client.request("GET", f"/Recordings/{recording_key}")
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

    Returns the API's raw JSON -- shape (speaker turns, timecodes) is whatever
    Talk sends, not reshaped here.

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
    """Meeting summary: short recap and/or protocol.

    Without summary_type, calls GET /api/recordings/v2/{key}/summary, which
    returns protocol + short summary + transcript together. With summary_type
    set to "shortSummary" or "protocol", calls the narrower
    GET /api/recordings/{key}/summary/{type} instead.

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
async def download_recording(recording_key: str, quality: str, target_path: str) -> str:
    """Download a recording's video file to disk. An existing file at target_path is overwritten.

    Call get_recording first to find available quality names (e.g. "900p") --
    they are not guessed here.

    Args:
        recording_key: the recording's id.
        quality: quality name as listed on the recording (e.g. "900p").
        target_path: destination file path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(target_path)) or ".", exist_ok=True)
    try:
        path, size = await client.download(f"/Recordings/{recording_key}/file/{quality}", target_path)
    except KtalkAPIError as e:
        return _err_to_json(e)
    return json.dumps({"ok": True, "path": path, "bytes": size}, ensure_ascii=False)


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
    """Probe the configured API key against GET /api/Recordings/{key} with a bogus id.

    A 401 means the key itself is missing/invalid. A 404 (recording not found,
    but the key was accepted) or a 403 (valid key, missing scope) both mean the
    key authenticates -- only 401 is a real auth failure. No parameters.
    """
    result = {"space_url": client.space_url, "key_set": bool(client.api_key)}
    try:
        await client.request("GET", "/Recordings/00000000-0000-0000-0000-000000000000")
        result["status"] = "unexpected_success"
    except KtalkAPIError as e:
        if e.status == 401:
            result["status"] = "invalid_key"
        elif e.status in (403, 404):
            result["status"] = "key_valid"
            result["note"] = f"probe returned {e.status}, which requires a valid key"
        else:
            result["status"] = "unknown"
            result["detail"] = str(e)
    return json.dumps(result, ensure_ascii=False)


def main():
    if not client.space_url:
        log.error("KTALK_SPACE_URL is not set. Point it at your Talk space, e.g. https://<your-space>.ktalk.ru")
        sys.exit(2)
    if not client.api_key:
        log.error("KTALK_API_KEY is not set.")
        sys.exit(2)
    log.info("space=%s", client.space_url)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    kwargs: dict = {}
    if transport in ("sse", "streamable-http"):
        kwargs["host"] = os.environ.get("MCP_HOST", "127.0.0.1")
        kwargs["port"] = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
