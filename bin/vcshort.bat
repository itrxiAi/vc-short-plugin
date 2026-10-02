@echo off
rem vcshort launcher (Windows cmd) - uses system Python
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ROOT%\src;%PYTHONPATH%"

for %%P in (python.exe python3.exe) do (
    if not "%%~f$PATH:P"=="" (
        set "PY=%%~f$PATH:P"
        goto :found
    )
)

echo 错误：未找到系统 Python。请安装 Python 3.10+（https://www.python.org/downloads/）
echo 安装后请运行：pip install -r "%ROOT%\requirements.txt"
exit /b 1

:found
"%PY%" "%ROOT%\src\vcshort\__main__.py" %*
endlocal & exit /b %ERRORLEVEL%
