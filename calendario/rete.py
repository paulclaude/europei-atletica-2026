# -*- coding: utf-8 -*-
"""Download delle pagine e i due tipi di guasto che contano.

- Irraggiungibile: la fonte non risponde. E' transitorio: si esce con 0, in
  silenzio, e si riprova al giro dopo. Il calendario resta all'ultima
  versione buona.
- PaginaCambiata: la pagina risponde ma non ha piu' la forma attesa. Va
  segnalato (uscita 1), altrimenti il calendario smette di aggiornarsi senza
  che nessuno se ne accorga.
"""
import subprocess
import time
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
TENTATIVI = 3
PAUSA = 15          # secondi fra un tentativo e l'altro
TIMEOUT = 45


class Irraggiungibile(Exception):
    """La fonte non risponde: e' transitorio, non un guasto da segnalare."""


class PaginaCambiata(Exception):
    """La fonte risponde ma la pagina non ha piu' la struttura attesa."""


def _urllib(url, minimo):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        dati = r.read()
    if len(dati) >= minimo:
        return dati.decode("utf-8", "ignore")
    raise OSError("risposta troppo corta (%d byte)" % len(dati))


def _curl(url, minimo):
    pr = subprocess.run(["curl", "-sL", "--max-time", str(TIMEOUT), "-A", UA,
                         "-H", "Accept-Language: it-IT,it", url],
                        capture_output=True)
    if pr.returncode == 0 and len(pr.stdout) >= minimo:
        return pr.stdout.decode("utf-8", "ignore")
    raise OSError("curl rc=%d, %d byte" % (pr.returncode, len(pr.stdout)))


def scarica(url, minimo=5000):
    """Scarica una pagina: 3 tentativi a 15 secondi l'uno dall'altro.

    Su GitHub Actions capita che un sito rifiuti o lasci cadere la richiesta
    (arriva da un datacenter): a Birmingham e' successo 3 volte su 20 la prima
    notte. Per ogni tentativo si prova urllib e poi curl, che alcuni siti
    trattano meglio.

    Un 404 o un 410 invece non e' rumore: l'indirizzo non esiste piu', e
    ritentare al prossimo giro non lo fara' tornare.
    """
    ultimo = None
    for tentativo in range(TENTATIVI):
        if tentativo:
            time.sleep(PAUSA)
        for metodo in (_urllib, _curl):
            try:
                return metodo(url, minimo)
            except urllib.error.HTTPError as ex:
                if ex.code in (404, 410):
                    raise PaginaCambiata("%s: HTTP %d, la pagina non esiste "
                                         "piu'" % (url, ex.code))
                ultimo = "HTTP %d" % ex.code
            except Exception as ex:
                ultimo = str(ex) or ex.__class__.__name__
    raise Irraggiungibile("%s: %s" % (url, ultimo or "motivo ignoto"))
