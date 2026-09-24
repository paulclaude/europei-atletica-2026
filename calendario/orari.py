# -*- coding: utf-8 -*-
"""Ore di gara: servono al cron di GitHub e al controllo di freschezza.

Il cron di GitHub non e' puntuale: con "*/15" a Birmingham sono stati
misurati intervalli fra 29 e 149 minuti. Le esecuzioni a inizio ora e ai
quarti sono le piu' contese; minuti sfalsati (7, 22, 37, 52) e le sole ore
di gara riducono i ritardi e non consumano esecuzioni quando non serve.
"""
import datetime as dt

from .config import ITALIA

UTC = dt.timezone.utc


def _giorni(evento):
    d = evento.inizio
    while d <= evento.fine:
        yield d
        d += dt.timedelta(days=1)


def finestre(evento):
    """Le finestre di gara come coppie di datetime (ora italiana)."""
    for d in _giorni(evento):
        for a, b in evento.sessioni:
            yield (dt.datetime.combine(d, a, tzinfo=ITALIA),
                   dt.datetime.combine(d, b, tzinfo=ITALIA))


def in_gara(evento, adesso):
    return any(a <= adesso < b for a, b in finestre(evento))


def minuti_di_gara(evento, da, a):
    """Minuti di gara trascorsi fra `da` e `a`: le pause fra le sessioni e
    le notti non contano. Senza questo, alle 20 la cronaca ferma dalle 15
    sembrerebbe morta da cinque ore."""
    tot = 0.0
    for x, y in finestre(evento):
        inizio, fine = max(x, da), min(y, a)
        if fine > inizio:
            tot += (fine - inizio).total_seconds() / 60
    return int(tot)


def _intervalli(numeri):
    numeri = sorted(set(numeri))
    out, i = [], 0
    while i < len(numeri):
        j = i
        while j + 1 < len(numeri) and numeri[j + 1] == numeri[j] + 1:
            j += 1
        out.append(str(numeri[i]) if i == j else "%d-%d" % (numeri[i], numeri[j]))
        i = j + 1
    return ",".join(out)


def cron(evento):
    """Righe cron (UTC) che coprono le sessioni, solo nei giorni dell'evento.

    Il risultato va copiato in .github/workflows/aggiorna.yml: un test
    controlla che le due cose coincidano.
    """
    ore = {}                     # data UTC -> ore UTC
    for a, b in finestre(evento):
        t = a.astimezone(UTC).replace(minute=0)
        fine = b.astimezone(UTC)
        while t < fine:
            ore.setdefault(t.date(), set()).add(t.hour)
            t += dt.timedelta(hours=1)
    # Giorni consecutivi dello stesso mese con le stesse ore: una riga sola.
    righe, gruppo = [], []
    for d in sorted(ore):
        if gruppo and (d.month != gruppo[-1].month or
                       d - gruppo[-1] != dt.timedelta(days=1) or
                       ore[d] != ore[gruppo[-1]]):
            righe.append(gruppo)
            gruppo = []
        gruppo.append(d)
    if gruppo:
        righe.append(gruppo)
    minuti = ",".join(str(m) for m in evento.cron_minuti)
    return ["%s %s %s %d *" % (minuti, _intervalli(ore[g[0]]),
                               _intervalli(d.day for d in g), g[0].month)
            for g in righe]
