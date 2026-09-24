# -*- coding: utf-8 -*-
"""Configurazione dell'evento, cron e workflow."""
import glob
import os
import re

import pytest
import yaml

from calendario.__main__ import main
from calendario.config import ConfigurazioneErrata, carica
from calendario.orari import cron

from conftest import CONFIG, RADICE

WORKFLOW = os.path.join(RADICE, ".github", "workflows", "aggiorna.yml")


def _workflow():
    with open(WORKFLOW, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_tutti_gli_eventi_si_caricano():
    file = glob.glob(os.path.join(RADICE, "eventi", "*.yaml"))
    assert file
    for f in file:
        carica(f)


def test_birmingham_ricostruita(evento):
    e = carica(CONFIG)
    assert (e.file_ics, e.file_stato) == ("europei.ics", "stato.json")
    assert e.dtstamp == "20260809T000000Z"
    assert e.sigla == "ea26" and e.dominio_uid == "paolo.local"
    assert e.programma.parser == "oasport"
    assert [f.nome for f in e.avanzamenti] == ["fidal-live"]
    assert e.tv.startswith("TV: Rai 2") and "\n" not in e.tv


def test_cron_del_workflow_coincide_con_l_evento():
    """Il cron di GitHub non puo' leggere il YAML dell'evento: il workflow
    riporta le righe generate, e questo test le tiene allineate."""
    w = _workflow()
    evento = carica(os.path.join(RADICE, w["env"]["EVENTO"]))
    # PyYAML legge la chiave "on" come True
    righe = [s["cron"] for s in w[True]["schedule"]]
    assert righe == cron(evento)


def test_cron_solo_giorni_e_ore_di_gara():
    e = carica(CONFIG)
    assert cron(e) == ["7,22,37,52 9-13,17-21 10-16 8 *"]


def test_cron_a_cavallo_di_due_mesi_e_dell_ora_solare(tmp_path):
    testo = open(CONFIG, encoding="utf-8").read()
    testo = testo.replace("inizio: 2026-08-10", "inizio: 2026-10-24") \
                 .replace("fine: 2026-08-16", "fine: 2026-11-02")
    p = tmp_path / "e.yaml"
    p.write_text(testo, encoding="utf-8")
    righe = cron(carica(str(p)))
    # il 25 ottobre finisce l'ora legale: le ore UTC si spostano di uno
    assert righe == ["7,22,37,52 9-13,17-21 24 10 *",
                     "7,22,37,52 10-14,18-22 25-31 10 *",
                     "7,22,37,52 10-14,18-22 1-2 11 *"]


def test_workflow_resta_quello_di_prima():
    """Stesso percorso del file: GitHub lo lega allo stato "disabilitato"."""
    w = _workflow()
    assert os.path.basename(WORKFLOW) == "aggiorna.yml"
    assert "workflow_dispatch" in w[True]
    passi = " ".join(s.get("run", "") for s in w["jobs"]["aggiorna"]["steps"])
    assert 'python -m calendario aggiorna "$EVENTO"' in passi


@pytest.mark.parametrize("modifica, messaggio", [
    (("sigla: ea26", "sigla: EA 26"), "sigla"),
    (("fuso: Europe/London", "fuso: Europa/Londra"), "fuso orario sconosciuto"),
    (("fine: 2026-08-16", "fine: 2026-08-01"), "fine viene prima"),
    (("parser: oasport", "parser: oa-sport"), "parser 'oa-sport' sconosciuto"),
    (('- "11:00-15:30"', '- "15:30-11:00"'), "la fine deve venire dopo"),
    (("ruolo: avanzamenti", "ruolo: programma"), "esattamente una fonte"),
    (("allarme_dopo_minuti: 150", "allarme_dopo_minuti: tanti"), "minuti"),
])
def test_errori_di_configurazione_chiari(tmp_path, modifica, messaggio):
    testo = open(CONFIG, encoding="utf-8").read()
    assert modifica[0] in testo
    p = tmp_path / "e.yaml"
    p.write_text(testo.replace(modifica[0], modifica[1], 1), encoding="utf-8")
    with pytest.raises(ConfigurazioneErrata, match=messaggio):
        carica(str(p))


def test_comando_con_configurazione_errata_esce_con_1(capsys):
    assert main(["cron", "eventi/non-esiste.yaml"]) == 1
    assert "non trovato" in capsys.readouterr().err


def test_comando_file(capsys):
    assert main(["file", CONFIG]) == 0
    assert capsys.readouterr().out.split() == ["europei.ics", "stato.json"]


def test_modello_esempio_valido():
    """Il modello per un evento nuovo, in eventi/, deve restare caricabile."""
    esempi = [f for f in glob.glob(os.path.join(RADICE, "eventi", "*.yaml"))
              if "esempio" in f]
    assert esempi
    e = carica(esempi[0])
    assert e.file_ics.startswith("calendari/")
    assert not re.search(r"ea26", e.sigla)
