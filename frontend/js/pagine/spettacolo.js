/* Dettaglio spettacolo: repliche, prenotazione (settore e tariffa), lista d'attesa, recensioni. */
(() => {
  const id = new URLSearchParams(location.search).get("id");
  const $ = (s) => document.getElementById(s);
  let replicaScelta = null, settoriCorrenti = [], tariffe = [];

  $("num-posti").innerHTML = [1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}">${n}</option>`).join("");

  async function caricaTariffe() {
    tariffe = await API.tariffe();
    $("tariffa").innerHTML = tariffe.map((t) =>
      `<option value="${t.id}">${UI.esc(t.nome)}${t.sconto_pct ? ` (−${t.sconto_pct}%)` : ""}</option>`).join("");
  }

  async function carica() {
    try {
      if (!tariffe.length) await caricaTariffe();
      const s = await API.spettacolo(id);
      document.title = `${s.titolo} · Teatro Garibaldi`;
      $("briciola").textContent = s.titolo;
      $("genere").textContent = UI.GENERI[s.genere];
      $("titolo").textContent = s.titolo;
      $("sottotitolo").textContent = [s.autore, s.compagnia].filter(Boolean).join(" · ");
      $("descrizione").textContent = s.descrizione || "";
      $("durata").textContent = s.durata_minuti ? `Durata: ${s.durata_minuti} minuti circa` : "";
      mostraRepliche(s.repliche);
      $("contenuto").hidden = false;
      caricaRecensioni();
    } catch (err) {
      UI.avviso($("messaggi"), err.message, "errore");
    }
  }

  function mostraRepliche(repliche) {
    const adesso = new Date();
    const future = repliche.filter((r) => new Date(r.data_ora) > adesso && r.stato !== "conclusa");
    if (!future.length) { $("repliche").innerHTML = '<li class="text-secondary">Nessuna replica prenotabile.</li>'; return; }
    $("repliche").innerHTML = future.map((r) => {
      const esaurito = r.posti_disponibili === 0 || r.stato === "annullata";
      const nota = r.stato === "annullata" ? '<span class="badge bg-danger">Annullata</span>'
        : esaurito ? '<span class="badge bg-secondary">Esaurito</span>'
          : `${r.posti_disponibili} posti<br>da ${UI.fmtEuro(r.prezzo_da)}`;
      // pochi posti o esaurito: possibilità di iscriversi alla lista d'attesa
      const attesa = r.stato === "programmata" && r.posti_disponibili < 6 ? `<div class="attesa">
          <label for="attesa-${r.id}">${esaurito ? "Esaurito:" : "Pochi posti:"} avvisami se se ne liberano</label>
          <select id="attesa-${r.id}" aria-label="Posti desiderati">${[1, 2, 3, 4, 5, 6].map((n) => `<option>${n}</option>`).join("")}</select>
          <button type="button" class="btn btn-outline-primary btn-xs" data-attesa="${r.id}">Lista d'attesa</button></div>` : "";
      return `<li><button type="button" class="replica" data-id="${r.id}" aria-pressed="false" ${esaurito ? "disabled" : ""}>
          <span><strong>${UI.fmtData(r.data_ora)}</strong><br><span class="text-secondary small">ore ${UI.fmtOra(r.data_ora)} · ${UI.esc(r.sala)}</span></span>
          <span class="text-secondary nota-replica">${nota}</span></button>${attesa}</li>`;
    }).join("");
  }

  $("repliche").addEventListener("click", async (e) => {
    const attesa = e.target.closest("[data-attesa]");
    if (attesa) return entraInAttesa(Number(attesa.dataset.attesa));
    const b = e.target.closest("button[data-id]"); if (!b) return;
    $("repliche").querySelectorAll("button[data-id]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    replicaScelta = Number(b.dataset.id);
    UI.avviso($("esito"), "");
    try {
      const disp = await API.disponibilita(replicaScelta);
      settoriCorrenti = disp.settori;
      $("settori").innerHTML = disp.settori.map((s, i) => {
        const perc = Math.round(100 * s.posti_occupati / s.posti_totali);
        const libero = s.posti_disponibili > 0;
        return `<div class="form-check settore">
            <input type="radio" name="settore" id="settore-${s.settore_id}" value="${s.settore_id}" ${libero ? "" : "disabled"} ${i === 0 && libero ? "checked" : ""}>
            <label for="settore-${s.settore_id}" class="settore-etichetta">
              <span><strong>${UI.esc(s.settore)}</strong> <span class="text-secondary small">· ${s.posti_disponibili} liberi</span>
                <span class="progress d-flex" aria-hidden="true"><span class="progress-bar bg-primary" style="width:${perc}%"></span></span></span>
              <strong>${UI.fmtEuro(s.prezzo)}</strong>
            </label></div>`;
      }).join("");
      if (!$("settori").querySelector("input:checked")) $("settori").querySelector("input:not(:disabled)")?.click();
      $("form-prenota").hidden = false;
      aggiornaTotale();
    } catch (err) { UI.avviso($("esito"), err.message, "errore"); }
  });

  async function entraInAttesa(replicaId) {
    if (!API.sessione.utente()) { location.href = `accedi.html?torna=${encodeURIComponent("spettacolo.html?id=" + id)}`; return; }
    try {
      const r = await API.entraInAttesa(replicaId, Number($(`attesa-${replicaId}`).value));
      UI.avviso($("esito"), `Sei in lista d'attesa (posizione ${r.posizione}). Ti avviseremo nei tuoi messaggi se si liberano posti.`, "ok");
    } catch (err) { UI.avviso($("esito"), err.message, "errore"); }
  }

  // Stesso calcolo del server: prezzo in centesimi, sconto arrotondato al centesimo
  const prezzoScontatoCent = (prezzo, sconto) => Math.floor((Math.round(prezzo * 100) * (100 - sconto) + 50) / 100);

  function aggiornaTotale() {
    const sel = $("settori").querySelector("input:checked");
    const settore = settoriCorrenti.find((s) => String(s.settore_id) === sel?.value);
    const tariffa = tariffe.find((t) => String(t.id) === $("tariffa").value) || { sconto_pct: 0 };
    const cent = settore ? prezzoScontatoCent(settore.prezzo, tariffa.sconto_pct) * Number($("num-posti").value) : 0;
    $("totale").textContent = UI.fmtEuro(cent / 100);
    $("nota-tariffa").hidden = !tariffa.richiede_documento;
    $("nota-tariffa").textContent = tariffa.richiede_documento
      ? `${tariffa.nome}: ${tariffa.descrizione || ""}. All'ingresso verrà richiesto un documento.` : "";
  }
  $("settori").addEventListener("change", aggiornaTotale);
  $("num-posti").addEventListener("change", aggiornaTotale);
  $("tariffa").addEventListener("change", aggiornaTotale);

  $("form-prenota").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!API.sessione.utente()) { location.href = `accedi.html?torna=${encodeURIComponent("spettacolo.html?id=" + id)}`; return; }
    const sel = $("settori").querySelector("input:checked");
    if (!sel) return UI.avviso($("esito"), "Seleziona un settore", "errore");
    $("conferma").disabled = true;
    try {
      const p = await API.prenota({ replica_id: replicaScelta, settore_id: Number(sel.value),
        num_posti: Number($("num-posti").value), tariffa_id: Number($("tariffa").value) });
      $("form-prenota").hidden = true;
      $("esito").innerHTML = `<div class="alert alert-success mt-4" role="status">
          <h3 class="h5 alert-heading">Prenotazione confermata!</h3>
          <p class="mb-1">Codice d'ingresso: <strong class="codice-esito">${UI.esc(p.codice)}</strong></p>
          <p class="mb-2">${p.num_posti} ${p.num_posti > 1 ? "posti" : "posto"} in ${UI.esc(p.settore)} · ${UI.esc(p.tariffa)} · ${UI.fmtEuro(p.importo_totale)}</p>
          <a href="area-personale.html">Vai ai miei biglietti (con QR code)</a></div>`;
      carica();
    } catch (err) {
      UI.avviso($("esito"), err.message, "errore");
    } finally {
      $("conferma").disabled = false;
    }
  });

  async function caricaRecensioni() {
    const elenco = await API.feedback(id);
    if (elenco.length) {
      const media = elenco.reduce((a, f) => a + f.voto, 0) / elenco.length;
      $("riepilogo-voti").innerHTML = `${UI.stelle(media.toFixed(1))} ${media.toFixed(1).replace(".", ",")} su 5 · ${elenco.length} recensioni`;
    } else $("riepilogo-voti").textContent = "Ancora nessuna recensione.";
    $("recensioni").innerHTML = elenco.map((f) => `<div class="recensione">${UI.stelle(f.voto)}
        <strong class="ms-1">${UI.esc(f.autore)}</strong> <span class="text-secondary small">· ${UI.fmtData(f.data, { weekday: undefined })}</span>
        ${f.commento ? `<p class="mt-1 mb-0">${UI.esc(f.commento)}</p>` : ""}</div>`).join("");
    mostraFormFeedback();
  }

  // Valutazione con il componente "rating" del kit (radio + icone a stella)
  function mostraFormFeedback() {
    if (!API.sessione.utente()) { $("form-feedback-wrap").innerHTML = ""; return; }
    const stella = (v) => `<input type="radio" id="voto-${v}" name="voto" value="${v}">
        <label class="full rating-star" for="voto-${v}">${UI.icona("star-full", "icon icon-sm")}<span class="visually-hidden">Valuta ${v} stelle su 5</span></label>`;
    $("form-feedback-wrap").innerHTML = `
      <button class="btn btn-outline-primary btn-sm mb-3" type="button" data-bs-toggle="collapse" data-bs-target="#pannello-feedback"
        aria-expanded="false" aria-controls="pannello-feedback">Hai visto lo spettacolo? Lascia un feedback</button>
      <div class="collapse" id="pannello-feedback">
        <form id="form-feedback" class="card card-body shadow-sm mb-4">
          <p class="small text-secondary mb-1" aria-hidden="true">Il tuo voto</p>
          <fieldset class="rating">
            <legend class="visually-hidden">Il tuo voto da 1 a 5 stelle</legend>
            ${[5, 4, 3, 2, 1].map(stella).join("")}
          </fieldset>
          <div class="form-group mt-4 mb-3">
            <label for="commento" class="active">Commento (facoltativo)</label>
            <textarea id="commento" class="form-control" rows="3" maxlength="1000"></textarea>
          </div>
          <div><button type="submit" class="btn btn-primary btn-sm">Invia</button></div>
          <div id="esito-feedback"></div>
        </form>
      </div>`;
    $("form-feedback").addEventListener("submit", async (e) => {
      e.preventDefault();
      const voto = e.target.querySelector("input[name=voto]:checked");
      if (!voto) return UI.avviso($("esito-feedback"), "Seleziona un voto da 1 a 5", "errore");
      try {
        await API.lasciaFeedback({ spettacolo_id: Number(id), voto: Number(voto.value), commento: $("commento").value });
        UI.toast("Grazie per il tuo feedback!");
        caricaRecensioni();
      } catch (err) { UI.avviso($("esito-feedback"), err.message, "errore"); }
    });
  }

  carica();
})();
