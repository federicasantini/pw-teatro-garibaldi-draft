####################################################################################################################
#                                           Manutenzione della piattaforma                                         #
####################################################################################################################

# Attività periodiche della piattaforma, da pianificare (es. ogni ora) con cron su Linux/macOS o con l'Utilità di 
# pianificazione su Windows:

# python -m backend.manutenzione

# invia il promemoria agli spettatori con una prenotazione per il giorno dopo;
# segna come 'conclusa' le repliche terminate;
# cancella sessioni scadute, vecchi tentativi di accesso falliti e le voci del registro di audit oltre il periodo di 
# conservazione (365 giorni)

from datetime import datetime, timedelta

from . import tempo
from .app import create_app
from .db import modifica, query_all, transazione
from .notifiche import data_leggibile, invia

ANTICIPO_PROMEMORIA = timedelta(hours=24)
DURATA_PREDEFINITA_MIN = 120
CONSERVAZIONE_TENTATIVI = timedelta(days=1)
CONSERVAZIONE_AUDIT = timedelta(days=365)  # deve coincidere con il trigger audit_conservazione


def invia_promemoria() -> int:
    ora = tempo.adesso()
    repliche = query_all(
        """SELECT r.id, r.data_ora, s.titolo FROM repliche r JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE r.stato = 'programmata' AND r.promemoria_inviato_il IS NULL AND r.data_ora > ? AND r.data_ora <= ?""",
        (tempo.minuti(ora), tempo.minuti(ora + ANTICIPO_PROMEMORIA)),
    )
    inviati = 0
    for r in repliche:
        with transazione():
            # aggiornamento condizionato: due esecuzioni sovrapposte non duplicano i messaggi
            if not modifica("UPDATE repliche SET promemoria_inviato_il = ? WHERE id = ? AND promemoria_inviato_il IS NULL",
                            (tempo.istante(ora), r["id"])):
                continue
            for p in query_all(
                """SELECT p.utente_id, p.codice, p.num_posti, se.nome AS settore
                   FROM prenotazioni p JOIN settori se ON se.id = p.settore_id
                   WHERE p.replica_id = ? AND p.stato = 'confermata'""", (r["id"],)):
                invia(p["utente_id"], f"Promemoria: {r['titolo']}",
                      f"Ti ricordiamo lo spettacolo «{r['titolo']}» del {data_leggibile(r['data_ora'])}.\n"
                      f"Posti: {p['num_posti']} in {p['settore']} · Codice d'ingresso: {p['codice']}\n"
                      f"Il check-in apre due ore prima dell'inizio.")
                inviati += 1
    return inviati


def concludi_repliche() -> int:
    ora = tempo.adesso()
    concluse = 0
    for r in query_all(
        """SELECT r.id, r.data_ora, s.durata_minuti FROM repliche r JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE r.stato = 'programmata' AND r.data_ora < ?""", (tempo.minuti(ora),)):
        fine = datetime.fromisoformat(r["data_ora"]) + timedelta(minutes=r["durata_minuti"] or DURATA_PREDEFINITA_MIN)
        if fine < ora:
            concluse += modifica("UPDATE repliche SET stato = 'conclusa' WHERE id = ? AND stato = 'programmata'",
                                 (r["id"],))
    return concluse


def pulizia() -> dict:
    ora = tempo.adesso()
    return {
        "sessioni_scadute": modifica("DELETE FROM sessioni WHERE scade_il <= ?", (tempo.istante(ora),)),
        "tentativi_login": modifica("DELETE FROM tentativi_login WHERE quando < ?",
                                    (tempo.istante(ora - CONSERVAZIONE_TENTATIVI),)),
        "audit_scaduto": modifica("DELETE FROM registro_audit WHERE quando < ?",
                                  (tempo.istante(ora - CONSERVAZIONE_AUDIT - timedelta(days=1)),)),
    }


def esegui() -> dict:
    return {"promemoria": invia_promemoria(), "repliche_concluse": concludi_repliche(), **pulizia()}


if __name__ == "__main__":
    with create_app().app_context():
        print(esegui())
