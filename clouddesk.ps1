<#
.SYNOPSIS
Aayushifty CloudDesk PowerShell Automation & CLI
#>
param(
    [Parameter(Position=0)]
    [ValidateSet("dashboard", "browser", "backup", "analyze", "init-drive", "relocate-ollama", "help")]
    [string]$Command = "dashboard",

    [Parameter(Position=1)]
    [string]$Target = ""
)

$AppDir = "C:\Users\joshi\.gemini\antigravity\scratch\aayushifty-clouddesk"
$PythonExe = "C:\Users\joshi\AppData\Local\Programs\Python\Python313\python.exe"

switch ($Command) {
    "dashboard" {
        Write-Host "Starting Aayushifty CloudDesk Desktop..." -ForegroundColor Cyan
        & $PythonExe "$AppDir\run_dashboard.py"
    }
    "browser" {
        Write-Host "Starting Aayushifty CloudDesk in Web Browser..." -ForegroundColor Cyan
        & $PythonExe "$AppDir\run_dashboard.py" --browser
    }
    "backup" {
        if (-not $Target) {
            Write-Host "Usage: ./clouddesk.ps1 backup <path_to_project>" -ForegroundColor Red
            return
        }
        Write-Host "Executing clean project backup for: $Target" -ForegroundColor Yellow
        & $PythonExe -c "import sys; sys.path.append(r'$AppDir'); from core.backup_engine import BackupEngine; res = BackupEngine.create_project_backup(r'$Target'); import json; print(json.dumps(res, indent=2))"
    }
    "analyze" {
        Write-Host "Running storage optimization scan..." -ForegroundColor Cyan
        & $PythonExe -c "import sys; sys.path.append(r'$AppDir'); from core.storage_optimizer import StorageOptimizer; import json; print(json.dumps(StorageOptimizer.scan_storage_overview(), indent=2))"
    }
    "init-drive" {
        Write-Host "Initializing unified Google Drive 9-folder structure..." -ForegroundColor Green
        & $PythonExe -c "import sys; sys.path.append(r'$AppDir'); from core.cloud_drive import CloudDriveManager; success, msg, folders = CloudDriveManager.initialize_folder_structure(); print(msg); print(folders)"
    }
    "relocate-ollama" {
        Write-Host "Relocating OLLAMA_MODELS to D:\ollama_models..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path "D:\ollama_models" -Force | Out-Null
        [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\ollama_models", "User")
        Write-Host "OLLAMA_MODELS user environment variable successfully set to D:\ollama_models." -ForegroundColor Green
        Write-Host "To transfer existing models (7.58 GB), run:" -ForegroundColor Cyan
        Write-Host "Move-Item 'C:\Users\joshi\.ollama\models\*' 'D:\ollama_models\' -Force" -ForegroundColor White
    }
    "help" {
        Write-Host "Aayushifty CloudDesk CLI Usage:" -ForegroundColor Cyan
        Write-Host "  ./clouddesk.ps1 dashboard         - Launch native desktop UI"
        Write-Host "  ./clouddesk.ps1 browser           - Launch UI in default browser"
        Write-Host "  ./clouddesk.ps1 backup <path>     - Cleanly backup project (excl. node_modules/.venv)"
        Write-Host "  ./clouddesk.ps1 analyze           - Scan for reclaimable storage"
        Write-Host "  ./clouddesk.ps1 init-drive        - Create 9 unified folders on G: Drive"
        Write-Host "  ./clouddesk.ps1 relocate-ollama   - Migrate Ollama models to D: drive (free 7.6GB)"
    }
}

