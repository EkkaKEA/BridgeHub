@echo off
title BridgeHub - DuckDB
set "DB_PATH=%~dp0bridgehub.duckdb"
set "DUCKDB=%~dp0bin\duckdb.exe"

if not exist "%DUCKDB%" (
    echo DuckDB not found: %DUCKDB%
    pause
    exit /b 1
)

if not exist "%DB_PATH%" (
    echo Database not found: %DB_PATH%
    pause
    exit /b 1
)

"%DUCKDB%" "%DB_PATH%"
pause
