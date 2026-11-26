####################################################################################################################
#                    Gestione uniforme degli errori dell'API (risposte JSON con codice HTTP)                       #
####################################################################################################################

from flask import jsonify


class ApiError(Exception):
    def __init__(self, status: int, messaggio: str, dettagli: dict | None = None,
                 headers: dict | None = None):
        super().__init__(messaggio)
        self.status = status
        self.messaggio = messaggio
        self.dettagli = dettagli or {}
        self.headers = headers or {}


def registra_gestori(app):
    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        corpo = {"errore": err.messaggio}
        if err.dettagli:
            corpo["dettagli"] = err.dettagli
        return jsonify(corpo), err.status, err.headers

    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"errore": "Risorsa non trovata"}), 404

    @app.errorhandler(405)
    def _method(_e):
        return jsonify({"errore": "Metodo non consentito"}), 405

    @app.errorhandler(500)
    def _server(_e):
        return jsonify({"errore": "Errore interno del server"}), 500
