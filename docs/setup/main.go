// Jahresring-Setup: eine einzelne Datei, die das Programm installiert oder aktualisiert.
// Enthält den Programmordner als ZIP. Der Ordner "daten" wird nie angefasst.
package main

import (
	"archive/zip"
	"bytes"
	_ "embed"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

//go:embed payload.zip
var payload []byte

//go:embed version.txt
var version string

var logDatei *os.File

func logf(format string, a ...any) {
	if logDatei != nil {
		fmt.Fprintf(logDatei, time.Now().Format("15:04:05 ")+format+"\r\n", a...)
	}
}

// laeuft prüft, ob auf diesem PC schon ein Jahresring antwortet.
func laeuft() bool {
	c := http.Client{Timeout: 1500 * time.Millisecond}
	r, err := c.Get("http://127.0.0.1:8765/api/version")
	if err != nil {
		return false
	}
	r.Body.Close()
	return r.StatusCode == 200
}

// zielOrdner: Übergabe als Argument > zuletzt benutzter Ordner > Ordner neben der Setup-Datei, wenn dort Jahresring liegt > Benutzerordner\Jahresring.
func zielOrdner() string {
	for _, a := range os.Args[1:] {
		if !strings.HasPrefix(a, "/") && !strings.HasPrefix(a, "-") {
			return a
		}
	}
	if b, err := os.ReadFile(merkDatei()); err == nil {
		o := strings.TrimSpace(strings.TrimPrefix(string(b), "\xef\xbb\xbf"))
		if _, err := os.Stat(filepath.Join(o, "app.py")); err == nil {
			return o
		}
	}
	if exe, err := os.Executable(); err == nil {
		d := filepath.Dir(exe)
		for _, o := range []string{d, filepath.Join(d, "Jahresring")} {
			if _, err := os.Stat(filepath.Join(o, "app.py")); err == nil {
				return o
			}
		}
	}
	// Empfohlener Ort laut Installationsanleitung: C:\Jahresring (nicht in synchronisierten Cloud-Ordnern, nicht unter C:\Programme).
	// Lässt sich dort kein Ordner anlegen, kommt das Programm in den Benutzerordner.
	if std := standardOrdner(); std != "" {
		if err := os.MkdirAll(std, 0o755); err == nil {
			probe := filepath.Join(std, ".schreibtest")
			if os.WriteFile(probe, []byte("x"), 0o644) == nil {
				os.Remove(probe)
				return std
			}
		}
	}
	return filepath.Join(heimOrdner(), "Jahresring")
}

func entpacken(ziel string) (int, error) {
	z, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return 0, err
	}
	n := 0
	for _, f := range z.File {
		name := strings.ReplaceAll(f.Name, "\\", "/")
		if i := strings.Index(name, "/"); i >= 0 && strings.HasPrefix(name, "Jahresring/") {
			name = name[i+1:]
		}
		if name == "" || strings.HasPrefix(name, "daten/") || name == "daten" || strings.Contains(name, "..") {
			continue // eigene Daten bleiben immer unberührt
		}
		pfad := filepath.Join(ziel, filepath.FromSlash(name))
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(pfad, 0o755); err != nil {
				return n, err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(pfad), 0o755); err != nil {
			return n, err
		}
		q, err := f.Open()
		if err != nil {
			return n, err
		}
		tmp := pfad + ".neu"
		w, err := os.Create(tmp)
		if err != nil {
			q.Close()
			return n, fmt.Errorf("%s: %w", name, err)
		}
		_, err = io.Copy(w, q)
		q.Close()
		w.Close()
		if err != nil {
			return n, fmt.Errorf("%s: %w", name, err)
		}
		os.Remove(pfad)
		if err := os.Rename(tmp, pfad); err != nil {
			os.Remove(tmp)
			return n, fmt.Errorf("%s ist gesperrt (läuft Jahresring noch?): %w", name, err)
		}
		n++
	}
	return n, nil
}

// datenQuelle findet in einem gewählten Ordner die Jahresring-Daten: der Ordner selbst, sein Unterordner „daten“ oder „Jahresring\daten“.
func datenQuelle(o string) string {
	for _, k := range []string{o, filepath.Join(o, "daten"), filepath.Join(o, "Jahresring", "daten")} {
		if _, err := os.Stat(filepath.Join(k, "buero.db")); err == nil {
			return k
		}
	}
	return ""
}

func kopieren(von, nach string) (int, error) {
	n := 0
	err := filepath.Walk(von, func(p string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(von, p)
		erste := strings.Split(filepath.ToSlash(rel), "/")[0]
		if erste == "tmp" || erste == "browser-profil" || erste == "zertifikat" {
			if info.IsDir() {
				return filepath.SkipDir // nur auf dem alten PC gültig bzw. Zwischendateien
			}
			return nil
		}
		ziel := filepath.Join(nach, rel)
		if info.IsDir() {
			return os.MkdirAll(ziel, 0o755)
		}
		q, err := os.Open(p)
		if err != nil {
			return err
		}
		defer q.Close()
		w, err := os.Create(ziel)
		if err != nil {
			return err
		}
		if _, err = io.Copy(w, q); err != nil {
			w.Close()
			return err
		}
		n++
		if err = w.Close(); err != nil {
			return err
		}
		return os.Chtimes(ziel, info.ModTime(), info.ModTime())
	})
	return n, err
}

// datenUebernehmen bietet bei einer Neuinstallation an, den Ordner „daten“ vom bisherigen PC (USB-Stick, Netzlaufwerk) zu kopieren.
func datenUebernehmen(ziel string) string {
	zd := filepath.Join(ziel, "daten")
	if _, err := os.Stat(filepath.Join(zd, "buero.db")); err == nil {
		return ""
	}
	if !frage("Sollen die Daten vom bisherigen PC übernommen werden?\n\nDazu wird der Ordner „daten“ aus dem alten Jahresring-Ordner gebraucht, z. B. auf einem USB-Stick " +
		"(auf dem alten PC vorher Jahresring beenden und den ganzen Ordner „Jahresring“ oder nur „daten“ kopieren).\n\n" +
		"Ja = Ordner jetzt auswählen\nNein = ohne Daten starten (lässt sich später nachholen)") {
		return ""
	}
	for {
		o := ordnerWaehlen("Ordner „daten“ oder den alten Ordner „Jahresring“ auswählen")
		if o == "" {
			return ""
		}
		q := datenQuelle(o)
		if q == "" {
			if !frage("In\n" + o + "\nliegen keine Jahresring-Daten (die Datei buero.db fehlt).\n\nAnderen Ordner wählen?") {
				return ""
			}
			continue
		}
		for _, x := range []string{"buero.db-wal", "buero.db-shm"} {
			if _, err := os.Stat(filepath.Join(q, x)); err == nil {
				logf("Hinweis: %s vorhanden – das alte Programm lief beim Kopieren evtl. noch", x)
			}
		}
		n, err := kopieren(q, zd)
		logf("Daten übernommen aus %s: %d Dateien, Fehler: %v", q, n, err)
		if err != nil {
			os.RemoveAll(zd)
			panic(fmt.Sprintf("Die Daten konnten nicht vollständig kopiert werden:\n%v\n\nEs wurde nichts übernommen; die Installation kann wiederholt werden.", err))
		}
		return fmt.Sprintf("%d Dateien aus %s übernommen. Das E-Mail-Passwort und – falls benutzt – das Sicherungskennwort bitte in den Einstellungen neu eingeben; "+
			"sie sind an den alten PC gebunden.\n\n", n, q)
	}
}

func main() {
	logDatei, _ = os.Create(filepath.Join(os.TempDir(), "Jahresring-Setup.log"))
	defer func() {
		if r := recover(); r != nil {
			logf("Abbruch: %v", r)
			meldung(fmt.Sprintf("Die Installation ist abgebrochen:\n\n%v\n\nEinzelheiten: %s", r, filepath.Join(os.TempDir(), "Jahresring-Setup.log")), true)
		}
	}()
	version = strings.TrimSpace(version)
	ziel := zielOrdner()
	_, errAlt := os.Stat(filepath.Join(ziel, "app.py"))
	update := errAlt == nil
	logf("Version %s, Ziel %s, Update %v", version, ziel, update)
	text := fmt.Sprintf("Jahresring %s wird installiert nach\n\n%s\n\nDabei entstehen Verknüpfungen auf dem Desktop und im Startmenü. Fortfahren?", version, ziel)
	if update {
		text = fmt.Sprintf("In\n\n%s\n\nist Jahresring bereits installiert und wird auf Version %s aktualisiert.\nAlle Daten (Ordner „daten“) bleiben unverändert erhalten. Fortfahren?", ziel, version)
	}
	if !frage(text) {
		os.Remove(ziel) // entfernt nur einen leeren, eben erst angelegten Ordner
		return
	}
	for laeuft() {
		if !frage("Jahresring läuft gerade.\n\nBitte das Programm beenden (Symbol unten rechts neben der Uhr › Rechtsklick › Beenden) und danach auf „Ja“ klicken.\n\n„Nein“ bricht die Installation ab.") {
			return
		}
		time.Sleep(1500 * time.Millisecond)
	}
	if err := os.MkdirAll(ziel, 0o755); err != nil {
		panic(fmt.Sprintf("Der Ordner %s lässt sich nicht anlegen: %v", ziel, err))
	}
	n, err := entpacken(ziel)
	logf("%d Dateien entpackt, Fehler: %v", n, err)
	if err != nil {
		panic(fmt.Sprintf("Die Programmdateien konnten nicht geschrieben werden:\n%v", err))
	}
	os.MkdirAll(filepath.Dir(merkDatei()), 0o755)
	os.WriteFile(merkDatei(), []byte(ziel), 0o644)
	if err := verknuepfungen(ziel); err != nil {
		logf("Verknüpfungen: %v", err)
	}
	netz := ""
	if !firewallVorhanden() {
		if frage("Soll Jahresring für Tablets, Handys und weitere PCs im eigenen Netzwerk freigegeben werden?\n\n" +
			"Dazu werden in der Windows-Firewall die Ports 8765 bis 8767 für private Netzwerke geöffnet. Windows fragt dafür gleich nach Administratorrechten.\n\n" +
			"Nein = nur an diesem PC benutzen (lässt sich später mit Handy-Freigabe.bat nachholen)") {
			profil, err := firewallFreigeben()
			logf("Firewall: Profil %q, Fehler: %v", profil, err)
			if err != nil {
				netz = "Die Firewall wurde nicht geändert (Abfrage abgelehnt oder Fehler). Für Tablets und Handys später im Programmordner Handy-Freigabe.bat ausführen.\n\n"
			} else if strings.Contains(strings.ToLower(profil), "public") {
				netz = "Die Firewall ist freigegeben. Achtung: Windows führt das Netzwerk dieses PCs als „Öffentlich“ – so kommen Tablets und Handys nicht durch. " +
					"Bitte unter Einstellungen › Netzwerk und Internet › WLAN bzw. Ethernet › Eigenschaften auf „Privates Netzwerk“ umstellen.\n\n"
			} else {
				netz = "Die Firewall ist für Tablets und Handys im eigenen Netzwerk freigegeben.\n\n"
			}
		}
	}
	uebernommen := ""
	if !update {
		uebernommen = datenUebernehmen(ziel)
	}
	fertig := "Jahresring " + version + " ist installiert und startet jetzt.\n\n"
	if update {
		fertig = "Jahresring wurde auf Version " + version + " aktualisiert und startet jetzt.\n\n"
	} else {
		fertig += uebernommen + "Beim ersten Start richtet sich das Programm einmalig ein (Python, ein bis zwei Minuten, Internet nötig) – das schwarze Fenster dabei bitte offen lassen.\n\n"
		if uebernommen == "" {
			fertig += "Daten vom bisherigen PC später übernehmen: Jahresring beenden und den Ordner „daten“ vom alten PC nach\n" + ziel + "\nkopieren.\n\n"
		}
	}
	fertig += netz + "Gestartet wird künftig über „Jahresring“ auf dem Desktop."
	meldung(fertig, false)
	if err := starten(ziel); err != nil {
		logf("Start: %v", err)
		meldung("Das Programm ließ sich nicht automatisch starten. Bitte „Jahresring“ auf dem Desktop doppelklicken.", true)
	}
}
