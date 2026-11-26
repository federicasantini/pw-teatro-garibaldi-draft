####################################################################################################################
#                                      API del catalogo e delle repliche                                          #
####################################################################################################################

# Gestisce spettacoli, repliche, sale, settori e disponibilità dei posti

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from .. import tempo
from ..audit import registra
from ..auth import login_richiesto
from ..db import euro, execute, lista_json, modifica, query_all, query_one, transazione
from ..errors import ApiError
from ..notifiche import data_leggibile, invia
from ..validation import corpo_json, data_ora, importo_cent, intero, richiesti, testo

bp = Blueprint("catalogo", __name__)

GENERI = ("prosa", "lirica", "danza", "musica", "ragazzi")
LIMITI_TESTO = {"titolo": 200, "autore": 200, "compagnia": 200, "descrizione": 4000}

DURATA_PREDEFINITA_MIN = 120   # se lo spettacolo non ha durata si assumono 2 ore
CAMBIO_SCENA_MIN = 60          # intervallo minimo tra la fine di una replica e l'inizio della successiva

# Transizioni di stato consentite per una replica (vedi docs/diagrammi/stati_replica.png)
TRANSIZIONI_REPLICA = {
    "programmata": {"annullata", "conclusa"},
    "annullata": set(),   # stato finale: per recuperare la data si programma una nuova replica
    "conclusa": set(),    # stato finale
}


def _occupazione(replica_ids) -> dict[int, list[dict]]:
    # Disponibilità per settore di più repliche con UNA sola query 
    per_replica: dict[int, list[dict]] = {rid: [] for rid in replica_ids}
    for r in query_all(
        """SELECT * FROM v_occupazione WHERE replica_id IN (SELECT value FROM json_each(?))
           ORDER BY replica_id, prezzo_cent DESC""",
        (lista_json(replica_ids),),
    ):
        r["prezzo"] = euro(r["prezzo_cent"])
        r["posti_disponibili"] = r["posti_totali"] - r["posti_occupati"]
        per_replica[r["replica_id"]].append(r)
    return per_replica


# ------------------------------------------------------------------- spettacoli
@bp.get("/spettacoli")
def elenco_spettacoli():
    # Spettacoli attivi con la prossima replica e voto medio

    condizioni, params = [], [tempo.minuti()]
    if request.args.get("tutti") != "1":
        condizioni.append("s.attivo = 1")
    if genere := request.args.get("genere"):
        condizioni.append("s.genere = ?")
        params.append(genere)
    if q := request.args.get("q"):
        condizioni.append("(s.titolo LIKE ? OR s.autore LIKE ? OR s.compagnia LIKE ?)")
        params += [f"%{q}%"] * 3
    where = ("WHERE " + " AND ".join(condizioni)) if condizioni else ""
    sql = f"""
        SELECT s.*,
               (SELECT MIN(r.data_ora) FROM repliche r
                 WHERE r.spettacolo_id = s.id AND r.stato = 'programmata' AND r.data_ora >= ?)
                   AS prossima_replica,
               (SELECT ROUND(AVG(f.voto), 1) FROM feedback f WHERE f.spettacolo_id = s.id)
                   AS voto_medio,
               (SELECT COUNT(*) FROM feedback f WHERE f.spettacolo_id = s.id) AS num_recensioni
        FROM spettacoli s {where}
        ORDER BY prossima_replica IS NULL, prossima_replica, s.titolo"""
    return jsonify(query_all(sql, params))


@bp.get("/spettacoli/<int:sid>")
def dettaglio_spettacolo(sid):
    spettacolo = query_one("SELECT * FROM spettacoli WHERE id = ?", (sid,))
    if not spettacolo:
        raise ApiError(404, "Spettacolo non trovato")
    repliche = query_all(
        """SELECT r.id, r.data_ora, r.stato, sa.nome AS sala
           FROM repliche r JOIN sale sa ON sa.id = r.sala_id
           WHERE r.spettacolo_id = ? ORDER BY r.data_ora""",
        (sid,),
    )
    occupazione = _occupazione([r["id"] for r in repliche])
    for r in repliche:
        disp = occupazione[r["id"]]
        r["posti_disponibili"] = sum(d["posti_disponibili"] for d in disp)
        r["prezzo_da"] = min((d["prezzo"] for d in disp), default=None)
    spettacolo["repliche"] = repliche
    return jsonify(spettacolo)


def _valida_spettacolo(dati: dict, parziale: bool = False) -> dict:
    if not parziale:
        richiesti(dati, "titolo", "genere")
    valori = {}
    for campo, limite in LIMITI_TESTO.items():
        if campo in dati:
            valori[campo] = testo(dati[campo], campo, limite, obbligatorio=(campo == "titolo"))
    if "genere" in dati:
        if dati["genere"] not in GENERI:
            raise ApiError(422, f"Genere non valido. Valori ammessi: {', '.join(GENERI)}")
        valori["genere"] = dati["genere"]
    if "durata_minuti" in dati:
        valori["durata_minuti"] = (None if dati["durata_minuti"] in (None, "")
                                   else intero(dati["durata_minuti"], "durata_minuti", 1, 600))
    if "attivo" in dati:
        valori["attivo"] = 1 if dati["attivo"] else 0
    return valori


@bp.post("/spettacoli")
@login_richiesto("operatore")
def crea_spettacolo():
    valori = _valida_spettacolo(corpo_json())
    valori["creato_il"] = tempo.istante()
    colonne = ", ".join(valori)  # i nomi di colonna provengono da un elenco fisso, non dall'utente
    segnaposto = ", ".join("?" for _ in valori)
    sid = execute(f"INSERT INTO spettacoli ({colonne}) VALUES ({segnaposto})", tuple(valori.values()))
    registra("catalogo.spettacolo_creato", oggetto=f"spettacolo:{sid}", dettagli={"titolo": valori["titolo"]})
    return jsonify(query_one("SELECT * FROM spettacoli WHERE id = ?", (sid,))), 201


@bp.put("/spettacoli/<int:sid>")
@login_richiesto("operatore")
def modifica_spettacolo(sid):
    if not query_one("SELECT id FROM spettacoli WHERE id = ?", (sid,)):
        raise ApiError(404, "Spettacolo non trovato")
    valori = _valida_spettacolo(corpo_json(), parziale=True)
    if not valori:
        raise ApiError(422, "Nessun campo da aggiornare")
    assegnazioni = ", ".join(f"{k} = ?" for k in valori)
    execute(f"UPDATE spettacoli SET {assegnazioni} WHERE id = ?", (*valori.values(), sid))
    registra("catalogo.spettacolo_modificato", oggetto=f"spettacolo:{sid}", dettagli={"campi": sorted(valori)})
    return jsonify(query_one("SELECT * FROM spettacoli WHERE id = ?", (sid,)))


@bp.delete("/spettacoli/<int:sid>")
@login_richiesto("admin")
def elimina_spettacolo(sid):
    # Eliminazione logica: lo spettacolo esce dalla programmazione ma lo storico resta
    if not query_one("SELECT id FROM spettacoli WHERE id = ?", (sid,)):
        raise ApiError(404, "Spettacolo non trovato")
    execute("UPDATE spettacoli SET attivo = 0 WHERE id = ?", (sid,))
    registra("catalogo.spettacolo_ritirato", oggetto=f"spettacolo:{sid}")
    return "", 204


@bp.get("/repliche")
def elenco_repliche():
    # Calendario delle repliche
    da = request.args.get("da", "0000-01-01")
    a = request.args.get("a", "9999-12-31") + "T23:59"
    righe = query_all(
        """SELECT r.id, r.data_ora, r.stato, r.spettacolo_id, r.sala_id, s.titolo, s.genere,
                  s.durata_minuti, sa.nome AS sala,
                  COALESCE(o.posti_totali, 0) AS posti_totali, COALESCE(o.posti_occupati, 0) AS posti_occupati
           FROM repliche r
           JOIN spettacoli s ON s.id = r.spettacolo_id
           JOIN sale sa ON sa.id = r.sala_id
           LEFT JOIN (SELECT replica_id, SUM(posti_totali) AS posti_totali, SUM(posti_occupati) AS posti_occupati
                      FROM v_occupazione GROUP BY replica_id) o ON o.replica_id = r.id
           WHERE r.data_ora BETWEEN ? AND ?
           ORDER BY r.data_ora""",
        (da, a),
    )
    return jsonify(righe)


@bp.get("/repliche/<int:rid>/disponibilita")
def disponibilita(rid):
    replica = query_one(
        """SELECT r.*, s.titolo FROM repliche r JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE r.id = ?""",
        (rid,),
    )
    if not replica:
        raise ApiError(404, "Replica non trovata")
    replica["settori"] = _occupazione([rid])[rid]
    return jsonify(replica)


def _fine(inizio: datetime, durata) -> datetime:
    return inizio + timedelta(minutes=durata or DURATA_PREDEFINITA_MIN)


def _verifica_sala_libera(sala_id: int, inizio: datetime, durata) -> None:
    #Due repliche nella stessa sala non possono sovrapporsi

    fine = _fine(inizio, durata)
    vicine = query_all(
        """SELECT r.id, r.data_ora, s.titolo, s.durata_minuti FROM repliche r
           JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE r.sala_id = ? AND r.stato <> 'annullata' AND r.data_ora BETWEEN ? AND ?""",
        (sala_id, tempo.minuti(inizio - timedelta(days=1)), tempo.minuti(inizio + timedelta(days=1))),
    )
    margine = timedelta(minutes=CAMBIO_SCENA_MIN)
    for altra in vicine:
        a_inizio = datetime.fromisoformat(altra["data_ora"])
        a_fine = _fine(a_inizio, altra["durata_minuti"])
        if inizio < a_fine + margine and a_inizio < fine + margine:
            raise ApiError(409, f"La sala è occupata: «{altra['titolo']}» il {data_leggibile(altra['data_ora'])} "
                                f"(serve un intervallo di almeno {CAMBIO_SCENA_MIN} minuti tra le repliche)",
                           {"replica_in_conflitto": altra["id"]})


@bp.post("/repliche")
@login_richiesto("operatore")
def crea_replica():
    # Programma una replica

    dati = corpo_json()
    richiesti(dati, "spettacolo_id", "data_ora")
    sid = intero(dati["spettacolo_id"], "spettacolo_id", 1)
    quando = data_ora(dati["data_ora"])
    sala_id = intero(dati.get("sala_id", 1), "sala_id", 1)
    spettacolo = query_one("SELECT id, durata_minuti FROM spettacoli WHERE id = ? AND attivo = 1", (sid,))
    if not spettacolo:
        raise ApiError(404, "Spettacolo non trovato o non attivo")
    if not query_one("SELECT id FROM sale WHERE id = ?", (sala_id,)):
        raise ApiError(404, "Sala non trovata")
    if quando < tempo.minuti():
        raise ApiError(422, "Non è possibile programmare una replica nel passato")

    prezzi = dati.get("prezzi") or {}
    if not isinstance(prezzi, dict):
        raise ApiError(422, "Il campo 'prezzi' deve essere un oggetto {settore_id: prezzo}")
    settori_sala = {r["id"] for r in query_all("SELECT id FROM settori WHERE sala_id = ?", (sala_id,))}
    listino = {}
    for chiave, valore in prezzi.items():
        settore_id = intero(chiave, "settore_id", 1)
        if settore_id not in settori_sala:
            raise ApiError(422, "Il listino contiene un settore che non appartiene alla sala")
        if valore not in (None, ""):
            listino[settore_id] = importo_cent(valore, f"prezzo del settore {settore_id}")

    with transazione():
        _verifica_sala_libera(sala_id, datetime.fromisoformat(quando), spettacolo["durata_minuti"])
        rid = execute("INSERT INTO repliche (spettacolo_id, sala_id, data_ora) VALUES (?, ?, ?)",
                      (sid, sala_id, quando))
        for settore_id, cent in listino.items():
            execute("INSERT INTO prezzi_replica (replica_id, settore_id, prezzo_cent) VALUES (?, ?, ?)",
                    (rid, settore_id, cent))
    registra("catalogo.replica_creata", oggetto=f"replica:{rid}",
             dettagli={"spettacolo_id": sid, "data_ora": quando, "listino_cent": listino or None})
    return jsonify(query_one("SELECT * FROM repliche WHERE id = ?", (rid,))), 201


@bp.patch("/repliche/<int:rid>")
@login_richiesto("operatore")
def aggiorna_stato_replica(rid):
    # Cambio di stato della replica
    # L'annullamento annulla anche le prenotazioni e avvisa gli spettatori
    
    dati = corpo_json()
    stato = dati.get("stato")
    if stato not in TRANSIZIONI_REPLICA:
        raise ApiError(422, "Stato non valido")
    with transazione():
        replica = query_one(
            """SELECT r.*, s.titolo FROM repliche r JOIN spettacoli s ON s.id = r.spettacolo_id
               WHERE r.id = ?""", (rid,))
        if not replica:
            raise ApiError(404, "Replica non trovata")
        if stato not in TRANSIZIONI_REPLICA[replica["stato"]]:
            raise ApiError(409, f"Transizione non consentita: da '{replica['stato']}' a '{stato}'")
        if stato == "conclusa" and replica["data_ora"] > tempo.minuti():
            raise ApiError(409, "Una replica non ancora iniziata non può essere conclusa")

        modifica("UPDATE repliche SET stato = ? WHERE id = ?", (stato, rid))
        if stato == "annullata":
            coinvolti = query_all(
                """SELECT DISTINCT utente_id FROM prenotazioni WHERE replica_id = ? AND stato = 'confermata'""",
                (rid,))
            modifica("""UPDATE prenotazioni SET stato = 'annullata', annullata_il = ?
                        WHERE replica_id = ? AND stato = 'confermata'""", (tempo.istante(), rid))
            modifica("DELETE FROM lista_attesa WHERE replica_id = ?", (rid,))
            for c in coinvolti:
                invia(c["utente_id"], f"Replica annullata: {replica['titolo']}",
                      f"Ci dispiace: la replica «{replica['titolo']}» del {data_leggibile(replica['data_ora'])} "
                      f"è stata annullata e la tua prenotazione è stata cancellata. "
                      f"Puoi scegliere un'altra data dalla programmazione.")
    registra("catalogo.replica_stato", oggetto=f"replica:{rid}",
             dettagli={"precedente": replica["stato"], "nuovo": stato})
    return jsonify(query_one("SELECT * FROM repliche WHERE id = ?", (rid,)))


@bp.get("/sale")
def sale():
    elenco = query_all("SELECT * FROM sale ORDER BY id")
    settori = query_all("SELECT * FROM settori ORDER BY sala_id, prezzo_cent DESC")
    for s in elenco:
        s["settori"] = [{**x, "prezzo": euro(x["prezzo_cent"])} for x in settori if x["sala_id"] == s["id"]]
    return jsonify(elenco)
