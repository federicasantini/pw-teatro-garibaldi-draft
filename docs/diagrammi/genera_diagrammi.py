##############################################################################
# Genera i diagrammi della documentazione (richiede Graphviz e matplotlib)
# Uso: python docs/diagrammi/genera_diagrammi.py
##############################################################################

import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).parent
VELLUTO, OTTONE, AVORIO, INCH = "#6e1423", "#b8862b", "#f7f2e9", "#241a17"
FONT = "DejaVu Sans"


def dot(nome, sorgente):
    (OUT / f"{nome}.dot").write_text(sorgente, encoding="utf-8")
    subprocess.run(["dot", "-Tpng", "-Gdpi=170", str(OUT / f"{nome}.dot"), "-o", str(OUT / f"{nome}.png")], check=True)


# Architettura

dot("architettura", f"""
digraph G {{
  rankdir=TB; nodesep=0.6; ranksep=0.55; fontname="{FONT}"; node [fontname="{FONT}", fontsize=11, shape=box, style="rounded,filled", fillcolor="{AVORIO}", color="{VELLUTO}"];
  edge [fontname="{FONT}", fontsize=9, color="{INCH}"];
  subgraph cluster_client {{ label="Client (browser)"; style="rounded,dashed"; color="{OTTONE}";
    ui [label="Front-end\\nHTML5 · JavaScript · Bootstrap Italia 2.18\\n(design system Designers Italia)\\nindex, spettacolo, accedi,\\narea-personale, gestione, privacy"];
    apijs [label="api.js\\nclient REST (fetch)\\n+ token di sessione"];
    ui -> apijs; {{rank=same; ui; apijs}} }}
  subgraph cluster_server {{ label="Server applicativo (Python 3 · Flask)"; style="rounded,dashed"; color="{OTTONE}";
    router [label="Routing /api/*\\nBlueprint"];
    sic [label="Sicurezza\\nauth.py (token hash, RBAC,\\nlimite tentativi) · validation.py\\nintestazioni CSP"];
    logica [label="Logica applicativa\\nutenti/GDPR · catalogo · prenotazioni (QR)\\nlista d'attesa · feedback · dashboard (CSV)"];
    notif [label="Notifiche\\nnotifiche.py\\n(posta in uscita simulata)"];
    audit [label="Sicurezza operativa\\naudit.py · rilevamento.py\\n(registro, log JSON, avvisi)\\nbackup.py"];
    logica -> audit; audit -> dal;
    manut [label="Manutenzione periodica\\nmanutenzione.py\\n(promemoria, chiusura repliche)", style="rounded,filled,dashed"];
    logica -> notif; manut -> notif; manut -> dal;
    dal [label="Accesso ai dati\\ndb.py (sqlite3)"];
    router -> sic -> logica -> dal; {{rank=same; router; sic}} {{rank=same; logica; dal}} }}
  dbf [label="Base dati relazionale\\nSQLite (teatro.db)\\n15 tabelle + 1 vista", shape=cylinder, fillcolor="#efe2c4"];
  apijs -> router [label="HTTP · JSON\\nGET/POST/PUT/PATCH/DELETE"];
  router -> ui [label="file statici", style=dashed];
  dal -> dbf [label="SQL parametrico\\ntransazioni"];
}}""")

# Modello ER

def tab(nome, campi):
    righe = "".join(f'<tr><td align="left" port="{c.split()[0]}">{c}</td></tr>' for c in campi)
    return f'{nome} [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4"><tr><td bgcolor="{VELLUTO}"><font color="white"><b>{nome}</b></font></td></tr>{righe}</table>>];'

dot("modello_er", f"""
digraph ER {{
  rankdir=LR; node [shape=plaintext, fontname="{FONT}", fontsize=10]; edge [fontname="{FONT}", fontsize=9, color="{INCH}", arrowhead=crow, arrowtail=tee, dir=both];
  {tab("utenti", ["id PK", "nome", "cognome", "email UNIQUE", "password_hash", "ruolo", "consenso_privacy", "data_registrazione", "eliminato_il"])}
  {tab("sessioni", ["token_hash PK", "utente_id FK", "creata_il", "scade_il"])}
  {tab("tentativi_login", ["id PK", "email", "ip", "quando"])}
  {tab("sale", ["id PK", "nome UNIQUE", "capienza"])}
  {tab("settori", ["id PK", "sala_id FK", "nome", "posti_totali", "prezzo_cent"])}
  {tab("tariffe", ["id PK", "codice UNIQUE", "nome", "descrizione", "sconto_pct", "richiede_documento", "attiva"])}
  {tab("spettacoli", ["id PK", "titolo", "autore", "compagnia", "genere", "descrizione", "durata_minuti", "attivo", "creato_il"])}
  {tab("repliche", ["id PK", "spettacolo_id FK", "sala_id FK", "data_ora", "stato", "promemoria_inviato_il"])}
  {tab("prezzi_replica", ["replica_id PK,FK", "settore_id PK,FK", "prezzo_cent"])}
  {tab("prenotazioni", ["id PK", "codice UNIQUE", "utente_id FK", "replica_id FK", "settore_id FK", "tariffa_id FK", "num_posti", "prezzo_unitario_cent", "importo_cent", "stato", "data_prenotazione", "annullata_il", "check_in_il"])}
  {tab("feedback", ["id PK", "utente_id FK", "spettacolo_id FK", "voto (1-5)", "commento", "data"])}
  {tab("lista_attesa", ["id PK", "utente_id FK", "replica_id FK", "num_posti", "creata_il", "notificata_il"])}
  {tab("notifiche", ["id PK", "utente_id FK", "destinatario", "oggetto", "corpo", "creata_il"])}
  {tab("registro_audit", ["id PK", "quando", "utente_id", "ruolo", "email", "ip", "azione", "esito", "oggetto", "dettagli"])}
  {tab("avvisi", ["id PK", "quando", "regola", "gravita", "soggetto", "descrizione", "chiave UNIQUE", "gestito_il", "gestito_da FK", "note"])}
  utenti:id -> sessioni:utente_id;
  utenti:id -> lista_attesa:utente_id;
  utenti:id -> notifiche:utente_id;
  repliche:id -> lista_attesa:replica_id;
  repliche:id -> prezzi_replica:replica_id;
  settori:id -> prezzi_replica:settore_id;
  tariffe:id -> prenotazioni:tariffa_id;
  utenti:id -> avvisi:gestito_da;
  utenti:id -> registro_audit:utente_id [style=dashed, label="senza vincolo"];
  utenti:id -> prenotazioni:utente_id;
  utenti:id -> feedback:utente_id;
  sale:id -> settori:sala_id;
  sale:id -> repliche:sala_id;
  spettacoli:id -> repliche:spettacolo_id;
  spettacoli:id -> feedback:spettacolo_id;
  repliche:id -> prenotazioni:replica_id;
  settori:id -> prenotazioni:settore_id;
}}""")

# Casi d'uso

dot("casi_uso", f"""
digraph UC {{
  rankdir=LR; fontname="{FONT}"; node [fontname="{FONT}", fontsize=10]; edge [color="{INCH}", arrowhead=none];
  node [shape=box, style="filled", fillcolor="#efe2c4", color="{OTTONE}"];
  V [label="Visitatore"]; S [label="Spettatore"]; O [label="Operatore\\nbiglietteria"]; A [label="Amministratore"];
  edge [arrowhead=empty, style=dashed]; S -> V; O -> S; A -> O;
  edge [arrowhead=none, style=solid];
  subgraph cluster_sys {{ label="Piattaforma Teatro Garibaldi"; style=rounded; color="{VELLUTO}";
    node [shape=ellipse, style=filled, fillcolor="{AVORIO}", color="{VELLUTO}"];
    uc1 [label="Consultare il cartellone"]; uc2 [label="Verificare la disponibilità"]; uc3 [label="Registrarsi / Accedere"];
    uc4 [label="Prenotare posti"]; uc5 [label="Annullare prenotazione"]; uc6 [label="Lasciare un feedback"];
    uc7 [label="Convalidare ingresso\\n(check-in)"]; uc8 [label="Gestire spettacoli\\ne repliche"]; uc9 [label="Consultare dashboard KPI"];
    uc10 [label="Gestire utenti e ruoli"]; uc11 [label="Iscriversi alla\\nlista d'attesa"];
    uc12 [label="Esportare o cancellare\\ni propri dati (GDPR)"]; uc13 [label="Esportare i dati\\nin CSV"]; }}
  V -> uc1; V -> uc2; V -> uc3; S -> uc4; S -> uc5; S -> uc6; S -> uc11; S -> uc12;
  O -> uc7; O -> uc8; O -> uc9; O -> uc13; A -> uc10;
}}""")

# Diagramma di sequenza (prenotazione)

fig, ax = plt.subplots(figsize=(11, 7.2), dpi=170)
ax.set_xlim(0, 11); ax.set_ylim(0, 7.4); ax.axis("off")
attori = [("Spettatore\n(browser)", 1), ("Front-end\nspettacolo.html", 3.4), ("API Flask\n/api/prenotazioni", 6), ("SQLite\nteatro.db", 9)]
for nome, x in attori:
    ax.add_patch(FancyBboxPatch((x - 0.9, 6.7), 1.8, 0.6, boxstyle="round,pad=0.02", fc=AVORIO, ec=VELLUTO, lw=1.3))
    ax.text(x, 7.0, nome, ha="center", va="center", fontsize=8.5, family=FONT, weight="bold")
    ax.plot([x, x], [0.2, 6.7], ls="--", color="#999", lw=0.8)
messaggi = [
    (1, 3.4, 6.3, "seleziona replica, settore, n. posti"),
    (3.4, 6, 5.8, "POST /api/prenotazioni  {replica_id, settore_id, num_posti, tariffa_id}\nAuthorization: Bearer <token>"),
    (6, 9, 5.2, "verifica hash del token (sessioni JOIN utenti)"),
    (6, 9, 4.7, "BEGIN IMMEDIATE  (lock di scrittura)"),
    (6, 9, 4.2, "SELECT repliche / v_occupazione"),
    (9, 6, 3.75, "posti_totali, posti_occupati", True),
    (6, 6, 3.3, "[limite per utente o liberi < richiesti] → ROLLBACK, 409"),
    (6, 9, 2.8, "INSERT INTO prenotazioni (codice, importo in centesimi)"),
    (6, 9, 2.35, "COMMIT"),
    (6, 3.4, 1.8, "201 Created  {codice, settore, tariffa, importo_totale} + notifica", True),
    (3.4, 1, 1.25, "mostra conferma e codice d'ingresso", True),
]
for m in messaggi:
    x1, x2, y, testo = m[:4]
    ritorno = len(m) > 4
    if x1 == x2:
        ax.annotate("", xy=(x1 + 0.05, y - 0.15), xytext=(x1 + 0.05, y + 0.1),
                    arrowprops=dict(arrowstyle="->", color=VELLUTO, connectionstyle="arc3,rad=-1.6"))
        ax.text(x1 + 0.5, y, testo, fontsize=8, family=FONT, color=VELLUTO, va="center")
        continue
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="->", color=OTTONE if ritorno else INCH, lw=1.2, ls="--" if ritorno else "-"))
    ax.text((x1 + x2) / 2, y + 0.08, testo, ha="center", va="bottom", fontsize=7.8, family=FONT)
ax.add_patch(FancyBboxPatch((5.75, 2.2), 3.55, 2.65, boxstyle="round,pad=0.02", fc="none", ec=VELLUTO, lw=0.9, ls=":"))
ax.text(5.8, 2.02, "transazione atomica", fontsize=7.5, family=FONT, color=VELLUTO, style="italic")
plt.tight_layout(); plt.savefig(OUT / "sequenza_prenotazione.png"); plt.close()

# Stati della prenotazione

dot("stati_prenotazione", f"""
digraph S {{
  rankdir=LR; node [fontname="{FONT}", fontsize=10, shape=box, style="rounded,filled", fillcolor="{AVORIO}", color="{VELLUTO}"]; edge [fontname="{FONT}", fontsize=9];
  start [shape=circle, label="", width=0.2, fillcolor="{INCH}"];
  start -> confermata [label="POST /prenotazioni\\n(posti disponibili, max 6 per utente)"];
  confermata -> utilizzata [label="check-in operatore\\n(da 2 h prima a fine spettacolo)"];
  confermata -> annullata [label="annullamento utente (≥24h), biglietteria,\\nreplica annullata o account eliminato"];
}}""")

# Stati della replica

dot("stati_replica", f"""
digraph R {{
  rankdir=LR; node [fontname="{FONT}", fontsize=10, shape=box, style="rounded,filled", fillcolor="{AVORIO}", color="{VELLUTO}"]; edge [fontname="{FONT}", fontsize=9];
  start [shape=circle, label="", width=0.2, fillcolor="{INCH}"];
  fine [shape=doublecircle, label="", width=0.15, fillcolor="{INCH}"];
  start -> programmata [label="POST /repliche\\n(sala libera: durata + 60 min)"];
  programmata -> conclusa [label="PATCH dopo l'inizio\\no manutenzione a fine spettacolo"];
  programmata -> annullata [label="PATCH stato=annullata\\n(annulla prenotazioni e avvisa)"];
  conclusa -> fine; annullata -> fine;
}}""")
print("Diagrammi generati in", OUT)
