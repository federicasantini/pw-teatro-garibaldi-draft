# Teatro Garibaldi

Project Work - CdS INFORMATICA PER LE AZIENDE DIGITALI (L-31)

**Tema**

1 - La digitalizzazione dell'impresa

**Traccia**

22 - Digitalizzazione dei processi aziendali in un’impresa culturale: progettazione di una piattaforma informatica per la gestione di servizi, dati e utenti 

**Titolo dell'elaborato**

La trasformazione digitale del Teatro Garibaldi: progettazione e sviluppo di un'applicazione web per la gestione dei servizi e il coinvolgimento della comunità.

**Descrizione**

Prototipo di piattaforma web per la digitalizzazione dei processi di un teatro: programmazione, prenotazione dei posti, biglietto con QR code, lista d'attesa, area personale con messaggi, check-in all'ingresso, raccolta delle recensioni, gestione del catalogo con repliche, dashboard con indicatori di attività esportabili in CSV per gli amministratori.

Il caso di studio è il **Teatro Garibaldi di Mazara del Vallo**, piccolo teatro storico di proprietà comunale e gestito direttamente dal Comune. I dati dimostrativi riproducono la sala di **92 posti**, suddivisi in platea (52), palchi (28) e loggione (12). La ripartizione per settore, i prezzi e gli spettacoli sono ipotetici.


## Stack tecnologico

| Livello | Tecnologia |
|--------------|-------------------------------------------------|
| Front-end | HTML5, JavaScript, [Bootstrap Italia](https://italia.github.io/bootstrap-italia/) 2.18 e [Design Tokens Italia](https://github.com/italia/design-tokens-italia) 1.3.3 – design system di Designers Italia |
| Back-end | Python 3.10+, Flask 3, segno (QR code) |
| Base dati | SQLite 3 (relazionale, file `data/teatro.db`) |
| Comunicazione| API REST, formato JSON, autenticazione Bearer token |
| Qualità | pytest (66 test funzionali, inclusi test di concorrenza e di sicurezza), ruff, GitHub Actions |

## Struttura del repository

```
teatro-garibaldi/
├── backend/
│ ├── app.py # application factory Flask, blueprint, intestazioni di sicurezza, file statici
│ ├── db.py # connessione SQLite, transazioni e funzioni di accesso ai dati
│ ├── schema.sql # schema relazionale (tabelle, vincoli, indici, vista)
│ ├── seed.py # dati dimostrativi della stagione (non sovrascrive senza --reset)
│ ├── auth.py # sessioni a token (hash), limite tentativi di accesso, RBAC
│ ├── audit.py # registro di audit e log di sicurezza in JSON
│ ├── rilevamento.py # regole di rilevamento e avvisi di sicurezza
│ ├── backup.py # backup verificati (SHA-256), rotazione e ripristino
│ ├── tempo.py # data/ora uniformi nel fuso del teatro
│ ├── notifiche.py # messaggi agli utenti (posta in uscita simulata)
│ ├── manutenzione.py # attività periodiche: promemoria, chiusura repliche, pulizia
│ ├── validation.py # validazione dell'input
│ ├── errors.py # errori uniformi in JSON
│ └── api/ # endpoint REST: utenti, catalogo, prenotazioni, lista_attesa, feedback, dashboard
├── frontend/
│ ├── index.html # cartellone con ricerca e filtri
│ ├── spettacolo.html # dettaglio, prenotazione, recensioni
│ ├── accedi.html # login e registrazione
│ ├── area-personale.html
│ ├── gestione.html # back-office: dashboard, check-in, spettacoli, repliche, utenti
│ ├── privacy.html # informativa sul trattamento dei dati
│ ├── accessibilita.html # bozza della dichiarazione di accessibilità (modello AgID per le PA)
│ ├── vendor/design-tokens-italia/ # variables.css: token --it-* di Designers Italia
│ ├── vendor/bootstrap-italia/ # kit Designers Italia (CSS, JS, icone, font) servito in locale
│ ├── css/fonts.css # @font-face dei font del kit (Titillium Web, Roboto Mono, Lora)
│ ├── css/style.css # solo personalizzazioni sopra il kit, scritte con i token var(--it-...)
│ └── js/ # api.js, ui.js e pagine/ (uno script per pagina: niente JS inline)
├── test/ # conftest.py, test_api.py, test_miglioramenti.py, test_sicurezza.py
├── docs/nis2.md # la piattaforma e la direttiva NIS2 (sezione della relazione)
├── .github/workflows/ci.yml # lint + test automatici a ogni push
├── docs/diagrammi/ # architettura, ER, casi d'uso, sequenza, stati
├── docs/screenshot/ # schermate del prototipo
├── scripts/screenshot.py # rigenera le schermate (Playwright) su un database dimostrativo temporaneo
└── requirements.txt
```

## Esecuzione

```bash
# 1. ambiente virtuale e dipendenze
python -m venv .venv
source .venv/bin/activate 
cd project-work-main
pip install -r requirements.txt
  # per Windows usare: .venv\Scripts\activate

# 2. creazione del database con dati dimostrativi
python -m backend.seed # rifiuta di sovrascrivere un database esistente
python -m backend.seed --reset # ricrea il database CANCELLANDO tutti i dati

# 3. avvio del server
python -m backend.app
```

Aprire il browser su **http://localhost:5000**

Variabili d'ambiente (tutte facoltative)

| Variabile | Predefinito | Significato |
|---|---|---|
| `TG_DATABASE` | `data/teatro.db` | Percorso del database |
| `TG_DEBUG` | – | `1` attiva il debugger di Flask (solo in sviluppo: consente di eseguire codice) |
| `TG_HOST` / `TG_PORT` | `127.0.0.1` / `5000` | Indirizzo e porta di ascolto |
| `TG_FUSO_ORARIO` | `Europe/Rome` | Fuso orario del teatro, usato per tutte le date |

Attività periodiche (promemoria il giorno prima dell'evento prenotato, chiusura automatica delle repliche
terminate, pulizia di sessioni e gestione tentativi di accesso), da pianificare ad esempio ogni ora con `cron` o con:

```bash
python -m backend.manutenzione
```

Backup del database e ripristino (a server fermo):

```bash
python -m backend.backup crea
```

```bash
python -m backend.backup elenco
```

```bash
python -m backend.backup ripristina data/backup/teatro-AAAAMMGG-HHMMSS.db --conferma
```

Il log di sicurezza (una riga JSON per evento) è in `data/log/sicurezza.log`; la cartella si cambia con `TG_LOG_DIR`, quella dei backup con `TG_BACKUP_DIR`.

Account dimostrativi:

| Ruolo | Email | Password |
|-------------|------------------------------------|------------------|
| Spettatore | anna.rinaldi@example.com | Spettatore2026! |
| Operatore | biglietteria@teatrogaribaldi.it | Operatore2026! |
| Admin | admin@teatrogaribaldi.it | Admin2026! |

Test automatici e controllo dello stile:
```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest -v
```

## Documentazione delle API

- Le risposte sono in JSON (tranne QR code in SVG e le esportazioni in CSV);
- Gli errori hanno la forma `{"errore": "...", "dettagli": {...}}`;
- Gli importi sono espressi in euro nelle API e memorizzati in centesimi nel database;
- Le chiamate protette richiedono l'intestazione `Authorization: Bearer <token>` ottenuta dalla login.

| Metodo | Percorso | Ruolo minimo | Descrizione |
|---|---|---|---|
| POST | `/api/auth/registrazione` | – | Crea un account e restituisce il token |
| POST | `/api/auth/login` | – | Autentica e restituisce `{token, utente}` |
| POST | `/api/auth/logout` | – | Invalida il token |
| GET | `/api/auth/me` | spettatore | Profilo dell'utente autenticato |
| GET | `/api/auth/me/dati` | spettatore | Esporta tutti i propri dati personali in JSON (rif. GDPR artt. 15 e 20) |
| DELETE | `/api/auth/me` | spettatore | Elimina e anonimizza l'account, con conferma della password (art. 17) |
| GET | `/api/notifiche` | spettatore | Messaggi ricevuti (conferme, annullamenti, promemoria, lista d'attesa) |
| GET | `/api/spettacoli?genere=&q=` | – | Spettacoli con prossima data e voto medio |
| GET | `/api/spettacoli/{id}` | – | Dettaglio con elenco repliche e disponibilità |
| POST | `/api/spettacoli` | operatore | Crea uno spettacolo |
| PUT | `/api/spettacoli/{id}` | operatore | Modifica uno spettacolo |
| DELETE | `/api/spettacoli/{id}` | admin | Elimina dal calendario (eliminazione logica) |
| GET | `/api/repliche?da=&a=` | – | Calendario repliche con occupazione |
| GET | `/api/repliche/{id}/disponibilita` | – | Posti liberi e prezzo per settore |
| POST | `/api/repliche` | operatore | Programma una replica; facoltativo `prezzi: {settore_id: euro}`. Rifiuta sovrapposizioni in sala (durata + 60 min di cambio scena) |
| PATCH | `/api/repliche/{id}` | operatore | Cambia stato: `programmata → annullata` (annulla le prenotazioni e avvisa) o `programmata → conclusa` (solo dopo l'inizio) |
| POST / DELETE | `/api/repliche/{id}/lista-attesa` | spettatore | Iscrizione/uscita dalla lista d'attesa di una replica esaurita |
| GET | `/api/lista-attesa` | spettatore | Proprie iscrizioni in lista d'attesa |
| GET | `/api/sale` | – | Sale e settori |
| GET | `/api/tariffe` | – | Tariffe (intero e riduzioni) |
| POST | `/api/prenotazioni` | spettatore | Prenota da 1 a 6 posti con tariffa; max 6 posti per utente ed evento (transazione anti-overbooking) |
| GET | `/api/prenotazioni?mie=1&stato=&replica_id=` | spettatore | Proprie prenotazioni (per operatore ed admin: tutte) |
| DELETE | `/api/prenotazioni/{id}` | spettatore | Annulla (fino a 24h prima) e avvisa la lista d'attesa |
| GET | `/api/prenotazioni/{id}/qr` | spettatore | QR code del biglietto (SVG) |
| POST | `/api/prenotazioni/check-in` | operatore | Convalida il codice all'ingresso (da 2h prima a fine spettacolo, una sola volta anche con richieste simultanee) |
| GET | `/api/spettacoli/{id}/feedback` | – | Recensioni di uno spettacolo |
| POST | `/api/feedback` | spettatore | Recensione (solo spettacoli visti, una per spettacolo) |
| GET | `/api/dashboard` | operatore | KPI: biglietti, incasso (realizzato/prevendita), riempimento delle repliche concluse, prevendita, voti, tariffe, andamento |
| GET | `/api/dashboard/export?dati=spettacoli\|prenotazioni` | operatore | Esportazione CSV (senza dati personali) |
| GET | `/api/utenti` | admin | Elenco utenti |
| PATCH | `/api/utenti/{id}` | admin | Modifica il ruolo |
| GET | `/api/audit?categoria=&esito=&email=&da=&limite=` | admin | Registro di audit |
| GET | `/api/avvisi?stato=aperti\|tutti` | admin | Avvisi di sicurezza |
| PATCH | `/api/avvisi/{id}` | admin | Segna un avviso come gestito con nota obbligatoria |

Esempio di prenotazione:

```http
POST /api/prenotazioni
Authorization: Bearer 3bS0k...
Content-Type: application/json

{"replica_id": 14, "settore_id": 3, "num_posti": 2, "tariffa_id": 2}
```

```json
201 Created
{"id": 2604, "codice": "TG-48BQ4B", "num_posti": 2, "settore": "Loggione", "tariffa": "Under 26",
 "prezzo_unitario": 10.5, "importo_totale": 21.0, "stato": "confermata", "titolo": "Lo schiaccianoci", ...}
```

Codici di stato usati: 200, 201, 204, 400 (JSON non valido), 401 (non autenticato), 403 (ruolo insufficiente), 404, 409 (conflitto: posti esauriti, limite per utente, duplicati, sala occupata, transizione di stato non consentita, biglietto per un'altra data), 422 (dati non validi), 429 (troppi tentativi di accesso).

## Interfaccia e design system

L'interfaccia è costruita con **Bootstrap Italia 2.18**, il kit di sviluppo di [Designers Italia](https://designers.italia.it/) basato su Bootstrap 5, che applica le linee guida di design per i servizi digitali della PA (font Titillium Web, palette, componenti accessibili).

| Elemento | Componente del kit |
|---|---|
| Testata | Header *slim* + centrale + navbar con menu laterale su mobile, menu utente a tendina |
| Navigazione | Skiplink, breadcrumb, schede (*nav-tabs*), torna su |
| Spettacoli | Card con categoria, filtri, campo di ricerca |
| Prenotazione | Radio con barre *progress*, *select* del kit, alert di esito |
| Recensioni | Componente *rating* a stelle, *collapse* |
| Area personale | Card dei biglietti, *accordion* dei messaggi, *callout* privacy, finestra *modal* per la cancellazione |
| Area gestione | Card KPI, grafici con *progress*, tabelle, form, *notification* di conferma |
| Accesso | Campo password con mostra/nascondi, *checkbox*, *callout* |
| Piè di pagina | *Footer* con colonne di link e *small prints* |

Le personalizzazioni (`css/style.css`) usano **le variabili dei Design Tokens Italia 1.3.3** (`frontend/vendor/design-tokens-italia/variables.css`) per colori, tipografia, spaziature, bordi, raggi e dimensioni delle icone: nessun colore è scritto a mano. Anche le locandine dei generi usano famiglie di colore dei token (blue, slate, teal, seagreen, orange).

### Accessibilità

- Contrasti WCAG 2.1 AA: testo ≥ 4,5:1, contorni dei controlli e indicatori grafici ≥ 3:1;
- Verifica con axe-core (WCAG 2.0/2.1 A e AA) su 13 pagine e stati: nessuna violazione rilevata;
- Nessuno scorrimento orizzontale a 320 pixel di larghezza; prenotazione completabile da tastiera;
- Bozza della **dichiarazione di accessibilità** in `frontend/accessibilita.html`, raggiungibile tramite link nel footer, con le non conformità note (grafico giornaliero senza alternativa testuale e scadenza della sessione senza preavviso) e le parti da completare.

Il kit (CSS, bundle JS con Popper, sprite delle icone, font) è incluso in `frontend/vendor/` e servito dallo stesso server: non è presente alcuna richiesta a CDN, coerente con la Content Security Policy. Le conferme usano la finestra modale del kit al posto di `confirm()`.

## Sicurezza

- Password con hash (Werkzeug); token di sessione casuali a 256 bit, salvati nel database **solo come hash SHA-256**, con scadenza a 8 ore;
- Dopo 5 accessi falliti in 15 minuti per lo stesso account (o 20 dallo stesso IP) la login risponde `429` con `Retry-After`;
- Controllo degli accessi per ruolo; validazione del tipo e della lunghezza di ogni campo in ingresso; SQL parametrico;
- Intestazioni `Content-Security-Policy` (niente script inline o esterni, solo risorse dello stesso sito), `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`; `Cache-Control: no-store`
 sulle API;
- Operazioni concorrenti sicure: prenotazione in transazione `BEGIN IMMEDIATE`; check-in e annullamenti con aggiornamenti condizionati (`... WHERE stato = 'confermata'`), verificati da test con richieste parallele;
- Debugger disattivato di default.

## Registro di audit, avvisi e backup (NIS2)

A supporto delle misure di gestione del rischio previste dalla direttiva NIS2 (D.Lgs. 138/2024, art. 24) la piattaforma offre:
- **Registro di audit** a sola aggiunta (accessi, ruoli, catalogo, check-in, esportazioni, backup), conservato 365 giorni e consultabile dagli amministratori nella scheda *Sicurezza*;
- **Log di sicurezza** in formato JSON (`data/log/sicurezza.log`);
- **Regole di rilevamento** (forza bruta, password spraying, nuovo amministratore, accessi negati, esportazioni ripetute, check-in sospetti) che generano avvisi e avvisano gli amministratori;
- **Backup verificati** con impronta SHA-256, rotazione e ripristino con copia di sicurezza.

L'analisi di applicabilità della NIS2 al teatro, la corrispondenza con le misure dell'art. 24 e la procedura dall'avviso di notifica degli incidenti sono in [`docs/nis2.md`](docs/nis2.md).

## Protezione dei dati (GDPR)

- Consenso esplicito in registrazione;
- Accesso e portabilità: l'utente scarica in JSON tutti i propri dati dall'area personale;
- Cancellazione: quando l'account viene eliminato, viene anonimizzato in modo irreversibile; le prenotazioni future sono annullate, le sessioni, i messaggi e i commenti sono eliminati; restano, senza dati identificativi, i movimenti utili alla contabilità e i voti per le statistiche;
- Minimizzazione: le esportazioni CSV per la direzione non contengono dati personali.

## Note sul prototipo
I dati sono simulati: il Teatro Garibaldi è trattato come caso di studio e utenti, spettacoli e date della stagione sono ipotetici.

Le email non vengono spedite: i messaggi (conferme, annullamenti, promemoria, avvisi della lista d'attesa) sono salvati nella tabella `notifiche` e mostrati nell'area personale. Per l'invio reale è necessario sostituire la funzione `invia` in `backend/notifiche.py` con una spedizione SMTP.

La lettura del QR code da fotocamera usa l'API nativa `BarcodeDetector` (Chrome, Edge, Android); sugli altri browser resta disponibile l'inserimento manuale del codice.


