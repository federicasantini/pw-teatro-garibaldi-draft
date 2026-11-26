####################################################################################################################
#                                      API della dashboard direzionale                                             #
####################################################################################################################

# Espone indicatori KPI calcolati con SQL aggregato ed esportazione dei dati in CSV.

import csv
import io
from datetime import timedelta

from flask import Blueprint, Response, jsonify, request

from .. import tempo
from ..audit import registra
from ..auth import login_richiesto
from ..db import euro, query_all, query_one
from ..errors import ApiError

bp = Blueprint("dashboard", __name__)

VALIDA = "stato <> 'annullata'"


def _tasso(occupati, totali):
    return round(100 * occupati / totali, 1) if totali else None


def _per_spettacolo():
    righe = query_all(
        """SELECT s.id, s.titolo, s.genere,
                  COUNT(DISTINCT r.id) AS repliche,
                  COALESCE(SUM(CASE WHEN p.stato <> 'annullata' THEN p.num_posti END), 0) AS biglietti,
                  COALESCE(SUM(CASE WHEN p.stato <> 'annullata' THEN p.importo_cent END), 0) AS incasso_cent,
                  (SELECT ROUND(AVG(voto), 1) FROM feedback f WHERE f.spettacolo_id = s.id) AS voto_medio
           FROM spettacoli s
           LEFT JOIN repliche r     ON r.spettacolo_id = s.id AND r.stato <> 'annullata'
           LEFT JOIN prenotazioni p ON p.replica_id = r.id
           GROUP BY s.id ORDER BY biglietti DESC"""
    )
    for r in righe:
        r["incasso"] = euro(r.pop("incasso_cent"))
    return righe


@bp.get("/dashboard")
@login_richiesto("operatore")
def dashboard():
    ora = tempo.minuti()
    kpi = query_one(
        f"""SELECT
             (SELECT COUNT(*) FROM utenti WHERE ruolo = 'spettatore' AND eliminato_il IS NULL) AS spettatori_registrati,
             (SELECT COUNT(*) FROM prenotazioni WHERE {VALIDA})                     AS prenotazioni_valide,
             (SELECT COALESCE(SUM(num_posti), 0) FROM prenotazioni WHERE {VALIDA})  AS biglietti_emessi,
             (SELECT COALESCE(SUM(importo_cent), 0) FROM prenotazioni WHERE {VALIDA}) AS incasso_cent,
             (SELECT COALESCE(SUM(p.importo_cent), 0) FROM prenotazioni p JOIN repliche r ON r.id = p.replica_id
               WHERE p.{VALIDA} AND r.data_ora > ?)                                 AS prevendita_cent,
             (SELECT COUNT(*) FROM prenotazioni WHERE stato = 'annullata')          AS prenotazioni_annullate,
             (SELECT ROUND(AVG(voto), 2) FROM feedback)                             AS voto_medio,
             (SELECT COUNT(*) FROM feedback)                                        AS numero_feedback,
             (SELECT COUNT(*) FROM lista_attesa la JOIN repliche r ON r.id = la.replica_id
               WHERE r.data_ora > ? AND la.notificata_il IS NULL)                   AS in_lista_attesa""",
        (ora, ora),
    )
    kpi["incasso"] = euro(kpi.pop("incasso_cent"))
    kpi["incasso_prevendita"] = euro(kpi.pop("prevendita_cent"))
    kpi["incasso_realizzato"] = round(kpi["incasso"] - kpi["incasso_prevendita"], 2)
    totale = kpi["prenotazioni_valide"] + kpi["prenotazioni_annullate"]
    kpi["tasso_annullamento"] = round(100 * kpi["prenotazioni_annullate"] / totale, 1) if totale else 0

    # Il riempimento si misura solo sulle repliche già andate in scena: includere quelle
    # future, ancora in vendita, abbasserebbe artificialmente la media.
    # Per le repliche future si riporta a parte l'andamento della prevendita.
    occ = query_one(
        """SELECT SUM(CASE WHEN r.data_ora <= ? THEN o.posti_occupati END) AS occ_passate,
                  SUM(CASE WHEN r.data_ora <= ? THEN o.posti_totali END)   AS tot_passate,
                  SUM(CASE WHEN r.data_ora >  ? THEN o.posti_occupati END) AS occ_future,
                  SUM(CASE WHEN r.data_ora >  ? THEN o.posti_totali END)   AS tot_future
           FROM v_occupazione o JOIN repliche r ON r.id = o.replica_id
           WHERE r.stato <> 'annullata'""",
        (ora, ora, ora, ora),
    )
    kpi["tasso_riempimento"] = _tasso(occ["occ_passate"], occ["tot_passate"]) or 0
    kpi["tasso_prevendita"] = _tasso(occ["occ_future"], occ["tot_future"]) or 0

    per_genere = query_all(
        """SELECT s.genere, COALESCE(SUM(p.num_posti), 0) AS biglietti
           FROM prenotazioni p
           JOIN repliche r ON r.id = p.replica_id
           JOIN spettacoli s ON s.id = r.spettacolo_id
           WHERE p.stato <> 'annullata'
           GROUP BY s.genere ORDER BY biglietti DESC"""
    )
    per_settore = query_all(
        """SELECT se.nome AS settore, COALESCE(SUM(p.num_posti), 0) AS biglietti,
                  COALESCE(SUM(p.importo_cent), 0) AS incasso_cent
           FROM settori se LEFT JOIN prenotazioni p ON p.settore_id = se.id AND p.stato <> 'annullata'
           GROUP BY se.id ORDER BY se.prezzo_cent DESC"""
    )
    for r in per_settore:
        r["incasso"] = euro(r.pop("incasso_cent"))
    per_tariffa = query_all(
        """SELECT t.nome AS tariffa, COALESCE(SUM(p.num_posti), 0) AS biglietti
           FROM tariffe t LEFT JOIN prenotazioni p ON p.tariffa_id = t.id AND p.stato <> 'annullata'
           GROUP BY t.id ORDER BY biglietti DESC"""
    )
    andamento = query_all(
        """SELECT substr(data_prenotazione, 1, 10) AS giorno, COUNT(*) AS prenotazioni,
                  SUM(num_posti) AS biglietti
           FROM prenotazioni
           WHERE stato <> 'annullata' AND data_prenotazione >= ?
           GROUP BY giorno ORDER BY giorno""",
        (tempo.istante(tempo.adesso() - timedelta(days=30))[:10],),
    )
    return jsonify({
        "kpi": kpi,
        "per_spettacolo": _per_spettacolo(),
        "per_genere": per_genere,
        "per_settore": per_settore,
        "per_tariffa": per_tariffa,
        "andamento_30_giorni": andamento,
    })


def _csv(nome_file: str, intestazioni: list[str], righe) -> Response:
    """CSV in italiano: separatore ';', virgola decimale, BOM UTF-8"""
    def cella(v):
        return f"{v:.2f}".replace(".", ",") if isinstance(v, float) else v
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(intestazioni)
    for r in righe:
        w.writerow([cella(v) for v in r])
    return Response(buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome_file}"'})


@bp.get("/dashboard/export")
@login_richiesto("operatore")
def esporta():
    """Esportazione CSV: ?dati=spettacoli (riepilogo) oppure ?dati=prenotazioni (dettaglio)"""
    oggi = tempo.adesso().strftime("%Y%m%d")
    tipo = request.args.get("dati", "spettacoli")
    if tipo in ("spettacoli", "prenotazioni"):
        registra("dati.export_csv", dettagli={"dati": tipo})
    if tipo == "spettacoli":
        righe = _per_spettacolo()
        return _csv(f"riepilogo-spettacoli-{oggi}.csv",
                    ["Titolo", "Genere", "Repliche", "Biglietti", "Incasso (€)", "Voto medio"],
                    ([r["titolo"], r["genere"], r["repliche"], r["biglietti"], r["incasso"],
                      float(r["voto_medio"]) if r["voto_medio"] is not None else ""] for r in righe))
    if tipo == "prenotazioni":
        righe = query_all(
            """SELECT p.codice, s.titolo, r.data_ora, se.nome AS settore, t.nome AS tariffa,
                      p.num_posti, p.importo_cent, p.stato, p.data_prenotazione
               FROM prenotazioni p
               JOIN repliche r ON r.id = p.replica_id JOIN spettacoli s ON s.id = r.spettacolo_id
               JOIN settori se ON se.id = p.settore_id JOIN tariffe t ON t.id = p.tariffa_id
               ORDER BY r.data_ora, p.id""")
        # nessun dato personale dello spettatore nell'export (minimizzazione, art. 5 GDPR)
        return _csv(f"prenotazioni-{oggi}.csv",
                    ["Codice", "Spettacolo", "Data replica", "Settore", "Tariffa", "Posti", "Importo (€)",
                     "Stato", "Data prenotazione"],
                    ([r["codice"], r["titolo"], r["data_ora"].replace("T", " "), r["settore"], r["tariffa"],
                      r["num_posti"], euro(r["importo_cent"]), r["stato"],
                      r["data_prenotazione"].replace("T", " ")] for r in righe))
    raise ApiError(422, "Parametro 'dati' non valido: usare 'spettacoli' o 'prenotazioni'")
