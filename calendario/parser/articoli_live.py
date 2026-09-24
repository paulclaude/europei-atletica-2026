# -*- coding: utf-8 -*-
"""Articoli "LIVE" in prosa, trovati a partire da una pagina indice.

Pensato per la FIDAL (fidal.it), che durante gli Europei di Birmingham
pubblicava in home articoli come "LIVE Birmingham: la mattina del day 4",
aggiornati durante la sessione. Funziona con qualunque sito che linki i suoi
articoli da una pagina indice: basta cambiare le opzioni.

Opzioni nel file dell'evento:
    indice          pagina da cui partire (per esempio la home)
    titolo          regex che il testo del link deve contenere ("LIVE")
    filtro_url      regex che l'indirizzo del link deve contenere
    massimo_articoli  quanti link al massimo seguire a ogni giro
    articoli_fissi  indirizzi da leggere sempre, anche se spariscono
                    dall'indice
    minimo_caratteri  sotto questa lunghezza il corpo estratto e' sospetto

Il parser NON interpreta la prosa: restituisce titolo e testo pulito di ogni
articolo. A capire chi e' passato e chi e' uscito ci pensa avanzamenti.py.
"""
import re
from urllib.parse import urljoin

from ..rete import Irraggiungibile, PaginaCambiata
from ..testo import analizza_pagina, collegamenti, impronta


def trova_link(pagina, opzioni):
    """Link agli articoli live nella pagina indice, senza doppioni."""
    base = opzioni["indice"]
    filtro = re.compile(opzioni.get("filtro_url") or ".", re.I)
    titolo = re.compile(opzioni.get("titolo") or "LIVE", re.I)
    tutti = [(urljoin(base, h), t) for h, t in collegamenti(pagina)
             if h and not h.startswith(("#", "mailto:", "javascript:"))]
    candidati = [(h, t) for h, t in tutti if filtro.search(h)]
    if not candidati:
        # Nessun link del tipo atteso: non e' "oggi non ci sono articoli
        # live", e' l'indice che ha cambiato forma.
        raise PaginaCambiata("nessun link che corrisponda a %r in %s"
                             % (filtro.pattern, base))
    visti, scelti = set(), []
    for h, t in candidati:
        if titolo.search(t) and h not in visti:
            visti.add(h)
            scelti.append((h, t))
    return scelti[:int(opzioni.get("massimo_articoli") or 8)]


def articoli(opzioni, evento, scarica, log=print):
    """Scarica l'indice e gli articoli. Un articolo irraggiungibile viene
    saltato (restano validi i suoi esiti gia' letti); un indice
    irraggiungibile fa saltare tutta la fonte per questo giro."""
    indice = scarica(opzioni["indice"], minimo=2000)
    link = trova_link(indice, opzioni)
    for u in opzioni.get("articoli_fissi") or []:
        if u not in [h for h, _ in link]:
            link.append((u, ""))
    minimo = int(opzioni.get("minimo_caratteri") or 300)
    out = []
    for url, testo_link in link:
        try:
            pagina = scarica(url, minimo=2000)
        except Irraggiungibile as ex:
            log("  articolo irraggiungibile, lo salto per ora: %s" % ex)
            out.append({"url": url, "titolo": testo_link, "irraggiungibile": True})
            continue
        a = analizza_pagina(pagina, minimo)
        if len(a["corpo"]) < minimo:
            log("  attenzione: corpo di soli %d caratteri in %s"
                % (len(a["corpo"]), url))
        out.append({"url": url, "titolo": a["titolo"] or testo_link,
                    "testo": a["corpo"], "impronta": impronta(a["corpo"]),
                    "pubblicato": a["pubblicato"], "modificato": a["modificato"],
                    "metodo": a["metodo"]})
    return out
