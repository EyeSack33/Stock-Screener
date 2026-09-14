@echo off
REM Double-click this file to start the screener on Windows.
REM The first run takes a couple of minutes while it installs things.

cd /d "%~dp0"

echo ===================================================
echo   Dip Screener
echo ===================================================
echo.

REM Find a working Python
set PY=
where python >nul 2>&1 && set PY=python
if "%PY%"=="" where py >nul 2>&1 && set PY=py

if "%PY%"=="" (
    echo Python is not installed, or it was installed without
    echo "Add Python to PATH" ticked.
    echo.
    echo Download it from https://www.python.org/downloads/
    echo During setup, TICK the box that says "Add Python to PATH".
    echo Then double-click this file again.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Using %%v
echo.

REM Install the packages only if they are missing
%PY% -c "import flask, yfinance, yaml" >nul 2>&1
if errorlevel 1 (
    echo First run: installing Flask and yfinance. This takes a minute...
    echo.
    %PY% -m pip install --quiet --upgrade pip
    %PY% -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo.
        echo The install failed. Check your internet connection.
        pause
        exit /b 1
    )
    echo Done installing.
    echo.
)

REM Open the browser shortly after the server starts
start "" /b cmd /c "timeout /t 4 >nul & start http://localhost:8000"

echo Starting up. Your browser will open by itself.
echo The page says "Scanning the market" for up to a minute - that is normal.
echo.
echo To stop: close this window, or press Control+C.
echo.

%PY% serve.py

echo.
echo Stopped.
pause
