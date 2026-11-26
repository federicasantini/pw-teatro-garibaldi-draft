# La piattaforma e la direttiva NIS2

*Approfondimento del project work*

## 1. Il quadro normativo

La direttiva UE 2022/2555, detta **NIS2**, chiede agli Stati membri dell'Unione Europea di innalzare il livello di cybersicurezza dei soggetti che erogano servizi importanti per l'economia e la società. In Italia è stata recepita con il **D.Lgs. del 4 settembre 2024, n. 138**. L'autorità nazionale competente è l'**Agenzia per la Cybersicurezza Nazionale (ACN)** e gli incidenti si notificano al **CSIRT Italia**.

Per i soggetti inclusi, gli obblighi principali sono quattro:
- **Governance (art. 23)**: gli organi di amministrazione approvano le misure di sicurezza, ne sovrintendono l'attuazione, ne rispondono e seguono una formazione specifica;
- **Misure di gestione dei rischi (art. 24)**: misure tecniche, operative e organizzative proporzionate al rischio (analisi dei rischi, gestione degli incidenti, continuità operativa e backup, sicurezza della catena di approvvigionamento, sviluppo sicuro, controllo degli accessi, crittografia, formazione);
- **Notifica degli incidenti significativi (art. 25)** al CSIRT Italia, in più fasi: preallarme entro 24 ore, notifica entro 72 ore, relazione finale entro un mese;
- **Registrazione e aggiornamento dei dati** sulla piattaforma digitale dell'ACN.

## 2. L'organizzazione rientra nella NIS2?

**La NIS2 si applica alle organizzazioni, non ai software.** Non esiste quindi un'applicazione "conforme alla NIS2", ma esiste un'organizzazione conforme che usa strumenti in grado di supportare i suoi obblighi.

Il Teatro Garibaldi è di proprietà del **Comune di Mazara del Vallo**, che lo gestisce direttamente: il soggetto da valutare è quindi il Comune.

Un teatro non rientra nei settori "altamente critici" o "critici" della direttiva (allegati I e II), ma il decreto italiano prevede però alcune **categorie ulteriori**:
- **Allegato III – pubbliche amministrazioni**: tra gli enti locali, il perimetro comprende regioni, province autonome, città metropolitane, comuni capoluogo di regione e **comuni con più di 100.000 abitanti**. Mazara del Vallo conta circa 50.000 abitanti e non è capoluogo di regione: il Comune quindi **non rientra** di diritto nel perimetro;
- **Allegato IV – soggetti che svolgono attività di interesse culturale**: l'ACN può individuarli, su proposta dell'autorità di settore (il Ministero della Cultura), indipendentemente dalle loro dimensioni. Gli obblighi scatterebbero solo dopo questa designazione;
- **Catena di approvvigionamento**: se il Comune affidasse servizi a fornitori soggetti alla NIS2, o fornisse servizi a un soggetto NIS2, potrebbero esserci requisiti di sicurezza per contratto.

Anche fuori dal perimetro NIS2, il Comune resta tenuto, come ogni pubblica amministrazione, alle misure di sicurezza dei dati e dei sistemi previste dal **Codice dell'amministrazione digitale (art. 51)** e alle **Misure minime di sicurezza ICT per le PA** dell'AgID, oltre che al GDPR.

**Conclusione per il caso di studio**
Senza una designazione dell'ACN, il Comune non è obbligato ai sensi della NIS2 per il servizio del teatro e il prototipo (con dati simulati) certamente non lo è. È comunque utile progettare la piattaforma in modo che **supporti** le misure dell'art. 24:
- sono buone pratiche di sicurezza, in larga parte già richieste a una PA;
- il Comune sarebbe pronto in caso di designazione o di richieste di un partner.

## 3. Cosa fa la piattaforma e cosa resta all'organizzazione

La tabella confronta le aree di misure previste dalla direttiva (art. 21, par. 2, ripreso dall'art. 24 del decreto) con ciò che fa il prototipo.

| Area di misure | Supporto della piattaforma | A carico dell'organizzazione |
|---|---|---|
| a) Analisi dei rischi e politiche di sicurezza | – | Analisi dei rischi, politica di sicurezza approvata dagli organi del Comune |
| b) Gestione degli incidenti | **Registro di audit**, **log di sicurezza**, **regole di rilevamento con avvisi** | Procedura di valutazione e notifica, ruoli e reperibilità |
| c) Continuità operativa, backup, ripristino | **Backup verificati con impronta, rotazione, ripristino con copia di sicurezza** | Pianificazione, copie fuori sede, prove periodiche di ripristino, piano di continuità |
| d) Catena di approvvigionamento | Componenti grafici serviti in locale con versione fissata, nessun servizio esterno | Valutazione dei fornitori (hosting, connettività) |
| e) Sviluppo sicuro e manutenzione | Validazione dell'input, SQL parametrico, Content Security Policy, test automatici, controlli di sicurezza del codice nella CI | Gestione delle vulnerabilità delle dipendenze *(non trattata nel project work)* |
| f) Valutazione dell'efficacia delle misure | 66 test automatici, di cui 19 sulle misure di sicurezza | Audit periodici, revisione degli avvisi |
| g) Igiene informatica e formazione | Password robuste obbligatorie | Formazione del personale e della direzione |
| h) Crittografia | Password con hash, token di sessione salvati solo come hash SHA-256 | Cifratura dei dischi e dei backup, HTTPS in produzione *(non trattato nel project work)* |
| i) Controllo degli accessi e risorse umane | Ruoli (spettatore, operatore, admin), blocco dopo accessi falliti, sessioni a scadenza, **avviso su ogni nuovo amministratore** | Assegnazione e revoca dei ruoli, ingresso e uscita del personale |
| j) Autenticazione multifattore | *Non implementata nel prototipo* | Da valutare per il personale con ruoli di gestione |

Le misure *non trattate* sono state escluse dal perimetro del project work e sono indicate come possibili sviluppi futuri.

## 4. Le misure implementate

### 4.1 Registro di audit

Tabella `registro_audit` del database
Per ogni evento registra **quando**, **chi** (utente, ruolo, email), **da dove** (indirizzo IP), **cosa** (azione e oggetto) e con quale **esito** (`ok`, `fallito`, `negato`).

| Categoria | Eventi registrati |
|---|---|
| `accesso` | accesso riuscito o fallito, account bloccato, uscita, tentativo di usare funzioni non consentite al proprio ruolo |
| `account` | registrazione, cambio di ruolo (con ruolo precedente e nuovo), esportazione dei propri dati, eliminazione dell'account |
| `catalogo` | creazione, modifica e ritiro di spettacoli; creazione di repliche e cambi di stato |
| `prenotazioni` | check-in riusciti e rifiutati, annullamenti fatti dalla biglietteria |
| `dati` | esportazioni CSV della dashboard |
| `sistema` | backup creati e ripristinati, avvisi gestite |

Scelte di progetto:
- **A sola aggiunta**: due trigger SQLite impediscono di modificare le voci e di cancellarle prima che siano trascorsi 365 giorni così chi compie un'azione non può cancellare la traccia dall'applicazione;
- **Conservazione limitata**: le voci più vecchie di 365 giorni vengono eliminate dallo script di manutenzione. Il registro contiene dati personali (email, IP), quindi va rispettato il principio di limitazione della conservazione del GDPR;
- **Minimizzazione**: si registrano gli eventi di sicurezza e le azioni dello staff, non la normale attività degli spettatori come ogni singola prenotazione. Password e token non vengono mai registrati;
- **Account eliminati**: dopo la cancellazione di un account, l'evento non riporta più l'email ma solo l'identificativo numerico;
- **Consultazione**: il registro è consultabile solo dagli amministratori, nella scheda "Sicurezza" dell'area gestione.

### 4.2 Log di sicurezza

Ogni evento del registro viene scritto nel file `data/log/sicurezza.log`, **una riga JSON per evento**, con rotazione automatica (5 file da 1 MB). Il formato JSON permette in futuro di inviare i log a un sistema di raccolta centralizzato senza modificare l'applicazione. Il file è anche una seconda traccia, indipendente dal database: resta disponibile anche se il database viene ripristinato da un backup.

### 4.3 Rilevamento e avvisi

Ogni evento registrato passa per alcune **regole di rilevamento** (modulo `backend/rilevamento.py`). Ogni regola è un conteggio sugli eventi recenti.

| Regola | Cosa rileva | Soglia | Gravità |
|---|---|---|---|
| `forza_bruta` | tentativi ripetuti di indovinare la password di un account | l'account viene bloccato (5 errori in 15 minuti) | media |
| `password_spraying` | tentativi di password comuni su molti account | ≥ 5 account diversi dallo stesso IP in un'ora | alta |
| `nuovo_amministratore` | assegnazione del ruolo di amministratore | ogni volta | alta |
| `accessi_negati` | un utente prova funzioni non consentite al suo ruolo | ≥ 10 volte in 15 minuti | media |
| `esportazioni_ripetute` | possibile estrazione massiva di dati | ≥ 5 esportazioni in un'ora | media |
| `check_in_sospetti` | codici falsi o copiati presentati all'ingresso | ≥ 10 codici rifiutati allo stesso varco in 15 minuti | media |

Quando una regola scatta:
1. si crea un avviso nella tabella `avvisi`, al massimo uno per regola, soggetto e ora, per non sommergere gli amministratori;
2. tutti gli amministratori ricevono un messaggio nella propria area personale;
3. nella scheda "Sicurezza" compare l'avviso.

L'amministratore **valuta** l'avviso e lo chiude con una nota obbligatoria sull'esito, ad esempio "falso positivo: test interno" oppure "incidente: avviata la procedura". Anche la chiusura finisce nel registro di audit.

### 4.4 Backup e ripristino

Comando `python -m backend.backup` (modulo `backend/backup.py`):

| Comando | Cosa fa |
|---|---|
| `crea` | Copia coerente del database con l'API di backup di SQLite, controllo di integrità, impronta SHA-256 in un file `.sha256`, conservazione degli ultimi 14 backup |
| `elenco` | Elenca i backup e ne verifica lo stato |
| `verifica <file>` | Ricalcola l'impronta e controlla l'integrità: un file alterato o danneggiato viene segnalato |
| `ripristina <file> --conferma` | Ripristina solo un backup verificato; prima salva il database attuale in una copia di sicurezza, così anche un ripristino sbagliato si può annullare |

Creazioni e ripristini sono annotati nel registro di audit. Un test simula una perdita di dati, ripristina il backup e controlla che i dati siano tornati: è il "test di ripristino" che le buone pratiche raccomandano di eseguire periodicamente.

## 5. Dall'avviso alla notifica: la procedura organizzativa

La piattaforma rileva e documenta, ma la decisione resta sempre ad una persona. Un avviso **non è di per sé un "incidente significativo"**: lo diventa se causa, o può causare, una grave perturbazione del servizio o perdite economiche, oppure danni considerevoli ad altre persone. La procedura che il Comune dovrebbe adottare, se fosse soggetto alla NIS2, è questa:
1. **Valutazione**: il referente per la sicurezza esamina l'avviso. Il registro di audit fornisce la cronologia degli eventi: chi, cosa, quando e da quale IP;
2. **Contenimento**: si interviene sul problema, ad esempio revocando un ruolo, cambiando le credenziali o ripristinando un backup;
3. **Decisione**: si stabilisce se l'incidente è significativo;
4. **Notifica.**: se l'incidente è significativo, si notifica al CSIRT Italia: preallarme entro 24 ore, notifica entro 72 ore, relazione finale entro un mese. Se sono coinvolti dati personali, si valuta separatamente anche la notifica al Garante (GDPR, art. 33, entro 72 ore);
5. **Chiusura**: l'avviso viene chiuso nella piattaforma con una nota che rimanda alla documentazione dell'incidente.

## 6. Verifica

Le misure sono coperte da test automatici in `test/test_sicurezza.py` (TC40–TC58), che verificano che:
- gli accessi vengano registrati senza password;
- il registro non sia modificabile;
- ogni regola di rilevamento scatti alla soglia prevista e una sola volta;
- la gestione degli avvisi richieda la nota;
- il backup ripristini i dati e che un backup alterato venga rifiutato;
- la conservazione del registro sia rispettata.

## 7. Limiti e sviluppi futuri

Restano fuori dal perimetro del project work e andrebbero affrontati prima di un uso reale:
- **Autenticazione multifattore** per gli utenti con ruoli di gestione;
- **Gestione delle vulnerabilità** delle librerie usate (aggiornamenti e verifiche periodiche);
- **Messa in produzione sicura**: HTTPS, server applicativo adatto alla produzione, cifratura dei dischi e dei backup;
- **Conservazione dei backup e dei log fuori dal server** ad esempio con la regola 3-2-1: tre copie su due supporti diversi uno dei quali in un'altra sede;
- **Invio dei log a un sistema centralizzato (SIEM)** e regole di rilevamento più evolute;
- **Misure organizzative**: analisi dei rischi, politiche, formazione, valutazione dei fornitori, piano di continuità operativa.

## Fonti

- Direttiva UE 2022/2555 (NIS2)
- D.Lgs. 4 settembre 2024, n. 138 (recepimento della direttiva NIS2)
- Agenzia per la Cybersicurezza Nazionale: <https://www.acn.gov.it/>
- Determinazione ACN n. 164179 del 14 aprile 2025: specifiche di base per gli obblighi degli artt. 23, 24, 25, 29 e 32 del D.Lgs. 138/2024
