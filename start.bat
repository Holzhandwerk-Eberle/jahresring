@echo off
chcp 65001 >NUL
cd /d "%~dp0"
title Jahresring

rem --- 1. Funktioniert Python schon? ---
call :pruefen
if defined PY goto starten

echo.
echo  Python fehlt noch und wird jetzt einmalig eingerichtet.
echo  Das dauert ein bis zwei Minuten. Bitte warten ...
echo.

rem --- 2. Versuch ueber den Python-Installationsmanager ---
where py >NUL 2>NUL
if not errorlevel 1 (
  set "PYTHON_MANAGER_CONFIRM=false"
  py install default
  call :pruefen
  if defined PY goto fertig
)

rem --- 3. Versuch ueber winget (in Windows 10/11 enthalten) ---
where winget >NUL 2>NUL
if not errorlevel 1 (
  winget install --id Python.Python.3.13 -e --silent --accept-package-agreements --accept-source-agreements
  call :pruefen
  if defined PY goto fertig
  if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto fertig
  )
)

rem --- 4. Versuch: Installationsprogramm direkt von python.org laden (nur fuer dieses Benutzerkonto, ohne Administratorrechte) ---
echo  Python wird von python.org geladen ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; $f=Join-Path $env:TEMP 'python-3.13-setup.exe'; Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe' -OutFile $f; Start-Process -FilePath $f -ArgumentList '/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Shortcuts=0' -Wait"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
  set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  goto fertig
)

echo.
echo  Python konnte nicht automatisch eingerichtet werden.
echo  Bitte Python 3.12 oder neuer von python.org installieren und Jahresring erneut starten.
echo.
pause
exit /b 1

:fertig
echo.
echo  Python ist eingerichtet.
echo.

:starten
rem Das Programm wechselt selbst in den Hintergrund (ohne Fenster).
rem Mit "start.bat konsole" bleibt das Fenster zur Fehlersuche offen.
if /i "%~1"=="konsole" ("%PY%" app.py --konsole) else if /i "%~1"=="kein-browser" ("%PY%" app.py --kein-browser) else ("%PY%" app.py)
if errorlevel 1 pause
exit /b 0

rem --- Hilfsroutine: findet ein funktionierendes Python ---
:pruefen
set "PY="
for %%P in (py python) do (
  if not defined PY (
    %%P -c "import sqlite3" >NUL 2>NUL && set "PY=%%P"
  )
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
rem Echte python.exe statt App-Alias (WindowsApps) verwenden - sonst kommen Handys im WLAN nicht durch
if defined PY (
  for /f "usebackq delims=" %%X in (`%PY% -c "import sys,os;print(os.path.realpath(getattr(sys,'_base_executable',None) or sys.executable))"`) do set "PYECHT=%%X"
)
if defined PYECHT (
  echo %PYECHT% | findstr /i "WindowsApps" >NUL || set "PY=%PYECHT%"
)
if defined PY (
  echo %PY% | findstr /i "WindowsApps" >NUL && for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
)
exit /b 0
