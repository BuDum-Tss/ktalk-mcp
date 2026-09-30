"""Kontur Talk (ktalk.ru) public HTTP API client, authenticated with an API key.

Talk has two auth schemes for the officially documented public API
(see talk.public.api-api-2.json in this repo, security scheme "xAuthToken"):

- a domain (space) API key, issued by a space admin in the admin panel
  ("Управление" -> "API-ключи"), scoped to the whole space;
- a personal API key, issued by the user themselves (avatar -> "Настройки" ->
  "API ключи"), scoped to only the data that user can already see.

Both are sent the same way: header ``X-Auth-Token: <key>``. Which endpoints a
given key can actually call depends on the scopes it was granted when issued
(see README) -- a personal key with only the "Записи" (Recordings) read scope
can fetch a known recording's detail/transcript/summary, but the domain-level
listing endpoints (``/api/Domain/recordings``) require a domain key with the
"Просмотр списка записей" scope.
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
    def __init__(self, space_url: str, api_key: str, verify_ssl: bool = True):
        self.space_url = (space_url or "").rstrip("/")
        self.base_url = f"{self.space_url}/api"
        self.api_key = api_key
        self.verify_ssl = verify_ssl

    def _headers(self) -> dict:
        if not self.api_key:
            raise KtalkAPIError("KTALK_API_KEY is not set")
        return {"X-Auth-Token": self.api_key, "Accept": "application/json"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
    ) -> dict | list:
        """Call the Talk public API and return parsed JSON."""
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            try:
                resp = await client.request(
                    method, url, headers=self._headers(), params=params,
                    timeout=30.0, follow_redirects=True,
                )
            except httpx.HTTPError as e:
                raise KtalkAPIError(f"Network error on {method} {path}: {e}")
        if resp.status_code == 401:
            raise KtalkAPIError(
                "HTTP 401: API key rejected or missing — check KTALK_API_KEY and KTALK_SPACE_URL",
                status=401,
            )
        if resp.status_code == 403:
            raise KtalkAPIError(
                f"HTTP 403: key is valid but lacks the scope for {method} {path} "
                "— check the key's scopes in Talk settings",
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

    async def download(self, path: str, dest_path: str) -> tuple[str, int]:
        """Stream a file endpoint (e.g. the recording video) to ``dest_path``."""
        url = f"{self.base_url}{path}"
        total = 0
        timeout = httpx.Timeout(30.0, read=600.0)
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            async with client.stream(
                "GET", url, headers=self._headers(), timeout=timeout, follow_redirects=True
            ) as resp:
                if resp.status_code == 401:
                    raise KtalkAPIError("HTTP 401: API key rejected or missing", status=401)
                if resp.status_code == 403:
                    raise KtalkAPIError("HTTP 403: key lacks scope to download this file", status=403)
                if resp.status_code >= 400:
                    raise KtalkAPIError(f"HTTP {resp.status_code} downloading file", status=resp.status_code)
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
                        total += len(chunk)
        return dest_path, total


def client_from_env() -> KtalkClient:
    space_url = os.environ.get("KTALK_SPACE_URL", "").strip()
    api_key = os.environ.get("KTALK_API_KEY", "").strip()
    verify_ssl = os.environ.get("KTALK_VERIFY_SSL", "true").lower() not in ("false", "0", "no")
    return KtalkClient(space_url=space_url, api_key=api_key, verify_ssl=verify_ssl)
