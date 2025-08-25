@@echo off
setlocal

rem === настройки ===
set "PYVER=3.12.6"
set "PYDIR=%~dp0py"   rem целевая папка (без завершающего \)
set "ZIP=%~dp0python-%PYVER%-embed-win32.zip"
set "GETPIP=%TEMP%\get-pip.py"

rem === подготовка каталога ===
mkdir "%PYDIR%" 2>nul

rem === скачать embeddable ZIP (если ещё не скачан) ===
if not exist "%ZIP%" (
  echo Downloading %ZIP% ...
  curl -L -o "%ZIP%" "https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-win32.zip" || goto :err
)

rem === распаковать ===
tar -xf "%ZIP%" -C "%PYDIR%" || goto :err

rem === включить import site (раскомментировать в python312._pth) ===

> "%PYDIR%\python312._pth"  echo python312.zip
>>"%PYDIR%\python312._pth"  echo .
>>"%PYDIR%\python312._pth"  echo import site

rem === скачать bootstrap для pip ===
echo Downloading get-pip.py ...
curl -L -o "%GETPIP%" "https://bootstrap.pypa.io/get-pip.py" || goto :err

rem === установить pip внутрь embeddable-папки ===
"%PYDIR%\python.exe" "%GETPIP%" --no-warn-script-location || goto :err

rem === проверка ===
"%PYDIR%\python.exe" -m pip --version || goto :err

echo.
echo OK: pip install.

"%PYDIR%\python.exe" -m pip install --upgrade pip   
"%PYDIR%\python.exe" -m pip  install python-telegram-bot
"%PYDIR%\python.exe" -V
goto :end

:err
echo.
echo ERROR: что-то пошло не так. Проверь сообщения выше.
exit /b 1

:end
endlocal


