# Starts the TraderClaw engine at logon, in the background, and checks that it runs.
# From the kit folder, in PowerShell (no administrator needed):
#   powershell -ExecutionPolicy Bypass -File scripts/windows/install-startup.ps1
# Uninstall: docs/update-and-uninstall.md
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
if (-not (Test-Path "$Repo\config.json")) { throw "Create config.json first (docs/setup.md, step 3)." }

# Find a real Python 3.9+ through the py launcher (python.exe on PATH may be the Microsoft Store stub).
$Exe = $null
try { $Exe = (& py -3 -c "import sys; print(sys.executable)" 2>$null).Trim() } catch { }
if (-not $Exe) { $Exe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $Exe -or $Exe -like "*WindowsApps*") { throw "Python 3.9+ not found. Install it from python.org, then run this again." }
& $Exe -c "import sys; sys.exit(sys.version_info < (3, 9))"
if ($LASTEXITCODE -ne 0) { throw "$Exe is older than Python 3.9. Install a newer Python from python.org." }
$Pyw = Join-Path (Split-Path $Exe) "pythonw.exe"          # no console window
if (-not (Test-Path $Pyw)) { $Pyw = $Exe }
New-Item -ItemType Directory -Force -Path "$Repo\data" | Out-Null
$Log = "$Repo\data\engine.log"
$Before = if (Test-Path $Log) { (Get-Item $Log).LastWriteTime } else { Get-Date "2000-01-01" }

try {
    # A scheduled task restarts the engine if it ever stops.
    $Action   = New-ScheduledTaskAction -Execute $Pyw -Argument "-m traderclaw run" -WorkingDirectory $Repo
    $Trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName "TraderClaw engine" -Action $Action -Trigger $Trigger -Settings $Settings `
      -Description "TraderClaw kit engine (read-only: levels, alerts, journal)" -Force | Out-Null
    Start-ScheduledTask -TaskName "TraderClaw engine"
    Write-Host "Installed as a scheduled task: TraderClaw engine"
} catch {
    # Some PCs don't let a normal user register logon tasks: a Startup-folder shortcut does the same job.
    $Startup = [Environment]::GetFolderPath("Startup")
    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut("$Startup\TraderClaw engine.lnk")
    $Link.TargetPath = $Pyw
    $Link.Arguments = "-m traderclaw run"
    $Link.WorkingDirectory = $Repo
    $Link.WindowStyle = 7
    $Link.Save()
    Start-Process -FilePath $Pyw -ArgumentList "-m traderclaw run" -WorkingDirectory $Repo -WindowStyle Hidden
    Write-Host "Installed as a Startup-folder shortcut (the scheduled task wasn't allowed: $($_.Exception.Message))"
}

Write-Host "Checking that the engine runs (up to 45 s)..."
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 1
    if ((Test-Path $Log) -and (Get-Item $Log).LastWriteTime -gt $Before) {
        Write-Host "Running. Last log line: $(Get-Content $Log -Tail 1)"
        exit 0
    }
}
Write-Host "No new line in data\engine.log yet. Run 'py -3 -m traderclaw once' in this folder to see the error."
exit 1
