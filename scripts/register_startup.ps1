$WshShell = New-Object -ComObject WScript.Shell
$StartupFolder = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Startup)
$ShortcutPath = Join-Path $StartupFolder "Aayushifty CloudDesk Service.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Users\joshi\AppData\Local\Programs\Python\Python313\pythonw.exe"
$Shortcut.Arguments = "`"C:\Users\joshi\.gemini\antigravity\scratch\aayushifty-clouddesk\scripts\clouddesk_service.py`""
$Shortcut.WorkingDirectory = "C:\Users\joshi\.gemini\antigravity\scratch\aayushifty-clouddesk"
$Shortcut.Description = "Aayushifty CloudDesk 2.0 Background Automation Daemon"
$Shortcut.WindowStyle = 7 # Minimized/Silent
$Shortcut.Save()

Write-Host "Startup shortcut created at: $ShortcutPath" -ForegroundColor Green

