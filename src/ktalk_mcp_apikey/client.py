"""Kontur Talk (ktalk.ru) HTTP API client, with two interchangeable auth modes.

1. ``api_key`` -- the officially documented public API (see
   talk.public.api-api-2.json in this repo, security scheme "xAuthToken"):
   header ``X-Auth-Token: <key>``. A personal key (issued by the user in
   avatar -> "Настройки" -> "API ключи") has a *fixed*, non-configurable
   scope set that -- empirically, see scripts/probe_scopes.py -- does not
   include recordings/transcripts/summaries at all, only rooms/users/
   calendar-ish endpoints. A domain key (issued by a space admin) can be
   granted the "Записи" scope and reach the ``/Domain/recordings*``
   endpoints.

2. ``session`` -- the same browser session Talk's own web app uses, header
   ``Authorization: Session <token>``. This is not scope-limited the way a
   personal API key is: it sees whatever the logged-in user can see in the
   UI, via a set of lowercase, undocumented-but-stable paths (``/recordings``,
   ``/recordings/{id}``, ``/conferencesHistory/...``) that mirror what
   community tools (mainpart/ktalk-mcp, mdemyanov/ktalk-cli) already use in
   production. The token lives in the browser's localStorage and expires in
   ~30 days; see README for how to extract it.
"""

from __future__ import annotations

import os

import httpx


class KtalkAPIError(Exception):
    """Any non-2xx response or network failure."""

    def __init__(self, message: str, status: int | None = None):
        self.status = status
        super().__init__(message)


class KtalkClient:
    def __init__(
        self,
        space_url: str,
        auth_mode: str,
        api_key: str | None = None,
        session_token: str | None = None,
        verify_ssl: bool = True,
    ):
        self.space_url = (space_url or "").rstrip("/")
        self.base_url = f"{self.space_url}/api"
        self.auth_mode = auth_mode  # "api_key" | "session"
        self.api_key = api_key
        self.session_token = session_token
        self.verify_ssl = verify_ssl

    def _headers(self) -> dict:
        if self.auth_mode == "session":
            if not self.session_token:
                raise KtalkAPIError("KTALK_SESSION_TOKEN is not set")
            return {"Authorization": f"Session {self.session_token}", "Accept": "application/json"}
        if not self.api_key:
            raise KtalkAPIError("KTALK_API_KEY is not set")
        return {"X-Auth-Token": self.api_key, "Accept": "application/json"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        absolute_url: str | None = None,
    ) -> dict | list:
        """Call the Talk API and return parsed JSON.

        ``absolute_url`` bypasses ``base_url`` entirely -- used for the
        per-recording file URLs Talk hands back in ``qualities[].fileUrl``,
        which are relative to ``space_url`` (no ``/api``), not to it.
        """
        url = absolute_url or f"{self.base_url}{path}"
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            try:
                resp = await client.request(
                    method, url, headers=self._headers(), params=params,
                    timeout=30.0, follow_redirects=True,
                )
            except httpx.HTTPError as e:
                raise KtalkAPIError(f"Network error on {method} {path}: {e}")
        if resp.status_code == 401:
            hint = (
                "session token missing/expired — re-extract it (see README)"
                if self.auth_mode == "session"
                else "API key rejected or missing — check KTALK_API_KEY"
            )
            raise KtalkAPIError(f"HTTP 401: {hint}", status=401)
        if resp.status_code == 403:
            raise KtalkAPIError(
                f"HTTP 403: authenticated but not allowed to {method} {path} "
                "— in api_key mode this usually means a missing scope; in session mode "
                "it means the logged-in user itself can't access this",
                status=403,
            )
        if resp.status_code >= 400:
            raise KtalkAPIError(f"HTTP {resp.status_code}: {resp.text[:500]}", status=resp.status_code)
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    async def download(self, *, path: str | None = None, absolute_url: str | None = None, dest_path: str) -> tuple[str, int]:
        """Stream a file endpoint (e.g. the recording video) to ``dest_path``."""
        if absolute_url and not absolute_url.startswith(("http://", "https://")):
            absolute_url = f"{self.space_url}/{absolute_url.lstrip('/')}"
        url = absolute_url or f"{self.base_url}{path}"
        total = 0
        timeout = httpx.Timeout(30.0, read=600.0)
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            async with client.stream(
                "GET", url, headers=self._headers(), timeout=timeout, follow_redirects=True
            ) as resp:
                if resp.status_code == 401:
                    raise KtalkAPIError("HTTP 401: not authenticated", status=401)
                if resp.status_code == 403:
                    raise KtalkAPIError("HTTP 403: not allowed to download this file", status=403)
                if resp.status_code >= 400:
                    raise KtalkAPIError(f"HTTP {resp.status_code} downloading file", status=resp.status_code)
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
                        total += len(chunk)
        return dest_path, total


def client_from_env() -> KtalkClient:
    space_url = os.environ.get("KTALK_SPACE_URL", "").strip()
    api_key = os.environ.get("KTALK_API_KEY", "").strip() or None
    session_token = os.environ.get("KTALK_SESSION_TOKEN", "").strip() or None
    verify_ssl = os.environ.get("KTALK_VERIFY_SSL", "true").lower() not in ("false", "0", "no")

    auth_mode = os.environ.get("KTALK_AUTH_MODE", "").strip().lower()
    if auth_mode not in ("api_key", "session"):
        auth_mode = "session" if session_token else "api_key"

    return KtalkClient(
        space_url=space_url,
        auth_mode=auth_mode,
        api_key=api_key,
        session_token=session_token,
        verify_ssl=verify_ssl,
    )
