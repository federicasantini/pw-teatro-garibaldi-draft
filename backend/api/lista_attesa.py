####################################################################################################################
#                                           API della lista d'attesa                                             #
####################################################################################################################

# Avvisa gli spettatori quando si liberano posti su una replica esaurita.

from flask import Blueprint, jsonify

from .. import tempo
from ..auth import login_richiesto, utente_corrente
from ..db import execute, modifica, query_all, query_one
from ..errors import ApiError
from ..notifiche import data_leggibile, invia
from ..validation import corpo_json, intero

bp = Blueprint("lista_attesa", __name__)


def posti_liberi(replica_id: int) -> int:
    r = query_one("""SELECT COALESCE(SUM(posti_totali - posti_occupati), 0) AS liberi
                     FROM v_occupazione WHERE replica_id = ?""", (replica_id,))
    return r["liberi"]


def notifica_posti_liberati(replica_id: int) -> int:
    # Dopo un annullamento vengono avvisati in ordine di iscrizione gli utenti in lista d'attesa la cui richiesta rientra nei posti tornati disponibili 
    # Non si prenota al posto dell'utente
    
    replica = query_one(
        """SELECT r.data_ora, r.stato, s.titolo FROM repliche r JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE r.id = ?""", (replica_id,))
    if not replica or replica["stato"] != "programmata" or replica["data_ora"] <= tempo.minuti():
        return 0
    liberi = posti_liberi(replica_id)
    avvisati = 0
    for voce in query_all(
        """SELECT id, utente_id, num_posti FROM lista_attesa
           WHERE replica_id = ? AND notificata_il IS NULL ORDER BY creata_il, id""", (replica_id,)
    ):
        if voce["num_posti"] > liberi:
            continue
        liberi -= voce["num_posti"]
        modifica("UPDATE lista_attesa SET notificata_il = ? WHERE id = ?", (tempo.istante(), voce["id"]))
        invia(voce["utente_id"], f"Si sono liberati posti per {replica['titolo']}",
              f"Buone notizie! Per «{replica['titolo']}» del {data_leggibile(replica['data_ora'])} "
              f"si sono liberati dei posti. Prenota il prima possibile: "
              f"i posti vengono assegnati a chi conferma per primo.")
        avvisati += 1
    return avvisati


@bp.post("/repliche/<int:rid>/lista-attesa")
@login_richiesto()
def iscriviti(rid):
    dati = corpo_json()
    num_posti = intero(dati.get("num_posti", 1), "num_posti", 1, 6)
    utente = utente_corrente()
    replica = query_one("SELECT * FROM repliche WHERE id = ?", (rid,))
    if not replica:
        raise ApiError(404, "Replica non trovata")
    if replica["stato"] != "programmata" or replica["data_ora"] <= tempo.minuti():
        raise ApiError(409, "La replica non è prenotabile")
    if posti_liberi(rid) >= num_posti:
        raise ApiError(409, "Ci sono ancora posti disponibili: puoi prenotare direttamente")
    if query_one("SELECT 1 FROM lista_attesa WHERE utente_id = ? AND replica_id = ?", (utente["id"], rid)):
        raise ApiError(409, "Sei già in lista d'attesa per questa replica!")
    lid = execute("INSERT INTO lista_attesa (utente_id, replica_id, num_posti, creata_il) VALUES (?, ?, ?, ?)",
                  (utente["id"], rid, num_posti, tempo.istante()))
    posizione = query_one("SELECT COUNT(*) AS n FROM lista_attesa WHERE replica_id = ? AND id <= ?", (rid, lid))["n"]
    return jsonify({"id": lid, "replica_id": rid, "num_posti": num_posti, "posizione": posizione}), 201


@bp.delete("/repliche/<int:rid>/lista-attesa")
@login_richiesto()
def esci(rid):
    if not modifica("DELETE FROM lista_attesa WHERE utente_id = ? AND replica_id = ?", (utente_corrente()["id"], rid)):
        raise ApiError(404, "Non sei in lista d'attesa per questa replica")
    return "", 204


@bp.get("/lista-attesa")
@login_richiesto()
def mie_iscrizioni():
    return jsonify(query_all(
        """SELECT la.id, la.replica_id, la.num_posti, la.creata_il, la.notificata_il,
                  r.data_ora, r.stato AS stato_replica, s.id AS spettacolo_id, s.titolo
           FROM lista_attesa la
           JOIN repliche r   ON r.id = la.replica_id
           JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE la.utente_id = ? AND r.data_ora > ?
           ORDER BY r.data_ora""",
        (utente_corrente()["id"], tempo.minuti()),
    ))
