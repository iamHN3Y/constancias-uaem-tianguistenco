/* ============================================================
   Recorrido guiado (coach marks) — sin dependencias.

   Los pasos NO se escriben aquí: salen de los elementos de la pantalla
   marcados con data-recorrido="N" (macro ayuda(..., paso=N) en las
   plantillas), usando su mismo título y texto de ayuda. Así el recorrido
   y el modo ayuda nunca se contradicen.

   La página activa el recorrido con:  window.TOUR = { key: "home-admin" }
   · Arranca solo la primera vez que alguien abre esa pantalla en este
     equipo (se recuerda en localStorage, si está disponible).
   · Se relanza con window.iniciarRecorrido() (botón de la banda del modo
     ayuda) o abriendo la pantalla con ?recorrido=1 (enlaces del centro
     de ayuda).
   · El último paso siempre señala el botón «Modo ayuda», para que quien
     lo termine sepa dónde volver a preguntar.
   ============================================================ */
(function () {
  "use strict";

  var SEEN_PREFIX = "tour_seen_";
  var PAD = 8;

  var steps = [];
  var idx = 0;
  var key = "";
  var dom = null;
  var previoFoco = null;

  function leerVisto(k) { try { return localStorage.getItem(SEEN_PREFIX + k); } catch (e) { return "1"; } }
  function marcarVisto(k) { try { localStorage.setItem(SEEN_PREFIX + k, "1"); } catch (e) { /* sin almacenamiento */ } }

  function recolectarPasos() {
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-recorrido]"))
      .filter(function (el) { return el.getClientRects().length; });
    els.sort(function (a, b) {
      return Number(a.getAttribute("data-recorrido")) - Number(b.getAttribute("data-recorrido"));
    });
    var pasos = els.map(function (el) {
      return { el: el, title: el.getAttribute("data-ayuda"), text: el.getAttribute("data-ayuda-texto") };
    });
    var btn = document.getElementById("btnModoAyuda");
    if (pasos.length && btn) {
      pasos.push({
        el: btn,
        title: "¿Se te olvidó algo? Usa el modo ayuda",
        text: "No necesitas repetir este recorrido. Pulsa «Modo ayuda» (o la tecla ?) y haz clic sobre cualquier parte de la pantalla para ver qué hace. En «Guías» están los manuales paso a paso.",
      });
    }
    return pasos;
  }

  function build() {
    var overlay = document.createElement("div");
    overlay.className = "tour-overlay";
    overlay.innerHTML =
      '<div class="tour-hole"></div>' +
      '<div class="tour-pop" role="dialog" aria-modal="true" aria-labelledby="tourTitulo" aria-describedby="tourTexto">' +
        '<div class="tour-progress"><span class="tour-paso"></span><span class="tour-barra"><span></span></span></div>' +
        '<h3 class="tour-title" id="tourTitulo"></h3>' +
        '<p class="tour-text" id="tourTexto"></p>' +
        '<div class="tour-actions">' +
          '<button type="button" class="btn-text tour-skip">Saltar recorrido</button>' +
          '<span style="flex:1"></span>' +
          '<button type="button" class="btn-ghost tour-prev">Anterior</button>' +
          '<button type="button" class="tour-next">Siguiente</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    dom = {
      overlay: overlay,
      hole: overlay.querySelector(".tour-hole"),
      pop: overlay.querySelector(".tour-pop"),
      paso: overlay.querySelector(".tour-paso"),
      barra: overlay.querySelector(".tour-barra span"),
      title: overlay.querySelector(".tour-title"),
      text: overlay.querySelector(".tour-text"),
      skip: overlay.querySelector(".tour-skip"),
      prev: overlay.querySelector(".tour-prev"),
      next: overlay.querySelector(".tour-next"),
    };

    dom.skip.addEventListener("click", finish);
    dom.prev.addEventListener("click", function () { go(idx - 1); });
    dom.next.addEventListener("click", function () {
      if (idx >= steps.length - 1) finish(); else go(idx + 1);
    });
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    document.addEventListener("keydown", onKey, true);
  }

  function onKey(e) {
    if (!dom) return;
    if (e.key === "Escape") { e.preventDefault(); finish(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); (idx >= steps.length - 1) ? finish() : go(idx + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); go(idx - 1); }
  }

  function go(i) {
    idx = Math.max(0, Math.min(i, steps.length - 1));
    render();
  }

  function render() {
    var step = steps[idx];
    dom.paso.textContent = "Paso " + (idx + 1) + " de " + steps.length;
    dom.barra.style.width = ((idx + 1) / steps.length * 100) + "%";
    dom.title.textContent = step.title || "";
    dom.text.textContent = step.text || "";
    dom.prev.style.visibility = idx === 0 ? "hidden" : "visible";
    dom.next.textContent = idx >= steps.length - 1 ? "Entendido" : "Siguiente";

    var sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    step.el.scrollIntoView({ block: "center", inline: "nearest", behavior: sinMovimiento ? "auto" : "smooth" });
    position();
    setTimeout(position, 350);
    dom.next.focus({ preventScroll: true });
  }

  function position() {
    if (!dom) return;
    var r = steps[idx].el.getBoundingClientRect();

    dom.hole.style.left = (r.left - PAD) + "px";
    dom.hole.style.top = (r.top - PAD) + "px";
    dom.hole.style.width = (r.width + PAD * 2) + "px";
    dom.hole.style.height = (r.height + PAD * 2) + "px";

    var popW = dom.pop.offsetWidth;
    var popH = dom.pop.offsetHeight;
    var top = r.bottom + 14;
    if (top + popH > window.innerHeight - 10) {
      var above = r.top - popH - 14;
      top = above >= 10 ? above : Math.max(10, window.innerHeight - popH - 10);
    }
    var left = r.left + r.width / 2 - popW / 2;
    left = Math.max(10, Math.min(left, window.innerWidth - popW - 10));
    dom.pop.style.top = top + "px";
    dom.pop.style.left = left + "px";
  }

  function start() {
    if (dom) return;
    if (window.modoAyuda) window.modoAyuda.desactivar();
    steps = recolectarPasos();
    if (!steps.length) return;
    key = (window.TOUR && window.TOUR.key) || "default";
    idx = 0;
    previoFoco = document.activeElement;
    build();
    render();
  }

  function finish() {
    if (key) marcarVisto(key);
    if (!dom) return;
    window.removeEventListener("resize", position);
    window.removeEventListener("scroll", position, true);
    document.removeEventListener("keydown", onKey, true);
    dom.overlay.remove();
    dom = null;
    if (previoFoco && previoFoco.focus) previoFoco.focus({ preventScroll: true });
  }

  function init() {
    var cfg = window.TOUR;
    if (!cfg || !cfg.key) return;
    var forzado = /[?&]recorrido=1\b/.test(location.search);
    if (forzado || !leerVisto(cfg.key)) {
      // pequeño retraso: deja asentar el layout (fuentes, iframe, etc.)
      setTimeout(start, 450);
    }
  }

  window.iniciarRecorrido = start;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
