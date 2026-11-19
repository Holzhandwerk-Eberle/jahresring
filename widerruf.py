"""Jahresring – Widerrufsbelehrung für Verträge, die außerhalb von Geschäftsräumen geschlossen werden (§§ 312b, 312g, 355 BGB).

Am Angebot, am Kostenvoranschlag und an der Auftragsbestätigung lässt sich „außerhalb von Geschäftsräumen geschlossen“ einschalten.
Dann druckt das Programm einen Hinweissatz in den Beleg und hängt ein eigenes Blatt an: die Widerrufsbelehrung nach dem gesetzlichen
Muster für Dienstleistungen (Anlage 1 zu Artikel 246a § 1 Absatz 2 Satz 2 EGBGB) und das Muster-Widerrufsformular (Anlage 2) mit den
Angaben des Betriebs, auf einer zweiten Seite die Erklärungen des Kunden (Empfang auf Papier, Beginn vor Ablauf der Frist).
Im Kalender steht die Widerrufsfrist als Sperre am Auftrag.

Die Vorgaben folgen den gesetzlichen Mustern Wort für Wort; eigene Fassungen lassen sich in den Einstellungen hinterlegen.
Ob ein Widerrufsrecht besteht und welche Fassung passt, entscheidet nicht das Programm (siehe Handbuch)."""
import re
from datetime import date, timedelta
from html import escape as h

ARTEN = ("angebot", "kv", "ab")   # nur diese Belege tragen den Schalter
FRIST_TAGE = 14

HINWEIS = ("Dieser Vertrag wird außerhalb von Geschäftsräumen geschlossen. Als Verbraucher haben Sie ein Widerrufsrecht. "
           "Die Widerrufsbelehrung und das Muster-Widerrufsformular sind beigefügt.")

# Muster-Widerrufsbelehrung (Anlage 1 zu Art. 246a § 1 Abs. 2 Satz 2 EGBGB), Fassung für Verträge über Dienstleistungen:
# Fristbeginn mit dem Vertragsabschluss (Gestaltungshinweis 1 a), Angaben des Unternehmers (Gestaltungshinweis 2),
# Wertersatz bei Beginn während der Frist (Gestaltungshinweis 6). Zeilen mit „## “ sind Überschriften.
BELEHRUNG = """## Widerrufsrecht
Sie haben das Recht, binnen vierzehn Tagen ohne Angabe von Gründen diesen Vertrag zu widerrufen.
Die Widerrufsfrist beträgt vierzehn Tage ab dem Tag des Vertragsabschlusses.
Um Ihr Widerrufsrecht auszuüben, müssen Sie uns ({unternehmer}) mittels einer eindeutigen Erklärung (z. B. ein mit der Post versandter Brief oder eine E-Mail) über Ihren Entschluss, diesen Vertrag zu widerrufen, informieren. Sie können dafür das beigefügte Muster-Widerrufsformular verwenden, das jedoch nicht vorgeschrieben ist.
Zur Wahrung der Widerrufsfrist reicht es aus, dass Sie die Mitteilung über die Ausübung des Widerrufsrechts vor Ablauf der Widerrufsfrist absenden.
## Folgen des Widerrufs
Wenn Sie diesen Vertrag widerrufen, haben wir Ihnen alle Zahlungen, die wir von Ihnen erhalten haben, einschließlich der Lieferkosten (mit Ausnahme der zusätzlichen Kosten, die sich daraus ergeben, dass Sie eine andere Art der Lieferung als die von uns angebotene, günstigste Standardlieferung gewählt haben), unverzüglich und spätestens binnen vierzehn Tagen ab dem Tag zurückzuzahlen, an dem die Mitteilung über Ihren Widerruf dieses Vertrags bei uns eingegangen ist. Für diese Rückzahlung verwenden wir dasselbe Zahlungsmittel, das Sie bei der ursprünglichen Transaktion eingesetzt haben, es sei denn, mit Ihnen wurde ausdrücklich etwas anderes vereinbart; in keinem Fall werden Ihnen wegen dieser Rückzahlung Entgelte berechnet.
Haben Sie verlangt, dass die Dienstleistungen während der Widerrufsfrist beginnen soll, so haben Sie uns einen angemessenen Betrag zu zahlen, der dem Anteil der bis zu dem Zeitpunkt, zu dem Sie uns von der Ausübung des Widerrufsrechts hinsichtlich dieses Vertrags unterrichten, bereits erbrachten Dienstleistungen im Vergleich zum Gesamtumfang der im Vertrag vorgesehenen Dienstleistungen entspricht."""

# Muster-Widerrufsformular (Anlage 2 zu Art. 246a § 1 Abs. 2 Satz 1 Nr. 1 und § 2 Abs. 2 Nr. 2 EGBGB)
FORMULAR_KOPF = "(Wenn Sie den Vertrag widerrufen wollen, dann füllen Sie bitte dieses Formular aus und senden Sie es zurück.)"
FORMULAR_ERKLAERUNG = ("Hiermit widerrufe(n) ich/wir (*) den von mir/uns (*) abgeschlossenen Vertrag über den Kauf der folgenden Waren (*)/"
                       "die Erbringung der folgenden Dienstleistung (*)")
FORMULAR_FELDER = ("Bestellt am (*)/erhalten am (*)", "Name des/der Verbraucher(s)", "Anschrift des/der Verbraucher(s)",
                   "Unterschrift des/der Verbraucher(s) (nur bei Mitteilung auf Papier)", "Datum")
FORMULAR_FUSS = "(*) Unzutreffendes streichen."

EMPFANG = "Die Widerrufsbelehrung und das Muster-Widerrufsformular habe(n) ich/wir auf Papier erhalten."
# Zustimmung zum Beginn vor Fristende und Kenntnis vom Erlöschen des Widerrufsrechts (§ 356 Abs. 4 Nr. 2, § 357a Abs. 2 BGB)
ERKLAERUNG = ("Ich/Wir verlange(n) ausdrücklich und stimme(n) zu, dass {firma} mit der Ausführung der beauftragten Leistungen vor Ablauf "
              "der Widerrufsfrist beginnt. Mir/Uns ist bekannt, dass ich/wir bei einem Widerruf einen angemessenen Betrag für die bis dahin "
              "erbrachten Leistungen zu zahlen habe(n) und dass das Widerrufsrecht erlischt, sobald die Leistungen vollständig erbracht sind.")

CSS = """
.agb.wdr { box-sizing: border-box; padding: 20mm 20mm 14mm 25mm; font-size: 9.5pt; line-height: 1.36; color: #222; }
.wdr h2 { font-size: 13pt; margin: 0 0 3mm; font-weight: 600; }
.wdr h2.zwei { margin-top: 7mm; padding-top: 5mm; border-top: .4pt solid #888; }
.wdr h3 { font-size: 10pt; margin: 3.2mm 0 1mm; font-weight: 600; }
.wdr p { margin: 0 0 1.6mm; }
.wdr .klein { font-size: 8.5pt; color: #444; }
.wdr .feld { display: flex; gap: 3mm; align-items: flex-end; margin-top: 5.5mm; }
.wdr .feld span { flex: 0 0 auto; }
.wdr .feld i { flex: 1 1 auto; border-bottom: .4pt solid #444; height: 0; }
.wdr .leer { border-bottom: .4pt solid #444; height: 7mm; }
.wdr .unter { display: flex; gap: 12mm; margin-top: 13mm; }
.wdr .unter div { flex: 1 1 0; border-top: .4pt solid #444; padding-top: 1mm; font-size: 8.5pt; color: #444; }
.wdr .kasten { border: .4pt solid #888; padding: 4mm 5mm 5mm; margin-top: 6mm; break-inside: avoid; }
.wdr .kasten h3 { margin-top: 0; }
p.wdr-hinweis { margin: 3mm 0; }
"""


def frist_ende(vertrag_am, feiertag=None):
    """Letzter Tag der Widerrufsfrist: 14 Tage nach dem Tag des Vertragsschlusses (der Tag selbst zählt nicht mit, § 187 Abs. 1 BGB).
    Fällt das Ende auf Samstag, Sonntag oder einen Feiertag, endet die Frist am nächsten Werktag (§ 193 BGB)."""
    try:
        d = date.fromisoformat(str(vertrag_am or "")[:10]) + timedelta(days=FRIST_TAGE)
    except ValueError:
        return ""
    for _ in range(10):
        if d.weekday() < 5 and not (feiertag and feiertag(d.isoformat())):
            break
        d += timedelta(days=1)
    return d.isoformat()


def unternehmer(fi, mit_telefon=True):
    """Name, Anschrift, Telefonnummer und E-Mail-Adresse des Betriebs in einer Zeile (für das Formular ohne Telefon)."""
    firma, inhaber = (fi.get("firma") or "").strip(), (fi.get("firma_inhaber") or "").strip()
    teile = [firma] + ([inhaber] if inhaber and inhaber.lower() not in firma.lower() else [])
    teile += [z.strip() for z in (fi.get("firma_anschrift") or "").split("\n") if z.strip()]
    if mit_telefon and (fi.get("firma_telefon") or "").strip():
        teile.append("Telefon " + fi["firma_telefon"].strip())
    if (fi.get("firma_email") or "").strip():
        teile.append("E-Mail " + fi["firma_email"].strip())
    return ", ".join(t for t in teile if t)


def fehlende_angaben(fi):
    """Was für die Belehrung fehlt (das Muster verlangt Name, Anschrift, Telefonnummer und E-Mail-Adresse)."""
    return [name for name, k in (("Firmenname", "firma"), ("Anschrift", "firma_anschrift"), ("Telefon", "firma_telefon"), ("E-Mail", "firma_email"))
            if not (fi.get(k) or "").strip()]


def hinweis(e):
    return (e.get("widerruf_hinweis") or "").strip() or HINWEIS


def _absaetze(text):
    aus = []
    for z in str(text or "").replace("\r\n", "\n").split("\n"):
        z = z.strip()
        if not z:
            continue
        aus.append(f"<h3>{h(z[3:].strip())}</h3>" if z.startswith("## ") else f"<p>{h(z)}</p>")
    return "".join(aus)


def seiten_html(e, fi, b, kunde_anschrift=""):
    """Die angehängten Blätter: Seite 1 Widerrufsbelehrung und Muster-Widerrufsformular, Seite 2 Erklärungen des Kunden."""
    belehrung = ((e.get("widerruf_belehrung") or "").strip() or BELEHRUNG).replace("{unternehmer}", unternehmer(fi))
    erklaerung = ((e.get("widerruf_erklaerung") or "").strip() or ERKLAERUNG).replace("{firma}", (fi.get("firma") or "der Betrieb").strip())
    beleg = " ".join(x for x in [b.get("artname") or "", b.get("nummer") or ""] if x)
    tag = b.get("datum") or ""
    vom = f" vom {tag[8:10]}.{tag[5:7]}.{tag[:4]}" if len(tag) >= 10 else ""
    kunde = ", ".join(z.strip() for z in str(kunde_anschrift or "").split("\n") if z.strip())
    feld = lambda t: f'<div class="feld"><span>{h(t)}</span><i></i></div>'   # noqa: E731
    unter = '<div class="unter"><div>Ort, Datum</div><div>Unterschrift des Kunden / der Kunden</div></div>'
    seite1 = (f'<div class="agb wdr"><h2>Widerrufsbelehrung</h2>{_absaetze(belehrung)}'
              f'<h2 class="zwei">Muster-Widerrufsformular</h2><p>{h(FORMULAR_KOPF)}</p>'
              f'<p>An {h(unternehmer(fi, mit_telefon=False))}:</p><p>{h(FORMULAR_ERKLAERUNG)}</p><div class="leer"></div><div class="leer"></div>'
              + "".join(feld(t) for t in FORMULAR_FELDER) + f'<p class="klein" style="margin-top:5mm">{h(FORMULAR_FUSS)}</p></div>')
    seite2 = (f'<div class="agb wdr"><h2>Erklärungen des Kunden</h2><p>zu {h(beleg or "dem Vertrag")}{h(vom)}'
              + (f'<br>Kunde: {h(kunde)}' if kunde else "") + '</p>'
              f'<div class="kasten"><h3>Empfangsbestätigung</h3><p>{h(EMPFANG)}</p>{unter}</div>'
              '<div class="kasten"><h3>Beginn der Arbeiten vor Ablauf der Widerrufsfrist</h3>'
              '<p class="klein">Nur ausfüllen, wenn die Arbeiten vor Ablauf der Widerrufsfrist von vierzehn Tagen beginnen sollen.</p>'
              f'{_absaetze(erklaerung)}{unter}</div>'
              '<p class="klein" style="margin-top:6mm">Dieses Blatt bleibt beim Betrieb. Die Widerrufsbelehrung und das Muster-Widerrufsformular '
              'behält der Kunde.</p></div>')
    return f"<style>{CSS}</style>" + seite1 + seite2


def hinweis_html(e):
    return f'<p class="wdr-hinweis">{h(hinweis(e))}</p>'


def sperren(con, von, bis, feiertag=None, status_ende=()):
    """Widerrufsfristen, die den Zeitraum berühren: je Auftrag der jüngste Vertragsschluss eines Belegs mit dem Schalter.
    → [{auftrag_id, beleg_id, nummer, artname, vertrag_am, von, bis, beginn, auftragsnr, kunde}]"""
    frueh = (date.fromisoformat(von) - timedelta(days=FRIST_TAGE + 10)).isoformat()
    je_auftrag = {}
    for r in con.execute("SELECT b.id, b.auftrag_id, b.art, b.nummer, b.vertrag_am, b.agv_beginn, a.nummer AS auftragsnr, a.status, k.kurzname AS kunde "
                         "FROM belege b JOIN auftraege a ON a.id=b.auftrag_id LEFT JOIN kunden k ON k.id=a.kunde_id "
                         "WHERE b.agv=1 AND b.vertrag_am>=? AND b.vertrag_am<=? ORDER BY b.vertrag_am, b.id", (frueh, bis)):
        if r["status"] in status_ende:
            continue
        je_auftrag[r["auftrag_id"]] = r   # der spätere Vertragsschluss gilt
    aus = []
    for r in je_auftrag.values():
        ende = frist_ende(r["vertrag_am"], feiertag)
        if not ende or ende < von:
            continue
        aus.append({"auftrag_id": r["auftrag_id"], "beleg_id": r["id"], "nummer": r["nummer"] or "", "art": r["art"], "vertrag_am": r["vertrag_am"],
                    "von": r["vertrag_am"], "bis": ende, "beginn": bool(r["agv_beginn"]), "auftragsnr": r["auftragsnr"], "kunde": r["kunde"] or ""})
    return aus


def sperre_fuer(con, auftrag_id, von, bis, feiertag=None):
    """Liegt der Zeitraum eines Termins ganz oder teilweise in der Widerrufsfrist des Auftrags? → Sperre oder None.
    Hat der Kunde den Beginn vor Fristende verlangt, gibt es keine Sperre."""
    if not auftrag_id or not von:
        return None
    bis = bis or von
    r = con.execute("SELECT id, nummer, art, vertrag_am, agv_beginn FROM belege WHERE auftrag_id=? AND agv=1 AND IFNULL(vertrag_am,'')<>'' "
                    "ORDER BY vertrag_am DESC, id DESC LIMIT 1", (int(auftrag_id),)).fetchone()
    if not r or r["agv_beginn"]:
        return None
    ende = frist_ende(r["vertrag_am"], feiertag)
    if not ende or bis < r["vertrag_am"] or von > ende:
        return None
    return {"beleg_id": r["id"], "nummer": r["nummer"] or "", "vertrag_am": r["vertrag_am"], "bis": ende}


def datum_pruefen(wert):
    """Tag des Vertragsschlusses: leer oder ein gültiges Datum JJJJ-MM-TT."""
    wert = str(wert or "").strip()
    if not wert:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", wert):
        raise ValueError("Bitte das Datum des Vertragsschlusses als Tag angeben.")
    date.fromisoformat(wert)
    return wert
