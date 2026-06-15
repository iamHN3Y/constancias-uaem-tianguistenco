/* ============================================================
   Tour guiado (coach marks) — self-contained, sin dependencias.

   Cada página define antes de cargar este script:
     window.TOUR = {
       key: "home",                       // id único para recordar si ya se vio
       steps: [
         { sel: "#cuenta", title: "...", text: "..." },
         ...
       ]
     };
   Los pasos cuyo elemento no exista en la página se omiten solos
   (sirve para diferencias admin/invitado). El tour arranca solo la
   primera vez (localStorage) y cualquier botón [data-tour] lo relanza.
   ============================================================ */
(function () {
  const SEEN_PREFIX = "tour_seen_";
  const PAD = 8;

  let steps = [];
  let idx = 0;
  let key = "";
  let dom = null;

  function build() {
    const overlay = document.createElement("div");
    overlay.className = "tour-overlay";
    overlay.innerHTML =
      '<div class="tour-hole"></div>' +
      '<div class="tour-pop" role="dialog" aria-modal="true">' +
        '<div class="tour-progress"></div>' +
        '<h3 class="tour-title"></h3>' +
        '<p class="tour-text"></p>' +
        '<div class="tour-actions">' +
          '<button type="button" class="btn-text tour-skip">Saltar</button>' +
          '<span style="flex:1"></span>' +
          '<button type="button" class="btn-ghost tour-prev">Anterior</button>' +
          '<button type="button" class="tour-next">Siguiente</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    dom = {
      overlay,
      hole: overlay.querySelector(".tour-hole"),
      pop: overlay.querySelector(".tour-pop"),
      progress: overlay.querySelector(".tour-progress"),
      title: overlay.querySelector(".tour-title"),
      text: overlay.querySelector(".tour-text"),
      skip: overlay.querySelector(".tour-skip"),
      prev: overlay.querySelector(".tour-prev"),
      next: overlay.querySelector(".tour-next"),
    };

    dom.skip.addEventListener("click", finish);
    dom.prev.addEventListener("click", () => go(idx - 1));
    dom.next.addEventListener("click", () => {
      if (idx >= steps.length - 1) finish();
      else go(idx + 1);
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
    const step = steps[idx];
    const el = document.querySelector(step.sel);
    if (!el) { // por si el elemento desapareció
      if (idx < steps.length - 1) return go(idx + 1);
      return finish();
    }
    dom.progress.textContent = "Paso " + (idx + 1) + " de " + steps.length;
    dom.title.textContent = step.title || "";
    dom.text.textContent = step.text || "";
    dom.prev.style.visibility = idx === 0 ? "hidden" : "visible";
    dom.next.textContent = idx >= steps.length - 1 ? "Entendido" : "Siguiente";

    el.scrollIntoView({ block: "center", inline: "nearest" });
    position();
  }

  function position() {
    if (!dom) return;
    const step = steps[idx];
    const el = document.querySelector(step.sel);
    if (!el) return;
    const r = el.getBoundingClientRect();

    dom.hole.style.left = (r.left - PAD) + "px";
    dom.hole.style.top = (r.top - PAD) + "px";
    dom.hole.style.width = (r.width + PAD * 2) + "px";
    dom.hole.style.height = (r.height + PAD * 2) + "px";

    const popW = dom.pop.offsetWidth;
    const popH = dom.pop.offsetHeight;
    let top = r.bottom + 14;
    if (top + popH > window.innerHeight - 10) {
      const above = r.top - popH - 14;
      top = above >= 10 ? above : Math.max(10, window.innerHeight - popH - 10);
    }
    let left = r.left + r.width / 2 - popW / 2;
    left = Math.max(10, Math.min(left, window.innerWidth - popW - 10));
    dom.pop.style.top = top + "px";
    dom.pop.style.left = left + "px";
  }

  function start(force) {
    const cfg = window.TOUR;
    if (!cfg || !cfg.steps) return;
    steps = cfg.steps.filter((s) => document.querySelector(s.sel));
    if (!steps.length) return;
    key = cfg.key || "default";
    idx = 0;
    if (!dom) build();
    dom.overlay.style.display = "block";
    render();
  }

  function finish() {
    if (key) localStorage.setItem(SEEN_PREFIX + key, "1");
    teardown();
  }

  function teardown() {
    if (!dom) return;
    window.removeEventListener("resize", position);
    window.removeEventListener("scroll", position, true);
    document.removeEventListener("keydown", onKey, true);
    dom.overlay.remove();
    dom = null;
  }

  function init() {
    document.querySelectorAll("[data-tour]").forEach((b) =>
      b.addEventListener("click", () => start(true))
    );
    const cfg = window.TOUR;
    if (cfg && cfg.key && !localStorage.getItem(SEEN_PREFIX + cfg.key)) {
      // pequeño retraso: deja asentar el layout (fuentes, iframe, etc.)
      setTimeout(() => start(false), 400);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
