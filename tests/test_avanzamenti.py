# -*- coding: utf-8 -*-
"""Nomi tolleranti, fusione degli esiti, lettura via API (finta)."""
import json

import pytest

from calendario import avanzamenti as av
from calendario import ics
from calendario.fusione import fondi
from calendario.nomi import stessa_gara, stesso_atleta, trova_atleta
from calendario.parser.oasport import analizza

from conftest import ClientFinto, leggi, per_titolo

zitto = lambda *_: None  # noqa: E731


@pytest.fixture
def gare(evento):
    return analizza(leggi("oasport_programma.html"), evento.programma.opzioni,
                    evento)


def esito(atleta, gara, genere, fase, e):
    return {"atleta": atleta, "gara": gara, "genere": genere, "fase": fase,
            "esito": e, "citazione": ""}


def cal(evento, gare, esiti):
    return ics.genera(evento, fondi(gare, esiti, zitto))


# --- nomi ------------------------------------------------------------------

@pytest.mark.parametrize("programma, cronaca", [
    ("Conti", "Conte"), ("Conte", "Conti"),            # refusi di Birmingham
    ("Oliveri", "Olivieri"), ("Olivieri", "Oliveri"),
    ("Tamberi", "Gianmarco Tamberi"), ("Tamberi", "TAMBERI Gianmarco"),
    ("Del Buono", "Federica Del Buono"), ("Alì", "Chituru Ali"),
    ("O. Zoghlami", "Osama Zoghlami"), ("A. Zoghlami", "Ala Zoghlami"),
    ("A. Zoghlami", "A. Zoghlami"), ("Italia", "Italia"),
])
def test_stesso_atleta(programma, cronaca):
    assert stesso_atleta(programma, cronaca)


@pytest.mark.parametrize("programma, cronaca", [
    ("A. Zoghlami", "Osama Zoghlami"), ("Fina", "Fino"), ("Sito", "Sioli"),
    ("Musci", "Mulas"), ("Dosso", "Desalu"),
])
def test_atleti_diversi(programma, cronaca):
    assert not stesso_atleta(programma, cronaca)


def test_omonimi_ambigui_non_si_sceglie_a_caso():
    atleti = ["Bouih", "A. Zoghlami", "O. Zoghlami"]
    assert trova_atleta(atleti, "Zoghlami") is None
    assert trova_atleta(atleti, "Osama Zoghlami") == 2


def test_gare_tolleranti():
    assert stessa_gara("4×400", "4x400")
    assert stessa_gara("Salto con l’asta", "salto con l'asta")
    assert stessa_gara("400 ostacoli", "400 hs")
    assert stessa_gara("100 metri", "100m")
    assert stessa_gara("Lancio del martelo", "Lancio del martello")
    assert not stessa_gara("100 ostacoli", "400 ostacoli")
    assert not stessa_gara("100 metri", "200 metri")


# --- fusione ---------------------------------------------------------------

def test_qualificazione_toglie_eventuale_e_mette_la_sveglia(evento, gare):
    prima = per_titolo(cal(evento, gare, []), "[F] 800 metri (femminile)")
    assert "(eventuale)" in prima["SUMMARY"] and not prima["ALLARME"]
    dopo = per_titolo(cal(evento, gare, [esito(
        "Eloisa Coiro", "800 metri", "femminile", "semifinali", "qualificato")]),
        "[F] 800 metri (femminile)")
    assert dopo["SUMMARY"] == "[F] 800 metri (femminile) - finale | Coiro"
    assert dopo["ALLARME"]
    assert dopo["UID"] == prima["UID"]
    assert "Presenza italiana confermata: Coiro." in dopo["DESCRIPTION"]


def test_qualificazione_parziale(evento, gare):
    testo = cal(evento, gare, [esito("Kaddari", "200 metri", "femminile",
                                     "semifinali", "qualificato")])
    ev = per_titolo(testo, "[F] 200 metri (femminile)")
    assert "(eventuale)" not in ev["SUMMARY"]
    assert "Ancora da decidere nel turno precedente: Cambiolo\\, Fontana" \
        in ev["DESCRIPTION"]


def test_eliminazione_toglie_l_atleta_dai_turni_successivi(evento, gare):
    testo = cal(evento, gare, [
        esito("Frattini", "Tiro del giavellotto", "maschile", "qualificazioni",
              "qualificato"),
        esito("Fina", "Tiro del giavellotto", "maschile", "qualificazioni",
              "eliminato")])
    ev = per_titolo(testo, "[F] Tiro del giavellotto (maschile)")
    assert ev["SUMMARY"] == "[F] Tiro del giavellotto (maschile) - finale | Frattini"
    # la qualificazione gia' disputata non cambia
    q = per_titolo(testo, "[Q] Tiro del giavellotto (maschile)")
    assert q["SUMMARY"].endswith("| Fina\\, Frattini")


def test_eliminazione_con_refuso_nel_programma(evento, gare):
    """Qualificazioni: "Conte"; finale: "Conti". E' la stessa atleta."""
    testo = cal(evento, gare, [esito("Conte", "Lancio del disco", "femminile",
                                     "qualificazioni", "eliminato")])
    ev = per_titolo(testo, "[F] Lancio del disco (femminile)")
    assert ev["SUMMARY"].endswith("| Benedetti\\, Osakue")


def test_eliminazione_di_tutti_toglie_la_gara(evento, gare):
    esiti = [esito("Mulas", "110 ostacoli", "maschile", "semifinali", "eliminato")]
    testo = cal(evento, gare, esiti)
    assert per_titolo(testo, "[F] 110 ostacoli") is None
    assert per_titolo(testo, "[SF] 110 ostacoli") is not None
    assert len(fondi(gare, esiti, zitto)) == len(gare) - 1


def test_eliminazione_in_batteria_svuota_semifinale_e_finale(evento, gare):
    esiti = [esito(a, "400 metri", "femminile", "batterie", "eliminato")
             for a in ("Bonora", "Mangione")]
    testo = cal(evento, gare, esiti)
    assert per_titolo(testo, "[SF] 400 metri (femminile)")["SUMMARY"] \
        .endswith("| Polinari")
    assert per_titolo(testo, "[F] 400 metri (femminile)")["SUMMARY"] \
        .endswith("| Polinari")
    assert per_titolo(testo, "[B] 400 metri (femminile)")["SUMMARY"] \
        .endswith("| Bonora\\, Mangione")


def test_ritiro_nelle_prove_multiple(evento, gare):
    testo = cal(evento, gare, [esito("Nonino", "Decathlon", "",
                                     "salto con l'asta", "ritirato")])
    assert per_titolo(testo, "[10] Decathlon - tiro del giavellotto")["SUMMARY"] \
        .endswith("| Dester")
    assert per_titolo(testo, "[10] Decathlon - 1500 metri")["SUMMARY"] \
        .endswith("| Dester")
    # le prove gia' disputate restano com'erano
    assert per_titolo(testo, "[10] Decathlon - salto con l’asta")["SUMMARY"] \
        .endswith("| Dester\\, Nonino")


def test_non_partente_esce_anche_dal_turno_indicato(evento, gare):
    testo = cal(evento, gare, [esito("Tamberi", "Salto in alto", "maschile",
                                     "finale", "non_partente"),
                               esito("Gianmarco Tamberi", "Salto in alto",
                                     "maschile", "finale", "infortunato")])
    ev = per_titolo(testo, "[F] Salto in alto (maschile)")
    assert ev["SUMMARY"].endswith("| Falocchi\\, Sioli\\, Stronati")


def test_esiti_non_abbinati_sono_ignorati(evento, gare):
    log = []
    fondi(gare, [esito("Warholm", "400 ostacoli", "maschile", "finale",
                       "qualificato")], log.append)
    assert any("non abbinato" in r for r in log)


def test_turno_citato_assente_dal_programma(evento, gare):
    """Batteria dei 200 donne: nel programma c'e', ma se mancasse si usa il
    rango del turno."""
    senza_batterie = [g for g in gare if not (g["gara"] == "200 metri" and
                                              g["fase"] == "batterie")]
    out = fondi(senza_batterie, [esito("Fontana", "200 metri", "femminile",
                                       "batterie", "eliminato")], zitto)
    sf = next(g for g in out if g["gara"] == "200 metri" and
              g["fase"] == "semifinali" and g["genere"] == "femminile")
    assert sf["atleti"] == ["Cambiolo", "Kaddari"]


# --- lettura via API (finta) -------------------------------------------------

ARTICOLO = {"url": "https://x/1", "titolo": "LIVE Birmingham: la mattina del "
            "day 4", "testo": "Eloisa Coiro e' in finale.", "impronta": "x"}


def test_richiesta_con_schema_e_programma(evento, gare):
    par = av.richiesta(ARTICOLO, gare, evento, {"modello": "claude-opus-5"})
    assert par["model"] == "claude-opus-5"
    assert par["output_config"]["format"] == {"type": "json_schema",
                                              "schema": av.SCHEMA}
    assert par["fallbacks"] == "default"
    istruzioni, gare_ = par["system"]
    assert "qualificato" in istruzioni["text"]
    assert "gara: 800 metri | genere: femminile | fase: finale" in gare_["text"]
    assert gare_["cache_control"] == {"type": "ephemeral"}
    assert "Eloisa Coiro e' in finale." in par["messages"][0]["content"]


def test_risposta_validata(evento, gare):
    c = ClientFinto()
    r = av.estrai_esiti(c, ARTICOLO, gare, evento, {})
    assert len(r["esiti"]) == 15
    assert c.richieste[0]["betas"] == [av.BETA_RIPIEGO]


@pytest.mark.parametrize("risposta", [
    "non e' JSON",
    json.dumps({"esiti": [{"atleta": "Coiro"}]}),
    json.dumps({"esiti": [dict(json.loads(leggi("esiti_day4.json"))["esiti"][0],
                               esito="promosso")]}),
    json.dumps({"esiti": [], "commento": "extra"}),
])
def test_risposta_non_valida_e_transitoria(evento, gare, risposta):
    c = ClientFinto(risposte={"day 4": risposta})
    with pytest.raises(av.ErroreTransitorio):
        av.estrai_esiti(c, ARTICOLO, gare, evento, {})


def test_rifiuto_e_troncamento(evento, gare):
    r = av.estrai_esiti(ClientFinto(stop_reason="refusal"), ARTICOLO, gare,
                        evento, {})
    assert r == {"esiti": [], "rifiutato": True}
    with pytest.raises(av.ErroreTransitorio):
        av.estrai_esiti(ClientFinto(stop_reason="max_tokens"), ARTICOLO, gare,
                        evento, {})


def _errore_api(classe, codice):
    import anthropic
    import httpx2
    risposta = httpx2.Response(codice, request=httpx2.Request(
        "POST", "https://api.anthropic.com/v1/messages"))
    return classe("errore finto", response=risposta, body=None)


def test_errori_api(evento, gare):
    import anthropic
    grave = ClientFinto(errore=_errore_api(anthropic.AuthenticationError, 401))
    with pytest.raises(av.ErroreGrave):
        av.estrai_esiti(grave, ARTICOLO, gare, evento, {})
    lento = ClientFinto(errore=_errore_api(anthropic.RateLimitError, 429))
    with pytest.raises(av.ErroreTransitorio):
        av.estrai_esiti(lento, ARTICOLO, gare, evento, {})
    guasto = ClientFinto(errore=_errore_api(anthropic.InternalServerError, 529))
    with pytest.raises(av.ErroreTransitorio):
        av.estrai_esiti(guasto, ARTICOLO, gare, evento, {})
