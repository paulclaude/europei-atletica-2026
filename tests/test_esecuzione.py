# -*- coding: utf-8 -*-
"""Esecuzioni complete di `aggiorna`, con rete e API finte."""
import json
import os
import re

import pytest

from calendario import principale, rete
from calendario.rete import PaginaCambiata

from conftest import (FIXTURE, URL_DAY4, URL_HOME, URL_OA, ClientFinto, Rete,
                      leggi, leggi_file, ora_italiana, per_titolo)

MATTINA = ora_italiana("2026-08-13T15:10")     # dentro la sessione del mattino


def gira(evento, rete_finta, client=None, adesso=MATTINA, allarme=None):
    log = []
    codice = principale.aggiorna(evento, adesso=adesso, allarme=allarme,
                                 log=log.append, scarica=rete_finta,
                                 crea_client=lambda: client or ClientFinto())
    return codice, log


def test_senza_chiave_api_solo_programma(evento, senza_chiave):
    r = Rete()
    codice, log = gira(evento, r, client=pytest.fail)
    assert codice == 0
    assert r.chiamate == [URL_OA]           # la cronaca non viene nemmeno letta
    assert any("ANTHROPIC_API_KEY assente" in x for x in log)
    testo = leggi_file(evento.file_ics)
    assert "(eventuale) | Coiro" in per_titolo(testo, "[F] 800 metri (femminile)")["SUMMARY"]
    assert testo.count("BEGIN:VEVENT") == 113


def test_con_chiave_gli_avanzamenti_aggiornano_il_calendario(evento, con_chiave):
    c = ClientFinto()
    codice, log = gira(evento, Rete(), c)
    assert codice == 0, log
    assert len(c.richieste) == 2            # due articoli LIVE, uno per chiamata
    testo = leggi_file(evento.file_ics)
    assert per_titolo(testo, "[F] 800 metri (femminile)")["SUMMARY"] == \
        "[F] 800 metri (femminile) - finale | Coiro"
    assert per_titolo(testo, "[F] 3000 siepi (maschile)")["SUMMARY"].endswith(
        "finale | Bouih\\, A. Zoghlami\\, O. Zoghlami")
    assert per_titolo(testo, "[F] Salto in alto (femminile)")["SUMMARY"] \
        .endswith("| Pieroni\\, Tavernini")
    assert per_titolo(testo, "[F] 400 metri (femminile)")["SUMMARY"] \
        .endswith("finale | Polinari")
    assert per_titolo(testo, "[F] 110 ostacoli") is None       # Mulas eliminato
    assert per_titolo(testo, "[10] Decathlon - 1500 metri")["SUMMARY"] \
        .endswith("| Dester")                                  # Nonino ritirato
    assert per_titolo(testo, "[F] Lancio del disco (femminile)")["SUMMARY"] \
        .endswith("| Benedetti\\, Osakue")                     # Conte/Conti
    stato = json.loads(leggi_file(evento.file_stato))
    assert stato["versione"] == 2
    assert set(stato["articoli"]) == {URL_DAY4, URL_DAY4.replace(
        "la-mattina-del-day-4/186150", "la-serata-del-day-3/186142")}


def test_articolo_gia_letto_non_richiama_l_api(evento, con_chiave):
    gira(evento, Rete(), ClientFinto())
    c = ClientFinto()
    gira(evento, Rete(**{URL_DAY4: "fidal_live_day4_altra_pubblicita.html"}), c)
    assert c.richieste == []               # pubblicita' diversa, stesso testo
    gira(evento, Rete(**{URL_DAY4: "fidal_live_day4_aggiornato.html"}), c)
    assert len(c.richieste) == 1           # testo cambiato: si rilegge


def test_doppia_esecuzione_file_identico(evento, con_chiave):
    gira(evento, Rete())
    prima_ics, prima_stato = leggi_file(evento.file_ics), leggi_file(evento.file_stato)
    t = os.path.getmtime(evento.file_ics)
    os.utime(evento.file_ics, (t - 100, t - 100))
    codice, log = gira(evento, Rete(), adesso=ora_italiana("2026-08-13T15:40"))
    assert codice == 0
    assert "nessun cambiamento (112 eventi)" in log
    assert leggi_file(evento.file_ics) == prima_ics
    assert leggi_file(evento.file_stato) == prima_stato
    assert os.path.getmtime(evento.file_ics) == t - 100      # non riscritto


def test_cambio_orario_stesso_uid(evento, senza_chiave, tmp_path):
    gira(evento, Rete())
    prima = per_titolo(leggi_file(evento.file_ics), "[F] 800 metri (femminile)")
    spostata = tmp_path / "oa.html"
    spostata.write_text(leggi("oasport_programma.html").replace(
        "22.45 800 metri (femminile)", "22.55 800 metri (femminile)"),
        encoding="utf-8")
    codice, log = gira(evento, Rete(**{URL_OA: str(spostata)}))
    assert codice == 0
    dopo = per_titolo(leggi_file(evento.file_ics), "[F] 800 metri (femminile)")
    assert dopo["UID"] == prima["UID"]
    assert prima["DTSTART;TZID=Europe/Rome"] == "20260814T224500"
    assert dopo["DTSTART;TZID=Europe/Rome"] == "20260814T225500"
    assert leggi_file(evento.file_ics).count("BEGIN:VEVENT") == 113


def test_fonte_irraggiungibile_al_primo_giro(evento, senza_chiave):
    codice, log = gira(evento, Rete(**{URL_OA: None}))
    assert codice == 0
    assert any("momentaneamente irraggiungibile" in x for x in log)
    assert not os.path.exists(evento.file_ics)


def test_fonte_irraggiungibile_dopo_si_usa_l_ultimo_programma(evento, con_chiave):
    gira(evento, Rete(), ClientFinto())
    prima = leggi_file(evento.file_ics)
    codice, log = gira(evento, Rete(**{URL_OA: None, URL_HOME: None}))
    assert codice == 0
    assert leggi_file(evento.file_ics) == prima


def test_scarica_ritenta_tre_volte_a_15_secondi(monkeypatch):
    pause, tentativi = [], []

    def rifiuta(url, minimo):
        tentativi.append(url)
        raise OSError("Connection reset by peer")
    monkeypatch.setattr(rete.time, "sleep", pause.append)
    monkeypatch.setattr(rete, "_urllib", rifiuta)
    monkeypatch.setattr(rete, "_curl", rifiuta)
    with pytest.raises(rete.Irraggiungibile, match="Connection reset"):
        rete.scarica("https://esempio.it/")
    assert pause == [15, 15]
    assert len(tentativi) == 6               # 3 tentativi x (urllib, curl)


def test_scarica_404_e_pagina_cambiata(monkeypatch):
    import urllib.error

    def manca(url, minimo):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr(rete, "_urllib", manca)
    with pytest.raises(PaginaCambiata, match="404"):
        rete.scarica("https://esempio.it/")


def test_pagina_cambiata_nella_struttura(evento, senza_chiave, tmp_path):
    gira(evento, Rete())
    prima = leggi_file(evento.file_ics)
    rotta = tmp_path / "oa.html"
    rotta.write_text(leggi("oasport_programma.html").replace(
        "CALENDARIO ITALIANI", "GLI AZZURRI IN GARA"), encoding="utf-8")
    codice, log = gira(evento, Rete(**{URL_OA: str(rotta)}))
    assert codice == 1
    assert any(x.startswith("ERRORE") and "non trovato" in x for x in log)
    assert leggi_file(evento.file_ics) == prima


def test_indice_live_cambiato_e_segnalato_ma_il_calendario_si_aggiorna(
        evento, con_chiave, tmp_path):
    vuota = tmp_path / "home.html"
    vuota.write_text("<html><body>" + "<p>manutenzione</p>" * 300 +
                     "</body></html>", encoding="utf-8")
    codice, log = gira(evento, Rete(**{URL_HOME: str(vuota)}))
    assert codice == 1
    assert any("ERRORE: avanzamenti (fidal-live)" in x for x in log)
    assert os.path.exists(evento.file_ics)


def test_chiave_non_valida_e_segnalata(evento, con_chiave):
    import anthropic
    import httpx2
    err = anthropic.AuthenticationError(
        "invalid x-api-key", body=None, response=httpx2.Response(
            401, request=httpx2.Request("POST", "https://api.anthropic.com")))
    codice, log = gira(evento, Rete(), ClientFinto(errore=err))
    assert codice == 1
    assert any("invalid x-api-key" in x for x in log)
    assert os.path.exists(evento.file_ics)          # il programma basta


def test_errore_transitorio_api_si_riprova(evento, con_chiave):
    c = ClientFinto(risposte={"day 4": "{rotto", "day 3": "{rotto"})
    codice, log = gira(evento, Rete(), c)
    assert codice == 0
    stato = json.loads(leggi_file(evento.file_stato))
    assert stato["articoli"] == {}              # niente in cache: si riprova
    c2 = ClientFinto()
    gira(evento, Rete(), c2)
    assert len(c2.richieste) == 2


# --- freschezza --------------------------------------------------------------

def test_freschezza_sul_contenuto_estratto(evento, con_chiave, tmp_path):
    allarme = str(tmp_path / "allarme.md")
    gira(evento, Rete(), adesso=ora_italiana("2026-08-13T11:10"))
    # la pubblicita' cambia a ogni giro, il testo no: la fonte e' ferma
    altra = Rete(**{URL_DAY4: "fidal_live_day4_altra_pubblicita.html"})
    codice, _ = gira(evento, altra, adesso=ora_italiana("2026-08-13T13:30"),
                     allarme=allarme)
    assert codice == 0 and not os.path.exists(allarme)      # 140 minuti
    codice, log = gira(evento, altra, adesso=ora_italiana("2026-08-13T13:45"),
                       allarme=allarme)
    assert codice == 0                      # una fonte ferma non fa fallire
    assert os.path.exists(allarme)
    testo = leggi_file(allarme)
    assert "fidal-live" in testo and "fermo da 155 minuti di gara" in testo
    assert "oasport" not in testo           # sul programma nessun allarme
    # la fonte riparte: l'allarme sparisce (e il workflow chiude la issue)
    gira(evento, Rete(**{URL_DAY4: "fidal_live_day4_aggiornato.html"}),
         adesso=ora_italiana("2026-08-13T14:00"), allarme=allarme)
    assert not os.path.exists(allarme)


def test_niente_allarme_fuori_dalle_ore_di_gara(evento, con_chiave, tmp_path):
    allarme = str(tmp_path / "allarme.md")
    gira(evento, Rete(), adesso=ora_italiana("2026-08-13T11:10"))
    # alle 17 e' pausa; alle 19:30 contano solo 4h20 del mattino + 30 minuti
    for ora in ("2026-08-13T17:00", "2026-08-17T12:00"):
        gira(evento, Rete(), adesso=ora_italiana(ora), allarme=allarme)
        assert not os.path.exists(allarme), ora


def test_minuti_di_gara_escludono_pause_e_notti(evento):
    from calendario.orari import minuti_di_gara
    da = ora_italiana("2026-08-13T15:00")
    assert minuti_di_gara(evento, da, ora_italiana("2026-08-13T19:00")) == 30
    assert minuti_di_gara(evento, da, ora_italiana("2026-08-13T20:00")) == 90
    notte = ora_italiana("2026-08-13T23:30")
    assert minuti_di_gara(evento, notte, ora_italiana("2026-08-14T11:30")) == 59


def test_stato_del_vecchio_genera_py_viene_riscritto(evento, senza_chiave):
    with open(os.path.join(FIXTURE, "..", "..", "stato.json"),
              encoding="utf-8") as f:
        vecchio = f.read()
    with open(evento.file_stato, "w", encoding="utf-8") as f:
        f.write(vecchio)
    codice, log = gira(evento, Rete())
    assert codice == 0
    assert any("vecchio genera.py" in x for x in log)
    assert json.loads(leggi_file(evento.file_stato))["versione"] == 2


def test_log_senza_segreti(evento, con_chiave):
    _, log = gira(evento, Rete())
    assert not any(re.search(r"sk-ant", x) for x in log)


def test_senza_chiave_nessun_allarme_sulla_cronaca(evento, con_chiave,
                                                  monkeypatch, tmp_path):
    allarme = str(tmp_path / "allarme.md")
    gira(evento, Rete(), adesso=ora_italiana("2026-08-13T11:10"))
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    gira(evento, Rete(), adesso=ora_italiana("2026-08-13T15:00"), allarme=allarme)
    assert not os.path.exists(allarme)


def test_verifica_mostra_date_e_salva_il_contenuto(evento, con_chiave, tmp_path):
    log = []
    cartella = tmp_path / "verifica"
    principale.verifica(evento, str(cartella), esiti=True, log=log.append,
                        scarica=Rete(), crea_client=ClientFinto)
    testo = "\n".join(log)
    # OA Sport: solo data di pubblicazione, mai modificata -> avviso
    assert "modificata: NON INDICATO" in testo
    assert "gare lette: 113" in testo
    assert "modificata: 2026-08-13T15:05:00+02:00" in testo
    assert "-> Eloisa Coiro, 800 metri femminile semifinali: qualificato" in testo
    salvati = sorted(os.listdir(cartella))
    assert salvati == ["fidal-live-1.txt", "fidal-live-2.txt", "oasport.txt"]
    assert "2026-08-14 22:45 800 metri femminile finale: Coiro (eventuale)" in \
        (cartella / "oasport.txt").read_text(encoding="utf-8")
