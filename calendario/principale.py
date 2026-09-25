# -*- coding: utf-8 -*-
"""Un giro completo: programma, avanzamenti, fusione, calendario, freschezza.

Codici di uscita:
    0  tutto bene, oppure fonte momentaneamente irraggiungibile (si riprova
       al giro dopo, in silenzio)
    1  qualcosa va sistemato a mano: pagina cambiata nella struttura, chiave
       API non valida, configurazione errata. Su GitHub il job fallisce e
       arriva la mail.

Una fonte ferma da troppo tempo durante le ore di gara non fa fallire il
job: se viene passato --allarme, si scrive li' un testo in Markdown e il
workflow apre una issue (e la chiude quando la fonte riparte).
"""
import datetime as dt
import json
import os

from . import avanzamenti as av
from . import ics, orari
from .config import ITALIA
from .fusione import fondi
from .parser import PARSER
from .rete import Irraggiungibile, PaginaCambiata, scarica
from .testo import impronta

VERSIONE_STATO = 2


def carica_stato(percorso, log=print):
    if not os.path.exists(percorso):
        return {}
    try:
        with open(percorso, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError) as ex:
        log("stato illeggibile (%s): riparto da zero" % ex)
        return {}
    if not isinstance(s, dict) or s.get("versione") != VERSIONE_STATO:
        # Il vecchio genera.py salvava solo la lista delle gare.
        log("stato nel formato del vecchio genera.py: al primo giro riuscito "
            "verra' riscritto nel formato nuovo")
        return {}
    return s


def _json(dati):
    return json.dumps(dati, ensure_ascii=False, indent=1) + "\n"


def scrivi_se_diverso(percorso, testo):
    """Scrive solo se il contenuto cambia: niente commit a vuoto."""
    if os.path.exists(percorso):
        with open(percorso, encoding="utf-8", newline="") as f:
            if f.read() == testo:
                return False
    cartella = os.path.dirname(percorso)
    if cartella:
        os.makedirs(cartella, exist_ok=True)
    with open(percorso, "w", encoding="utf-8", newline="") as f:
        f.write(testo)
    return True


def in_ora_italiana(gare, fuso):
    """Gli orari della fonte (nel suo fuso) portati all'ora italiana."""
    if fuso is None or str(fuso) == "Europe/Rome":
        return gare
    from zoneinfo import ZoneInfo
    z = ZoneInfo(str(fuso))
    out = []
    for g in gare:
        t = dt.datetime.fromisoformat("%sT%s" % (g["data"], g["ora"]))
        t = t.replace(tzinfo=z).astimezone(ITALIA)
        out.append(dict(g, data=t.date().isoformat(), ora=t.strftime("%H:%M")))
    return out


def leggi_programma(evento, scarica=scarica):
    f = evento.programma
    pagina = scarica(f.opzioni["url"])
    gare = PARSER["programma"][f.parser](pagina, f.opzioni, evento)
    return in_ora_italiana(gare, f.opzioni.get("fuso"))


def _freschezza(fonti, nome, contenuto, adesso):
    """Aggiorna l'impronta del contenuto estratto e l'ora dell'ultimo
    cambiamento. Nessun timestamp del "giro" finisce nello stato: cambierebbe
    a ogni esecuzione e produrrebbe un commit ogni quarto d'ora."""
    imp = impronta(contenuto)
    prima = fonti.get(nome) or {}
    if prima.get("impronta") != imp:
        fonti[nome] = {"impronta": imp,
                       "cambiata_il": adesso.astimezone(orari.UTC).isoformat()}
        return True
    return False


def fonti_ferme(evento, stato_fonti, adesso, lette=None):
    """Fonti il cui contenuto estratto e' fermo da troppi minuti di gara.
    `lette`: i nomi delle fonti consultate in questo giro (senza chiave API
    la cronaca non viene letta, e non ha senso dire che e' ferma)."""
    if not orari.in_gara(evento, adesso):
        return []
    ferme = []
    for f in evento.fonti:
        if lette is not None and f.nome not in lette:
            continue
        s = stato_fonti.get(f.nome)
        if not f.allarme_dopo_minuti or not s:
            continue
        da = dt.datetime.fromisoformat(s["cambiata_il"])
        fermi = orari.minuti_di_gara(evento, da, adesso)
        if fermi >= f.allarme_dopo_minuti:
            ferme.append((f, da, fermi))
    return ferme


def testo_allarme(evento, ferme):
    r = ["Durante le ore di gara il contenuto di queste fonti non cambia da "
         "troppo tempo. Il calendario **%s** potrebbe non riflettere "
         "qualificazioni ed eliminazioni." % evento.nome_calendario, ""]
    for f, da, minuti in ferme:
        url = f.opzioni.get("url") or f.opzioni.get("indice") or ""
        r.append("- **%s** (%s): ultimo contenuto nuovo il %s, fermo da %d "
                 "minuti di gara (soglia %d). %s"
                 % (f.nome, f.ruolo, da.astimezone(ITALIA).strftime("%d/%m alle %H:%M"),
                    minuti, f.allarme_dopo_minuti, url))
    r += ["", "Cosa controllare:",
          "1. apri la pagina nel browser: si aggiorna ancora? ha cambiato "
          "indirizzo?",
          "2. dal Terminale, `python -m calendario verifica %s` mostra cosa "
          "viene estratto;" % evento.percorso,
          "3. se la fonte e' morta, cambiala nel file dell'evento.",
          "", "La issue si chiude da sola quando la fonte riprende ad "
          "aggiornarsi."]
    return "\n".join(r) + "\n"


def aggiorna(evento, adesso=None, allarme=None, log=print, scarica=scarica,
             crea_client=None):
    adesso = adesso or dt.datetime.now(orari.UTC)
    stato = carica_stato(evento.file_stato, log)
    fonti = dict(stato.get("fonti") or {})
    articoli = dict(stato.get("articoli") or {})
    programma = stato.get("programma")
    anomalie = []

    # 1. Programma: senza programma non c'e' calendario.
    fp = evento.programma
    try:
        programma = leggi_programma(evento, scarica)
        log("programma (%s): %d gare" % (fp.nome, len(programma)))
        _freschezza(fonti, fp.nome, programma, adesso)
    except Irraggiungibile as ex:
        if not programma:
            log("fonte momentaneamente irraggiungibile (%s): riprovo al "
                "prossimo giro" % ex)
            return 0
        log("programma irraggiungibile (%s): uso l'ultimo letto" % ex)
    except PaginaCambiata as ex:
        log("ERRORE: programma (%s): %s" % (fp.nome, ex))
        return 1

    # 2. Avanzamenti dalla cronaca, solo con la chiave API.
    if evento.avanzamenti and not av.chiave_presente():
        log("ANTHROPIC_API_KEY assente: calendario dal solo programma "
            "(qualificazioni ed eliminazioni non vengono lette)")
    elif evento.avanzamenti:
        client, grave = None, False
        for fa in evento.avanzamenti:
            if grave:
                break
            try:
                lista = PARSER["avanzamenti"][fa.parser](fa.opzioni, evento,
                                                          scarica, log)
            except Irraggiungibile as ex:
                log("avanzamenti (%s) irraggiungibili (%s): riprovo al "
                    "prossimo giro" % (fa.nome, ex))
                continue
            except PaginaCambiata as ex:
                anomalie.append("avanzamenti (%s): %s" % (fa.nome, ex))
                continue
            log("avanzamenti (%s): %d articoli" % (fa.nome, len(lista)))
            contenuto = []
            for a in lista:
                vecchio = articoli.get(a["url"])
                if a.get("irraggiungibile"):
                    if vecchio:
                        contenuto.append([a["url"], vecchio["impronta"]])
                    continue
                contenuto.append([a["url"], a["impronta"]])
                if vecchio and vecchio["impronta"] == a["impronta"]:
                    continue            # gia' letto: niente chiamata API
                client = client or (crea_client or av.crea_client)()
                try:
                    r = av.estrai_esiti(client, a, programma, evento, fa.opzioni)
                except av.ErroreTransitorio as ex:
                    log("  %s: %s (riprovo al prossimo giro)" % (a["url"], ex))
                    continue
                except av.ErroreGrave as ex:
                    anomalie.append(str(ex))
                    grave = True
                    break
                log("  %s: %d esiti%s" % (a["titolo"] or a["url"],
                                          len(r["esiti"]),
                                          " (richiesta rifiutata)"
                                          if r.get("rifiutato") else ""))
                articoli[a["url"]] = dict({"fonte": fa.nome,
                                           "titolo": a["titolo"],
                                           "impronta": a["impronta"]}, **r)
            if not grave:
                _freschezza(fonti, fa.nome, contenuto, adesso)

    # 3. Fusione e calendario.
    esiti = [e for a in articoli.values() for e in a["esiti"]]
    gare = fondi(programma, esiti, log)
    nuovo = {"versione": VERSIONE_STATO, "evento": evento.nome,
             "fonti": fonti, "programma": programma, "articoli": articoli,
             "calendario": gare}
    cambiato_ics = scrivi_se_diverso(evento.file_ics, ics.genera(evento, gare))
    cambiato_stato = scrivi_se_diverso(evento.file_stato, _json(nuovo))
    if cambiato_ics:
        log("aggiornato: %d eventi in %s" % (len(gare), evento.file_ics))
    elif cambiato_stato:
        log("calendario invariato (%d eventi), stato aggiornato" % len(gare))
    else:
        log("nessun cambiamento (%d eventi)" % len(gare))

    # 4. Freschezza del contenuto.
    lette = [f.nome for f in evento.fonti
             if f.ruolo == "programma" or av.chiave_presente()]
    ferme = fonti_ferme(evento, fonti, adesso, lette)
    for f, da, minuti in ferme:
        log("ATTENZIONE: %s ferma da %d minuti di gara" % (f.nome, minuti))
    if allarme:
        if ferme:
            with open(allarme, "w", encoding="utf-8") as fh:
                fh.write(testo_allarme(evento, ferme))
        elif os.path.exists(allarme):
            os.remove(allarme)

    for a in anomalie:
        log("ERRORE: %s" % a)
    return 1 if anomalie else 0


def verifica(evento, cartella=None, esiti=False, log=print, scarica=scarica,
             crea_client=None):
    """Mostra che cosa si estrae da ogni fonte, per giudicarla prima di
    usarla. Con `cartella` salva i testi estratti: rilanciando dopo un turno
    di gara si confronta che cosa e' cambiato."""
    from .testo import analizza_pagina
    if cartella:
        os.makedirs(cartella, exist_ok=True)

    def salva(nome, testo):
        if cartella:
            p = os.path.join(cartella, nome + ".txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(testo)
            log("  testo estratto salvato in %s" % p)

    def date(meta):
        log("  pubblicata: %s" % (meta["pubblicato"] or "non indicato"))
        if meta["modificato"]:
            log("  modificata: %s" % meta["modificato"])
        else:
            log("  modificata: NON INDICATO. Attenzione: niente dateModified "
                "e' il segno di un articolo che forse non viene aggiornato.")

    fp = evento.programma
    log("== %s (programma, parser %s)\n  %s" % (fp.nome, fp.parser,
                                               fp.opzioni["url"]))
    try:
        pagina = scarica(fp.opzioni["url"])
        date(analizza_pagina(pagina))
        gare = in_ora_italiana(PARSER["programma"][fp.parser](
            pagina, fp.opzioni, evento), fp.opzioni.get("fuso"))
        log("  gare lette: %d, impronta del contenuto: %s"
            % (len(gare), impronta(gare)))
        salva(fp.nome, "\n".join(
            "%s %s %s %s %s: %s%s" % (g["data"], g["ora"], g["gara"],
                                      g["genere"], g["fase"],
                                      ", ".join(g["atleti"]),
                                      " (eventuale)" if g["eventuale"] else "")
            for g in gare) + "\n")
    except (Irraggiungibile, PaginaCambiata) as ex:
        log("  PROBLEMA: %s" % ex)
        gare = []
    for fa in evento.avanzamenti:
        log("== %s (avanzamenti, parser %s)\n  %s"
            % (fa.nome, fa.parser, fa.opzioni.get("indice", "")))
        try:
            lista = PARSER["avanzamenti"][fa.parser](fa.opzioni, evento,
                                                      scarica, log)
        except (Irraggiungibile, PaginaCambiata) as ex:
            log("  PROBLEMA: %s" % ex)
            continue
        log("  articoli trovati: %d" % len(lista))
        for i, a in enumerate(lista, 1):
            if a.get("irraggiungibile"):
                log(" [%d] %s: irraggiungibile" % (i, a["url"]))
                continue
            log(" [%d] %s\n  %s" % (i, a["titolo"], a["url"]))
            date(a)
            log("  corpo: %d caratteri (metodo %s), impronta %s"
                % (len(a["testo"]), a["metodo"], a["impronta"]))
            salva("%s-%d" % (fa.nome, i), a["titolo"] + "\n\n" + a["testo"] + "\n")
            if esiti and gare:
                if not av.chiave_presente():
                    log("  (esiti non letti: manca ANTHROPIC_API_KEY)")
                    continue
                try:
                    r = av.estrai_esiti((crea_client or av.crea_client)(), a,
                                        gare, evento, fa.opzioni)
                except (av.ErroreTransitorio, av.ErroreGrave) as ex:
                    log("  esiti: errore %s" % ex)
                    continue
                for e in r["esiti"]:
                    log("  -> %s, %s %s %s: %s  «%s»"
                        % (e["atleta"], e["gara"], e["genere"], e["fase"],
                           e["esito"], e["citazione"]))
    return 0
