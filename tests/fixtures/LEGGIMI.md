# Fixture dei test

**Sono tutte sintetiche.** La rete dell'ambiente in cui sono state preparate
bloccava sia fidal.it sia oasport.it (403 dal proxy), quindi non è stato
possibile scaricare le pagine vere.

- `oasport_programma.html`: pagina costruita a partire da `stato.json` del
  2026, cioè dai dati che il vecchio `genera.py` aveva estratto dalla pagina
  vera di OA Sport. Contiene di proposito spazi non standard (` `,
  ` `, ` `), le parole "eventuale"/"eventuali" in entrambe le
  posizioni, un menu, una pubblicità e una colonna laterale. Il parser deve
  ricavarne esattamente le 113 gare di `stato.json`.
- `fidal_home.html`, `fidal_live_*.html`: home e articoli "LIVE" in prosa
  scritti sul modello di quelli FIDAL di Birmingham (titoli, struttura per
  orario e disciplina). I fatti del day 4 ricalcano la sintesi pubblicata
  dalla FIDAL ("Birmingham: altri 7 in finale, Coiro 1:57.74"); gli altri
  sono inventati per coprire i casi dei test (eliminazione, ritiro, refusi
  nei nomi). La struttura HTML vera della FIDAL non è stata verificata.
  - `fidal_live_day4_altra_pubblicita.html`: stesso articolo, altra
    pubblicità e altre "ultime notizie": l'impronta deve restare la stessa.
  - `fidal_live_day4_aggiornato.html`: stesso articolo con un paragrafo in
    più: l'impronta deve cambiare.
- `esiti_day*.json`: risposte finte del modello per i due articoli, nel
  formato imposto dallo schema. Nessun test chiama l'API vera.

Prima di usare il sistema con fonti vere, segui la sezione "Come verificare
una fonte" del README principale.
