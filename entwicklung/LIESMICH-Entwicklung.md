# Entwicklung (nicht Teil der Auslieferung)

Dieser Ordner enthält die Prüfskripte, die Bauwerkzeuge für `Jahresring-Setup.exe` und die Generatoren der
Arbeitsschutz-Vorlagen. Er wird beim Bauen nicht mit ausgeliefert.

Die Skripte erwarten ihre Arbeitsordner unter `/tmp/claude-0/t/` (Linux-Testumgebung, Playwright und Chromium
vorhanden). Wiederherstellen:

    bash entwicklung/einrichten.sh

Danach gelten die Abläufe aus `docs/Technische_Dokumentation.md` (Abschnitt Tests), z. B.:

    bash /tmp/claude-0/t/lauf/teil1.sh   # Grundtests, Kalkulation, E-Rechnung
    bash /tmp/claude-0/t/lauf/teil2.sh   # Sicherheit, GoBD, Rechte, XSS
    bash /tmp/claude-0/t/lauf/teil3.sh   # Status, Kalender, Export, Fuzzing
    bash /tmp/claude-0/t/lauf/teil4.sh   # Arbeitsschutz, Layout, Dokument-PDFs
    bash /tmp/claude-0/t/inst/bauen.sh   # Jahresring.zip und Jahresring-Setup.exe

Ergebnisse stehen in `/tmp/claude-0/t/lauf/*.txt`.
