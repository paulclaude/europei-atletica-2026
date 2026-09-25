# -*- coding: utf-8 -*-
"""Lettura degli avanzamenti dalla cronaca in prosa, tramite l'API Anthropic.

Gli articoli live sono scritti per essere letti da una persona ("Coiro vola
in finale con 1:57.74", "si ferma in batteria Mulas"): nessuna regex li
capisce in modo affidabile. Il testo va al modello insieme all'elenco delle
gare del programma, e il modello restituisce un JSON vincolato da SCHEMA
(structured outputs). Il JSON viene poi ricontrollato qui contro lo stesso
schema prima di essere usato.

La chiave arriva dalla variabile d'ambiente ANTHROPIC_API_KEY (su GitHub
Actions, dal secret omonimo). Senza chiave questo modulo non viene usato e
il calendario si basa sul solo programma.
"""
import json
import os

from .fusione import ESITI

MODELLO = "claude-opus-5"
# Se il modello rifiuta la richiesta, l'API la ripete su un altro modello.
BETA_RIPIEGO = "server-side-fallback-2026-07-01"

SCHEMA = {
    "type": "object",
    "properties": {
        "esiti": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "atleta": {"type": "string"},
                    "gara": {"type": "string"},
                    "genere": {"type": "string",
                               "enum": ["maschile", "femminile", "mista", ""]},
                    "fase": {"type": "string"},
                    "esito": {"type": "string", "enum": list(ESITI)},
                    "citazione": {"type": "string"},
                },
                "required": ["atleta", "gara", "genere", "fase", "esito",
                             "citazione"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["esiti"],
    "additionalProperties": False,
}

ISTRUZIONI = """\
Leggi una cronaca sportiva in italiano e ne estrai gli esiti degli atleti \
italiani, per aggiornare un calendario delle loro gare.

Riceverai l'elenco delle gare in programma con gli italiani iscritti e poi \
il testo dell'articolo. Per ogni atleta italiano di cui l'articolo dice \
chiaramente come e' andato un turno, restituisci un esito:

- qualificato: ha superato il turno indicato in "fase" e disputera' il turno \
successivo (anche se ci arriva come ripescato o per tempi).
- eliminato: e' uscito nel turno indicato in "fase".
- squalificato: squalificato nel turno indicato in "fase".
- ritirato: si e' ritirato durante il turno indicato in "fase".
- infortunato: si e' infortunato nel turno indicato in "fase" e non \
proseguira'.
- non_partente: non prendera' (o non ha preso) il via proprio nel turno \
indicato in "fase" (forfait, rinuncia).

Regole:
- Usa per "gara", "genere" e "fase" esattamente le parole dell'elenco delle \
gare. Per "atleta" usa il nome come compare nell'elenco (di solito il \
cognome); per le staffette usa "Italia".
- Nelle prove multiple (decathlon, eptathlon) la "fase" e' la singola prova.
- Una vittoria, una medaglia o un piazzamento in finale non sono esiti: \
dopo la finale non c'e' un turno successivo. Non restituirli.
- Solo fatti gia' avvenuti e scritti nell'articolo. Niente previsioni, \
niente deduzioni da tempi o classifiche se l'articolo non dice l'esito.
- Ignora gli atleti non italiani.
- In "citazione" copia la frase dell'articolo che attesta l'esito.
- Se non ci sono esiti, restituisci un elenco vuoto."""


class ErroreTransitorio(Exception):
    """Rete, limiti di frequenza, server sovraccarico: si riprova al giro dopo."""


class ErroreGrave(Exception):
    """Chiave non valida, modello inesistente, richiesta rifiutata dall'API:
    non si risolve da solo, va segnalato."""


def chiave_presente():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def crea_client():
    import anthropic
    return anthropic.Anthropic(max_retries=3, timeout=180)


def valida(dato, schema, dove="risposta"):
    """Controllo del JSON contro lo schema (il sottoinsieme usato qui)."""
    t = schema.get("type")
    tipi = {"object": dict, "array": list, "string": str}
    if t in tipi and not isinstance(dato, tipi[t]):
        raise ValueError("%s: atteso %s" % (dove, t))
    if "enum" in schema and dato not in schema["enum"]:
        raise ValueError("%s: valore %r non ammesso" % (dove, dato))
    if t == "object":
        for k in schema.get("required", []):
            if k not in dato:
                raise ValueError("%s: manca %s" % (dove, k))
        if schema.get("additionalProperties") is False:
            extra = set(dato) - set(schema["properties"])
            if extra:
                raise ValueError("%s: campi inattesi %s" % (dove, sorted(extra)))
        for k, v in dato.items():
            valida(v, schema["properties"][k], "%s.%s" % (dove, k))
    if t == "array":
        for i, v in enumerate(dato):
            valida(v, schema["items"], "%s[%d]" % (dove, i))
    return dato


def _elenco_gare(programma):
    righe = []
    for g in programma:
        righe.append("- gara: %s | genere: %s | fase: %s | %s ore %s | "
                     "italiani: %s" % (g["gara"], g["genere"] or "-", g["fase"],
                                       g["data"], g["ora"],
                                       ", ".join(g["atleti"]) or "-"))
    return "\n".join(righe)


def richiesta(articolo, programma, evento, opzioni):
    """Parametri della chiamata alla Messages API (separati per i test).

    Istruzioni ed elenco delle gare sono uguali per tutti gli articoli dello
    stesso giro: stanno nel prompt di sistema, marcati per la cache, e
    l'articolo arriva dopo. Cosi' dal secondo articolo in poi quella parte
    costa un decimo.
    """
    gare = ("Manifestazione: %s (%s).\n\n<gare>\n%s\n</gare>"
            % (evento.nome, evento.citta, _elenco_gare(programma)))
    testo = "<articolo>\nTitolo: %s\n\n%s\n</articolo>" % (
        articolo["titolo"], articolo["testo"])
    config = {"format": {"type": "json_schema", "schema": SCHEMA}}
    if opzioni.get("sforzo"):
        config["effort"] = opzioni["sforzo"]
    par = {"model": opzioni.get("modello") or MODELLO,
           "max_tokens": 16000,
           "system": [{"type": "text", "text": ISTRUZIONI},
                      {"type": "text", "text": gare,
                       "cache_control": {"type": "ephemeral"}}],
           "messages": [{"role": "user", "content": testo}],
           "output_config": config}
    if opzioni.get("ripiego", True):
        par["betas"] = [BETA_RIPIEGO]
        par["fallbacks"] = "default"
    return par


def estrai_esiti(client, articolo, programma, evento, opzioni):
    """Esiti di un articolo. Solleva ErroreTransitorio o ErroreGrave."""
    import anthropic
    par = richiesta(articolo, programma, evento, opzioni)
    try:
        if "betas" in par:
            r = client.beta.messages.create(**par)
        else:
            r = client.messages.create(**par)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
            anthropic.NotFoundError, anthropic.BadRequestError) as ex:
        raise ErroreGrave("API Anthropic: %s" % ex)
    except (anthropic.APIConnectionError, anthropic.RateLimitError,
            anthropic.InternalServerError) as ex:
        raise ErroreTransitorio("API Anthropic: %s" % ex)
    except anthropic.APIStatusError as ex:
        if ex.status_code >= 500:
            raise ErroreTransitorio("API Anthropic: %s" % ex)
        raise ErroreGrave("API Anthropic: %s" % ex)
    if r.stop_reason == "refusal":
        # Nessun esito, ma lo si ricorda: ripetere la stessa richiesta a ogni
        # giro costerebbe senza cambiare nulla. Si riprova se l'articolo cambia.
        return {"esiti": [], "rifiutato": True}
    if r.stop_reason == "max_tokens":
        raise ErroreTransitorio("risposta troncata (max_tokens)")
    testo = next((b.text for b in r.content if b.type == "text"), None)
    if testo is None:
        raise ErroreTransitorio("risposta senza testo")
    try:
        dati = valida(json.loads(testo), SCHEMA)
    except ValueError as ex:
        raise ErroreTransitorio("JSON non valido: %s" % ex)
    return {"esiti": [{k: e[k] for k in ("atleta", "gara", "genere", "fase",
                                         "esito", "citazione")}
                      for e in dati["esiti"]]}
