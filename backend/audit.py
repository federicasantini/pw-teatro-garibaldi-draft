####################################################################################################################
#                                       Registro di audit e log di sicurezza                                       #
####################################################################################################################

# Ogni azione rilevante per la sicurezza viene:
# 1) salvata nella tabella `registro_audit` (consultabile dagli admin, a sola aggiunta);
# 2) scritta come riga JSON nel file di log di sicurezza (data/log/sicurezza.log), pronto per essere letto da 
#    eventuali strumenti di monitoraggio;
# 3) passata alle regole di rilevamento (modulo rilevamento.py) che possono generare un alert

# Principio di minimizzazione: 
# a) si registrano gli eventi di sicurezza e le azioni dello staff, non le attività degli spettatori;
# b) non si registrano mai password o token.

####################################################################################################################

import json
import logging
import sqlite3
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import g, has_request_context, request

from . import tempo
from .db import get_db

log_sicurezza = logging.getLogger("teatro.sicurezza")
CAMPI_VIETATI = {"password", "token", "password_hash", "token_hash"}


class FormatoJson(logging.Formatter):
    # una riga JSON per evento

    def format(self, record):
        voce = {"livello": record.levelname, **getattr(record, "evento", {"messaggio": record.getMessage()})}
        return json.dumps(voce, ensure_ascii=False)


def configura_log(cartella: str) -> None:
    # File di log di sicurezza

    Path(cartella).mkdir(parents=True, exist_ok=True)
    for h in list(log_sicurezza.handlers):  # una sola destinazione per volta
        log_sicurezza.removeHandler(h)
        h.close()
    gestore = RotatingFileHandler(Path(cartella) / "sicurezza.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    gestore.setFormatter(FormatoJson())
    log_sicurezza.addHandler(gestore)
    log_sicurezza.setLevel(logging.INFO)
    log_sicurezza.propagate = False


def scrivi(conn: sqlite3.Connection, azione: str, *, esito: str = "ok", utente: dict | None = None,
           email: str | None = None, ip: str | None = None, oggetto: str | None = None,
           dettagli: dict | None = None) -> dict:

    # Salva l'evento nel registro
    dettagli = {k: v for k, v in (dettagli or {}).items() if k not in CAMPI_VIETATI}
    evento = {
        "quando": tempo.istante(),
        "utente_id": utente["id"] if utente else None,
        "ruolo": utente["ruolo"] if utente else None,
        "email": email or (utente["email"] if utente else None),
        "ip": ip,
        "azione": azione,
        "esito": esito,
        "oggetto": oggetto,
        "dettagli": json.dumps(dettagli, ensure_ascii=False) if dettagli else None,
    }
    conn.execute(
        """INSERT INTO registro_audit (quando, utente_id, ruolo, email, ip, azione, esito, oggetto, dettagli)
           VALUES (:quando, :utente_id, :ruolo, :email, :ip, :azione, :esito, :oggetto, :dettagli)""",
        evento,
    )
    livello = logging.INFO if esito == "ok" else logging.WARNING
    log_sicurezza.log(livello, azione, extra={"evento": {**evento, "dettagli": dettagli or None}})
    return evento


def registra(azione: str, *, esito: str = "ok", email: str | None = None, oggetto: str | None = None,
             dettagli: dict | None = None, utente: dict | None = None) -> None:

    # Registra un evento durante una richiesta
    from .rilevamento import controlla

    if utente is None and has_request_context():
        utente = g.get("utente")
    ip = (request.remote_addr or "sconosciuto") if has_request_context() else None
    evento = scrivi(get_db(), azione, esito=esito, utente=utente, email=email, ip=ip,
                    oggetto=oggetto, dettagli=dettagli)
    controlla(evento)
