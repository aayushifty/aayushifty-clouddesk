# Aayushifty CloudDesk 2.0 — Cloud-First Hybrid Environment

> **A cloud-first hybrid development environment transforming Google Drive (5 TB) into the central primary storage layer, using local NVMe SSD (D: & E:) as an active execution workspace and cache.**

---

## 0. Cloud Workspace & AI Gateway (start here)

Google Drive is the **only permanent home** of your projects. The laptop holds a project
only while you work on it. Heavy AI runs in the cloud.

| You do | What happens |
|---|---|
| **Open** (dashboard → Cloud Workspace, right-click → *CloudDesk: Open on this laptop*, or `cdesk open <name>`) | Copies the project from `G:\My Drive\Projects` to `D:\CloudDesk\Workspace`, restores its `.env`/keys, installs dependencies in the background (caches on D:), opens VS Code |
| **Park** (dashboard, right-click → *CloudDesk: Park to Google Drive*, or `cdesk park <name>`) | Uploads changes, mirrors deletions, **verifies every file with SHA-256**, then deletes the laptop copy *including* `node_modules`/`.venv`/build output. If anything fails, nothing local is deleted. |
| Nothing (7 days idle) | The background service parks the project automatically (`auto_park_days` in `D:\CloudDesk\clouddesk_config.json`, 0 = off) |
| **Run in cloud** | Opens the project in GitHub Codespaces: cloud CPU/RAM, nothing runs on the laptop |

Secrets never go to the cloud: on park, `.env`, `*.pem`, `*.key`… move to `D:\CloudDesk\Vault\<project>`
and come back on open. Regenerable folders are never uploaded. Files deleted from a cloud
project go to Google Drive's Trash (recoverable for 30 days).

**AI Gateway.** Point any agent or tool that speaks the OpenAI API at CloudDesk:

```
OPENAI_BASE_URL=http://127.0.0.1:8765/v1
OPENAI_API_KEY=clouddesk          # dummy - the real Gemini key stays in Windows Credential Manager
model=auto                        # -> ai_gateway.default_model (gemini-3.5-flash-lite)
```

Requests run on Gemini, so they use 0 MB of laptop RAM instead of 2–4 GB for an Ollama
model. `local:<model>` forces local Ollama. When the cloud is unreachable, requests fall
back to `ai_gateway.local_model` on Ollama automatically. Only the dashboard origin and
local programs can call it: websites can't spend your key. Try it with `cdesk ai "hello"`.

**Setup (once):** `powershell -ExecutionPolicy Bypass -File scripts\install_cloud_workspace.ps1`
adds the right-click menu (on Windows 11 it's under *Show more options*), the `cdesk`
command and a *CloudDesk Projects* desktop shortcut. The background service now also
serves the API, so the gateway works with the dashboard window closed.

---

## 1. Central Storage Philosophy

```
+---------------------------------------------------------------------------------------------------+
|                                  AAYUSHIFTY CLOUDDESK 2.0                                         |
|                                                                                                   |
|  1. GOOGLE DRIVE (G:)   = PRIMARY CENTRAL STORAGE (5 TB Capacity)                                 |
|     • Central Project Folders, AI Datasets, Model Archives, Videos, PCB Designs, Backups         |
|                                                                                                   |
|  2. LOCAL NVMe SSD      = ACTIVE WORKSPACE & CACHE LAYER                                          |
|     • D:\CloudDesk\Workspace     -> Active project code & high-speed execution                    |
|     • D:\CloudDesk\Dependencies  -> Local node_modules & Python venvs                             |
|     • D:\CloudDesk\ModelCache    -> AI models actively running locally                            |
|     • E:\CloudDesk\Temporary     -> Intermediate compiler/build scratch                           |
|     • E:\CloudDesk\Staging       -> Atomic upload/download transfer buffers                       |
|     • E:\CloudDesk\Recovery      -> Verified restoration sandboxes                                |
|                                                                                                   |
|  3. GITHUB              = SOURCE CODE VERSION CONTROL & COLLABORATION                             |
|  4. REMOTE COMPUTE      = HEAVY ML / DATA ACCELERATION (Google Colab Free GPU / Codespaces)       |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Directory Architecture

### Local Workspace (D: & E: Drives)
| Directory | Role | Description |
| :--- | :--- | :--- |
| `D:\CloudDesk\Workspace` | Active Workspaces | Where your code runs locally with NVMe speeds. |
| `D:\CloudDesk\Dependencies` | Local Dependencies | Dedicated storage for `node_modules` and Python venvs. |
| `D:\CloudDesk\ModelCache` | Active Model Cache | AI model weights currently running in local inference. |
| `E:\CloudDesk\Temporary` | Temporary Output | Scratch builds, intermediate render frames, test output. |
| `E:\CloudDesk\Staging` | Transfer Staging | Staging buffer for atomic uploads to Google Drive. |
| `E:\CloudDesk\Recovery` | Sandbox & Restores | Extraction sandbox for safe project restoration. |

### Central Cloud Store (Google Drive `G:\My Drive\`)
* `Projects/` — Central project directories & asset mirrors.
* `AI_Models/` — All AI models (GGUF, safetensors, checkpoints).
* `Datasets/` — Raw training datasets (CSV, Parquet, images, audio).
* `Development_Assets/` — Textures, 3D models, Figma exports, media.
* `Videos/` — High-bitrate video captures and renders.
* `PCB_Designs/` — KiCad, Gerber, and hardware engineering files.
* `Archives/` — Clean, verified completion archives.
* `Backups/` — Automated project backup archives.
* `Documentation/` — Architecture manuals and reference specs.

---

## 3. End-to-End Project Lifecycle

### A. Creating a Project
1. Create in CloudDesk Dashboard or run:
   ```powershell
   # Local workspace + Google Drive central folder + Git initialization
   ```
2. Automatically establishes dual mapping:
   * Local execution: `D:\CloudDesk\Workspace\<project>`
   * Cloud primary: `G:\My Drive\Projects\<project>`
   * Git repository initialized with strict `.gitignore`.

### B. Modifying & Synchronizing Assets
* Code changes are preserved locally and pushed to GitHub.
* Large assets (`assets/`, `models/`, `data/`) are scanned via `/api/projects/diff/{name}`.
* One-click synchronization streams assets to Google Drive using atomic staging in `E:\CloudDesk\Staging`.
* **Zero-Leakage Security Guarantee**: `.env`, `.env.*`, `credentials.json`, `*.pem`, `*.key`, and `id_rsa` are **STRICTLY EXCLUDED** and never uploaded.

### C. Completing & Archiving a Project
1. Generates clean project archive on Google Drive (`Archives/<project>_complete_<timestamp>.zip`).
2. Verifies archive integrity using ZIP CRC32 and SHA256 checksums.
3. Evicts local `node_modules/` and `.venv/` to reclaim local SSD space.
4. Project remains 100% recoverable in one click from the CloudDesk dashboard.

---

## 4. Ollama Migration Status

* **Status**: **MIGRATION COMPLETE & VERIFIED**
* **Source Path**: `C:\Users\joshi\.ollama\models` (7.582 GB)
* **Destination Path**: `D:\ollama_models` (7.582 GB — 100% byte parity match)
* **Windows User Environment Variable**: `OLLAMA_MODELS = D:\ollama_models`
* **Installed Models Verified**:
  * `qwen3:4b-instruct` (2.5 GB)
  * `gemma3:4b` (3.4 GB)
  * `nomic-embed-text:latest` (274 MB)
  * `llama3.2:latest` (2.0 GB)
* **Space Reclamation Recommendation**: The original `C:\Users\joshi\.ollama\models` folder can now be safely deleted to free **7.58 GB** on `C:\`. (Awaiting user confirmation).

---

## 5. Security & Isolation Audit

* **Localhost Isolation**: The dashboard server binds strictly to `127.0.0.1:8765`. No external or public network interfaces are exposed.
* **Credential Vault**: Integrates directly with Windows Credential Manager (`win32cred`). Zero plain-text tokens.
* **Backup Exclusions**: Verified zero-leakage of private keys or environment variables.

---

*Aayushifty CloudDesk 2.0 — Engineered by Antigravity.*
