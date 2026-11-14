@echo off
chcp 65001 >NUL
cd /d "%~dp0"
title Jahresring einrichten
echo.
echo  1. Programmdateien freigeben (keine "Ausfuehren"-Abfrage mehr) ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0.' -Recurse -File | Unblock-File"
echo  2. Verknuepfung "Jahresring" auf dem Desktop anlegen ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$o='%~dp0.'; $d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Jahresring.lnk')); $s.TargetPath=(Join-Path $o 'start.bat'); $s.WorkingDirectory=$o; $s.WindowStyle=7; $s.IconLocation=(Join-Path $o 'static\jahresring.ico'); $s.Description='Jahresring'; $s.Save()"
echo  3. Verknuepfung auch im Startmenue anlegen ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$o='%~dp0.'; $d=[Environment]::GetFolderPath('Programs'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Jahresring.lnk')); $s.TargetPath=(Join-Path $o 'start.bat'); $s.WorkingDirectory=$o; $s.WindowStyle=7; $s.IconLocation=(Join-Path $o 'static\jahresring.ico'); $s.Description='Jahresring'; $s.Save()"
echo.
echo  Fertig. Ab jetzt startest du das Programm ueber "Jahresring" auf dem Desktop.
echo  Nach einem Update diese Datei einfach noch einmal doppelklicken.
echo.
pause
