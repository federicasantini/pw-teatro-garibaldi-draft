"""Test delle misure di sicurezza a supporto della NIS2:
registro di audit, regole di rilevamento con avvisi, log di sicurezza, backup e ripristino."""

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from backend import backup, manutenzione, tempo

from .conftest import accedi_come, prima_replica_futura


def eventi(db, azione=None):
    sql, params = "SELECT * FROM registro_audit", ()
    if azione:
        sql, params = sql + " WHERE azione = ?", (azione,)
    return [dict(r) for r in db.execute(sql + " ORDER BY id", params)]


def avvisi(db, regola=None):
    sql = "SELECT * FROM avvisi" + (" WHERE regola = ?" if regola else "")
    return [dict(r) for r in db.execute(sql, (regola,) if regola else ())]


# ----------------------------------------------------------- registro di audit
def test_TC40_accessi_registrati_senza_segreti(client, db):
    accedi_come(client, "spettatore")
    client.post("/api/auth/login", json={"email": "anna.rinaldi@example.com", "password": "Sbagliata123"})
    ok, ko = eventi(db, "accesso.riuscito"), eventi(db, "accesso.fallito")
    assert ok[-1]["email"] == "anna.rinaldi@example.com" and ok[-1]["ip"] and ok[-1]["esito"] == "ok"
    assert ko[-1]["email"] == "anna.rinaldi@example.com" and ko[-1]["esito"] == "fallito"
    tutto = json.dumps(eventi(db))
    assert "Sbagliata123" not in tutto and "Spettatore2026!" not in tutto  # mai password nel registro


def test_TC41_azioni_dello_staff_registrate(client, db, operatore, admin):
    sid = client.post("/api/spettacoli", headers=operatore, json={"titolo": "Amleto", "genere": "prosa"}).get_json()["id"]
    quando = (tempo.adesso() + timedelta(days=210)).strftime("%Y-%m-%dT21:00")
    rid = client.post("/api/repliche", headers=operatore, json={"spettacolo_id": sid, "data_ora": quando}).get_json()["id"]
    client.patch(f"/api/repliche/{rid}", headers=operatore, json={"stato": "annullata"})
    client.get("/api/dashboard/export?dati=prenotazioni", headers=operatore)
    target = next(u for u in client.get("/api/utenti", headers=admin).get_json() if u["ruolo"] == "spettatore")
    client.patch(f"/api/utenti/{target['id']}", headers=admin, json={"ruolo": "operatore"})
    azioni = {e["azione"] for e in eventi(db)}
    assert {"catalogo.spettacolo_creato", "catalogo.replica_creata", "catalogo.replica_stato",
            "dati.export_csv", "account.ruolo_modificato"} <= azioni
    ruolo = eventi(db, "account.ruolo_modificato")[-1]
    assert json.loads(ruolo["dettagli"]) == {"utente": target["email"], "precedente": "spettatore", "nuovo": "operatore"}
    assert ruolo["email"] == "admin@teatrogaribaldi.it"


def test_TC42_registro_a_sola_aggiunta(client, db):
    accedi_come(client, "spettatore")
    with pytest.raises(sqlite3.IntegrityError, match="non può essere modificato"):
        db.execute("UPDATE registro_audit SET esito = 'ok'")
    with pytest.raises(sqlite3.IntegrityError, match="365 giorni"):
        db.execute("DELETE FROM registro_audit")
    # le voci oltre il periodo di conservazione si possono eliminare
    vecchia = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute("INSERT INTO registro_audit (quando, azione) VALUES (?, 'prova.vecchia')", (vecchia,))
    assert db.execute("DELETE FROM registro_audit WHERE azione = 'prova.vecchia'").rowcount == 1


def test_TC43_registro_consultabile_solo_dagli_amministratori(client, operatore, admin):
    assert client.get("/api/audit", headers=operatore).status_code == 403
    r = client.get("/api/audit?categoria=accesso&esito=ok", headers=admin).get_json()
    assert r and all(e["azione"].startswith("accesso.") and e["esito"] == "ok" for e in r)
    assert client.get("/api/audit?esito=boh", headers=admin).status_code == 422


def test_TC44_log_di_sicurezza_in_json(app, client):
    accedi_come(client, "operatore")
    with open(f"{app.config['LOG_DIR']}/sicurezza.log", encoding="utf-8") as f:
        righe = [json.loads(r) for r in f]
    assert any(r["azione"] == "accesso.riuscito" and r["email"] == "biglietteria@teatrogaribaldi.it" for r in righe)


# ------------------------------------------------------ regole di rilevamento
def test_TC45_forza_bruta_genera_avviso_e_avvisa_gli_admin(client, db):
    for _ in range(7):
        client.post("/api/auth/login", json={"email": "anna.rinaldi@example.com", "password": "Sbagliata123"})
    a = avvisi(db, "forza_bruta")
    assert len(a) == 1 and a[0]["soggetto"] == "anna.rinaldi@example.com"  # un solo avviso, non una per tentativo
    msg = client.get("/api/notifiche", headers=accedi_come(client, "admin")).get_json()
    assert any("Avviso di sicurezza" in m["oggetto"] for m in msg)


def test_TC46_password_spraying(client, db):
    for i in range(5):
        client.post("/api/auth/login", json={"email": f"vittima{i}@example.com", "password": "Estate2026"})
    a = avvisi(db, "password_spraying")
    assert len(a) == 1 and a[0]["gravita"] == "alta"


def test_TC47_nuovo_amministratore(client, db, admin):
    target = next(u for u in client.get("/api/utenti", headers=admin).get_json() if u["ruolo"] == "spettatore")
    client.patch(f"/api/utenti/{target['id']}", headers=admin, json={"ruolo": "operatore"})
    assert not avvisi(db, "nuovo_amministratore")
    client.patch(f"/api/utenti/{target['id']}", headers=admin, json={"ruolo": "admin"})
    a = avvisi(db, "nuovo_amministratore")
    assert len(a) == 1 and a[0]["soggetto"] == target["email"]


def test_TC48_accessi_negati_ripetuti(client, db, spettatore):
    for _ in range(10):
        assert client.get("/api/dashboard", headers=spettatore).status_code == 403
    assert len(eventi(db, "accesso.negato")) == 10
    assert len(avvisi(db, "accessi_negati")) == 1


def test_TC49_esportazioni_ripetute(client, db, operatore):
    for _ in range(5):
        client.get("/api/dashboard/export?dati=spettacoli", headers=operatore)
    assert len(avvisi(db, "esportazioni_ripetute")) == 1


def test_TC50_check_in_sospetti(client, db, operatore):
    for i in range(10):
        assert client.post("/api/prenotazioni/check-in", headers=operatore, json={"codice": f"TG-FALS{i:02d}"}).status_code == 404
    rifiuti = eventi(db, "prenotazioni.check_in")
    assert len(rifiuti) == 10 and all(e["esito"] == "negato" for e in rifiuti)
    assert len(avvisi(db, "check_in_sospetti")) == 1


def test_TC51_gestione_delle_avvisi(client, db, admin):
    for i in range(5):
        client.post("/api/auth/login", json={"email": f"x{i}@example.com", "password": "Estate2026"})
    aperta = client.get("/api/avvisi", headers=admin).get_json()[0]
    assert client.patch(f"/api/avvisi/{aperta['id']}", headers=admin, json={}).status_code == 422  # nota obbligatoria
    r = client.patch(f"/api/avvisi/{aperta['id']}", headers=admin, json={"note": "Test interno, falso positivo"})
    assert r.status_code == 200 and r.get_json()["gestito_il"]
    assert client.patch(f"/api/avvisi/{aperta['id']}", headers=admin, json={"note": "di nuovo"}).status_code == 409
    assert client.get("/api/avvisi", headers=admin).get_json() == []
    assert len(client.get("/api/avvisi?stato=tutte", headers=admin).get_json()) == 1
    assert eventi(db, "sistema.avviso_gestito")
    assert client.get("/api/avvisi", headers=accedi_come(client, "operatore")).status_code == 403


def test_TC52_eliminazione_account_senza_email_nel_registro(client, db, spettatore):
    client.delete("/api/auth/me", headers=spettatore, json={"password": "Spettatore2026!"})
    ultimo = eventi(db, "account.eliminato")[-1]
    assert ultimo["esito"] == "ok" and ultimo["email"] is None and ultimo["utente_id"]


# ----------------------------------------------------------- backup e ripristino
def test_TC53_backup_verifica_e_ripristino(app, tmp_path, db):
    cartella = tmp_path / "backup"
    file = backup.crea_backup(app.config["DATABASE"], str(cartella))
    assert file.exists() and file.with_suffix(".sha256").exists()
    assert backup.verifica_backup(file) == (True, "backup integro")
    prenotazioni_prima = db.execute("SELECT COUNT(*) FROM prenotazioni").fetchone()[0]

    db.execute("DELETE FROM feedback")  # "incidente": perdita di dati
    db.execute("DELETE FROM lista_attesa")
    db.execute("UPDATE prenotazioni SET stato = 'annullata'")

    copia = backup.ripristina(file, app.config["DATABASE"], str(cartella))
    dopo = sqlite3.connect(app.config["DATABASE"])
    assert dopo.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] > 0
    assert dopo.execute("SELECT COUNT(*) FROM prenotazioni WHERE stato <> 'annullata'").fetchone()[0] > 0
    assert dopo.execute("SELECT COUNT(*) FROM prenotazioni").fetchone()[0] == prenotazioni_prima
    assert dopo.execute("SELECT COUNT(*) FROM registro_audit WHERE azione = 'sistema.backup_ripristinato'").fetchone()[0] == 1
    dopo.close()
    # il database sostituito è stato conservato: anche il ripristino si può annullare
    vecchio = sqlite3.connect(copia)
    assert vecchio.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 0
    vecchio.close()


def test_TC54_backup_alterato_non_si_ripristina(app, tmp_path):
    file = backup.crea_backup(app.config["DATABASE"], str(tmp_path / "b"))
    with open(file, "r+b") as f:
        f.seek(5000)
        f.write(b"\x00alterato\x00")
    ok, motivo = backup.verifica_backup(file)
    assert not ok and "SHA-256" in motivo
    with pytest.raises(ValueError, match="Ripristino annullato"):
        backup.ripristina(file, app.config["DATABASE"], str(tmp_path / "b"))


def test_TC55_rotazione_dei_backup(app, tmp_path):
    cartella = str(tmp_path / "b")
    for _ in range(4):
        backup.crea_backup(app.config["DATABASE"], cartella, conserva=2)
    assert len(backup.elenco(cartella)) == 2
    assert len(list((tmp_path / "b").glob("*.sha256"))) == 2


def test_TC56_ripristino_richiede_conferma_da_riga_di_comando(app, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TG_LOG_DIR", str(tmp_path / "log"))
    file = backup.crea_backup(app.config["DATABASE"], str(tmp_path / "b"))
    assert backup.main(["--database", app.config["DATABASE"], "ripristina", str(file)]) == 2
    assert "--conferma" in capsys.readouterr().out


def test_TC57_manutenzione_rispetta_la_conservazione_del_registro(app, client, db):
    accedi_come(client, "spettatore")
    vecchia = (tempo.adesso() - timedelta(days=500)).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute("INSERT INTO registro_audit (quando, azione) VALUES (?, 'prova.vecchia')", (vecchia,))
    with app.app_context():
        assert manutenzione.esegui()["audit_scaduto"] == 1
    assert eventi(db, "accesso.riuscito")  # le voci recenti restano


def test_TC58_il_check_in_riuscito_e_registrato(client, db, spettatore, orologio):
    rep = prima_replica_futura(client)
    p = client.post("/api/prenotazioni", headers=spettatore, json={"replica_id": rep["id"], "settore_id": 1, "num_posti": 1}).get_json()
    orologio(datetime.fromisoformat(rep["data_ora"]) - timedelta(minutes=10))
    client.post("/api/prenotazioni/check-in", headers=accedi_come(client, "operatore"), json={"codice": p["codice"]})
    e = eventi(db, "prenotazioni.check_in")[-1]
    assert e["esito"] == "ok" and e["oggetto"] == f"prenotazione:{p['id']}"
