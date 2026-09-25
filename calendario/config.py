# -*- coding: utf-8 -*-
"""Configurazione di un evento: eventi/<nome>.yaml.

Tutto cio' che cambia da una manifestazione all'altra sta nel file YAML; il
codice resta lo stesso. Il file e' controllato qui, all'avvio, con messaggi
in italiano: un errore di battitura deve fermarsi subito e dire dove, non
produrre un calendario sbagliato.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

ITALIA = ZoneInfo("Europe/Rome")
RUOLI = ("programma", "avanzamenti")


class ConfigurazioneErrata(Exception):
    pass


@dataclass
class Fonte:
    nome: str
    ruolo: str
    parser: str
    opzioni: dict
    allarme_dopo_minuti: int | None


@dataclass
class Evento:
    percorso: str
    nome: str
    sigla: str
    dominio_uid: str
    inizio: dt.date
    fine: dt.date
    citta: str
    luogo: str
    fuso_sede: ZoneInfo
    nome_calendario: str
    prodid: str
    file_ics: str
    file_stato: str
    dtstamp: str
    aggiornamento_minuti: int
    tv: str
    sessioni: list          # [(time, time)] in ora italiana
    cron_minuti: list
    fonti: list = field(default_factory=list)
    durate: list = field(default_factory=list)      # [(regex, minuti)]

    @property
    def programma(self):
        return next(f for f in self.fonti if f.ruolo == "programma")

    @property
    def avanzamenti(self):
        return [f for f in self.fonti if f.ruolo == "avanzamenti"]


def _serve(d, chiave, dove):
    if chiave not in d or d[chiave] in (None, ""):
        raise ConfigurazioneErrata("manca '%s' in %s" % (chiave, dove))
    return d[chiave]


def _data(v, dove):
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v))
    except ValueError:
        raise ConfigurazioneErrata("%s: data non valida %r (serve AAAA-MM-GG)"
                                   % (dove, v))


def _fuso(v, dove):
    try:
        return ZoneInfo(str(v))
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigurazioneErrata("%s: fuso orario sconosciuto %r (esempi: "
                                   "Europe/London, Asia/Tokyo)" % (dove, v))


def _sessione(v):
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*-\s*(\d{1,2})[:.](\d{2})\s*",
                     str(v))
    if not m:
        raise ConfigurazioneErrata("sessione %r: scrivi per esempio "
                                   "\"19:00-23:30\"" % v)
    a = dt.time(int(m.group(1)), int(m.group(2)))
    b = dt.time(int(m.group(3)), int(m.group(4)))
    if b <= a:
        raise ConfigurazioneErrata("sessione %r: la fine deve venire dopo "
                                   "l'inizio (niente sessioni a cavallo della "
                                   "mezzanotte: usa \"23:59\")" % v)
    return a, b


def carica(percorso):
    if not os.path.exists(percorso):
        raise ConfigurazioneErrata("file di configurazione non trovato: %s"
                                   % percorso)
    with open(percorso, encoding="utf-8") as f:
        try:
            d = yaml.safe_load(f)
        except yaml.YAMLError as ex:
            raise ConfigurazioneErrata("%s non e' YAML valido: %s"
                                       % (percorso, ex))
    if not isinstance(d, dict):
        raise ConfigurazioneErrata("%s e' vuoto o malformato" % percorso)
    dove = os.path.basename(percorso)
    date = _serve(d, "date", dove)
    sede = _serve(d, "sede", dove)
    cal = _serve(d, "calendario", dove)
    inizio = _data(_serve(date, "inizio", "date"), "date.inizio")
    fine = _data(_serve(date, "fine", "date"), "date.fine")
    if fine < inizio:
        raise ConfigurazioneErrata("date: la fine viene prima dell'inizio")
    base = os.path.splitext(dove)[0]
    fonti = []
    for i, fd in enumerate(_serve(d, "fonti", dove)):
        qui = "fonti[%d]" % i
        ruolo = _serve(fd, "ruolo", qui)
        if ruolo not in RUOLI:
            raise ConfigurazioneErrata("%s: ruolo %r, deve essere uno fra %s"
                                       % (qui, ruolo, ", ".join(RUOLI)))
        soglia = fd.get("allarme_dopo_minuti")
        if soglia is not None and (not isinstance(soglia, int) or soglia <= 0):
            raise ConfigurazioneErrata("%s: allarme_dopo_minuti deve essere un "
                                       "numero intero di minuti (o null)" % qui)
        fonti.append(Fonte(nome=_serve(fd, "nome", qui), ruolo=ruolo,
                           parser=_serve(fd, "parser", qui), opzioni=fd,
                           allarme_dopo_minuti=soglia))
    if sum(f.ruolo == "programma" for f in fonti) != 1:
        raise ConfigurazioneErrata("serve esattamente una fonte con "
                                   "ruolo: programma")
    if len({f.nome for f in fonti}) != len(fonti):
        raise ConfigurazioneErrata("due fonti hanno lo stesso nome")
    from . import parser as registro   # evita l'import circolare
    for f in fonti:
        if f.parser not in registro.PARSER[f.ruolo]:
            raise ConfigurazioneErrata(
                "fonte %s: parser %r sconosciuto per il ruolo %s (disponibili:"
                " %s)" % (f.nome, f.parser, f.ruolo,
                          ", ".join(sorted(registro.PARSER[f.ruolo]))))
    for f in fonti:
        if "fuso" in f.opzioni:
            _fuso(f.opzioni["fuso"], "fonte %s" % f.nome)
    durate = []
    for regola in d.get("durate") or []:
        try:
            durate.append((re.compile(regola["se"], re.I), int(regola["minuti"])))
        except (KeyError, TypeError, ValueError, re.error):
            raise ConfigurazioneErrata("durate: ogni regola vuole 'se' (una "
                                       "espressione regolare) e 'minuti'")
    minuti = d.get("cron_minuti") or [7, 22, 37, 52]
    if not all(isinstance(m, int) and 0 <= m < 60 for m in minuti):
        raise ConfigurazioneErrata("cron_minuti: numeri da 0 a 59")
    sigla = str(_serve(d, "sigla", dove))
    if not re.fullmatch(r"[a-z0-9-]+", sigla):
        raise ConfigurazioneErrata("sigla: solo minuscole, cifre e trattini")
    return Evento(
        percorso=percorso,
        nome=_serve(d, "nome", dove),
        sigla=sigla,
        dominio_uid=d.get("dominio_uid") or "calendario.local",
        inizio=inizio, fine=fine,
        citta=_serve(sede, "citta", "sede"),
        luogo=_serve(sede, "luogo", "sede"),
        fuso_sede=_fuso(_serve(sede, "fuso", "sede"), "sede.fuso"),
        nome_calendario=_serve(cal, "nome", "calendario"),
        prodid=cal.get("prodid") or "-//Calendario azzurri//%s//IT" % d["nome"],
        file_ics=cal.get("file") or "calendari/%s.ics" % base,
        file_stato=cal.get("stato") or "stato/%s.json" % base,
        dtstamp=str(cal.get("dtstamp") or
                    inizio.strftime("%Y%m%dT000000Z")),
        aggiornamento_minuti=int(cal.get("aggiornamento_minuti") or 15),
        tv=d.get("tv") or "",
        sessioni=[_sessione(s) for s in _serve(d, "sessioni", dove)],
        cron_minuti=sorted(minuti),
        fonti=fonti,
        durate=durate,
    )
