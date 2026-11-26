-- =====================================================================
--  Teatro Garibaldi
--  DB relazionale (SQLite 3)
--
--  Convenzioni:
--  a) importi in centesimi (INTEGER) per evitare errori di arrotondamento;
--  b) date-time ora locale del teatro, testo ISO 8601 ('YYYY-MM-DDTHH:MM:SS' per gli istanti, 'YYYY-MM-DDTHH:MM' per gli spettacoli)
--
--  ATTENZIONE: lo script ricrea tutte le tabelle e cancella i dati esistenti
--  Viene eseguito tramite `python -m backend.seed`
-- =====================================================================

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_occupazione;
DROP TABLE IF EXISTS avvisi;
DROP TABLE IF EXISTS registro_audit;
DROP TABLE IF EXISTS notifiche;
DROP TABLE IF EXISTS lista_attesa;
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS prenotazioni;
DROP TABLE IF EXISTS prezzi_replica;
DROP TABLE IF EXISTS repliche;
DROP TABLE IF EXISTS spettacoli;
DROP TABLE IF EXISTS tariffe;
DROP TABLE IF EXISTS settori;
DROP TABLE IF EXISTS sale;
DROP TABLE IF EXISTS tentativi_login;
DROP TABLE IF EXISTS sessioni;
DROP TABLE IF EXISTS utenti;

-- Utenti della piattaforma: spettatori, operatori di biglietteria, amministratori

CREATE TABLE utenti (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nome               TEXT    NOT NULL,
    cognome            TEXT    NOT NULL,
    email              TEXT    NOT NULL UNIQUE,
    password_hash      TEXT    NOT NULL,
    ruolo              TEXT    NOT NULL DEFAULT 'spettatore'
                       CHECK (ruolo IN ('spettatore', 'operatore', 'admin')),
    consenso_privacy   INTEGER NOT NULL DEFAULT 0 CHECK (consenso_privacy IN (0, 1)),
    data_registrazione TEXT    NOT NULL,
    eliminato_il       TEXT                       -- account cancellato e anonimizzato (GDPR art. 17)
);

-- Sessioni autenticate - viene memorizzato solo l'hash SHA-256 del token

CREATE TABLE sessioni (
    token_hash TEXT    PRIMARY KEY,
    utente_id  INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
    creata_il  TEXT    NOT NULL,
    scade_il   TEXT    NOT NULL
);
CREATE INDEX idx_sessioni_scadenza ON sessioni(scade_il);

-- Tentativi di accesso falliti (limitare gli attacchi a forza bruta)

CREATE TABLE tentativi_login (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    email  TEXT NOT NULL,
    ip     TEXT NOT NULL,
    quando TEXT NOT NULL
);
CREATE INDEX idx_tentativi_email ON tentativi_login(email, quando);
CREATE INDEX idx_tentativi_ip    ON tentativi_login(ip, quando);

-- Sale del teatro (una sola)

CREATE TABLE sale (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nome     TEXT    NOT NULL UNIQUE,
    capienza INTEGER NOT NULL CHECK (capienza > 0)
);

-- Settori di una sala (platea, palchi, galleria) con prezzo base (intero)

CREATE TABLE settori (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sala_id      INTEGER NOT NULL REFERENCES sale(id) ON DELETE CASCADE,
    nome         TEXT    NOT NULL,
    posti_totali INTEGER NOT NULL CHECK (posti_totali > 0),
    prezzo_cent  INTEGER NOT NULL CHECK (prezzo_cent >= 0),
    UNIQUE (sala_id, nome)
);

-- Tariffe (intero e riduzioni) applicate al settore

CREATE TABLE tariffe (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    codice             TEXT    NOT NULL UNIQUE,
    nome               TEXT    NOT NULL,
    descrizione        TEXT,
    sconto_pct         INTEGER NOT NULL DEFAULT 0 CHECK (sconto_pct BETWEEN 0 AND 100),
    richiede_documento INTEGER NOT NULL DEFAULT 0 CHECK (richiede_documento IN (0, 1)),
    attiva             INTEGER NOT NULL DEFAULT 1 CHECK (attiva IN (0, 1))
);

-- Catalogo degli spettacoli in programmazione

CREATE TABLE spettacoli (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    titolo         TEXT    NOT NULL,
    autore         TEXT,
    compagnia      TEXT,
    genere         TEXT    NOT NULL
                   CHECK (genere IN ('prosa', 'lirica', 'danza', 'musica', 'ragazzi')),
    descrizione    TEXT,
    durata_minuti  INTEGER CHECK (durata_minuti > 0),
    attivo         INTEGER NOT NULL DEFAULT 1 CHECK (attivo IN (0, 1)),
    creato_il      TEXT    NOT NULL
);

-- Repliche di uno spettacolo

CREATE TABLE repliche (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    spettacolo_id         INTEGER NOT NULL REFERENCES spettacoli(id) ON DELETE CASCADE,
    sala_id               INTEGER NOT NULL REFERENCES sale(id),
    data_ora              TEXT    NOT NULL,          -- 'YYYY-MM-DDTHH:MM'
    stato                 TEXT    NOT NULL DEFAULT 'programmata'
                          CHECK (stato IN ('programmata', 'annullata', 'conclusa')),
    promemoria_inviato_il TEXT
);

-- Una replica annullata si può riprogrammare
-- Controllo su sovrapposizioni parziali (durata + cambio scena)

CREATE UNIQUE INDEX idx_repliche_sala_ora ON repliche(sala_id, data_ora) WHERE stato <> 'annullata';
CREATE INDEX idx_repliche_data ON repliche(data_ora);

-- Listino di una replica, se assente vale il prezzo del settore

CREATE TABLE prezzi_replica (
    replica_id  INTEGER NOT NULL REFERENCES repliche(id) ON DELETE CASCADE,
    settore_id  INTEGER NOT NULL REFERENCES settori(id),
    prezzo_cent INTEGER NOT NULL CHECK (prezzo_cent >= 0),
    PRIMARY KEY (replica_id, settore_id)
);

-- Prenotazioni dei posti per settore e tariffa per una replica

CREATE TABLE prenotazioni (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    codice               TEXT    NOT NULL UNIQUE,   -- codice mostrato all'ingresso
    utente_id            INTEGER NOT NULL REFERENCES utenti(id),
    replica_id           INTEGER NOT NULL REFERENCES repliche(id),
    settore_id           INTEGER NOT NULL REFERENCES settori(id),
    tariffa_id           INTEGER NOT NULL REFERENCES tariffe(id),
    num_posti            INTEGER NOT NULL CHECK (num_posti BETWEEN 1 AND 6),
    prezzo_unitario_cent INTEGER NOT NULL CHECK (prezzo_unitario_cent >= 0),
    importo_cent         INTEGER NOT NULL CHECK (importo_cent >= 0),
    stato                TEXT    NOT NULL DEFAULT 'confermata'
                         CHECK (stato IN ('confermata', 'annullata', 'utilizzata')),
    data_prenotazione    TEXT    NOT NULL,
    annullata_il         TEXT,
    check_in_il          TEXT
);
CREATE INDEX idx_prenotazioni_replica ON prenotazioni(replica_id, settore_id, stato);
CREATE INDEX idx_prenotazioni_utente  ON prenotazioni(utente_id);

-- Feedback degli spettatori sugli spettacoli visti

CREATE TABLE feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    utente_id     INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
    spettacolo_id INTEGER NOT NULL REFERENCES spettacoli(id) ON DELETE CASCADE,
    voto          INTEGER NOT NULL CHECK (voto BETWEEN 1 AND 5),
    commento      TEXT,
    data          TEXT    NOT NULL,
    UNIQUE (utente_id, spettacolo_id)
);
CREATE INDEX idx_feedback_spettacolo ON feedback(spettacolo_id);

-- Lista d'attesa in ordine di arrivo

CREATE TABLE lista_attesa (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    utente_id     INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
    replica_id    INTEGER NOT NULL REFERENCES repliche(id) ON DELETE CASCADE,
    num_posti     INTEGER NOT NULL CHECK (num_posti BETWEEN 1 AND 6),
    creata_il     TEXT    NOT NULL,
    notificata_il TEXT,
    UNIQUE (utente_id, replica_id)
);
CREATE INDEX idx_attesa_replica ON lista_attesa(replica_id, creata_il);

-- Messaggi inviati agli utenti
-- La tabella fa da "posta in uscita" simulata

CREATE TABLE notifiche (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    utente_id    INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
    destinatario TEXT    NOT NULL,
    oggetto      TEXT    NOT NULL,
    corpo        TEXT    NOT NULL,
    creata_il    TEXT    NOT NULL
);
CREATE INDEX idx_notifiche_utente ON notifiche(utente_id, creata_il);

-- Registro di audit
-- Non contiene password o token

CREATE TABLE registro_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    quando      TEXT    NOT NULL,
    utente_id   INTEGER,                 
    ruolo       TEXT,
    email       TEXT,                    
    ip          TEXT,
    azione      TEXT    NOT NULL,        -- esempio 'accesso.fallito', 'account.ruolo_modificato'
    esito       TEXT    NOT NULL DEFAULT 'ok' CHECK (esito IN ('ok', 'fallito', 'negato')),
    oggetto     TEXT,                    -- esempio 'replica:14', 'utente:7'
    dettagli    TEXT                     
);
CREATE INDEX idx_audit_quando ON registro_audit(quando);
CREATE INDEX idx_audit_azione ON registro_audit(azione, quando);
CREATE INDEX idx_audit_utente ON registro_audit(utente_id, quando);
CREATE INDEX idx_audit_ip     ON registro_audit(ip, azione, quando);

-- Il registro è a sola aggiunta
-- Le voci non si possono modificare e si possonocancellare solo quando hanno superato il periodo di conservazione  di 365 gg

CREATE TRIGGER audit_non_modificabile BEFORE UPDATE ON registro_audit
BEGIN
    SELECT RAISE(ABORT, 'Il registro di audit non può essere modificato');
END;
CREATE TRIGGER audit_conservazione BEFORE DELETE ON registro_audit
WHEN julianday(OLD.quando) > julianday('now', 'localtime', '-365 days')
BEGIN
    SELECT RAISE(ABORT, 'Le voci del registro di audit si conservano per 365 giorni');
END;

-- Avvisi di sicurezza generati automaticamente dalle regole di rilevamento

CREATE TABLE avvisi (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    quando      TEXT    NOT NULL,
    regola      TEXT    NOT NULL,        -- ad esempio 'forza_bruta' o 'nuovo_amministratore'
    gravita     TEXT    NOT NULL CHECK (gravita IN ('media', 'alta')),
    soggetto    TEXT    NOT NULL,        -- account, IP o utente coinvolto
    descrizione TEXT    NOT NULL,
    chiave      TEXT    NOT NULL UNIQUE, -- evita avvisi duplicati
    gestito_il  TEXT,
    gestito_da  INTEGER REFERENCES utenti(id),
    note        TEXT
);
CREATE INDEX idx_avvisi_aperti ON avvisi(gestito_il, quando);

-- Vista: posti occupati e prezzo effettivo per replica e settore

CREATE VIEW v_occupazione AS
SELECT r.id                                    AS replica_id,
       s.id                                    AS settore_id,
       s.nome                                  AS settore,
       s.posti_totali                          AS posti_totali,
       COALESCE(pr.prezzo_cent, s.prezzo_cent) AS prezzo_cent,
       COALESCE((SELECT SUM(p.num_posti) FROM prenotazioni p
                  WHERE p.replica_id = r.id AND p.settore_id = s.id
                    AND p.stato <> 'annullata'), 0) AS posti_occupati
FROM repliche r
JOIN settori s             ON s.sala_id = r.sala_id
LEFT JOIN prezzi_replica pr ON pr.replica_id = r.id AND pr.settore_id = s.id;
