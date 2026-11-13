"""
cdesk - one-command / one-click control of the CloudDesk Cloud Workspace.

    cdesk list                      projects: parked in Google Drive or open on the laptop
    cdesk open  <name> [--code]     bring a project onto the laptop (D:), install deps, open VS Code
    cdesk park  <name>              save to Google Drive (verified) and free the laptop copy
    cdesk autopark [--days N]       park everything untouched for N days
    cdesk ai "prompt"               ask the cloud AI (Gemini via the gateway, 0 MB local RAM)
    cdesk open-path <folder>        used by the Explorer right-click menu
    cdesk park-path <folder>        used by the Explorer right-click menu

Works without the dashboard running; --notify shows a Windows toast instead of printing.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.cloud_workspace import CloudWorkspace  # noqa: E402
from core.workspace_manager import WorkspaceManager  # noqa: E402


def toast(title: str, msg: str) -> None:
    title, msg = title.replace("'", "''"), msg.replace("'", "''")[:240]
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
        "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
        f"$x=$t.GetElementsByTagName('text');$x.Item(0).AppendChild($t.CreateTextNode('{title}'))>$null;"
        f"$x.Item(1).AppendChild($t.CreateTextNode('{msg}'))>$null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('CloudDesk')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def name_from_path(path: str) -> str:
    """Accept a folder in D:\\CloudDesk\\Workspace or G:\\My Drive\\Projects."""
    p = Path(path).resolve()
    roots = [CloudWorkspace.local_root().resolve()]
    try:
        roots.append(CloudWorkspace.cloud_root().resolve())
    except RuntimeError:
        pass
    for root in roots:
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if rel.parts:
            return rel.parts[0]
    raise ValueError(f"{p} is not inside {' or '.join(map(str, roots))}")


def open_vscode(path: str) -> None:
    code = shutil.which("code")
    if code:
        subprocess.Popen([code, path], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def report(args, title: str, res: dict) -> int:
    ok = res.get("success", True)
    if args.notify:
        if ok:
            bits = [f"{k.replace('_', ' ')}: {v}" for k, v in res.items()
                    if k in ("uploaded", "verified", "files_copied", "secrets_restored", "path")]
            toast(f"CloudDesk - {title}", "; ".join(bits) or "Done")
        else:
            toast(f"CloudDesk - {title} failed", res.get("error", "Unknown error"))
    else:
        print(json.dumps(res, indent=2, default=str))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cdesk", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--notify", action="store_true", help="show a Windows notification instead of printing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for c in ("open", "open-path"):
        sp = sub.add_parser(c)
        sp.add_argument("target")
        sp.add_argument("--code", action="store_true", help="open in VS Code afterwards")
        sp.add_argument("--no-deps", action="store_true")
    for c in ("park", "park-path"):
        sub.add_parser(c).add_argument("target")
    sp = sub.add_parser("autopark")
    sp.add_argument("--days", type=float)
    sp = sub.add_parser("ai")
    sp.add_argument("prompt")
    sp.add_argument("--model", default="auto")  # -> ai_gateway default_model
    args = ap.parse_args(argv)

    try:
        if args.cmd == "list":
            for p in CloudWorkspace.list_projects():
                where = "LAPTOP" if p["on_laptop"] else "cloud "
                print(f"  [{where}] {p['name']}" + (f"  (github: {p['github']})" if p["github"] else ""))
            return 0
        if args.cmd in ("open", "open-path"):
            name = args.target if args.cmd == "open" else name_from_path(args.target)
            res = CloudWorkspace.open(name, install_deps=not args.no_deps)
            if args.code and res.get("success"):
                open_vscode(res["path"])
            if res.get("dependencies", {}) and res["dependencies"].get("status") == "running" and not args.notify:
                print("  dependencies are installing in the background (see dashboard)")
            return report(args, f"opened {name}", res)
        if args.cmd in ("park", "park-path"):
            name = args.target if args.cmd == "park" else name_from_path(args.target)
            return report(args, f"parked {name}", CloudWorkspace.park(name))
        if args.cmd == "autopark":
            days = args.days if args.days is not None else WorkspaceManager.load_config().get("auto_park_days", 7)
            res = CloudWorkspace.auto_park(float(days))
            res["success"] = not res["skipped"]
            return report(args, "auto-park", res)
        if args.cmd == "ai":
            from core import ai_gateway
            backend, resp = ai_gateway.chat({"model": args.model, "messages": [{"role": "user", "content": args.prompt}]})
            with resp:
                data = json.loads(resp.read())
            print(data["choices"][0]["message"]["content"])
            print(f"\n  [answered by: {backend} / {data.get('model', '?')}]", file=sys.stderr)
            return 0
    except Exception as e:
        return report(args, args.cmd, {"success": False, "error": str(e)})
    return 1


if __name__ == "__main__":
    sys.exit(main())
