/* ============================================================
   Modo ayuda — ayuda contextual sobre la propia pantalla.

   Al activarlo (botón «Modo ayuda» de la barra superior o tecla «?»):
     · cada zona con [data-ayuda] se marca con un borde y un botón «?»;
     · al pasar el cursor la zona se resalta y muestra su título;
     · al hacer clic (o Enter sobre el «?») se abre una tarjeta con la
       explicación, enlace a la guía completa y flechas para recorrer
       todas las zonas de la pantalla en orden.
   Mientras está activo, los clics en las zonas NO ejecutan la acción
   (no se envía nada por accidente). Esc cierra la tarjeta; otro Esc sale.

   El contenido sale de los atributos que pone la macro ayuda() en las
   plantillas (data-ayuda, data-ayuda-texto, data-ayuda-articulo), los
   mismos que usa el recorrido guiado (tour.js). Sin dependencias.
   ============================================================ */
(function () {
  "use strict";

  var activo = false;
  var capa = null;          // contenedor de los «?» (position: fixed)
  var tarjeta = null;       // popover con la explicación
  var etiqueta = null;      // título flotante al pasar el cursor
  var banda = null;         // aviso inferior «Modo ayuda activo»
  var zonas = [];           // elementos [data-ayuda] visibles, en orden de lectura
  var actual = -1;          // índice de la zona abierta en la tarjeta
  var raf = 0;
  var boton = null;

  function visible(el) {
    if (!el.getClientRects().length) return false;
    var r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return false;
    var cs = getComputedStyle(el);
    return cs.visibility !== "hidden" && cs.display !== "none";
  }

  function recolectar() {
    zonas = Array.prototype.filter.call(document.querySelectorAll("[data-ayuda]"), visible);
    // Orden de lectura: de arriba abajo y de izquierda a derecha.
    zonas.sort(function (a, b) {
      var ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      var dy = (ra.top + window.scrollY) - (rb.top + window.scrollY);
      return Math.abs(dy) > 12 ? dy : ra.left - rb.left;
    });
  }

  // ---------- Construcción de la interfaz ----------

  function construir() {
    capa = document.createElement("div");
    capa.className = "ayuda-capa";
    document.body.appendChild(capa);

    etiqueta = document.createElement("div");
    etiqueta.className = "ayuda-etiqueta";
    etiqueta.setAttribute("aria-hidden", "true");
    document.body.appendChild(etiqueta);

    tarjeta = document.createElement("div");
    tarjeta.className = "ayuda-tarjeta";
    tarjeta.setAttribute("role", "dialog");
    tarjeta.setAttribute("aria-modal", "false");
    tarjeta.setAttribute("aria-labelledby", "ayudaTarjetaTitulo");
    tarjeta.innerHTML =
      '<div class="ayuda-tarjeta-cab">' +
        '<span class="ayuda-tarjeta-num"></span>' +
        '<button type="button" class="icon-btn ayuda-cerrar" aria-label="Cerrar explicación">' +
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.3 5.7L12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7 2.9 18.3 9.2 12 2.9 5.7 4.3 4.3l6.3 6.3 6.3-6.3z"/></svg>' +
        '</button>' +
      '</div>' +
      '<h3 id="ayudaTarjetaTitulo" class="ayuda-tarjeta-titulo"></h3>' +
      '<p class="ayuda-tarjeta-texto"></p>' +
      '<a class="ayuda-tarjeta-guia" target="_blank" rel="noopener"></a>' +
      '<div class="ayuda-tarjeta-nav">' +
        '<button type="button" class="btn-ghost ayuda-ant">‹ Anterior</button>' +
        '<button type="button" class="btn-tonal ayuda-sig">Siguiente ›</button>' +
      '</div>';
    document.body.appendChild(tarjeta);
    tarjeta.querySelector(".ayuda-cerrar").addEventListener("click", cerrarTarjeta);
    tarjeta.querySelector(".ayuda-ant").addEventListener("click", function () { abrir(actual - 1); });
    tarjeta.querySelector(".ayuda-sig").addEventListener("click", function () { abrir(actual + 1); });

    banda = document.createElement("div");
    banda.className = "ayuda-banda";
    banda.setAttribute("role", "status");
    banda.innerHTML =
      '<span class="ayuda-banda-texto"><strong>Modo ayuda activo.</strong> Pasa el cursor sobre la pantalla y haz clic en lo que quieras entender.</span>' +
      '<span class="ayuda-banda-acciones">' +
        '<button type="button" class="btn-tonal ayuda-recorrido">Recorrido guiado</button>' +
        '<button type="button" class="ayuda-salir">Salir <kbd>Esc</kbd></button>' +
      '</span>';
    document.body.appendChild(banda);
    banda.querySelector(".ayuda-salir").addEventListener("click", desactivar);
    var btnRec = banda.querySelector(".ayuda-recorrido");
    if (window.iniciarRecorrido && document.querySelector("[data-recorrido]")) {
      btnRec.addEventListener("click", function () { desactivar(); window.iniciarRecorrido(); });
    } else {
      btnRec.remove();
    }
  }

  function pintarMarcas() {
    capa.innerHTML = "";
    zonas.forEach(function (el, i) {
      var pin = document.createElement("button");
      pin.type = "button";
      pin.className = "ayuda-pin";
      pin.textContent = "?";
      pin.setAttribute("aria-label", "Ayuda: " + el.getAttribute("data-ayuda"));
      pin.addEventListener("click", function (e) { e.stopPropagation(); abrir(i); });
      capa.appendChild(pin);
    });
    posicionar();
  }

  function posicionar() {
    raf = 0;
    if (!activo) return;
    var pins = capa.children;
    zonas.forEach(function (el, i) {
      var r = el.getBoundingClientRect();
      var pin = pins[i];
      if (!pin) return;
      var fuera = r.bottom < 0 || r.top > window.innerHeight;
      pin.style.display = fuera ? "none" : "";
      pin.style.left = Math.min(window.innerWidth - 30, Math.max(4, r.right - 14)) + "px";
      pin.style.top = Math.max(4, r.top - 10) + "px";
    });
    if (actual >= 0) colocarTarjeta();
  }

  function programarPosicion() {
    if (!raf) raf = requestAnimationFrame(posicionar);
  }

  // ---------- Tarjeta ----------

  function abrir(i) {
    if (!zonas.length) return;
    actual = (i + zonas.length) % zonas.length;
    var el = zonas[actual];
    document.querySelectorAll(".ayuda-foco").forEach(function (x) { x.classList.remove("ayuda-foco"); });
    el.classList.add("ayuda-foco");

    tarjeta.querySelector(".ayuda-tarjeta-num").textContent = (actual + 1) + " de " + zonas.length;
    tarjeta.querySelector(".ayuda-tarjeta-titulo").textContent = el.getAttribute("data-ayuda");
    tarjeta.querySelector(".ayuda-tarjeta-texto").textContent = el.getAttribute("data-ayuda-texto") || "";
    var guia = tarjeta.querySelector(".ayuda-tarjeta-guia");
    var art = el.getAttribute("data-ayuda-articulo");
    if (art) {
      guia.href = "/ayuda/" + art;
      guia.textContent = "Leer la guía completa ↗";
      guia.hidden = false;
    } else {
      guia.hidden = true;
    }
    var unico = zonas.length < 2;
    tarjeta.querySelector(".ayuda-ant").hidden = unico;
    tarjeta.querySelector(".ayuda-sig").hidden = unico;

    tarjeta.classList.add("visible");
    var sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var r = el.getBoundingClientRect();
    if (r.top < 70 || r.bottom > window.innerHeight - 80) {
      el.scrollIntoView({ block: "center", behavior: sinMovimiento ? "auto" : "smooth" });
    }
    colocarTarjeta();
    tarjeta.querySelector(".ayuda-sig").hidden ? tarjeta.querySelector(".ayuda-cerrar").focus()
                                               : tarjeta.querySelector(".ayuda-sig").focus();
  }

  function colocarTarjeta() {
    var el = zonas[actual];
    if (!el) return;
    var r = el.getBoundingClientRect();
    var w = tarjeta.offsetWidth, h = tarjeta.offsetHeight;
    var margen = 12;
    var minTop = 64, maxBottom = window.innerHeight - 70;   // bajo la barra superior, sobre la banda
    var top, left;
    if (r.bottom + margen + h <= maxBottom) {                 // debajo de la zona
      top = r.bottom + margen;
      left = r.left;
    } else if (r.top - h - margen >= minTop) {                // encima
      top = r.top - h - margen;
      left = r.left;
    } else if (r.left - w - margen >= margen) {               // zona alta: a su izquierda
      left = r.left - w - margen;
      top = Math.max(minTop, Math.min(r.top, maxBottom - h));
    } else if (r.right + margen + w <= window.innerWidth - margen) {  // o a su derecha
      left = r.right + margen;
      top = Math.max(minTop, Math.min(r.top, maxBottom - h));
    } else {                                                  // sin espacio: abajo de la ventana
      top = Math.max(minTop, maxBottom - h);
      left = r.left;
    }
    left = Math.max(margen, Math.min(left, window.innerWidth - w - margen));
    tarjeta.style.top = top + "px";
    tarjeta.style.left = left + "px";
  }

  function cerrarTarjeta() {
    actual = -1;
    if (tarjeta) tarjeta.classList.remove("visible");
    document.querySelectorAll(".ayuda-foco").forEach(function (x) { x.classList.remove("ayuda-foco"); });
  }

  // ---------- Interacción ----------

  function zonaDe(target) {
    if (!target || !target.closest) return null;
    if (target.closest("[data-ayuda-exento], .ayuda-tarjeta, .ayuda-banda, .ayuda-capa")) return null;
    return target.closest("[data-ayuda]");
  }

  function alHacerClic(e) {
    if (!activo) return;
    var z = zonaDe(e.target);
    if (z) {
      // En modo ayuda, el clic explica en vez de ejecutar.
      e.preventDefault();
      e.stopPropagation();
      recolectar();
      var i = zonas.indexOf(z);
      if (i >= 0) abrir(i);
    } else if (!e.target.closest(".ayuda-tarjeta, .ayuda-banda, .ayuda-capa, [data-ayuda-exento]")) {
      cerrarTarjeta();
    }
  }

  function alMoverCursor(e) {
    if (!activo) return;
    var z = zonaDe(e.target);
    if (!z || z.classList.contains("ayuda-foco")) {
      etiqueta.classList.remove("visible");
      return;
    }
    etiqueta.textContent = z.getAttribute("data-ayuda") + " — clic para saber más";
    etiqueta.classList.add("visible");
    var x = Math.min(e.clientX + 14, window.innerWidth - etiqueta.offsetWidth - 8);
    var y = e.clientY + 18;
    if (y + 30 > window.innerHeight) y = e.clientY - 34;
    etiqueta.style.left = x + "px";
    etiqueta.style.top = y + "px";
  }

  function alTeclear(e) {
    var el = document.activeElement;
    var escribiendo = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
    if (e.key === "?" && !escribiendo && !document.querySelector(".tour-overlay")) {
      e.preventDefault();
      activo ? desactivar() : activar();
      return;
    }
    if (!activo) return;
    if (e.key === "Escape") {
      e.preventDefault();
      if (actual >= 0) cerrarTarjeta(); else desactivar();
    } else if (actual >= 0 && e.key === "ArrowRight") {
      e.preventDefault(); abrir(actual + 1);
    } else if (actual >= 0 && e.key === "ArrowLeft") {
      e.preventDefault(); abrir(actual - 1);
    }
  }

  function activar() {
    if (activo) return;
    activo = true;
    if (!capa) construir();
    document.documentElement.classList.add("modo-ayuda");
    if (boton) boton.setAttribute("aria-pressed", "true");
    recolectar();
    pintarMarcas();
    banda.classList.add("visible");
    window.addEventListener("scroll", programarPosicion, true);
    window.addEventListener("resize", recolectarYPintar);
  }

  function recolectarYPintar() { recolectar(); pintarMarcas(); }

  function desactivar() {
    if (!activo) return;
    activo = false;
    cerrarTarjeta();
    document.documentElement.classList.remove("modo-ayuda");
    if (boton) { boton.setAttribute("aria-pressed", "false"); boton.focus({ preventScroll: true }); }
    capa.innerHTML = "";
    etiqueta.classList.remove("visible");
    banda.classList.remove("visible");
    window.removeEventListener("scroll", programarPosicion, true);
    window.removeEventListener("resize", recolectarYPintar);
  }

  function init() {
    boton = document.getElementById("btnModoAyuda");
    if (boton) boton.addEventListener("click", function () { activo ? desactivar() : activar(); });
    document.addEventListener("click", alHacerClic, true);
    // Bloquea también envíos de formulario por Enter dentro de una zona.
    document.addEventListener("submit", function (e) { if (activo) { e.preventDefault(); e.stopPropagation(); } }, true);
    document.addEventListener("mousemove", alMoverCursor, { passive: true });
    document.addEventListener("keydown", alTeclear);
    // Enlace profundo: /pantalla?ayuda=1 abre la pantalla ya en modo ayuda
    // (lo usan los botones «Mostrármelo en pantalla» del centro de ayuda).
    if (/[?&]ayuda=1\b/.test(location.search)) setTimeout(activar, 300);
  }

  window.modoAyuda = { activar: activar, desactivar: desactivar };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
