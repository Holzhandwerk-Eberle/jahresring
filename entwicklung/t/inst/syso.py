"""Erzeugt rsrc_windows_amd64.syso (COFF-Objekt mit .rsrc): Programmsymbol, Manifest und Versionsangabe für Jahresring-Setup.exe."""
import struct, sys
ico_pfad, ziel = sys.argv[1], sys.argv[2]
ico = open(ico_pfad, "rb").read()
_, typ, anzahl = struct.unpack_from("<HHH", ico, 0)
assert typ == 1 and anzahl
bilder, gruppe = [], struct.pack("<HHH", 0, 1, anzahl)
for i in range(anzahl):
    w, h, farben, res, ebenen, bpp, groesse, offset = struct.unpack_from("<BBBBHHII", ico, 6 + 16 * i)
    bilder.append(ico[offset:offset + groesse])
    gruppe += struct.pack("<BBBBHHIH", w, h, farben, res, ebenen, bpp, groesse, i + 1)
manifest = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<assemblyIdentity type="win32" name="Jahresring.Setup" version="1.0.0.0" processorArchitecture="amd64"/>
<description>Jahresring Setup</description>
<dependency><dependentAssembly><assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0" processorArchitecture="amd64" publicKeyToken="6595b64144ccf1df" language="*"/></dependentAssembly></dependency>
<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"/></requestedPrivileges></security></trustInfo>
<application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings>
<dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
<dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2</dpiAwareness></windowsSettings></application>
<compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1"><application><supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/></application></compatibility>
</assembly>"""
# Versionsangaben (Rechtsklick › Eigenschaften › Details): VS_VERSIONINFO
version = sys.argv[3] if len(sys.argv) > 3 else "0.0.0-0"
firma = sys.argv[4] if len(sys.argv) > 4 else ""
zahlen = ([int(x) for x in version.replace("-", ".").split(".") if x.isdigit()] + [0, 0, 0, 0])[:4]
u16 = lambda t: t.encode("utf-16-le") + b"\0\0"
pad = lambda b: b + b"\0" * (-len(b) % 4)


def knoten(name, wert=b"", wert_laenge=0, typ=1, kinder=()):
    inhalt = pad(struct.pack("<HHH", 0, wert_laenge, typ) + u16(name)) + pad(wert) + b"".join(pad(k) for k in kinder)
    return struct.pack("<H", len(inhalt)) + inhalt[2:]


def text(name, wert):
    return knoten(name, u16(wert), len(wert) + 1, 1)


fest = struct.pack("<IIIIIIIIIIIII", 0xFEEF04BD, 0x00010000, zahlen[0] << 16 | zahlen[1], zahlen[2] << 16 | zahlen[3],
                   zahlen[0] << 16 | zahlen[1], zahlen[2] << 16 | zahlen[3], 0x3F, 0, 0x00040004, 1, 0, 0, 0)
angaben = [("CompanyName", firma), ("FileDescription", "Jahresring Setup – Installation und Update"), ("FileVersion", version),
           ("InternalName", "Jahresring-Setup"), ("LegalCopyright", "© " + str(zahlen[0]) + " " + firma), ("OriginalFilename", "Jahresring-Setup.exe"),
           ("ProductName", "Jahresring"), ("ProductVersion", version)]
versionsinfo = knoten("VS_VERSION_INFO", fest, len(fest), 0, [
    knoten("StringFileInfo", kinder=[knoten("040704B0", kinder=[text(k, v) for k, v in angaben if v])]),
    knoten("VarFileInfo", kinder=[knoten("Translation", struct.pack("<HH", 0x0407, 0x04B0), 4, 0)])])
# Ressourcen: (Typ, [(Id, Daten)]), Typen aufsteigend
res = [(3, [(i + 1, b) for i, b in enumerate(bilder)]), (14, [(1, gruppe)]), (16, [(1, versionsinfo)]), (24, [(1, manifest)])]
SPRACHE = 1031
n_typ, n_ein = len(res), sum(len(e) for _, e in res)
VERZ, EINTRAG, DATEN = 16, 8, 16
off_typ = 0
off_namen = VERZ + EINTRAG * n_typ                       # je Typ ein Verzeichnis mit seinen Ids
off_spr = off_namen + sum(VERZ + EINTRAG * len(e) for _, e in res)   # je Ressource ein Sprachverzeichnis mit 1 Eintrag
off_dat = off_spr + n_ein * (VERZ + EINTRAG)             # Dateneinträge
off_roh = off_dat + n_ein * DATEN                        # Rohdaten
kopf = lambda n: struct.pack("<IIHHHH", 0, 0, 0, 0, 0, n)
t_typ, t_namen, t_spr, t_dat, roh, relocs = kopf(n_typ), b"", b"", b"", b"", []
pos_namen, k = off_namen, 0
for typ, eintraege in res:
    t_typ += struct.pack("<II", typ, 0x80000000 | pos_namen)
    t_namen += kopf(len(eintraege))
    for rid, daten in eintraege:
        t_namen += struct.pack("<II", rid, 0x80000000 | (off_spr + k * (VERZ + EINTRAG)))
        t_spr += kopf(1) + struct.pack("<II", SPRACHE, off_dat + k * DATEN)
        relocs.append(off_dat + k * DATEN)               # Feld OffsetToData wird vom Linker zur RVA ergänzt
        t_dat += struct.pack("<IIII", off_roh + len(roh), len(daten), 0, 0)
        roh += daten + b"\0" * (-len(daten) % 8)
        k += 1
    pos_namen += VERZ + EINTRAG * len(eintraege)
sektion = t_typ + t_namen + t_spr + t_dat + roh
assert len(t_typ + t_namen) == off_spr and len(t_typ + t_namen + t_spr) == off_dat
p_roh = 20 + 40
p_rel = p_roh + len(sektion)
p_sym = p_rel + 10 * len(relocs)
datei = struct.pack("<HHIIIHH", 0x8664, 1, 0, p_sym, 1, 0, 0)
datei += struct.pack("<8sIIIIIIHHI", b".rsrc", 0, 0, len(sektion), p_roh, p_rel, 0, len(relocs), 0, 0x40000040)
datei += sektion + b"".join(struct.pack("<IIH", r, 0, 3) for r in relocs)   # IMAGE_REL_AMD64_ADDR32NB
datei += struct.pack("<8sIhHBB", b".rsrc", 0, 1, 0, 3, 0) + struct.pack("<I", 4)
open(ziel, "wb").write(datei)
print("syso:", len(datei), "Bytes,", anzahl, "Symbolgrößen", [(b[0] or 256) for b in [ico[6 + 16 * i:7 + 16 * i] for i in range(anzahl)]])
