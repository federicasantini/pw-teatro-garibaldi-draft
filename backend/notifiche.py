####################################################################################################################
#                              Invio simulato delle comunicazioni agli utenti                                      #
####################################################################################################################

# Nel prototipo i messaggi sono salvati nella tabella `notifiche`, che fa da posta in uscita ed è consultabile 
# dall'utente nella propria area personale

# Per passare all'invio reale basta sostituire il corpo di `invia` con una spedizione SMTP o con le API di un 
# servizio di posta transazionale


from flask import current_app

from . import tempo
from .db import execute, query_one

FIRMA = "\n\nTeatro Garibaldi · Biglietteria: mar–sab 10–13 / 16–19"


def invia(utente_id: int, oggetto: str, corpo: str) -> None:
    utente = query_one("SELECT email FROM utenti WHERE id = ? AND eliminato_il IS NULL", (utente_id,))
    if not utente:
        return
    execute(
        "INSERT INTO notifiche (utente_id, destinatario, oggetto, corpo, creata_il) VALUES (?, ?, ?, ?, ?)",
        (utente_id, utente["email"], oggetto, corpo + FIRMA, tempo.istante()),
    )
    current_app.logger.info("Notifica a %s: %s", utente["email"], oggetto)


def data_leggibile(data_ora: str) -> str:
    giorno, ora = data_ora.split("T")
    a, m, g = giorno.split("-")
    return f"{g}/{m}/{a} alle {ora[:5]}"
