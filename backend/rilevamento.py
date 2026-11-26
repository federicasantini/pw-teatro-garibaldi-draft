####################################################################################################################
#                                         Rilevamento delle anomalie                                              #
####################################################################################################################

# Regole di rilevamento: 
# individuano comportamenti sospetti a partire dal registro di audit e generano un avviso per gli admin

# Ogni regola è una interrogazione di conteggio sugli eventi recenti
# Un alert NON è automaticamente un "incidente significativo" ai sensi della NIS2: è un segnale che una persona 
# deve valutare (vedi docs/nis2.md)

# Tabella esplicativa delle regole di rilevamento e dei criteri di attivazione:
# | Regola                | Evento che la attiva       | Condizione                                   | Gravità |
# |-----------------------|----------------------------|----------------------------------------------|---------|
# | forza_bruta           | accesso.bloccato           | un account viene bloccato per troppi errori  | media   |
# | password_spraying     | accesso.fallito            | stesso IP, ≥ 5 account diversi in 1 ora      | alta    |
# | nuovo_amministratore  | account.ruolo_modificato   | un utente diventa amministratore             | alta    |
# | accessi_negati        | accesso.negato             | stesso utente, ≥ 10 rifiuti in 15 minuti     | media   |
# | esportazioni_ripetute | *esportazione*             | stesso utente, ≥ 5 esportazioni in 1 ora     | media   |
# | check_in_sospetti     | prenotazioni.check_in KO   | stesso operatore, ≥ 10 codici rifiutati      | media   |
# |                       |                            | in 15 minuti (codici inventati o copiati?)   |         |

import json
from datetime import timedelta

from flask import current_app

from . import tempo
from .db import execute, query_all, query_one
from .notifiche import invia

SOGLIA_SPRAYING = 5
SOGLIA_ACCESSI_NEGATI = 10
SOGLIA_ESPORTAZIONI = 5
SOGLIA_CHECK_IN_RIFIUTATI = 10
AZIONI_ESPORTAZIONE = ("account.dati_esportati", "dati.export_csv")


def _da(minuti: int) -> str:
    return tempo.istante(tempo.adesso() - timedelta(minutes=minuti))


def _conta(sql: str, params) -> int:
    return query_one(sql, params)["n"]


def crea_avviso(regola: str, gravita: str, soggetto: str, descrizione: str) -> bool:
   
    # Crea l'avviso e avvisa gli amministratori
    # Restituisce false se esisteva già

    ora = tempo.adesso()
    chiave = f"{regola}|{soggetto}|{ora.strftime('%Y-%m-%dT%H')}"
    if query_one("SELECT 1 FROM avvisi WHERE chiave = ?", (chiave,)):
        return False
    execute("""INSERT INTO avvisi (quando, regola, gravita, soggetto, descrizione, chiave)
               VALUES (?, ?, ?, ?, ?, ?)""", (tempo.istante(ora), regola, gravita, soggetto, descrizione, chiave))
    current_app.logger.warning("AVVISO %s (%s): %s", regola, gravita, descrizione)
    for admin in query_all("SELECT id FROM utenti WHERE ruolo = 'admin' AND eliminato_il IS NULL"):
        invia(admin["id"], f"Avviso di sicurezza ({gravita}): {regola.replace('_', ' ')}",
              f"{descrizione}\n\nVerifica il registro nell'area gestione, scheda \"Sicurezza\", "
              f"e segna l'avviso come gestito dopo averlo valutato")
    return True


def controlla(evento: dict) -> None:

    # Applica le regole pertinenti all'evento appena registrato
    
    azione, esito = evento["azione"], evento["esito"]

    if azione == "accesso.bloccato":
        crea_avviso("forza_bruta", "media", evento["email"],
                     f"L'account {evento['email']} è stato bloccato temporaneamente per troppi tentativi "
                     f"di accesso falliti (ultimo tentativo dall'IP {evento['ip']})")

    elif azione == "accesso.fallito" and evento["ip"]:
        account = _conta("""SELECT COUNT(DISTINCT email) AS n FROM registro_audit
                            WHERE azione = 'accesso.fallito' AND ip = ? AND quando > ?""", (evento["ip"], _da(60)))
        if account >= SOGLIA_SPRAYING:
            crea_avviso("password_spraying", "alta", evento["ip"],
                         f"Dall'IP {evento['ip']} sono falliti accessi su {account} account diversi nell'ultima ora: "
                         f"possibile tentativo di indovinare password comuni su molti account")

    elif azione == "account.ruolo_modificato" and json.loads(evento["dettagli"] or "{}").get("nuovo") == "admin":
        destinatario = json.loads(evento["dettagli"]).get("utente", evento["oggetto"])
        crea_avviso("nuovo_amministratore", "alta", destinatario,
                     f"L'utente {evento['email']} ha assegnato il ruolo di amministratore a {destinatario}. "
                     f"Verifica che la modifica sia stata autorizzata")

    elif azione == "accesso.negato" and evento["utente_id"]:
        rifiuti = _conta("""SELECT COUNT(*) AS n FROM registro_audit
                            WHERE azione = 'accesso.negato' AND utente_id = ? AND quando > ?""",
                         (evento["utente_id"], _da(15)))
        if rifiuti >= SOGLIA_ACCESSI_NEGATI:
            crea_avviso("accessi_negati", "media", evento["email"],
                         f"L'utente {evento['email']} ha tentato {rifiuti} volte in 15 minuti di usare funzioni "
                         f"non consentite al suo ruolo")

    elif azione in AZIONI_ESPORTAZIONE and evento["utente_id"]:
        esportazioni = _conta(f"""SELECT COUNT(*) AS n FROM registro_audit
                                  WHERE azione IN ({",".join("?" * len(AZIONI_ESPORTAZIONE))})
                                    AND utente_id = ? AND quando > ?""",
                              (*AZIONI_ESPORTAZIONE, evento["utente_id"], _da(60)))
        if esportazioni >= SOGLIA_ESPORTAZIONI:
            crea_avviso("esportazioni_ripetute", "media", evento["email"],
                         f"L'utente {evento['email']} ha esportato dati {esportazioni} volte nell'ultima ora")

    elif azione == "prenotazioni.check_in" and esito != "ok" and evento["utente_id"]:
        rifiutati = _conta("""SELECT COUNT(*) AS n FROM registro_audit
                              WHERE azione = 'prenotazioni.check_in' AND esito <> 'ok'
                                AND utente_id = ? AND quando > ?""", (evento["utente_id"], _da(15)))
        if rifiutati >= SOGLIA_CHECK_IN_RIFIUTATI:
            crea_avviso("check_in_sospetti", "media", evento["email"],
                         f"Al varco dell'operatore {evento['email']} sono stati rifiutati {rifiutati} codici in "
                         f"15 minuti: possibili biglietti falsi o duplicati!")
