####################################################################################################################
#                                        Rigenerazione delle schermate                                              #
####################################################################################################################

# Rigenera le schermate di docs/screenshot/ su un database dimostrativo appena creato

# Uso (dalla cartella del progetto, con Playwright e Chromium installati):

#     python scripts/screenshot.py

# Lo script crea un database temporaneo con i dati dimostrativi, avvia il server su una porta libera,
# esegue i percorsi principali (spettatore, operatore, amministratore) e salva le schermate a
# risoluzione 1,5x (smartphone 3x). Il database reale in data/ non viene toccato

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

RADICE = Path(__file__).resolve().parent.parent
USCITA = RADICE / "docs" / "screenshot"
SPETTATORE = ("anna.rinaldi@example.com", "Spettatore2026!")
OPERATORE = ("biglietteria@teatrogaribaldi.it", "Operatore2026!")
ADMIN = ("admin@teatrogaribaldi.it", "Admin2026!")


def porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def chiama(base: str, metodo: str, percorso: str, dati=None, token: str | None = None):
    # base è sempre http://127.0.0.1:<porta> del server avviato dallo script
    req = urllib.request.Request(base + percorso,  # noqa: S310 method=metodo,
                                 data=json.dumps(dati).encode() if dati is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:  # noqa: S310
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    env = {**os.environ, "TG_DATABASE": str(tmp / "teatro.db"), "TG_LOG_DIR": str(tmp / "log"),
           "TG_PORT": str(porta_libera())}
    subprocess.run([sys.executable, "-m", "backend.seed", env["TG_DATABASE"]],  # noqa: S603
                   cwd=RADICE, env=env, check=True)
    server = subprocess.Popen([sys.executable, "-m", "backend.app"], cwd=RADICE, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{env['TG_PORT']}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/index.html")  # noqa: S310
            break
        except OSError:
            time.sleep(0.2)
    USCITA.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            esegui(browser, p, base, env["TG_DATABASE"])
            browser.close()
    finally:
        server.terminate()


def esegui(browser, p, base: str, db: str) -> None:
    def contesto():
        return browser.new_context(viewport={"width": 1280, "height": 860}, device_scale_factor=1.5,
                                   locale="it-IT", timezone_id="Europe/Rome")

    def foto(page, nome, **kw):
        page.wait_for_timeout(400)
        page.screenshot(path=str(USCITA / f"{nome}.png"), **kw)

    def accedi(page, credenziali):
        page.goto(base + "/accedi.html")
        page.fill("#l-email", credenziali[0])
        page.fill("#l-password", credenziali[1])
        page.click("#form-login button[type=submit]")
        page.wait_for_url(lambda u: "accedi.html" not in u)
        page.wait_for_load_state("networkidle")

    # ------------------------------------------------------------- spettatore
    ctx = contesto()
    page = ctx.new_page()
    page.goto(base + "/index.html")
    page.wait_for_load_state("networkidle")
    foto(page, "01_cartellone")

    page.goto(base + "/accedi.html")
    page.fill("#l-email", SPETTATORE[0])
    page.fill("#l-password", SPETTATORE[1])
    foto(page, "02_accesso")
    page.click("#form-login button[type=submit]")
    page.wait_for_url(lambda u: "accedi.html" not in u)
    page.wait_for_load_state("networkidle")

    page.goto(base + "/spettacolo.html?id=4")
    page.wait_for_load_state("networkidle")
    page.click("#repliche button[data-id]:not([disabled])")
    page.wait_for_selector("#settori input[name=settore]")
    page.check("#settori input[name=settore] >> nth=0")
    page.select_option("#num-posti", "2")
    page.select_option("#tariffa", label=page.locator("#tariffa option", has_text="Under 26").first.inner_text())
    foto(page, "03_prenotazione", full_page=True)
    page.click("#conferma")
    page.wait_for_selector("#esito .alert-success")
    page.evaluate("document.getElementById('esito').scrollIntoView({block: 'center'})")
    foto(page, "04_conferma")

    page.goto(base + "/area-personale.html")
    page.wait_for_load_state("networkidle")
    foto(page, "05_area_personale")

    page.goto(base + "/spettacolo.html?id=2")
    page.wait_for_load_state("networkidle")
    page.click("[data-bs-target='#pannello-feedback']")
    page.wait_for_selector("#form-feedback", state="visible")
    page.click("label[for='voto-5']")
    page.fill("#form-feedback textarea", "Regia coraggiosa e attori in stato di grazia.")
    page.evaluate("document.getElementById('form-feedback').scrollIntoView({block: 'center'})")
    foto(page, "06_recensioni")
    page.click("#form-feedback button[type=submit]")
    page.wait_for_timeout(800)
    page.locator("#recensioni").scroll_into_view_if_needed()
    foto(page, "06b_feedback_inviato")
    ctx.close()

    # Una replica che inizia tra un'ora, per mostrare il check-in in finestra
    inizio = (datetime.now(ZoneInfo("Europe/Rome")) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO repliche (spettacolo_id, sala_id, data_ora) VALUES (6, 1, ?)", (inizio,))
    replica = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    _, sess = chiama(base, "POST", "/api/auth/login", {"email": SPETTATORE[0], "password": SPETTATORE[1]})
    token = sess["token"]
    _, pren = chiama(base, "POST", "/api/prenotazioni",
                     {"replica_id": replica, "settore_id": 1, "num_posti": 2, "tariffa_id": 1}, token)
    codice = pren["codice"]

    # ------------------------------------------------------------- operatore
    ctx = contesto()
    page = ctx.new_page()
    accedi(page, OPERATORE)
    page.goto(base + "/gestione.html")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    foto(page, "07_dashboard", full_page=True)

    page.click("[data-scheda=checkin]")
    page.fill("#codice", codice)
    page.click("#form-checkin button[type=submit]")
    page.wait_for_selector("#esito-checkin .alert, #esito-checkin [role]")
    foto(page, "08_checkin")
    page.fill("#codice", codice)
    page.click("#form-checkin button[type=submit]")
    page.wait_for_timeout(600)
    foto(page, "09_checkin_duplicato")

    page.click("[data-scheda=spettacoli]")
    page.wait_for_selector("[data-modifica='6']")
    page.click("[data-modifica='6']")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    foto(page, "10_gestione_spettacoli")

    page.click("[data-scheda=repliche]")
    page.wait_for_timeout(500)
    sel = page.locator("#pannello-repliche select").first
    sel.select_option(label=sel.locator("option", has_text="Pinocchio").first.inner_text())
    page.wait_for_timeout(300)
    foto(page, "11_gestione_repliche")
    ctx.close()

    # ------------------------------------------------------------- amministratore
    ctx = contesto()
    page = ctx.new_page()
    accedi(page, ADMIN)
    # Tentativi falliti simulati: forza bruta su un account e password spraying su più account
    for _ in range(6):
        chiama(base, "POST", "/api/auth/login", {"email": SPETTATORE[0], "password": "sbagliata"})
    for i in range(5):
        chiama(base, "POST", "/api/auth/login", {"email": f"utente{i}@example.com", "password": "Estate2026"})
    page.goto(base + "/gestione.html")
    page.wait_for_load_state("networkidle")
    page.click("[data-scheda=utenti]")
    page.wait_for_timeout(600)
    foto(page, "12_utenti")
    page.click("[data-scheda=sicurezza]")
    page.wait_for_timeout(800)
    foto(page, "14_sicurezza")
    ctx.close()

    # ------------------------------------------------------------- smartphone
    ctx = browser.new_context(**p.devices["iPhone 13"], locale="it-IT", timezone_id="Europe/Rome")
    page = ctx.new_page()
    page.goto(base + "/index.html")
    page.wait_for_load_state("networkidle")
    foto(page, "13_mobile")
    ctx.close()


if __name__ == "__main__":
    main()
