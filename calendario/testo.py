# -*- coding: utf-8 -*-
"""Trattamento del testo: spazi strani, righe di una pagina, corpo di un
articolo, metadati (date di pubblicazione e modifica).

Qui c'e' la lezione di Birmingham: il controllo di freschezza va fatto sul
contenuto ESTRATTO, mai sulla pagina intera. Pubblicita', box "piu' letti" e
contatori cambiano a ogni visita e fanno sembrare viva una pagina morta.
"""
import hashlib
import html
import json
import re
import unicodedata
from html.parser import HTMLParser

# OA Sport mescolava spazi normali, non-breaking space e spazi sottili nella
# stessa pagina: "11.35" e "11.35" sembravano uguali ma non lo erano.
SPAZI = {" ": " ", " ": " ", " ": " ", " ": " ",
         "​": "", "﻿": ""}


def pulisci(s):
    """Normalizza gli spazi: va chiamata prima di ogni confronto."""
    for c, r in SPAZI.items():
        s = s.replace(c, r)
    return s


def righe(pagina):
    """Tutte le righe di testo della pagina, nell'ordine in cui compaiono.

    E' il metodo del vecchio genera.py, che su OA Sport funzionava: toglie
    script e stili, trasforma ogni tag in un a capo e lascia al parser il
    compito di riconoscere le righe che gli interessano.
    """
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", pagina,
               flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = pulisci(html.unescape(t))
    return [r.strip() for r in t.split("\n") if r.strip()]


def chiave(gara, genere, fase):
    """Chiave stabile di una gara: da qui nasce l'UID dell'evento.

    Non va mai cambiata a evento in corso: un UID diverso fa comparire un
    doppione nel calendario di chi e' abbonato.
    """
    s = unicodedata.normalize("NFKD", ("%s|%s|%s" % (gara, genere, fase)).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9|]+", "", s)


def impronta(dati):
    """Impronta breve e deterministica di dati JSON (liste, dizionari, testo)."""
    if not isinstance(dati, str):
        dati = json.dumps(dati, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(dati.encode("utf-8")).hexdigest()[:16]


# --- estrazione del corpo di un articolo -----------------------------------

_BLOCCHI = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
            "br", "tr", "td", "th", "section", "article", "main", "table",
            "blockquote", "dd", "dt", "figcaption", "header", "footer"}
_SALTA = {"script", "style", "noscript", "template", "svg", "iframe", "form",
          "nav", "aside", "footer", "header", "button", "select", "figure"}
_VUOTI = {"br", "img", "meta", "link", "input", "hr", "source", "wbr", "area",
          "base", "col", "embed", "param", "track"}
# Classi dei riquadri di contorno. Si confronta il singolo nome di classe
# (o il suo prefisso "adv-..."), non una sottostringa: "has-sidebar" su un
# contenitore non deve far sparire l'articolo.
_RUMORE = re.compile(r"^(adv|ads|advert\w*|banner|sidebar|widget|related|"
                     r"correlat\w*|share|social|cookie\w*|newsletter|"
                     r"comments?|breadcrumbs?|piu-letti|popular|footer|header|"
                     r"menu|nav\w*)([-_].*)?$",
                     re.I)


class _Estrattore(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila = []          # (tag, salta, dentro_article)
        self.blocchi = {"tutto": [[]], "article": [[]], "main": [[]], "p": [[]]}
        self.titolo, self._in_title = [], False
        self.jsonld, self._in_jsonld = [], False
        self.meta = {}

    def _salta(self):
        return any(s for _, s in self.pila)

    def _dentro(self, tag):
        return any(t == tag for t, _ in self.pila)

    def _a_capo(self):
        for b in self.blocchi.values():
            if b[-1]:
                b.append([])

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = a.get("property") or a.get("name") or a.get("itemprop")
            if k and a.get("content"):
                self.meta.setdefault(k.lower(), a["content"])
            return
        if tag == "script" and "ld+json" in (a.get("type") or ""):
            self._in_jsonld = True
            self.jsonld.append("")
        if tag == "title":
            self._in_title = True
        if tag in _VUOTI:
            if tag == "br":
                self._a_capo()
            return
        classi = (a.get("class") or "").split() + [a.get("id") or ""]
        salta = tag in _SALTA or any(_RUMORE.match(c) for c in classi if c)
        self.pila.append((tag, salta))
        if tag in _BLOCCHI:
            self._a_capo()

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_jsonld = False
        if tag == "title":
            self._in_title = False
        if tag in _VUOTI:
            return
        # HTML reale: tag non chiusi. Si chiude fino al tag corrispondente,
        # se c'e'; altrimenti si ignora.
        for i in range(len(self.pila) - 1, -1, -1):
            if self.pila[i][0] == tag:
                del self.pila[i:]
                break
        if tag in _BLOCCHI:
            self._a_capo()

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld[-1] += data
            return
        if self._in_title:
            self.titolo.append(data)
            return
        if self._salta() or self._dentro("script") or self._dentro("style"):
            return
        self.blocchi["tutto"][-1].append(data)
        for tag in ("article", "main", "p"):
            if self._dentro(tag):
                self.blocchi[tag][-1].append(data)


def _unisci(blocchi):
    out = []
    for b in blocchi:
        t = re.sub(r"\s+", " ", pulisci("".join(b))).strip()
        if t:
            out.append(t)
    return "\n".join(out)


def _oggetti_jsonld(testi):
    for t in testi:
        try:
            d = json.loads(t.strip())
        except ValueError:
            continue
        pila = [d]
        while pila:
            x = pila.pop()
            if isinstance(x, list):
                pila.extend(x)
            elif isinstance(x, dict):
                yield x
                pila.extend(v for v in x.values() if isinstance(v, (list, dict)))


def analizza_pagina(pagina, minimo=300):
    """Corpo, titolo e date di un articolo.

    Per il corpo prova, nell'ordine: articleBody dei metadati JSON-LD,
    l'elemento <article>, l'elemento <main>, i soli paragrafi <p>, tutto il
    testo. Tiene il primo che supera `minimo` caratteri. Menu, colonne
    laterali, pubblicita' e articoli correlati restano fuori.
    """
    e = _Estrattore()
    e.feed(pagina)
    e.close()
    pubblicato = modificato = titolo = corpo_ld = None
    for o in _oggetti_jsonld(e.jsonld):
        pubblicato = pubblicato or o.get("datePublished")
        modificato = modificato or o.get("dateModified")
        titolo = titolo or o.get("headline")
        if isinstance(o.get("articleBody"), str) and not corpo_ld:
            corpo_ld = pulisci(html.unescape(o["articleBody"])).strip()
    pubblicato = pubblicato or e.meta.get("article:published_time")
    modificato = (modificato or e.meta.get("article:modified_time")
                  or e.meta.get("og:updated_time"))
    titolo = (titolo or e.meta.get("og:title")
              or re.sub(r"\s+", " ", pulisci("".join(e.titolo))).strip())
    candidati = [("json-ld", corpo_ld or "")]
    for nome in ("article", "main", "p", "tutto"):
        candidati.append((nome, _unisci(e.blocchi[nome])))
    metodo, corpo = next(((n, c) for n, c in candidati if len(c) >= minimo),
                         max(candidati, key=lambda x: len(x[1])))
    return {"titolo": pulisci(html.unescape(titolo or "")), "corpo": corpo,
            "metodo": metodo, "pubblicato": pubblicato, "modificato": modificato}


class _Collegamenti(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.link, self._corrente = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            a = dict(attrs)
            self._corrente = [a.get("href") or "", [a.get("title") or ""]]

    def handle_data(self, data):
        if self._corrente is not None:
            self._corrente[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._corrente is not None:
            href, pezzi = self._corrente
            testo = re.sub(r"\s+", " ", pulisci(" ".join(pezzi))).strip()
            self.link.append((href, testo))
            self._corrente = None


def collegamenti(pagina):
    """Coppie (href, testo) di tutti i link della pagina."""
    c = _Collegamenti()
    c.feed(pagina)
    c.close()
    return c.link
