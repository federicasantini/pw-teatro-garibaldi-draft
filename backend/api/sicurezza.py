####################################################################################################################
#                                         API di sicurezza degli admin                                             #
####################################################################################################################

# Permette la consultazione del registro di audit e la gestione degli avvisi

from flask import Blueprint, jsonify, request

from .. import tempo
from ..audit import registra
from ..auth import login_richiesto, utente_corrente
from ..db import modifica, query_all, query_one
from ..errors import ApiError
from ..validation import corpo_json, intero, testo

bp = Blueprint("sicurezza", __name__)

MAX_RIGHE = 500


@bp.get("/audit")
@login_richiesto("admin")
def registro():

    # Voci del registro

    condizioni, params = [], []
    if categoria := request.args.get("categoria"):
        condizioni.append("azione LIKE ?")
        params.append(f"{categoria}.%")
    if esito := request.args.get("esito"):
        if esito not in ("ok", "fallito", "negato"):
            raise ApiError(422, "Esito non valido")
        condizioni.append("esito = ?")
        params.append(esito)
    if email := request.args.get("email"):
        condizioni.append("email LIKE ?")
        params.append(f"%{email}%")
    if da := request.args.get("da"):
        condizioni.append("quando >= ?")
        params.append(da)
    limite = intero(request.args.get("limite", 200), "limite", 1, MAX_RIGHE)
    where = ("WHERE " + " AND ".join(condizioni)) if condizioni else ""
    return jsonify(query_all(f"SELECT * FROM registro_audit {where} ORDER BY id DESC LIMIT ?", (*params, limite)))


@bp.get("/avvisi")
@login_richiesto("admin")
def avvisi():
    
    # Avvisi di sicurezza
    solo_aperti = request.args.get("stato", "aperti") == "aperti"
    return jsonify(query_all(
        f"""SELECT a.*, u.email AS gestito_da_email FROM avvisi a LEFT JOIN utenti u ON u.id = a.gestito_da
            {"WHERE a.gestito_il IS NULL" if solo_aperti else ""}
            ORDER BY a.gestito_il IS NOT NULL, a.quando DESC LIMIT 200"""))


@bp.patch("/avvisi/<int:aid>")
@login_richiesto("admin")
def gestisci_avviso(aid):

    # Segna un avviso come gestito con una nota obbligatoria

    dati = corpo_json()
    note = testo(dati.get("note"), "note", 1000)
    avviso = query_one("SELECT * FROM avvisi WHERE id = ?", (aid,))
    if not avviso:
        raise ApiError(404, "Avviso non trovato")
    if not modifica("UPDATE avvisi SET gestito_il = ?, gestito_da = ?, note = ? WHERE id = ? AND gestito_il IS NULL",
                    (tempo.istante(), utente_corrente()["id"], note, aid)):
        raise ApiError(409, "L'avviso è già stato gestito")
    registra("sistema.avviso_gestito", oggetto=f"avviso:{aid}", dettagli={"regola": avviso["regola"], "note": note})
    return jsonify(query_one("SELECT * FROM avvisi WHERE id = ?", (aid,)))


