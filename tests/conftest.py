# -*- coding: utf-8 -*-
"""Strumenti comuni ai test: niente rete, niente API vera."""
import dataclasses
import datetime as dt
import json
import os
import sys
from types import SimpleNamespace

import pytest

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)

from calendario.config import ITALIA, carica  # noqa: E402
from calendario.rete import Irraggiungibile  # noqa: E402

FIXTURE = os.path.join(RADICE, "tests", "fixtures")
CONFIG = os.path.join(RADICE, "eventi", "birmingham-2026.yaml")

URL_OA = ("https://www.oasport.it/2026/08/europei-atletica-2026-gli-italiani-"
          "in-gara-giorno-per-giorno-orari-e-dove-vederli-in-tv/")
URL_HOME = "https://www.fidal.it/"
URL_DAY4 = "https://www.fidal.it/content/LIVE-Birmingham-la-mattina-del-day-4/186150"
URL_DAY3 = "https://www.fidal.it/content/LIVE-Birmingham-la-serata-del-day-3/186142"


def leggi(nome):
    with open(os.path.join(FIXTURE, nome), encoding="utf-8") as f:
        return f.read()


def ora_italiana(testo):
    return dt.datetime.fromisoformat(testo).replace(tzinfo=ITALIA)


class Rete:
    """Finta rete: indirizzo -> fixture. None = irraggiungibile."""

    def __init__(self, **pagine):
        self.pagine = {URL_OA: "oasport_programma.html",
                       URL_HOME: "fidal_home.html",
                       URL_DAY4: "fidal_live_day4.html",
                       URL_DAY3: "fidal_live_day3.html"}
        self.pagine.update(pagine)
        self.chiamate = []

    def __call__(self, url, minimo=5000):
        self.chiamate.append(url)
        nome = self.pagine.get(url)
        if nome is None:
            raise Irraggiungibile("%s: connessione rifiutata" % url)
        if isinstance(nome, Exception):
            raise nome
        return leggi(nome)


class ClientFinto:
    """Imita anthropic.Anthropic: risponde con gli esiti in fixture, scelti
    in base al titolo dell'articolo presente nella richiesta."""

    def __init__(self, risposte=None, stop_reason="end_turn", errore=None):
        self.risposte = risposte or {
            "la mattina del day 4": leggi("esiti_day4.json"),
            "la serata del day 3": leggi("esiti_day3.json"),
        }
        self.stop_reason = stop_reason
        self.errore = errore
        self.richieste = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crea))
        self.messages = SimpleNamespace(create=self._crea)

    def _crea(self, **par):
        self.richieste.append(par)
        if self.errore:
            raise self.errore
        testo = par["messages"][0]["content"]
        risposta = next((v for k, v in self.risposte.items() if k in testo),
                        json.dumps({"esiti": []}))
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=risposta)])


@pytest.fixture
def evento(tmp_path):
    e = carica(CONFIG)
    return dataclasses.replace(e, file_ics=str(tmp_path / "europei.ics"),
                               file_stato=str(tmp_path / "stato.json"))


@pytest.fixture
def senza_chiave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def con_chiave(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-finta")


def leggi_file(percorso):
    with open(percorso, encoding="utf-8", newline="") as f:
        return f.read()


def eventi_ics(testo):
    """VEVENT del calendario come dizionari (righe ripiegate riunite)."""
    righe = testo.replace("\r\n ", "").split("\r\n")
    out, cor = [], None
    for r in righe:
        if r == "BEGIN:VEVENT":
            cor = {"ALLARME": False}
        elif r == "END:VEVENT":
            out.append(cor)
            cor = None
        elif cor is not None:
            if r == "BEGIN:VALARM":
                cor["ALLARME"] = True
            k, _, v = r.partition(":")
            cor.setdefault(k, v)
    return out


def per_titolo(testo, inizio_titolo):
    """L'unico evento il cui SUMMARY comincia con `inizio_titolo`."""
    ev = [e for e in eventi_ics(testo) if e["SUMMARY"].startswith(inizio_titolo)]
    assert len(ev) <= 1, [e["SUMMARY"] for e in ev]
    return ev[0] if ev else None
