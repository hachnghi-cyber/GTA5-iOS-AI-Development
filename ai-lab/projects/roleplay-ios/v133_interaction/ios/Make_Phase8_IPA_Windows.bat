@echo off
setlocal EnableExtensions DisableDelayedExpansion
title GTA V iOS v13.3 - Phase8 Startup Probe unsigned IPA
echo.
echo GTA V iOS v13.3 - Local Phase8 Diagnostic IPA
echo No GTA files are uploaded anywhere. Input is checked by SHA-256.
echo.
if "%~1"=="" (
  echo KEO THA file GTAV-v13.3.ipa GOC vao file BAT nay.
  echo Hoac chay: Make_Phase8_IPA_Windows.bat "C:\duongdan\GTAV-v13.3.ipa"
  pause
  exit /b 2
)
if not exist "%~f1" (
  echo ERROR: Khong tim thay IPA nguon: "%~f1"
  pause
  exit /b 2
)
if not exist "%~dp0PoliceRPV133Probe.dylib" (
  echo ERROR: Thieu PoliceRPV133Probe.dylib trong cung thu muc BAT.
  pause
  exit /b 2
)
if not exist "%~dp0patch_exact_v133_probe.py" (
  echo ERROR: Thieu patch_exact_v133_probe.py trong cung thu muc BAT.
  pause
  exit /b 2
)
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Chua cai Python 3. Cai Python 3 roi chay lai.
    pause
    exit /b 2
  )
  set "PYTHON_CMD=python"
)
set "OUTPUT=%~dpn1-Phase8-Probe-UNSIGNED.ipa"
if exist "%OUTPUT%" (
  echo ERROR: File output da ton tai, KHONG ghi de: "%OUTPUT%"
  pause
  exit /b 2
)
%PYTHON_CMD% "%~dp0patch_exact_v133_probe.py" --ipa "%~f1" --bridge "%~dp0PoliceRPV133Probe.dylib" --out "%OUTPUT%" --enable-file-sharing
if errorlevel 1 (
  echo.
  echo BUILD FAILED. IPA goc khong bi sua. Kiem tra SHA-256 va log ben tren.
  pause
  exit /b 1
)
echo.
echo PASS: Da tao file IPA unsigned:
echo "%OUTPUT%"
echo BAT BUOC: Ky lai ca app va dylib bang cung chung chi Apple tren ESign/Sideloadly.
echo Chi la startup probe, KHONG phai Police RP Online.
pause
exit /b 0
