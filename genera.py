#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera europei.ics con tutte le gare degli Europei di atletica Birmingham 2026
in cui sono impegnati atleti italiani. Pensato per girare su GitHub Actions.

Fonte: OA Sport, "gli italiani in gara giorno per giorno" - unica fonte italiana
completa, strutturata e raggiungibile da uno script (le altre danno 403).

Scrive europei.ics SOLO se i dati sono davvero cambiati: cosi' il repository non
si riempie di commit inutili e chi e' abbonato al calendario non viene
disturbato quando non c'e' niente di nuovo.
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

URL = ("https://www.oasport.it/2026/08/europei-atletica-2026-gli-italiani-in-"
       "gara-giorno-per-giorno-orari-e-dove-vederli-in-tv/")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato",
          "domenica")
ICS = "europei.ics"
STATO = "stato.json"


class Irraggiungibile(Exception):
    """La fonte non risponde: e' transitorio, non un guasto da segnalare."""


def scarica():
    """Scarica la pagina, con tre tentativi.

    Su GitHub Actions capita che OA Sport rifiuti o lasci cadere la richiesta
    (le richieste arrivano da un datacenter): e' successo 3 volte su 20 la prima
    notte. Non e' un guasto, e' rumore: si riprova e passa.
    """
    ultimo = None
    for tentativo in range(3):
        if tentativo:
            time.sleep(15)
        try:
            req = urllib.request.Request(
                URL, headers={"User-Agent": UA, "Accept-Language": "it-IT,it"})
            with urllib.request.urlopen(req, timeout=45) as r:
                dati = r.read()
            if len(dati) > 5000:
                return dati.decode("utf-8", "ignore")
            ultimo = "risposta troppo corta (%d byte)" % len(dati)
        except Exception as ex:
            ultimo = str(ex)
        try:
            import subprocess
            pr = subprocess.run(["curl", "-sL", "--max-time", "45",
                                 "-A", UA, URL], capture_output=True)
            if pr.returncode == 0 and len(pr.stdout) > 5000:
                return pr.stdout.decode("utf-8", "ignore")
            ultimo = "curl rc=%d, %d byte" % (pr.returncode, len(pr.stdout))
        except Exception as ex:
            ultimo = str(ex)
    raise Irraggiungibile(ultimo or "motivo ignoto")


def testo(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = html.unescape(t)
    # OA Sport mescola spazi normali e non-breaking space nella stessa pagina
    for c in ("\u00a0", "\u2009", "\u202f"):
        t = t.replace(c, " ")
    return [l.strip() for l in t.split("\n") if l.strip()]


def chiave(gara, genere, fase):
    s = unicodedata.normalize("NFKD", ("%s|%s|%s" % (gara, genere, fase)).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9|]+", "", s)


def analizza(righe):
    try:
        i = next(n for n, l in enumerate(righe)
                 if "CALENDARIO ITALIANI" in l.upper())
    except StopIteration:
        raise RuntimeError("blocco 'CALENDARIO ITALIANI' non trovato")
    eventi, giorno = [], None
    for l in righe[i + 1:]:
        if re.match(r"^(PROGRAMMA|COME VEDERL|Diretta tv)", l, re.I):
            break
        m = re.match(r"^(%s)\s+(\d{1,2})\s+agosto" % "|".join(GIORNI), l, re.I)
        if m:
            giorno = int(m.group(2))
            continue
        m = re.match(r"^(\d{1,2})\.(\d{2})\s+(.+)$", l)
        if not (m and giorno):
            continue
        ora = "%02d:%02d" % (int(m.group(1)), int(m.group(2)))
        resto = m.group(3)
        testa, atleti_txt = (resto.split(":", 1) if ":" in resto
                             else (resto, ""))
        testa = testa.strip()
        mg = re.match(r"^(.*?)\s*\((maschile|femminile|mista)\)\s*(?:,\s*(.*))?$",
                      testa)
        if mg:
            gara, genere, fase = mg.group(1).strip(), mg.group(2), (mg.group(3) or "").strip()
        elif "," in testa:
            gara, fase = [x.strip() for x in testa.split(",", 1)]
            genere = ""
        else:
            gara, fase, genere = testa, "", ""
        fase = fase or "finale"
        eventuale = "eventual" in atleti_txt.lower()
        at = re.sub(r"\beventual[ei]\b", "", atleti_txt, flags=re.I)
        atleti = [a.strip() for a in at.split(",") if a.strip()]
        atleti = [a for a in atleti if a.lower() not in ("eventuale", "eventuali")]
        eventi.append({"k": chiave(gara, genere, fase), "giorno": giorno,
                       "ora": ora, "gara": gara, "genere": genere,
                       "fase": fase, "atleti": atleti, "eventuale": eventuale})
    if len(eventi) < 60:
        raise RuntimeError("solo %d eventi letti: la pagina e' cambiata?"
                           % len(eventi))
    return eventi


def durata(gara, fase):
    g, f = gara.lower(), fase.lower()
    if "mezza maratona di marcia" in g:
        return 100
    if "maratona di marcia" in g:
        return 220
    if "maratona" in g:
        return 160
    if g.startswith(("decathlon", "eptathlon")):
        if "asta" in f:
            return 90
        if "alto" in f:
            return 110
        if "metri" in f or "ostacoli" in f:
            return 20
        return 65
    campo = any(k in g for k in ("salto", "getto", "lancio", "tiro"))
    if "qualificazioni" in f:
        return 110 if campo else 40
    if "batterie" in f:
        return 35
    if "semifinali" in f:
        return 25
    if "finale" in f:
        if campo:
            return 120 if ("asta" in g or "alto" in g) else 90
        if "10.000" in g:
            return 35
        if "5000" in g:
            return 20
        return 15
    return 30


def tag(fase):
    f = fase.lower()
    for chiavef, t in (("finale", "[F]"), ("semifinali", "[SF]"),
                       ("batterie", "[B]"), ("qualificazioni", "[Q]")):
        if chiavef in f:
            return t
    return "[10]"


def esc(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;")
             .replace(",", "\\,").replace("\n", "\\n"))


def piega(riga):
    b = riga.encode("utf-8")
    if len(b) <= 73:
        return riga
    testa = b[:73].decode("utf-8", "ignore")
    out, resto = [testa], b[len(testa.encode("utf-8")):]
    while resto:
        c = resto[:72].decode("utf-8", "ignore")
        out.append(" " + c)
        resto = resto[len(c.encode("utf-8")):]
    return "\r\n".join(out)


VTZ = """BEGIN:VTIMEZONE
TZID:Europe/Rome
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE"""

TV = ("TV: Rai 2 / Rai Sport HD (in chiaro), Sky Sport, Eurosport 1. "
      "Streaming: RaiPlay, NOW, Sky Go, HBO Max, Discovery+.")


def genera_ics(eventi):
    r = ["BEGIN:VCALENDAR", "VERSION:2.0",
         "PRODID:-//Paolo//Europei Atletica Birmingham 2026//IT",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         "X-WR-CALNAME:Europei atletica 2026 - Azzurri",
         "X-WR-TIMEZONE:Europe/Rome",
         "X-PUBLISHED-TTL:PT15M", "REFRESH-INTERVAL;VALUE=DURATION:PT15M"]
    r += VTZ.split("\n")
    for e in eventi:
        hh, mm = map(int, e["ora"].split(":"))
        ini = dt.datetime(2026, 8, e["giorno"], hh, mm)
        fin = ini + dt.timedelta(minutes=durata(e["gara"], e["fase"]))
        gen = " (%s)" % e["genere"] if e["genere"] else ""
        tit = "%s %s%s - %s" % (tag(e["fase"]), e["gara"], gen, e["fase"])
        if e["eventuale"]:
            tit += " (eventuale)"
        if e["atleti"]:
            tit += " | " + ", ".join(e["atleti"])
        desc = ["Azzurri: " + (", ".join(e["atleti"]) or "-"),
                ("Presenza italiana non ancora certa: dipende dal turno "
                 "precedente." if e["eventuale"]
                 else "Presenza italiana confermata."),
                "Orario italiano. A Birmingham un'ora in meno.", TV]
        uid = "ea26-" + hashlib.md5(e["k"].encode()).hexdigest()[:12]
        # DTSTAMP fisso e derivato dal contenuto: se i dati non cambiano il file
        # e' identico byte per byte e non genera commit a vuoto.
        r += ["BEGIN:VEVENT", "UID:%s@paolo.local" % uid,
              "DTSTAMP:20260809T000000Z",
              "DTSTART;TZID=Europe/Rome:" + ini.strftime("%Y%m%dT%H%M%S"),
              "DTEND;TZID=Europe/Rome:" + fin.strftime("%Y%m%dT%H%M%S"),
              piega("SUMMARY:" + esc(tit)),
              piega("DESCRIPTION:" + esc("\n".join(desc))),
              "LOCATION:Alexander Stadium\\, Birmingham (GBR)",
              "CATEGORIES:" + ("Finali" if "finale" in e["fase"].lower()
                               else "Turni"),
              "TRANSP:TRANSPARENT", "STATUS:CONFIRMED"]
        if "finale" in e["fase"].lower() and not e["eventuale"]:
            r += ["BEGIN:VALARM", "ACTION:DISPLAY",
                  "DESCRIPTION:" + esc(e["gara"] + " tra 15 minuti"),
                  "TRIGGER:-PT15M", "END:VALARM"]
        r.append("END:VEVENT")
    r.append("END:VCALENDAR")
    return "\r\n".join(r) + "\r\n"


def main():
    eventi = analizza(testo(scarica()))
    vecchi = None
    if os.path.exists(STATO):
        try:
            vecchi = json.load(open(STATO, encoding="utf-8"))
        except Exception:
            vecchi = None
    if vecchi == eventi and os.path.exists(ICS):
        print("nessun cambiamento (%d eventi)" % len(eventi))
        return
    with open(ICS, "w", encoding="utf-8", newline="") as f:
        f.write(genera_ics(eventi))
    json.dump(eventi, open(STATO, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("aggiornato: %d eventi" % len(eventi))


if __name__ == "__main__":
    try:
        main()
    except Irraggiungibile as ex:
        # Non e' un fallimento: la pagina risponde di nuovo al prossimo giro e
        # il calendario resta all'ultima versione buona. Uscire con errore qui
        # significherebbe solo una mail di allarme per un problema che si
        # risolve da solo.
        print("fonte momentaneamente irraggiungibile (%s): riprovo al prossimo "
              "giro" % ex)
    except Exception as ex:
        # Questo invece va segnalato: vuol dire che la pagina e' cambiata
        # nella struttura e il calendario smetterebbe di aggiornarsi in
        # silenzio.
        print("ERRORE:", ex, file=sys.stderr)
        sys.exit(1)
