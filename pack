@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ============================================
echo   SerialVoltageGUI EXE 一键打包脚本
echo ============================================

REM 切换到 bat 所在目录
cd /d "%~dp0"

set "SCRIPT=serial_voltage_gui.py"
if not exist "%SCRIPT%" (
  echo [错误] 当前目录未找到 %SCRIPT%
  echo 请把本 bat 文件和 serial_voltage_gui.py 放在同一个文件夹后重试。
  pause
  exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PY=python"
  ) else (
    echo [错误] 未检测到 Python（py/python）。
    echo 请先安装 Python 3.10+，并勾选 Add Python to PATH。
    pause
    exit /b 1
  )
)

echo [1/4] 升级 pip...
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [2/4] 安装打包依赖 pyinstaller...
%PY% -m pip install pyinstaller
if errorlevel 1 goto :fail

echo [3/4] 安装运行依赖...
if exist requirements.txt (
  %PY% -m pip install -r requirements.txt
) else (
  echo [提示] 未找到 requirements.txt，尝试安装最小依赖...
  %PY% -m pip install pyserial matplotlib
)
if errorlevel 1 goto :fail

echo [4/4] 开始打包 EXE...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name SerialVoltageGUI "%SCRIPT%"
if errorlevel 1 goto :fail

echo.
echo [完成] 打包成功！
echo EXE 路径：%cd%\dist\SerialVoltageGUI.exe
echo 你可以直接双击该 EXE 运行。
pause
exit /b 0

:fail
echo.
echo [失败] 打包过程中发生错误，请检查上方日志。
pause
exit /b 1
