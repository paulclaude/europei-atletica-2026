# Calendario degli azzurri in gara

Un calendario che si aggiorna da solo, con tutte le gare di una manifestazione
(Europei, Mondiali, Olimpiadi, di atletica o di un altro sport) in cui sono
impegnati atleti italiani. Si sottoscrive una volta con Calendario di Apple, su
Mac, iPhone e iPad, e poi segue la manifestazione: quando un azzurro passa il
turno sparisce "(eventuale)", quando viene eliminato il suo nome esce dalle gare
successive, e una gara rimasta senza italiani sparisce del tutto.

La prima manifestazione seguita è stata quella degli **Europei di atletica di
Birmingham, 10-16 agosto 2026**. Il suo calendario è `europei.ics`:

    https://raw.githubusercontent.com/paulclaude/europei-atletica-2026/main/europei.ics

Tutto ciò che cambia da un evento all'altro sta in un file di configurazione
nella cartella `eventi/`: per un evento nuovo si scrive un file nuovo, il codice
resta lo stesso.

---

## Indice

1. [Come funziona](#come-funziona)
2. [Sottoscrivere il calendario (Mac, iPhone, iPad)](#sottoscrivere-il-calendario-mac-iphone-ipad)
3. [Legenda dei titoli](#legenda-dei-titoli)
4. [Come verificare una fonte prima di usarla](#come-verificare-una-fonte-prima-di-usarla)
5. [Preparare un nuovo evento, passo passo](#preparare-un-nuovo-evento-passo-passo)
6. [La chiave API di Anthropic (il "secret")](#la-chiave-api-di-anthropic-il-secret)
7. [Quando qualcosa va storto](#quando-qualcosa-va-storto)
8. [Per chi mette mano al codice](#per-chi-mette-mano-al-codice)

---

## Come funziona

A Birmingham il sistema funzionava dal punto di vista meccanico, ma la fonte no.
La pagina di OA Sport era un articolo scritto alla vigilia e **mai aggiornato**,
per cui il calendario non ha mai registrato qualificazioni ed eliminazioni. La
fonte che si aggiornava davvero erano gli articoli "LIVE" della FIDAL, che però
sono cronaca in prosa e non elenchi. Da qui i due livelli di dati:

| Livello | Che cosa contiene | Da dove arriva | Come viene letto |
|---|---|---|---|
| **Programma** | giorno, ora, gara, genere, turno, atleti previsti | una pagina strutturata (per Birmingham, OA Sport) | un *parser* scritto per quella pagina |
| **Avanzamenti** | chi passa il turno, chi è eliminato, chi si ritira | articoli live in prosa (per Birmingham, FIDAL) | il modello Claude tramite l'API di Anthropic, che risponde in un formato JSON fisso |

Gli avanzamenti vengono poi **fusi** nel programma:

- *qualificato*: nel turno successivo la presenza italiana è confermata e
  "(eventuale)" sparisce. Se è una finale compare la sveglia;
- *eliminato*, *squalificato*, *ritirato*, *infortunato*: l'atleta esce dai
  turni successivi;
- *non partente* (forfait): l'atleta esce anche dal turno indicato;
- una gara senza più italiani sparisce dal calendario.

I nomi sono confrontati in modo tollerante, perché le fonti hanno refusi: a
Birmingham c'erano Conte/Conti e Oliveri/Olivieri. "Gianmarco Tamberi" corrisponde
a "Tamberi". Se due atleti sono distinguibili solo dall'iniziale (A. e O.
Zoghlami) e la cronaca non la dà, l'esito viene ignorato anziché attribuito a caso.

**Senza la chiave API il sistema funziona lo stesso** e costruisce il
calendario dal solo programma, come a Birmingham.

Un'azione programmata di GitHub ("workflow") ripete tutto a ogni quarto d'ora,
ma solo nelle ore di gara. Pubblica il calendario **solo se è cambiato
davvero**: niente modifiche a vuoto, niente disturbo per chi è abbonato.

---

## Sottoscrivere il calendario (Mac, iPhone, iPad)

L'indirizzo da sottoscrivere è sempre questo, dove `FILE` è il nome del
calendario dell'evento:

    https://raw.githubusercontent.com/paulclaude/europei-atletica-2026/main/FILE

Per Birmingham 2026 `FILE` è `europei.ics`. Per un evento nuovo è il valore
`calendario.file` del suo file di configurazione (se non è indicato:
`calendari/<nome-del-file>.ics`).

### Su Mac

1. Apri **Calendario**.
2. Menu **File** (o **Archivio**) **→ Nuovo abbonamento calendario…**
3. Incolla l'indirizzo e premi **Abbonati**.
4. Nella finestra che si apre:
   - **Posizione**: *iCloud*, così il calendario compare anche su iPhone e iPad;
   - **Aggiornamento automatico**: *Ogni 15 minuti*;
   - lascia **deselezionato** "Rimuovi: Avvisi", altrimenti spariscono le
     sveglie delle finali.
5. **OK**.

### Su iPhone e iPad

Se hai già fatto l'abbonamento sul Mac con posizione *iCloud*, il calendario
arriva da solo. iCloud però aggiorna gli abbonamenti con i suoi tempi, che
possono essere lunghi. Se durante le gare vuoi aggiornamenti più rapidi,
abbonati direttamente dal dispositivo:

1. **Impostazioni → App → Calendario → Account calendario → Aggiungi account**
   (su iOS meno recenti: *Impostazioni → Calendario → Account*).
2. **Altro → Aggiungi calendario sottoscritto**.
3. Nel campo **Server** incolla l'indirizzo, poi **Avanti** e **Salva**.

Il calendario usa l'ora italiana. Nella descrizione di ogni gara c'è anche
l'ora locale della sede.

---

## Legenda dei titoli

    [F] 800 metri (femminile) - finale | Coiro

- `[B]` batterie, `[Q]` qualificazioni, `[SF]` semifinali, `[F]` finale,
  `[10]` singola prova delle prove multiple (decathlon, eptathlon)
- dopo la barra verticale `|`, gli azzurri in gara
- `(eventuale)`: la presenza italiana dipende dal turno precedente. Sparisce
  quando almeno un azzurro si qualifica
- le finali con azzurri certi hanno una **sveglia 15 minuti prima**
- gli eventi sono "liberi" (non "occupato"): non bloccano l'agenda
- nella descrizione: chi è confermato e chi deve ancora passare il turno,
  l'ora locale della sede e i canali TV

---

## Come verificare una fonte prima di usarla

**È il passo più importante.** A Birmingham tutto il resto funzionava; è
mancata solo questa verifica. Una fonte va bene solo se **cambia davvero
mentre le gare si svolgono**. Sembrare aggiornata non basta.

Le verifiche si fanno con il comando `verifica` dal Terminale del Mac. Se non
l'hai mai usato, vedi [Preparare il Mac](#preparare-il-mac-una-volta-sola).

```
python3 -m calendario verifica eventi/NOME.yaml --salva verifica/prima
```

Per ogni fonte il comando mostra:

- la **data di pubblicazione** e la **data di ultima modifica**
  (`datePublished` e `dateModified` dei metadati della pagina);
- quante gare (programma) o quanti articoli (cronaca) riesce a estrarre;
- l'**impronta del contenuto estratto**: un codice che cambia solo se cambia
  il testo che interessa, non la pubblicità;
- con `--salva`, il testo estratto in una cartella, per confrontarlo dopo.

### Le tre prove

**1. I metadati: `dateModified`.**
Se la pagina ha solo `datePublished` e nessun `dateModified`, il comando lo
segnala con `modificata: NON INDICATO`. È esattamente il caso della pagina di
OA Sport di Birmingham: un articolo della vigilia che nessuno ha più toccato.
Non basta per scartare la fonte, ma è un campanello d'allarme. Se
`dateModified` c'è, rilancia la verifica il giorno dopo: deve essere cambiata.

Per controllare a mano, nel browser: *Safari → Sviluppo → Mostra sorgente
pagina* (il menu Sviluppo si attiva in *Safari → Impostazioni → Avanzate*),
poi cerca `dateModified` con ⌘F.

**2. Il contenuto estratto cambia dopo un turno.**
Lancia la verifica prima di una sessione di gara e di nuovo dopo la fine di
un turno che riguarda un italiano:

```
python3 -m calendario verifica eventi/NOME.yaml --salva verifica/prima
# ... dopo il turno ...
python3 -m calendario verifica eventi/NOME.yaml --salva verifica/dopo
diff -r verifica/prima verifica/dopo
```

Se `diff` non mostra niente e l'impronta è la stessa, la fonte **non si è
mossa**: non va bene per gli avanzamenti. Attenzione: confrontare la pagina
intera non serve. Pubblicità, "più letti" e contatori cambiano a ogni visita e
fanno sembrare viva una pagina morta. Per questo si confronta solo il
contenuto estratto.

**3. Una gara conclusa risulta conclusa.**
Scegli una gara finita da un'ora con un italiano in gara e controlla che:

- nella cronaca ci sia l'esito (il file salvato in `verifica/dopo`);
- con la chiave API, `--esiti` lo estragga correttamente:

  ```
  python3 -m calendario verifica eventi/NOME.yaml --esiti
  ```

  Ogni esito compare come `-> atleta, gara genere turno: esito «frase»`, con la
  frase dell'articolo da cui è stato ricavato;
- se usi la stessa pagina anche per il programma, l'"eventuale" del turno
  successivo sia sparito.

Se una di queste tre prove fallisce, **cerca un'altra fonte** prima di
pubblicare il calendario.

---

## Preparare un nuovo evento, passo passo

Tutto si può fare dal sito di GitHub, tranne due comandi da lanciare sul Mac
(la verifica delle fonti e il calcolo del cron).

### Preparare il Mac (una volta sola)

1. Sul sito del repository premi il pulsante verde **Code → Download ZIP** e
   scompatta il file, oppure, se hai `git`:
   `git clone https://github.com/paulclaude/europei-atletica-2026.git`
2. Apri il **Terminale** e controlla la versione di Python con
   `python3 --version`: serve la 3.10 o successiva (consigliata la 3.12). Il
   Python preinstallato su molti Mac è il 3.9: in quel caso installa la 3.12 da
   <https://www.python.org/downloads/macos/> e usa `python3.12` al posto di
   `python3` nei comandi di questa pagina.
3. Entra nella cartella:
   `cd ~/Downloads/europei-atletica-2026-main` (o dove l'hai messa).
4. Installa le dipendenze:
   `python3 -m pip install --user -r requirements.txt`

Per usare `--esiti` serve anche la chiave nel Terminale:
`export ANTHROPIC_API_KEY=sk-ant-...` (vale finché chiudi la finestra).

### 1. Trova e verifica le fonti

Servono:

- una pagina con il **programma** degli italiani (giorno, ora, gara, turno,
  nomi). Oggi il sistema sa leggere il formato di OA Sport ("gli italiani in
  gara giorno per giorno"). Per un formato diverso serve un parser nuovo: vedi
  [Aggiungere un parser](#aggiungere-un-parser);
- una pagina **indice** da cui partono gli articoli di cronaca live (per
  l'atletica, la home della FIDAL) e una parola che ne distingua i titoli
  ("LIVE").

Verificale come spiegato [sopra](#come-verificare-una-fonte-prima-di-usarla).

### 2. Scrivi il file dell'evento

1. Su GitHub apri la cartella `eventi/` e il file `esempio-tokyo.yaml`, poi
   copiane il contenuto.
2. Torna in `eventi/`, **Add file → Create new file**, dagli un nome come
   `mondiali-2027.yaml` e incolla.
3. Modifica i campi (le righe che cominciano con `#` sono commenti):

| Campo | Che cosa mettere |
|---|---|
| `nome` | nome della manifestazione |
| `sigla` | prefisso breve e unico degli UID, per esempio `mo27`. **Dopo la prima pubblicazione non cambiarlo mai**: chi è abbonato vedrebbe ogni gara doppia |
| `date.inizio`, `date.fine` | primo e ultimo giorno di gare, `AAAA-MM-GG` |
| `sede.citta`, `sede.luogo` | per la descrizione e il luogo degli eventi |
| `sede.fuso` | fuso orario della sede, per esempio `Europe/London`, `America/New_York`, `Asia/Tokyo` |
| `calendario.nome` | come si chiamerà il calendario sui dispositivi |
| `calendario.file` | facoltativo: nome del file `.ics`. **Decidilo prima di dare il link**, poi non cambiarlo |
| `calendario.dtstamp` | una data fissa qualunque, per esempio il giorno prima dell'inizio (`20270909T000000Z`). Non cambiarla |
| `tv` | canali e piattaforme, finisce nella descrizione |
| `sessioni` | fasce orarie di gara **in ora italiana**, per esempio `"19:00-23:59"`. Aggiungi un po' di margine dopo l'ultima gara: la cronaca arriva dopo |
| `fonti` | le fonti: una con `ruolo: programma`, una o più con `ruolo: avanzamenti` |

Per ogni fonte:

| Campo | Significato |
|---|---|
| `nome` | un nome breve, compare nei messaggi |
| `parser` | `oasport` per il programma, `articoli_live` per la cronaca |
| `url` (programma) | la pagina del programma |
| `fuso` (programma) | fuso degli orari **scritti nella pagina**: `Europe/Rome` se sono italiani, quello della sede se sono locali |
| `indice`, `filtro_url`, `titolo` (cronaca) | pagina da cui partire; testo che l'indirizzo dei link deve contenere; parole che il titolo deve contenere (`LIVE\|Tokyo` significa "LIVE oppure Tokyo") |
| `massimo_articoli` | quanti articoli leggere al massimo a ogni giro |
| `modello` | modello Claude usato per leggere la cronaca (predefinito `claude-opus-5`) |
| `allarme_dopo_minuti` | dopo quanti minuti **di gara** senza contenuto nuovo aprire una segnalazione; `null` per nessun controllo |

4. **Commit changes** in fondo alla pagina.

### 3. Calcola il cron e aggiorna il workflow

Il programmatore di GitHub non può leggere il file dell'evento, quindi le ore
vanno scritte anche nel workflow. Nel Terminale:

```
python3 -m calendario cron eventi/mondiali-2027.yaml
```

Esce una riga come `7,22,37,52 9-13,17-21 10-16 8 *`: vuol dire minuti 7, 22,
37 e 52, ore UTC di gara, solo nei giorni dell'evento. Poi, su GitHub:

1. apri `.github/workflows/aggiorna.yml` e premi la matita (**Edit**);
2. sostituisci la riga `- cron: "..."` con quella nuova, tra virgolette (se
   escono più righe, metti una riga `- cron:` per ciascuna);
3. sostituisci `EVENTO: eventi/birmingham-2026.yaml` con il file nuovo;
4. **Commit changes**.

Minuti sfalsati e ore di gara non sono un vezzo. Il cron di GitHub non è
puntuale: a Birmingham, con "ogni 15 minuti", sono stati misurati intervalli
da 29 a 149 minuti. Le esecuzioni a inizio ora sono le più ritardate.

### 4. Aggiungi la chiave API

Vedi [la sezione dedicata](#la-chiave-api-di-anthropic-il-secret). Se la chiave
è già stata aggiunta per un evento precedente, non devi rifare niente.

### 5. Riattiva il workflow e prova

Il workflow è **disabilitato** e resta tale finché non lo riattivi a mano.
Modificare il file non lo riattiva.

1. Scheda **Actions** del repository.
2. A sinistra, **Aggiorna calendario azzurri**.
3. **Enable workflow**.
4. **Run workflow → Run workflow** per una prima esecuzione subito: così il
   calendario esiste già prima dell'inizio delle gare.
5. Apri l'esecuzione e controlla il passo **Rigenera il calendario**: deve dire
   quante gare ha letto e `aggiornato: N eventi`.

Poi dai il link agli interessati (vedi [Sottoscrivere](#sottoscrivere-il-calendario-mac-iphone-ipad)).

### 6. Dopo l'evento

**Actions → Aggiorna calendario azzurri → "…" → Disable workflow.** Il cron
copre comunque solo i giorni dell'evento, ma è più pulito così.

Il file `.ics` di un evento concluso resta dov'è: chi l'ha sottoscritto continua
a vederlo. Per un nuovo evento usa un **nuovo file** (`calendario.file`) e una
**nuova sigla**: non riusare quelli di un evento precedente.

---

## La chiave API di Anthropic (il "secret")

La chiave serve solo per leggere la cronaca. Senza, il calendario si basa sul
solo programma.

### Ottenere la chiave

1. Vai su <https://console.anthropic.com> e accedi.
2. **API Keys → Create Key**, dai un nome (per esempio `calendario-azzurri`) e
   copia la chiave (comincia con `sk-ant-`). Viene mostrata una volta sola.
3. In **Billing** imposta un limite di spesa mensile: è la tua rete di
   sicurezza.

### Metterla su GitHub

1. Nel repository: **Settings → Secrets and variables → Actions**.
2. **New repository secret**.
3. **Name**: `ANTHROPIC_API_KEY` (esattamente così).
4. **Secret**: incolla la chiave.
5. **Add secret**.

La chiave non compare mai nei log e non viene scritta in nessun file.

### Quanto costa

Il modello viene chiamato **solo quando il testo di un articolo cambia**, non a
ogni giro, e le parti fisse della richiesta vengono riusate (cache). Stima
indicativa con `claude-opus-5`: qualche centesimo per articolo letto, quindi
pochi euro al giorno nelle giornate piene. Per spendere meno puoi indicare un
modello più economico nel file dell'evento (`modello: claude-sonnet-5`). Se con
un altro modello la chiamata desse un errore sul parametro `fallbacks`,
aggiungi `ripiego: false` nella stessa fonte.

---

## Quando qualcosa va storto

Ci sono tre situazioni diverse, trattate in tre modi diversi.

**Fonte momentaneamente irraggiungibile** (il sito non risponde, rifiuta la
richiesta). Succede: le richieste arrivano da un datacenter, e a Birmingham è
capitato 3 volte su 20 la prima notte. Il programma prova 3 volte a 15 secondi
di distanza, poi rinuncia **in silenzio** e riprova al giro dopo. Il calendario
resta all'ultima versione buona. Se il programma non risponde ma la cronaca sì,
gli avanzamenti vengono applicati all'ultimo programma letto.

**Pagina cambiata nella struttura** (il blocco atteso non c'è più, troppe poche
gare, l'indirizzo dà "404", l'indice della cronaca non ha più link del tipo
atteso, la chiave API non è valida). Non si risolve da solo: il job **fallisce** e
GitHub ti manda una **mail**. Se il problema riguarda la cronaca o la chiave, il
calendario viene comunque aggiornato con il programma.

**Fonte ferma durante le gare.** La pagina risponde, ma il contenuto estratto
non cambia da troppi minuti di gara (`allarme_dopo_minuti`). Pause fra le
sessioni e notti non contano. È il difetto di Birmingham: una fonte "viva" in
apparenza ma morta nei fatti. In questo caso il workflow **apre una issue**
(scheda *Issues*, etichetta `fonte-ferma`) con il nome della fonte, l'ora
dell'ultimo contenuto nuovo e che cosa controllare. **La chiude da solo**
quando la fonte riparte.

Perché una issue e non un job fallito? Una fonte ferma resta ferma per ore. Un
job fallito ogni quarto d'ora vorrebbe dire una mail ogni quarto d'ora, tutte
uguali, e dopo tre giri non le legge più nessuno. La issue invece:

- arriva **una volta**: all'apertura GitHub manda di norma una mail a chi
  segue il repository (il proprietario lo segue già), e la notifica compare
  anche nell'app GitHub sul telefono;
- dice **che cosa** è fermo e da quando, non solo che "qualcosa è fallito";
- si chiude da sola quando il problema passa, lasciando traccia di quanto è
  durato;
- non si confonde con i guasti veri (pagina cambiata), che restano job falliti.

Perché la mail arrivi, nel repository deve essere attivo **Watch** (in alto a
destra) almeno su *Issues*. Per chi ha creato il repository lo è già.

---

## Per chi mette mano al codice

```
calendario/
  config.py        lettura e controllo di eventi/<nome>.yaml
  rete.py          download (3 tentativi a 15 s); Irraggiungibile / PaginaCambiata
  testo.py         spazi strani, righe, corpo dell'articolo, metadati, impronte
  parser/          un modulo per formato di pagina, registrati in __init__.py
    oasport.py       programma OA Sport (il parser del vecchio genera.py)
    articoli_live.py articoli live trovati da una pagina indice
  avanzamenti.py   chiamata all'API Anthropic, schema JSON e sua validazione
  nomi.py          confronto tollerante di atleti e gare
  fusione.py       applica gli esiti al programma
  ics.py           scrittura del calendario
  orari.py         sessioni di gara, minuti di gara, cron
  principale.py    un giro completo; il comando verifica
genera.py          compatibilità: `python genera.py` = Birmingham
eventi/            un file per manifestazione
tests/             test con pytest, senza rete e senza API (vedi tests/fixtures/LEGGIMI.md)
```

Comandi:

```
python -m calendario aggiorna eventi/NOME.yaml [--allarme FILE]
python -m calendario verifica eventi/NOME.yaml [--salva CARTELLA] [--esiti]
python -m calendario cron     eventi/NOME.yaml
python -m calendario file     eventi/NOME.yaml
```

Test:

```
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

Scelte da non toccare senza un buon motivo:

- **UID** = sigla + hash di gara, genere e turno. Non dipende da orario e atleti:
  un aggiornamento modifica l'evento, non lo duplica. Due gare con la stessa
  chiave ricevono un suffisso (nel file di Birmingham due batterie dei 1500
  avevano lo stesso UID, e Calendario ne mostrava una sola).
- **DTSTAMP fisso**: due esecuzioni senza cambiamenti producono file identici
  byte per byte. Lo stato (`stato.json`) non contiene l'ora dell'esecuzione,
  per lo stesso motivo.
- **Spazi**: ` `, ` `, ` ` vengono normalizzati prima di ogni
  confronto.
- "eventuale" / "eventuali" si riconoscono con `eventual[ei]`.
- **Freschezza sul contenuto estratto**, mai sulla pagina intera.
- La cronaca in ingresso al modello è testo non fidato. Lo schema limita la
  forma della risposta (sei esiti possibili, campi fissi), e un esito che non
  corrisponde a un atleta e a una gara del programma viene ignorato: nel
  peggiore dei casi un articolo può togliere o confermare un azzurro, non
  inventare gare.

### Aggiungere un parser

1. Crea `calendario/parser/nuovo.py` con una funzione
   `analizza(pagina, opzioni, evento)` che restituisce una lista di gare
   (vedi la documentazione in `calendario/parser/__init__.py`). Se la pagina non
   ha la forma attesa deve sollevare `PaginaCambiata`.
2. Registrala in `calendario/parser/__init__.py`.
3. Aggiungi una fixture in `tests/fixtures/` e un test.
4. Nel file dell'evento: `parser: nuovo`.
