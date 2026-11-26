/* Accesso e registrazione (schede "nav-tabs" del kit). */
(() => {
  const $ = (s) => document.getElementById(s);
  const torna = new URLSearchParams(location.search).get("torna");
  // Accetta solo destinazioni interne (evita open redirect)
  const destinazione = (u) => torna && /^[\w-]+\.html(\?[\w=&%-]*)?$/.test(torna) ? torna
    : (u.ruolo === "spettatore" ? "index.html" : "gestione.html");

  const schede = document.querySelectorAll("[data-scheda]");
  function mostra(nome) {
    schede.forEach((b) => {
      const attiva = b.dataset.scheda === nome;
      b.classList.toggle("active", attiva);
      b.setAttribute("aria-selected", attiva);
      b.tabIndex = attiva ? 0 : -1;
    });
    $("form-login").hidden = nome !== "login";
    $("form-registrazione").hidden = nome !== "registrazione";
  }
  schede.forEach((b) => b.addEventListener("click", () => mostra(b.dataset.scheda)));
  // navigazione da tastiera tra le schede (frecce sinistra/destra)
  document.querySelector(".nav-tabs").addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const prossima = [...schede].find((b) => b.getAttribute("aria-selected") !== "true");
    mostra(prossima.dataset.scheda);
    prossima.focus();
  });
  if (location.hash === "#registrazione") mostra("registrazione");

  $("form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const { token, utente } = await API.login($("l-email").value, $("l-password").value);
      API.sessione.salva(token, utente);
      location.href = destinazione(utente);
    } catch (err) { UI.avviso($("esito-login"), err.message, "errore"); }
  });

  $("form-registrazione").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const { token, utente } = await API.registrazione({
        nome: $("r-nome").value, cognome: $("r-cognome").value, email: $("r-email").value,
        password: $("r-password").value, consenso_privacy: $("r-privacy").checked,
      });
      API.sessione.salva(token, utente);
      location.href = destinazione(utente);
    } catch (err) { UI.avviso($("esito-reg"), err.message, "errore"); }
  });
})();
