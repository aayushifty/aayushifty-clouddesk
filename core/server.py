"""
FastAPI Server Backend - Aayushifty CloudDesk 2.0
Cloud-First Architecture Engine.
Integrates Google Drive primary storage layer, Intelligent Local Workspace (D:\\ & E:\\),
differential asset synchronization, safe cache eviction, and project lifecycle management.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from core.system_monitor import SystemMonitor
from core.cloud_drive import CloudDriveManager
from core.storage_optimizer import StorageOptimizer
from core.backup_engine import BackupEngine
from core.cloud_dev import CloudDevManager
from core.credentials_vault import CredentialsVault
from core.workspace_manager import WorkspaceManager, LOCAL_DIRS
from core.project_lifecycle import ProjectLifecycleManager
from core.cache_manager import CacheManager
from core.ai_asset_manager import AIAssetManager
from core.automation_engine import AutomationEngine
from core.ttl_cache import ttl_cache
from core.cloud_workspace import CloudWorkspace
from core import ai_gateway

app = FastAPI(
    title="Aayushifty CloudDesk 2.0 API",
    version="2.0.0",
    description="Cloud-First Hybrid Development Environment Engine"
)

# Strict Localhost binding policy - NEVER expose to public internet
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Binding to 127.0.0.1 is not enough on its own: any website you visit can still
# send requests to localhost. Two guards close that:
#  1. DNS rebinding - a site whose domain resolves to 127.0.0.1 sends its own Host
#     header, so only accept Host = localhost / 127.0.0.1.
#  2. Cross-site requests - browsers always attach an Origin header to cross-site
#     POST/DELETE. Reject state-changing requests from any origin but the dashboard.
#     (Simple POSTs such as /api/storage/purge-c-ollama?confirmed=true need no CORS
#     preflight, so CORS alone did not stop them.)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

ALLOWED_ORIGINS = {"http://127.0.0.1:8765", "http://localhost:8765"}


@app.middleware("http")
async def block_cross_site_writes(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        site = request.headers.get("sec-fetch-site")
        if (origin and origin not in ALLOWED_ORIGINS) or site == "cross-site":
            return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)
    return await call_next(request)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "dashboard" / "static"


# ---------------- API Schemas ----------------

class CreateProjectRequest(BaseModel):
    project_name: str
    template: str = "empty"
    init_git: bool = True
    create_gh_repo: bool = False


class CompleteProjectRequest(BaseModel):
    project_name: str
    evict_local_build_artifacts: bool = True


class RestoreProjectRequest(BaseModel):
    archive_path: str
    restore_name: Optional[str] = None


class BackupRequest(BaseModel):
    project_path: str
    destination: Optional[str] = None


class CachePinRequest(BaseModel):
    asset_name: str
    pinned: bool


class CacheEvictRequest(BaseModel):
    model_name: str


class CachePullRequest(BaseModel):
    model_name: str


class CredentialSaveRequest(BaseModel):
    key_name: str
    secret_value: str


class ActionOpenPathRequest(BaseModel):
    path: str


# ---------------- Telemetry & Core Endpoints ----------------

@app.get("/api/telemetry")
def get_telemetry():
    """Non-blocking hardware metrics: CPU, RAM, GPU RTX 3050, Disks, and Processes."""
    return SystemMonitor.get_full_telemetry()


@app.get("/api/drive/status")
def get_drive_status():
    """Google Drive running status, mount point, and folders."""
    return CloudDriveManager.get_status()


@app.post("/api/drive/init-folders")
def init_drive_folders():
    """Initializes the 9 cloud directories in Google Drive."""
    success, message, created = CloudDriveManager.initialize_folder_structure()
    return {"success": success, "message": message, "created_folders": created}


# ---------------- Cloud Storage Analytics (Requirement 4) ----------------

@app.get("/api/cloud/analytics")
def get_cloud_analytics(refresh: bool = False):
    """
    Returns actual Google Drive quota and storage consumption across
    Projects, Datasets, AI_Models, Backups, Archives, and local cache.
    """
    # Both scans are cached (10 / 5 min); the dashboard's "refresh" button forces a rescan.
    cloud_analytics = CloudDriveManager.get_cloud_storage_analytics(refresh=refresh)
    workspace_metrics = WorkspaceManager.get_directory_metrics(refresh=refresh)
    return {
        "cloud": cloud_analytics,
        "local_cache": workspace_metrics
    }


# ---------------- Project Lifecycle Management (Requirement 3) ----------------

@app.get("/api/projects/mappings")
def list_project_mappings():
    """Lists registered projects mapped between D:\\CloudDesk\\Workspace and Google Drive."""
    return WorkspaceManager.load_mappings()


@app.post("/api/projects/create")
def create_project(req: CreateProjectRequest):
    """Provisions a new project in local D:\\ workspace and Google Drive central folder."""
    try:
        return ProjectLifecycleManager.create_project(
            project_name=req.project_name,
            template=req.template,
            init_git=req.init_git,
            create_gh_repo=req.create_gh_repo
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projects/diff/{project_name}")
def get_project_diff(project_name: str):
    """Scans changed files and eligible assets ready for sync (excluding .env)."""
    try:
        return ProjectLifecycleManager.scan_project_diff(project_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/projects/sync/{project_name}")
def sync_project_assets(project_name: str):
    """Synchronizes eligible assets to Google Drive with SHA256 integrity verification."""
    try:
        return ProjectLifecycleManager.sync_project_assets(project_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/complete")
def complete_project(req: CompleteProjectRequest):
    """Archives project cleanly to Google Drive and offers to evict local build artifacts."""
    try:
        return ProjectLifecycleManager.complete_and_archive_project(
            project_name=req.project_name,
            evict_local_build_artifacts=req.evict_local_build_artifacts
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/restore")
def restore_project(req: RestoreProjectRequest):
    """Restores a project from a Google Drive archive into D:\\CloudDesk\\Workspace."""
    try:
        return ProjectLifecycleManager.restore_project_from_archive(
            archive_path_str=req.archive_path,
            restore_name=req.restore_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- Intelligent Cache Management (Requirement 5) ----------------

@app.get("/api/cache/status")
def get_cache_status():
    """Monitors cache limits, pressure, and cached model inventory."""
    return CacheManager.get_cache_status()


@app.post("/api/cache/pin")
def pin_cache_asset(req: CachePinRequest):
    """Protects or unprotects an asset from cache eviction."""
    if req.pinned:
        CacheManager.pin_asset(req.asset_name)
    else:
        CacheManager.unpin_asset(req.asset_name)
    return {"success": True, "asset_name": req.asset_name, "pinned": req.pinned}


@app.post("/api/cache/evict")
def evict_cached_model(req: CacheEvictRequest):
    """Safely evicts model (uploads to Google Drive first if not already present)."""
    try:
        return CacheManager.evict_model_safely(req.model_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/cache/pull")
def pull_cached_model(req: CachePullRequest):
    """Pulls cold model from Google Drive AI_Models into local D:\\CloudDesk\\ModelCache."""
    try:
        return CacheManager.pull_model_from_cloud(req.model_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- AI Datasets and Models (Requirement 6) ----------------

@app.get("/api/cloud/datasets")
def list_datasets():
    """Lists cloud datasets and local cached slices."""
    return AIAssetManager.list_datasets()


@app.get("/api/cloud/models")
def list_models():
    """Lists Google Drive models and local ModelCache inventory."""
    return AIAssetManager.list_models()


# ---------------- Storage Optimizer & Backups ----------------

@app.get("/api/storage/scan")
def scan_storage():
    """Analyzes reclaimable bloat (Ollama models, temp files, caches)."""
    return StorageOptimizer.scan_storage_overview()


@app.post("/api/storage/clean-temp")
def clean_temp_files():
    """Cleans temporary files older than 24 hours safely."""
    return StorageOptimizer.clean_safe_temp_files()


@app.post("/api/backup/run")
def run_backup(req: BackupRequest):
    """Executes a clean project backup strictly omitting .env and dependencies."""
    try:
        return BackupEngine.create_project_backup(req.project_path, req.destination)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backup/list")
def list_backups():
    """Lists existing backups."""
    return BackupEngine.list_backups()


# ---------------- Action Endpoints ----------------

@app.post("/api/actions/open-drive")
def action_open_drive():
    """Opens Google Drive in Windows File Explorer."""
    mount = CloudDriveManager.get_drive_mount()
    target = str(mount) if mount else "G:\\"
    subprocess.Popen(["explorer.exe", target])
    return {"success": True, "target": target}


@app.post("/api/actions/open-workspace")
def action_open_workspace():
    """Opens D:\\CloudDesk\\Workspace in Windows File Explorer."""
    subprocess.Popen(["explorer.exe", str(LOCAL_DIRS["workspace"])])
    return {"success": True, "target": str(LOCAL_DIRS["workspace"])}


_SHELL_META = re.compile(r'[&|<>^%"\r\n]')


def _existing_path(raw: str) -> Path:
    p = Path(raw).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    return p


@app.post("/api/actions/open-vscode")
def action_open_vscode(req: ActionOpenPathRequest):
    """Opens a specified project folder in VS Code."""
    p = _existing_path(req.path)
    # `code` is a .cmd script, so cmd.exe parses the arguments: refuse shell metacharacters
    # instead of the old shell=True, which turned a crafted folder name into a command.
    if _SHELL_META.search(str(p)):
        raise HTTPException(status_code=400, detail="Path contains characters that are unsafe to pass to VS Code")
    code = shutil.which("code")
    if not code:
        raise HTTPException(status_code=404, detail="VS Code ('code') is not on PATH")
    subprocess.Popen([code, str(p)])
    return {"success": True, "opened": str(p)}


@app.post("/api/actions/open-explorer")
def action_open_explorer(req: ActionOpenPathRequest):
    """Opens a folder in Windows File Explorer."""
    p = _existing_path(req.path)
    subprocess.Popen(["explorer.exe", str(p)])
    return {"success": True, "opened": str(p)}


@app.post("/api/actions/open-url")
def action_open_url(req: ActionOpenPathRequest):
    """Opens a web URL in the default browser (http/https only)."""
    # On Windows webbrowser.open() falls back to os.startfile(), which would happily
    # run C:\\...\\anything.exe - only real web links are allowed.
    u = urlparse(req.path)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise HTTPException(status_code=400, detail="Only http(s) URLs can be opened")
    webbrowser.open(req.path)
    return {"success": True, "url": req.path}


@app.post("/api/actions/install-drive")
def action_install_drive():
    """Launches the downloaded Google Drive installer (triggers UAC elevation)."""
    installer_path = BASE_DIR.parent / "GoogleDriveSetup.exe"
    if not installer_path.exists():
        raise HTTPException(status_code=404, detail="GoogleDriveSetup.exe not found")
    subprocess.Popen([str(installer_path)])
    return {"success": True, "message": "Google Drive installer started. Please approve the Windows UAC elevation prompt on your screen."}


# ---------------- Credentials Endpoints ----------------

@app.get("/api/credentials/list")
def list_credentials():
    """Returns stored API key names and masked previews."""
    return CredentialsVault.list_keys()


@app.post("/api/credentials/save")
def save_credential(req: CredentialSaveRequest):
    """Saves API key securely in Windows Credential Manager."""
    success = CredentialsVault.store_secret(req.key_name, req.secret_value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed writing to Windows Credential Manager")
    return {"success": True, "key_name": req.key_name}


@app.delete("/api/credentials/{key_name}")
def delete_credential(key_name: str):
    """Deletes API key from Windows Credential Manager."""
    success = CredentialsVault.delete_secret(key_name)
    return {"success": success}


# ---------------- Automation Endpoints ----------------

@app.post("/api/automation/sync-now")
def trigger_auto_sync():
    """Triggers autonomous synchronization of all registered project assets to Google Drive."""
    return AutomationEngine.run_auto_sync()


@app.get("/api/automation/guardrail")
def check_guardrails():
    """Checks RAM and disk capacity thresholds, returning health alerts."""
    return AutomationEngine.run_system_guardrail_check()


@app.get("/api/automation/report")
def generate_storage_report():
    """Generates complete storage audit and analytics report."""
    return AutomationEngine.generate_storage_report()


@app.post("/api/storage/purge-c-ollama")
def purge_c_ollama(confirmed: bool = False):
    """
    Purges original C:\\Users\\joshi\\.ollama\\models (7.58 GB)
    ONLY AFTER user confirmation and verified parity on D:\\ollama_models.
    """
    if not confirmed:
        raise HTTPException(status_code=400, detail="Confirmation required to delete C:\\.ollama\\models")

    c_models = Path.home() / ".ollama" / "models"
    d_models = Path("D:/ollama_models")

    if not d_models.exists():
        raise HTTPException(status_code=400, detail="D:\\ollama_models not found. Migration not verified.")

    c_size = sum(f.stat().st_size for f in c_models.rglob("*") if f.is_file()) if c_models.exists() else 0
    d_size = sum(f.stat().st_size for f in d_models.rglob("*") if f.is_file()) if d_models.exists() else 0

    if c_size != d_size or c_size == 0:
        raise HTTPException(status_code=400, detail=f"Parity mismatch (C: {c_size} vs D: {d_size}). Aborting for safety.")

    import shutil
    shutil.rmtree(c_models, ignore_errors=True)
    return {
        "success": True,
        "reclaimed_gb": round(c_size / (1024 ** 3), 2),
        "message": f"Successfully purged original C:\\.ollama\\models. Reclaimed {round(c_size / (1024 ** 3), 2)} GB on C: drive!"
    }


# ---------------- Endpoints the dashboard already calls ----------------

@ttl_cache(300)
def _projects_overview() -> Dict[str, Any]:
    return {
        "local_projects": CloudDevManager.discover_local_projects(),
        "github_repositories": CloudDevManager.get_user_repositories(),
    }


@app.get("/api/projects")
def list_projects(refresh: bool = False):
    """Local projects + GitHub repositories (Active Workspaces tab). Cached 5 min."""
    return _projects_overview(refresh=refresh)


@app.post("/api/colab/generate")
def generate_colab_notebook():
    """Writes the Colab GPU accelerator notebook into Google Drive (or the project's templates/)."""
    my_drive = CloudDriveManager.get_my_drive_path()
    target_dir = (my_drive / "Colab Notebooks") if my_drive else (BASE_DIR / "templates")
    target_dir.mkdir(parents=True, exist_ok=True)
    out = CloudDevManager.generate_colab_template(target_dir / "Aayushifty_CloudDesk_ML_Accelerator.ipynb")
    return {"success": True, "path": str(out)}


# ---------------- CloudDesk Guard (clouddesk-toolkit watchdog) ----------------

GUARD_STATUS_FILE = Path(os.environ.get("CLOUDDESK_GUARD_STATUS", "D:/CloudDesk/guard_status.json"))


@app.get("/api/guard")
def guard_status():
    """Latest status written by CloudDesk Guard (RAM/disk watchdog from clouddesk-toolkit)."""
    if not GUARD_STATUS_FILE.exists():
        return {"running": False, "detail": "CloudDesk Guard is not installed or hasn't run yet."}
    try:
        data = json.loads(GUARD_STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"running": False, "detail": f"Unreadable guard status: {e}"}
    age = max(0.0, time.time() - GUARD_STATUS_FILE.stat().st_mtime)
    data["running"] = age < 300  # guard writes every 60 s
    data["age_seconds"] = round(age)
    return data


# ---------------- Cloud Workspace: Google Drive is the home, D: is a cache ----------------

class WorkspaceRequest(BaseModel):
    name: str
    install_deps: bool = True


class AutoParkRequest(BaseModel):
    idle_days: Optional[float] = None


def _ws_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/workspace/projects")
def workspace_projects():
    """Every project: parked in Google Drive, or open on the laptop."""
    return _ws_call(CloudWorkspace.list_projects)


@app.post("/api/workspace/open")
def workspace_open(req: WorkspaceRequest):
    """One click: bring a project from Drive onto D:, restore secrets, install deps in background."""
    return _ws_call(CloudWorkspace.open, req.name, install_deps=req.install_deps)


@app.post("/api/workspace/park")
def workspace_park(req: WorkspaceRequest):
    """One click: upload + SHA-256 verify to Drive, then free the laptop copy completely."""
    return _ws_call(CloudWorkspace.park, req.name)


@app.post("/api/workspace/deps")
def workspace_deps(req: WorkspaceRequest):
    """(Re)install a working copy's dependencies in the background."""
    return _ws_call(CloudWorkspace.install_dependencies, req.name)


@app.post("/api/workspace/autopark")
def workspace_autopark(req: AutoParkRequest):
    days = req.idle_days if req.idle_days is not None else WorkspaceManager.load_config().get("auto_park_days", 7)
    return _ws_call(CloudWorkspace.auto_park, float(days))


@app.post("/api/workspace/run-in-cloud")
def workspace_run_in_cloud(req: WorkspaceRequest):
    """Open the project in GitHub Codespaces (cloud CPU/RAM) - needs a GitHub remote."""
    repo = CloudWorkspace.github_repo(req.name)
    if not repo:
        raise HTTPException(status_code=400, detail="This project has no GitHub remote yet - push it to GitHub first.")
    url = f"https://codespaces.new/{repo}"
    webbrowser.open(url)
    return {"success": True, "url": url}


# ---------------- AI Gateway: OpenAI-compatible, runs on Gemini (cloud) ----------------

@app.get("/api/ai/status")
def ai_status(refresh: bool = False):
    return ai_gateway.status(refresh=refresh)


@app.get("/v1/models")
def ai_models():
    return ai_gateway.list_models()


@app.post("/v1/chat/completions")
async def ai_chat_completions(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Body must be JSON")
    try:
        backend, resp = await anyio.to_thread.run_sync(ai_gateway.chat, body)
    except ai_gateway.GatewayError as e:
        return Response(e.body, status_code=e.status, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No AI backend reachable: {e}")
    headers = {"X-CloudDesk-Backend": backend}
    media = resp.headers.get("Content-Type", "application/json")
    if body.get("stream"):
        return StreamingResponse(ai_gateway.stream_body(resp), media_type=media, headers=headers)
    with resp:
        data = resp.read()
    return Response(data, media_type=media, headers=headers)


# ---------------- Static & Dashboard Serving ----------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = BASE_DIR / "dashboard" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "Aayushifty CloudDesk 2.0 Operational"})
