"""
AI Gateway - cloud models behind a local, OpenAI-compatible endpoint.

Any agent, IDE plugin or script that speaks the OpenAI API can point at

    OPENAI_BASE_URL = http://127.0.0.1:8765/v1      OPENAI_API_KEY = clouddesk

and it runs on Google Gemini in the cloud - 0 MB of laptop RAM/VRAM instead of
2-4 GB for a local Ollama model. The real Gemini key never leaves Windows
Credential Manager; tools only ever see the dummy key.

Routing (model field of the request):
    "auto" / "" / "cloud"   -> default Gemini model (config: ai_gateway.default_model)
    "gemini-..."            -> that Gemini model
    "local:<ollama model>"  -> local Ollama (explicit opt-in)
If Gemini is unreachable (offline, quota, outage) and local_fallback is on, the
request is retried on the local Ollama model so agents keep working offline.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.ttl_cache import ttl_cache
from core.workspace_manager import WorkspaceManager

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
OLLAMA_BASE = os.environ.get("OLLAMA_OPENAI_BASE", "http://127.0.0.1:11434/v1")

DEFAULTS = {
    "default_model": "gemini-2.5-flash",
    "local_fallback": True,
    "local_model": "qwen3:4b-instruct",
    "timeout_seconds": 300,
}


class GatewayError(Exception):
    def __init__(self, status: int, body: bytes):
        super().__init__(f"HTTP {status}")
        self.status, self.body = status, body


def config() -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg.update(WorkspaceManager.load_config().get("ai_gateway", {}) or {})
    return cfg


def gemini_key() -> Optional[str]:
    try:
        from core.credentials_vault import CredentialsVault
        key = CredentialsVault.get_secret("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def _open(url: str, payload: Optional[dict], key: Optional[str], timeout: float):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - fixed hosts
    except urllib.error.HTTPError as e:
        raise GatewayError(e.code, e.read() or b"{}") from None


def route(model: Optional[str]) -> Tuple[str, str]:
    """-> (backend, model_name) where backend is 'gemini' or 'local'."""
    cfg = config()
    m = (model or "").strip()
    if m.startswith("local:"):
        return "local", m[len("local:"):] or cfg["local_model"]
    if m in ("", "auto", "cloud", "default") or not m.startswith(("gemini", "models/gemini", "gemma")):
        # unknown names (e.g. "gpt-4o" hard-coded in an agent) go to the default cloud model
        return "gemini", cfg["default_model"]
    return "gemini", m


def chat(body: Dict[str, Any]) -> Tuple[str, Any]:
    """
    Forward an OpenAI chat.completions request. Returns (backend_used, http_response).
    The response is a file-like object; stream it straight back to the caller.
    """
    cfg = config()
    backend, model = route(body.get("model"))
    timeout = float(cfg["timeout_seconds"])
    payload = dict(body, model=model)

    if backend == "gemini":
        key = gemini_key()
        try:
            if not key:
                raise GatewayError(401, b'{"error":{"message":"GEMINI_API_KEY is not set in the CloudDesk vault"}}')
            return "gemini", _open(f"{GEMINI_BASE}/chat/completions", payload, key, timeout)
        except (GatewayError, urllib.error.URLError, TimeoutError, OSError) as e:
            retryable = not isinstance(e, GatewayError) or e.status in (401, 403, 408, 429, 500, 502, 503, 504)
            if not (cfg["local_fallback"] and retryable):
                raise
            payload["model"] = cfg["local_model"]
            try:
                return "local-fallback", _open(f"{OLLAMA_BASE}/chat/completions", payload, None, timeout)
            except (urllib.error.URLError, OSError):
                raise e from None
    return "local", _open(f"{OLLAMA_BASE}/chat/completions", payload, None, timeout)


def stream_body(resp, chunk: int = 4096) -> Iterator[bytes]:
    try:
        while True:
            data = resp.read1(chunk) if hasattr(resp, "read1") else resp.read(chunk)
            if not data:
                break
            yield data
    finally:
        resp.close()


@ttl_cache(600)
def list_models() -> Dict[str, Any]:
    cfg = config()
    models: List[Dict[str, Any]] = [{"id": "auto", "object": "model", "owned_by": f"clouddesk -> {cfg['default_model']}"}]
    key = gemini_key()
    if key:
        try:
            with _open(f"{GEMINI_BASE}/models", None, key, 15) as r:
                for m in json.loads(r.read()).get("data", []):
                    mid = m.get("id", "").replace("models/", "")
                    if mid.startswith(("gemini", "gemma")):
                        models.append({"id": mid, "object": "model", "owned_by": "google (cloud)"})
        except Exception:
            pass
    try:
        with _open(f"{OLLAMA_BASE}/models", None, None, 3) as r:
            for m in json.loads(r.read()).get("data", []):
                models.append({"id": f"local:{m.get('id')}", "object": "model", "owned_by": "ollama (laptop)"})
    except Exception:
        pass
    return {"object": "list", "data": models}


@ttl_cache(120)
def status() -> Dict[str, Any]:
    cfg = config()
    ids = [m["id"] for m in list_models()["data"]]
    return {
        "endpoint": "http://127.0.0.1:8765/v1",
        "gemini_key_configured": bool(gemini_key()),
        "gemini_reachable": any(not i.startswith("local:") and i != "auto" for i in ids),
        "ollama_running": any(i.startswith("local:") for i in ids),
        "default_model": cfg["default_model"],
        "local_fallback": cfg["local_fallback"],
        "local_model": cfg["local_model"],
        "how_to_use": {"OPENAI_BASE_URL": "http://127.0.0.1:8765/v1", "OPENAI_API_KEY": "clouddesk", "model": "auto"},
    }
