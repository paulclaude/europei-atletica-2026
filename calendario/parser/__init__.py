# -*- coding: utf-8 -*-
"""Registro dei parser, per ruolo.

Per aggiungere una fonte nuova si scrive un modulo in questa cartella e lo si
registra qui sotto:

- ruolo "programma": una funzione analizza(pagina, opzioni, evento) che
  restituisce una lista di gare, ciascuna con k, data (AAAA-MM-GG), ora
  (HH:MM nel fuso della fonte), gara, genere, fase, atleti, eventuale.
  Se la pagina non ha la forma attesa solleva rete.PaginaCambiata.
- ruolo "avanzamenti": una funzione articoli(opzioni, evento, scarica, log)
  che restituisce una lista di articoli {url, titolo, testo, impronta}.
"""
from . import articoli_live, oasport

PARSER = {
    "programma": {"oasport": oasport.analizza},
    "avanzamenti": {"articoli_live": articoli_live.articoli},
}
