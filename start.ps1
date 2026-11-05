# 실행: 설치된 가상환경으로 Streamlit을 시작합니다. 127.0.0.1은 이 PC에서만 접속 가능한 주소입니다.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run .\install.ps1 first.' }
& $python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
exit $LASTEXITCODE
