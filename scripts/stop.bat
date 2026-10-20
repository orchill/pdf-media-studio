@echo off
setlocal
set "PORT=8756"
if not "%~1"=="" set "PORT=%~1"
echo Stopping PDF ^& Media Studio (port %PORT%) ...
set "FOUND="
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr LISTENING') do (
  set FOUND=1
  echo   killing PID %%p
  taskkill /PID %%p /T /F >nul 2>&1
)
if not defined FOUND echo   nothing is listening on port %PORT%.
echo Done.
pause
