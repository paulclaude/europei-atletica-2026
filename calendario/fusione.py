# -*- coding: utf-8 -*-
"""Fusione: gli avanzamenti letti dalla cronaca aggiornano le gare del
programma.

Un esito dice che cosa e' successo a un atleta in un turno ("fase"):

- qualificato   passa al turno dopo: in quel turno la presenza italiana e'
                confermata e sparisce "(eventuale)"
- eliminato, squalificato, ritirato, infortunato
                non disputera' i turni successivi: viene tolto da quelli
- non_partente  non prende il via proprio nel turno indicato (forfait,
                rinuncia): viene tolto da quel turno e dai successivi

Una gara che resta senza italiani sparisce dal calendario. Le gare gia'
disputate non vengono toccate da un'eliminazione: un'eliminazione in
batteria svuota semifinale e finale, non la batteria.
"""
import re

from .nomi import normalizza, stessa_gara, trova_atleta

ESITI = ("qualificato", "eliminato", "squalificato", "ritirato", "infortunato",
         "non_partente")
_TOGLIE_DOPO = {"eliminato", "squalificato", "ritirato", "infortunato"}
# Rango dei turni, per quando il turno citato dalla cronaca non compare nel
# programma (per esempio una batteria senza italiani annunciati).
_RANGHI = ((r"semifinal", 2), (r"finale", 3),
           (r"batteri|qualificazion|ripescagg|preliminar|primo turno", 1))


def rango(fase):
    f = normalizza(fase)
    for regex, r in _RANGHI:
        if re.search(regex, f):
            return r
    return None


def stessa_fase(a, b):
    ra, rb = rango(a), rango(b)
    if ra is not None and rb is not None:
        return ra == rb
    return stessa_gara(a, b)


def _compatibile(genere_programma, genere_esito):
    # Il programma a volte non indica il genere ("110 ostacoli"): va bene.
    return not genere_programma or not genere_esito or \
        genere_programma == genere_esito


def _quando(g):
    return (g["data"], g["ora"])


def fondi(programma, esiti, log=print):
    """Restituisce le gare del calendario: quelle del programma, con gli
    atleti eliminati tolti, le conferme segnate in "confermati" e senza le
    gare rimaste vuote. Non modifica `programma`."""
    via = [set() for _ in programma]
    ok = [set() for _ in programma]
    for e in esiti:
        descr = "%s, %s %s %s: %s" % (e["atleta"], e["gara"], e["genere"],
                                      e["fase"], e["esito"])
        stesse = [i for i, g in enumerate(programma)
                  if stessa_gara(g["gara"], e["gara"])
                  and _compatibile(g["genere"], e["genere"])]
        con = []
        for i in stesse:
            a = trova_atleta(programma[i]["atleti"], e["atleta"])
            if a is not None:
                con.append((i, programma[i]["atleti"][a]))
        if not con:
            log("  esito non abbinato a nessuna gara del programma (%s)" % descr)
            continue
        rif = sorted((x for x in con if stessa_fase(programma[x[0]]["fase"],
                                                    e["fase"])),
                     key=lambda x: _quando(programma[x[0]]))
        if rif:
            t0 = _quando(programma[rif[0][0]])
            successive = [x for x in con if _quando(programma[x[0]]) > t0]
        else:
            r0 = rango(e["fase"])
            if r0 is None:
                log("  esito con turno non riconosciuto, ignorato (%s)" % descr)
                continue
            successive = [x for x in con
                          if (rango(programma[x[0]]["fase"]) or 0) > r0]
        successive.sort(key=lambda x: _quando(programma[x[0]]))
        if e["esito"] == "qualificato":
            if successive:
                i, nome = successive[0]
                ok[i].add(nome)
            else:
                log("  qualificato ma nessun turno successivo nel programma "
                    "(%s)" % descr)
        elif e["esito"] in _TOGLIE_DOPO:
            for i, nome in successive:
                via[i].add(nome)
        elif e["esito"] == "non_partente":
            for i, nome in rif[:1] + successive:
                via[i].add(nome)
    out = []
    for i, g in enumerate(programma):
        atleti = [a for a in g["atleti"] if a not in via[i]]
        if g["atleti"] and not atleti:
            log("  tolta, nessun italiano rimasto: %s %s %s del %s"
                % (g["gara"], g["genere"], g["fase"], g["data"]))
            continue
        out.append(dict(g, atleti=atleti,
                        confermati=[a for a in atleti if a in ok[i]]))
    return out
