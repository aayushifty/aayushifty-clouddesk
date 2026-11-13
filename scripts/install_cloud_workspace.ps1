<#
.SYNOPSIS
    One-time setup for the CloudDesk Cloud Workspace (no admin needed):
      * Explorer right-click: "CloudDesk: Park to Google Drive" on projects in D:\CloudDesk\Workspace
                              "CloudDesk: Open on this laptop" on projects in G:\My Drive\Projects
      * `cdesk` command in any terminal
      * Desktop shortcut "CloudDesk Projects" that opens G:\My Drive\Projects
    Re-run any time. -Uninstall removes the menu entries and the command.
#>
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$root   = Split-Path $PSScriptRoot -Parent
$cdesk  = Join-Path $root 'scripts\cdesk.py'
$py     = (Get-Command python -ErrorAction Stop).Source
$pyw    = Join-Path (Split-Path $py) 'pythonw.exe'
$binDir = Join-Path $env:LOCALAPPDATA 'CloudDesk\bin'
$menu   = 'HKCU:\Software\Classes\Directory\shell'

$entries = @{
    'CloudDeskPark' = @{ Label = 'CloudDesk: Park to Google Drive'; Verb = 'park-path'; Extra = '';
                         AppliesTo = 'System.ItemPathDisplay:~<"D:\CloudDesk\Workspace\"'; Icon = 'imageres.dll,-1043' }
    'CloudDeskOpen' = @{ Label = 'CloudDesk: Open on this laptop';  Verb = 'open-path'; Extra = ' --code';
                         AppliesTo = 'System.ItemPathDisplay:~<"G:\My Drive\Projects\"'; Icon = 'imageres.dll,-1024' }
}

if ($Uninstall) {
    foreach ($k in $entries.Keys) { Remove-Item "$menu\$k" -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item $binDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host 'CloudDesk menu entries and cdesk command removed.' -ForegroundColor Green
    return
}

# 1. Explorer right-click menu (current user only)
foreach ($k in $entries.Keys) {
    $e = $entries[$k]
    New-Item -Path "$menu\$k\command" -Force | Out-Null
    Set-ItemProperty "$menu\$k" -Name '(default)'  -Value $e.Label
    Set-ItemProperty "$menu\$k" -Name 'Icon'       -Value $e.Icon
    Set-ItemProperty "$menu\$k" -Name 'AppliesTo'  -Value $e.AppliesTo
    Set-ItemProperty "$menu\$k\command" -Name '(default)' -Value "`"$pyw`" `"$cdesk`" --notify $($e.Verb) `"%1`"$($e.Extra)"
}

# 2. `cdesk` command on PATH
New-Item -ItemType Directory -Path $binDir -Force | Out-Null
Set-Content -Path (Join-Path $binDir 'cdesk.cmd') -Value "@`"$py`" `"$cdesk`" %*" -Encoding ASCII
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $binDir) {
    [Environment]::SetEnvironmentVariable('Path', ($userPath.TrimEnd(';') + ";$binDir"), 'User')
}

# 3. Desktop shortcut to the cloud project folder
$target = 'G:\My Drive\Projects'
if (Test-Path $target) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'CloudDesk Projects.lnk'))
    $lnk.TargetPath = $target
    $lnk.Description = 'Your projects in Google Drive - right-click one > CloudDesk: Open on this laptop'
    $lnk.Save()
}

Write-Host 'Cloud Workspace installed:' -ForegroundColor Green
Write-Host '  - Right-click a project folder in G:\My Drive\Projects  -> "CloudDesk: Open on this laptop"'
Write-Host '  - Right-click a project folder in D:\CloudDesk\Workspace -> "CloudDesk: Park to Google Drive"'
Write-Host '  - Terminal: cdesk list | cdesk open <name> | cdesk park <name> | cdesk ai "question"  (open a new terminal first)'
