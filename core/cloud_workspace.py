"""
Cloud Workspace - Google Drive as the permanent home of every project.

    G:\\My Drive\\Projects\\<name>   the ONE permanent copy (source code, assets, .git)
    D:\\CloudDesk\\Workspace\\<name> a temporary working copy, only while you work on it

open(name)  -> copy the project from Drive to D:, restore its secrets, install deps
park(name)  -> upload changes to Drive, verify every file byte for byte (SHA-256),
               then delete the laptop copy *including* node_modules/.venv/build output
auto_park() -> park projects nobody has touched for N days

Nothing regenerable (node_modules, .venv, dist, caches) is ever uploaded, and secrets
(.env, keys) never leave the laptop: on park they move to D:\\CloudDesk\\Vault and come
back on open. So a parked project costs 0 bytes of laptop disk except its tiny secrets.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from core.cloud_drive import CloudDriveManager
from core.project_lifecycle import STRICT_EXCLUDE_DIRS, STRICT_EXCLUDE_FILES
from core.workspace_manager import LOCAL_DIRS, WorkspaceManager

VAULT_ROOT = Path("D:/CloudDesk/Vault")
STATE_FILE = Path("D:/CloudDesk/workspace_state.json")
CLOUD_SUBDIR = "Projects"

_state_lock = threading.Lock()
_deps_threads: Dict[str, threading.Thread] = {}


# ----------------------------------------------------------------- helpers --
def safe_project_name(name: str) -> str:
    name = (name or "").strip()
    if not name or name in (".", "..") or any(c in name for c in '/\\:*?"<>|') or Path(name).name != name:
        raise ValueError(f"Invalid project name: {name!r}")
    return name


def is_secret(filename: str) -> bool:
    low = filename.lower()
    if low.startswith(".env"):
        return True
    for pat in STRICT_EXCLUDE_FILES:
        p = pat.lower()
        if (p.startswith("*") and low.endswith(p[1:])) or low == p:
            return True
    return False


def is_regenerable_dir(dirname: str) -> bool:
    return dirname in STRICT_EXCLUDE_DIRS or dirname.startswith(".venv")


def walk_project(root: Path) -> Iterator[Tuple[Path, bool]]:
    """Yield (relative_path, is_secret) for every file worth keeping."""
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not is_regenerable_dir(d)]
        for f in files:
            full = Path(cur) / f
            if full.is_symlink():
                continue
            yield full.relative_to(root), is_secret(f)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _force_remove(func: Callable, path: str, _exc) -> None:
    """git marks object files read-only on Windows; clear the flag and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def rmtree_hard(path: Path) -> List[str]:
    """Delete a tree; return what couldn't be removed (files open in an editor, etc.)."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_remove)
    else:
        shutil.rmtree(path, onerror=_force_remove)
    if not path.exists():
        return []
    return [str(p) for p in path.rglob("*")][:20] or [str(path)]


def newest_mtime(root: Path) -> float:
    newest = 0.0
    for rel, _ in walk_project(root):
        try:
            newest = max(newest, (root / rel).stat().st_mtime)
        except OSError:
            continue
    return newest or root.stat().st_mtime


# ------------------------------------------------------------------- state --
def load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_state(name: str, **fields: Any) -> Dict[str, Any]:
    with _state_lock:
        st = load_state()
        entry = st.setdefault(name, {})
        entry.update(fields)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
        return entry


# --------------------------------------------------------------- workspace --
class CloudWorkspace:
    """Open (hydrate) and park (dehydrate) projects between Google Drive and D:."""

    @staticmethod
    def cloud_root() -> Path:
        my_drive = CloudDriveManager.get_my_drive_path()
        if not my_drive or not Path(my_drive).exists():
            raise RuntimeError("Google Drive (G:) is not mounted - start Google Drive for desktop.")
        root = Path(my_drive) / CLOUD_SUBDIR
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def local_root() -> Path:
        return LOCAL_DIRS["workspace"]

    # ---------------------------------------------------------------- list --
    @classmethod
    def list_projects(cls) -> List[Dict[str, Any]]:
        state = load_state()
        names: Dict[str, Dict[str, Any]] = {}
        try:
            for d in cls.cloud_root().iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    names.setdefault(d.name, {})["in_cloud"] = True
        except RuntimeError:
            pass
        lr = cls.local_root()
        if lr.exists():
            for d in lr.iterdir():
                if d.is_dir() and not d.name.startswith((".", "_")):
                    names.setdefault(d.name, {})["on_laptop"] = True
        out = []
        for name in sorted(names, key=str.lower):
            flags = names[name]
            entry = state.get(name, {})
            out.append({
                "name": name,
                "on_laptop": bool(flags.get("on_laptop")),
                "in_cloud": bool(flags.get("in_cloud")),
                "status": "working" if flags.get("on_laptop") else "parked",
                "last_opened": entry.get("opened_at"),
                "last_parked": entry.get("parked_at"),
                "deps": entry.get("deps"),
                "github": cls.github_repo(name),
                "secrets_in_vault": (VAULT_ROOT / name).exists(),
            })
        return out

    @classmethod
    def github_repo(cls, name: str) -> Optional[str]:
        """owner/repo from the project's .git/config (local copy first, then Drive)."""
        candidates = [cls.local_root() / name / ".git" / "config"]
        try:
            candidates.append(cls.cloud_root() / name / ".git" / "config")
        except RuntimeError:
            pass
        for cfg in candidates:
            try:
                text = cfg.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("url") and "github.com" in line:
                    tail = line.split("github.com", 1)[1].lstrip(":/")
                    tail = tail[:-4] if tail.endswith(".git") else tail
                    if tail.count("/") == 1:
                        return tail
        return None

    # ---------------------------------------------------------------- open --
    @classmethod
    def open(cls, name: str, install_deps: bool = True) -> Dict[str, Any]:
        name = safe_project_name(name)
        src = cls.cloud_root() / name
        dst = cls.local_root() / name
        state = load_state().get(name, {})

        if dst.exists() and state.get("status") != "parking":
            return {"success": True, "project": name, "path": str(dst), "already_on_laptop": True}
        if not src.exists():
            raise FileNotFoundError(f"'{name}' is not in Google Drive ({src}).")

        copied = 0
        for rel, _secret in walk_project(src):
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            s = src / rel
            if target.exists() and target.stat().st_size == s.stat().st_size:
                continue  # finishing an interrupted open
            shutil.copy2(s, target)
            copied += 1

        restored = cls._restore_secrets(name, dst)
        update_state(name, status="working", opened_at=datetime.now().isoformat(timespec="seconds"))
        deps = cls.install_dependencies(name) if install_deps else None
        return {"success": True, "project": name, "path": str(dst), "files_copied": copied,
                "secrets_restored": restored, "dependencies": deps}

    # ---------------------------------------------------------------- park --
    @classmethod
    def park(cls, name: str, verify: str = "sha256") -> Dict[str, Any]:
        name = safe_project_name(name)
        local = cls.local_root() / name
        if not local.exists():
            raise FileNotFoundError(f"'{name}' is not on the laptop ({local}).")
        cloud = cls.cloud_root() / name
        cloud.mkdir(parents=True, exist_ok=True)
        update_state(name, status="parking")

        keep, secrets = set(), []
        uploaded = skipped = 0
        for rel, secret in walk_project(local):
            if secret:
                secrets.append(rel)
                continue
            keep.add(rel)
            s, d = local / rel, cloud / rel
            if d.exists():
                ss, ds = s.stat(), d.stat()
                if ss.st_size == ds.st_size and abs(ss.st_mtime - ds.st_mtime) < 2:
                    skipped += 1
                    continue
            try:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)
                uploaded += 1
            except OSError:
                keep.discard(rel)

        # mirror deletions: files removed locally must not linger in the cloud copy
        removed = 0
        for rel, _ in list(walk_project(cloud)):
            if rel not in keep and not is_secret(rel.name):
                try:
                    (cloud / rel).unlink()
                    removed += 1
                except OSError:
                    pass

        # verify every file before touching the laptop copy; anything that differs
        # (e.g. a same-size edit the size+mtime shortcut skipped) is re-uploaded once
        def differs(rel: Path) -> bool:
            s, d = local / rel, cloud / rel
            if not d.exists() or d.stat().st_size != s.stat().st_size:
                return True
            return verify == "sha256" and sha256(s) != sha256(d)

        bad = [rel for rel in keep if differs(rel)]
        for rel in bad:
            try:
                shutil.copy2(local / rel, cloud / rel)
                uploaded += 1
            except OSError:
                pass
        bad = [str(rel) for rel in bad if differs(rel)]
        if bad:
            update_state(name, status="working")
            return {"success": False, "project": name, "error": "Verification failed - laptop copy kept.",
                    "mismatched_files": bad[:20]}

        cls._vault_secrets(name, local, secrets)
        leftovers = rmtree_hard(local)
        now = datetime.now().isoformat(timespec="seconds")
        if leftovers:
            update_state(name, status="parking", parked_at=now)
            return {"success": False, "project": name, "uploaded": uploaded, "verified": len(keep),
                    "error": "Saved to Google Drive, but some files are open in another app. "
                             "Close the editor/terminal using the project and park again.",
                    "locked": leftovers}
        update_state(name, status="parked", parked_at=now, deps=None)
        return {"success": True, "project": name, "cloud_path": str(cloud), "uploaded": uploaded,
                "unchanged": skipped, "removed_from_cloud": removed, "verified": len(keep),
                "secrets_kept_local": len(secrets)}

    @classmethod
    def auto_park(cls, idle_days: float) -> Dict[str, Any]:
        """Park every laptop project with no file changes for idle_days."""
        if idle_days <= 0 or not cls.local_root().exists():
            return {"parked": [], "skipped": []}
        cutoff = time.time() - idle_days * 86400
        parked, skipped = [], []
        for d in cls.local_root().iterdir():
            if not d.is_dir() or d.name.startswith((".", "_")):
                continue
            try:
                if newest_mtime(d) >= cutoff:
                    continue
                res = cls.park(d.name)
                (parked if res.get("success") else skipped).append({d.name: res.get("error", "ok")})
            except Exception as e:  # one bad project must not stop the rest
                skipped.append({d.name: str(e)})
        return {"parked": parked, "skipped": skipped}

    # ------------------------------------------------------------- secrets --
    @staticmethod
    def _vault_secrets(name: str, local: Path, secrets: List[Path]) -> None:
        for rel in secrets:
            target = VAULT_ROOT / name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local / rel, target)

    @staticmethod
    def _restore_secrets(name: str, dst: Path) -> int:
        vault = VAULT_ROOT / name
        if not vault.exists():
            return 0
        n = 0
        for f in vault.rglob("*"):
            if f.is_file():
                target = dst / f.relative_to(vault)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                n += 1
        rmtree_hard(vault)  # one copy only: the secrets now live in the working copy
        return n

    # -------------------------------------------------------- dependencies --
    @staticmethod
    def dependency_commands(project: Path) -> List[List[str]]:
        cmds: List[List[str]] = []
        if (project / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
            cmds.append([shutil.which("pnpm"), "install", "--frozen-lockfile"])
        elif (project / "yarn.lock").exists() and shutil.which("yarn"):
            cmds.append([shutil.which("yarn"), "install", "--frozen-lockfile"])
        elif (project / "package-lock.json").exists() and shutil.which("npm"):
            cmds.append([shutil.which("npm"), "ci", "--no-audit", "--no-fund"])
        elif (project / "package.json").exists() and shutil.which("npm"):
            cmds.append([shutil.which("npm"), "install", "--no-audit", "--no-fund"])
        if (project / "requirements.txt").exists():
            py = project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            cmds.append([sys.executable, "-m", "venv", str(project / ".venv")])
            cmds.append([str(py), "-m", "pip", "install", "-q", "-r", str(project / "requirements.txt")])
        return cmds

    @classmethod
    def install_dependencies(cls, name: str) -> Dict[str, Any]:
        """Install in the background (caches already live on D:); progress goes to the state file."""
        name = safe_project_name(name)
        project = cls.local_root() / name
        cmds = cls.dependency_commands(project)
        if not cmds:
            update_state(name, deps={"status": "none"})
            return {"status": "none"}
        running = _deps_threads.get(name)
        if running and running.is_alive():
            return {"status": "running"}

        def run() -> None:
            update_state(name, deps={"status": "running", "started": datetime.now().isoformat(timespec="seconds")})
            for cmd in cmds:
                try:
                    r = subprocess.run(cmd, cwd=str(project), capture_output=True, text=True, timeout=1800,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except (OSError, subprocess.TimeoutExpired) as e:
                    update_state(name, deps={"status": "failed", "error": str(e)})
                    return
                if r.returncode != 0:
                    tail = (r.stderr or r.stdout).strip().splitlines()[-5:]
                    update_state(name, deps={"status": "failed", "command": " ".join(cmd[1:3]), "log": tail})
                    return
            update_state(name, deps={"status": "ready", "finished": datetime.now().isoformat(timespec="seconds")})

        t = threading.Thread(target=run, name=f"deps-{name}", daemon=True)
        _deps_threads[name] = t
        t.start()
        return {"status": "running", "steps": len(cmds)}
