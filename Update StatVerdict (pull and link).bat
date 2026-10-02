@echo off
setlocal
title StatVerdict - update and link
rem ---------------------------------------------------------------
rem  What this does, in plain words:
rem  1) Downloads the latest StatVerdict code from GitHub (git pull).
rem  2) The first time only: links the WoW AddOns folder to this project,
rem     so the game always reads the project folder directly.
rem  After that you only run this file, then type /reload in the game.
rem
rem  If your WoW is installed somewhere else, change the line below.
rem ---------------------------------------------------------------
set "PROJECT=C:\Users\ElaNte\Desktop\Projects\StatVerdict"
set "ADDONS=C:\Program Files (x86)\World of Warcraft\_retail_\Interface\AddOns"

cd /d "%PROJECT%" || (echo Cannot find %PROJECT% & pause & exit /b 1)

echo.
echo === 1/2  Getting the latest code ===
git pull origin main
if errorlevel 1 (
  echo.
  echo git pull FAILED. Is git installed, and is this the cloned project folder?
  pause
  exit /b 1
)

echo.
echo === 2/2  Linking the AddOns folder ===
if not exist "%ADDONS%" (
  echo Cannot find the AddOns folder:
  echo   %ADDONS%
  echo Open this file in Notepad and fix the ADDONS line.
  pause
  exit /b 1
)

dir /AL "%ADDONS%" 2>nul | findstr /I "StatVerdict" >nul
if not errorlevel 1 (
  echo Already linked. Nothing to do.
  goto done
)

if exist "%ADDONS%\StatVerdict" (
  echo Found an installed StatVerdict folder; renaming it to StatVerdict_old first.
  if exist "%ADDONS%\StatVerdict_old" rmdir /S /Q "%ADDONS%\StatVerdict_old"
  ren "%ADDONS%\StatVerdict" StatVerdict_old
)
mklink /J "%ADDONS%\StatVerdict" "%PROJECT%\StatVerdict"
if errorlevel 1 (
  echo.
  echo Linking failed. Try again with "Run as administrator".
  pause
  exit /b 1
)
echo Linked. Remember to delete StatVerdict_old later (it must not stay in AddOns, or the game loads it twice).

:done
echo.
echo OK. Now in the game type /reload
echo.
pause
