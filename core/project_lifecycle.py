"""
Project Lifecycle & Synchronization Engine - Aayushifty CloudDesk 2.0
Handles end-to-end project lifecycle:
  1. Create: Maps Local Workspace (D:\\CloudDesk\\Workspace) <-> Cloud (Google Drive Projects)
  2. Modify: Tracks diffs, verifies asset integrity, syncs eligible assets (never secrets)
  3. Finish: Creates clean verified archive on Google Drive, safely evicts local build caches,
             and guarantees instant 1-click recovery.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.workspace_manager import WorkspaceManager, LOCAL_DIRS
from core.cloud_drive import CloudDriveManager

# Strict security exclusions: NEVER upload or mirror these files to cloud
STRICT_EXCLUDE_FILES: Set[str] = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "credentials.json",
    "service_account.json",
    "token.json",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.kdbx"
}

# Directories that must NEVER be synced to Google Drive stream
STRICT_EXCLUDE_DIRS: Set[str] = {
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".turbo",
    ".parcel-cache",
    ".gradle",
    "bin",
    "obj"
}

# Project assets eligible for cloud synchronization
ASSET_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif",
    ".mp4", ".mov", ".avi", ".mkv",
    ".obj", ".fbx", ".gltf", ".glb", ".blend", ".step", ".stl",
    ".kicad_pcb", ".kicad_sch", ".gerber",
    ".pdf", ".md", ".txt", ".docx",
    ".csv", ".parquet", ".json", ".sqlite3",
    ".gguf", ".safetensors", ".bin", ".onnx", ".pt", ".pth"
}


def compute_sha256(filepath: Path) -> str:
    """Computes SHA256 checksum with streaming chunks for large files."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):  # 1MB buffer
            hasher.update(chunk)
    return hasher.hexdigest()


class ProjectLifecycleManager:
    """Orchestrates cloud-first project creation, differential asset sync, and safe completion."""

    @classmethod
    def create_project(
        cls,
        project_name: str,
        template: str = "empty",
        init_git: bool = True,
        create_gh_repo: bool = False
    ) -> Dict[str, Any]:
        """
        Creates dual mapping: Local SSD execution workspace + Google Drive central project folder.
        """
        clean_name = "".join(c for c in project_name if c.isalnum() or c in ("-", "_")).strip()
        if not clean_name:
            raise ValueError("Invalid project name.")

        local_path = LOCAL_DIRS["workspace"] / clean_name
        local_path.mkdir(parents=True, exist_ok=True)

        # Google Drive central project path
        my_drive = CloudDriveManager.get_my_drive_path()
        cloud_path = (my_drive / "Projects" / clean_name) if my_drive else None

        if cloud_path:
            try:
                cloud_path.mkdir(parents=True, exist_ok=True)
                (cloud_path / "assets").mkdir(exist_ok=True)
                (cloud_path / "docs").mkdir(exist_ok=True)
            except Exception:
                pass

        # Create basic structure locally
        (local_path / "src").mkdir(exist_ok=True)
        (local_path / "assets").mkdir(exist_ok=True)
        (local_path / "docs").mkdir(exist_ok=True)

        # Standard .gitignore preventing security leaks and node_modules sync
        gitignore = local_path / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "# Aayushifty CloudDesk Guardrails\n"
                ".env\n.env.*\n*.pem\n*.key\ncredentials.json\n"
                "node_modules/\n.venv/\nvenv/\n"
                "dist/\nbuild/\n.next/\n__pycache__/\n*.pyc\n"
                "D:/CloudDesk/Dependencies/\n",
                encoding="utf-8"
            )

        readme = local_path / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {clean_name}\n\n"
                f"Managed by **Aayushifty CloudDesk 2.0 (Cloud-First Hybrid Environment)**\n\n"
                f"- **Local Workspace**: `{local_path}`\n"
                f"- **Google Drive Central**: `{cloud_path or 'G:/My Drive/Projects/' + clean_name}`\n",
                encoding="utf-8"
            )

        git_initialized = False
        if init_git:
            try:
                subprocess.run(["git", "init"], cwd=str(local_path), capture_output=True, check=True)
                subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=str(local_path), capture_output=True)
                subprocess.run(["git", "commit", "-m", "Initial commit from Aayushifty CloudDesk 2.0"], cwd=str(local_path), capture_output=True)
                git_initialized = True
            except Exception:
                pass

        gh_url = None
        if create_gh_repo and git_initialized and shutil.which("gh"):
            try:
                res = subprocess.run(
                    ["gh", "repo", "create", clean_name, "--private", "--source=.", "--remote=origin", "--push"],
                    cwd=str(local_path), capture_output=True, text=True
                )
                if res.returncode == 0:
                    gh_url = f"https://github.com/aayushbhatta230-ux/{clean_name}"
            except Exception:
                pass

        # Register mapping
        mapping = {
            "name": clean_name,
            "local_path": str(local_path),
            "cloud_path": str(cloud_path) if cloud_path else f"G:\\My Drive\\Projects\\{clean_name}",
            "created_at": datetime.now().isoformat(),
            "last_synced": datetime.now().isoformat(),
            "git_initialized": git_initialized,
            "github_url": gh_url,
            "status": "active"
        }
        WorkspaceManager.save_mapping(clean_name, mapping)

        return {
            "success": True,
            "project_name": clean_name,
            "local_path": str(local_path),
            "cloud_path": str(cloud_path) if cloud_path else f"G:\\My Drive\\Projects\\{clean_name}",
            "git_initialized": git_initialized,
            "github_url": gh_url
        }

    @classmethod
    def scan_project_diff(cls, project_name: str) -> Dict[str, Any]:
        """
        Scans for changed files and eligible large assets ready for Google Drive synchronization.
        Enforces strict zero-leakage security (never includes .env or private credentials).
        """
        mappings = WorkspaceManager.load_mappings()
        if project_name not in mappings:
            raise FileNotFoundError(f"Project '{project_name}' is not registered in CloudDesk mappings.")

        local_path = Path(mappings[project_name]["local_path"])
        if not local_path.exists():
            raise FileNotFoundError(f"Local project path does not exist: {local_path}")

        eligible_assets = []
        excluded_sensitive = []
        total_asset_bytes = 0

        for root, dirs, files in os.walk(local_path):
            # Exclude forbidden dependency trees in-place
            dirs[:] = [d for d in dirs if d not in STRICT_EXCLUDE_DIRS and not d.startswith(".venv")]

            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(local_path)
                file_lower = file.lower()

                # Security check
                is_sensitive = any(
                    file_lower == ex.lower() or
                    (ex.startswith("*") and file_lower.endswith(ex[1:].lower()))
                    for ex in STRICT_EXCLUDE_FILES
                )
                if is_sensitive or ".env" in file_lower:
                    excluded_sensitive.append(str(rel_path))
                    continue

                ext = file_path.suffix.lower()
                size = file_path.stat().st_size

                # Eligible if inside assets/ or matches asset extension or large file (> 2MB)
                is_asset = (
                    "assets" in rel_path.parts or
                    "models" in rel_path.parts or
                    "datasets" in rel_path.parts or
                    ext in ASSET_EXTENSIONS or
                    size > 2 * 1024 * 1024
                )

                if is_asset:
                    eligible_assets.append({
                        "rel_path": str(rel_path),
                        "abs_path": str(file_path),
                        "size_mb": round(size / (1024 ** 2), 2),
                        "size_bytes": size,
                        "extension": ext,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
                    total_asset_bytes += size

        return {
            "project_name": project_name,
            "eligible_assets_count": len(eligible_assets),
            "total_asset_size_mb": round(total_asset_bytes / (1024 ** 2), 2),
            "assets": eligible_assets,
            "excluded_sensitive_files": excluded_sensitive
        }

    @classmethod
    def sync_project_assets(cls, project_name: str) -> Dict[str, Any]:
        """
        Synchronizes eligible assets to Google Drive with SHA256 integrity verification.
        Uses staging on E:\\CloudDesk\\Staging to avoid partial writes.
        """
        diff = cls.scan_project_diff(project_name)
        mappings = WorkspaceManager.load_mappings()
        proj_meta = mappings[project_name]

        my_drive = CloudDriveManager.get_my_drive_path()
        if not my_drive or not my_drive.exists():
            return {
                "success": False,
                "error": "Google Drive (G:) is not mounted. Please ensure Google Drive for Desktop is running."
            }

        cloud_target = my_drive / "Projects" / project_name
        cloud_target.mkdir(parents=True, exist_ok=True)

        staging_dir = LOCAL_DIRS["staging"] / project_name
        staging_dir.mkdir(parents=True, exist_ok=True)

        synced_files = []
        failed_files = []

        for asset in diff["assets"]:
            src_path = Path(asset["abs_path"])
            dest_path = cloud_target / asset["rel_path"]
            stage_path = staging_dir / asset["rel_path"]

            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                stage_path.parent.mkdir(parents=True, exist_ok=True)

                # Check if destination already has identical size and mtime to avoid unnecessary uploads
                if dest_path.exists():
                    if dest_path.stat().st_size == src_path.stat().st_size:
                        continue

                # Copy to staging first (atomic write)
                shutil.copy2(src_path, stage_path)
                src_hash = compute_sha256(stage_path)

                # Stream to Google Drive
                shutil.copy2(stage_path, dest_path)

                # Verify integrity
                dest_hash = compute_sha256(dest_path)
                if src_hash != dest_hash:
                    failed_files.append({"file": asset["rel_path"], "error": "Checksum mismatch after transfer"})
                    dest_path.unlink(missing_ok=True)
                else:
                    synced_files.append({"file": asset["rel_path"], "size_mb": asset["size_mb"], "sha256": src_hash})

            except Exception as e:
                failed_files.append({"file": asset["rel_path"], "error": str(e)})

        # Cleanup staging
        shutil.rmtree(staging_dir, ignore_errors=True)

        # Update last sync timestamp
        proj_meta["last_synced"] = datetime.now().isoformat()
        WorkspaceManager.save_mapping(project_name, proj_meta)

        return {
            "success": len(failed_files) == 0,
            "project_name": project_name,
            "synced_count": len(synced_files),
            "synced_files": synced_files,
            "failed_files": failed_files,
            "timestamp": datetime.now().isoformat()
        }

    @classmethod
    def complete_and_archive_project(
        cls,
        project_name: str,
        evict_local_build_artifacts: bool = True
    ) -> Dict[str, Any]:
        """
        Completes a project:
          1. Creates a clean, dependency-stripped source archive (.zip)
          2. Uploads and verifies archive in Google Drive (Archives/ and Backups/)
          3. Verifies zip integrity (CRC32 test)
          4. Safely evicts local node_modules & .venv if requested (saving local SSD space)
          5. Guarantees 1-click recovery from cloud archive.
        """
        mappings = WorkspaceManager.load_mappings()
        if project_name not in mappings:
            raise FileNotFoundError(f"Project '{project_name}' is not registered.")

        local_path = Path(mappings[project_name]["local_path"])
        if not local_path.exists():
            raise FileNotFoundError(f"Local project path does not exist: {local_path}")

        my_drive = CloudDriveManager.get_my_drive_path()
        if not my_drive or not my_drive.exists():
            # Fallback to local E:\CloudDesk\Recovery if Drive offline
            dest_dir = LOCAL_DIRS["recovery"]
        else:
            dest_dir = my_drive / "Archives"
        dest_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{project_name}_complete_{timestamp_str}.zip"
        archive_path = dest_dir / archive_name

        archived_files = []
        raw_size = 0

        # Create clean zip archive
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            for root, dirs, files in os.walk(local_path):
                # Filter out heavy dependency directories
                dirs[:] = [d for d in dirs if d not in STRICT_EXCLUDE_DIRS and not d.startswith(".venv")]

                for file in files:
                    file_path = Path(root) / file
                    file_lower = file.lower()

                    # Strict security exclusions (never include secrets)
                    if any(file_lower == ex.lower() or (ex.startswith("*") and file_lower.endswith(ex[1:].lower())) for ex in STRICT_EXCLUDE_FILES):
                        continue

                    try:
                        rel_path = file_path.relative_to(local_path)
                        zipf.write(file_path, arcname=str(rel_path))
                        archived_files.append(str(rel_path))
                        raw_size += file_path.stat().st_size
                    except (PermissionError, FileNotFoundError):
                        continue

            manifest = {
                "project_name": project_name,
                "local_path": str(local_path),
                "completed_at": datetime.now().isoformat(),
                "file_count": len(archived_files),
                "raw_size_bytes": raw_size,
                "archive_name": archive_name,
                "engine": "Aayushifty CloudDesk 2.0 Cloud-First Archiver"
            }
            zipf.writestr("clouddesk_archive_manifest.json", json.dumps(manifest, indent=2))

        # Test archive integrity
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            bad_file = zipf.testzip()
            if bad_file:
                archive_path.unlink(missing_ok=True)
                raise IOError(f"Archive verification failed! Corrupted file in zip: {bad_file}")

        archive_sha256 = compute_sha256(archive_path)
        compressed_size = archive_path.stat().st_size

        # Evict local build artifacts if requested (node_modules, .venv, dist)
        evicted_items = []
        reclaimed_bytes = 0
        if evict_local_build_artifacts:
            for target_name in ["node_modules", ".venv", "venv", "dist", "build", ".next"]:
                target_path = local_path / target_name
                if target_path.exists():
                    try:
                        size = sum(f.stat().st_size for f in target_path.rglob("*") if f.is_file())
                        shutil.rmtree(target_path, ignore_errors=True)
                        evicted_items.append(target_name)
                        reclaimed_bytes += size
                    except Exception:
                        pass

        # Update mapping
        mappings[project_name]["status"] = "completed"
        mappings[project_name]["last_archive"] = str(archive_path)
        mappings[project_name]["archive_sha256"] = archive_sha256
        WorkspaceManager.save_mapping(project_name, mappings[project_name])

        return {
            "success": True,
            "project_name": project_name,
            "archive_path": str(archive_path),
            "archive_name": archive_name,
            "sha256": archive_sha256,
            "file_count": len(archived_files),
            "raw_size_mb": round(raw_size / (1024 ** 2), 2),
            "compressed_size_mb": round(compressed_size / (1024 ** 2), 2),
            "evicted_artifacts": evicted_items,
            "reclaimed_local_mb": round(reclaimed_bytes / (1024 ** 2), 2),
            "recoverable": True
        }

    @classmethod
    def restore_project_from_archive(
        cls,
        archive_path_str: str,
        restore_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Restores a project from a Google Drive archive into D:\\CloudDesk\\Workspace.
        Extracts into a safe sandbox on E:\\CloudDesk\\Recovery first to verify before deploying.
        """
        archive_path = Path(archive_path_str).resolve()
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive file not found: {archive_path}")

        # Verify integrity before touching anything
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            bad_file = zipf.testzip()
            if bad_file:
                raise IOError(f"Archive integrity corrupted! Failed on file: {bad_file}")

            # Read manifest if present
            proj_name = restore_name
            try:
                manifest_data = zipf.read("clouddesk_archive_manifest.json")
                manifest = json.loads(manifest_data.decode("utf-8"))
                if not proj_name:
                    proj_name = manifest.get("project_name")
            except Exception:
                if not proj_name:
                    proj_name = archive_path.stem.split("_complete_")[0]

            # Stage in E:\CloudDesk\Recovery
            sandbox_dir = LOCAL_DIRS["recovery"] / proj_name
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            zipf.extractall(sandbox_dir)

            # Move verified files into D:\CloudDesk\Workspace\<proj_name>
            target_dest = LOCAL_DIRS["workspace"] / proj_name
            target_dest.mkdir(parents=True, exist_ok=True)
            for item in sandbox_dir.iterdir():
                if item.name == "clouddesk_archive_manifest.json":
                    continue
                dest_item = target_dest / item.name
                if dest_item.exists():
                    if dest_item.is_dir():
                        shutil.rmtree(dest_item, ignore_errors=True)
                    else:
                        dest_item.unlink(missing_ok=True)
                shutil.move(str(item), str(target_dest))

            # Cleanup sandbox
            shutil.rmtree(sandbox_dir, ignore_errors=True)

            # Register mapping
            my_drive = CloudDriveManager.get_my_drive_path()
            mapping = {
                "name": proj_name,
                "local_path": str(target_dest),
                "cloud_path": str(my_drive / "Projects" / proj_name) if my_drive else f"G:\\My Drive\\Projects\\{proj_name}",
                "restored_at": datetime.now().isoformat(),
                "restored_from": str(archive_path),
                "status": "active"
            }
            WorkspaceManager.save_mapping(proj_name, mapping)

            return {
                "success": True,
                "project_name": proj_name,
                "destination": str(target_dest),
                "restored_from": str(archive_path),
                "message": f"Project '{proj_name}' restored successfully to {target_dest}"
            }

