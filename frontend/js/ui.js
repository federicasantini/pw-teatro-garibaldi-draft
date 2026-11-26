/* =====================================================================
   Componenti di interfaccia condivisi, costruiti con il kit Bootstrap Italia
   di Designers Italia: header (slim, centrale, navbar), footer, skiplink,
   torna su, alert, notifiche, finestra modale di conferma, icone e formattazione.
   Header e footer sono inseriti subito (non al DOMContentLoaded) così i plugin
   del kit li trovano già nel documento quando si inizializzano.
   ===================================================================== */
const UI = (() => {
  const GENERI = { prosa: "Prosa", lirica: "Lirica", danza: "Danza", musica: "Musica", ragazzi: "Ragazzi" };
  const SPRITE = "vendor/bootstrap-italia/svg/sprites.svg";

  /** Icona del kit (sprite SVG): icona("calendar", "icon icon-sm icon-primary") */
  const icona = (nome, classi = "icon icon-sm") =>
    `<svg class="${classi}" aria-hidden="true" focusable="false"><use href="${SPRITE}#it-${nome}"></use></svg>`;

  // Escape dell'HTML: impedisce l'iniezione di codice (XSS) nei dati mostrati
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const fmtData = (iso, opzioni = {}) => new Date(iso).toLocaleDateString("it-IT", {
    weekday: "short", day: "numeric", month: "long", year: "numeric", ...opzioni });
  const fmtOra = (iso) => new Date(iso).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  const fmtEuro = (n) => Number(n || 0).toLocaleString("it-IT", { style: "currency", currency: "EUR" });
  const fmtNum = (n) => Number(n || 0).toLocaleString("it-IT");
  const stelle = (voto) => {
    if (voto == null) return "";
    const pieno = Math.round(voto);
    const s = [1, 2, 3, 4, 5].map((i) => icona(i <= pieno ? "star-full" : "star-outline", "icon icon-xs icon-primary")).join("");
    return `<span class="stelle" role="img" aria-label="Voto ${esc(voto)} su 5">${s}</span>`;
  };

  const LOGO = `<svg class="icon logo-teatro" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <path d="M4 6h32v4c-4 0-6 3-6 8v16h-4V18c0-6-3-8-6-8s-6 2-6 8v16h-4V18c0-5-2-8-6-8z" fill="currentColor"/>
      <circle cx="20" cy="22" r="3" fill="currentColor"/></svg>`;

  // ------------------------------------------------------------------ header
  function testata() {
    const utente = API.sessione.utente();
    const qui = location.pathname.split("/").pop() || "index.html";
    const voce = (href, testo, nomeIcona) => `<li class="nav-item">
        <a class="nav-link${qui === href ? " active" : ""}" href="${href}"${qui === href ? ' aria-current="page"' : ""}>
          ${icona(nomeIcona, "icon icon-sm me-1 d-lg-none")}<span>${testo}</span></a></li>`;
    let menu = voce("index.html", "Cartellone", "calendar");
    if (utente) {
      menu += voce("area-personale.html", "I miei biglietti", "card");
      if (utente.ruolo !== "spettatore") menu += voce("gestione.html", "Gestione", "settings");
    }

    const zonaUtente = utente
      ? `<div class="nav-item dropdown">
          <button class="btn btn-primary btn-icon btn-full dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false" id="menu-utente">
            <span class="rounded-icon">${icona("user", "icon icon-primary")}</span>
            <span class="d-none d-lg-block">${esc(utente.nome)} ${esc(utente.cognome || "")}</span>
            ${icona("expand", "icon icon-white d-none d-lg-block")}
          </button>
          <div class="dropdown-menu dropdown-menu-end" aria-labelledby="menu-utente">
            <div class="link-list-wrapper"><ul class="link-list">
              <li><a class="dropdown-item list-item" href="area-personale.html"><span>I miei biglietti</span></a></li>
              ${utente.ruolo !== "spettatore" ? '<li><a class="dropdown-item list-item" href="gestione.html"><span>Area gestione</span></a></li>' : ""}
              <li><span class="divider"></span></li>
              <li><button type="button" class="dropdown-item list-item btn-link" id="esci">${icona("logout", "icon icon-sm icon-primary me-1")}<span>Esci</span></button></li>
            </ul></div>
          </div>
        </div>`
      : `<a class="btn btn-primary btn-icon btn-full" href="accedi.html">
          <span class="rounded-icon">${icona("user", "icon icon-primary")}</span>
          <span class="d-none d-lg-block">Accedi all'area personale</span></a>`;

    const el = document.createElement("div");
    el.innerHTML = `
      <div class="skiplinks">
        <a class="visually-hidden-focusable" href="#principale">Vai al contenuto principale</a>
        <a class="visually-hidden-focusable" href="#pie-di-pagina">Vai al piè di pagina</a>
      </div>
      <header class="it-header-wrapper">
        <div class="it-header-slim-wrapper">
          <div class="container"><div class="row"><div class="col-12">
            <div class="it-header-slim-wrapper-content">
              <a class="d-lg-block navbar-brand" href="index.html">Comune di Mazara del Vallo</a>
              <div class="it-header-slim-right-zone">${zonaUtente}</div>
            </div>
          </div></div></div>
        </div>
        <div class="it-nav-wrapper">
          <div class="it-header-center-wrapper">
            <div class="container"><div class="row"><div class="col-12">
              <div class="it-header-center-content-wrapper">
                <div class="it-brand-wrapper">
                  <a href="index.html">${LOGO}
                    <div class="it-brand-text">
                      <div class="it-brand-title">Teatro Garibaldi</div>
                      <div class="it-brand-tagline d-none d-md-block">Teatro comunale · Stagione 2026/27</div>
                    </div>
                  </a>
                </div>
              </div>
            </div></div></div>
          </div>
          <div class="it-header-navbar-wrapper">
            <div class="container"><div class="row"><div class="col-12">
              <nav class="navbar navbar-expand-lg has-megamenu" aria-label="Navigazione principale">
                <button class="custom-navbar-toggler" type="button" aria-controls="menu-principale" aria-expanded="false"
                  aria-label="Mostra o nascondi la navigazione" data-bs-toggle="navbarcollapsible" data-bs-target="#menu-principale">
                  ${icona("burger", "icon")}
                </button>
                <div class="navbar-collapsable" id="menu-principale" style="display: none;">
                  <div class="overlay" style="display: none;"></div>
                  <div class="close-div">
                    <button class="btn close-menu" type="button"><span class="visually-hidden">Nascondi la navigazione</span>${icona("close-big", "icon")}</button>
                  </div>
                  <div class="menu-wrapper"><ul class="navbar-nav">${menu}</ul></div>
                </div>
              </nav>
            </div></div></div>
          </div>
        </div>
      </header>`;
    document.body.prepend(...el.children);
    document.getElementById("esci")?.addEventListener("click", async () => {
      try { await API.logout(); } catch {}
      API.sessione.cancella();
      location.href = "index.html";
    });
  }

  // ------------------------------------------------------------------ footer
  function piede() {
    const el = document.createElement("div");
    el.innerHTML = `
      <footer class="it-footer" id="pie-di-pagina">
        <div class="it-footer-main">
          <div class="container">
            <section>
              <div class="row clearfix"><div class="col-sm-12">
                <div class="it-brand-wrapper">
                  <a href="index.html">${LOGO}
                    <div class="it-brand-text">
                      <h2 class="no_toc">Teatro Garibaldi</h2>
                      <h3 class="no_toc d-none d-md-block">Teatro comunale · Comune di Mazara del Vallo</h3>
                    </div>
                  </a>
                </div>
              </div></div>
            </section>
            <section class="py-4 border-white border-top">
              <div class="row">
                <div class="col-lg-4 col-md-4 pb-2">
                  <h4><span class="text-white">Biglietteria</span></h4>
                  <p>Da martedì a sabato<br>10:00–13:00 e 16:00–19:00</p>
                  <p>Pagamento al ritiro dei biglietti.</p>
                </div>
                <div class="col-lg-4 col-md-4 pb-2">
                  <h4><span class="text-white">Servizi online</span></h4>
                  <div class="link-list-wrapper"><ul class="footer-list link-list clearfix">
                    <li><a class="list-item" href="index.html">Cartellone e prenotazioni</a></li>
                    <li><a class="list-item" href="area-personale.html">I miei biglietti</a></li>
                    <li><a class="list-item" href="accedi.html">Accedi o registrati</a></li>
                  </ul></div>
                </div>
                <div class="col-lg-4 col-md-4 pb-2">
                  <h4><span class="text-white">Informazioni</span></h4>
                  <div class="link-list-wrapper"><ul class="footer-list link-list clearfix">
                    <li><a class="list-item" href="privacy.html">Informativa sulla privacy</a></li>
                    <li><a class="list-item" href="accessibilita.html">Dichiarazione di accessibilità</a></li>
                  </ul></div>
                </div>
              </div>
            </section>
          </div>
        </div>
        <div class="it-footer-small-prints clearfix">
          <div class="container">
            <h3 class="visually-hidden">Collegamenti utili</h3>
            <ul class="it-footer-small-prints-list list-inline mb-0 d-flex flex-column flex-md-row">
              <li class="list-inline-item"><a href="privacy.html">Privacy</a></li>
              <li class="list-inline-item"><a href="accessibilita.html">Dichiarazione di accessibilità</a></li>
              <li class="list-inline-item"><span class="text-white">Prototipo didattico · dati simulati</span></li>
            </ul>
          </div>
        </div>
      </footer>
      <a href="#" aria-hidden="true" tabindex="-1" data-bs-toggle="backtotop" class="back-to-top shadow">
        ${icona("arrow-up", "icon icon-light")}<span class="visually-hidden">Torna su</span></a>`;
    document.body.append(...el.children);
  }

  // --------------------------------------------------------- avvisi e notifiche
  const TIPO_ALERT = { ok: "success", errore: "danger", info: "info", attenzione: "warning" };

  /** Alert del kit dentro un contenitore; testo vuoto = rimuove l'avviso. */
  function avviso(contenitore, testo, tipo = "info") {
    contenitore.innerHTML = testo
      ? `<div class="alert alert-${TIPO_ALERT[tipo] || tipo} mt-3" role="${tipo === "errore" ? "alert" : "status"}">${esc(testo)}</div>`
      : "";
  }

  /** Notifica temporanea (componente "notification" del kit). */
  function toast(testo, tipo = "success") {
    let el = document.getElementById("notifica");
    if (!el) {
      el = document.createElement("div");
      el.id = "notifica";
      el.setAttribute("role", "status");
      el.setAttribute("aria-labelledby", "notifica-titolo");
      document.body.append(el);
    }
    const nomeIcona = tipo === "error" ? "close-circle" : "check-circle";
    el.className = `notification with-icon bottom-fix ${tipo}`;
    el.innerHTML = `<h2 class="h5" id="notifica-titolo">${icona(nomeIcona, "icon")}${esc(testo)}</h2>`;
    window.bootstrap.Notification.getOrCreateInstance(el).show(3500);
  }

  /** Finestra modale di conferma del kit: restituisce una Promise<boolean>. */
  function conferma(testo, { titolo = "Conferma", ok = "Conferma", pericolo = false } = {}) {
    let el = document.getElementById("modale-conferma");
    if (!el) {
      el = document.createElement("div");
      el.className = "modal fade";
      el.id = "modale-conferma";
      el.tabIndex = -1;
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-labelledby", "modale-conferma-titolo");
      el.innerHTML = `<div class="modal-dialog modal-dialog-centered" role="document"><div class="modal-content">
          <div class="modal-header"><h2 class="modal-title h5" id="modale-conferma-titolo"></h2></div>
          <div class="modal-body"><p></p></div>
          <div class="modal-footer">
            <button class="btn btn-outline-primary btn-sm" type="button" data-bs-dismiss="modal">Annulla</button>
            <button class="btn btn-primary btn-sm" type="button" data-conferma>Conferma</button>
          </div></div></div>`;
      document.body.append(el);
    }
    el.querySelector(".modal-title").textContent = titolo;
    el.querySelector(".modal-body p").textContent = testo;
    const bottone = el.querySelector("[data-conferma]");
    bottone.textContent = ok;
    bottone.className = `btn btn-${pericolo ? "danger" : "primary"} btn-sm`;
    const modale = window.bootstrap.Modal.getOrCreateInstance(el);
    return new Promise((risolvi) => {
      let esito = false;
      bottone.onclick = () => { esito = true; modale.hide(); };
      el.addEventListener("hidden.bs.modal", () => risolvi(esito), { once: true });
      modale.show();
    });
  }

  /** Reindirizza al login se l'utente non è autenticato o non ha il ruolo richiesto. */
  function richiediAccesso(ruoli) {
    const utente = API.sessione.utente();
    if (!utente) { location.href = `accedi.html?torna=${encodeURIComponent(location.pathname.split("/").pop() + location.search)}`; return null; }
    if (ruoli && !ruoli.includes(utente.ruolo)) { location.href = "index.html"; return null; }
    return utente;
  }

  testata();
  piede();

  return { GENERI, icona, esc, fmtData, fmtOra, fmtEuro, fmtNum, stelle, avviso, toast, conferma, richiediAccesso };
})();
