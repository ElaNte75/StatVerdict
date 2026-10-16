@echo off
title StatVerdict Ship
cd /d "%~dp0StatVerdict"
echo.
echo StatVerdict Ship
echo - Bumps version
echo - Creates StatVerdict-x.y.z.zip on Desktop
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\ship.ps1"
echo.
if errorlevel 1 (
  echo FAILED. Check the messages above.
) else (
  echo OK. Check your Desktop for StatVerdict-*.zip
)
echo.
pause
