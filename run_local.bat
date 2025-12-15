@echo off
echo ========================================
echo   Telegram Store Bot - Local Development
echo ========================================
echo.

REM Check if ngrok is running
tasklist /FI "IMAGENAME eq ngrok.exe" 2>NUL | find /I /N "ngrok.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Ngrok is already running
) else (
    echo [INFO] Starting ngrok on port 5000...
    start "" ngrok http 5000
    echo [INFO] Waiting for ngrok to start...
    timeout /t 5 /nobreak >nul
)

echo.
echo [INFO] Getting ngrok URL...
for /f "tokens=*" %%a in ('curl -s http://localhost:4040/api/tunnels ^| findstr "https://"') do set NGROK_OUTPUT=%%a

echo.
echo ========================================
echo   IMPORTANT: Copy the ngrok HTTPS URL
echo   from the ngrok window and update
echo   config.env with NGROK_HTTPS_URL=...
echo ========================================
echo.

echo [INFO] Starting bot...
python store_main.py

pause
