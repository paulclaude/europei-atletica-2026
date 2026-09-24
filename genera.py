#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibilita' con il vecchio comando `python genera.py`.

Il generatore ora vive nel pacchetto `calendario` e legge la configurazione
da eventi/<nome>.yaml. Senza argomenti rigenera Birmingham 2026:

    python genera.py                         # = eventi/birmingham-2026.yaml
    python genera.py eventi/ALTRO.yaml
"""
import sys

from calendario.__main__ import main

if __name__ == "__main__":
    evento = sys.argv[1] if len(sys.argv) > 1 else "eventi/birmingham-2026.yaml"
    sys.exit(main(["aggiorna", evento] + sys.argv[2:]))
