@echo off
setlocal

REM ========================================================
REM Build Script Wrapper
REM ========================================================

echo Checking environment...

REM 1. Check for local virtual environment
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Found local .venv, using it...
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo [WARN] .venv not found, trying system python...
    set "PYTHON_EXE=python"
)

REM 2. Verify Python
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python interpreter not found!
    echo Please install Python or check your PATH.
    pause
    exit /b
)

REM 3. Print Python info
echo [INFO] Using Python executable:
"%PYTHON_EXE%" -c "import sys; print(sys.executable)"

REM 4. Run the build script
echo.
echo [INFO] Starting build process...
"%PYTHON_EXE%" scripts/build.py

echo.
if errorlevel 1 (
    echo [ERROR] Build failed.
) else (
    echo [SUCCESS] Build finished successfully.
)

echo.
echo Press any key to exit...
pause