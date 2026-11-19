@echo off
REM Builds the frontend and starts ONE server that serves the whole app on http://localhost:8000
REM (and on your network address, so people on the same Wi-Fi can open it too).
cd /d "%~dp0frontend"
call npm install
call npm run build
cd /d "%~dp0backend"
call venv\Scripts\activate
echo.
echo Open http://localhost:8000   (leave this window open)
uvicorn app.main:app --host 0.0.0.0 --port 8000
