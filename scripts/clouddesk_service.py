"""
Aayushifty CloudDesk 2.0 - Background Automation Daemon
Runs lightweight background tasks every 10 minutes:
  1. Auto-syncs eligible assets from D:\\CloudDesk\\Workspace to Google Drive
  2. Runs system capacity guardrail checks (RAM & Disk limits)
  3. Reclaims safe temporary files (>24 hours old)
  4. Parks idle projects to Google Drive (config: auto_park_days, default 7; 0 = off)
It also serves the CloudDesk API on 127.0.0.1:8765 (dashboard + AI gateway) so
agents can use http://127.0.0.1:8765/v1 even when the dashboard window is closed.
"""
import socket
import threading
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.automation_engine import AutomationEngine
from core.storage_optimizer import StorageOptimizer
from core.workspace_manager import WorkspaceManager

HOST, PORT = "127.0.0.1", 8765
AUTO_PARK_EVERY = 6 * 3600  # check for idle projects every 6 hours
_last_auto_park = 0.0


def port_in_use(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def start_api_server() -> None:
    """Serve the API headless unless the dashboard window already does."""
    if port_in_use():
        return
    import uvicorn
    from core.server import app

    threading.Thread(
        target=lambda: uvicorn.run(app, host=HOST, port=PORT, log_level="warning"),
        name="clouddesk-api", daemon=True,
    ).start()


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

    # 4. Park idle projects (laptop copy freed, Google Drive keeps the verified original)
    global _last_auto_park
    days = float(WorkspaceManager.load_config().get("auto_park_days", 7) or 0)
    if days > 0 and time.time() - _last_auto_park > AUTO_PARK_EVERY:
        _last_auto_park = time.time()
        from core.cloud_workspace import CloudWorkspace
        res = CloudWorkspace.auto_park(days)
        for item in res["parked"]:
            print(f"  [PARKED] {list(item)[0]} -> Google Drive (idle {days:g}+ days)")
        for item in res["skipped"]:
            print(f"  [PARK SKIPPED] {item}")


def main():
    print("=== Aayushifty CloudDesk Background Automation Daemon Active ===")
    try:
        start_api_server()
    except Exception as e:
        print(f"API server not started: {e}")
    while True:
        try:
            run_daemon_cycle()
        except Exception as e:
            print(f"Daemon cycle error: {e}")
        # Sleep for 10 minutes (600 seconds)
        time.sleep(600)


if __name__ == "__main__":
    main()

