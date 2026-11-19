"""Externe Kalender (iCal): Serientermine."""
import sys, os, time
os.environ["TZ"] = "Europe/Berlin"
if hasattr(time, "tzset"): time.tzset()   # unter Windows gibt es tzset nicht; die geprüften Termine tragen ihre Zeitzone selbst
sys.path.insert(0, "/home/claude/eberle-buero")
import kalender as K
from datetime import datetime
def ics(body): return "BEGIN:VCALENDAR\nBEGIN:VEVENT\n" + body + "\nEND:VEVENT\nEND:VCALENDAR"
von, bis = datetime(2026, 11, 1), datetime(2026, 12, 31, 23, 59)
fehler = []
def T(name, body, v, b, soll):
    ist = [e["von"] + (" " + e["zeit_von"] if e.get("zeit_von") else "") for e in K.ics_parsen(ics(body), v, b)]
    print("ok  " if ist == soll else "FEHLER", name, ist if ist != soll else "")
    if ist != soll: fehler.append(name)
T("jeden 2. Dienstag", "UID:1\nDTSTART;TZID=Europe/Berlin:20260113T190000\nDTEND;TZID=Europe/Berlin:20260113T210000\nRRULE:FREQ=MONTHLY;BYDAY=2TU", von, bis, ["2026-11-10 19:00", "2026-12-08 19:00"])
T("Monatsletzter", "UID:3\nDTSTART;VALUE=DATE:20260131\nRRULE:FREQ=MONTHLY;BYMONTHDAY=-1", von, bis, ["2026-11-30", "2026-12-31"])
T("Weltzeit-Serie im Winter eine Stunde früher", "UID:5\nDTSTART:20260601T080000Z\nDTEND:20260601T090000Z\nRRULE:FREQ=WEEKLY;COUNT=24", von, datetime(2026, 11, 8), ["2026-11-02 09:00"])
T("Mo+Mi fünfmal", "UID:6\nDTSTART:20261102T080000\nDTEND:20261102T090000\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=5", von, bis, ["2026-11-02 08:00", "2026-11-04 08:00", "2026-11-09 08:00", "2026-11-11 08:00", "2026-11-16 08:00"])
n = len(K.ics_parsen(ics("UID:2\nDTSTART:20190101T080000\nDTEND:20190101T090000\nRRULE:FREQ=DAILY"), von, bis)); print("ok  " if n == 61 else "FEHLER", "tägliche Serie seit 2019:", n)
if n != 61: fehler.append("täglich")
T("letzter Freitag", "UID:7\nDTSTART:20240126T100000\nRRULE:FREQ=MONTHLY;BYDAY=-1FR", von, bis, ["2026-11-27 10:00", "2026-12-25 10:00"])
T("letzter Werktag (SETPOS)", "UID:8\nDTSTART;VALUE=DATE:20240131\nRRULE:FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1", von, bis, ["2026-11-30", "2026-12-31"])
T("jährlich 1. Advent-artig (BYMONTH+BYDAY)", "UID:9\nDTSTART;VALUE=DATE:20201101\nRRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU", von, bis, ["2026-11-01"])
T("täglich Mo-Fr UNTIL", "UID:10\nDTSTART:20261123T070000\nRRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20261201", von, bis, ["2026-11-23 07:00", "2026-11-24 07:00", "2026-11-25 07:00", "2026-11-26 07:00", "2026-11-27 07:00", "2026-11-30 07:00", "2026-12-01 07:00"])
T("alle 2 Wochen seit 2015", "UID:11\nDTSTART:20150105T090000\nRRULE:FREQ=WEEKLY;INTERVAL=2", von, bis, ["2026-11-09 09:00", "2026-11-23 09:00", "2026-12-07 09:00", "2026-12-21 09:00"])
T("EXDATE", "UID:12\nDTSTART:20261102T090000\nRRULE:FREQ=WEEKLY;COUNT=3\nEXDATE:20261109T090000", von, bis, ["2026-11-02 09:00", "2026-11-16 09:00"])
T("monatlich am 31.", "UID:13\nDTSTART;VALUE=DATE:20260131\nRRULE:FREQ=MONTHLY", von, bis, ["2026-12-31"])
T("jährlich Geburtstag", "UID:14\nDTSTART;VALUE=DATE:19800315\nRRULE:FREQ=YEARLY", datetime(2027,3,1), datetime(2027,3,31), ["2027-03-15"])
T("einzeln", "UID:15\nDTSTART:20261110T080000\nDTEND:20261110T100000", von, bis, ["2026-11-10 08:00"])
x = K.ics_export([{"art": "t", "id": 1, "von": "2026-11-16", "bis": "2026-11-16", "zeit_von": "08:00", "zeit_bis": "", "titel": "Montage"}])
print("ok  " if "DTEND:20261116T090000" in x else "FEHLER", "Export ohne Endzeit: eine Stunde")
if "DTEND:20261116T090000" not in x: fehler.append("export")
print("\nFEHLER:", fehler); sys.exit(1 if fehler else 0)
