####################################################################################################################
#                                          Punto di ingresso dell'applicazione Flask                               #
####################################################################################################################

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from . import db
from .api import catalogo, dashboard, feedback, lista_attesa, prenotazioni, sicurezza, utenti
from .audit import configura_log
from .errors import registra_gestori

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# 1) Content Security Policy: solo risorse dello stesso sito. Niente script inline né script esterni

# 2) Un eventuale XSS non può eseguire codice

# 3) Il kit Bootstrap Italia è in frontend/vendor/

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",  # i componenti del kit impostano stili inline
    "font-src 'self' data:",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

INTESTAZIONI_SICUREZZA = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(
        DATABASE=os.environ.get("TG_DATABASE", str(BASE_DIR / "data" / "teatro.db")),
        LOG_DIR=os.environ.get("TG_LOG_DIR", str(BASE_DIR / "data" / "log")),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if config:
        app.config.update(config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.json.ensure_ascii = False
    app.logger.setLevel(logging.INFO)
    configura_log(app.config["LOG_DIR"])  # log di sicurezza in formato JSON (data/log/sicurezza.log)

    # API REST: tutte esposte sotto il prefisso /api
    
    for modulo in (utenti, catalogo, prenotazioni, lista_attesa, feedback, dashboard, sicurezza):
        app.register_blueprint(modulo.bp, url_prefix="/api")

    app.teardown_appcontext(db.close_db)
    registra_gestori(app)

    @app.after_request
    def intestazioni(risposta):
        for nome, valore in INTESTAZIONI_SICUREZZA.items():
            risposta.headers.setdefault(nome, valore)
        if request.path.startswith("/api/"):
            # dati personali e token non devono assolutamente finire nella cache del browser o dei proxy
            risposta.headers.setdefault("Cache-Control", "no-store")
        return risposta

    @app.get("/api/salute")
    def salute():
        return jsonify({"stato": "ok"})

    # FRONTEND: tutte le richieste non API servono i file statici (HTML, JS, CSS, immagini) della cartella frontend/

    @app.get("/")
    def home():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:percorso>")
    def statici(percorso):
        return send_from_directory(FRONTEND_DIR, percorso)

    return app


if __name__ == "__main__":
    # Il debugger di Werkzeug consente di eseguire codice dal browser:
    # si attiva solo esplicitamente con TG_DEBUG=1 e il server ascolta di default in locale
    debug = os.environ.get("TG_DEBUG") == "1"
    host = os.environ.get("TG_HOST", "127.0.0.1")
    create_app().run(debug=debug, host=host, port=int(os.environ.get("TG_PORT", "5000")))
