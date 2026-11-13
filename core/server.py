"""
FastAPI Server Backend - Aayushifty CloudDesk 2.0
Cloud-First Architecture Engine.
Integrates Google Drive primary storage layer, Intelligent Local Workspace (D:\\ & E:\\),
differential asset synchronization, safe cache eviction, and project lifecycle management.
"""
from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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
def get_cloud_analytics():
    """
    Returns actual Google Drive quota and storage consumption across
    Projects, Datasets, AI_Models, Backups, Archives, and local cache.
    """
    cloud_analytics = CloudDriveManager.get_cloud_storage_analytics()
    workspace_metrics = WorkspaceManager.get_directory_metrics()
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


@app.post("/api/actions/open-vscode")
def action_open_vscode(req: ActionOpenPathRequest):
    """Opens a specified project folder in VS Code."""
    if not Path(req.path).exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    subprocess.Popen(["code", req.path], shell=True)
    return {"success": True, "opened": req.path}


@app.post("/api/actions/open-explorer")
def action_open_explorer(req: ActionOpenPathRequest):
    """Opens a folder in Windows File Explorer."""
    p = Path(req.path).resolve()
    subprocess.Popen(["explorer.exe", str(p)])
    return {"success": True, "opened": str(p)}


@app.post("/api/actions/open-url")
def action_open_url(req: ActionOpenPathRequest):
    """Opens a URL in the default browser."""
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


# ---------------- Static & Dashboard Serving ----------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = BASE_DIR / "dashboard" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "Aayushifty CloudDesk 2.0 Operational"})
