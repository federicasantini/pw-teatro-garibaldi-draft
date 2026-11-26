####################################################################################################################
#                                           Backup e ripristino del database                                       #
####################################################################################################################
# Elementi di sicurezza:
#    python -m backend.backup crea                     => nuovo backup in data/backup/
#    python -m backend.backup elenco                   => backup disponibili
#    python -m backend.backup verifica  <file.db>      => controlla integrità e impronta
#    python -m backend.backup ripristina <file.db> --conferma

# Come funziona:
# a) il backup usa l'API di backup di SQLite che copia il database anche mentre il server è in funzione;
# b) per ogni backup viene salvata l'impronta SHA-256 (file .sha256): se il file viene alterato o si corrompe, 
#    la verifica se ne accorge;
# c) vengono conservati gli ultimi 14 backup (predefinito 14, configurabile con --conserva): i backup più vecchi vengono eliminati;
# d) prima del ripristino, il database attuale viene salvato in una copia di sicurezza;
# e) creazione e il ripristino vengono annotati nel registro di audit

# Pianificazione giornaliera:
# Dove conservare le copie (altro disco, altra sede, cifratura) è una scelta organizzativa (vedi documento dedicato docs/nis2.md)

# IMPORTANTE: Il ripristino va eseguito a server fermo

####################################################################################################################

import argparse
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

from . import tempo
from .audit import configura_log, scrivi

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PREDEFINITO = os.environ.get("TG_DATABASE", str(BASE_DIR / "data" / "teatro.db"))
CARTELLA_PREDEFINITA = os.environ.get("TG_BACKUP_DIR", str(BASE_DIR / "data" / "backup"))
CONSERVA_PREDEFINITO = 14


def impronta(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def _copia(origine: str, destinazione: str) -> None:

    src, dst = sqlite3.connect(origine), sqlite3.connect(destinazione)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def _integro(percorso: Path) -> bool:
    try:
        conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
        try:
            return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def _annota(db_path: str, azione: str, dettagli: dict) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        scrivi(conn, azione, dettagli=dettagli)
    finally:
        conn.close()


def crea_backup(db_path: str = DB_PREDEFINITO, cartella: str = CARTELLA_PREDEFINITA,
                conserva: int = CONSERVA_PREDEFINITO) -> Path:
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database non trovato: {db_path}")
    Path(cartella).mkdir(parents=True, exist_ok=True)
    destinazione = Path(cartella) / f"teatro-{tempo.adesso().strftime('%Y%m%d-%H%M%S')}.db"
    n = 1
    while destinazione.exists():  # due backup nello stesso secondo
        destinazione = destinazione.with_name(f"{destinazione.stem}-{n}.db")
        n += 1
    _copia(db_path, str(destinazione))
    if not _integro(destinazione):
        destinazione.unlink()
        raise RuntimeError("Il backup appena creato non supera il controllo di integrità")
    destinazione.with_suffix(".sha256").write_text(f"{impronta(destinazione)}  {destinazione.name}\n")
    eliminati = ruota(cartella, conserva)
    _annota(db_path, "sistema.backup_creato", {"file": destinazione.name, "backup_eliminati": len(eliminati)})
    return destinazione


def elenco(cartella: str = CARTELLA_PREDEFINITA) -> list[Path]:
    return sorted(Path(cartella).glob("teatro-*.db"))


def ruota(cartella: str, conserva: int) -> list[Path]:
    # Elimina i backup più vecchi oltre il numero da conservare

    vecchi = elenco(cartella)[:-conserva] if conserva > 0 else []
    for f in vecchi:
        f.unlink()
        f.with_suffix(".sha256").unlink(missing_ok=True)
    return vecchi


def verifica_backup(percorso: str | Path) -> tuple[bool, str]:
    percorso = Path(percorso)
    if not percorso.exists():
        return False, "file inesistente"
    file_impronta = percorso.with_suffix(".sha256")
    if not file_impronta.exists():
        return False, "impronta SHA-256 mancante"
    if file_impronta.read_text().split()[0] != impronta(percorso):
        return False, "impronta SHA-256 diversa: il file è stato alterato o è danneggiato"
    if not _integro(percorso):
        return False, "il database non supera il controllo di integrità"
    return True, "backup integro"


def ripristina(percorso: str | Path, db_path: str = DB_PREDEFINITO,
               cartella: str = CARTELLA_PREDEFINITA) -> Path | None:
    
    # Ripristina un backup verificato e restituisce la copia di sicurezza del db sostituito
    
    ok, motivo = verifica_backup(percorso)
    if not ok:
        raise ValueError(f"Ripristino annullato: {motivo}")
    copia_sicurezza = None
    if Path(db_path).exists():
        Path(cartella).mkdir(parents=True, exist_ok=True)
        copia_sicurezza = Path(cartella) / f"prima-del-ripristino-{tempo.adesso().strftime('%Y%m%d-%H%M%S')}.db"
        _copia(db_path, str(copia_sicurezza))
    _copia(str(percorso), db_path)
    _annota(db_path, "sistema.backup_ripristinato",
            {"file": Path(percorso).name, "copia_sicurezza": copia_sicurezza.name if copia_sicurezza else None})
    return copia_sicurezza


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.backup", description="Backup e ripristino del database")
    parser.add_argument("--database", default=DB_PREDEFINITO)
    parser.add_argument("--cartella", default=CARTELLA_PREDEFINITA)
    sub = parser.add_subparsers(dest="comando", required=True)
    crea = sub.add_parser("crea", help="crea un nuovo backup")
    crea.add_argument("--conserva", type=int, default=CONSERVA_PREDEFINITO, help="numero di backup da tenere")
    sub.add_parser("elenco", help="elenca i backup disponibili")
    ver = sub.add_parser("verifica", help="verifica integrità e impronta di un backup")
    ver.add_argument("file")
    rip = sub.add_parser("ripristina", help="ripristina un backup")
    rip.add_argument("file")
    rip.add_argument("--conferma", action="store_true", help="obbligatorio: conferma la sostituzione del database")
    a = parser.parse_args(argv)
    configura_log(os.environ.get("TG_LOG_DIR", str(BASE_DIR / "data" / "log")))

    if a.comando == "crea":
        print(f"Backup creato: {crea_backup(a.database, a.cartella, a.conserva)}")
    elif a.comando == "elenco":
        for f in elenco(a.cartella):
            ok, motivo = verifica_backup(f)
            print(f"{'OK ' if ok else 'KO '} {f.name}  ({f.stat().st_size // 1024} KB) – {motivo}")
    elif a.comando == "verifica":
        ok, motivo = verifica_backup(a.file)
        print(("OK: " if ok else "ERRORE: ") + motivo)
        return 0 if ok else 1
    elif a.comando == "ripristina":
        if not a.conferma:
            print("Il ripristino sostituisce il database attuale: ripetere il comando con --conferma")
            return 2
        copia = ripristina(a.file, a.database, a.cartella)
        print(f"Database ripristinato da {a.file}." + (f" Copia del database precedente: {copia}" if copia else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
