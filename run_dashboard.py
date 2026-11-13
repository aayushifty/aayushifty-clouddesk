"""
Aayushifty CloudDesk - Desktop Dashboard Launcher
Lightweight, native Windows desktop runner using Microsoft Edge WebView2 (pywebview)
with fallback to default browser. Ultra-low RAM footprint (< 45 MB).
"""
import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn
from core.server import app

PORT = 8765
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"


def start_server():
    """Runs the FastAPI backend via uvicorn in a background thread."""
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main():
    use_browser = "--browser" in sys.argv

    # Start FastAPI daemon thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait briefly for server initialization
    time.sleep(1.2)

    if not use_browser:
        try:
            import webview
            print(f"[CloudDesk] Starting native Edge WebView2 window on {URL}...")
            webview.create_window(
                title="Aayushifty CloudDesk — Hybrid Cloud Environment",
                url=URL,
                width=1240,
                height=800,
                min_size=(960, 640),
                background_color="#090d16"
            )
            webview.start()
            return
        except Exception as e:
            print(f"[CloudDesk] pywebview fallback: {e}")

    # Fallback to default browser
    print(f"[CloudDesk] Opening in browser: {URL}")
    webbrowser.open(URL)
    print("[CloudDesk] Server running. Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[CloudDesk] Shutting down cleanly.")


if __name__ == "__main__":
    main()

