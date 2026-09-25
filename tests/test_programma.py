# -*- coding: utf-8 -*-
"""Parser del programma (OA Sport) e scrittura del calendario."""
import json
import os
import re

import pytest

from calendario import ics
from calendario.fusione import fondi
from calendario.parser.oasport import analizza
from calendario.rete import PaginaCambiata
from calendario.testo import pulisci, righe

from conftest import RADICE, leggi, per_titolo


def programma(evento, pagina=None):
    return analizza(pagina or leggi("oasport_programma.html"),
                    evento.programma.opzioni, evento)


def test_spazi_strani_normalizzati():
    assert pulisci("11.35\u00a0Getto\u2009del\u202fpeso") == "11.35 Getto del peso"
    assert righe("<p>11.35&nbsp;Getto</p><p>\u202f</p>") == ["11.35 Getto"]


def test_parser_ricostruisce_stato_pubblicato(evento):
    """Il parser portato nella nuova architettura legge le stesse 113 gare
    che il vecchio genera.py aveva salvato in stato.json."""
    with open(os.path.join(RADICE, "stato.json"), encoding="utf-8") as f:
        vecchio = json.load(f)
    nuovo = programma(evento)
    assert len(nuovo) == len(vecchio) == 113
    for n, v in zip(nuovo, vecchio):
        assert n["data"] == "2026-08-%02d" % v["giorno"]
        for campo in ("ora", "gara", "genere", "fase", "atleti", "eventuale"):
            assert n[campo] == v[campo], (campo, n, v)
        # stessa chiave, salvo il doppione corretto (vedi test sotto)
        assert n["k"] == v["k"] or n["k"] == v["k"] + "|2"


def test_eventuale_eventuali_in_ogni_posizione(evento):
    g = {(x["data"], x["ora"]): x for x in programma(evento)}
    # "Musci, Verteramo eventuali" e "eventuale Coiro"
    assert g[("2026-08-10", "20:03")]["atleti"] == ["Musci", "Verteramo"]
    assert g[("2026-08-10", "20:03")]["eventuale"]
    assert g[("2026-08-14", "22:45")]["atleti"] == ["Coiro"]
    assert g[("2026-08-14", "22:45")]["eventuale"]
    assert not any("ventual" in a for x in g.values() for a in x["atleti"])


def test_chiavi_doppie_non_danno_uid_doppi(evento):
    """Nel file pubblicato due batterie dei 1500 femminili avevano lo stesso
    UID (OA Sport le elencava entrambe cosi'): Calendario ne mostrava una."""
    testo = ics.genera(evento, fondi(programma(evento), [], lambda *_: None))
    uid = re.findall(r"^UID:(.*)$", testo, re.M)
    assert len(uid) == len(set(uid)) == 113
    with open(os.path.join(RADICE, "europei.ics"), encoding="utf-8") as f:
        pubblicati = re.findall(r"^UID:(.*?)\r?$", f.read(), re.M)
    assert len(pubblicati) - len(set(pubblicati)) == 1


def test_calendario_uguale_a_quello_pubblicato(evento):
    """Dallo stesso programma esce il file pubblicato su main, byte per byte,
    con due sole differenze volute: l'ora locale in descrizione e l'UID del
    doppione corretto."""
    testo = ics.genera(evento, fondi(programma(evento), [], lambda *_: None))
    with open(os.path.join(RADICE, "europei.ics"), encoding="utf-8",
              newline="") as f:
        pubblicato = f.read()
    a = pubblicato.replace("\r\n ", "").split("\r\n")
    b = [re.sub(r" \(ora locale \d\d:\d\d\)", "", r)
         for r in testo.replace("\r\n ", "").split("\r\n")]
    diverse = [(x, y) for x, y in zip(a, b) if x != y]
    assert len(a) == len(b)
    assert diverse == [("UID:ea26-b1c0e5b6777d@paolo.local",
                        "UID:ea26-b31359ff831b@paolo.local")]


def test_convenzioni_del_calendario(evento):
    testo = ics.genera(evento, fondi(programma(evento), [], lambda *_: None))
    assert testo.endswith("END:VCALENDAR\r\n")
    assert all(len(r.encode()) <= 75 for r in testo.split("\r\n"))
    # finale con italiani certi: sveglia; finale eventuale: niente sveglia
    certa = per_titolo(testo, "[F] 5000 metri (maschile) - finale")
    assert certa["SUMMARY"].endswith("| Guerra\\, Maggi\\, Parolini")
    assert certa["ALLARME"]
    incerta = per_titolo(testo, "[F] 800 metri (femminile) - finale")
    assert "(eventuale) | Coiro" in incerta["SUMMARY"]
    assert not incerta["ALLARME"]
    assert not per_titolo(testo, "[Q] Getto del peso (femminile)")["ALLARME"]
    assert per_titolo(testo, "[10] Decathlon - 100 metri")
    assert per_titolo(testo, "[SF] 100 metri (femminile)")
    assert per_titolo(testo, "[B] 800 metri (maschile)")
    ev = per_titolo(testo, "[Q] Getto del peso (femminile)")
    assert ev["DTSTART;TZID=Europe/Rome"] == "20260810T113500"
    assert ev["TRANSP"] == "TRANSPARENT"
    assert ev["DTSTAMP"] == "20260809T000000Z"
    assert "un'ora in meno (ora locale 10:35)" in ev["DESCRIPTION"]


def test_ora_locale_per_fusi_lontani(evento):
    import dataclasses
    import datetime as dt
    from zoneinfo import ZoneInfo
    from calendario.config import ITALIA
    tokyo = dataclasses.replace(evento, citta="Tokyo",
                                fuso_sede=ZoneInfo("Asia/Tokyo"))
    t = dt.datetime(2026, 8, 10, 20, 0, tzinfo=ITALIA)
    assert ics.ora_locale(tokyo, t) == ("Orario italiano. A Tokyo 7 ore in "
                                        "piu' (ora locale 03:00 del giorno dopo).")
    roma = dataclasses.replace(evento, citta="Roma", fuso_sede=ITALIA)
    assert ics.ora_locale(roma, t) == "Orario italiano, lo stesso di Roma."


def test_uid_stabili(evento):
    """L'UID dipende solo da gara+genere+fase: non da orario, atleti o
    ordine. Ed e' lo stesso del vecchio genera.py."""
    assert ics.uid(evento, "gettodelpeso|femminile|qualificazioni") == \
        "ea26-72d05c76abe2@paolo.local"
    gare = programma(evento)
    spostata = [dict(g, ora="09:00", atleti=["Altro"]) for g in reversed(gare)]
    u1 = {g["k"]: ics.uid(evento, g["k"]) for g in gare}
    u2 = {g["k"]: ics.uid(evento, g["k"]) for g in spostata}
    assert u1 == u2


def test_pagina_senza_blocco_e_cambiata(evento):
    pagina = leggi("oasport_programma.html").replace("CALENDARIO ITALIANI",
                                                     "PROGRAMMA AZZURRI")
    with pytest.raises(PaginaCambiata, match="non trovato"):
        programma(evento, pagina)


def test_pagina_con_poche_gare_e_cambiata(evento):
    pagina = re.sub(r"<p>\d{1,2}\.\d\d.*?</p>\n", "", leggi("oasport_programma.html"),
                    count=100)
    with pytest.raises(PaginaCambiata, match="gare lette"):
        programma(evento, pagina)
