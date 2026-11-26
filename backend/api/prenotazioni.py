####################################################################################################################
#                           API di prenotazione, QR code e check-in                                               #
####################################################################################################################

# Gestisce creazione, consultazione, annullamento e convalida delle prenotazioni.

import io
import secrets
from datetime import datetime, timedelta

import segno
from flask import Blueprint, Response, jsonify, request

from .. import tempo
from ..audit import registra
from ..auth import is_staff, login_richiesto, utente_corrente
from ..db import execute, modifica, query_all, query_one, transazione
from ..errors import ApiError
from ..notifiche import data_leggibile, invia
from ..validation import corpo_json, intero, richiesti, testo
from .lista_attesa import notifica_posti_liberati

bp = Blueprint("prenotazioni", __name__)

MAX_POSTI_PER_PRENOTAZIONE = 6
MAX_POSTI_PER_UTENTE_REPLICA = 6     # tetto complessivo per utente e replica (per bloccare il possibile bagarinaggio)
ORE_LIMITE_ANNULLAMENTO = 24
CHECK_IN_APERTURA = timedelta(hours=2)  # il check-in apre 2 ore prima dell'inizio
DURATA_PREDEFINITA_MIN = 120            # e chiude a fine spettacolo (durata o 2 ore se ignota)
STATI = ("confermata", "annullata", "utilizzata")
ALFABETO_CODICE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # senza caratteri ambigui (O/0, I/1)

SELECT_PRENOTAZIONE = """
    SELECT p.id, p.codice, p.utente_id, p.replica_id, p.settore_id, p.tariffa_id, p.num_posti,
           p.prezzo_unitario_cent / 100.0 AS prezzo_unitario,
           p.importo_cent / 100.0 AS importo_totale,
           p.stato, p.data_prenotazione, p.annullata_il, p.check_in_il,
           r.data_ora, r.stato AS stato_replica, r.spettacolo_id, s.titolo, s.durata_minuti,
           se.nome AS settore, t.nome AS tariffa, t.richiede_documento,
           u.nome || ' ' || u.cognome AS intestatario, u.email
    FROM prenotazioni p
    JOIN repliche r   ON r.id = p.replica_id
    JOIN spettacoli s ON s.id = r.spettacolo_id
    JOIN settori se   ON se.id = p.settore_id
    JOIN tariffe t    ON t.id = p.tariffa_id
    JOIN utenti u     ON u.id = p.utente_id
"""


def _nuovo_codice() -> str:
    return "TG-" + "".join(secrets.choice(ALFABETO_CODICE) for _ in range(6))


def prezzo_scontato(prezzo_cent: int, sconto_pct: int) -> int:
    # Prezzo unitario in centesimi dopo lo sconto
    return (prezzo_cent * (100 - sconto_pct) + 50) // 100


def leggi_prenotazione(pid: int) -> dict | None:
    return query_one(SELECT_PRENOTAZIONE + " WHERE p.id = ?", (pid,))


@bp.get("/tariffe")
def tariffe():
    return jsonify(query_all(
        """SELECT id, codice, nome, descrizione, sconto_pct, richiede_documento
           FROM tariffe WHERE attiva = 1 ORDER BY sconto_pct, id"""))


@bp.post("/prenotazioni")
@login_richiesto()
def crea_prenotazione():
    dati = corpo_json()
    richiesti(dati, "replica_id", "settore_id", "num_posti")
    replica_id = intero(dati["replica_id"], "replica_id", 1)
    settore_id = intero(dati["settore_id"], "settore_id", 1)
    num_posti = intero(dati["num_posti"], "num_posti", 1, MAX_POSTI_PER_PRENOTAZIONE)
    utente = utente_corrente()

    if dati.get("tariffa_id") in (None, ""):
        tariffa = query_one("SELECT * FROM tariffe WHERE codice = 'INTERO'")
    else:
        tariffa = query_one("SELECT * FROM tariffe WHERE id = ? AND attiva = 1",
                            (intero(dati["tariffa_id"], "tariffa_id", 1),))
        if not tariffa:
            raise ApiError(422, "Tariffa non valida")

    # La transazione con lock immediato rende atomiche la verifica della disponibilità
    # e l'inserimento: due richieste concorrenti non possono vendere gli stessi posti

    with transazione():
        replica = query_one("SELECT * FROM repliche WHERE id = ?", (replica_id,))
        if not replica:
            raise ApiError(404, "Replica non trovata")
        if replica["stato"] != "programmata":
            raise ApiError(409, "La replica non è prenotabile")
        if replica["data_ora"] <= tempo.minuti():
            raise ApiError(409, "La replica è già iniziata o conclusa")

        occ = query_one("SELECT * FROM v_occupazione WHERE replica_id = ? AND settore_id = ?",
                        (replica_id, settore_id))
        if not occ:
            raise ApiError(422, "Il settore indicato non appartiene alla sala della replica")

        gia_prenotati = query_one(
            """SELECT COALESCE(SUM(num_posti), 0) AS n FROM prenotazioni
               WHERE utente_id = ? AND replica_id = ? AND stato <> 'annullata'""",
            (utente["id"], replica_id))["n"]
        residui = MAX_POSTI_PER_UTENTE_REPLICA - gia_prenotati
        if num_posti > residui:
            raise ApiError(409, f"Puoi prenotare al massimo {MAX_POSTI_PER_UTENTE_REPLICA} posti "
                                f"(te ne restano {max(residui, 0)})",
                           {"posti_ancora_prenotabili": max(residui, 0)})

        liberi = occ["posti_totali"] - occ["posti_occupati"]
        if num_posti > liberi:
            raise ApiError(409, f"Posti insufficienti nel settore {occ['settore']}",
                           {"posti_disponibili": liberi})

        codice = _nuovo_codice()
        while query_one("SELECT 1 FROM prenotazioni WHERE codice = ?", (codice,)):
            codice = _nuovo_codice()

        unitario = prezzo_scontato(occ["prezzo_cent"], tariffa["sconto_pct"])
        pid = execute(
            """INSERT INTO prenotazioni (codice, utente_id, replica_id, settore_id, tariffa_id, num_posti,
                                         prezzo_unitario_cent, importo_cent, data_prenotazione)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (codice, utente["id"], replica_id, settore_id, tariffa["id"], num_posti,
             unitario, unitario * num_posti, tempo.istante()),
        )
        # chi prenota esce dalla lista d'attesa di quella replica
        modifica("DELETE FROM lista_attesa WHERE utente_id = ? AND replica_id = ?", (utente["id"], replica_id))

    pren = leggi_prenotazione(pid)
    nota_doc = (f"\nTariffa {pren['tariffa']}: all'ingresso porta un documento per aver diritto alla riduzione"
                if pren["richiede_documento"] else "")
    invia(utente["id"], f"Prenotazione confermata: {pren['titolo']}",
          f"Ciao {utente['nome']},\nla tua prenotazione è confermata!\n\n"
          f"Spettacolo: {pren['titolo']}\nData: {data_leggibile(pren['data_ora'])}\n"
          f"Posti: {num_posti} in {pren['settore']} ({pren['tariffa']})\n"
          f"Importo: € {pren['importo_totale']:.2f} (da pagare in biglietteria)\n"
          f"Codice d'ingresso: {pren['codice']}{nota_doc}\n\n"
          f"Il QR code del biglietto è nella tua area personale.")
    return jsonify(pren), 201


@bp.get("/prenotazioni")
@login_richiesto()
def elenco_prenotazioni():
    # Lo spettatore vede le proprie prenotazioni, operatore e admin le vedono tutte

    utente = utente_corrente()
    condizioni, params = [], []
    if not is_staff(utente) or request.args.get("mie") == "1":
        condizioni.append("p.utente_id = ?")
        params.append(utente["id"])
    if rid := request.args.get("replica_id"):
        condizioni.append("p.replica_id = ?")
        params.append(intero(rid, "replica_id"))
    if stato := request.args.get("stato"):
        if stato not in STATI:
            raise ApiError(422, "Stato non valido")
        condizioni.append("p.stato = ?")
        params.append(stato)
    where = ("WHERE " + " AND ".join(condizioni)) if condizioni else ""
    return jsonify(query_all(f"{SELECT_PRENOTAZIONE} {where} ORDER BY r.data_ora DESC, p.id DESC", params))


def annulla(pren: dict, motivo: str | None = None) -> bool:
    # Annulla una prenotazione confermata

    if not modifica("UPDATE prenotazioni SET stato = 'annullata', annullata_il = ? WHERE id = ? AND stato = 'confermata'",
                    (tempo.istante(), pren["id"])):
        return False
    invia(pren["utente_id"], f"Prenotazione annullata: {pren['titolo']}",
          f"La prenotazione {pren['codice']} per «{pren['titolo']}» del {data_leggibile(pren['data_ora'])} "
          f"è stata annullata.{(' ' + motivo) if motivo else ''}")
    notifica_posti_liberati(pren["replica_id"])
    return True


@bp.delete("/prenotazioni/<int:pid>")
@login_richiesto()
def annulla_prenotazione(pid):
    utente = utente_corrente()
    pren = leggi_prenotazione(pid)
    if not pren:
        raise ApiError(404, "Prenotazione non trovata")
    staff = is_staff(utente)
    if pren["utente_id"] != utente["id"] and not staff:
        raise ApiError(403, "Non puoi annullare prenotazioni di altri utenti")
    if pren["stato"] != "confermata":
        raise ApiError(409, "La prenotazione non è annullabile")
    limite = datetime.fromisoformat(pren["data_ora"]) - timedelta(hours=ORE_LIMITE_ANNULLAMENTO)
    if tempo.adesso() > limite and not staff:
        raise ApiError(409, f"L'annullamento è possibile fino a {ORE_LIMITE_ANNULLAMENTO} ore prima dello spettacolo")
    da_staff = pren["utente_id"] != utente["id"]
    if not annulla(pren, "Annullamento effettuato dalla biglietteria" if da_staff else None):
        raise ApiError(409, "La prenotazione non è annullabile")
    if da_staff:
        registra("prenotazioni.annullata_da_staff", oggetto=f"prenotazione:{pid}", dettagli={"codice": pren["codice"]})
    return "", 204


@bp.get("/prenotazioni/<int:pid>/qr")
@login_richiesto()
def qr_code(pid):
    # QR code del codice della prenotazione da mostrare all'ingresso
    utente = utente_corrente()
    pren = query_one("SELECT codice, utente_id FROM prenotazioni WHERE id = ?", (pid,))
    if not pren:
        raise ApiError(404, "Prenotazione non trovata")
    if pren["utente_id"] != utente["id"] and not is_staff(utente):
        raise ApiError(403, "Non puoi visualizzare prenotazioni di altri utenti")
    buf = io.BytesIO()
    segno.make(pren["codice"], error="m").save(buf, kind="svg", scale=6, border=2, dark="#241a17",
                                               xmldecl=False, title=pren["codice"])
    return Response(buf.getvalue(), mimetype="image/svg+xml",
                    headers={"Cache-Control": "private, max-age=86400"})


@bp.post("/prenotazioni/check-in")
@login_richiesto("operatore")
def check_in():
    # Convalida all'ingresso del codice prenotazione (digitato o letto dal QR code)
    dati = corpo_json()
    richiesti(dati, "codice")
    codice = testo(dati["codice"], "codice", 20).upper()

    def rifiuta(status: int, messaggio: str, prenotazione: dict | None = None):
        # ogni ingresso rifiutato finisce nel registro: molti rifiuti ravvicinati
        # possono indicare biglietti falsi o copiati (rif. regola check_in_sospetti)
        registra("prenotazioni.check_in", esito="negato", oggetto=f"codice:{codice}", dettagli={"motivo": messaggio})
        raise ApiError(status, messaggio, {"prenotazione": prenotazione} if prenotazione else None)

    pren = query_one(SELECT_PRENOTAZIONE + " WHERE p.codice = ?", (codice,))
    if not pren:
        rifiuta(404, "Codice prenotazione inesistente")
    if pren["stato"] == "utilizzata":
        rifiuta(409, "Prenotazione già utilizzata", pren)
    if pren["stato"] == "annullata":
        rifiuta(409, "Prenotazione annullata", pren)

    # Il biglietto vale solo per la propria replica: check-in aperto da 2 ore prima dell'inizio
    # fino al termine dello spettacolo

    inizio = datetime.fromisoformat(pren["data_ora"])
    fine = inizio + timedelta(minutes=pren["durata_minuti"] or DURATA_PREDEFINITA_MIN)
    ora = tempo.adesso()
    if pren["stato_replica"] != "programmata" and not (pren["stato_replica"] == "conclusa" and ora <= fine):
        rifiuta(409, "La replica non è valida", pren)
    if ora < inizio - CHECK_IN_APERTURA:
        rifiuta(409, f"Il biglietto è per un'altra data: {data_leggibile(pren['data_ora'])}", pren)
    if ora > fine:
        rifiuta(409, f"Biglietto scaduto: lo spettacolo era il {data_leggibile(pren['data_ora'])}", pren)

    # Aggiornamento condizionato: se due varchi leggono lo stesso codice nello stesso
    # istante, solo uno trova ancora lo stato 'confermata' e convalida l'ingresso
    
    if not modifica("UPDATE prenotazioni SET stato = 'utilizzata', check_in_il = ? WHERE id = ? AND stato = 'confermata'",
                    (tempo.istante(ora), pren["id"])):
        rifiuta(409, "Prenotazione già utilizzata", leggi_prenotazione(pren["id"]))
    registra("prenotazioni.check_in", oggetto=f"prenotazione:{pren['id']}", dettagli={"codice": codice})
    return jsonify(leggi_prenotazione(pren["id"]))

