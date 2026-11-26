####################################################################################################################
#                                     Autenticazione e controllo degli accessi                                        #
####################################################################################################################

#L' Autenticazione è basata su:
# a) token;
# b) protezione dagli attacchi a forza bruta;
# c) controllo degli accessi per ruolo

import hashlib
import secrets
from datetime import timedelta
from functools import wraps

from flask import g, request

from . import tempo
from .audit import registra
from .db import execute, modifica, query_one
from .errors import ApiError

DURATA_SESSIONE = timedelta(hours=8)

# Limitazione dei tentativi di accesso falliti
FINESTRA_TENTATIVI = timedelta(minutes=15)
MAX_TENTATIVI_PER_EMAIL = 5
MAX_TENTATIVI_PER_IP = 20

# Gerarchia dei ruoli: un ruolo eredita i permessi di quelli di livello inferiore
LIVELLO_RUOLO = {"spettatore": 1, "operatore": 2, "admin": 3}


def hash_token(token: str) -> str:
    # Nel database viene conservata solo l'impronta SHA-256 del token

    return hashlib.sha256(token.encode()).hexdigest()


def crea_sessione(utente_id: int) -> str:
    # Genera un token casuale e registra l'hash

    token = secrets.token_urlsafe(32)
    ora = tempo.adesso()

    # pulizia delle sessioni scadute
    modifica("DELETE FROM sessioni WHERE scade_il <= ?", (tempo.istante(ora),))
    execute(
        "INSERT INTO sessioni (token_hash, utente_id, creata_il, scade_il) VALUES (?, ?, ?, ?)",
        (hash_token(token), utente_id, tempo.istante(ora), tempo.istante(ora + DURATA_SESSIONE)),
    )
    return token


def elimina_sessione(token: str) -> None:
    modifica("DELETE FROM sessioni WHERE token_hash = ?", (hash_token(token),))


def _token_dalla_richiesta() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip() or None
    return None


def utente_corrente() -> dict | None:
    # Restituisce l'utente associato al token
    if "utente" in g:
        return g.utente
    token = _token_dalla_richiesta()
    utente = None
    if token:
        utente = query_one(
            """SELECT u.id, u.nome, u.cognome, u.email, u.ruolo
               FROM sessioni s JOIN utenti u ON u.id = s.utente_id
               WHERE s.token_hash = ? AND s.scade_il > ? AND u.eliminato_il IS NULL""",
            (hash_token(token), tempo.istante()),
        )
    g.utente = utente
    g.token = token
    return utente


def is_staff(utente: dict) -> bool:
    return LIVELLO_RUOLO[utente["ruolo"]] >= LIVELLO_RUOLO["operatore"]


def login_richiesto(ruolo_minimo: str = "spettatore"):
    # Consente l'accesso solo agli utenti autenticati con ruolo adeguato

    def dec(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            utente = utente_corrente()
            if utente is None:
                raise ApiError(401, "Autenticazione richiesta")
            if LIVELLO_RUOLO[utente["ruolo"]] < LIVELLO_RUOLO[ruolo_minimo]:
                registra("accesso.negato", esito="negato", oggetto=f"{request.method} {request.path}")
                raise ApiError(403, "Permessi insufficienti per questa operazione")
            return view(*args, **kwargs)

        return wrapper

    return dec


def ip_client() -> str:

    # Configurare werkzeug.middleware.proxy_fix.ProxyFix dietro al reverse proxy
    # cosicché remote_addr contenga l'indirizzo reale del client
    return request.remote_addr or "sconosciuto"


def verifica_tentativi(email: str) -> None:

    # Blocca temporaneamente l'accesso dopo troppi tentativi falliti (per account e per indirizzo IP)
    
    da = tempo.istante(tempo.adesso() - FINESTRA_TENTATIVI)
    per_email = query_one("SELECT COUNT(*) AS n FROM tentativi_login WHERE email = ? AND quando > ?",
                          (email, da))["n"]
    per_ip = query_one("SELECT COUNT(*) AS n FROM tentativi_login WHERE ip = ? AND quando > ?",
                       (ip_client(), da))["n"]
    if per_email >= MAX_TENTATIVI_PER_EMAIL or per_ip >= MAX_TENTATIVI_PER_IP:
        registra("accesso.bloccato", esito="negato", email=email,
                 dettagli={"tentativi_account": per_email, "tentativi_ip": per_ip})
        minuti = int(FINESTRA_TENTATIVI.total_seconds() // 60)
        raise ApiError(429, f"Troppi tentativi di accesso. Riprova tra {minuti} minuti.",
                       headers={"Retry-After": str(int(FINESTRA_TENTATIVI.total_seconds()))})


def registra_tentativo_fallito(email: str) -> None:
    execute("INSERT INTO tentativi_login (email, ip, quando) VALUES (?, ?, ?)",
            (email, ip_client(), tempo.istante()))


def azzera_tentativi(email: str) -> None:
    modifica("DELETE FROM tentativi_login WHERE email = ?", (email,))
