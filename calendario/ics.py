# -*- coding: utf-8 -*-
"""Scrittura del file .ics.

Scelte che hanno funzionato a Birmingham e che restano:
- UID stabile derivato da gara+genere+fase: un aggiornamento modifica
  l'evento, non lo duplica;
- DTSTAMP fisso: due esecuzioni senza cambiamenti producono un file identico
  byte per byte, quindi nessun commit a vuoto;
- titoli con [B] [Q] [SF] [F] [10] e i nomi degli azzurri dopo la barra;
- orari italiani, con l'ora locale della sede in descrizione;
- sveglia 15 minuti prima solo sulle finali con italiani certi;
- TRANSP:TRANSPARENT, per non risultare "occupato" durante le gare.
"""
import datetime as dt
import hashlib

from .config import ITALIA

ETICHETTE = (("semifinal", "[SF]"), ("finale", "[F]"), ("batterie", "[B]"),
             ("qualificazioni", "[Q]"))

VTIMEZONE = """BEGIN:VTIMEZONE
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


def tag(fase):
    f = fase.lower()
    for chiave, t in ETICHETTE:
        if chiave in f:
            return t
    return "[10]"       # prove multiple: la "fase" e' la singola prova


def durata(gara, fase, regole=()):
    """Durata stimata in minuti. Le regole del file dell'evento vincono;
    altrimenti le stime dell'atletica usate a Birmingham."""
    testo = "%s %s" % (gara, fase)
    for regex, minuti in regole:
        if regex.search(testo):
            return minuti
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


def esc(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;")
             .replace(",", "\\,").replace("\n", "\\n"))


def piega(riga):
    """Righe lunghe spezzate a 75 byte come vuole RFC 5545, senza tagliare
    a meta' un carattere UTF-8."""
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


def uid(evento, k):
    return "%s-%s@%s" % (evento.sigla, hashlib.md5(k.encode()).hexdigest()[:12],
                         evento.dominio_uid)


def _numero(n):
    return {1: "un'ora"}.get(n, "%d ore" % n)


def ora_locale(evento, inizio):
    """Frase con la differenza di fuso e l'ora locale della sede."""
    loc = inizio.astimezone(evento.fuso_sede)
    diff = (loc.utcoffset() - inizio.utcoffset()).total_seconds() / 60
    if diff == 0:
        return "Orario italiano, lo stesso di %s." % evento.citta
    ore, minuti = divmod(abs(int(diff)), 60)
    quanto = _numero(ore) if ore else ""
    if minuti:
        quanto = (quanto + " e " if quanto else "") + "%d minuti" % minuti
    verso = "in meno" if diff < 0 else "in piu'"
    giorno = ""
    if loc.date() != inizio.date():
        giorno = " del giorno %s" % ("prima" if loc.date() < inizio.date()
                                     else "dopo")
    return "Orario italiano. A %s %s %s (ora locale %s%s)." % (
        evento.citta, quanto, verso, loc.strftime("%H:%M"), giorno)


def genera(evento, gare):
    r = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:" + evento.prodid,
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         piega("X-WR-CALNAME:" + esc(evento.nome_calendario)),
         "X-WR-TIMEZONE:Europe/Rome",
         "X-PUBLISHED-TTL:PT%dM" % evento.aggiornamento_minuti,
         "REFRESH-INTERVAL;VALUE=DURATION:PT%dM" % evento.aggiornamento_minuti]
    r += VTIMEZONE.split("\n")
    for e in gare:
        hh, mm = map(int, e["ora"].split(":"))
        ini = dt.datetime.combine(dt.date.fromisoformat(e["data"]),
                                  dt.time(hh, mm), tzinfo=ITALIA)
        fin = ini + dt.timedelta(minutes=durata(e["gara"], e["fase"],
                                                evento.durate))
        confermati = e.get("confermati") or []
        eventuale = e["eventuale"] and not confermati
        gen = " (%s)" % e["genere"] if e["genere"] else ""
        tit = "%s %s%s - %s" % (tag(e["fase"]), e["gara"], gen, e["fase"])
        if eventuale:
            tit += " (eventuale)"
        if e["atleti"]:
            tit += " | " + ", ".join(e["atleti"])
        if eventuale:
            presenza = ("Presenza italiana non ancora certa: dipende dal "
                        "turno precedente.")
        elif e["eventuale"]:
            attesa = [a for a in e["atleti"] if a not in confermati]
            presenza = "Presenza italiana confermata: %s." % ", ".join(confermati)
            if attesa:
                presenza += (" Ancora da decidere nel turno precedente: %s."
                             % ", ".join(attesa))
        else:
            presenza = "Presenza italiana confermata."
        desc = ["Azzurri: " + (", ".join(e["atleti"]) or "-"), presenza,
                ora_locale(evento, ini)]
        if evento.tv:
            desc.append(evento.tv)
        finale = "finale" in e["fase"].lower() and "semifinal" not in e["fase"].lower()
        r += ["BEGIN:VEVENT", "UID:" + uid(evento, e["k"]),
              "DTSTAMP:" + evento.dtstamp,
              "DTSTART;TZID=Europe/Rome:" + ini.strftime("%Y%m%dT%H%M%S"),
              "DTEND;TZID=Europe/Rome:" + fin.strftime("%Y%m%dT%H%M%S"),
              piega("SUMMARY:" + esc(tit)),
              piega("DESCRIPTION:" + esc("\n".join(desc))),
              piega("LOCATION:" + esc(evento.luogo)),
              "CATEGORIES:" + ("Finali" if finale else "Turni"),
              "TRANSP:TRANSPARENT", "STATUS:CONFIRMED"]
        if finale and not eventuale:
            r += ["BEGIN:VALARM", "ACTION:DISPLAY",
                  piega("DESCRIPTION:" + esc(e["gara"] + " tra 15 minuti")),
                  "TRIGGER:-PT15M", "END:VALARM"]
        r.append("END:VEVENT")
    r.append("END:VCALENDAR")
    return "\r\n".join(r) + "\r\n"
