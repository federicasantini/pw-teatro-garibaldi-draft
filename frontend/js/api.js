/* =====================================================================
   Client delle API REST.
   Centralizza le chiamate fetch(), l'invio del token di autenticazione e
   la gestione degli errori, così le pagine non ripetono codice di rete.
   ===================================================================== */
const API = (() => {
  const BASE = "/api";
  const CHIAVE_TOKEN = "tg_token";
  const CHIAVE_UTENTE = "tg_utente";

  // sessionStorage: la sessione termina alla chiusura della scheda del browser
  const sessione = {
    token: () => { try { return sessionStorage.getItem(CHIAVE_TOKEN); } catch { return null; } },
    utente: () => { try { return JSON.parse(sessionStorage.getItem(CHIAVE_UTENTE)); } catch { return null; } },
    salva(token, utente) {
      try { sessionStorage.setItem(CHIAVE_TOKEN, token); sessionStorage.setItem(CHIAVE_UTENTE, JSON.stringify(utente)); } catch { }
    },
    cancella() {
      try { sessionStorage.removeItem(CHIAVE_TOKEN); sessionStorage.removeItem(CHIAVE_UTENTE); } catch { }
    },
  };

  class ErroreApi extends Error {
    constructor(status, messaggio, dettagli) {
      super(messaggio);
      this.status = status;
      this.dettagli = dettagli || {};
    }
  }

  async function richiesta(metodo, percorso, corpo, formato = "json") {
    const headers = { Accept: formato === "json" ? "application/json" : "*/*" };
    const token = sessione.token();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (corpo !== undefined) headers["Content-Type"] = "application/json";

    let risposta;
    try {
      risposta = await fetch(BASE + percorso, {
        method: metodo,
        headers,
        body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
      });
    } catch {
      throw new ErroreApi(0, "Impossibile contattare il server. Verifica la connessione.");
    }

    if (risposta.status === 204) return null;
    if (!risposta.ok) {
      const dati = await risposta.json().catch(() => ({}));
      if (risposta.status === 401 && token) sessione.cancella(); // token scaduto o non valido
      throw new ErroreApi(risposta.status, dati.errore || "Errore imprevisto", dati.dettagli);
    }
    if (formato === "blob") return risposta.blob();
    return risposta.json().catch(() => ({}));
  }

  /** Scarica un file prodotto da un'API protetta (serve il token, quindi non basta un link). */
  async function scarica(percorso, nomeFile) {
    const blob = await richiesta("GET", percorso, undefined, "blob");
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: nomeFile });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const qs = (parametri) => {
    const p = new URLSearchParams();
    Object.entries(parametri || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
    const s = p.toString();
    return s ? `?${s}` : "";
  };

  return {
    sessione,
    ErroreApi,
    // autenticazione
    registrazione: (dati) => richiesta("POST", "/auth/registrazione", dati),
    login: (email, password) => richiesta("POST", "/auth/login", { email, password }),
    logout: () => richiesta("POST", "/auth/logout"),
    me: () => richiesta("GET", "/auth/me"),
    esportaDati: () => scarica("/auth/me/dati", "teatro-garibaldi-miei-dati.json"),
    eliminaAccount: (password) => richiesta("DELETE", "/auth/me", { password }),
    notifiche: () => richiesta("GET", "/notifiche"),
    // catalogo
    spettacoli: (filtri) => richiesta("GET", "/spettacoli" + qs(filtri)),
    spettacolo: (id) => richiesta("GET", `/spettacoli/${id}`),
    creaSpettacolo: (dati) => richiesta("POST", "/spettacoli", dati),
    modificaSpettacolo: (id, dati) => richiesta("PUT", `/spettacoli/${id}`, dati),
    eliminaSpettacolo: (id) => richiesta("DELETE", `/spettacoli/${id}`),
    repliche: (filtri) => richiesta("GET", "/repliche" + qs(filtri)),
    disponibilita: (id) => richiesta("GET", `/repliche/${id}/disponibilita`),
    creaReplica: (dati) => richiesta("POST", "/repliche", dati),
    statoReplica: (id, stato) => richiesta("PATCH", `/repliche/${id}`, { stato }),
    sale: () => richiesta("GET", "/sale"),
    tariffe: () => richiesta("GET", "/tariffe"),
    // prenotazioni
    prenota: (dati) => richiesta("POST", "/prenotazioni", dati),
    prenotazioni: (filtri) => richiesta("GET", "/prenotazioni" + qs(filtri)),
    annullaPrenotazione: (id) => richiesta("DELETE", `/prenotazioni/${id}`),
    checkIn: (codice) => richiesta("POST", "/prenotazioni/check-in", { codice }),
    qrCode: (id) => richiesta("GET", `/prenotazioni/${id}/qr`, undefined, "blob"),
    // lista d'attesa
    entraInAttesa: (replicaId, numPosti) => richiesta("POST", `/repliche/${replicaId}/lista-attesa`, { num_posti: numPosti }),
    esciDaAttesa: (replicaId) => richiesta("DELETE", `/repliche/${replicaId}/lista-attesa`),
    listaAttesa: () => richiesta("GET", "/lista-attesa"),
    // feedback
    feedback: (spettacoloId) => richiesta("GET", `/spettacoli/${spettacoloId}/feedback`),
    lasciaFeedback: (dati) => richiesta("POST", "/feedback", dati),
    // back-office
    dashboard: () => richiesta("GET", "/dashboard"),
    esportaCsv: (dati) => scarica(`/dashboard/export?dati=${dati}`, `${dati}.csv`),
    utenti: () => richiesta("GET", "/utenti"),
    cambiaRuolo: (id, ruolo) => richiesta("PATCH", `/utenti/${id}`, { ruolo }),
    // sicurezza (solo amministratori)
    audit: (filtri) => richiesta("GET", "/audit" + qs(filtri)),
    avvisi: (stato) => richiesta("GET", "/avvisi" + qs({ stato })),
    gestisciAvviso: (id, note) => richiesta("PATCH", `/avvisi/${id}`, { note }),
  };
})();
