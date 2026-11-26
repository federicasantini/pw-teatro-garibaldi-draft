/* =====================================================================
   Area di gestione (operatori di biglietteria e amministratori):
   dashboard KPI ed export CSV, check-in (anche con QR), catalogo spettacoli,
   repliche con listino, utenti, sicurezza (registro di audit e avvisi).
   ===================================================================== */
(() => {
  const utente = UI.richiediAccesso(["operatore", "admin"]);
  if (!utente) return;
  const $ = (s) => document.getElementById(s);
  const errore = (err) => UI.avviso($("messaggi"), err.message, "errore");

  if (utente.ruolo !== "admin") { $("tab-utenti").remove(); $("tab-sicurezza").remove(); }
  $("sp-genere").innerHTML = Object.entries(UI.GENERI).map(([v, t]) => `<option value="${v}">${t}</option>`).join("");

  // ----------------------------------------------------------- navigazione schede
  const caricatori = { dashboard: caricaDashboard, spettacoli: caricaSpettacoli, repliche: caricaRepliche, utenti: caricaUtenti, sicurezza: caricaSicurezza, checkin: () => $("codice").focus() };
  const percento = (n) => `${String(n).replace(".", ",")}%`;
  $("schede").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("schede").querySelectorAll("button").forEach((x) => {
      x.setAttribute("aria-selected", x === b);
      x.classList.toggle("active", x === b);
    });
    document.querySelectorAll("[data-pannello]").forEach((p) => { p.hidden = p.dataset.pannello !== b.dataset.scheda; });
    UI.avviso($("messaggi"), "");
    if (b.dataset.scheda !== "checkin") fermaScanner();
    caricatori[b.dataset.scheda]?.();
  });

  // ------------------------------------------------------------------ dashboard
  function barre(contenitore, righe, etichetta, valore, formato = UI.fmtNum) {
    const max = Math.max(1, ...righe.map(valore));
    // barre orizzontali realizzate con il componente "progress" del kit
    contenitore.innerHTML = righe.map((r) => `<div class="riga">
        <span class="nome-barra" title="${UI.esc(etichetta(r))}">${UI.esc(etichetta(r))}</span>
        <div class="progress" aria-hidden="true"><div class="progress-bar bg-primary" style="width:${(100 * valore(r)) / max}%"></div></div>
        <span class="valore">${formato(valore(r))}</span></div>`).join("") || '<p class="text-secondary">Nessun dato</p>';
  }

  async function caricaDashboard() {
    try {
      const d = await API.dashboard();
      const k = d.kpi;
      const euroTondi = (n) => Number(n).toLocaleString("it-IT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
      const tessere = [
        ["Biglietti emessi", UI.fmtNum(k.biglietti_emessi)],
        ["Incasso totale", euroTondi(k.incasso), `${euroTondi(k.incasso_realizzato)} realizzato · ${euroTondi(k.incasso_prevendita)} in prevendita`],
        ["Riempimento", percento(k.tasso_riempimento), "repliche già andate in scena"],
        ["Prevendita", percento(k.tasso_prevendita), "posti venduti sulle repliche future"],
        ["Spettatori registrati", UI.fmtNum(k.spettatori_registrati)],
        ["Voto medio", k.voto_medio ? `${String(k.voto_medio).replace(".", ",")} / 5` : "—", `${UI.fmtNum(k.numero_feedback)} recensioni`],
        ["Tasso annullamento", percento(k.tasso_annullamento)],
        ["In lista d'attesa", UI.fmtNum(k.in_lista_attesa), "richieste non ancora soddisfatte"],
      ];
      $("kpi").innerHTML = tessere.map(([t, v, nota]) => `<div class="col-12 col-sm-6 col-md-4 col-xl-3">
          <div class="card card-bg no-after shadow-sm rounded"><div class="card-body p-3">
            <span class="kpi-titolo">${t}</span><span class="valore">${v}</span>${nota ? `<span class="nota">${nota}</span>` : ""}
          </div></div></div>`).join("");
      barre($("g-spettacoli"), d.per_spettacolo, (r) => r.titolo, (r) => r.biglietti);
      barre($("g-settori"), d.per_settore, (r) => r.settore, (r) => r.incasso, UI.fmtEuro);
      barre($("g-generi"), d.per_genere, (r) => UI.GENERI[r.genere], (r) => r.biglietti);
      barre($("g-tariffe"), d.per_tariffa, (r) => r.tariffa, (r) => r.biglietti);
      const serie = d.andamento_30_giorni;
      const max = Math.max(1, ...serie.map((g) => g.biglietti));
      $("g-andamento").innerHTML = serie.map((g) =>
        `<span style="height:${(100 * g.biglietti) / max}%" title="${g.giorno}: ${g.prenotazioni} prenotazioni, ${g.biglietti} biglietti"></span>`).join("");
      $("g-andamento-assi").innerHTML = serie.length ? `<span>${serie[0].giorno}</span><span>${serie.at(-1).giorno}</span>` : "";
    } catch (err) { errore(err); }
  }

  $("barra-csv").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-csv]"); if (!b) return;
    try { await API.esportaCsv(b.dataset.csv); } catch (err) { errore(err); }
  });

  // ------------------------------------------------------------------- check-in
  async function convalida(codice) {
    if (!codice) return;
    try {
      const p = await API.checkIn(codice);
      const documento = p.richiede_documento ? ` — VERIFICARE IL DOCUMENTO per la tariffa ${p.tariffa}` : "";
      UI.avviso($("esito-checkin"), `Ingresso consentito: ${p.intestatario} · ${p.titolo} · ${p.num_posti} ${p.num_posti > 1 ? "posti" : "posto"} in ${p.settore} (${p.tariffa})${documento}`, "ok");
      $("codice").value = "";
    } catch (err) {
      const p = err.dettagli?.prenotazione;
      UI.avviso($("esito-checkin"), p ? `${err.message} (${p.intestatario} · ${p.titolo})` : err.message, "errore");
    }
    $("codice").focus();
  }
  $("form-checkin").addEventListener("submit", (e) => { e.preventDefault(); convalida($("codice").value.trim()); });

  // Lettura del QR con la fotocamera tramite l'API nativa BarcodeDetector
  // (Chrome/Edge/Android). Dove non è disponibile resta l'inserimento manuale.
  let flusso = null, timerScanner = null;
  if ("BarcodeDetector" in window && navigator.mediaDevices?.getUserMedia) $("avvia-scanner").hidden = false;

  function fermaScanner() {
    clearInterval(timerScanner);
    flusso?.getTracks().forEach((t) => t.stop());
    flusso = null;
    $("scanner").hidden = true;
  }
  $("ferma-scanner").addEventListener("click", fermaScanner);

  $("avvia-scanner").addEventListener("click", async () => {
    try {
      const rilevatore = new BarcodeDetector({ formats: ["qr_code"] });
      flusso = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      const video = $("video-scanner");
      video.srcObject = flusso;
      await video.play();
      $("scanner").hidden = false;
      let ultimo = "";
      timerScanner = setInterval(async () => {
        const [qr] = await rilevatore.detect(video).catch(() => []);
        const codice = qr?.rawValue?.trim().toUpperCase();
        if (codice && /^TG-[A-Z0-9]{5,10}$/.test(codice) && codice !== ultimo) {
          ultimo = codice; // evita di convalidare più volte lo stesso QR inquadrato
          $("codice").value = codice;
          convalida(codice);
        }
      }, 400);
    } catch (err) {
      fermaScanner();
      UI.avviso($("esito-checkin"), `Fotocamera non disponibile: ${err.message}`, "errore");
    }
  });

  // ----------------------------------------------------------------- spettacoli
  let cacheSpettacoli = [];
  async function caricaSpettacoli() {
    try {
      cacheSpettacoli = await API.spettacoli({ tutti: 1 });
      $("tab-spettacoli").innerHTML = cacheSpettacoli.map((s) => `<tr>
          <td><strong>${UI.esc(s.titolo)}</strong><br><span class="text-secondary small">${UI.esc(s.compagnia || "")}</span></td>
          <td>${UI.GENERI[s.genere]}</td>
          <td>${s.prossima_replica ? UI.fmtData(s.prossima_replica) : "—"}</td>
          <td><span class="badge bg-${s.attivo ? "success" : "secondary"}">${s.attivo ? "in cartellone" : "ritirato"}</span></td>
          <td class="tabella-azioni text-end"><button class="btn btn-outline-primary btn-xs" data-modifica="${s.id}">Modifica</button>
            ${utente.ruolo === "admin" && s.attivo ? `<button class="btn btn-outline-danger btn-xs" data-ritira="${s.id}">Ritira</button>` : ""}</td></tr>`).join("");
    } catch (err) { errore(err); }
  }

  function resetFormSpettacolo() {
    $("form-spettacolo").reset();
    $("sp-id").value = "";
    $("titolo-form-sp").textContent = "Nuovo spettacolo";
    $("sp-annulla").hidden = true;
  }
  $("sp-annulla").addEventListener("click", resetFormSpettacolo);

  $("tab-spettacoli").addEventListener("click", async (e) => {
    const mod = e.target.closest("[data-modifica]");
    const rit = e.target.closest("[data-ritira]");
    if (mod) {
      const s = cacheSpettacoli.find((x) => x.id === Number(mod.dataset.modifica));
      $("sp-id").value = s.id;
      ["titolo", "autore", "compagnia", "genere", "descrizione"].forEach((c) => { $(`sp-${c}`).value = s[c] ?? ""; });
      $("sp-durata").value = s.durata_minuti ?? "";
      $("titolo-form-sp").textContent = `Modifica: ${s.titolo}`;
      $("sp-annulla").hidden = false;
      $("form-spettacolo").scrollIntoView({ behavior: "smooth" });
    }
    if (rit && await UI.conferma("Lo spettacolo non sarà più visibile nel cartellone; lo storico resta nei dati.",
      { titolo: "Ritirare lo spettacolo?", ok: "Ritira", pericolo: true })) {
      try { await API.eliminaSpettacolo(rit.dataset.ritira); UI.toast("Spettacolo ritirato"); caricaSpettacoli(); } catch (err) { errore(err); }
    }
  });

  $("form-spettacolo").addEventListener("submit", async (e) => {
    e.preventDefault();
    const dati = {
      titolo: $("sp-titolo").value.trim(), autore: $("sp-autore").value.trim(), compagnia: $("sp-compagnia").value.trim(),
      genere: $("sp-genere").value, descrizione: $("sp-descrizione").value.trim(), durata_minuti: $("sp-durata").value || null,
    };
    try {
      if ($("sp-id").value) await API.modificaSpettacolo($("sp-id").value, dati);
      else await API.creaSpettacolo(dati);
      UI.toast("Spettacolo salvato");
      resetFormSpettacolo();
      UI.avviso($("esito-sp"), "");
      caricaSpettacoli();
    } catch (err) { UI.avviso($("esito-sp"), err.message, "errore"); }
  });

  // ------------------------------------------------------------------- repliche
  let sale = [];
  function mostraListino() {
    const sala = sale.find((s) => String(s.id) === $("rp-sala").value);
    $("rp-prezzi").innerHTML = (sala?.settori || []).map((st) => `<div class="form-group col-md-4">
        <label for="rp-prezzo-${st.id}" class="active">${UI.esc(st.nome)} (€)</label>
        <input id="rp-prezzo-${st.id}" class="form-control" data-settore="${st.id}" type="number" min="0" step="0.5" placeholder="base: ${UI.fmtEuro(st.prezzo)}"></div>`).join("");
  }
  $("rp-sala").addEventListener("change", mostraListino);

  async function caricaRepliche() {
    try {
      const [repliche, spettacoli, elencoSale] = await Promise.all([API.repliche(), API.spettacoli(), sale.length ? sale : API.sale()]);
      $("rp-spettacolo").innerHTML = spettacoli.map((s) => `<option value="${s.id}">${UI.esc(s.titolo)}</option>`).join("");
      if (!sale.length) {
        sale = elencoSale;
        $("rp-sala").innerHTML = sale.map((s) => `<option value="${s.id}">${UI.esc(s.nome)} (${s.capienza} posti)</option>`).join("");
        mostraListino();
      }
      const adesso = new Date();
      $("tab-repliche").innerHTML = repliche.slice().reverse().map((r) => {
        const perc = r.posti_totali ? Math.round((100 * r.posti_occupati) / r.posti_totali) : 0;
        const iniziata = new Date(r.data_ora) <= adesso;
        const azioni = r.stato !== "programmata" ? ""
          : iniziata ? `<button class="btn btn-outline-primary btn-xs" data-concludi-replica="${r.id}">Concludi</button>`
            : `<button class="btn btn-outline-danger btn-xs" data-annulla-replica="${r.id}">Annulla</button>`;
        const colore = { programmata: "success", annullata: "danger", conclusa: "secondary" }[r.stato];
        return `<tr><td>${UI.fmtData(r.data_ora)}<br><span class="text-secondary small">ore ${UI.fmtOra(r.data_ora)} · ${UI.esc(r.sala)}</span></td>
          <td>${UI.esc(r.titolo)}</td>
          <td class="text-end">${r.posti_occupati} / ${r.posti_totali}<br><span class="text-secondary small">${perc}%</span></td>
          <td><span class="badge bg-${colore}">${r.stato}</span></td>
          <td class="tabella-azioni text-end">${azioni}</td></tr>`;
      }).join("");
    } catch (err) { errore(err); }
  }

  $("tab-repliche").addEventListener("click", async (e) => {
    const annulla = e.target.closest("[data-annulla-replica]");
    const concludi = e.target.closest("[data-concludi-replica]");
    try {
      if (annulla) {
        if (!await UI.conferma("Verranno annullate anche tutte le prenotazioni collegate e gli spettatori riceveranno un avviso.",
          { titolo: "Annullare la replica?", ok: "Annulla replica", pericolo: true })) return;
        await API.statoReplica(annulla.dataset.annullaReplica, "annullata");
        UI.toast("Replica annullata");
      } else if (concludi) {
        await API.statoReplica(concludi.dataset.concludiReplica, "conclusa");
        UI.toast("Replica conclusa");
      } else return;
      caricaRepliche();
    } catch (err) { errore(err); }
  });

  $("form-replica").addEventListener("submit", async (e) => {
    e.preventDefault();
    const prezzi = {};
    $("rp-prezzi").querySelectorAll("input[data-settore]").forEach((i) => { if (i.value !== "") prezzi[i.dataset.settore] = i.value; });
    try {
      await API.creaReplica({
        spettacolo_id: Number($("rp-spettacolo").value), data_ora: $("rp-data").value,
        sala_id: Number($("rp-sala").value), prezzi
      });
      $("rp-prezzi").querySelectorAll("input").forEach((i) => { i.value = ""; });
      UI.toast("Replica programmata");
      UI.avviso($("esito-rp"), "");
      caricaRepliche();
    } catch (err) { UI.avviso($("esito-rp"), err.message, "errore"); }
  });

  // --------------------------------------------------------------------- utenti
  async function caricaUtenti() {
    try {
      const elenco = await API.utenti();
      $("tab-utenti-body").innerHTML = elenco.map((u) => `<tr>
          <td>${UI.esc(u.cognome)} ${UI.esc(u.nome)}</td><td>${UI.esc(u.email)}</td><td class="text-end">${u.prenotazioni}</td>
          <td><select class="form-select form-select-sm w-auto" data-ruolo="${u.id}" aria-label="Ruolo di ${UI.esc(u.nome)} ${UI.esc(u.cognome)}" ${u.id === utente.id ? "disabled" : ""}>
            ${["spettatore", "operatore", "admin"].map((r) => `<option ${r === u.ruolo ? "selected" : ""}>${r}</option>`).join("")}
          </select></td></tr>`).join("");
    } catch (err) { errore(err); }
  }
  $("tab-utenti-body").addEventListener("change", async (e) => {
    const s = e.target.closest("[data-ruolo]"); if (!s) return;
    try { await API.cambiaRuolo(s.dataset.ruolo, s.value); UI.toast("Ruolo aggiornato"); } catch (err) { errore(err); caricaUtenti(); }
  });

  // ------------------------------------------------------------------ sicurezza
  const COLORE_ESITO = { ok: "success", fallito: "warning", negato: "danger" };
  const COLORE_GRAVITA = { alta: "danger", media: "warning" };
  const fmtIstante = (iso) => `${UI.fmtData(iso, { weekday: undefined, month: "short" })} ${iso.slice(11, 19)}`;

  async function contaAvvisi() {
    if (utente.ruolo !== "admin") return;
    try {
      const n = (await API.avvisi("aperti")).length;
      $("conta-avvisi").textContent = n;
      $("conta-avvisi").hidden = n === 0;
    } catch { /* il conteggio è solo informativo */ }
  }

  async function caricaAvvisi() {
    const elenco = await API.avvisi("aperti");
    $("conta-avvisi").textContent = elenco.length;
    $("conta-avvisi").hidden = elenco.length === 0;
    $("elenco-avvisi").innerHTML = elenco.length ? elenco.map((a) => `
      <div class="card card-bg no-after shadow-sm rounded mb-3"><div class="card-body d-md-flex justify-content-between gap-4">
        <div>
          <span class="badge bg-${COLORE_GRAVITA[a.gravita]}">gravità ${a.gravita}</span>
          <strong class="ms-2">${UI.esc(a.regola.replaceAll("_", " "))}</strong>
          <span class="text-secondary small ms-2">${fmtIstante(a.quando)}</span>
          <p class="mt-2 mb-0">${UI.esc(a.descrizione)}</p>
        </div>
        <div class="mt-3 mt-md-0"><button class="btn btn-outline-primary btn-xs text-nowrap" data-gestisci="${a.id}">Segna come gestito</button></div>
      </div></div>`).join("")
      : '<div class="alert alert-success">Nessun avviso aperto</div>';
    $("elenco-avvisi").dataset.avvisi = JSON.stringify(elenco.map((a) => [a.id, a.descrizione]));
  }

  async function caricaAudit() {
    const righe = await API.audit({ categoria: $("au-categoria").value, esito: $("au-esito").value, email: $("au-email").value.trim() });
    $("tab-audit").innerHTML = righe.length ? righe.map((r) => `<tr>
        <td class="text-nowrap">${fmtIstante(r.quando)}</td>
        <td><code>${UI.esc(r.azione)}</code>${r.oggetto ? `<br><span class="text-secondary">${UI.esc(r.oggetto)}</span>` : ""}</td>
        <td><span class="badge bg-${COLORE_ESITO[r.esito]}">${r.esito}</span></td>
        <td>${UI.esc(r.email || (r.utente_id ? `utente ${r.utente_id}` : "sistema"))}${r.ruolo ? `<br><span class="text-secondary">${r.ruolo}</span>` : ""}</td>
        <td class="text-nowrap">${UI.esc(r.ip || "—")}</td>
        <td class="dettagli-audit">${r.dettagli ? UI.esc(r.dettagli) : ""}</td></tr>`).join("")
      : '<tr><td colspan="6" class="text-secondary">Nessun evento corrisponde ai filtri.</td></tr>';
  }

  async function caricaSicurezza() {
    try { await Promise.all([caricaAvvisi(), caricaAudit()]); } catch (err) { errore(err); }
  }

  if (utente.ruolo === "admin") {
    $("filtri-audit").addEventListener("submit", async (e) => {
      e.preventDefault();
      try { await caricaAudit(); } catch (err) { errore(err); }
    });

    const modaleAvviso = window.bootstrap.Modal.getOrCreateInstance($("modale-avviso"));
    $("elenco-avvisi").addEventListener("click", (e) => {
      const b = e.target.closest("[data-gestisci]"); if (!b) return;
      const descrizione = new Map(JSON.parse($("elenco-avvisi").dataset.avvisi)).get(Number(b.dataset.gestisci));
      $("avviso-id").value = b.dataset.gestisci;
      $("testo-modale-avviso").textContent = descrizione;
      $("avviso-note").value = "";
      UI.avviso($("esito-avviso"), "");
      modaleAvviso.show();
    });
    $("form-avviso").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await API.gestisciAvviso($("avviso-id").value, $("avviso-note").value);
        modaleAvviso.hide();
        UI.toast("Avviso gestito");
        caricaSicurezza();
      } catch (err) { UI.avviso($("esito-avviso"), err.message, "errore"); }
    });
  }

  caricaDashboard();
  contaAvvisi();
})();
