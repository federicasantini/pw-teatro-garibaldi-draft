###############################################################################
# Test funzionali delle API REST (pytest + client di test Flask)
# Fixture e funzioni di supporto sono in conftest.py
###############################################################################

from datetime import datetime, timedelta

from backend import tempo

from .conftest import accedi_come, login, nuovo_utente, prima_replica_futura


# --------------------------------------------------------------- autenticazione
def test_TC01_registrazione_e_login(client):
    dati = {"nome": "Mario", "cognome": "Verdi", "email": "mario@example.com",
            "password": "Sicura123", "consenso_privacy": True}
    r = client.post("/api/auth/registrazione", json=dati)
    assert r.status_code == 201
    assert r.get_json()["utente"]["ruolo"] == "spettatore"
    # email duplicata
    assert client.post("/api/auth/registrazione", json=dati).status_code == 409
    h = login(client, "mario@example.com", "Sicura123")
    assert client.get("/api/auth/me", headers=h).get_json()["email"] == "mario@example.com"


def test_TC02_registrazione_validazione(client):
    base = {"nome": "A", "cognome": "B", "email": "x@example.com", "consenso_privacy": True}
    assert client.post("/api/auth/registrazione", json={**base, "password": "corta"}).status_code == 422
    assert client.post("/api/auth/registrazione", json={**base, "password": "Sicura123", "email": "non-email"}).status_code == 422
    assert client.post("/api/auth/registrazione", json={**base, "password": "Sicura123", "consenso_privacy": False}).status_code == 422


def test_TC03_login_errato_e_logout(client, spettatore):
    assert client.post("/api/auth/login", json={"email": "anna.rinaldi@example.com", "password": "sbagliata"}).status_code == 401
    assert client.post("/api/auth/logout", headers=spettatore).status_code == 204
    assert client.get("/api/auth/me", headers=spettatore).status_code == 401  # token invalidato


# --------------------------------------------------------------------- catalogo
def test_TC04_cartellone_e_filtri(client):
    tutti = client.get("/api/spettacoli").get_json()
    assert len(tutti) == 6
    lirica = client.get("/api/spettacoli?genere=lirica").get_json()
    assert [s["titolo"] for s in lirica] == ["La traviata"]
    assert client.get("/api/spettacoli?q=Goldoni").get_json()[0]["titolo"] == "La locandiera"


def test_TC05_dettaglio_e_disponibilita(client):
    s = client.get("/api/spettacoli/1").get_json()
    assert s["repliche"]
    rid = s["repliche"][0]["id"]
    disp = client.get(f"/api/repliche/{rid}/disponibilita").get_json()
    assert {x["settore"] for x in disp["settori"]} == {"Platea", "Palchi", "Loggione"}
    assert client.get("/api/spettacoli/999").status_code == 404


# ------------------------------------------------------------------ prenotazioni
def test_TC06_prenotazione_completa(client, spettatore):
    rep = prima_replica_futura(client)
    disp = client.get(f"/api/repliche/{rep['id']}/disponibilita").get_json()
    loggione = next(s for s in disp["settori"] if s["settore"] == "Loggione")
    r = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rep["id"], "settore_id": loggione["settore_id"], "num_posti": 2})
    assert r.status_code == 201
    p = r.get_json()
    assert p["codice"].startswith("TG-") and p["importo_totale"] == 30.0
    dopo = client.get(f"/api/repliche/{rep['id']}/disponibilita").get_json()
    g2 = next(s for s in dopo["settori"] if s["settore"] == "Loggione")
    assert g2["posti_disponibili"] == loggione["posti_disponibili"] - 2


def test_TC07_prenotazione_richiede_login(client):
    rep = prima_replica_futura(client)
    r = client.post("/api/prenotazioni", json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1})
    assert r.status_code == 401


def test_TC08_overbooking_impedito(client):
    rep = prima_replica_futura(client)
    disp = client.get(f"/api/repliche/{rep['id']}/disponibilita").get_json()
    settore = min(disp["settori"], key=lambda s: s["posti_disponibili"])
    # esaurisce il settore a blocchi di 6 posti, un utente diverso per blocco
    # (ogni utente può prenotare al massimo 6 posti per replica)
    liberi = settore["posti_disponibili"]
    while liberi > 0:
        n = min(6, liberi)
        assert client.post("/api/prenotazioni", headers=nuovo_utente(client),
                           json={"replica_id": rep["id"], "settore_id": settore["settore_id"], "num_posti": n}).status_code == 201
        liberi -= n
    r = client.post("/api/prenotazioni", headers=nuovo_utente(client),
                    json={"replica_id": rep["id"], "settore_id": settore["settore_id"], "num_posti": 1})
    assert r.status_code == 409
    assert r.get_json()["dettagli"]["posti_disponibili"] == 0


def test_TC09_limite_posti_per_prenotazione(client, spettatore):
    rep = prima_replica_futura(client)
    r = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 7})
    assert r.status_code == 422


def test_TC10_annullamento_e_check_in(client, spettatore, orologio):
    rep = prima_replica_futura(client)
    p = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1}).get_json()
    # check-in da parte dell'operatore, mezz'ora prima dell'inizio
    orologio(datetime.fromisoformat(rep["data_ora"]) - timedelta(minutes=30))
    operatore = accedi_come(client, "operatore")
    r = client.post("/api/prenotazioni/check-in", headers=operatore, json={"codice": p["codice"].lower()})
    assert r.status_code == 200 and r.get_json()["stato"] == "utilizzata"
    assert r.get_json()["check_in_il"] is not None
    # doppio ingresso respinto
    assert client.post("/api/prenotazioni/check-in", headers=operatore, json={"codice": p["codice"]}).status_code == 409
    # una prenotazione utilizzata non è più annullabile
    assert client.delete(f"/api/prenotazioni/{p['id']}", headers=accedi_come(client, "spettatore")).status_code == 409


def test_TC11_spettatore_vede_solo_le_proprie_prenotazioni(client, spettatore, operatore):
    mie = client.get("/api/prenotazioni", headers=spettatore).get_json()
    assert mie and {p["email"] for p in mie} == {"anna.rinaldi@example.com"}
    tutte = client.get("/api/prenotazioni", headers=operatore).get_json()
    assert len(tutte) > len(mie)


# --------------------------------------------------------------------- feedback
def test_TC12_feedback_solo_dopo_visione(client):
    # un nuovo utente non ha visto nulla: feedback respinto
    r = client.post("/api/auth/registrazione", json={"nome": "N", "cognome": "U", "email": "nuovo@example.com",
                                                      "password": "Sicura123", "consenso_privacy": True})
    h = {"Authorization": f"Bearer {r.get_json()['token']}"}
    assert client.post("/api/feedback", headers=h, json={"spettacolo_id": 1, "voto": 5}).status_code == 403


def test_TC13_feedback_valido_e_duplicato(client, operatore, orologio):
    pren = client.get("/api/prenotazioni?stato=utilizzata", headers=operatore).get_json()
    assert pren  # il seed contiene prenotazioni utilizzate
    client.post("/api/auth/registrazione", json={"nome": "Fe", "cognome": "Db", "email": "fb@example.com",
                                                 "password": "Sicura123", "consenso_privacy": True})
    h = login(client, "fb@example.com", "Sicura123")
    rep = prima_replica_futura(client)
    p = client.post("/api/prenotazioni", headers=h, json={"replica_id": rep["id"], "settore_id": 2, "num_posti": 1}).get_json()
    sid = client.get(f"/api/repliche/{rep['id']}/disponibilita").get_json()["spettacolo_id"]
    # prima di aver visto lo spettacolo il feedback è respinto
    assert client.post("/api/feedback", headers=h, json={"spettacolo_id": sid, "voto": 4}).status_code == 403
    orologio(datetime.fromisoformat(rep["data_ora"]) - timedelta(minutes=10))
    assert client.post("/api/prenotazioni/check-in", headers=accedi_come(client, "operatore"),
                       json={"codice": p["codice"]}).status_code == 200
    h = login(client, "fb@example.com", "Sicura123")  # la sessione precedente è scaduta: l'orologio è avanzato
    assert client.post("/api/feedback", headers=h, json={"spettacolo_id": sid, "voto": 4, "commento": "Bello"}).status_code == 201
    assert client.post("/api/feedback", headers=h, json={"spettacolo_id": sid, "voto": 5}).status_code == 409
    assert client.post("/api/feedback", headers=h, json={"spettacolo_id": sid, "voto": 9}).status_code == 422


# --------------------------------------------------------------- back-office
def test_TC14_controllo_accessi_per_ruolo(client, spettatore, operatore, admin):
    assert client.get("/api/dashboard", headers=spettatore).status_code == 403
    assert client.get("/api/dashboard", headers=operatore).status_code == 200
    assert client.get("/api/utenti", headers=operatore).status_code == 403
    assert client.get("/api/utenti", headers=admin).status_code == 200
    assert client.post("/api/spettacoli", headers=spettatore, json={"titolo": "X", "genere": "prosa"}).status_code == 403


def test_TC15_gestione_catalogo_e_repliche(client, operatore, spettatore):
    s = client.post("/api/spettacoli", headers=operatore,
                    json={"titolo": "Il malato immaginario", "autore": "Molière", "genere": "prosa", "durata_minuti": 110})
    assert s.status_code == 201
    sid = s.get_json()["id"]
    assert client.put(f"/api/spettacoli/{sid}", headers=operatore, json={"compagnia": "Nuova Compagnia"}).get_json()["compagnia"] == "Nuova Compagnia"
    assert client.post("/api/spettacoli", headers=operatore, json={"titolo": "X", "genere": "circo"}).status_code == 422

    quando = (tempo.adesso() + timedelta(days=200)).strftime("%Y-%m-%dT21:00")
    r = client.post("/api/repliche", headers=operatore, json={"spettacolo_id": sid, "data_ora": quando})
    assert r.status_code == 201
    rid = r.get_json()["id"]
    # stessa sala alla stessa ora: conflitto
    assert client.post("/api/repliche", headers=operatore, json={"spettacolo_id": sid, "data_ora": quando}).status_code == 409
    # replica nel passato non ammessa
    assert client.post("/api/repliche", headers=operatore, json={"spettacolo_id": sid, "data_ora": "2020-01-01T21:00"}).status_code == 422

    p = client.post("/api/prenotazioni", headers=spettatore, json={"replica_id": rid, "settore_id": 1, "num_posti": 2}).get_json()
    # annullando la replica si annullano a cascata le prenotazioni
    assert client.patch(f"/api/repliche/{rid}", headers=operatore, json={"stato": "annullata"}).status_code == 200
    mie = client.get("/api/prenotazioni", headers=spettatore).get_json()
    assert next(x for x in mie if x["id"] == p["id"])["stato"] == "annullata"


def test_TC16_dashboard_kpi_coerenti(client, admin):
    d = client.get("/api/dashboard", headers=admin).get_json()
    k = d["kpi"]
    assert k["biglietti_emessi"] == sum(x["biglietti"] for x in d["per_settore"])
    assert abs(k["incasso"] - sum(x["incasso"] for x in d["per_settore"])) < 0.01
    assert 0 < k["tasso_riempimento"] <= 100 and 0 < k["tasso_prevendita"] <= 100
    # il riempimento si calcola sulle repliche già andate in scena: è più alto della prevendita
    assert k["tasso_riempimento"] > k["tasso_prevendita"]
    assert abs(k["incasso"] - k["incasso_realizzato"] - k["incasso_prevendita"]) < 0.01
    assert 1 <= k["voto_medio"] <= 5


def test_TC17_amministrazione_ruoli(client, admin):
    utenti = client.get("/api/utenti", headers=admin).get_json()
    target = next(u for u in utenti if u["ruolo"] == "spettatore")
    assert client.patch(f"/api/utenti/{target['id']}", headers=admin, json={"ruolo": "operatore"}).get_json()["ruolo"] == "operatore"
    io = next(u for u in utenti if u["email"] == "admin@teatrogaribaldi.it")
    assert client.patch(f"/api/utenti/{io['id']}", headers=admin, json={"ruolo": "spettatore"}).status_code == 409


def test_TC18_errori_in_json(client):
    r = client.get("/api/inesistente")
    assert r.status_code == 404 and r.is_json
    r = client.post("/api/auth/login", data="non json", content_type="text/plain")
    assert r.status_code == 400 and "errore" in r.get_json()
