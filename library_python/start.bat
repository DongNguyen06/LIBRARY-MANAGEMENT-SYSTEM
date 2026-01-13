@echo off
chcp 65001 >nul
echo ========================================
echo   Library Management System
echo   Powered by Cloudflare Tunnel
echo ========================================
echo.

REM Check if Cloudflare Tunnel is installed
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cloudflare Tunnel is not installed!
    echo.
    echo Please install Cloudflare Tunnel:
    echo 1. Download from: https://github.com/cloudflare/cloudflared/releases
    echo 2. Or run: winget install --id Cloudflare.cloudflared
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking for existing processes...
echo.

REM Kill any existing Flask/Python processes on port 5000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    echo      Killing process on port 5000 (PID: %%a)
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill any existing Cloudflare tunnel
taskkill /IM cloudflared.exe /F >nul 2>&1

REM Wait to ensure ports are released
timeout /t 2 /nobreak >nul

echo [2/4] Starting Flask Server...
echo.

REM Start Flask server in new window
start "Flask Server" cmd /k "cd /d %~dp0 && python app.py"

REM Wait for server to start
timeout /t 5 /nobreak >nul

echo [3/4] Starting Cloudflare Tunnel...
echo.

REM Start Cloudflare Tunnel in new window
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:5000"

echo [4/4] System is starting...
echo.
echo ========================================
echo   IMPORTANT INSTRUCTIONS
echo ========================================
echo.
echo Two terminal windows have been opened:
echo.
echo   1. Flask Server (Terminal 1)
echo      - Running on http://localhost:5000
echo.
echo   2. Cloudflare Tunnel (Terminal 2)
echo      - Wait 10-15 seconds
echo      - Look for URL: https://xxxxx.trycloudflare.com
echo      - Copy and share that URL!
echo.
echo ========================================
echo.
echo Press any key to close this window...
pause >nul
