@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\aadiv\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "APP_URL=http://127.0.0.1:8000"

if not exist "%PYTHON_EXE%" (
  echo Could not find bundled Python:
  echo %PYTHON_EXE%
  pause
  exit /b 1
)

start "" "%APP_URL%"
echo Teacher Tools is starting at %APP_URL%
echo Keep this window open while using the web app.
echo.
"%PYTHON_EXE%" web_app.py --host 127.0.0.1 --port 8000

pause
