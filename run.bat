@echo off
REM ─────────────────────────────────────────────────────
REM  run.bat  —  Start the DNS Resolution Service
REM  Launches:  1) Flask REST API   2) Web dashboard
REM ─────────────────────────────────────────────────────

setlocal
set BINARY=core\dns_resolver.exe
set API=api\server.py
set WEB=http://127.0.0.1:5000/

echo.
echo  ██████╗ ███╗   ██╗███████╗     ██████╗ ██████╗ ██████╗ ███████╗
echo  ██╔══██╗████╗  ██║██╔════╝    ██╔════╝██╔═══██╗██╔══██╗██╔════╝
echo  ██║  ██║██╔██╗ ██║███████╗    ██║     ██║   ██║██████╔╝█████╗
echo  ██║  ██║██║╚██╗██║╚════██║    ██║     ██║   ██║██╔══██╗██╔══╝
echo  ██████╔╝██║ ╚████║███████║    ╚██████╗╚██████╔╝██║  ██║███████╗
echo  ╚═════╝ ╚═╝  ╚═══╝╚══════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
echo.
echo  RFC 1035 DNS Resolver  —  C++ Engine + Python API
echo ────────────────────────────────────────────────────

REM Check binary exists
if not exist "%BINARY%" (
    echo.
    echo  [!] C++ binary not found.  Building...
    call build.bat
    if %errorlevel% neq 0 (
        echo  Build failed. Exiting.
        exit /b 1
    )
)

echo.
echo  [1/2] Starting Flask API on http://127.0.0.1:5000 ...
start "DNS API" cmd /k "python %API%"

REM Small delay to let Flask start
timeout /t 2 /nobreak >nul

echo  [2/2] Opening web dashboard ...
start "" "%WEB%"

echo.
echo  ✓ DNS Resolution Service is running.
echo.
echo  API   →  http://127.0.0.1:5000/resolve?domain=google.com^&type=A
echo  Cache →  http://127.0.0.1:5000/cache
echo  Tests →  python -m pytest tests/ -v
echo.
echo  Press any key to stop all services.
pause >nul

REM Kill spawned processes
taskkill /FI "WindowTitle eq DNS API" /F >nul 2>&1
echo Services stopped.
