@echo off
rem TachRang.bat — chạy giao diện Tách Răng CBCT bằng 1 cú double-click
rem Thứ tự tìm Python: biến TACHRANG_PYTHON -> .venv (nếu đã cài đủ thư viện) -> pythonw trong PATH
cd /d "%~dp0"
set PY=%TACHRANG_PYTHON%
if "%PY%"=="" if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import PySide6, vtk, SimpleITK" >nul 2>&1 && set PY=.venv\Scripts\pythonw.exe
)
if "%PY%"=="" set PY=pythonw
start "" "%PY%" -m tachrang
