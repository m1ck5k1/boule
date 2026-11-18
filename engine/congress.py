"""Congress.gov API client.

The key comes from CONGRESS_API_KEY. With no key we fall back to DEMO_KEY, which
WORKS but is throttled hard (observed: x-ratelimit-limit: 10). That is enough to
prove a gate against one bill and nowhere near enough to poll. So the fallback is
allowed but always announced — never silent.

Stdlib only (urllib), so the engine runs anywhere Python does.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.congress.gov/v3"


def _load_dotenv() -> None:
    """Minimal .env loader — stdlib only, no python-dotenv dependency.

    A real environment variable ALWAYS wins, so CI can inject
    CONGRESS_API_KEY as a GitHub Actions secret without a stale local file
    shadowing it.
    """
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# Cloudflare sits in front of api.congress.gov and rejects the default
# "Python-urllib/3.12" User-Agent with `error code: 1010`. Identify the client
# honestly rather than spoofing a browser.
USER_AGENT = "boule/0.1 (+https://github.com/m1ck5k1/boule)"


class ApiError(RuntimeError):
    pass


def _ssl_context() -> ssl.SSLContext:
    """macOS python.org builds ship no CA bundle, so urllib dies with
    CERTIFICATE_VERIFY_FAILED while curl works fine. Prefer certifi, then the
    usual system paths, then whatever the platform default is."""
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for path in (
        "/etc/ssl/cert.pem",
        "/opt/homebrew/etc/openssl@3/cert.pem",
        "/opt/homebrew/etc/ca-certificates/cert.pem",
        "/usr/local/etc/openssl@3/cert.pem",
    ):
        if os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


def api_key() -> str:
    return os.environ.get("CONGRESS_API_KEY") or "DEMO_KEY"


def using_demo_key() -> bool:
    return not os.environ.get("CONGRESS_API_KEY")


def get(path: str, **params) -> dict:
    """GET {BASE}{path}. Retries 429/network with backoff."""
    params.setdefault("format", "json")
    params["api_key"] = api_key()
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    ctx = _ssl_context()

    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
                continue
            detail = exc.read()[:300].decode("utf-8", "replace")
            raise ApiError(f"HTTP {exc.code} on {url}\n{detail}") from exc
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(2 ** attempt)

    raise ApiError(f"gave up on {url}: {last}")


def fetch_bill(congress: int, bill_type: str, number: int) -> dict:
    return get(f"/bill/{congress}/{bill_type}/{number}")["bill"]


def fetch_actions(congress: int, bill_type: str, number: int, limit: int = 250) -> list[dict]:
    """All recorded actions, oldest-first as returned by congress.gov.

    /actions is the endpoint that matters: it is the only place stage history and
    roll-call links live together.
    """
    out: list[dict] = []
    offset = 0
    while True:
        page = get(f"/bill/{congress}/{bill_type}/{number}/actions",
                   limit=limit, offset=offset)
        batch = page.get("actions", [])
        out.extend(batch)
        total = page.get("pagination", {}).get("count", len(out))
        if not batch or len(out) >= total:
            break
        offset += len(batch)
    return out
