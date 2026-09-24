# -*- coding: utf-8 -*-
"""Confronto tollerante di nomi di atleti e di gare.

Le fonti hanno refusi e varianti: a Birmingham la stessa pagina scriveva
Conte e Conti, Oliveri e Olivieri; la cronaca scrive "Gianmarco Tamberi"
dove il programma dice solo "Tamberi"; ci sono due Zoghlami distinti solo
dall'iniziale.
"""
import re
import unicodedata

from .testo import pulisci


def normalizza(s):
    s = unicodedata.normalize("NFKD", pulisci(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[.'’`\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def distanza(a, b):
    """Distanza di Levenshtein (inserimenti, cancellazioni, sostituzioni)."""
    if len(a) < len(b):
        a, b = b, a
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cor = [i]
        for j, cb in enumerate(b, 1):
            cor.append(min(prec[j] + 1, cor[j - 1] + 1,
                           prec[j - 1] + (ca != cb)))
        prec = cor
    return prec[-1]


def quasi_uguali(a, b):
    """Uguali a meno di un refuso: 0 errori fino a 4 lettere, 1 fino a 7,
    2 oltre. "Fina" e "Fino" restano diversi, "Conte" e "Conti" no."""
    if a == b:
        return True
    n = max(len(a), len(b))
    return distanza(a, b) <= (0 if n <= 4 else 1 if n <= 7 else 2)


def _parti(nome):
    t = normalizza(nome).split()
    return [x for x in t if len(x) == 1], [x for x in t if len(x) > 1]


def stesso_atleta(nel_programma, nella_cronaca):
    """Il nome del programma (di solito il solo cognome, a volte con
    l'iniziale: "A. Zoghlami") corrisponde a quello della cronaca?"""
    p_ini, p_cog = _parti(nel_programma)
    c_ini, c_tok = _parti(nella_cronaca)
    n = len(p_cog)
    if not n or not c_tok:
        return False
    cognome = " ".join(p_cog)
    # "Nome Cognome" oppure "Cognome Nome"
    for pezzo, resto in ((c_tok[-n:], c_tok[:-n]), (c_tok[:n], c_tok[n:])):
        if len(pezzo) == n and quasi_uguali(cognome, " ".join(pezzo)):
            if p_ini:
                iniziale = (resto[0][0] if resto else
                            c_ini[0] if c_ini else None)
                if iniziale and iniziale != p_ini[0]:
                    continue
            return True
    return False


def trova_atleta(atleti, nome):
    """Indice dell'atleta `nome` nella lista, oppure None.

    Se piu' atleti corrispondono (due Zoghlami e la cronaca scrive solo
    "Zoghlami") non si sceglie a caso: None, e l'esito viene ignorato.
    """
    trovati = [i for i, a in enumerate(atleti) if stesso_atleta(a, nome)]
    if len(trovati) == 1:
        return trovati[0]
    esatti = [i for i in trovati if normalizza(atleti[i]) == normalizza(nome)]
    return esatti[0] if len(esatti) == 1 else None


def normalizza_gara(s):
    s = normalizza(s).replace("×", "x")
    s = re.sub(r"\bhs\b", "ostacoli", s)
    s = re.sub(r"(\d)\s*(m|metri)\b", r"\1", s)
    s = re.sub(r"\b(metri|m)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def stessa_gara(a, b):
    x, y = normalizza_gara(a), normalizza_gara(b)
    if re.findall(r"\d+", x) != re.findall(r"\d+", y):
        return False        # "100 ostacoli" e "400 ostacoli": un refuso no
    return x == y or (min(len(x), len(y)) >= 8 and quasi_uguali(x, y))
