@echo off
setlocal
cd /d "%~dp0.."

echo ==============================================
echo  PDF ^& Media Studio - first-time setup
echo ==============================================

where python >nul 2>nul || (echo [error] Python 3.10+ not found. Install from https://www.python.org/downloads/ and check "Add python.exe to PATH". & pause & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating virtual environment...
  python -m venv .venv || goto :err
)
set "PY=.venv\Scripts\python.exe"
echo [setup] Installing backend dependencies...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt || goto :err

if exist "frontend\package.json" (
  where npm >nul 2>nul && (
    echo [setup] Building web interface ^(npm^)...
    pushd frontend
    call npm install --no-audit --no-fund
    call npm run build
    popd
  ) || echo [info] npm not found - the bundled prebuilt interface will be used.
)

echo.
echo [setup] Done. Start the app with: scripts\start.bat
pause
goto :eof

:err
echo [error] Setup failed - see messages above.
pause
