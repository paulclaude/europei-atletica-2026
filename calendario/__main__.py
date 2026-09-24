# -*- coding: utf-8 -*-
"""Uso:

    python -m calendario aggiorna eventi/NOME.yaml [--allarme FILE]
    python -m calendario verifica eventi/NOME.yaml [--salva CARTELLA] [--esiti]
    python -m calendario cron     eventi/NOME.yaml
    python -m calendario file     eventi/NOME.yaml
"""
import argparse
import sys

from . import orari, principale
from .config import ConfigurazioneErrata, carica


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m calendario",
                                description="Calendario delle gare degli "
                                "italiani, da un file di configurazione.")
    sub = p.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("aggiorna", help="rigenera calendario e stato")
    a.add_argument("evento")
    a.add_argument("--allarme", help="file dove scrivere l'avviso di fonte "
                   "ferma (lo usa il workflow per aprire una issue)")
    v = sub.add_parser("verifica", help="mostra che cosa si estrae dalle fonti")
    v.add_argument("evento")
    v.add_argument("--salva", metavar="CARTELLA",
                   help="salva i testi estratti, per confrontarli dopo")
    v.add_argument("--esiti", action="store_true",
                   help="legge anche gli esiti con l'API (serve la chiave)")
    c = sub.add_parser("cron", help="righe cron per il workflow")
    c.add_argument("evento")
    f = sub.add_parser("file", help="file prodotti (per git add)")
    f.add_argument("evento")
    args = p.parse_args(argv)
    try:
        evento = carica(args.evento)
    except ConfigurazioneErrata as ex:
        print("ERRORE di configurazione: %s" % ex, file=sys.stderr)
        return 1
    if args.comando == "aggiorna":
        return principale.aggiorna(evento, allarme=args.allarme)
    if args.comando == "verifica":
        return principale.verifica(evento, args.salva, args.esiti)
    if args.comando == "cron":
        print("\n".join(orari.cron(evento)))
        return 0
    print(evento.file_ics)
    print(evento.file_stato)
    return 0


if __name__ == "__main__":
    sys.exit(main())
