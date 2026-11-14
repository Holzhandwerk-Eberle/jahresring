# Jahresring: Windows-Firewall fuer Handys im WLAN einrichten und pruefen
$port = 8765
Write-Host ""
Write-Host "=== 1. Programm ===" -ForegroundColor Cyan
$alle = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
$exe = $null
if (-not $alle) { Write-Host "  Jahresring laeuft gerade nicht. Bitte starten und diese Datei noch einmal ausfuehren." -ForegroundColor Yellow }
foreach ($c in $alle) {
  $pr = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $c.OwningProcess) -ErrorAction SilentlyContinue
  $pfad = if ($pr) { $pr.ExecutablePath } else { "(unbekannt)" }
  if ($pr -and $pr.ExecutablePath -match 'python') { $exe = $pr.ExecutablePath }
  Write-Host ("  " + $c.LocalAddress + ":" + $port + "  Prozess " + $c.OwningProcess + "  " + $pfad)
}
$pids = @($alle | Select-Object -ExpandProperty OwningProcess -Unique)
if ($pids.Count -gt 1) {
  Write-Host ""
  Write-Host "  Das Programm laeuft MEHRFACH gleichzeitig (" $pids.Count "mal). Dann landen Anfragen mal beim einen, mal beim anderen." -ForegroundColor Red
  $a = Read-Host "  Alle beenden? Danach Jahresring einmal neu starten (J/N)"
  if ($a -match '^[jJyY]') { $pids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }; Write-Host "  beendet - jetzt Jahresring neu starten und diese Datei noch einmal ausfuehren." -ForegroundColor Yellow; $alle = @() }
} elseif ($alle) {
  if ($alle | Where-Object { $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' }) { Write-Host "  im Netzwerk erreichbar: ja" -ForegroundColor Green }
  else { Write-Host "  im Netzwerk erreichbar: NEIN - Einstellungen > Benutzer & Netzwerk: Haken setzen, Programm beenden und neu starten." -ForegroundColor Red }
}

Write-Host ""
Write-Host "=== 2. Netzwerkprofil (muss Private sein) ===" -ForegroundColor Cyan
Get-NetConnectionProfile | ForEach-Object { Write-Host ("  " + $_.InterfaceAlias + ": " + $_.NetworkCategory) }

Write-Host ""
Write-Host "=== 3. Sperr-Regeln entfernen ===" -ForegroundColor Cyan
$block = Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True -ErrorAction SilentlyContinue | Where-Object {
  $f = $_ | Get-NetFirewallApplicationFilter; $p = $_ | Get-NetFirewallPortFilter
  ($f.Program -match 'python') -or ($exe -and $f.Program -eq $exe) -or ($p.LocalPort -contains "$port")
}
if ($block) { $block | ForEach-Object { Write-Host ("  entfernt: " + $_.DisplayName + " (" + $_.Profile + ")") -ForegroundColor Yellow }; $block | Remove-NetFirewallRule }
else { Write-Host "  keine gefunden" }

Write-Host ""
Write-Host "=== 4. Freigaben anlegen ===" -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName 'Jahresring*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'Jahresring Port 8765' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -Profile Private,Domain | Out-Null
Write-Host "  Port $port fuer private Netzwerke freigegeben"
Get-NetFirewallRule -DisplayName 'Jahresring https' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'Jahresring https' -Direction Inbound -Action Allow -Protocol TCP -LocalPort ($port + 1),($port + 2) -Profile Private,Domain | Out-Null
Write-Host ("  Ports " + ($port + 1) + " und " + ($port + 2) + " (https, Stempeluhr) fuer private Netzwerke freigegeben")
if ($exe) {
  New-NetFirewallRule -DisplayName 'Jahresring Programm' -Direction Inbound -Action Allow -Program $exe -Profile Private,Domain | Out-Null
  Write-Host "  Programm freigegeben: $exe"
}

Write-Host ""
Write-Host "=== 5. Andere Firewall-Programme ===" -ForegroundColor Cyan
$fw = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName FirewallProduct -ErrorAction SilentlyContinue
if ($fw) { $fw | ForEach-Object { Write-Host ("  " + $_.displayName + "  <- blockiert unabhaengig von Windows; dort Port $port freigeben") -ForegroundColor Yellow } }
else { Write-Host "  keine (nur Windows-Firewall)" }

Write-Host ""
Write-Host "=== 6. Adresse fuers Handy ===" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker|VirtualBox|VMware' } |
  ForEach-Object { Write-Host ("  http://" + $_.IPAddress + ":$port/stempel   (" + $_.InterfaceAlias + ")") -ForegroundColor Green }
Write-Host ""
