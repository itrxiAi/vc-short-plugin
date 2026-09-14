@echo off
rem vcshort portable launcher (Windows cmd) - uses bundled Python runtime
setlocal
set "ROOT=%~dp0.."
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ROOT%\src;%PYTHONPATH%"
"%ROOT%\python\python.exe" "%ROOT%\src\vcshort\__main__.py" %*
endlocal & exit /b %ERRORLEVEL%
