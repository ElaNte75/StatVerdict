@echo off
title StatVerdict Ship (no version bump)
cd /d "C:\Users\ElaNte\Desktop\Projects\StatVerdict\StatVerdict"
echo.
echo StatVerdict Ship - NO version bump
echo - Keeps the version in StatVerdict.toc as it is
echo - Creates StatVerdict-x.y.z.zip on Desktop
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\ship.ps1" -SkipBump
echo.
if errorlevel 1 (
  echo FAILED. Check the messages above.
) else (
  echo OK. Check your Desktop for StatVerdict-*.zip
)
echo.
pause
