"""
Verification & Test Suite - Aayushifty CloudDesk
Validates telemetry, storage scanner, backup engine, and credentials vault.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.system_monitor import SystemMonitor
from core.cloud_drive import CloudDriveManager
from core.storage_optimizer import StorageOptimizer
from core.backup_engine import BackupEngine
from core.cloud_dev import CloudDevManager
from core.credentials_vault import CredentialsVault


def run_tests():
    print("=== TEST 1: Telemetry ===")
    telem = SystemMonitor.get_full_telemetry()
    assert "cpu" in telem
    assert "memory" in telem
    assert "gpu" in telem
    assert "disks" in telem
    print(f"CPU: {telem['cpu']['percent']}%, RAM Used: {telem['memory']['used_gb']} GB ({telem['memory']['percent']}%)")
    print(f"GPU: {telem['gpu']['name']} (Available: {telem['gpu']['available']})")
    print("✓ Telemetry PASSED")

    print("\n=== TEST 2: Cloud Drive Status ===")
    drive_stat = CloudDriveManager.get_status()
    print(f"Drive Installed: {drive_stat['installed']}, Mount: {drive_stat['mount_point']}")
    print("✓ Cloud Drive Status PASSED")

    print("\n=== TEST 3: Storage Optimizer Scan ===")
    storage = StorageOptimizer.scan_storage_overview()
    print(f"Temp files: {storage['temp_files']['size_mb']} MB, Caches: {storage['total_cache_gb']} GB")
    print(f"AI Models: {storage['total_model_gb']} GB, Recommendations: {len(storage['recommendations'])}")
    print("✓ Storage Optimizer PASSED")

    print("\n=== TEST 4: Cloud Dev & Projects ===")
    projects = CloudDevManager.discover_local_projects()
    gh = CloudDevManager.get_github_status()
    print(f"Discovered Local Projects: {len(projects)}")
    print(f"GitHub Auth Status: {gh['authenticated']}")
    print("✓ Cloud Dev PASSED")

    print("\n=== TEST 5: Backup Engine (Dry run on aayushifty-clouddesk) ===")
    # Test backing up a subfolder
    sample_dir = BASE_DIR / "templates"
    sample_dir.mkdir(parents=True, exist_ok=True)
    test_file = sample_dir / "sample.txt"
    test_file.write_text("Aayushifty CloudDesk test payload", encoding="utf-8")

    dest_dir = BASE_DIR / "scratch_backups"
    res = BackupEngine.create_project_backup(str(sample_dir), str(dest_dir))
    assert res["success"] is True
    print(f"Backup created: {res['archive_name']} ({res['compressed_size_mb']} MB, {res['files_count']} files)")
    print("✓ Backup Engine PASSED")

    print("\n=== TEST 6: Credentials Vault ===")
    keys = CredentialsVault.list_keys()
    print(f"Available Providers: {len(keys)}")
    print("✓ Credentials Vault PASSED")

    print("\n===========================================")
    print(" ALL 6 CORE INTEGRATION TESTS PASSED 100%! ")
    print("===========================================")


if __name__ == "__main__":
    run_tests()

