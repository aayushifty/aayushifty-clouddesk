$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path $DesktopPath "Aayushifty CloudDesk.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Users\joshi\AppData\Local\Programs\Python\Python313\pythonw.exe"
$Shortcut.Arguments = "`"C:\Users\joshi\.gemini\antigravity\scratch\aayushifty-clouddesk\run_dashboard.py`""
$Shortcut.WorkingDirectory = "C:\Users\joshi\.gemini\antigravity\scratch\aayushifty-clouddesk"
$Shortcut.Description = "Aayushifty CloudDesk — Hybrid Cloud Development Environment"
$Shortcut.WindowStyle = 1
$Shortcut.Save()

Write-Host "Desktop shortcut created at: $ShortcutPath" -ForegroundColor Green

