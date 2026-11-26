# Fix e funzioni di supporto condivise dai test

# Ogni test lavora su un database temporaneo popolato dallo script di seed
# i test sono indipendenti tra loro e ripetibili

import itertools
import sqlite3
from datetime import datetime

import pytest

from backend import tempo
from backend.app import create_app
from backend.seed import seed

STAFF = {
    "spettatore": ("anna.rinaldi@example.com", "Spettatore2026!"),
    "operatore": ("biglietteria@teatrogaribaldi.it", "Operatore2026!"),
    "admin": ("admin@teatrogaribaldi.it", "Admin2026!"),
}
_contatore = itertools.count(1)


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    seed(str(db_path))
    return create_app({"DATABASE": str(db_path), "LOG_DIR": str(tmp_path / "log"), "TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    # Connessione diretta al database del test 

    conn = sqlite3.connect(app.config["DATABASE"], isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


def accedi_come(client, ruolo):
    return login(client, *STAFF[ruolo])


def nuovo_utente(client, nome="Test"):
    # Registra un nuovo spettatore e restituisce l'intestazione di autenticazione 

    n = next(_contatore)
    r = client.post("/api/auth/registrazione", json={
        "nome": nome, "cognome": f"Utente{n}", "email": f"utente{n}@example.com",
        "password": "Sicura123", "consenso_privacy": True})
    assert r.status_code == 201, r.get_json()
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


@pytest.fixture
def spettatore(client):
    return accedi_come(client, "spettatore")


@pytest.fixture
def operatore(client):
    return accedi_come(client, "operatore")


@pytest.fixture
def admin(client):
    return accedi_come(client, "admin")


@pytest.fixture
def orologio(monkeypatch):
    # Permette di "spostare" l'ora corrente dell'applicazione
    def imposta(dt: datetime):
        monkeypatch.setattr(tempo, "adesso", lambda: dt)
    return imposta


def prima_replica_futura(client):
    repliche = client.get("/api/repliche").get_json()
    adesso = tempo.minuti()
    return next(r for r in repliche if r["stato"] == "programmata" and r["data_ora"] > adesso)


def disponibilita_settore(client, replica_id, nome_settore):
    disp = client.get(f"/api/repliche/{replica_id}/disponibilita").get_json()
    return next(s for s in disp["settori"] if s["settore"] == nome_settore)
