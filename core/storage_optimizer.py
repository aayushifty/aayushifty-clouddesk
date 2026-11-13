"""
Storage Optimizer Module - Aayushifty CloudDesk
Analyzes disk consumption, discovers bloat (caches, models, temp),
and generates safe reclamation recommendations without accidental deletion.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class StorageOptimizer:
    """Analyzes disk space, identifies reclaimable bloat, and prepares safe cleanup tasks."""

    SAFE_TEMP_DIRS = [
        Path(os.environ.get("LOCALAPPDATA", r"C:\Users\joshi\AppData\Local")) / "Temp",
    ]

    CACHE_DIRS = [
        ("NPM Cache", Path(os.environ.get("LOCALAPPDATA", r"C:\Users\joshi\AppData\Local")) / "npm-cache"),
        ("Pip Cache", Path(os.environ.get("LOCALAPPDATA", r"C:\Users\joshi\AppData\Local")) / "pip" / "cache"),
        ("User .cache", Path.home() / ".cache"),
    ]

    AI_MODEL_DIRS = [
        ("Ollama Models", Path.home() / ".ollama" / "models"),
        ("HuggingFace Cache", Path.home() / ".cache" / "huggingface"),
    ]

    @staticmethod
    def get_directory_size(path: Path) -> int:
        """Calculates total size of a directory in bytes safely."""
        if not path.exists():
            return 0
        total = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += StorageOptimizer.get_directory_size(Path(entry.path))
                except (PermissionError, FileNotFoundError):
                    continue
        except (PermissionError, FileNotFoundError):
            return 0
        return total

    @classmethod
    def scan_storage_overview(cls) -> Dict[str, Any]:
        """Provides a breakdown of reclaimable storage categories."""
        # 1. Temp files
        temp_bytes = sum(cls.get_directory_size(p) for p in cls.SAFE_TEMP_DIRS if p.exists())

        # 2. Package caches
        caches = []
        total_cache_bytes = 0
        for name, p in cls.CACHE_DIRS:
            size = cls.get_directory_size(p)
            if size > 0:
                caches.append({
                    "name": name,
                    "path": str(p),
                    "size_mb": round(size / (1024 ** 2), 2),
                    "size_gb": round(size / (1024 ** 3), 2)
                })
                total_cache_bytes += size

        # 3. AI Models
        models = []
        total_model_bytes = 0
        for name, p in cls.AI_MODEL_DIRS:
            size = cls.get_directory_size(p)
            if size > 0:
                models.append({
                    "name": name,
                    "path": str(p),
                    "size_mb": round(size / (1024 ** 2), 2),
                    "size_gb": round(size / (1024 ** 3), 2)
                })
                total_model_bytes += size

        # 4. Generate recommendations
        recommendations = []

        # Check Ollama models on C:
        ollama_path = Path.home() / ".ollama" / "models"
        if ollama_path.exists():
            ollama_size = cls.get_directory_size(ollama_path)
            if ollama_size > 1024 ** 3:  # > 1GB
                ollama_gb = round(ollama_size / (1024 ** 3), 2)
                recommendations.append({
                    "id": "relocate_ollama",
                    "priority": "HIGH",
                    "title": f"Migrate Ollama Models to D:\\ Drive (Save {ollama_gb} GB on C:)",
                    "description": (
                        f"Your local Ollama models occupy {ollama_gb} GB on the nearly-full C: drive. "
                        f"Your D: drive has ~157 GB free. Relocating OLLAMA_MODELS to D:\\ollama_models "
                        f"will immediately free {ollama_gb} GB on C: without losing any models."
                    ),
                    "reclaimable_gb": ollama_gb,
                    "safe": True
                })

        # Check Temp directory
        if temp_bytes > 500 * (1024 ** 2):  # > 500MB
            temp_gb = round(temp_bytes / (1024 ** 3), 2)
            recommendations.append({
                "id": "clean_temp",
                "priority": "MEDIUM",
                "title": f"Clean Safe Temporary Files (Save ~{temp_gb} GB)",
                "description": f"Purge temporary system/app files older than 24 hours from AppData/Local/Temp.",
                "reclaimable_gb": temp_gb,
                "safe": True
            })

        # Check Caches
        if total_cache_bytes > 500 * (1024 ** 2):
            cache_gb = round(total_cache_bytes / (1024 ** 3), 2)
            recommendations.append({
                "id": "clean_caches",
                "priority": "LOW",
                "title": f"Purge Package Manager Caches (Save ~{cache_gb} GB)",
                "description": "Clear npm-cache and pip caches. Dependencies will be re-downloaded when next required.",
                "reclaimable_gb": cache_gb,
                "safe": True
            })

        return {
            "temp_files": {
                "size_mb": round(temp_bytes / (1024 ** 2), 2),
                "size_gb": round(temp_bytes / (1024 ** 3), 2)
            },
            "caches": caches,
            "total_cache_gb": round(total_cache_bytes / (1024 ** 3), 2),
            "ai_models": models,
            "total_model_gb": round(total_model_bytes / (1024 ** 3), 2),
            "recommendations": recommendations
        }

    @classmethod
    def clean_safe_temp_files(cls) -> Dict[str, Any]:
        """
        Cleans safe temporary files older than 24 hours.
        NEVER throws on locked files (active applications).
        """
        deleted_count = 0
        reclaimed_bytes = 0
        cutoff = time.time() - (24 * 3600)  # 24 hours old

        for temp_dir in cls.SAFE_TEMP_DIRS:
            if not temp_dir.exists():
                continue
            for entry in os.scandir(temp_dir):
                try:
                    p = Path(entry.path)
                    stat = entry.stat(follow_symlinks=False)
                    if stat.st_mtime < cutoff:
                        if entry.is_file(follow_symlinks=False):
                            size = stat.st_size
                            p.unlink(missing_ok=True)
                            deleted_count += 1
                            reclaimed_bytes += size
                        elif entry.is_dir(follow_symlinks=False):
                            dir_size = cls.get_directory_size(p)
                            shutil.rmtree(p, ignore_errors=True)
                            deleted_count += 1
                            reclaimed_bytes += dir_size
                except (PermissionError, FileNotFoundError, OSError):
                    # File locked by Windows or in-use by running app
                    continue

        return {
            "success": True,
            "deleted_items": deleted_count,
            "reclaimed_mb": round(reclaimed_bytes / (1024 ** 2), 2),
            "reclaimed_gb": round(reclaimed_bytes / (1024 ** 3), 2)
        }

