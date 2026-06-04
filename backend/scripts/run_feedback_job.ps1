# Schedule with Windows Task Scheduler, e.g. every 6 hours:
# Program: powershell.exe
# Arguments: -ExecutionPolicy Bypass -File "F:\...\backend\scripts\run_feedback_job.ps1"

$ErrorActionPreference = "Stop"
$Backend = Split-Path -Parent $PSScriptRoot
Set-Location $Backend

& .\venv\Scripts\python.exe .\scripts\process_feedback.py --limit 10 --reingest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
