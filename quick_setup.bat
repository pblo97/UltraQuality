@echo off
REM Quick setup script for UltraQuality screener (Windows)

echo ==================================
echo UltraQuality Screener - Quick Setup
echo ==================================
echo.

REM Check Python
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.9+ from python.org
    pause
    exit /b 1
)

echo.
echo Installing dependencies...
pip install -q pandas numpy requests pyyaml scipy python-dotenv
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully!

echo.
echo ==================================
echo Setup complete!
echo ==================================
echo.
echo Next steps:
echo   1. Set your API key:
echo      set FMP_API_KEY=your_key_here
echo.
echo   2. Run the screener:
echo      python run_screener.py
echo.
echo   3. For qualitative analysis:
echo      python run_screener.py --symbol AAPL
echo.
pause
