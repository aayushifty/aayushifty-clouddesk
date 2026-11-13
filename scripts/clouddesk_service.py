"""
Aayushifty CloudDesk 2.0 - Background Automation Daemon
Runs lightweight background tasks every 10 minutes:
  1. Auto-syncs eligible assets from D:\\CloudDesk\\Workspace to Google Drive
  2. Runs system capacity guardrail checks (RAM & Disk limits)
  3. Reclaims safe temporary files (>24 hours old)
Ultra-low RAM overhead (< 15 MB).
"""
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.automation_engine import AutomationEngine
from core.storage_optimizer import StorageOptimizer


def run_daemon_cycle():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Running CloudDesk 2.0 Automation Cycle...")
    
    # 1. Capacity Guardrail Check
    guard = AutomationEngine.run_system_guardrail_check()
    if guard["warnings"]:
        for w in guard["warnings"]:
            print(f"  [GUARDRAIL WARNING] {w}")
    else:
        print("  [HEALTH] System capacity within optimal thresholds.")

    # 2. Project Asset Auto-Sync
    sync = AutomationEngine.run_auto_sync()
    print(f"  [SYNC] Processed {sync['synced_projects']} projects ({sync['total_synced_files']} files synced to Google Drive).")

    # 3. Safe Temp File Cleanup
    clean = StorageOptimizer.clean_safe_temp_files()
    if clean["deleted_items"] > 0:
        print(f"  [STORAGE] Purged {clean['deleted_items']} orphan temp files ({clean['reclaimed_mb']} MB reclaimed).")


def main():
    print("=== Aayushifty CloudDesk 2.0 Background Automation Daemon Active ===")
    while True:
        try:
            run_daemon_cycle()
        except Exception as e:
            print(f"Daemon cycle error: {e}")
        # Sleep for 10 minutes (600 seconds)
        time.sleep(600)


if __name__ == "__main__":
    main()

