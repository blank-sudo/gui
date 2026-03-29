@echo off
setlocal

REM Run in script directory
cd /d "%~dp0"

set SCRIPT=serial_voltage_gui.py
set APP_NAME=SerialVoltageGUI

if not exist "%SCRIPT%" (
  echo [ERROR] %SCRIPT% not found in current folder.
  echo Put build_exe.bat and serial_voltage_gui.py in the same folder.
  pause
  exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
  set PY=py
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set PY=python
  ) else (
    echo [ERROR] Python launcher not found.
    echo Install Python 3.10+ and enable PATH.
    pause
    exit /b 1
  )
)

echo [1/4] Upgrade pip...
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [2/4] Install pyinstaller...
%PY% -m pip install pyinstaller
if errorlevel 1 goto :fail

echo [3/4] Install dependencies...
if exist requirements.txt (
  %PY% -m pip install -r requirements.txt
) else (
  %PY% -m pip install pyserial matplotlib
)
if errorlevel 1 goto :fail

echo [4/4] Build EXE...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name %APP_NAME% "%SCRIPT%"
if errorlevel 1 goto :fail

echo.
echo [OK] Build done.
echo EXE: %cd%\dist\%APP_NAME%.exe
pause
exit /b 0

:fail
echo.
echo [ERROR] Build failed. Check logs above.
pause
exit /b 1
