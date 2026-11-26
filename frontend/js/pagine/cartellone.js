/* Cartellone: elenco degli spettacoli (card del kit) con ricerca e filtro per genere. */
(() => {
  const stato = { genere: "", q: "" };
  const contGeneri = document.getElementById("generi");
  const cartellone = document.getElementById("cartellone");

  // Pulsanti filtro per genere (stato selezionato: btn-primary + aria-pressed)
  const pulsante = (v, t) => `<button type="button" class="btn btn-sm ${v === stato.genere ? "btn-primary" : "btn-outline-primary"}"
      data-genere="${v}" aria-pressed="${v === stato.genere}">${t}</button>`;
  const disegnaFiltri = () => {
    contGeneri.innerHTML = [["", "Tutti"], ...Object.entries(UI.GENERI)].map(([v, t]) => pulsante(v, t)).join("");
  };
  disegnaFiltri();
  contGeneri.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    stato.genere = b.dataset.genere;
    disegnaFiltri();
    contGeneri.querySelector(`[data-genere="${stato.genere}"]`).focus();
    carica();
  });

  // Ricerca con debounce: evita una richiesta per ogni tasto premuto
  let timer;
  document.getElementById("ricerca").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { stato.q = e.target.value.trim(); carica(); }, 250);
  });
  document.getElementById("filtri").addEventListener("submit", (e) => e.preventDefault());

  function scheda(s) {
    const quando = s.prossima_replica
      ? `${UI.icona("calendar", "icon icon-xs me-1")}${UI.fmtData(s.prossima_replica, { weekday: "short", year: undefined })} · ore ${UI.fmtOra(s.prossima_replica)}`
      : "Nessuna replica in programma";
    const voto = s.voto_medio
      ? `${UI.stelle(s.voto_medio)} <span class="small text-secondary">${String(s.voto_medio).replace(".", ",")} (${s.num_recensioni})</span>`
      : '<span class="small text-secondary">Nessuna recensione</span>';
    return `<div class="col-12 col-md-6 col-lg-4">
        <div class="card-wrapper card-space">
          <article class="card card-bg shadow-sm rounded scheda-spettacolo">
            <div class="locandina ${UI.esc(s.genere)}" aria-hidden="true">${UI.GENERI[s.genere] || ""}</div>
            <div class="card-body">
              <div class="category-top">
                <span class="category">${UI.GENERI[s.genere] || ""}</span>
                <span class="data">${s.durata_minuti ? `${s.durata_minuti} min` : ""}</span>
              </div>
              <h3 class="card-title h5">${UI.esc(s.titolo)}</h3>
              <p class="card-text font-sans-serif">${UI.esc(s.autore || "")}${s.compagnia ? " · " + UI.esc(s.compagnia) : ""}</p>
              <p class="card-text font-sans-serif small mb-2">${quando}</p>
              <div class="mb-4">${voto}</div>
              <a class="read-more" href="spettacolo.html?id=${s.id}">
                <span class="text">${s.prossima_replica ? "Prenota" : "Dettagli"}</span>
                <span class="visually-hidden">${UI.esc(s.titolo)}</span>
                ${UI.icona("arrow-right", "icon")}
              </a>
            </div>
          </article>
        </div>
      </div>`;
  }

  async function carica() {
    try {
      const elenco = await API.spettacoli({ genere: stato.genere, q: stato.q });
      cartellone.innerHTML = elenco.length ? elenco.map(scheda).join("")
        : '<div class="col-12"><div class="alert alert-info">Nessuno spettacolo corrisponde alla ricerca.</div></div>';
    } catch (err) {
      UI.avviso(document.getElementById("messaggi"), err.message, "errore");
    }
  }
  carica();
})();
