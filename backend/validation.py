####################################################################################################################
#                                      Validazione dei dati in ingresso                                        #
####################################################################################################################

# Funzioni di validazione dei dati in ingresso alle API

import re
from datetime import datetime

from flask import request

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def corpo_json() -> dict:
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        raise ApiError(400, "Il corpo della richiesta deve essere un oggetto JSON")
    return dati


def richiesti(dati: dict, *campi: str) -> None:
    mancanti = [c for c in campi if dati.get(c) in (None, "")]
    if mancanti:
        raise ApiError(422, "Campi obbligatori mancanti", {"campi": mancanti})


def testo(valore, nome: str, max_len: int = 200, obbligatorio: bool = True) -> str | None:
   
    if valore is None or valore == "":
        if obbligatorio:
            raise ApiError(422, f"Il campo '{nome}' è obbligatorio")
        return None
    if not isinstance(valore, str):
        raise ApiError(422, f"Il campo '{nome}' deve essere un testo")
    valore = valore.strip()
    if obbligatorio and not valore:
        raise ApiError(422, f"Il campo '{nome}' è obbligatorio")
    if len(valore) > max_len:
        raise ApiError(422, f"Il campo '{nome}' supera i {max_len} caratteri")
    return valore or None


def email_valida(email) -> str:
    email = testo(email, "email", 254).lower()
    if not EMAIL_RE.match(email):
        raise ApiError(422, "Indirizzo email non valido")
    return email


def password_robusta(pw) -> str:
    if not isinstance(pw, str):
        raise ApiError(422, "Il campo 'password' deve essere un testo")
    if len(pw) < 8 or len(pw) > 128 or not re.search(r"\d", pw) or not re.search(r"[A-Za-z]", pw):
        raise ApiError(422, "La password deve avere almeno 8 caratteri, con lettere e numeri")
    return pw


def intero(valore, nome: str, minimo: int | None = None, massimo: int | None = None) -> int:
    if isinstance(valore, bool) or isinstance(valore, float) and not valore.is_integer():
        raise ApiError(422, f"Il campo '{nome}' deve essere un numero intero")
    try:
        n = int(valore)
    except (TypeError, ValueError):
        raise ApiError(422, f"Il campo '{nome}' deve essere un numero intero") from None
    if (minimo is not None and n < minimo) or (massimo is not None and n > massimo):
        raise ApiError(422, f"Il campo '{nome}' è fuori dall'intervallo consentito")
    return n


def importo_cent(valore, nome: str) -> int:
    # Converte un importo in euro in centesimi 
    
    if isinstance(valore, bool):
        raise ApiError(422, f"Il campo '{nome}' deve essere un importo")
    try:
        euro = float(str(valore).replace(",", "."))
    except (TypeError, ValueError):
        raise ApiError(422, f"Il campo '{nome}' deve essere un importo") from None
    if not 0 <= euro <= 10_000:
        raise ApiError(422, f"Il campo '{nome}' è fuori dall'intervallo consentito")
    return round(euro * 100)


def data_ora(valore, nome: str = "data_ora") -> str:
    try:
        return datetime.fromisoformat(valore).strftime("%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        raise ApiError(422, f"Il campo '{nome}' deve essere una data ISO (YYYY-MM-DDTHH:MM)") from None
