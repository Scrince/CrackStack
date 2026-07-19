@echo off
setlocal

set "HARNESS_ROOT=%~dp0"
set "PYTHON_EXE=%HARNESS_ROOT%runtime\python\windows-x64\python.exe"
set "CRACKSTACK_ROOT=%HARNESS_ROOT%"
set "PYTHONPATH=%HARNESS_ROOT%;%HARNESS_ROOT%runtime\site-packages\windows-x64"
set "PATH=%HARNESS_ROOT%runtime\python\windows-x64;%HARNESS_ROOT%runtime\python\windows-x64\Scripts;%PATH%"

if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" -m harness.cli %*
  exit /b %ERRORLEVEL%
)

echo Bundled Windows x64 Python was not found at:
echo   %PYTHON_EXE%
echo Falling back to host Python for development only.
py -3 -m harness.cli %*
exit /b %ERRORLEVEL%
