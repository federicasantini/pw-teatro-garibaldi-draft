"""Test delle correzioni e delle funzionalità aggiunte dopo la prima revisione:
validazione dei tipi, conflitti di sala, stati delle repliche, finestra e
concorrenza del check-in, overbooking concorrente, sicurezza, listini e tariffe,
GDPR, lista d'attesa, notifiche, QR code, export CSV e manutenzione."""
import hashlib
import threading
from datetime import datetime, timedelta

import pytest

from backend import manutenzione, tempo
from backend.seed import seed

from .conftest import accedi_come, disponibilita_settore, nuovo_utente, prima_replica_futura

PAGINE = ("index.html", "spettacolo.html", "accedi.html", "area-personale.html", "gestione.html", "privacy.html",
          "accessibilita.html")


def crea_replica(client, operatore, spettacolo_id, quando: datetime, **extra):
    return client.post("/api/repliche", headers=operatore,
                       json={"spettacolo_id": spettacolo_id, "data_ora": quando.strftime("%Y-%m-%dT%H:%M"), **extra})


def riempi_replica(db, replica_id, lascia_liberi=0):
    """Occupa (direttamente sul DB) tutti i posti della replica tranne `lascia_liberi`."""
    utente = db.execute("SELECT id FROM utenti WHERE email LIKE '%@example.com' AND ruolo = 'spettatore' "
                        "ORDER BY id DESC LIMIT 1").fetchone()["id"]
    ora = tempo.istante()
    settori = db.execute("SELECT settore_id, posti_totali - posti_occupati AS liberi FROM v_occupazione "
                         "WHERE replica_id = ? ORDER BY settore_id", (replica_id,)).fetchall()
    for i, s in enumerate(settori):
        da_occupare = s["liberi"] - (lascia_liberi if i == 0 else 0)
        while da_occupare > 0:
            n = min(6, da_occupare)
            db.execute("INSERT INTO prenotazioni (codice, utente_id, replica_id, settore_id, tariffa_id, num_posti, "
                       "prezzo_unitario_cent, importo_cent, data_prenotazione) VALUES (?, ?, ?, ?, 1, ?, 0, 0, ?)",
                       (f"TG-F{replica_id}{s['settore_id']}{da_occupare:03d}", utente, replica_id, s["settore_id"], n, ora))
            da_occupare -= n


# ------------------------------------------------------------ 1. correzioni
@pytest.mark.parametrize("percorso,corpo", [
    ("/api/auth/login", {"email": 5, "password": "x"}),
    ("/api/auth/login", {"email": "a@b.it", "password": ["x"]}),
    ("/api/auth/registrazione", {"nome": 1, "cognome": "a", "email": "z@z.it", "password": "abcd1234",
                                 "consenso_privacy": True}),
    ("/api/auth/registrazione", {"nome": "a", "cognome": "b", "email": {"x": 1}, "password": "abcd1234",
                                 "consenso_privacy": True}),
])
def test_TC19_tipi_non_validi_danno_422_non_500(client, percorso, corpo):
    assert client.post(percorso, json=corpo).status_code == 422


def test_TC19b_tipi_non_validi_su_rotte_protette(client, operatore):
    assert client.post("/api/prenotazioni/check-in", headers=operatore, json={"codice": 123}).status_code == 422
    assert client.post("/api/spettacoli", headers=operatore, json={"titolo": 42, "genere": "prosa"}).status_code == 422
    assert client.post("/api/spettacoli", headers=operatore, json={"titolo": "X", "genere": ["prosa"]}).status_code == 422
    assert client.post("/api/feedback", headers=operatore, json={"spettacolo_id": 1, "voto": 3, "commento": 7}).status_code == 422


def test_TC20_repliche_sovrapposte_nella_stessa_sala(client, operatore):
    quando = (tempo.adesso() + timedelta(days=200)).replace(hour=17, minute=0, second=0)
    assert crea_replica(client, operatore, 1, quando).status_code == 201  # La locandiera: 120 minuti
    # 30 minuti dopo: lo spettacolo precedente è ancora in scena
    r = crea_replica(client, operatore, 2, quando + timedelta(minutes=30))
    assert r.status_code == 409 and "replica_in_conflitto" in r.get_json()["dettagli"]
    # un'ora prima: finirebbe dopo l'inizio dell'altra
    assert crea_replica(client, operatore, 2, quando - timedelta(minutes=60)).status_code == 409
    # fine (19:00) + 60 minuti di cambio scena: alle 20:00 la sala è libera
    assert crea_replica(client, operatore, 2, quando + timedelta(hours=3)).status_code == 201


def test_TC21_transizioni_di_stato_della_replica(client, operatore, orologio):
    quando = (tempo.adesso() + timedelta(days=150)).replace(hour=21, minute=0, second=0)
    rid = crea_replica(client, operatore, 1, quando).get_json()["id"]
    # una replica futura non può essere conclusa
    assert client.patch(f"/api/repliche/{rid}", headers=operatore, json={"stato": "conclusa"}).status_code == 409
    assert client.patch(f"/api/repliche/{rid}", headers=operatore, json={"stato": "annullata"}).status_code == 200
    # annullata è uno stato finale
    r = client.patch(f"/api/repliche/{rid}", headers=operatore, json={"stato": "programmata"})
    assert r.status_code == 409 and "Transizione non consentita" in r.get_json()["errore"]
    # dopo l'annullamento la stessa data si può riprogrammare
    assert crea_replica(client, operatore, 1, quando).status_code == 201
    # conclusione ammessa solo a spettacolo iniziato
    rid2 = crea_replica(client, operatore, 1, quando + timedelta(days=2)).get_json()["id"]
    orologio(quando + timedelta(days=2, hours=3))
    op = accedi_come(client, "operatore")
    assert client.patch(f"/api/repliche/{rid2}", headers=op, json={"stato": "conclusa"}).status_code == 200
    assert client.patch(f"/api/repliche/{rid2}", headers=op, json={"stato": "annullata"}).status_code == 409


def test_TC22_check_in_solo_nella_finestra_della_replica(client, spettatore, orologio):
    rep = prima_replica_futura(client)
    inizio = datetime.fromisoformat(rep["data_ora"])
    p = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1}).get_json()
    # il giorno prima: biglietto per un'altra data
    orologio(inizio - timedelta(days=1))
    r = client.post("/api/prenotazioni/check-in", headers=accedi_come(client, "operatore"), json={"codice": p["codice"]})
    assert r.status_code == 409 and "altra data" in r.get_json()["errore"]
    # a spettacolo finito: biglietto scaduto
    orologio(inizio + timedelta(hours=5))
    r = client.post("/api/prenotazioni/check-in", headers=accedi_come(client, "operatore"), json={"codice": p["codice"]})
    assert r.status_code == 409 and "scaduto" in r.get_json()["errore"]
    # 2 ore prima dell'inizio il check-in è aperto
    orologio(inizio - timedelta(hours=2))
    r = client.post("/api/prenotazioni/check-in", headers=accedi_come(client, "operatore"), json={"codice": p["codice"]})
    assert r.status_code == 200


def test_TC23_check_in_concorrente_convalida_una_sola_volta(app, client, spettatore, orologio):
    rep = prima_replica_futura(client)
    p = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 2}).get_json()
    orologio(datetime.fromisoformat(rep["data_ora"]) - timedelta(minutes=20))
    operatore = accedi_come(client, "operatore")
    esiti, barriera = [], threading.Barrier(8)

    def varco():
        c = app.test_client()
        barriera.wait()
        esiti.append(c.post("/api/prenotazioni/check-in", headers=operatore, json={"codice": p["codice"]}).status_code)

    thread = [threading.Thread(target=varco) for _ in range(8)]
    for t in thread:
        t.start()
    for t in thread:
        t.join()
    assert sorted(esiti) == [200] + [409] * 7


# ------------------------------------------------------------- 2. sicurezza
def test_TC24_token_salvato_solo_come_hash(client, db):
    token = client.post("/api/auth/login", json={"email": "anna.rinaldi@example.com",
                                                 "password": "Spettatore2026!"}).get_json()["token"]
    righe = [r["token_hash"] for r in db.execute("SELECT token_hash FROM sessioni")]
    assert token not in righe
    assert hashlib.sha256(token.encode()).hexdigest() in righe


def test_TC25_blocco_dopo_troppi_tentativi_falliti(client):
    credenziali = {"email": "anna.rinaldi@example.com", "password": "sbagliata1"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=credenziali).status_code == 401
    r = client.post("/api/auth/login", json={**credenziali, "password": "Spettatore2026!"})
    assert r.status_code == 429 and r.headers["Retry-After"]
    # gli altri account non sono bloccati
    assert client.post("/api/auth/login", json={"email": "admin@teatrogaribaldi.it",
                                                "password": "Admin2026!"}).status_code == 200


def test_TC25b_il_blocco_scade_e_il_successo_azzera(client, orologio):
    credenziali = {"email": "anna.rinaldi@example.com", "password": "sbagliata1"}
    for _ in range(5):
        client.post("/api/auth/login", json=credenziali)
    orologio(tempo.adesso() + timedelta(minutes=16))
    assert client.post("/api/auth/login", json={**credenziali, "password": "Spettatore2026!"}).status_code == 200


def test_TC26_intestazioni_di_sicurezza(client):
    for percorso in ("/", "/api/spettacoli"):
        h = client.get(percorso).headers
        assert "script-src 'self'" in h["Content-Security-Policy"]
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["X-Frame-Options"] == "DENY"
    assert client.get("/api/spettacoli").headers["Cache-Control"] == "no-store"


def test_TC26b_pagine_senza_script_inline(client):
    """La CSP vieta gli script inline: tutte le pagine devono caricare file .js esterni."""
    import re
    for pagina in PAGINE:
        html = client.get(f"/{pagina}").get_data(as_text=True)
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), pagina
        assert not re.search(r"\son[a-z]+=", html), pagina


def test_TC26c_design_kit_servito_localmente(client):
    """Bootstrap Italia (CSS, JS, icone, font) è servito dal sito stesso: nessuna
    risorsa esterna, coerente con la CSP e senza trasferire dati a terzi."""
    import re
    for pagina in PAGINE:
        html = client.get(f"/{pagina}").get_data(as_text=True)
        assert 'href="vendor/bootstrap-italia/css/bootstrap-italia.min.css"' in html, pagina
        assert 'src="vendor/bootstrap-italia/js/bootstrap-italia.bundle.min.js"' in html, pagina
        assert 'href="vendor/design-tokens-italia/variables.css"' in html, pagina
        assert not re.search(r'(?:src|href)="(?:https?:)?//', html), pagina
    for risorsa in ("vendor/bootstrap-italia/css/bootstrap-italia.min.css",
                    "vendor/bootstrap-italia/js/bootstrap-italia.bundle.min.js",
                    "vendor/bootstrap-italia/svg/sprites.svg",
                    "vendor/design-tokens-italia/variables.css",
                    "vendor/bootstrap-italia/fonts/Titillium_Web/titillium-web-v10-latin-ext_latin-regular.woff2",
                    "css/fonts.css"):
        assert client.get(f"/{risorsa}").status_code == 200, risorsa
    assert "font-src 'self'" in client.get("/").headers["Content-Security-Policy"]


def test_TC27_orari_coerenti_nel_fuso_del_teatro(client, spettatore, db, orologio):
    fisso = (tempo.adesso() + timedelta(days=1)).replace(hour=11, minute=22, second=33)
    orologio(fisso)
    h = accedi_come(client, "spettatore")
    rep = prima_replica_futura(client)
    p = client.post("/api/prenotazioni", headers=h, json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1}).get_json()
    assert p["data_prenotazione"] == fisso.strftime("%Y-%m-%dT%H:%M:%S")
    sessione = db.execute("SELECT creata_il, scade_il FROM sessioni ORDER BY creata_il DESC LIMIT 1").fetchone()
    assert sessione["creata_il"] == fisso.strftime("%Y-%m-%dT%H:%M:%S")
    assert sessione["scade_il"] == (fisso + timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------- 3. modello dati
def test_TC28_limite_posti_per_utente_e_replica(client, spettatore):
    rep = prima_replica_futura(client)
    ok = client.post("/api/prenotazioni", headers=spettatore, json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 4})
    assert ok.status_code == 201
    r = client.post("/api/prenotazioni", headers=spettatore, json={"replica_id": rep["id"], "settore_id": 2, "num_posti": 3})
    assert r.status_code == 409 and r.get_json()["dettagli"]["posti_ancora_prenotabili"] == 2
    assert client.post("/api/prenotazioni", headers=spettatore,
                       json={"replica_id": rep["id"], "settore_id": 2, "num_posti": 2}).status_code == 201
    # annullando, i posti tornano disponibili per lo stesso utente
    assert client.delete(f"/api/prenotazioni/{ok.get_json()['id']}", headers=spettatore).status_code == 204
    assert client.post("/api/prenotazioni", headers=spettatore,
                       json={"replica_id": rep["id"], "settore_id": 2, "num_posti": 4}).status_code == 201


def test_TC29_tariffe_ridotte_in_centesimi(client, spettatore, db):
    tariffe = {t["codice"]: t for t in client.get("/api/tariffe").get_json()}
    assert tariffe["INTERO"]["sconto_pct"] == 0 and tariffe["UNDER26"]["richiede_documento"] == 1
    rep = prima_replica_futura(client)
    loggione = disponibilita_settore(client, rep["id"], "Loggione")  # 15,00 €
    p = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rep["id"], "settore_id": loggione["settore_id"], "num_posti": 3,
                          "tariffa_id": tariffe["UNDER26"]["id"]}).get_json()
    assert p["prezzo_unitario"] == 10.5 and p["importo_totale"] == 31.5 and p["tariffa"] == "Under 26"
    riga = db.execute("SELECT prezzo_unitario_cent, importo_cent FROM prenotazioni WHERE id = ?", (p["id"],)).fetchone()
    assert (riga["prezzo_unitario_cent"], riga["importo_cent"]) == (1050, 3150)
    assert client.post("/api/prenotazioni", headers=spettatore,
                       json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1, "tariffa_id": 999}).status_code == 422


def test_TC30_listino_specifico_della_replica(client, operatore, spettatore):
    sale = client.get("/api/sale").get_json()
    platea = next(s for s in sale[0]["settori"] if s["nome"] == "Platea")
    quando = (tempo.adesso() + timedelta(days=120)).replace(hour=21, minute=0)
    r = crea_replica(client, operatore, 3, quando, prezzi={str(platea["id"]): "39,90"})
    assert r.status_code == 201
    rid = r.get_json()["id"]
    disp = {s["settore"]: s["prezzo"] for s in client.get(f"/api/repliche/{rid}/disponibilita").get_json()["settori"]}
    assert disp == {"Platea": 39.9, "Palchi": 22.0, "Loggione": 15.0}
    p = client.post("/api/prenotazioni", headers=spettatore,
                    json={"replica_id": rid, "settore_id": platea["id"], "num_posti": 2}).get_json()
    assert p["importo_totale"] == 79.8
    assert crea_replica(client, operatore, 3, quando + timedelta(days=1), prezzi={"999": 10}).status_code == 422
    assert crea_replica(client, operatore, 3, quando + timedelta(days=1), prezzi={str(platea["id"]): "gratis"}).status_code == 422


def test_TC31_seed_non_sovrascrive_un_database_esistente(app):
    with pytest.raises(FileExistsError):
        seed(app.config["DATABASE"])
    seed(app.config["DATABASE"], sovrascrivi=True)  # con conferma esplicita è consentito


# -------------------------------------------------------- 4. funzionalità
def test_TC32_qr_code_del_biglietto(client, spettatore):
    pren = client.get("/api/prenotazioni?mie=1", headers=spettatore).get_json()[0]
    r = client.get(f"/api/prenotazioni/{pren['id']}/qr", headers=spettatore)
    assert r.status_code == 200 and r.mimetype == "image/svg+xml" and b"<svg" in r.data
    assert client.get(f"/api/prenotazioni/{pren['id']}/qr", headers=nuovo_utente(client)).status_code == 403
    assert client.get(f"/api/prenotazioni/{pren['id']}/qr", headers=accedi_come(client, "operatore")).status_code == 200


def test_TC33_notifiche_di_conferma_e_annullamento(client, spettatore, operatore):
    rep = prima_replica_futura(client)
    p = client.post("/api/prenotazioni", headers=spettatore, json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1}).get_json()
    msg = client.get("/api/notifiche", headers=spettatore).get_json()
    assert msg[0]["oggetto"].startswith("Prenotazione confermata") and p["codice"] in msg[0]["corpo"]
    assert client.patch(f"/api/repliche/{rep['id']}", headers=operatore, json={"stato": "annullata"}).status_code == 200
    assert client.get("/api/notifiche", headers=spettatore).get_json()[0]["oggetto"].startswith("Replica annullata")


def test_TC34_lista_d_attesa(client, operatore, db):
    quando = (tempo.adesso() + timedelta(days=90)).replace(hour=21, minute=0)
    rid = crea_replica(client, operatore, 2, quando).get_json()["id"]
    riempi_replica(db, rid, lascia_liberi=1)
    primo, secondo = nuovo_utente(client), nuovo_utente(client)
    # con posti sufficienti non ci si iscrive: si prenota
    assert client.post(f"/api/repliche/{rid}/lista-attesa", headers=primo, json={"num_posti": 1}).status_code == 409
    r1 = client.post(f"/api/repliche/{rid}/lista-attesa", headers=primo, json={"num_posti": 4})
    r2 = client.post(f"/api/repliche/{rid}/lista-attesa", headers=secondo, json={"num_posti": 2})
    assert (r1.status_code, r1.get_json()["posizione"], r2.get_json()["posizione"]) == (201, 1, 2)
    assert client.post(f"/api/repliche/{rid}/lista-attesa", headers=primo, json={"num_posti": 2}).status_code == 409
    assert len(client.get("/api/lista-attesa", headers=primo).get_json()) == 1

    # la biglietteria annulla una prenotazione da 2 posti: 3 liberi, il primo (4) non rientra, il secondo (2) sì
    pid = db.execute("SELECT id FROM prenotazioni WHERE replica_id = ? AND num_posti = 2 AND stato = 'confermata' LIMIT 1",
                     (rid,)).fetchone()
    if pid is None:  # nessun blocco da 2: si crea lo scenario annullando un blocco da 6 → 7 liberi
        pid = db.execute("SELECT id FROM prenotazioni WHERE replica_id = ? AND num_posti = 6 LIMIT 1", (rid,)).fetchone()
    assert client.delete(f"/api/prenotazioni/{pid['id']}", headers=operatore).status_code == 204
    avvisi = lambda h: [m for m in client.get("/api/notifiche", headers=h).get_json() if "liberati" in m["oggetto"]]  # noqa: E731
    assert avvisi(secondo)
    # chi prenota esce dalla lista d'attesa
    sett = db.execute("SELECT settore_id FROM v_occupazione WHERE replica_id = ? AND posti_totali > posti_occupati",
                      (rid,)).fetchone()["settore_id"]
    assert client.post("/api/prenotazioni", headers=secondo, json={"replica_id": rid, "settore_id": sett, "num_posti": 2}).status_code == 201
    assert client.get("/api/lista-attesa", headers=secondo).get_json() == []
    assert client.delete(f"/api/repliche/{rid}/lista-attesa", headers=primo).status_code == 204


def test_TC35_esportazione_dati_personali(client, spettatore):
    r = client.get("/api/auth/me/dati", headers=spettatore)
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    dati = r.get_json()
    assert dati["profilo"]["email"] == "anna.rinaldi@example.com"
    assert {p["codice"] for p in dati["prenotazioni"]} >= {"TG-DEMO01", "TG-DEMO03"}
    assert dati["feedback"] and "password_hash" not in dati["profilo"]


def test_TC36_cancellazione_account(client, spettatore, operatore, db):
    assert client.delete("/api/auth/me", headers=spettatore, json={"password": "errata"}).status_code == 403
    assert client.delete("/api/auth/me", headers=spettatore, json={"password": "Spettatore2026!"}).status_code == 204
    # sessione invalidata, login impossibile, dati identificativi rimossi
    assert client.get("/api/auth/me", headers=spettatore).status_code == 401
    assert client.post("/api/auth/login", json={"email": "anna.rinaldi@example.com", "password": "Spettatore2026!"}).status_code == 401
    assert not db.execute("SELECT 1 FROM utenti WHERE email = 'anna.rinaldi@example.com'").fetchone()
    # prenotazione futura annullata (posti liberati), storico anonimo conservato
    stati = dict(db.execute("SELECT codice, stato FROM prenotazioni WHERE codice LIKE 'TG-DEMO%'").fetchall())
    assert stati == {"TG-DEMO01": "utilizzata", "TG-DEMO02": "utilizzata", "TG-DEMO03": "annullata"}
    rec = client.get("/api/spettacoli/1/feedback").get_json()
    assert not any("Anna" in f["autore"] for f in rec)
    assert all(u["email"] != "anna.rinaldi@example.com" for u in client.get("/api/utenti", headers=accedi_come(client, "admin")).get_json())


def test_TC36b_l_unico_admin_non_si_elimina(client, admin):
    assert client.delete("/api/auth/me", headers=admin, json={"password": "Admin2026!"}).status_code == 409


def test_TC37_dashboard_csv(client, operatore, spettatore):
    r = client.get("/api/dashboard/export?dati=spettacoli", headers=operatore)
    testo = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "text/csv" and testo.startswith("﻿Titolo;Genere")
    assert "La traviata;lirica" in testo
    r = client.get("/api/dashboard/export?dati=prenotazioni", headers=operatore).get_data(as_text=True)
    assert "TG-DEMO01" in r and "anna.rinaldi" not in r  # nessun dato personale
    assert client.get("/api/dashboard/export?dati=utenti", headers=operatore).status_code == 422
    assert client.get("/api/dashboard/export", headers=spettatore).status_code == 403


def test_TC38_manutenzione_periodica(app, client, spettatore, db, orologio):
    rep = prima_replica_futura(client)
    client.post("/api/prenotazioni", headers=spettatore, json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1})
    inizio = datetime.fromisoformat(rep["data_ora"])
    orologio(inizio - timedelta(hours=20))
    with app.app_context():
        esito = manutenzione.esegui()
        assert esito["promemoria"] > 0
        assert esito["sessioni_scadute"] >= 1  # le sessioni aperti all'inizio del test sono scadute
        assert manutenzione.esegui()["promemoria"] == 0  # nessun doppio invio
    assert db.execute("SELECT COUNT(*) FROM notifiche WHERE oggetto LIKE 'Promemoria%' AND utente_id = "
                      "(SELECT id FROM utenti WHERE email = 'anna.rinaldi@example.com')").fetchone()[0] == 1
    orologio(inizio + timedelta(hours=4))
    with app.app_context():
        esito = manutenzione.esegui()
    assert esito["repliche_concluse"] >= 1
    assert db.execute("SELECT stato FROM repliche WHERE id = ?", (rep["id"],)).fetchone()[0] == "conclusa"


# ----------------------------------------------------------- 5. concorrenza
def test_TC39_overbooking_con_richieste_concorrenti(app, client, db):
    """La garanzia anti-overbooking verificata davvero: 12 utenti prenotano in
    parallelo gli ultimi 5 posti di un settore. Devono riuscirci esattamente 5."""
    rep = prima_replica_futura(client)
    settore = disponibilita_settore(client, rep["id"], "Platea")
    da_occupare = settore["posti_disponibili"] - 5
    ora = tempo.istante()
    utente = db.execute("SELECT id FROM utenti WHERE ruolo = 'spettatore' ORDER BY id DESC LIMIT 1").fetchone()[0]
    i = 0
    while da_occupare > 0:
        n = min(6, da_occupare)
        db.execute("INSERT INTO prenotazioni (codice, utente_id, replica_id, settore_id, tariffa_id, num_posti, "
                   "prezzo_unitario_cent, importo_cent, data_prenotazione) VALUES (?, ?, ?, ?, 1, ?, 0, 0, ?)",
                   (f"TG-RIEM{i:03d}", utente, rep["id"], settore["settore_id"], n, ora))
        da_occupare -= n
        i += 1
    utenti = [nuovo_utente(client) for _ in range(12)]
    esiti, barriera = [], threading.Barrier(len(utenti))

    def prenota(h):
        c = app.test_client()
        barriera.wait()
        esiti.append(c.post("/api/prenotazioni", headers=h, json={
            "replica_id": rep["id"], "settore_id": settore["settore_id"], "num_posti": 1}).status_code)

    thread = [threading.Thread(target=prenota, args=(h,)) for h in utenti]
    for t in thread:
        t.start()
    for t in thread:
        t.join()
    assert esiti.count(201) == 5 and esiti.count(409) == 7
    finale = disponibilita_settore(client, rep["id"], "Platea")
    assert finale["posti_disponibili"] == 0 and finale["posti_occupati"] == finale["posti_totali"]
