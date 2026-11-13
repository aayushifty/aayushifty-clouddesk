"""
Intelligent Cache Manager Module - Aayushifty CloudDesk 2.0
Enforces local SSD cache limits across D:\\CloudDesk\\ModelCache, Dependencies, and Temporary.
Guarantees: NEVER delete the only copy of a file (syncs to Google Drive before eviction).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.workspace_manager import WorkspaceManager, LOCAL_DIRS
from core.cloud_drive import CloudDriveManager

PINNED_CONFIG_FILE = Path("D:/CloudDesk/pinned_assets.json")


class CacheManager:
    """Monitors cache thresholds, protects active dependencies, and safely evicts cold assets."""

    @classmethod
    def load_pinned_assets(cls) -> Set[str]:
        """Returns set of paths or names that are immune to automatic cache eviction."""
        if not PINNED_CONFIG_FILE.exists():
            return set()
        try:
            return set(json.loads(PINNED_CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()

    @classmethod
    def pin_asset(cls, asset_name: str) -> None:
        """Protects an asset from eviction."""
        pinned = cls.load_pinned_assets()
        pinned.add(asset_name)
        PINNED_CONFIG_FILE.write_text(json.dumps(list(pinned), indent=2), encoding="utf-8")

    @classmethod
    def unpin_asset(cls, asset_name: str) -> None:
        """Removes eviction immunity from an asset."""
        pinned = cls.load_pinned_assets()
        pinned.discard(asset_name)
        PINNED_CONFIG_FILE.write_text(json.dumps(list(pinned), indent=2), encoding="utf-8")

    @classmethod
    def get_cache_status(cls) -> Dict[str, Any]:
        """Provides full breakdown of cache usage against configured capacity limits."""
        config = WorkspaceManager.load_config()
        limits = config.get("cache_limits_gb", {"model_cache": 25.0, "dependencies": 20.0, "temporary": 15.0})
        metrics = WorkspaceManager.get_directory_metrics()
        pinned = cls.load_pinned_assets()

        status = {}
        for cache_key in ["model_cache", "dependencies", "temporary"]:
            used_gb = metrics.get(cache_key, {}).get("size_gb", 0.0)
            limit_gb = limits.get(cache_key, 20.0)
            percent = round((used_gb / limit_gb) * 100, 1) if limit_gb > 0 else 0.0
            status[cache_key] = {
                "used_gb": used_gb,
                "limit_gb": limit_gb,
                "percent": percent,
                "pressure": "HIGH" if percent >= 85 else "OPTIMAL",
                "path": str(LOCAL_DIRS[cache_key])
            }

        # Scan active cached AI models
        model_files = []
        model_cache_dir = LOCAL_DIRS["model_cache"]
        if model_cache_dir.exists():
            for f in model_cache_dir.glob("*"):
                if f.is_file():
                    size_mb = round(f.stat().st_size / (1024 ** 2), 2)
                    is_pinned = f.name in pinned
                    # Check if backed up in Google Drive
                    my_drive = CloudDriveManager.get_my_drive_path()
                    in_cloud = (my_drive / "AI_Models" / f.name).exists() if my_drive else False

                    model_files.append({
                        "name": f.name,
                        "size_mb": size_mb,
                        "pinned": is_pinned,
                        "stored_in_cloud": in_cloud,
                        "last_accessed": datetime.fromtimestamp(f.stat().st_atime).isoformat() if hasattr(f.stat(), "st_atime") else None
                    })

        return {
            "caches": status,
            "cached_models": model_files,
            "pinned_count": len(pinned)
        }

    @classmethod
    def evict_model_safely(cls, model_name: str) -> Dict[str, Any]:
        """
        Evicts a model from local D:\\CloudDesk\\ModelCache.
        SAFETY RULE: If the model is not already stored in Google Drive (G:\\AI_Models),
        it uploads it to Google Drive FIRST before removing the local copy!
        """
        model_path = LOCAL_DIRS["model_cache"] / model_name
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found in cache: {model_name}")

        pinned = cls.load_pinned_assets()
        if model_name in pinned:
            raise PermissionError(f"Model '{model_name}' is pinned and protected from eviction. Unpin first.")

        my_drive = CloudDriveManager.get_my_drive_path()
        cloud_dest = (my_drive / "AI_Models" / model_name) if my_drive else None

        # Verify cloud copy exists
        cloud_copy_verified = False
        if cloud_dest and cloud_dest.exists():
            if cloud_dest.stat().st_size == model_path.stat().st_size:
                cloud_copy_verified = True

        # If cloud copy doesn't exist, upload it first!
        uploaded_first = False
        if not cloud_copy_verified and cloud_dest:
            cloud_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(model_path, cloud_dest)
            if cloud_dest.stat().st_size == model_path.stat().st_size:
                cloud_copy_verified = True
                uploaded_first = True

        if not cloud_copy_verified:
            raise IOError("Cannot evict model: Google Drive is offline and no cloud backup exists. Data loss prevented.")

        size_reclaimed = model_path.stat().st_size
        model_path.unlink()

        return {
            "success": True,
            "model_name": model_name,
            "uploaded_to_cloud_first": uploaded_first,
            "reclaimed_mb": round(size_reclaimed / (1024 ** 2), 2),
            "cloud_location": str(cloud_dest)
        }

    @classmethod
    def pull_model_from_cloud(cls, model_name: str) -> Dict[str, Any]:
        """Fetches a cold model from Google Drive AI_Models into D:\\CloudDesk\\ModelCache."""
        my_drive = CloudDriveManager.get_my_drive_path()
        if not my_drive or not my_drive.exists():
            raise FileNotFoundError("Google Drive is not mounted.")

        cloud_src = my_drive / "AI_Models" / model_name
        if not cloud_src.exists():
            raise FileNotFoundError(f"Model not found in Google Drive: {cloud_src}")

        dest = LOCAL_DIRS["model_cache"] / model_name
        dest.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(cloud_src, dest)
        return {
            "success": True,
            "model_name": model_name,
            "local_path": str(dest),
            "size_mb": round(dest.stat().st_size / (1024 ** 2), 2)
        }

