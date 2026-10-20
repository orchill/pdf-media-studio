@echo off
setlocal
title PDF ^& Media Studio
cd /d "%~dp0.."

rem ---- locate python (project venv preferred) ----
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [error] Python 3.10+ is required. Run scripts\setup.bat first.
  pause & exit /b 1
)

rem ---- one-time setup if needed ----
if not exist ".venv\Scripts\python.exe" (
  echo [setup] First run - creating virtual environment...
  "%PY%" -m venv .venv || goto :err
  set "PY=.venv\Scripts\python.exe"
  "%PY%" -m pip install --upgrade pip >nul
  "%PY%" -m pip install -r requirements.txt || goto :err
)
if not exist "frontend\dist\index.html" (
  echo [setup] Building the web interface...
  where npm >nul 2>nul && ( pushd frontend & call npm install --no-audit --no-fund >nul 2>nul & call npm run build & popd ) || echo [info] npm not found - using bundled UI.
)

"%PY%" run.py %*
goto :eof

:err
echo [error] Setup failed - see messages above.
pause
