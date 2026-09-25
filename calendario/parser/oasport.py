# -*- coding: utf-8 -*-
"""Parser del programma "gli italiani in gara giorno per giorno" di OA Sport.

E' il parser del vecchio genera.py, portato qui senza cambiarne il
comportamento: dalla stessa pagina estrae le stesse gare con le stesse
chiavi, quindi gli UID dei calendari gia' sottoscritti non cambiano.

Formato atteso, dopo il titolo "CALENDARIO ITALIANI":

    lunedì 10 agosto
    11.35 Getto del peso (femminile), qualificazioni: Musci, Verteramo
    20.03 Getto del peso (femminile), finale: Musci, Verteramo eventuali
    ...

Opzioni nel file dell'evento:
    url            indirizzo della pagina
    inizio         testo che apre il blocco (predefinito "CALENDARIO ITALIANI")
    fine           regex della riga che chiude il blocco
    minimo_eventi  sotto questa soglia la pagina e' considerata cambiata
"""
import datetime as dt
import re

from ..rete import PaginaCambiata
from ..testo import chiave, righe

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato",
          "domenica")
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre")
FINE = r"^(PROGRAMMA|COME VEDERL|Diretta tv)"
# "eventuale" o "eventuali": la presenza italiana dipende dal turno prima.
EVENTUALE = re.compile(r"\beventual[ei]\b", re.I)


def _anno(mese, giorno, evento):
    """L'anno giusto per una data senza anno (eventi a cavallo di capodanno)."""
    for anno in sorted({evento.inizio.year, evento.fine.year}):
        try:
            d = dt.date(anno, mese, giorno)
        except ValueError:
            continue
        if evento.inizio - dt.timedelta(days=31) <= d <= evento.fine + dt.timedelta(days=31):
            return d
    raise PaginaCambiata("data %d/%d fuori dalle date dell'evento" % (giorno, mese))


def analizza(pagina, opzioni, evento):
    rr = righe(pagina)
    inizio = (opzioni.get("inizio") or "CALENDARIO ITALIANI").upper()
    try:
        i = next(n for n, r in enumerate(rr) if inizio in r.upper())
    except StopIteration:
        raise PaginaCambiata("blocco '%s' non trovato" % inizio)
    fine = re.compile(opzioni.get("fine") or FINE, re.I)
    re_giorno = re.compile(r"^(?:%s)\s+(\d{1,2})\s+(%s)\b"
                           % ("|".join(GIORNI), "|".join(MESI)), re.I)
    eventi, giorno, viste = [], None, set()
    for r in rr[i + 1:]:
        if fine.match(r):
            break
        m = re_giorno.match(r)
        if m:
            giorno = _anno(MESI.index(m.group(2).lower()) + 1,
                           int(m.group(1)), evento)
            continue
        m = re.match(r"^(\d{1,2})[.:](\d{2})\s+(.+)$", r)
        if not (m and giorno):
            continue
        ora = "%02d:%02d" % (int(m.group(1)), int(m.group(2)))
        resto = m.group(3)
        testa, atleti_txt = (resto.split(":", 1) if ":" in resto
                             else (resto, ""))
        testa = testa.strip()
        mg = re.match(r"^(.*?)\s*\((maschile|femminile|mista)\)\s*(?:,\s*(.*))?$",
                      testa, re.I)
        if mg:
            gara, genere = mg.group(1).strip(), mg.group(2).lower()
            fase = (mg.group(3) or "").strip()
        elif "," in testa:
            gara, fase = [x.strip() for x in testa.split(",", 1)]
            genere = ""
        else:
            gara, fase, genere = testa, "", ""
        fase = fase or "finale"
        eventuale = bool(EVENTUALE.search(atleti_txt))
        at = EVENTUALE.sub("", atleti_txt)
        atleti = [a.strip() for a in at.split(",") if a.strip()]
        k = chiave(gara, genere, fase)
        # Due gare con la stessa chiave avrebbero lo stesso UID e il
        # calendario ne mostrerebbe una sola.
        n = 2
        while k in viste:
            k = "%s|%d" % (chiave(gara, genere, fase), n)
            n += 1
        viste.add(k)
        eventi.append({"k": k, "data": giorno.isoformat(), "ora": ora,
                       "gara": gara, "genere": genere, "fase": fase,
                       "atleti": atleti, "eventuale": eventuale})
    minimo = int(opzioni.get("minimo_eventi", 1))
    if len(eventi) < minimo:
        raise PaginaCambiata("solo %d gare lette (ne servono almeno %d): la "
                             "pagina e' cambiata?" % (len(eventi), minimo))
    return eventi
