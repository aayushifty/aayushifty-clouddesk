"""
Tests for the Cloud Workspace (open/park) and the AI Gateway.
Portable: no D:/G: drives, no network - Drive is a temp folder, Gemini/Ollama are fake local servers.

    python -m pytest tests/test_cloud_native.py -q
"""
import json
import os
import stat
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if "win32cred" not in sys.modules:
    try:
        import win32cred  # noqa: F401
    except ImportError:
        sys.modules["win32cred"] = types.ModuleType("win32cred")

from fastapi.testclient import TestClient  # noqa: E402

from core import ai_gateway, cloud_workspace as cw, server  # noqa: E402
from core.workspace_manager import WorkspaceManager  # noqa: E402

WS = cw.CloudWorkspace


@pytest.fixture
def env(tmp_path, monkeypatch):
    drive, local = tmp_path / "MyDrive", tmp_path / "Workspace"
    drive.mkdir()
    local.mkdir()
    monkeypatch.setattr(cw.CloudDriveManager, "get_my_drive_path", classmethod(lambda c: drive))
    monkeypatch.setitem(cw.LOCAL_DIRS, "workspace", local)
    monkeypatch.setattr(cw, "VAULT_ROOT", tmp_path / "Vault")
    monkeypatch.setattr(cw, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(WorkspaceManager, "load_config", classmethod(lambda c: {}))
    return types.SimpleNamespace(cloud=drive / "Projects", local=local, vault=tmp_path / "Vault", tmp=tmp_path)


def make_cloud_project(env, name="site"):
    p = env.cloud / name
    (p / "src").mkdir(parents=True)
    (p / "src" / "app.js").write_text("console.log(1)")
    (p / "package.json").write_text('{"name":"site"}')
    (p / "old.txt").write_text("will be deleted")
    (p / ".git").mkdir()
    (p / ".git" / "config").write_text('[remote "origin"]\n\turl = https://github.com/aayushifty/site.git\n')
    return p


# ------------------------------------------------------------- open / park --
def test_round_trip_keeps_one_copy(env):
    make_cloud_project(env)
    r = WS.open("site", install_deps=False)
    work = env.local / "site"
    assert r["success"] and (work / "src" / "app.js").read_text() == "console.log(1)"

    # work on it: edit, delete, add secrets and regenerable junk
    (work / "src" / "app.js").write_text("console.log(2)")
    (work / "old.txt").unlink()
    (work / ".env").write_text("API_KEY=secret")
    (work / "node_modules" / "react").mkdir(parents=True)
    (work / "node_modules" / "react" / "index.js").write_text("x" * 1000)
    obj = work / ".git" / "objects" / "ab"
    obj.mkdir(parents=True)
    (obj / "cdef").write_text("blob")
    os.chmod(obj / "cdef", stat.S_IREAD)          # git objects are read-only on Windows

    r = WS.park("site")
    assert r["success"], r
    cloud = env.cloud / "site"
    assert not work.exists()                                    # laptop copy completely gone
    assert (cloud / "src" / "app.js").read_text() == "console.log(2)"
    assert not (cloud / "old.txt").exists()                     # deletion mirrored
    assert not (cloud / "node_modules").exists()                # never uploaded
    assert not (cloud / ".env").exists()                        # secrets never reach the cloud
    assert (env.vault / "site" / ".env").read_text() == "API_KEY=secret"
    assert (cloud / ".git" / "objects" / "ab" / "cdef").exists()

    r = WS.open("site", install_deps=False)
    assert r["secrets_restored"] == 1
    assert (work / ".env").read_text() == "API_KEY=secret"
    assert not (env.vault / "site").exists()                    # single copy of secrets


def test_park_keeps_laptop_copy_if_verification_fails(env, monkeypatch):
    make_cloud_project(env)
    WS.open("site", install_deps=False)
    calls = iter(range(10_000))
    monkeypatch.setattr(cw, "sha256", lambda p: str(next(calls)))  # every hash differs
    r = WS.park("site")
    assert r["success"] is False and r["mismatched_files"]
    assert (env.local / "site" / "src" / "app.js").exists()


def test_open_is_idempotent_and_reports_already_local(env):
    make_cloud_project(env)
    WS.open("site", install_deps=False)
    assert WS.open("site", install_deps=False)["already_on_laptop"] is True


def test_list_projects_states(env):
    make_cloud_project(env, "parked-one")
    (env.local / "working-one").mkdir()
    rows = {p["name"]: p for p in WS.list_projects()}
    assert rows["parked-one"]["status"] == "parked" and rows["parked-one"]["github"] == "aayushifty/site"
    assert rows["working-one"]["status"] == "working"


def test_auto_park_only_idle_projects(env):
    for name, age_days in (("idle", 30), ("busy", 0)):
        d = env.local / name
        d.mkdir()
        f = d / "main.py"
        f.write_text("print(1)")
        t = time.time() - age_days * 86400
        os.utime(f, (t, t))
    res = WS.auto_park(7)
    assert [list(x)[0] for x in res["parked"]] == ["idle"]
    assert not (env.local / "idle").exists() and (env.local / "busy").exists()
    assert (env.cloud / "idle" / "main.py").exists()


@pytest.mark.parametrize("bad", ["..", "../x", "a/b", r"a\b", "", "C:", "con*"])
def test_project_names_cannot_escape(env, bad):
    with pytest.raises(ValueError):
        WS.open(bad)


def test_dependency_detection(env, monkeypatch):
    monkeypatch.setattr(cw.shutil, "which", lambda n: f"/bin/{n}")
    p = env.local / "proj"
    p.mkdir()
    (p / "package.json").write_text("{}")
    (p / "package-lock.json").write_text("{}")
    (p / "requirements.txt").write_text("requests")
    cmds = WS.dependency_commands(p)
    assert cmds[0][1:] == ["ci", "--no-audit", "--no-fund"]
    assert cmds[1][1:3] == ["-m", "venv"] and cmds[2][-1].endswith("requirements.txt")


def test_drive_offline_is_clear_error(env, monkeypatch):
    monkeypatch.setattr(cw.CloudDriveManager, "get_my_drive_path", classmethod(lambda c: None))
    with pytest.raises(RuntimeError, match="Google Drive"):
        WS.cloud_root()
    client = TestClient(server.app, base_url="http://127.0.0.1:8765")
    assert client.post("/api/workspace/open", json={"name": "x"}).status_code == 503


# ---------------------------------------------------------------- AI gateway --
class _Fake(BaseHTTPRequestHandler):
    status = 200
    seen: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self._send(200, {"data": [{"id": self.server.model_id}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.seen.append((self.headers.get("Authorization"), body))
        if self.server.fail:
            return self._send(503, {"error": {"message": "overloaded"}})
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n')
            return
        self._send(200, {"model": body["model"], "choices": [{"message": {"content": f"from {self.server.label}"}}]})

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _server(label, model_id, fail=False):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    srv.label, srv.model_id, srv.fail, srv.seen = label, model_id, fail, []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture
def gw(monkeypatch):
    gem, gem_url = _server("gemini", "models/gemini-2.5-flash")
    oll, oll_url = _server("ollama", "qwen3:4b-instruct")
    monkeypatch.setattr(ai_gateway, "GEMINI_BASE", gem_url)
    monkeypatch.setattr(ai_gateway, "OLLAMA_BASE", oll_url)
    monkeypatch.setattr(ai_gateway, "gemini_key", lambda: "test-key")
    monkeypatch.setattr(WorkspaceManager, "load_config", classmethod(lambda c: {}))
    ai_gateway.list_models.cache_clear()
    ai_gateway.status.cache_clear()
    yield types.SimpleNamespace(gem=gem, oll=oll)
    gem.shutdown()
    oll.shutdown()


def test_route_rules():
    assert ai_gateway.route("auto")[0] == "gemini"
    assert ai_gateway.route("gpt-4o") == ("gemini", "gemini-2.5-flash")   # agents with hard-coded OpenAI names
    assert ai_gateway.route("gemini-2.5-pro") == ("gemini", "gemini-2.5-pro")
    assert ai_gateway.route("local:llama3.2") == ("local", "llama3.2")


def test_chat_goes_to_gemini_with_vault_key(gw):
    client = TestClient(server.app, base_url="http://127.0.0.1:8765")
    r = client.post("/v1/chat/completions", json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.headers["x-clouddesk-backend"] == "gemini"
    assert r.json()["choices"][0]["message"]["content"] == "from gemini"
    auth, body = gw.gem.seen[0]
    assert auth == "Bearer test-key" and body["model"] == "gemini-2.5-flash"


def test_falls_back_to_local_ollama_when_cloud_down(gw):
    gw.gem.fail = True
    client = TestClient(server.app, base_url="http://127.0.0.1:8765")
    r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.headers["x-clouddesk-backend"] == "local-fallback"
    assert gw.oll.seen[0][0] is None                       # key never sent to Ollama
    assert gw.oll.seen[0][1]["model"] == "qwen3:4b-instruct"


def test_streaming_passthrough(gw):
    client = TestClient(server.app, base_url="http://127.0.0.1:8765")
    r = client.post("/v1/chat/completions", json={"model": "auto", "stream": True, "messages": []})
    assert r.status_code == 200 and "[DONE]" in r.text and r.headers["content-type"].startswith("text/event-stream")


def test_websites_cannot_spend_your_key(gw):
    client = TestClient(server.app, base_url="http://127.0.0.1:8765")
    r = client.post("/v1/chat/completions", json={"messages": []}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403 and gw.gem.seen == []


def test_models_and_status(gw):
    client = TestClient(server.app, base_url="http://127.0.0.1:8765")
    ids = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert ids == ["auto", "gemini-2.5-flash", "local:qwen3:4b-instruct"]
    s = client.get("/api/ai/status?refresh=true").json()
    assert s["gemini_reachable"] and s["ollama_running"] and s["gemini_key_configured"]


# --------------------------------------------------------------------- cdesk --
def test_cdesk_cli_open_park_by_path(env, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import cdesk
    make_cloud_project(env)
    assert cdesk.main(["open-path", str(env.cloud / "site" / "src"), "--no-deps"]) == 0   # any folder inside works
    assert (env.local / "site").exists()
    assert cdesk.main(["list"]) == 0 and "[LAPTOP] site" in capsys.readouterr().out
    assert cdesk.main(["park-path", str(env.local / "site")]) == 0
    assert not (env.local / "site").exists()
    assert cdesk.main(["park-path", str(env.tmp)]) == 1                                   # outside both roots
