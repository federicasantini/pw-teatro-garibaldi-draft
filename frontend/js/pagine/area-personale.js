/* Area personale: biglietti con QR code, lista d'attesa, messaggi (accordion) e diritti sui dati personali. */
(() => {
  const utente = UI.richiediAccesso();
  if (!utente) return;
  const $ = (s) => document.getElementById(s);
  const errore = (err) => UI.avviso($("messaggi"), err.message, "errore");
  const COLORE_STATO = { confermata: "success", annullata: "danger", utilizzata: "secondary" };

  const biglietto = (p, futura) => {
    const attivo = futura && p.stato === "confermata";
    return `<article class="card card-bg no-after shadow-sm rounded mb-3 biglietto ${p.stato}">
      <div class="card-body d-sm-flex justify-content-between gap-4">
        <div>
          <span class="badge bg-${COLORE_STATO[p.stato]}">${p.stato}</span>
          <h3 class="card-title h5 mt-2 mb-1">${UI.esc(p.titolo)}</h3>
          <p class="mb-1">${UI.icona("calendar", "icon icon-xs me-1")}${UI.fmtData(p.data_ora)} · ore ${UI.fmtOra(p.data_ora)}</p>
          <p class="text-secondary mb-1">${p.num_posti} ${p.num_posti > 1 ? "posti" : "posto"} in ${UI.esc(p.settore)} · ${UI.esc(p.tariffa)} · ${UI.fmtEuro(p.importo_totale)}</p>
          ${p.richiede_documento && attivo ? `<p class="small text-secondary mb-0">${UI.icona("info-circle", "icon icon-xs me-1")}Porta un documento che dia diritto alla tariffa ${UI.esc(p.tariffa)}.</p>` : ""}
        </div>
        <div class="azioni mt-3 mt-sm-0">
          ${attivo ? `<img class="qr" data-qr="${p.id}" alt="QR code del biglietto ${UI.esc(p.codice)}" width="132" height="132">` : ""}
          <span class="codice">${UI.esc(p.codice)}</span>
          ${attivo ? `<button class="btn btn-outline-danger btn-xs" data-annulla="${p.id}">Annulla prenotazione</button>` : ""}
          ${!futura && p.stato === "utilizzata" ? `<a class="btn btn-outline-primary btn-xs" href="spettacolo.html?id=${p.spettacolo_id ?? ""}">Lascia un feedback</a>` : ""}
        </div>
      </div></article>`;
  };

  // Il QR richiede il token di autenticazione: si scarica con fetch e si mostra come blob
  async function caricaQr() {
    for (const img of document.querySelectorAll("img[data-qr]")) {
      try { img.src = URL.createObjectURL(await API.qrCode(img.dataset.qr)); } catch { img.remove(); }
    }
  }

  const vuoto = (testo) => `<div class="alert alert-info">${testo}</div>`;

  async function caricaBiglietti() {
    const elenco = await API.prenotazioni({ mie: 1 });
    const adesso = new Date();
    const future = elenco.filter((p) => new Date(p.data_ora) >= adesso).reverse();
    const passate = elenco.filter((p) => new Date(p.data_ora) < adesso);
    $("future").innerHTML = future.length ? future.map((p) => biglietto(p, true)).join("")
      : vuoto('Nessuna prenotazione in programma. <a href="index.html">Scopri il cartellone</a>');
    $("passate").innerHTML = passate.length ? passate.map((p) => biglietto(p, false)).join("") : vuoto("Nessuno spettacolo passato.");
    caricaQr();
  }

  async function caricaAttesa() {
    const elenco = await API.listaAttesa();
    $("sezione-attesa").hidden = !elenco.length;
    $("attesa").innerHTML = elenco.map((a) => `<div class="card card-bg no-after shadow-sm rounded mb-3"><div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-3">
        <div><strong>${UI.esc(a.titolo)}</strong> · ${UI.fmtData(a.data_ora)} ore ${UI.fmtOra(a.data_ora)}<br>
          <span class="text-secondary small">${a.num_posti} ${a.num_posti > 1 ? "posti" : "posto"} ·
          ${a.notificata_il ? '<span class="badge bg-success">posti liberati: prenota subito!</span>' : "in attesa"}</span></div>
        <div class="d-flex gap-2">${a.notificata_il ? `<a class="btn btn-primary btn-xs" href="spettacolo.html?id=${a.spettacolo_id}">Prenota</a>` : ""}
          <button class="btn btn-outline-primary btn-xs" data-esci-attesa="${a.replica_id}">Esci dalla lista</button></div>
      </div></div>`).join("");
  }

  async function caricaNotifiche() {
    const elenco = await API.notifiche();
    $("notifiche").innerHTML = elenco.length ? elenco.map((n) => `<div class="accordion-item">
        <h3 class="accordion-header" id="intest-${n.id}">
          <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#notifica-${n.id}"
            aria-expanded="false" aria-controls="notifica-${n.id}">${UI.esc(n.oggetto)}</button>
        </h3>
        <div id="notifica-${n.id}" class="accordion-collapse collapse" role="region" aria-labelledby="intest-${n.id}">
          <div class="accordion-body"><p class="small text-secondary mb-2">${UI.fmtData(n.creata_il, { weekday: undefined })}</p>
            <p class="mb-0">${UI.esc(n.corpo).replace(/\n/g, "<br>")}</p></div>
        </div></div>`).join("")
      : vuoto("Nessun messaggio.");
  }

  async function carica() {
    try { await Promise.all([caricaBiglietti(), caricaAttesa(), caricaNotifiche()]); } catch (err) { errore(err); }
  }

  document.addEventListener("click", async (e) => {
    const annulla = e.target.closest("[data-annulla]");
    const esci = e.target.closest("[data-esci-attesa]");
    if (annulla) {
      const ok = await UI.conferma("La prenotazione verrà annullata e i posti torneranno disponibili.",
        { titolo: "Annullare la prenotazione?", ok: "Annulla prenotazione", pericolo: true });
      if (!ok) return;
      try { await API.annullaPrenotazione(annulla.dataset.annulla); UI.toast("Prenotazione annullata"); carica(); } catch (err) { errore(err); }
    }
    if (esci) {
      try { await API.esciDaAttesa(esci.dataset.esciAttesa); UI.toast("Sei uscito dalla lista d'attesa"); carica(); } catch (err) { errore(err); }
    }
  });

  $("scarica-dati").addEventListener("click", async () => {
    try { await API.esportaDati(); } catch (err) { errore(err); }
  });

  $("form-elimina").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await API.eliminaAccount($("pw-elimina").value);
      API.sessione.cancella();
      location.href = "index.html";
    } catch (err) { UI.avviso($("esito-elimina"), err.message, "errore"); }
  });

  carica();
})();
