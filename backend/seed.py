####################################################################################################################
#                                           Inizializzazione dei dati                                            #
####################################################################################################################

# python -m backend.seed [--reset] [percorso_db]

# Per sicurezza lo script si rifiuta di sovrascrivere un database esistente:
# per ricrearlo (cancellando tutti i dati) occorre passare --reset

# Le date delle repliche sono calcolate rispetto al giorno di esecuzione, così il
# prototipo mostra sempre una stagione "in corso" con repliche passate e future

import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

from . import tempo
from .db import SCHEMA_PATH

BASE_DIR = Path(__file__).resolve().parent.parent

UTENTI_STAFF = [
    ("Giulia", "Ferri", "admin@teatrogaribaldi.it", "Admin2026!", "admin"),
    ("Marco", "Lodi", "biglietteria@teatrogaribaldi.it", "Operatore2026!", "operatore"),
]
SPETTATORE_DEMO = ("Anna", "Rinaldi", "anna.rinaldi@example.com", "Spettatore2026!")

NOMI = ["Luca", "Sara", "Paolo", "Chiara", "Davide", "Elena", "Matteo", "Francesca",
        "Andrea", "Martina", "Stefano", "Laura", "Simone", "Valentina", "Giorgio",
        "Alessia", "Roberto", "Silvia", "Federico", "Irene"]
COGNOMI = ["Bianchi", "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti",
           "Costa", "Fontana", "Moretti", "Barbieri", "Lombardi", "Testa", "Serra"]

# Teatro Garibaldi di Mazara del Vallo: 92 posti tra platea, due ordini di palchi e loggione
# La ripartizione per settore e i prezzi sono ipotetici (dati dimostrativi)
SETTORI = [("Platea", 52, 2800), ("Palchi", 28, 2200), ("Loggione", 12, 1500)]  # prezzi in centesimi

# codice, nome, descrizione, sconto %, richiede documento
TARIFFE = [
    ("INTERO", "Intero", None, 0, 0),
    ("UNDER26", "Under 26", "Giovani fino a 26 anni", 30, 1),
    ("OVER65", "Over 65", "Dai 65 anni in su", 20, 1),
    ("RAGAZZI", "Ragazzi under 14", "Bambini e ragazzi fino a 14 anni", 50, 1),
]
NUM_SPETTATORI_FITTIZI = 120
MAX_POSTI_PER_UTENTE_REPLICA = 6

SPETTACOLI = [
    ("La locandiera", "Carlo Goldoni", "Compagnia Stabile del Garibaldi", "prosa",
     "La commedia goldoniana per eccellenza: Mirandolina, padrona di una locanda fiorentina, "
     "conquista con astuzia il misogino Cavaliere di Ripafratta.", 120),
    ("Sei personaggi in cerca d'autore", "Luigi Pirandello", "Teatro dell'Ascolto", "prosa",
     "Sei personaggi rifiutati dal loro autore irrompono durante una prova chiedendo di vivere "
     "il proprio dramma. Il capolavoro del teatro nel teatro.", 105),
    ("La traviata", "Giuseppe Verdi", "Orchestra e Coro Città Aperta", "lirica",
     "Opera in tre atti su libretto di Francesco Maria Piave. Allestimento in forma "
     "semiscenica con orchestra da camera.", 150),
    ("Lo schiaccianoci", "Pëtr Il'ič Čajkovskij", "Balletto Giovane Italia", "danza",
     "Il balletto natalizio più amato, in una versione pensata per tutta la famiglia.", 95),
    ("Concerto di Capodanno", "AA.VV.", "Ensemble Garibaldi", "musica",
     "Valzer, polke e ouverture dalla tradizione viennese e italiana per salutare il nuovo anno.", 90),
    ("Le avventure di Pinocchio", "da Carlo Collodi", "Teatro Piccolo Mondo", "ragazzi",
     "Burattini, musica dal vivo e narrazione per i più piccoli (età consigliata 5-10 anni).", 60),
]

COMMENTI = {
    5: ["Spettacolo meraviglioso, attori bravissimi.", "Emozionante dall'inizio alla fine.",
        "Allestimento curato e musiche splendide."],
    4: ["Molto bello, qualche lungaggine nel secondo atto.", "Ottima regia, acustica da migliorare."],
    3: ["Discreto, mi aspettavo di più.", "Interpretazioni buone, scenografia essenziale."],
    2: ["Poco coinvolgente.", "Visibilità limitata dal loggione."],
}


def database_popolato(db_path: str) -> bool:
    if not Path(db_path).exists():
        return False
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0] > 0


def seed(db_path: str, oggi: datetime | None = None, rng_seed: int = 42, sovrascrivi: bool = False) -> None:
    if database_popolato(db_path) and not sovrascrivi:
        raise FileExistsError(f"Il database {db_path} esiste già: usare --reset per ricrearlo (i dati andranno persi)")
    rnd = random.Random(rng_seed)
    oggi = (oggi or tempo.adesso()).replace(second=0, microsecond=0)
    ts = tempo.istante
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # letture concorrenti alle scritture (impostazione persistente)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    cur = conn.cursor()

    # utenti
    for nome, cognome, email, pw, ruolo in UTENTI_STAFF:
        cur.execute("INSERT INTO utenti (nome, cognome, email, password_hash, ruolo, consenso_privacy, data_registrazione) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?)",
                    (nome, cognome, email, generate_password_hash(pw), ruolo, ts(oggi - timedelta(days=120))))
    nome, cognome, email, pw = SPETTATORE_DEMO
    cur.execute("INSERT INTO utenti (nome, cognome, email, password_hash, ruolo, consenso_privacy, data_registrazione) "
                "VALUES (?, ?, ?, ?, 'spettatore', 1, ?)",
                (nome, cognome, email, generate_password_hash(pw), ts(oggi - timedelta(days=60))))
    demo_id = cur.lastrowid
    hash_comune = generate_password_hash("Password2026!")  # password unica per gli utenti fittizi
    spettatori = []
    for i in range(NUM_SPETTATORI_FITTIZI):
        n, c = rnd.choice(NOMI), rnd.choice(COGNOMI)
        cur.execute("INSERT INTO utenti (nome, cognome, email, password_hash, ruolo, consenso_privacy, data_registrazione) "
                    "VALUES (?, ?, ?, ?, 'spettatore', 1, ?)",
                    (n, c, f"{n}.{c}{i}@example.com".lower(), hash_comune,
                     ts(oggi - timedelta(days=rnd.randint(1, 90), minutes=rnd.randint(0, 1440)))))
        spettatori.append(cur.lastrowid)

    # tariffe
    tariffe = {}
    for codice, nome_t, descr, sconto, doc in TARIFFE:
        cur.execute("INSERT INTO tariffe (codice, nome, descrizione, sconto_pct, richiede_documento) VALUES (?, ?, ?, ?, ?)",
                    (codice, nome_t, descr, sconto, doc))
        tariffe[codice] = (cur.lastrowid, sconto)

    def scegli_tariffa(genere):
        if genere == "ragazzi":
            return rnd.choices(["INTERO", "RAGAZZI"], weights=[45, 55])[0]
        return rnd.choices(["INTERO", "UNDER26", "OVER65"], weights=[68, 14, 18])[0]

    # --- sala e settori
    cur.execute("INSERT INTO sale (nome, capienza) VALUES ('Sala del teatro', ?)", (sum(s[1] for s in SETTORI),))
    sala_id = cur.lastrowid
    settori = []
    for nome_s, posti, prezzo in SETTORI:
        cur.execute("INSERT INTO settori (sala_id, nome, posti_totali, prezzo_cent) VALUES (?, ?, ?, ?)",
                    (sala_id, nome_s, posti, prezzo))
        settori.append((cur.lastrowid, posti, prezzo))

    # --- spettacoli e repliche (stagione: da -40 a +60 giorni rispetto a oggi)
    giorni_occupati = set()
    repliche = []  # (id, spettacolo_id, data, stato, genere)
    listino = {}   # prezzi specifici per replica
    for idx, (titolo, autore, comp, genere, descr, durata) in enumerate(SPETTACOLI):
        cur.execute("INSERT INTO spettacoli (titolo, autore, compagnia, genere, descrizione, durata_minuti, creato_il) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)", (titolo, autore, comp, genere, descr, durata, ts(oggi - timedelta(days=90))))
        sid = cur.lastrowid
        inizio = -40 + idx * 16
        for k in range(4):
            giorno = inizio + k * 2
            while giorno in giorni_occupati:
                giorno += 1
            giorni_occupati.add(giorno)
            ora = 16 if genere == "ragazzi" else 21
            quando = (oggi + timedelta(days=giorno)).replace(hour=ora, minute=0)
            stato = "conclusa" if quando < oggi else "programmata"
            cur.execute("INSERT INTO repliche (spettacolo_id, sala_id, data_ora, stato) VALUES (?, ?, ?, ?)",
                        (sid, sala_id, quando.strftime("%Y-%m-%dT%H:%M"), stato))
            rid = cur.lastrowid
            repliche.append((rid, sid, quando, stato, genere))
            if genere == "musica" and k == 0:
                # serata speciale (Capodanno) con listino maggiorato
                for sett_id, _, prezzo in settori:
                    listino[(rid, sett_id)] = prezzo + 700
                    cur.execute("INSERT INTO prezzi_replica (replica_id, settore_id, prezzo_cent) VALUES (?, ?, ?)",
                                (rid, sett_id, prezzo + 700))

    # prenotazioni simulate (rispettando il limite di posti per utente e replica)
    codici = set()
    visti = set()

    def inserisci(codice, uid, rid, sett_id, tariffa_cod, n, prezzo, st, data_pren, quando):
        tid, sconto = tariffe[tariffa_cod]
        unitario = (prezzo * (100 - sconto) + 50) // 100
        cur.execute(
            "INSERT INTO prenotazioni (codice, utente_id, replica_id, settore_id, tariffa_id, num_posti, "
            "prezzo_unitario_cent, importo_cent, stato, data_prenotazione, annullata_il, check_in_il) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (codice, uid, rid, sett_id, tid, n, unitario, unitario * n, st, ts(data_pren),
             ts(min(data_pren + timedelta(days=2), oggi)) if st == "annullata" else None,
             ts(quando - timedelta(minutes=rnd.randint(5, 50))) if st == "utilizzata" else None))

    for rid, sid, quando, stato, genere in repliche:
        posti_utente = {}
        # le repliche passate sono più piene di quelle lontane nel futuro
        giorni_mancanti = (quando - oggi).days
        riempimento = 0.85 if giorni_mancanti < 0 else max(0.15, 0.7 - giorni_mancanti * 0.01)
        for sett_id, posti, prezzo_base in settori:
            prezzo = listino.get((rid, sett_id), prezzo_base)
            obiettivo = int(posti * riempimento * rnd.uniform(0.8, 1.05))
            venduti = 0
            while venduti < obiettivo:
                n = min(rnd.choice([1, 2, 2, 2, 3, 4]), obiettivo - venduti)
                uid = rnd.choice(spettatori)  # lo spettatore demo ha uno storico dedicato
                if posti_utente.get(uid, 0) + n > MAX_POSTI_PER_UTENTE_REPLICA:
                    continue
                codice = "TG-" + "".join(rnd.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
                if codice in codici:
                    continue
                codici.add(codice)
                anticipo = rnd.randint(1, 30)
                data_pren = quando - timedelta(days=anticipo, minutes=rnd.randint(0, 600))
                if data_pren >= oggi:  # repliche future: prenotazioni distribuite nell'ultimo mese
                    data_pren = oggi - timedelta(days=rnd.randint(0, 29), hours=rnd.randint(1, 12))
                if stato == "conclusa":
                    st = "utilizzata" if rnd.random() < 0.93 else "annullata"
                else:
                    st = "confermata" if rnd.random() < 0.95 else "annullata"
                inserisci(codice, uid, rid, sett_id, scegli_tariffa(genere), n, prezzo, st, data_pren, quando)
                if st != "annullata":
                    venduti += n
                    posti_utente[uid] = posti_utente.get(uid, 0) + n
                if st == "utilizzata":
                    visti.add((uid, sid, quando))

    #     storico dello spettatore demo: due spettacoli visti (uno già recensito)
    #     e una prenotazione futura confermata
    passate = [r for r in repliche if r[3] == "conclusa"]
    future = [r for r in repliche if r[3] == "programmata"]
    demo_pren = [(passate[0], "utilizzata", 2, 0), (passate[4], "utilizzata", 1, 1), (future[1], "confermata", 2, 1)]
    for i, ((rid, _, quando, _, _), st, n, sett) in enumerate(demo_pren):
        sett_id, _, prezzo = settori[sett]
        data_pren = min(quando, oggi - timedelta(days=1)) - timedelta(days=7)
        inserisci(f"TG-DEMO0{i + 1}", demo_id, rid, sett_id, "INTERO", n, listino.get((rid, sett_id), prezzo),
                  st, data_pren, quando)
    pid_recensito = passate[0][1]
    cur.execute("INSERT INTO feedback (utente_id, spettacolo_id, voto, commento, data) VALUES (?, ?, 5, ?, ?)",
                (demo_id, pid_recensito, "Mirandolina straordinaria, regia elegante.",
                 ts(passate[0][2] + timedelta(days=1))))
    cur.execute("INSERT INTO notifiche (utente_id, destinatario, oggetto, corpo, creata_il) VALUES (?, ?, ?, ?, ?)",
                (demo_id, SPETTATORE_DEMO[2], "Benvenuto al Teatro Garibaldi",
                 "Ciao Anna,\nil tuo account è attivo. Dal cartellone puoi prenotare i posti e nella tua area "
                 "personale trovi biglietti, QR code e messaggi.", ts(oggi - timedelta(days=60))))

    # feedback per una parte degli spettacoli visti
    recensiti = set()
    for uid, sid, quando in sorted(visti, key=lambda v: (v[0], v[1], v[2])):
        if (uid, sid) in recensiti or rnd.random() > 0.35:
            continue
        recensiti.add((uid, sid))
        voto = rnd.choices([5, 4, 3, 2], weights=[45, 35, 15, 5])[0]
        commento = rnd.choice(COMMENTI[voto]) if rnd.random() < 0.7 else None
        cur.execute("INSERT INTO feedback (utente_id, spettacolo_id, voto, commento, data) VALUES (?, ?, ?, ?, ?)",
                    (uid, sid, voto, commento, ts(quando + timedelta(days=1, hours=rnd.randint(-12, 12)))))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    argomenti = [a for a in sys.argv[1:] if a != "--reset"]
    destinazione = argomenti[0] if argomenti else str(BASE_DIR / "data" / "teatro.db")
    Path(destinazione).parent.mkdir(parents=True, exist_ok=True)
    try:
        seed(destinazione, sovrascrivi="--reset" in sys.argv)
    except FileExistsError as e:
        sys.exit(f"Operazione annullata. {e}")
    print(f"Database inizializzato con dati dimostrativi: {destinazione}")
