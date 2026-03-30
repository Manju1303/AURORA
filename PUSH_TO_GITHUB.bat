@echo off
echo.
echo ======================================================
echo    🌌 AURORA v4.0 — GitHub Sync Script
echo ======================================================
echo.

:: 0. Check if it's already a git repository
if not exist ".git" (
    echo [+] Repository not initialized. Connecting to GitHub...
    git init
    git remote add origin https://github.com/Manju1303/AURORA
    git branch -M main
    echo [+] Remote origin set to https://github.com/Manju1303/AURORA
)

:: 1. Add all changes
echo [+] Staging local v4.0 updates...
git add .

:: 2. Prompt for commit
echo [+] Preparing v4.0 Autonomous Personality commit...
git commit -m "AURORA v4.0 ✨: Autonomous Personality, SQLite Memory, and UI Minimalism"

:: 3. Push to Main
echo [+] Pushing to main branch at https://github.com/Manju1303/AURORA...
git push -u origin main --force

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ SUCCESS: Your repository is now updated to AURORA v4.0!
) else (
    echo.
    echo ❌ ERROR: Push failed. Check your internet connection or git permissions.
)

echo.
pause
