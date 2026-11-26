# Registro delle modifiche

## 1.5.0 – Teatro comunale di 92 posti

- Dati dimostrativi riallineati alla sala reale: **92 posti** in platea (52), palchi (28) e
  loggione (12); ripartizione e prezzi ipotetici. Test aggiornati (il settore "Galleria" diventa
  "Loggione"; TC39 usa la platea).
- Gestione pubblica: intestazione e footer indicano il **Comune di Mazara del Vallo**.
- **Dichiarazione di accessibilità** riscritta sul modello AgID per le pubbliche amministrazioni
  (sezione 1 con procedura di attuazione presso il Difensore civico per il digitale; sezione 2 con
  le informazioni sul sito e sulla struttura da completare a cura del Comune).
- **Informativa privacy**: titolare (Comune), responsabile della protezione dei dati, basi giuridiche
  (art. 6, par. 1, lett. b ed e), tempi di conservazione incluso il registro di audit (365 giorni),
  reclamo al Garante.
- `docs/nis2.md`: applicabilità valutata sul Comune (allegato III, soglia dei 100.000 abitanti;
  allegato IV) e richiamo all'art. 51 del CAD.
- Schermate in `docs/screenshot/` rigenerate con il nuovo script `scripts/screenshot.py`
  (Playwright, database temporaneo: i dati in `data/` non vengono toccati).

## 1.4.0 – Design Tokens Italia e accessibilità

- Inclusi i **Design Tokens Italia 1.3.3** (`vendor/design-tokens-italia/variables.css`), caricati in
  tutte le pagine.
- `style.css` riscritto usando solo le variabili `--it-*` per colori, tipografia, spaziature, bordi,
  raggi e icone; rimosse le variabili `--tg-*` e i colori scritti a mano.
- Locandine dei generi sulla palette dei token (blue, slate, teal, seagreen, orange), con testo
  bianco ≥ 4,5:1 su tutto il gradiente; hero con colori del tema.
- Contorni dei riquadri cliccabili (date, settori) e indicatori grafici portati ad almeno 3:1
  (`--it-color-border-secondary`); stato disabilitato con i token dedicati invece dell'opacità.
- Corretto lo scorrimento orizzontale a 320 px (spaziature delle griglie, KPI, elementi
  `visually-hidden` nelle aree scorrevoli).
- Bozza della **dichiarazione di accessibilità** (`accessibilita.html`), collegata dal footer.

## 1.3.0 – Misure di sicurezza a supporto della NIS2

- **Registro di audit** (`registro_audit`): accessi, ruoli, catalogo, check-in, esportazioni,
  eliminazioni di account, backup. A sola aggiunta (trigger SQLite), conservazione 365 giorni,
  senza password o token. Consultabile dagli amministratori (`GET /api/audit`).
- **Log di sicurezza** in JSON con rotazione (`data/log/sicurezza.log`).
- **Rilevamento e avvisi**: sei regole (forza bruta, password spraying, nuovo amministratore,
  accessi negati, esportazioni ripetute, check-in sospetti), avvisi senza duplicati, avviso agli
  amministratori, chiusura con nota obbligatoria (`/api/avvisi`).
- Nuova scheda **Sicurezza** nell'area gestione (solo amministratori).
- **Backup e ripristino** (`python -m backend.backup`): copia coerente, controllo di integrità,
  impronta SHA-256, rotazione, ripristino solo di backup verificati con copia di sicurezza.
- La manutenzione elimina le voci del registro oltre il periodo di conservazione.
- `docs/nis2.md`: applicabilità della NIS2 al teatro, corrispondenza con l'art. 24, procedura
  dall'avviso alla notifica, limiti.
- 19 nuovi test (`test/test_sicurezza.py`).

## 1.2.0 – Interfaccia con Bootstrap Italia

- Tutte le pagine riscritte con il design system di **Designers Italia** (Bootstrap Italia 2.18.3):
  header slim/centrale/navbar con menu mobile, footer, skiplink, breadcrumb, card, nav-tabs,
  form e select del kit, rating, accordion, callout, modal, notification, progress, torna su.
- Icone dallo sprite SVG del kit; font Titillium Web, Roboto Mono e Lora serviti localmente
  (`css/fonts.css`): eliminata la dipendenza da Google Fonts.
- Finestre di conferma con il componente *modal* al posto di `confirm()`; notifiche con il
  componente *notification*.
- Nuova pagina `privacy.html` (informativa), collegata dal footer e dalla registrazione.
- CSP più restrittiva: `style-src` e `font-src` solo dallo stesso sito.
- `style.css` ridotto alle sole personalizzazioni di dominio (locandine, biglietti, grafici, QR).
- Nuovo test: il kit è servito in locale e nessuna pagina carica risorse esterne.
- Screenshot della documentazione rigenerati.

## 1.1.0 – Revisione del prototipo

### Correzioni
- Gli input con tipo errato (es. un numero al posto di un testo) restituiscono `422` invece di `500`
  (`validation.testo`, applicato a login, registrazione, check-in, catalogo, feedback).
- Programmazione delle repliche: impedite le sovrapposizioni nella stessa sala considerando la durata
  dello spettacolo e 60 minuti di cambio scena (prima veniva bloccato solo l'orario identico).
- Stati della replica governati da una tabella di transizioni: `annullata` e `conclusa` sono stati finali;
  una replica può essere conclusa solo dopo l'inizio. Una data annullata si può riprogrammare.
- Check-in accettato solo per la replica del biglietto, da 2 ore prima dell'inizio a fine spettacolo.
- Check-in e annullamenti atomici (aggiornamento condizionato): due richieste simultanee non convalidano
  due volte lo stesso biglietto.
- L'attributo HTML `hidden` non era rispettato dagli elementi con una regola `display` nel CSS.

### Sicurezza
- Debugger disattivato di default (`TG_DEBUG=1` per attivarlo); server in ascolto su `127.0.0.1`.
- Token di sessione salvati come hash SHA-256; pulizia delle sessioni scadute.
- Limite ai tentativi di accesso falliti (5 per account / 20 per IP in 15 minuti → `429`).
- Data e ora uniformi nel fuso del teatro (`tempo.py`): eliminato il misto UTC/ora locale.
- Intestazioni di sicurezza (CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy) e
  `Cache-Control: no-store` sulle API; script spostati dall'HTML a file `.js` dedicati.

### Modello dati
- Importi in centesimi (interi) invece di `REAL`.
- Tariffe (intero, Under 26, Over 65, Ragazzi under 14) e listino specifico per replica (`prezzi_replica`).
- Massimo 6 posti per utente e per replica.
- `seed.py` non sovrascrive un database esistente senza `--reset`.

### Nuove funzionalità
- QR code del biglietto nell'area personale e lettura da fotocamera nel check-in.
- Messaggi agli utenti (conferma, annullamento, replica annullata, posti liberati, promemoria) con
  posta in uscita simulata e pagina "Messaggi".
- Lista d'attesa per le repliche esaurite, con avviso in ordine di iscrizione.
- GDPR: esportazione dei propri dati in JSON e cancellazione/anonimizzazione dell'account.
- Dashboard: riempimento calcolato sulle repliche concluse e prevendita separata, incasso realizzato e
  in prevendita, biglietti per tariffa, lista d'attesa; esportazione CSV senza dati personali.
- `python -m backend.manutenzione`: promemoria, chiusura automatica delle repliche, pulizia.

### Qualità
- Test passati da 18 a 46, inclusi test con richieste concorrenti (overbooking e doppio check-in).
- Eliminate le query N+1 su cartellone, calendario repliche e sale.
- `ruff` (stile, bug comuni, sicurezza) e workflow GitHub Actions con lint e test su Python 3.10 e 3.12.
- Diagrammi e screenshot aggiornati; nuovo diagramma degli stati della replica.
