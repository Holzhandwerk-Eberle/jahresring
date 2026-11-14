//go:build windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

var messageBox = syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")

func box(text string, flags uintptr) uintptr {
	t, _ := syscall.UTF16PtrFromString(text)
	k, _ := syscall.UTF16PtrFromString("Jahresring installieren")
	r, _, _ := messageBox.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(k)), flags|0x10000) // im Vordergrund
	return r
}

func frage(text string) bool { return box(text, 0x24) == 6 } // Ja/Nein mit Fragezeichen

func meldung(text string, fehler bool) {
	if fehler {
		box(text, 0x10)
	} else {
		box(text, 0x40)
	}
}

func heimOrdner() string {
	if h := os.Getenv("USERPROFILE"); h != "" {
		return h
	}
	h, _ := os.UserHomeDir()
	return h
}

func merkDatei() string { return filepath.Join(os.Getenv("APPDATA"), "Jahresring", "ordner.txt") }

func versteckt(name string, arg ...string) *exec.Cmd {
	c := exec.Command(name, arg...)
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return c
}

// verknuepfungen legt „Jahresring“ auf dem Desktop und im Startmenü an (wie einrichten.bat).
func verknuepfungen(ziel string) error {
	o := strings.ReplaceAll(ziel, "'", "''")
	ps := "$o='" + o + "'; foreach($n in 'Desktop','Programs'){ $d=[Environment]::GetFolderPath($n); " +
		"$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Jahresring.lnk')); $s.TargetPath=(Join-Path $o 'start.bat'); " +
		"$s.WorkingDirectory=$o; $s.WindowStyle=7; $s.IconLocation=(Join-Path $o 'static\\jahresring.ico'); $s.Description='Jahresring'; $s.Save() }"
	aus, err := versteckt("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps).CombinedOutput()
	logf("Verknüpfungen: %s", strings.TrimSpace(string(aus)))
	return err
}

func starten(ziel string) error {
	// start.bat in einem eigenen Konsolenfenster ausführen (dort ist beim ersten Mal die Python-Einrichtung zu sehen).
	// Die Befehlszeile wird wörtlich übergeben: „start“ würde das erste Wort sonst als Programmnamen deuten,
	// und Pfade mit Leerzeichen brauchen bei cmd /c die doppelten Anführungszeichen.
	c := exec.Command("cmd.exe")
	c.Dir = ziel
	c.SysProcAttr = &syscall.SysProcAttr{
		CmdLine:       `cmd.exe /c ""` + filepath.Join(ziel, "start.bat") + `""`,
		CreationFlags: 0x00000010, // CREATE_NEW_CONSOLE
	}
	return c.Start()
}

// ordnerWaehlen zeigt den Windows-Dialog „Ordner suchen“; leer = abgebrochen.
func ordnerWaehlen(titel string) string {
	ps := "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $f=(New-Object -ComObject Shell.Application).BrowseForFolder(0,'" +
		strings.ReplaceAll(titel, "'", "''") + "',0x51,17); if($f){ $f.Self.Path }"
	aus, err := versteckt("powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", ps).Output()
	logf("Ordnerwahl: %q %v", strings.TrimSpace(string(aus)), err)
	return strings.TrimSpace(string(aus))
}

func standardOrdner() string {
	lw := os.Getenv("SystemDrive")
	if lw == "" {
		lw = "C:"
	}
	return lw + `\Jahresring`
}

const fwRegel = "Jahresring Ports 8765-8767"

// firewallVorhanden: gibt es schon eine Jahresring-Freigabe (von diesem Setup oder von Handy-Freigabe.bat)? Lesen geht ohne Administratorrechte.
func firewallVorhanden() bool {
	aus, _ := versteckt("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
		"if(Get-NetFirewallRule -DisplayName 'Jahresring*' -ErrorAction SilentlyContinue){'ja'}").Output()
	return strings.Contains(string(aus), "ja")
}

// firewallFreigeben öffnet die Ports für private Netzwerke. Das braucht Administratorrechte: Windows zeigt dafür seine
// Sicherheitsabfrage. Liefert die Netzwerkprofile dieses PCs (z. B. "WLAN=Private").
func firewallFreigeben() (string, error) {
	ordner := os.TempDir()
	skript, ergebnis := filepath.Join(ordner, "Jahresring-Firewall.ps1"), filepath.Join(ordner, "Jahresring-Firewall.txt")
	os.Remove(ergebnis)
	q := func(p string) string { return strings.ReplaceAll(p, "'", "''") }
	ps := "$ErrorActionPreference='Stop'\r\n" +
		"try {\r\n" +
		"  Get-NetFirewallRule -DisplayName 'Jahresring Port*','Jahresring https' -ErrorAction SilentlyContinue | Remove-NetFirewallRule\r\n" +
		"  New-NetFirewallRule -DisplayName '" + fwRegel + "' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765,8766,8767 -Profile Private,Domain | Out-Null\r\n" +
		"  $p = (Get-NetConnectionProfile | ForEach-Object { $_.InterfaceAlias + '=' + $_.NetworkCategory }) -join '; '\r\n" +
		"  Set-Content -LiteralPath '" + q(ergebnis) + "' -Value ('OK ' + $p) -Encoding UTF8\r\n" +
		"} catch { Set-Content -LiteralPath '" + q(ergebnis) + "' -Value ('FEHLER ' + $_.Exception.Message) -Encoding UTF8 }\r\n"
	if err := os.WriteFile(skript, append([]byte{0xEF, 0xBB, 0xBF}, []byte(ps)...), 0o644); err != nil {
		return "", err
	}
	defer os.Remove(skript)
	start := "Start-Process -FilePath powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"" + q(skript) + "\"'"
	aus, err := versteckt("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", start).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("%v %s", err, strings.TrimSpace(string(aus)))
	}
	b, err := os.ReadFile(ergebnis)
	os.Remove(ergebnis)
	if err != nil {
		return "", fmt.Errorf("kein Ergebnis: %v", err)
	}
	t := strings.TrimSpace(strings.TrimPrefix(string(b), "\xef\xbb\xbf"))
	if !strings.HasPrefix(t, "OK") {
		return "", fmt.Errorf("%s", t)
	}
	return strings.TrimSpace(strings.TrimPrefix(t, "OK")), nil
}
