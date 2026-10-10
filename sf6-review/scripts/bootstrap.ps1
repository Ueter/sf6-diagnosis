$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv setup failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
& .\.venv\Scripts\python.exe scripts\doctor.py
if ($LASTEXITCODE -ne 0) { throw 'doctor failed; install missing FFmpeg tools and retry' }
