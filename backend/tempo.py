####################################################################################################################
#                                           Gestione di data e ora                                              #
####################################################################################################################

# Tutte le date dell'applicazione sono espresse nell'ora locale del teatro (fuso Europe/Rome, configurabile con TG_FUSO_ORARIO) 
# e memorizzate come testo ISO 8601 senza fuso: 'YYYY-MM-DDTHH:MM:SS' per gli istanti (registrazioni, prenotazioni, sessioni) e 'YYYY-MM-DDTHH:MM' per l'orario degli spettacoli
# I confronti tra stringhe nel database sono confronti cronologici e non si mescolano più UTC
# (datetime('now') di SQLite) e ora locale

# Le funzioni vanno richiamate come `tempo.adesso()` 
# i test "spostano l'orologio" con monkeypatch

import os
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo(os.environ.get("TG_FUSO_ORARIO", "Europe/Rome"))
FMT_ISTANTE = "%Y-%m-%dT%H:%M:%S"
FMT_MINUTI = "%Y-%m-%dT%H:%M"


def adesso() -> datetime:
    return datetime.now(FUSO).replace(tzinfo=None, microsecond=0)


def istante(dt: datetime | None = None) -> str:
    return (dt or adesso()).strftime(FMT_ISTANTE)


def minuti(dt: datetime | None = None) -> str:
    return (dt or adesso()).strftime(FMT_MINUTI)
