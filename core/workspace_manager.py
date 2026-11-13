"""
Workspace Manager Module - Aayushifty CloudDesk 2.0
Implements the Intelligent Local Workspace architecture:
  D:\\CloudDesk\\Workspace     (Active project code)
  D:\\CloudDesk\\Dependencies  (Package managers & virtual environments)
  D:\\CloudDesk\\ModelCache    (Active AI models cached from Google Drive)
  E:\\CloudDesk\\Temporary     (Build output & scratch storage)
  E:\\CloudDesk\\Staging       (Upload/download transfer staging)
  E:\\CloudDesk\\Recovery      (Restoration sandboxes & rollback points)
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.ttl_cache import ttl_cache

LOCAL_DIRS = {
    "workspace": Path("D:/CloudDesk/Workspace"),
    "dependencies": Path("D:/CloudDesk/Dependencies"),
    "model_cache": Path("D:/CloudDesk/ModelCache"),
    "temporary": Path("E:/CloudDesk/Temporary"),
    "staging": Path("E:/CloudDesk/Staging"),
    "recovery": Path("E:/CloudDesk/Recovery")
}

DIR_DESCRIPTIONS = {
    "workspace": "Active development projects. Code and assets run locally with high NVMe SSD speeds.",
    "dependencies": "Local node_modules, Python venvs, pip wheels, and package caches.",
    "model_cache": "AI model weights (GGUF, safetensors) actively running. Cold models stay in Google Drive.",
    "temporary": "Intermediate compiler outputs, build directories, and transient render frames.",
    "staging": "Buffer for incoming/outgoing transfers to Google Drive to ensure atomic syncs.",
    "recovery": "Restoration point sandboxes for verified recovery before overwriting local workspace."
}

MAPPINGS_FILE = Path("D:/CloudDesk/project_mappings.json")
CONFIG_FILE = Path("D:/CloudDesk/clouddesk_config.json")

DEFAULT_CONFIG = {
    "cache_limits_gb": {
        "model_cache": 25.0,
        "dependencies": 20.0,
        "temporary": 15.0
    },
    "auto_sync_assets": True,
    "max_upload_retries": 3,
    "strict_security_exclusions": True,
    "auto_park_days": 7,
    "ai_gateway": {
        "default_model": "gemini-3.5-flash-lite",
        "local_fallback": True,
        "local_model": "qwen3:4b-instruct"
    }
}


class WorkspaceManager:
    """Manages the two-tier local SSD workspace (D: & E:) and project mappings."""

    @classmethod
    def initialize_structure(cls) -> Dict[str, Any]:
        """Provisions all local workspace directories, configs, and documentation."""
        created = []
        for key, path in LOCAL_DIRS.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
                readme = path / "_CLOUDDESK_README.txt"
                if not readme.exists():
                    desc = DIR_DESCRIPTIONS.get(key, "")
                    readme.write_text(
                        f"=== Aayushifty CloudDesk 2.0: {path} ===\n\n"
                        f"Purpose: {desc}\n\n"
                        f"Architecture Policy:\n"
                        f"- High-speed execution layer on NVMe SSD.\n"
                        f"- Google Drive serves as central source of truth for assets & archives.\n"
                        f"- This local directory acts as a working cache and execution environment.\n",
                        encoding="utf-8"
                    )
                created.append(str(path))
            except Exception as e:
                return {"success": False, "error": f"Failed creating {path}: {str(e)}", "created": created}

        # Initialize project mappings file
        if not MAPPINGS_FILE.exists():
            MAPPINGS_FILE.write_text("{}", encoding="utf-8")

        # Initialize default configuration
        if not CONFIG_FILE.exists():
            CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")

        return {"success": True, "directories": created, "config": str(CONFIG_FILE)}

    @classmethod
    @ttl_cache(300)  # Dependencies/ holds npm/pip caches: hundreds of thousands of files
    def get_directory_metrics(cls) -> Dict[str, Any]:
        """Calculates size and file counts across all local CloudDesk directories."""
        results = {}
        for key, path in LOCAL_DIRS.items():
            if not path.exists():
                results[key] = {"path": str(path), "size_mb": 0.0, "size_gb": 0.0, "files_count": 0}
                continue

            total_bytes = 0
            file_count = 0
            try:
                for entry in path.rglob("*"):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total_bytes += entry.stat().st_size
                            file_count += 1
                    except (PermissionError, FileNotFoundError):
                        continue
            except Exception:
                pass

            results[key] = {
                "path": str(path),
                "size_mb": round(total_bytes / (1024 ** 2), 2),
                "size_gb": round(total_bytes / (1024 ** 3), 3),
                "files_count": file_count
            }

        return results

    @classmethod
    def load_mappings(cls) -> Dict[str, Any]:
        """Loads registered project mappings between local SSD and Google Drive."""
        if not MAPPINGS_FILE.exists():
            return {}
        try:
            return json.loads(MAPPINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def save_mapping(cls, project_name: str, mapping_data: Dict[str, Any]) -> None:
        """Saves or updates a project mapping."""
        mappings = cls.load_mappings()
        mappings[project_name] = mapping_data
        MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        MAPPINGS_FILE.write_text(json.dumps(mappings, indent=2), encoding="utf-8")

    @classmethod
    def remove_mapping(cls, project_name: str) -> bool:
        """Removes a project mapping from registry."""
        mappings = cls.load_mappings()
        if project_name in mappings:
            del mappings[project_name]
            MAPPINGS_FILE.write_text(json.dumps(mappings, indent=2), encoding="utf-8")
            return True
        return False

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """Loads configuration or defaults."""
        if not CONFIG_FILE.exists():
            return DEFAULT_CONFIG
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_CONFIG

    @classmethod
    def update_config(cls, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates and persists configuration."""
        cfg = cls.load_config()
        cfg.update(updates)
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg

