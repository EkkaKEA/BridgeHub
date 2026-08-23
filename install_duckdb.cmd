@echo off
setlocal

set "DUCKDB_VERSION=1.1.3"
set "DUCKDB_URL=https://github.com/duckdb/duckdb/releases/download/v%DUCKDB_VERSION%/duckdb_cli-windows-amd64.zip"
set "ZIP_FILE=%~dp0duckdb_cli.zip"
set "INSTALL_DIR=%~dp0bin"

echo ===================================
echo  Installing DuckDB v%DUCKDB_VERSION%
echo ===================================
echo.

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo Downloading DuckDB CLI...
powershell -Command "Invoke-WebRequest -Uri '%DUCKDB_URL%' -OutFile '%ZIP_FILE%'"

if %errorlevel% neq 0 (
    echo ERROR: Download failed.
    pause
    exit /b 1
)

echo Extracting...
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%INSTALL_DIR%' -Force"

if %errorlevel% neq 0 (
    echo ERROR: Extraction failed.
    pause
    exit /b 1
)

del "%ZIP_FILE%" 2>nul

echo.
echo Adding to PATH for current session...
set "PATH=%INSTALL_DIR%;%PATH%"

echo.
echo Verifying installation...
"%INSTALL_DIR%\duckdb.exe" --version

if %errorlevel% neq 0 (
    echo ERROR: DuckDB not found in %INSTALL_DIR%
    pause
    exit /b 1
)

echo.
echo ===================================
echo  DuckDB installed successfully!
echo ===================================
echo.
echo  Binary: %INSTALL_DIR%\duckdb.exe
echo  Database files will be created in: %~dp0
echo.
echo  To create a database, run:
echo    %INSTALL_DIR%\duckdb.exe bridgehub.duckdb
echo.
echo  To add DuckDB to PATH permanently, run:
echo    setx PATH "%%PATH%%;%INSTALL_DIR%"
echo.

pause
