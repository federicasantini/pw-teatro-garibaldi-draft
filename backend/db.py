####################################################################################################################
#                    Livello di accesso ai dati: connessione SQLite e funzioni di utilità                          #
####################################################################################################################

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
ATTESA_LOCK_SECONDI = 10  # attesa massima del lock di scrittura in caso di richieste concorrenti


def connetti(percorso: str) -> sqlite3.Connection:
    conn = sqlite3.connect(percorso, isolation_level=None, timeout=ATTESA_LOCK_SECONDI)
    conn.row_factory = sqlite3.Row            # righe accessibili per nome di colonna
    conn.execute("PRAGMA foreign_keys = ON")  # integrità referenziale attiva
    return conn


def get_db() -> sqlite3.Connection:
    # Restituisce la connessione associata alla richiesta HTTP corrente
    # Una connessione per richiesta, aperta al primo utilizzo e chiusa al termine della richiesta
    
    if "db" not in g:
        g.db = connetti(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    # Crea (o ricrea cancellando i dati) tutte le tabelle a partire da schema.sql

    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def query_all(sql: str, params=()) -> list[dict]:
    return [dict(r) for r in get_db().execute(sql, params).fetchall()]


def query_one(sql: str, params=()) -> dict | None:
    row = get_db().execute(sql, params).fetchone()
    return dict(row) if row else None


def execute(sql: str, params=()) -> int:
    # Esegue un comando di scrittura e restituisce l'id dell'ultima riga inserita
    return get_db().execute(sql, params).lastrowid


def modifica(sql: str, params=()) -> int:
    # Esegue UPDATE/DELETE e restituisce il numero di righe coinvolte
    # Serve per gli aggiornamenti condizionati: se due richieste concorrenti tentano la stessa transizione,
    # solo una modifica la riga e l'altra ottiene 0
    
    return get_db().execute(sql, params).rowcount


@contextmanager
def transazione():
    # Transazione con lock di scrittura immediato (BEGIN IMMEDIATE)
    # Viene impedito l'overbooking
    
    conn = get_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def lista_json(valori) -> str:
    # Parametro per `IN (SELECT value FROM json_each(?))`: una sola query per N id
    return json.dumps(list(valori))


def euro(centesimi) -> float:
    # Gli importi sono memorizzati in centesimi (int) e le API li espongono in euro
    return round((centesimi or 0) / 100, 2)
