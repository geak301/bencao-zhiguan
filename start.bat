@echo off
rem BenCao ZhiGuan Platform - Launcher (ASCII only to avoid codepage issues)
cd /d "%~dp0backend"
echo ============================================
echo   BenCao ZhiGuan Platform
echo   URL: http://127.0.0.1:5000
echo   First run: python init_db.py
echo   Ctrl+C to stop
echo ============================================
python app.py
pause
