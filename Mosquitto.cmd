@echo off
set MOSQUITTO=C:\Program Files\mosquitto\mosquitto.exe

if not exist "%MOSQUITTO%" (
    echo Mosquitto не найден: %MOSQUITTO%
    pause
    exit /b 1
)

REM Попытка запустить как сервис Windows
net start mosquitto 2>nul
if %errorlevel% equ 0 (
    echo Mosquitto service started.
    goto :check
)

REM Если сервис не запущен — запустить вручную (в отдельном окне)
echo Starting Mosquitto...
start "Mosquitto" "%MOSQUITTO%"
timeout /t 2 >nul

:check
REM Проверка порта 1883
netstat -ano | findstr ":1883" >nul 2>&1
if %errorlevel% equ 0 (
    echo Mosquitto is running on port 1883.
) else (
    echo Failed to start Mosquitto.
    pause
)
