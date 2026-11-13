"""
Regression tests for the performance / security hardening pass.
Portable: run on Windows or Linux (Windows-only modules are stubbed), no D:/E:/G: needed.

    python -m pytest tests/test_hardening.py -q
"""
import os
import sys
import time
import types
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

from core import server  # noqa: E402
from core.ttl_cache import ttl_cache  # noqa: E402
from core.cache_manager import _safe_name  # noqa: E402
from core.storage_optimizer import StorageOptimizer  # noqa: E402
from core import project_lifecycle, workspace_manager  # noqa: E402

LOCAL = "http://127.0.0.1:8765"


@pytest.fixture
def client():
    return TestClient(server.app, base_url=LOCAL)


def _age(p: Path, days: float):
    t = time.time() - days * 86400
    os.utime(p, (t, t))


# ------------------------------------------------------------------ security --
def test_dns_rebinding_host_rejected(client):
    r = client.get("/api/guard", headers={"host": "evil.example"})
    assert r.status_code == 400


def test_cross_site_post_blocked(client):
    r = client.post("/api/storage/purge-c-ollama?confirmed=true", headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/automation/sync-now", headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403


def test_dashboard_origin_allowed(client):
    # reaches the endpoint (which then rejects the non-web URL) instead of the 403 guard
    r = client.post("/api/actions/open-url", json={"path": "ftp://x"}, headers={"origin": LOCAL})
    assert r.status_code == 400


@pytest.mark.parametrize("bad", [r"C:\Windows\System32\calc.exe", "file:///C:/x.exe", "javascript:alert(1)", "calc"])
def test_open_url_only_web_links(client, monkeypatch, bad):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open", opened.append)
    assert client.post("/api/actions/open-url", json={"path": bad}).status_code == 400
    assert opened == []


def test_open_url_https_ok(client, monkeypatch):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open", opened.append)
    assert client.post("/api/actions/open-url", json={"path": "https://colab.research.google.com/"}).status_code == 200
    assert opened == ["https://colab.research.google.com/"]


def test_open_vscode_refuses_shell_metacharacters(client, tmp_path, monkeypatch):
    evil = tmp_path / "proj & calc"
    evil.mkdir()
    launched = []
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: launched.append(a))
    assert client.post("/api/actions/open-vscode", json={"path": str(evil)}).status_code == 400
    assert launched == []


def test_open_vscode_no_shell(client, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(server.shutil, "which", lambda n: "/usr/bin/code")
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    assert client.post("/api/actions/open-vscode", json={"path": str(tmp_path)}).status_code == 200
    (args,), kwargs = calls[0]
    assert args == ["/usr/bin/code", str(tmp_path.resolve())] and not kwargs.get("shell")


@pytest.mark.parametrize("bad", ["../../Windows/x", "..", "a/b", r"a\b", "C:x", ""])
def test_model_names_cannot_escape_cache(bad):
    with pytest.raises(ValueError):
        _safe_name(bad)


def test_model_name_plain_ok():
    assert _safe_name("gemma3-4b.gguf") == "gemma3-4b.gguf"


# --------------------------------------------------------------- performance --
def test_ttl_cache_and_refresh():
    calls = []

    @ttl_cache(60)
    def scan():
        calls.append(1)
        return len(calls)

    assert scan() == 1 and scan() == 1          # cached
    assert scan(refresh=True) == 2              # forced rescan
    scan.cache_clear()
    assert scan() == 3


# ------------------------------------------------------------- temp cleaning --
def test_temp_clean_keeps_live_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(StorageOptimizer, "SAFE_TEMP_DIRS", [tmp_path])
    live = tmp_path / "_MEI12345"            # e.g. a running PyInstaller app
    live.mkdir()
    (live / "python311.dll").write_bytes(b"x" * 10)          # fresh file inside
    _age(live, 5)                                            # old folder date
    old = tmp_path / "old.log"
    old.write_bytes(b"y" * 20)
    _age(old, 5)
    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    (stale_dir / "a.tmp").write_bytes(b"z")
    _age(stale_dir / "a.tmp", 5)

    res = StorageOptimizer.clean_safe_temp_files()
    assert (live / "python311.dll").exists()          # the old code rmtree'd this folder
    assert not old.exists() and not stale_dir.exists()
    assert res["deleted_items"] == 2


# ------------------------------------------------------------------ sync diff --
def test_sync_recopies_same_size_edits(tmp_path, monkeypatch):
    proj, drive, stage = tmp_path / "proj", tmp_path / "drive", tmp_path / "stage"
    (proj / "assets").mkdir(parents=True)
    drive.mkdir()
    f = proj / "assets" / "notes.md"
    f.write_text("AAAA")
    monkeypatch.setattr(workspace_manager, "MAPPINGS_FILE", tmp_path / "map.json")
    monkeypatch.setitem(project_lifecycle.LOCAL_DIRS, "staging", stage)
    monkeypatch.setattr(project_lifecycle.CloudDriveManager, "get_my_drive_path", classmethod(lambda c: drive))
    workspace_manager.WorkspaceManager.save_mapping("p", {"local_path": str(proj), "status": "active"})

    PLM = project_lifecycle.ProjectLifecycleManager
    assert PLM.sync_project_assets("p")["synced_count"] == 1
    assert PLM.sync_project_assets("p")["synced_count"] == 0     # unchanged -> skipped

    f.write_text("BBBB")                                          # same size, new content
    os.utime(f, (time.time() + 10, time.time() + 10))
    assert PLM.sync_project_assets("p")["synced_count"] == 1
    assert (drive / "Projects" / "p" / "assets" / "notes.md").read_text() == "BBBB"


# ------------------------------------------------------------- new endpoints --
def test_guard_endpoint(client, tmp_path, monkeypatch):
    status = tmp_path / "guard_status.json"
    monkeypatch.setattr(server, "GUARD_STATUS_FILE", status)
    assert client.get("/api/guard").json()["running"] is False
    status.write_text('{"ram_percent": 71.2, "disk_free_gb": 22.5, "actions": []}')
    g = client.get("/api/guard").json()
    assert g["running"] is True and g["ram_percent"] == 71.2


def test_projects_endpoint_exists(client, monkeypatch):
    monkeypatch.setattr(server.CloudDevManager, "discover_local_projects", staticmethod(lambda: [{"name": "x"}]))
    monkeypatch.setattr(server.CloudDevManager, "get_user_repositories", staticmethod(lambda limit=15: []))
    r = client.get("/api/projects?refresh=true")
    assert r.status_code == 200 and r.json()["local_projects"] == [{"name": "x"}]


def test_colab_generate_endpoint(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server.CloudDriveManager, "get_my_drive_path", classmethod(lambda c: tmp_path))
    r = client.post("/api/colab/generate")
    assert r.status_code == 200
    assert Path(r.json()["path"]).exists()
