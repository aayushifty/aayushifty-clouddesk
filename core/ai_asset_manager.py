"""
AI Asset Manager Module - Aayushifty CloudDesk 2.0
Manages cloud-hosted AI datasets and models:
  - Google Drive (G:\\AI_Models, G:\\Datasets) is the primary central store
  - Download-on-demand & streaming into local execution caches
  - Colab direct cloud processing integration
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.workspace_manager import LOCAL_DIRS
from core.cloud_drive import CloudDriveManager


class AIAssetManager:
    """Manages cloud-first AI datasets and models lifecycle."""

    @classmethod
    def list_datasets(cls) -> Dict[str, Any]:
        """Lists cloud-hosted datasets in Google Drive and local cached datasets."""
        my_drive = CloudDriveManager.get_my_drive_path()
        cloud_datasets = []
        if my_drive and (my_drive / "Datasets").exists():
            for item in (my_drive / "Datasets").iterdir():
                try:
                    if item.is_file():
                        size_mb = round(item.stat().st_size / (1024 ** 2), 2)
                        cloud_datasets.append({"name": item.name, "size_mb": size_mb, "type": "file", "path": str(item)})
                    elif item.is_dir():
                        cloud_datasets.append({"name": item.name, "type": "directory", "path": str(item)})
                except Exception:
                    continue

        return {
            "cloud_datasets_count": len(cloud_datasets),
            "datasets": cloud_datasets,
            "cloud_mounted": my_drive is not None
        }

    @classmethod
    def list_models(cls) -> Dict[str, Any]:
        """Lists models stored in Google Drive and models currently cached locally."""
        my_drive = CloudDriveManager.get_my_drive_path()
        cloud_models = []
        if my_drive and (my_drive / "AI_Models").exists():
            for item in (my_drive / "AI_Models").iterdir():
                try:
                    if item.is_file():
                        size_mb = round(item.stat().st_size / (1024 ** 2), 2)
                        cloud_models.append({"name": item.name, "size_mb": size_mb, "path": str(item)})
                except Exception:
                    continue

        local_cached = []
        model_cache_dir = LOCAL_DIRS["model_cache"]
        if model_cache_dir.exists():
            for item in model_cache_dir.iterdir():
                if item.is_file():
                    local_cached.append({"name": item.name, "size_mb": round(item.stat().st_size / (1024 ** 2), 2)})

        return {
            "cloud_models": cloud_models,
            "local_cached_models": local_cached,
            "cloud_mounted": my_drive is not None
        }

    @classmethod
    def offload_model_to_cloud(cls, source_file: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Uploads a locally downloaded model to Google Drive AI_Models and verifies size."""
        src = Path(source_file).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source model not found: {src}")

        my_drive = CloudDriveManager.get_my_drive_path()
        if not my_drive or not my_drive.exists():
            raise IOError("Google Drive is not mounted. Cannot offload to cloud.")

        dest_name = model_name or src.name
        dest = my_drive / "AI_Models" / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src, dest)
        if dest.stat().st_size != src.stat().st_size:
            dest.unlink(missing_ok=True)
            raise IOError("Upload verification failed: size mismatch.")

        return {
            "success": True,
            "model_name": dest_name,
            "cloud_path": str(dest),
            "size_mb": round(dest.stat().st_size / (1024 ** 2), 2)
        }

