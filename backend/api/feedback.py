####################################################################################################################
#                                         API dei feedback degli spettatori                                       #
####################################################################################################################

# Gestisce recensioni e commenti sugli spettacoli visti.

from flask import Blueprint, jsonify

from .. import tempo
from ..auth import login_richiesto, utente_corrente
from ..db import execute, query_all, query_one
from ..errors import ApiError
from ..validation import corpo_json, intero, richiesti, testo

bp = Blueprint("feedback", __name__)


@bp.get("/spettacoli/<int:sid>/feedback")
def feedback_spettacolo(sid):
    return jsonify(query_all(
        """SELECT f.id, f.voto, f.commento, f.data,
                  CASE WHEN u.eliminato_il IS NOT NULL THEN 'Utente eliminato'
                       ELSE u.nome || ' ' || substr(u.cognome, 1, 1) || '.' END AS autore
           FROM feedback f JOIN utenti u ON u.id = f.utente_id
           WHERE f.spettacolo_id = ? ORDER BY f.data DESC""",
        (sid,),
    ))


@bp.post("/feedback")
@login_richiesto()
def lascia_feedback():
    """Un feedback è ammesso solo se l'utente ha assistito allo spettacolo
    (prenotazione utilizzata o replica conclusa) e una sola volta per spettacolo"""
    dati = corpo_json()
    richiesti(dati, "spettacolo_id", "voto")
    sid = intero(dati["spettacolo_id"], "spettacolo_id", 1)
    voto = intero(dati["voto"], "voto", 1, 5)
    commento = testo(dati.get("commento"), "commento", 1000, obbligatorio=False)
    utente = utente_corrente()

    visto = query_one(
        """SELECT 1 FROM prenotazioni p JOIN repliche r ON r.id = p.replica_id
           WHERE p.utente_id = ? AND r.spettacolo_id = ?
             AND (p.stato = 'utilizzata' OR (p.stato = 'confermata' AND r.stato = 'conclusa'))""",
        (utente["id"], sid),
    )
    if not visto:
        raise ApiError(403, "Puoi recensire solo gli spettacoli a cui hai assistito!")
    if query_one("SELECT 1 FROM feedback WHERE utente_id = ? AND spettacolo_id = ?", (utente["id"], sid)):
        raise ApiError(409, "Hai già lasciato un feedback per questo spettacolo!")

    fid = execute(
        "INSERT INTO feedback (utente_id, spettacolo_id, voto, commento, data) VALUES (?, ?, ?, ?, ?)",
        (utente["id"], sid, voto, commento, tempo.istante()),
    )
    return jsonify(query_one("SELECT * FROM feedback WHERE id = ?", (fid,))), 201
