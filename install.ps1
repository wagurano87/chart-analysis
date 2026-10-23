$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    & py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ with the py launcher is required.' }
}
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Installed. Run .\start.ps1 to open the chart analysis app.'
