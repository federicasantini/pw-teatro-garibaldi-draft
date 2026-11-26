####################################################################################################################
#                             API di utenti, autenticazione e GDPR                                              #
####################################################################################################################

# Gestisce registrazione, accesso, diritti GDPR e amministrazione degli utenti.

import secrets

from flask import Blueprint, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from .. import tempo
from ..audit import registra
from ..auth import (
    azzera_tentativi,
    crea_sessione,
    elimina_sessione,
    login_richiesto,
    registra_tentativo_fallito,
    utente_corrente,
    verifica_tentativi,
)
from ..db import execute, modifica, query_all, query_one, transazione
from ..errors import ApiError
from ..notifiche import invia
from ..validation import corpo_json, email_valida, password_robusta, richiesti, testo
from .prenotazioni import SELECT_PRENOTAZIONE, annulla

bp = Blueprint("utenti", __name__)

CAMPI_PROFILO = "id, nome, cognome, email, ruolo"


@bp.post("/auth/registrazione")
def registrazione():
    dati = corpo_json()
    richiesti(dati, "nome", "cognome", "email", "password")
    nome = testo(dati["nome"], "nome", 100)
    cognome = testo(dati["cognome"], "cognome", 100)
    email = email_valida(dati["email"])
    password_robusta(dati["password"])
    if dati.get("consenso_privacy") is not True:
        raise ApiError(422, "È necessario accettare l'informativa sulla privacy")
    if query_one("SELECT id FROM utenti WHERE email = ?", (email,)):
        raise ApiError(409, "Esiste già un account con questa email")

    uid = execute(
        """INSERT INTO utenti (nome, cognome, email, password_hash, ruolo, consenso_privacy, data_registrazione)
           VALUES (?, ?, ?, ?, 'spettatore', 1, ?)""",
        (nome, cognome, email, generate_password_hash(dati["password"]), tempo.istante()),
    )
    token = crea_sessione(uid)
    registra("account.registrato", utente={"id": uid, "ruolo": "spettatore", "email": email})
    invia(uid, "Benvenuto al Teatro Garibaldi",
          f"Ciao {nome},\nil tuo account è attivo! Dalla programmazione puoi prenotare i posti e "
          f"nella tua area personale puoi trovare biglietti e messaggi.")
    utente = query_one(f"SELECT {CAMPI_PROFILO} FROM utenti WHERE id = ?", (uid,))
    return jsonify({"token": token, "utente": utente}), 201


@bp.post("/auth/login")
def login():
    dati = corpo_json()
    richiesti(dati, "email", "password")
    email = testo(dati["email"], "email", 254).lower()
    password = dati["password"]
    if not isinstance(password, str):
        raise ApiError(422, "Il campo 'password' deve essere un testo")
    verifica_tentativi(email)
    riga = query_one("SELECT * FROM utenti WHERE email = ? AND eliminato_il IS NULL", (email,))
    # Messaggio generico: non rivela se l'email esiste, mitiga l'enumerazione degli account
    if not riga or not check_password_hash(riga["password_hash"], password):
        registra_tentativo_fallito(email)
        registra("accesso.fallito", esito="fallito", email=email)
        raise ApiError(401, "Credenziali non valide")
    azzera_tentativi(email)
    token = crea_sessione(riga["id"])
    utente = {k: riga[k] for k in ("id", "nome", "cognome", "email", "ruolo")}
    registra("accesso.riuscito", utente=utente)
    return jsonify({"token": token, "utente": utente})


@bp.post("/auth/logout")
@login_richiesto()
def logout():
    elimina_sessione(g.token)
    registra("accesso.logout")
    return "", 204


@bp.get("/auth/me")
@login_richiesto()
def me():
    return jsonify(utente_corrente())


@bp.get("/notifiche")
@login_richiesto()
def mie_notifiche():
    return jsonify(query_all(
        "SELECT id, oggetto, corpo, creata_il FROM notifiche WHERE utente_id = ? ORDER BY creata_il DESC, id DESC LIMIT 50",
        (utente_corrente()["id"],)))


# ------------------------------------------------- Diritti GDPR
@bp.get("/auth/me/dati")
@login_richiesto()
def esporta_dati():
    # Diritto di accesso e portabilità (artt. 15 e 20 GDPR) 

    uid = utente_corrente()["id"]
    dati = {
        "esportato_il": tempo.istante(),
        "profilo": query_one(
            "SELECT id, nome, cognome, email, ruolo, consenso_privacy, data_registrazione FROM utenti WHERE id = ?",
            (uid,)),
        "prenotazioni": query_all(SELECT_PRENOTAZIONE + " WHERE p.utente_id = ? ORDER BY r.data_ora", (uid,)),
        "feedback": query_all(
            """SELECT f.spettacolo_id, s.titolo, f.voto, f.commento, f.data
               FROM feedback f JOIN spettacoli s ON s.id = f.spettacolo_id WHERE f.utente_id = ?""", (uid,)),
        "lista_attesa": query_all("SELECT replica_id, num_posti, creata_il, notificata_il FROM lista_attesa WHERE utente_id = ?",
                                  (uid,)),
        "notifiche": query_all("SELECT oggetto, corpo, creata_il FROM notifiche WHERE utente_id = ? ORDER BY creata_il",
                               (uid,)),
        "sessioni_attive": query_one("SELECT COUNT(*) AS n FROM sessioni WHERE utente_id = ? AND scade_il > ?",
                                     (uid, tempo.istante()))["n"],
    }
    registra("account.dati_esportati")
    risposta = jsonify(dati)
    risposta.headers["Content-Disposition"] = f'attachment; filename="teatro-garibaldi-dati-{uid}.json"'
    return risposta


@bp.delete("/auth/me")
@login_richiesto()
def elimina_account():
    # Diritto alla cancellazione (art. 17 GDPR): i dati identificativi vengono cancellati in modo irreversibile
    # ma restano anonimi i movimenti necessari per la contabilità e i voti (recensioni) per le statistiche 

    dati = corpo_json()
    utente = utente_corrente()
    riga = query_one("SELECT password_hash FROM utenti WHERE id = ?", (utente["id"],))
    if not isinstance(dati.get("password"), str) or not check_password_hash(riga["password_hash"], dati["password"]):
        registra("account.eliminato", esito="fallito", dettagli={"motivo": "password errata"})
        raise ApiError(403, "Password non corretta")
    if utente["ruolo"] == "admin" and query_one(
            "SELECT COUNT(*) AS n FROM utenti WHERE ruolo = 'admin' AND eliminato_il IS NULL")["n"] <= 1:
        raise ApiError(409, "Non è possibile eliminare l'unico amministratore")

    # le prenotazioni future vengono annullate (liberando i posti per la lista d'attesa)
    for pren in query_all(SELECT_PRENOTAZIONE + " WHERE p.utente_id = ? AND p.stato = 'confermata' AND r.data_ora > ?",
                          (utente["id"], tempo.minuti())):
        annulla(pren)
    with transazione():
        uid = utente["id"]
        for tabella in ("sessioni", "lista_attesa", "notifiche"):
            modifica(f"DELETE FROM {tabella} WHERE utente_id = ?", (uid,))
        modifica("UPDATE feedback SET commento = NULL WHERE utente_id = ?", (uid,))
        modifica(
            """UPDATE utenti SET nome = 'Utente', cognome = 'eliminato', email = ?, password_hash = ?,
                      consenso_privacy = 0, ruolo = 'spettatore', eliminato_il = ?
               WHERE id = ?""",
            (f"eliminato-{uid}@anonimo.invalid", generate_password_hash(secrets.token_urlsafe(32)),
             tempo.istante(), uid),
        )
    # dopo la cancellazione l'evento non riporta più l'email ma resta l'id utente

    registra("account.eliminato", utente={"id": uid, "ruolo": utente["ruolo"], "email": None})
    return "", 204


# ---------------------------------------------------------------- amministrazione
@bp.get("/utenti")
@login_richiesto("admin")
def elenco_utenti():
    return jsonify(query_all(
        """SELECT u.id, u.nome, u.cognome, u.email, u.ruolo, u.data_registrazione,
                  (SELECT COUNT(*) FROM prenotazioni p
                    WHERE p.utente_id = u.id AND p.stato <> 'annullata') AS prenotazioni
           FROM utenti u WHERE u.eliminato_il IS NULL ORDER BY u.cognome, u.nome"""
    ))


@bp.patch("/utenti/<int:uid>")
@login_richiesto("admin")
def modifica_ruolo(uid):
    dati = corpo_json()
    ruolo = dati.get("ruolo")
    if ruolo not in ("spettatore", "operatore", "admin"):
        raise ApiError(422, "Ruolo non valido")
    if uid == utente_corrente()["id"]:
        raise ApiError(409, "Non è possibile modificare il proprio ruolo")
    destinatario = query_one("SELECT email, ruolo FROM utenti WHERE id = ? AND eliminato_il IS NULL", (uid,))
    if not destinatario:
        raise ApiError(404, "Utente non trovato")
    execute("UPDATE utenti SET ruolo = ? WHERE id = ?", (ruolo, uid))
    registra("account.ruolo_modificato", oggetto=f"utente:{uid}",
             dettagli={"utente": destinatario["email"], "precedente": destinatario["ruolo"], "nuovo": ruolo})
    return jsonify(query_one(f"SELECT {CAMPI_PROFILO} FROM utenti WHERE id = ?", (uid,)))
