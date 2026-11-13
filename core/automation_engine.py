"""
Automation Engine Module - Aayushifty CloudDesk 2.0
Handles autonomous background synchronization, disk/RAM capacity guardrails,
and automated storage digests.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import psutil

from core.workspace_manager import WorkspaceManager, LOCAL_DIRS
from core.cloud_drive import CloudDriveManager
from core.project_lifecycle import ProjectLifecycleManager
from core.storage_optimizer import StorageOptimizer

AUTOMATION_LOG_FILE = Path("D:/CloudDesk/automation_history.json")


class AutomationEngine:
    """Orchestrates autonomous asset sync, capacity guardrails, and reporting."""

    @classmethod
    def log_event(cls, event_type: str, details: Dict[str, Any]) -> None:
        """Appends an event to the local automation history log."""
        events = []
        if AUTOMATION_LOG_FILE.exists():
            try:
                events = json.loads(AUTOMATION_LOG_FILE.read_text(encoding="utf-8"))
            except Exception:
                events = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        events.append(entry)
        # Keep last 100 events
        events = events[-100:]
        AUTOMATION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOMATION_LOG_FILE.write_text(json.dumps(events, indent=2), encoding="utf-8")

    @classmethod
    def run_auto_sync(cls) -> Dict[str, Any]:
        """
        Iterates over all registered projects and synchronizes eligible assets to Google Drive.
        Guarantees zero-leakage: .env and private credentials are NEVER synced.
        """
        mappings = WorkspaceManager.load_mappings()
        sync_results = {}
        total_synced_files = 0

        for name, meta in mappings.items():
            if meta.get("status") == "active":
                try:
                    res = ProjectLifecycleManager.sync_project_assets(name)
                    sync_results[name] = res
                    total_synced_files += res.get("synced_count", 0)
                except Exception as e:
                    sync_results[name] = {"success": False, "error": str(e)}

        cls.log_event("auto_sync", {
            "projects_count": len(mappings),
            "total_synced_files": total_synced_files,
            "results": sync_results
        })

        return {
            "success": True,
            "synced_projects": len(sync_results),
            "total_synced_files": total_synced_files,
            "details": sync_results
        }

    @classmethod
    def run_system_guardrail_check(cls) -> Dict[str, Any]:
        """
        Inspects RAM and disk capacity thresholds, issuing actionable warnings.
        """
        warnings = []

        # Check C: disk space
        c_usage = psutil.disk_usage("C:")
        c_free_gb = round(c_usage.free / (1024 ** 3), 2)
        if c_free_gb < 15.0:
            warnings.append(f"C: System drive is low on space ({c_free_gb} GB free). Purge C:\\.ollama\\models to gain 7.58 GB.")

        # Check RAM pressure
        mem = psutil.virtual_memory()
        if mem.percent > 85.0:
            warnings.append(f"RAM pressure elevated ({mem.percent}% used). Consider closing idle apps or offloading heavy tasks to Google Colab.")

        # Check Google Drive status
        g_drive_online = CloudDriveManager.is_drive_running() and CloudDriveManager.get_drive_mount() is not None
        if not g_drive_online:
            warnings.append("Google Drive virtual mount is currently disconnected.")

        status = {
            "healthy": len(warnings) == 0,
            "warnings": warnings,
            "c_free_gb": c_free_gb,
            "ram_percent": mem.percent,
            "google_drive_online": g_drive_online,
            "timestamp": datetime.now().isoformat()
        }

        cls.log_event("guardrail_check", status)
        return status

    @classmethod
    def generate_storage_report(cls) -> Dict[str, Any]:
        """Generates a comprehensive storage audit report."""
        workspace_metrics = WorkspaceManager.get_directory_metrics()
        cloud_analytics = CloudDriveManager.get_cloud_storage_analytics()
        optimizer_scan = StorageOptimizer.scan_storage_overview()

        report = {
            "generated_at": datetime.now().isoformat(),
            "local_workspace_metrics": workspace_metrics,
            "cloud_storage_analytics": cloud_analytics,
            "reclaimable_storage": optimizer_scan
        }

        cls.log_event("storage_report", {"summary": "Generated storage audit report"})
        return report

