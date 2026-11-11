/* ============================================================
   buscador.js — pantalla de inicio.

   · Sugerencias en vivo (combobox ARIA) mientras se escribe la cuenta o
     el nombre: GET /api/alumnos?q=…  Flechas + Enter o clic para elegir.
     Sin JS, el formulario sigue funcionando (POST /buscar).
   · Atajo «/» para saltar al buscador.
   · Lista «Recientes en este equipo» (window.recientes, de ui.js).
   ============================================================ */
(function () {
  "use strict";

  var form = document.getElementById("formBuscar");
  var input = document.getElementById("cuenta");
  var lista = document.getElementById("sugerencias");
  var ayudaTxt = document.getElementById("cuentaAyuda");

  function plantillaElegida() {
    if (!form) return "";
    var r = form.querySelector('input[name="plantilla"]:checked') || form.querySelector('input[name="plantilla"][type="hidden"]');
    return r ? r.value : "";
  }

  function urlGenerar(cuenta, plantilla) {
    return "/generar?cuenta=" + encodeURIComponent(cuenta) + "&plantilla=" + encodeURIComponent(plantilla || plantillaElegida());
  }

  // ---------- Sugerencias en vivo ----------
  if (form && input && lista) {
    var items = [];
    var activo = -1;
    var timer = null;
    var ctrl = null;
    var ultimaConsulta = "";

    function cerrar() {
      lista.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      activo = -1;
    }

    function marcar(i) {
      var opciones = lista.querySelectorAll('[role="option"]');
      opciones.forEach(function (o) { o.setAttribute("aria-selected", "false"); });
      activo = i;
      if (i >= 0 && opciones[i]) {
        opciones[i].setAttribute("aria-selected", "true");
        input.setAttribute("aria-activedescendant", opciones[i].id);
        opciones[i].scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }

    function resaltar(texto, consulta) {
      // Escapa y resalta cada palabra buscada (sin importar acentos).
      var span = document.createElement("span");
      span.textContent = texto;
      var html = span.innerHTML;
      var quitar = function (s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
      var base = quitar(html);
      consulta.split(/\s+/).filter(Boolean).forEach(function (p) {
        var q = quitar(p);
        var i = base.indexOf(q);
        if (i >= 0 && q.length > 1) {
          html = html.slice(0, i) + "\u0001" + html.slice(i, i + q.length) + "\u0002" + html.slice(i + q.length);
          base = base.slice(0, i) + "\u0001" + base.slice(i, i + q.length) + "\u0002" + base.slice(i + q.length);
        }
      });
      return html.replace(/\u0001/g, "<mark>").replace(/\u0002/g, "</mark>");
    }

    function pintar(consulta) {
      lista.innerHTML = "";
      if (!items.length) {
        var vacio = document.createElement("li");
        vacio.className = "sugerencia-vacia";
        vacio.textContent = /^\d+$/.test(consulta)
          ? "Ninguna cuenta empieza con " + consulta + "."
          : "Ningún alumno coincide. Prueba solo con un apellido.";
        lista.appendChild(vacio);
      }
      items.forEach(function (a, i) {
        var li = document.createElement("li");
        li.id = "sug-" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.className = "sugerencia";
        li.innerHTML =
          '<span class="sugerencia-nombre">' + resaltar(a.nombre, consulta) + "</span>" +
          '<span class="sugerencia-meta">Cuenta ' + resaltar(a.cuenta, consulta) +
          (a.plan ? " · " + resaltar(a.plan, "") : "") +
          (a.nuevo_ingreso ? ' · <span class="field-tag">nuevo ingreso</span>' : "") + "</span>";
        li.addEventListener("mousedown", function (e) { e.preventDefault(); });
        li.addEventListener("click", function () { elegir(i); });
        li.addEventListener("mousemove", function () { if (activo !== i) marcar(i); });
        lista.appendChild(li);
      });
      lista.hidden = false;
      input.setAttribute("aria-expanded", "true");
      marcar(items.length ? 0 : -1);
      if (ayudaTxt) {
        ayudaTxt.textContent = items.length
          ? items.length + (items.length === 1 ? " alumno encontrado" : " alumnos encontrados") + ". Usa ↑ ↓ y Enter, o haz clic."
          : "Sin coincidencias.";
      }
    }

    function elegir(i) {
      var a = items[i];
      if (!a) return;
      cerrar();
      input.value = a.nombre;
      location.href = urlGenerar(a.cuenta);
    }

    async function consultar() {
      var q = input.value.trim();
      if (q.length < 2) { cerrar(); items = []; return; }
      if (q === ultimaConsulta && !lista.hidden) return;
      ultimaConsulta = q;
      if (ctrl) ctrl.abort();
      ctrl = new AbortController();
      try {
        var res = await fetch("/api/alumnos?q=" + encodeURIComponent(q), { signal: ctrl.signal });
        if (!res.ok) return;
        items = await res.json();
        if (input.value.trim() === q) pintar(q);
      } catch (e) { /* abortado o sin red: el formulario normal sigue funcionando */ }
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(consultar, 180);
    });
    input.addEventListener("focus", function () { if (input.value.trim().length >= 2) consultar(); });
    input.addEventListener("blur", function () { setTimeout(cerrar, 120); });
    input.addEventListener("keydown", function (e) {
      var abierta = !lista.hidden && items.length;
      if (e.key === "ArrowDown" && abierta) { e.preventDefault(); marcar((activo + 1) % items.length); }
      else if (e.key === "ArrowUp" && abierta) { e.preventDefault(); marcar((activo - 1 + items.length) % items.length); }
      else if (e.key === "Escape" && !lista.hidden) { e.preventDefault(); cerrar(); }
      else if (e.key === "Enter" && abierta && activo >= 0) { e.preventDefault(); elegir(activo); }
    });
  }

  // ---------- Atajo «/» ----------
  if (input) {
    document.addEventListener("keydown", function (e) {
      if (e.key !== "/") return;
      var el = document.activeElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      e.preventDefault();
      input.focus();
      input.select();
    });
  }

  // ---------- Resultados por nombre (sin JS de sugerencias) ----------
  var resultados = document.getElementById("resultados-busqueda");
  if (resultados) {
    var sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    resultados.scrollIntoView({ behavior: sinMovimiento ? "auto" : "smooth", block: "start" });
    resultados.focus({ preventScroll: true });
  }

  // ---------- Recientes ----------
  var seccion = document.getElementById("recientes");
  var ul = document.getElementById("listaRecientes");
  if (seccion && ul && window.recientes) {
    var slugs = window.PLANTILLAS_SLUGS || [];
    function pintarRecientes() {
      var lista = window.recientes.listar().filter(function (r) { return !r.plantilla || slugs.indexOf(r.plantilla) >= 0; });
      ul.innerHTML = "";
      seccion.hidden = !lista.length;
      lista.forEach(function (r) {
        var li = document.createElement("li");
        var info = document.createElement("div");
        var nombre = document.createElement("div");
        nombre.className = "lista-nombre";
        nombre.textContent = r.nombre;
        var meta = document.createElement("div");
        meta.className = "lista-meta";
        meta.textContent = "Cuenta " + r.cuenta + (r.plantillaNombre ? " · " + r.plantillaNombre : "") + " · " + r.cuando;
        info.appendChild(nombre);
        info.appendChild(meta);
        var a = document.createElement("a");
        a.className = "btn btn-tonal";
        a.href = urlGenerar(r.cuenta, r.plantilla);
        a.textContent = "Generar otra vez";
        li.appendChild(info);
        li.appendChild(a);
        ul.appendChild(li);
      });
    }
    pintarRecientes();
    document.getElementById("btnBorrarRecientes").addEventListener("click", async function () {
      var ok = await window.confirmar({
        titulo: "¿Borrar la lista de recientes?",
        mensaje: "Solo se borra de este navegador. No afecta a ninguna constancia ni a los datos de los alumnos.",
        textoConfirmar: "Borrar lista",
      });
      if (!ok) return;
      window.recientes.borrar();
      pintarRecientes();
      window.avisar("Lista de recientes borrada", "exito");
    });
  }
})();
