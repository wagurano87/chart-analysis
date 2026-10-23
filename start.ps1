$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run .\install.ps1 first.' }
& $python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
exit $LASTEXITCODE
