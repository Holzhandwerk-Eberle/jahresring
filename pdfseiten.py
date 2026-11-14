"""Seitenzahlen „Seite 1 von 3“ in eine fertige PDF-Datei stempeln (ohne Zusatzpakete).
Es wird eine inkrementelle Aktualisierung an die Datei angehängt; der Inhalt der Seiten bleibt unverändert."""
import re

WS = b" \t\r\n\f\x00"
DELIM = b"()<>[]{}/%"


# Umrisse der Zeichen für „Seite 1 von 2“ (Liberation Sans, SIL Open Font License), Einheiten 1/1000 em.
# Die Seitenzahl wird als Vektorgrafik gezeichnet – ohne Schrift, damit PDF/A (ZUGFeRD) gültig bleibt.
GLYPHEN = {
    " ": (278, ""),
    "0": (556, "517 344 m 517 229 497 142 456 81 c 416 21 356 -10 277 -10 c 198 -10 138 20 99 81 c 59 141 39 229 39 344 c 39 462 58 551 97 610 c 135 669 196 698 280 698 c 361 698 421 668 459 609 c 498 549 517 461 517 344 c h 428 344 m 428 444 416 515 393 560 c 370 605 333 627 280 627 c 226 627 187 605 163 561 c 140 517 128 445 128 344 c 128 247 140 175 164 130 c 188 85 226 62 278 62 c 330 62 368 85 392 131 c 416 178 428 249 428 344 c h"),
    "1": (556, "76 0 m 76 75 l 251 75 l 251 604 l 96 493 l 96 576 l 259 688 l 340 688 l 340 75 l 507 75 l 507 0 l h"),
    "2": (556, "50 0 m 50 62 l 67 100 87 134 111 163 c 135 192 160 218 187 242 c 213 266 239 287 265 308 c 291 328 314 348 335 368 c 356 388 373 410 385 432 c 398 454 405 479 405 507 c 405 545 394 574 372 595 c 349 616 319 626 279 626 c 242 626 211 616 187 595 c 163 575 148 547 144 510 c 54 518 l 61 573 84 617 124 649 c 164 682 216 698 279 698 c 349 698 402 682 439 649 c 476 616 495 570 495 510 c 495 483 489 457 477 430 c 465 404 446 377 422 351 c 398 325 352 284 284 229 c 247 198 217 170 195 146 c 173 121 157 97 147 75 c 506 75 l 506 0 l h"),
    "3": (556, "512 190 m 512 126 492 77 452 42 c 411 8 354 -10 279 -10 c 209 -10 154 6 112 37 c 71 69 46 115 38 177 c 129 185 l 141 104 191 63 279 63 c 323 63 358 74 383 96 c 408 118 421 150 421 193 c 421 230 406 260 378 281 c 349 302 307 312 253 312 c 203 312 l 203 388 l 251 388 l 299 388 337 399 363 420 c 390 441 403 470 403 507 c 403 544 392 573 370 594 c 349 615 317 626 274 626 c 235 626 204 616 180 596 c 156 576 142 548 138 512 c 50 519 l 56 575 80 619 120 651 c 160 682 212 698 275 698 c 344 698 398 682 436 650 c 474 618 493 573 493 516 c 493 472 481 436 456 409 c 432 381 396 363 349 353 c 349 351 l 401 346 441 328 469 299 c 498 270 512 234 512 190 c h"),
    "4": (556, "430 156 m 430 0 l 347 0 l 347 156 l 23 156 l 23 224 l 338 688 l 430 688 l 430 225 l 527 225 l 527 156 l h 347 589 m 347 587 342 578 333 563 c 325 548 319 537 314 531 c 138 271 l 112 235 l 104 225 l 347 225 l h"),
    "5": (556, "514 224 m 514 152 493 94 449 53 c 406 11 347 -10 270 -10 c 206 -10 154 4 115 32 c 75 60 50 101 40 154 c 129 164 l 147 96 195 62 272 62 c 319 62 356 76 383 105 c 410 133 423 172 423 222 c 423 265 409 300 383 327 c 356 354 319 367 274 367 c 250 367 228 363 208 356 c 187 348 167 336 146 318 c 60 318 l 83 688 l 474 688 l 474 613 l 163 613 l 150 395 l 188 424 235 439 292 439 c 360 439 414 419 454 379 c 494 340 514 288 514 224 c h"),
    "6": (556, "512 225 m 512 153 493 95 453 53 c 414 11 359 -10 290 -10 c 213 -10 153 19 112 77 c 71 134 51 218 51 328 c 51 447 72 539 115 603 c 157 666 218 698 297 698 c 401 698 466 652 493 558 c 409 543 l 392 599 354 627 296 627 c 246 627 207 604 179 557 c 152 510 138 443 138 354 c 154 384 177 406 206 422 c 235 437 268 445 305 445 c 369 445 419 425 456 385 c 494 346 512 292 512 225 c h 423 221 m 423 271 411 309 386 336 c 362 363 328 377 284 377 c 243 377 210 365 185 341 c 160 317 147 284 147 242 c 147 189 160 146 186 112 c 212 78 246 61 287 61 c 329 61 363 75 387 104 c 411 132 423 171 423 221 c h"),
    "7": (556, "506 617 m 436 509 386 425 357 364 c 328 303 306 243 292 184 c 277 125 270 63 270 0 c 178 0 l 178 88 197 180 234 278 c 271 375 334 487 421 613 c 51 613 l 51 688 l 506 688 l h"),
    "8": (556, "513 192 m 513 128 493 79 452 43 c 412 8 354 -10 278 -10 c 205 -10 147 8 106 42 c 64 77 43 127 43 191 c 43 236 56 274 82 304 c 108 335 141 353 181 360 c 181 362 l 143 371 114 390 92 419 c 70 448 60 483 60 522 c 60 574 79 617 118 649 c 158 682 210 698 276 698 c 344 698 398 682 437 650 c 476 618 496 575 496 521 c 496 482 485 447 463 418 c 441 389 411 370 374 363 c 374 361 l 417 354 452 335 476 305 c 500 275 513 237 513 192 c h 404 516 m 404 594 362 633 276 633 c 235 633 204 623 182 604 c 160 584 149 555 149 516 c 149 477 161 447 183 426 c 205 405 237 395 277 395 c 319 395 350 405 372 424 c 393 443 404 473 404 516 c h 421 200 m 421 243 409 275 383 297 c 358 318 322 329 276 329 c 232 329 197 317 172 294 c 147 271 134 239 134 198 c 134 104 183 56 279 56 c 327 56 363 68 386 91 c 410 114 421 150 421 200 c h"),
    "9": (556, "509 358 m 509 240 487 149 444 85 c 401 22 340 -10 260 -10 c 206 -10 163 2 131 24 c 98 47 75 83 61 134 c 145 147 l 163 90 201 61 261 61 c 312 61 351 84 378 131 c 406 178 421 245 422 332 c 409 303 387 279 355 261 c 323 244 289 235 251 235 c 189 235 140 256 103 298 c 65 341 47 397 47 467 c 47 539 67 595 107 636 c 148 678 204 698 276 698 c 352 698 410 670 450 613 c 489 557 509 472 509 358 c h 413 443 m 413 498 400 543 375 576 c 350 610 316 627 273 627 c 231 627 197 613 173 584 c 148 555 136 516 136 467 c 136 417 148 377 173 348 c 197 319 230 304 272 304 c 297 304 321 310 343 322 c 365 333 382 349 394 371 c 407 392 413 416 413 443 c h"),
    "S": (667, "621 190 m 621 126 596 77 547 42 c 497 8 427 -10 337 -10 c 169 -10 72 49 45 165 c 136 183 l 146 142 168 111 202 92 c 236 73 282 63 340 63 c 401 63 447 73 480 94 c 512 115 529 145 529 185 c 529 208 524 226 513 240 c 503 254 489 265 470 274 c 452 284 430 291 404 297 c 378 304 350 310 318 317 c 264 329 223 341 195 354 c 166 366 144 379 128 394 c 112 409 99 426 91 446 c 82 466 78 488 78 514 c 78 573 100 618 145 650 c 190 682 255 698 339 698 c 417 698 477 686 518 662 c 559 638 588 598 605 540 c 513 524 l 503 560 484 587 456 603 c 427 620 388 628 338 628 c 283 628 241 619 212 601 c 183 582 168 555 168 519 c 168 498 174 480 185 467 c 197 453 213 441 234 431 c 255 422 297 410 360 396 c 382 391 403 386 424 381 c 445 376 465 370 484 363 c 503 356 521 348 538 338 c 555 329 569 317 582 304 c 594 290 604 274 611 255 c 618 237 621 215 621 190 c h"),
    "e": (556, "135 246 m 135 185 147 138 172 105 c 197 73 234 56 282 56 c 320 56 351 64 374 79 c 397 94 412 114 420 137 c 498 115 l 466 32 394 -10 282 -10 c 204 -10 145 14 104 60 c 63 107 42 176 42 268 c 42 355 63 422 104 468 c 145 515 203 538 279 538 c 434 538 512 444 512 257 c 512 246 l h 421 313 m 416 369 402 409 378 435 c 355 460 321 473 277 473 c 235 473 201 459 176 430 c 151 402 138 363 136 313 c h"),
    "i": (222, "67 641 m 67 725 l 155 725 l 155 641 l h 67 0 m 67 528 l 155 528 l 155 0 l h"),
    "n": (556, "403 0 m 403 335 l 403 370 399 397 393 416 c 386 435 375 449 360 458 c 345 466 323 470 294 470 c 252 470 218 456 194 427 c 169 398 157 358 157 306 c 157 0 l 69 0 l 69 416 l 69 477 68 515 66 528 c 149 528 l 150 527 150 522 150 515 c 151 508 151 500 152 490 c 152 481 153 464 153 438 c 155 438 l 175 474 198 500 225 515 c 251 531 284 538 324 538 c 382 538 424 524 451 495 c 478 466 491 418 491 352 c 491 0 l h"),
    "o": (556, "514 265 m 514 172 494 103 453 58 c 412 13 353 -10 276 -10 c 199 -10 140 14 101 61 c 62 108 42 176 42 265 c 42 447 121 538 279 538 c 360 538 419 516 457 471 c 495 427 514 358 514 265 c h 422 265 m 422 338 411 391 389 424 c 368 457 331 473 280 473 c 229 473 192 456 169 423 c 146 389 134 336 134 265 c 134 195 146 143 168 108 c 191 73 226 55 275 55 c 328 55 365 72 388 106 c 411 140 422 193 422 265 c h"),
    "t": (278, "271 4 m 242 -4 212 -8 182 -8 c 111 -8 76 32 76 112 c 76 464 l 15 464 l 15 528 l 80 528 l 105 646 l 164 646 l 164 528 l 262 528 l 262 464 l 164 464 l 164 131 l 164 105 168 88 177 77 c 185 67 199 62 220 62 c 231 62 248 64 271 69 c h"),
    "v": (500, "299 0 m 195 0 l 3 528 l 97 528 l 213 185 l 218 172 229 133 247 69 c 264 126 l 283 184 l 403 528 l 497 528 l h"),
}


class PdfFehler(Exception):
    pass


class Ref:
    def __init__(self, nr, gen=0):
        self.nr, self.gen = nr, gen

    def __repr__(self):
        return f"{self.nr} {self.gen} R"


class Name(str):
    pass


class Roh(bytes):
    """Wert, der unverändert wieder ausgegeben wird (Strings, Hex-Strings)."""


def _ws(d, i):
    while i < len(d):
        if d[i:i + 1] in WS:
            i += 1
        elif d[i:i + 1] == b"%":
            while i < len(d) and d[i:i + 1] not in b"\r\n":
                i += 1
        else:
            break
    return i


def parse(d, i):
    """Liest ein PDF-Objekt ab Position i → (wert, neue Position)."""
    i = _ws(d, i)
    c = d[i:i + 1]
    if d[i:i + 2] == b"<<":
        i += 2
        erg = {}
        while True:
            i = _ws(d, i)
            if d[i:i + 2] == b">>":
                return erg, i + 2
            k, i = parse(d, i)
            v, i = parse(d, i)
            erg[str(k)] = v
    if c == b"[":
        i += 1
        erg = []
        while True:
            i = _ws(d, i)
            if d[i:i + 1] == b"]":
                return erg, i + 1
            v, i = parse(d, i)
            erg.append(v)
    if c == b"/":
        j = i + 1
        while j < len(d) and d[j:j + 1] not in WS and d[j:j + 1] not in DELIM:
            j += 1
        return Name(d[i + 1:j].decode("latin-1")), j
    if c == b"(":
        tiefe, j = 0, i
        while j < len(d):
            ch = d[j:j + 1]
            if ch == b"\\":
                j += 2
                continue
            if ch == b"(":
                tiefe += 1
            elif ch == b")":
                tiefe -= 1
                if tiefe == 0:
                    return Roh(d[i:j + 1]), j + 1
            j += 1
        raise PdfFehler("String nicht abgeschlossen")
    if c == b"<":
        j = d.index(b">", i)
        return Roh(d[i:j + 1]), j + 1
    m = re.compile(rb"(-?\d+)\s+(\d+)\s+R(?![A-Za-z])").match(d, i)
    if m:
        return Ref(int(m.group(1)), int(m.group(2))), m.end()
    m = re.compile(rb"[-+]?(\d+\.?\d*|\.\d+)").match(d, i)
    if m:
        t = m.group(0)
        return (float(t) if b"." in t else int(t)), m.end()
    m = re.compile(rb"[A-Za-z]+").match(d, i)
    if m:
        w = m.group(0)
        return {b"true": True, b"false": False, b"null": None}.get(w, Name(w.decode())), m.end()
    raise PdfFehler(f"Unbekanntes Zeichen an Position {i}")


def schreiben(v):
    if isinstance(v, dict):
        return b"<<" + b"".join(b"/" + k.encode("latin-1") + b" " + schreiben(x) + b"\n" for k, x in v.items()) + b">>"
    if isinstance(v, list):
        return b"[" + b" ".join(schreiben(x) for x in v) + b"]"
    if isinstance(v, Ref):
        return f"{v.nr} {v.gen} R".encode()
    if isinstance(v, Name):
        return b"/" + v.encode("latin-1")
    if isinstance(v, Roh):
        return bytes(v)
    if v is True:
        return b"true"
    if v is False:
        return b"false"
    if v is None:
        return b"null"
    if isinstance(v, float):
        return (f"{v:.4f}".rstrip("0").rstrip(".")).encode()
    return str(v).encode()


class Pdf:
    def __init__(self, daten):
        self.d = daten
        self.pos = {}
        for m in re.finditer(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b", daten):
            self.pos[int(m.group(1))] = m.end()   # letzte Fassung gewinnt
        sx = daten.rfind(b"startxref")
        if sx < 0:
            raise PdfFehler("startxref fehlt")
        self.startxref = int(re.compile(rb"\s*(\d+)").match(daten, sx + 9).group(1))
        self.trailer = self._trailer()

    def _trailer(self):
        t = self.d.rfind(b"trailer")
        if t >= 0 and t > self.startxref - 1:
            v, _ = parse(self.d, t + 7)
            return v
        # Querverweis-Stream: Trailer-Einträge stehen im Stream-Dictionary
        v, _ = parse(self.d, re.compile(rb"\d+\s+\d+\s+obj").match(self.d, self.startxref).end())
        return v

    def obj(self, nr):
        if isinstance(nr, Ref):
            nr = nr.nr
        if nr not in self.pos:
            raise PdfFehler(f"Objekt {nr} nicht gefunden (evtl. in komprimiertem Objekt-Stream)")
        v, _ = parse(self.d, self.pos[nr])
        return v

    def wert(self, v):
        return self.obj(v) if isinstance(v, Ref) else v

    def seiten(self):
        katalog = self.obj(self.trailer["Root"])
        aus = []

        def lauf(ref, erbe):
            knoten = self.obj(ref)
            erbe = dict(erbe)
            for k in ("MediaBox", "Resources"):
                if k in knoten:
                    erbe[k] = knoten[k]
            if knoten.get("Type") == "Pages" or "Kids" in knoten:
                for kid in self.wert(knoten["Kids"]):
                    lauf(kid, erbe)
            else:
                aus.append((ref, knoten, erbe))
        lauf(katalog["Pages"], {})
        return aus


def stempeln(daten, texte, rechts_mm=18, unten_mm=8, groesse=8):
    """texte: Liste je Seite (None = nichts). Liefert die neue PDF-Datei als bytes."""
    pdf = Pdf(daten)
    seiten = pdf.seiten()
    neu = []                      # (nr, bytes)
    naechste = max(int(pdf.trailer.get("Size", 0)), max(pdf.pos) + 1)

    def anlegen(inhalt):
        nonlocal naechste
        nr = naechste
        naechste += 1
        neu.append((nr, inhalt))
        return Ref(nr)

    def stream(text):
        roh = text.encode("latin-1")
        return b"<</Length " + str(len(roh)).encode() + b">>\nstream\n" + roh + b"\nendstream"

    q_auf = anlegen(stream("q"))
    q_zu = anlegen(stream("Q"))
    for (ref, seite, erbe), text in zip(seiten, texte):
        if not text:
            continue
        mb = [float(x) for x in pdf.wert(seite.get("MediaBox") or erbe.get("MediaBox") or [0, 0, 595.28, 841.89])]
        breite = mb[2] - mb[0]
        pt = 72 / 25.4
        textbreite = sum(GLYPHEN.get(ch, (556, ""))[0] for ch in text) * groesse / 1000
        x = mb[0] + breite - rechts_mm * pt - textbreite
        y = mb[1] + unten_mm * pt
        teile, vor = [], 0
        for ch in text:
            w, pfad = GLYPHEN.get(ch, (556, ""))
            if pfad:
                teile.append(f"q 1 0 0 1 {vor} 0 cm {pfad} f Q")
            vor += w
        k = groesse / 1000
        mein = anlegen(stream(f"q 0.33 g {k:.4f} 0 0 {k:.4f} {x:.2f} {y:.2f} cm " + " ".join(teile) + " Q"))
        inhalt = seite.get("Contents")
        inhalt = pdf.wert(inhalt) if isinstance(inhalt, Ref) and isinstance(pdf.wert(inhalt), list) else inhalt
        alt = inhalt if isinstance(inhalt, list) else ([inhalt] if inhalt is not None else [])
        neu_seite = dict(seite)
        neu_seite["Contents"] = [q_auf] + alt + [q_zu, mein]
        neu.append((ref.nr, schreiben(neu_seite)))
    if len(neu) <= 3:
        return daten
    aus = bytearray(daten)
    if not aus.endswith(b"\n"):
        aus += b"\n"
    offsets = {}
    for nr, inhalt in neu:
        offsets[nr] = len(aus)
        aus += f"{nr} 0 obj\n".encode() + inhalt + b"\nendobj\n"
    xref = len(aus)
    aus += b"xref\n0 1\n0000000000 65535 f \n"
    for nr in sorted(offsets):
        aus += f"{nr} 1\n{offsets[nr]:010d} 00000 n \n".encode()
    trailer = {"Size": naechste, "Root": pdf.trailer["Root"], "Prev": pdf.startxref}
    if "Info" in pdf.trailer:
        trailer["Info"] = pdf.trailer["Info"]
    if "ID" in pdf.trailer:
        trailer["ID"] = pdf.trailer["ID"]
    aus += b"trailer\n" + schreiben(trailer) + f"\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(aus)


def seitenzahl(daten):
    return len(Pdf(daten).seiten())


def nummerieren(pfad, ohne_letzte=0, vorlage="Seite {n} von {gesamt}", **kw):
    """Nummeriert alle Seiten außer den letzten `ohne_letzte` (z. B. AGB). Bei nur einer Seite: keine Nummer."""
    with open(pfad, "rb") as f:
        daten = f.read()
    n = seitenzahl(daten)
    gesamt = n - ohne_letzte
    if gesamt < 2:
        return False
    texte = [vorlage.format(n=i + 1, gesamt=gesamt) if i < gesamt else None for i in range(n)]
    neu = stempeln(daten, texte, **kw)
    with open(pfad + ".tmp", "wb") as f:
        f.write(neu)
    import os
    os.replace(pfad + ".tmp", pfad)
    return True
