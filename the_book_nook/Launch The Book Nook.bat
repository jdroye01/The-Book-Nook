@echo off
REM Double-click this file in File Explorer to launch The Book Nook.
REM (If Windows shows a "Windows protected your PC" prompt the first time,
REM click "More info" then "Run anyway" -- this is normal for any script
REM that isn't digitally signed, and only appears once.)

cd /d "%~dp0"

where python >nul 2>nul
if not errorlevel 1 goto foundpython
where py >nul 2>nul
if not errorlevel 1 goto foundpy

echo Python was not found on this computer.
echo Install it from https://www.python.org/downloads/
echo and make sure to check "Add Python to PATH" during setup.
pause
exit /b 1

:foundpython
set PYCMD=python
goto run

:foundpy
set PYCMD=py
goto run

:run
REM Make sure dependencies are installed. Fast/no-op once already present,
REM so it's safe to leave in for every launch. The second attempt covers
REM Python installs (e.g. from the Microsoft Store) that restrict plain
REM pip installs by default.
%PYCMD% -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 %PYCMD% -m pip install -r requirements.txt --quiet --disable-pip-version-check --break-system-packages

%PYCMD% main.py
if errorlevel 1 (
    echo.
    echo The Book Nook closed with an error ^(see above^).
    pause
)
