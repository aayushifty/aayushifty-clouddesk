@echo off
REM Aayushifty CloudDesk - Windows Command Launcher
set PYTHON_EXE=C:\Users\joshi\AppData\Local\Programs\Python\Python313\python.exe
set APP_DIR=C:\Users\joshi\.gemini\antigravity\scratch\aayushifty-clouddesk

if "%1"=="backup" (
    "%PYTHON_EXE%" -c "import sys; sys.path.append(r'%APP_DIR%'); from core.backup_engine import BackupEngine; res = BackupEngine.create_project_backup(r'%2'); print(res)"
    goto end
)

if "%1"=="analyze" (
    "%PYTHON_EXE%" -c "import sys; sys.path.append(r'%APP_DIR%'); from core.storage_optimizer import StorageOptimizer; import json; print(json.dumps(StorageOptimizer.scan_storage_overview(), indent=2))"
    goto end
)

if "%1"=="browser" (
    "%PYTHON_EXE%" "%APP_DIR%\run_dashboard.py" --browser
    goto end
)

REM Default: Launch Desktop Dashboard
"%PYTHON_EXE%" "%APP_DIR%\run_dashboard.py"

:end

