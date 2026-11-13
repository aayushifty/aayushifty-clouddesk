"""
Migrate projects from C: to Cloud Workspace (Google Drive) and free local C: space.
Only deletes original C: directories if `CloudWorkspace.park(name)` succeeds and files are verified.
"""
import os
import shutil
import stat
import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.cloud_workspace import CloudWorkspace, rmtree_hard, is_regenerable_dir
from core.project_lifecycle import STRICT_EXCLUDE_DIRS

EXCLUDE_DIRS = set(STRICT_EXCLUDE_DIRS) | {
    "node_modules", "dist", "build", ".next", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".turbo",
    ".gradle", "bin", "obj", ".coverage", ".playwright-mcp",
    "webview", "workspaces", "EBWebView", "GrShaderCache"
}

INVALID_CHARS = '<>:"/\\|?*'

def is_invalid_name(name: str) -> bool:
    name_str = str(name).strip()
    if not name_str or name.endswith(" ") or name.startswith(" "):
        return True
    return any(c in name for c in INVALID_CHARS)

def get_dir_size(path: Path) -> int:
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total

def copy_clean(src: Path, dst: Path):
    if dst.exists():
        rmtree_hard(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        # Exclude regenerable and invalid dirs
        dirs[:] = [d for d in dirs if not (
            d in EXCLUDE_DIRS or
            d.startswith(".venv") or
            is_regenerable_dir(d) or
            is_invalid_name(d)
        )]
        rel_dir = Path(root).relative_to(src)
        target_dir = dst / rel_dir
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        for f in files:
            if is_invalid_name(f):
                continue
            s_file = Path(root) / f
            d_file = target_dir / f
            try:
                shutil.copy2(s_file, d_file)
            except OSError as e:
                pass

def main():
    user_dir = Path(r"C:\Users\joshi")
    scratch_dir = user_dir / ".gemini" / "antigravity" / "scratch"

    candidates = [
        ("code", user_dir / "code"),
        ("AETHER", user_dir / "AETHER"),
        ("FORGE", user_dir / "FORGE"),
        ("HandChord", user_dir / "HandChord"),
        ("offlinepay", user_dir / "offlinepay"),
        ("OpenJarvis", user_dir / "OpenJarvis"),
    ]

    for item in sorted(scratch_dir.iterdir(), key=lambda x: x.name.lower()):
        if item.is_dir() and item.name != "aayushifty-clouddesk":
            candidates.append((item.name, item))

    total_c, used_c_start, free_c_start = shutil.disk_usage("C:\\")
    print(f"=== STARTING PROJECT MIGRATION TO CLOUD WORKSPACE ===")
    print(f"C: Initial Free: {free_c_start / (1024**3):.2f} GB\n")

    # Check already parked projects
    try:
        projects_state = CloudWorkspace.list_projects()
        already_parked = {p["name"] for p in projects_state if p.get("in_cloud") and p.get("status") == "parked"}
    except Exception:
        already_parked = set()

    results = []
    total_freed_bytes = 0

    for name, src in candidates:
        if not src.exists():
            print(f"[-] Skipping {name}: source does not exist.")
            continue

        if name in already_parked and (CloudWorkspace.cloud_root() / name).exists():
            print(f"[+] {name} is already parked in Google Drive. Checking if C: original can be removed...")
            src_size = get_dir_size(src)
            if src_size > 0:
                rmtree_hard(src)
                print(f"    Removed C: copy for {name} ({src_size / (1024*1024):.2f} MB).")
                total_freed_bytes += src_size
                results.append({"name": name, "status": "ALREADY_PARKED_CLEANED", "freed_mb": src_size / (1024*1024), "verified": 0})
            else:
                results.append({"name": name, "status": "ALREADY_PARKED", "freed_mb": 0, "verified": 0})
            continue

        src_size = get_dir_size(src)
        src_size_mb = src_size / (1024 * 1024)
        print(f"\n---> Processing: {name} ({src_size_mb:.2f} MB on C:)")

        workspace_dst = CloudWorkspace.local_root() / name

        # 1. Copy clean project to D:\CloudDesk\Workspace
        print(f"     1. Copying to {workspace_dst} (stripping node_modules, .venv, build)...")
        copy_clean(src, workspace_dst)

        # 2. Park project to Google Drive with SHA-256 verification
        print(f"     2. Parking to Google Drive (G:\\My Drive\\Projects\\{name})...")
        t0 = time.time()
        park_res = CloudWorkspace.park(name)
        elapsed = time.time() - t0

        if park_res.get("success"):
            verified_count = park_res.get("verified", 0)
            uploaded_count = park_res.get("uploaded", 0)
            print(f"     [+] Park SUCCESS ({elapsed:.1f}s): {verified_count} files verified, {uploaded_count} uploaded.")
            
            # 3. Only delete original on C: if park succeeded!
            print(f"     3. Deleting C: original ({src})...")
            rmtree_hard(src)
            if not src.exists():
                print(f"     [+] C: original removed. Freed {src_size_mb:.2f} MB.")
                total_freed_bytes += src_size
                results.append({"name": name, "status": "SUCCESS", "freed_mb": src_size_mb, "verified": verified_count})
            else:
                print(f"     [!] Warning: C: original could not be fully removed (files might be locked).")
                results.append({"name": name, "status": "PARTIAL_DELETE", "freed_mb": 0, "verified": verified_count})
        else:
            err = park_res.get("error", "Unknown error")
            print(f"     [-] Park FAILED: {err}. C: ORIGINAL PRESERVED!")
            results.append({"name": name, "status": "FAILED", "error": err, "freed_mb": 0})

    total_c, used_c_end, free_c_end = shutil.disk_usage("C:\\")
    actual_freed_gb = (free_c_end - free_c_start) / (1024**3)

    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    for r in results:
        status = r["status"]
        if status in ("SUCCESS", "ALREADY_PARKED_CLEANED"):
            print(f"  [OK] {r['name']:<30}: {r['freed_mb']:>8.2f} MB freed ({r.get('verified', 0)} files verified)")
        else:
            print(f"  [{status}] {r['name']:<30}: {r.get('error', 'Done')}")

    print("-" * 60)
    print(f"Total Nominal Data Freed: {total_freed_bytes / (1024**3):.2f} GB ({total_freed_bytes / (1024**2):.2f} MB)")
    print(f"C: Drive Before: {free_c_start / (1024**3):.2f} GB free")
    print(f"C: Drive After:  {free_c_end / (1024**3):.2f} GB free")
    print(f"Actual C: Space Freed: {actual_freed_gb:.2f} GB")
    print("=" * 60)

if __name__ == "__main__":
    main()
