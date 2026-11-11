/* ============================================================
   generar.js — pantalla de generación.

   · Vista previa en vivo (POST /preview.pdf) con cada cambio.
   · Interruptores de líneas opcionales (apagado = no se envía = la línea
     desaparece del documento).
   · Revisión antes de descargar: avisa de campos importantes vacíos y
     permite ir a ellos o descargar de todos modos.
   · Tras descargar: diálogo «¿Qué sigue?» y registro en «Recientes».
   · Frases guardadas (comodines) para la línea libre.
   Datos de la página en window.GENERAR (cuenta, nombre, plantilla…).
   ============================================================ */
(function () {
  "use strict";

  const G = window.GENERAR || {};
  const form = document.getElementById("formCampos");
  const frameWrap = document.getElementById("pdfFrameWrap");
  const frame = document.getElementById("pdfFrame");
  const skeleton = document.getElementById("pdfSkeleton");
  const skeletonTexto = document.getElementById("pdfSkeletonTexto");
  const status = document.getElementById("status");
  const estadoRevision = document.getElementById("estadoRevision");
  const btnDocx = document.getElementById("btnDocx");
  const btnPdf = document.getElementById("btnPdf");
  const dlgListo = document.getElementById("dlgListo");

  let lastObjectUrl = null;
  let pendingTimer = null;
  let abortCtrl = null;
  let mensajeTimers = [];

  // ---------- Cambiar de tipo de constancia ----------
  const selPlantilla = document.getElementById("cambiarPlantilla");
  function irAPlantilla(slug) {
    location.href = "/generar?cuenta=" + encodeURIComponent(G.cuenta) + "&plantilla=" + encodeURIComponent(slug);
  }
  if (selPlantilla) selPlantilla.addEventListener("change", () => irAPlantilla(selPlantilla.value));

  // ---------- Vista previa ----------
  function setStatus(text, error) {
    status.textContent = text;
    status.classList.toggle("preview-status--error", !!error);
  }

  function limpiarMensajeTimers() {
    mensajeTimers.forEach((t) => clearTimeout(t));
    mensajeTimers = [];
  }

  function mostrarCarga() {
    frameWrap.classList.add("pdf-frame-wrap--cargando");
    frame.classList.add("pdf-frame--cargando");
    skeleton.classList.add("visible");
    skeletonTexto.textContent = "Generando vista previa…";
    limpiarMensajeTimers();
    // La conversión (arranque en frío de LibreOffice) puede tardar 2-5 s.
    mensajeTimers.push(setTimeout(() => { skeletonTexto.textContent = "Un momento, casi lista…"; }, 1200));
    mensajeTimers.push(setTimeout(() => { skeletonTexto.textContent = "Componiendo el documento…"; }, 2500));
  }

  function ocultarCarga() {
    limpiarMensajeTimers();
    frameWrap.classList.remove("pdf-frame-wrap--cargando");
    frame.classList.remove("pdf-frame--cargando");
    skeleton.classList.remove("visible");
  }

  async function refreshPreview() {
    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();
    setStatus("actualizando…");
    mostrarCarga();
    try {
      const res = await fetch("/preview.pdf", { method: "POST", body: new FormData(form), signal: abortCtrl.signal });
      if (!res.ok) {
        setStatus("no se pudo generar (error " + res.status + ")", true);
        ocultarCarga();
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      // Mantener la página actual del visor al regenerar.
      const prevSrc = frame.src;
      const hash = prevSrc.includes("#") ? "#" + prevSrc.split("#")[1] : "";
      const anteriorUrl = lastObjectUrl;
      let resuelto = false;
      const terminar = () => {
        if (resuelto) return;
        resuelto = true;
        frame.removeEventListener("load", terminar);
        setStatus("al día");
        ocultarCarga();
        if (anteriorUrl) URL.revokeObjectURL(anteriorUrl);
      };
      frame.addEventListener("load", terminar, { once: true });
      setTimeout(terminar, 1500);
      frame.src = url + hash;
      lastObjectUrl = url;
    } catch (e) {
      if (e.name !== "AbortError") { setStatus("sin conexión con el servidor", true); ocultarCarga(); }
    }
  }

  function debouncedRefresh() {
    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(refreshPreview, 700);
  }

  // ---------- Revisión de campos ----------
  // Campos «importantes» = los no opcionales que están visibles. Vacíos se
  // listan en la barra de descarga; no bloquean, solo avisan.
  function pendientes() {
    const faltan = [];
    if (form.querySelector('input[name="__genero__"]') && !form.querySelector('input[name="__genero__"]:checked')) {
      faltan.push({ etiqueta: "Género", el: form.querySelector('input[name="__genero__"]') });
    }
    form.querySelectorAll(".field[data-campo]:not(.field-opcional)").forEach((f) => {
      const ctl = f.querySelector('input[type="text"], input[type="date"], textarea');
      if (ctl && !ctl.disabled && !ctl.value.trim()) faltan.push({ etiqueta: f.dataset.etiqueta, el: ctl });
    });
    return faltan;
  }

  function pintarRevision() {
    const faltan = pendientes();
    form.querySelectorAll(".field--vacio").forEach((f) => f.classList.remove("field--vacio"));
    if (!faltan.length) {
      estadoRevision.innerHTML = '<span class="estado-ok">✓ Todo completo</span>';
      return;
    }
    faltan.forEach((x) => { const f = x.el.closest(".field"); if (f) f.classList.add("field--vacio"); });
    estadoRevision.textContent = "";
    const span = document.createElement("span");
    span.className = "estado-pendiente";
    span.textContent = faltan.length === 1 ? "Falta 1 campo: " : "Faltan " + faltan.length + " campos: ";
    estadoRevision.appendChild(span);
    faltan.slice(0, 3).forEach((x, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-link";
      b.textContent = x.etiqueta;
      b.addEventListener("click", () => irACampo(x.el));
      estadoRevision.appendChild(b);
      if (i < Math.min(faltan.length, 3) - 1) estadoRevision.appendChild(document.createTextNode(", "));
    });
    if (faltan.length > 3) estadoRevision.appendChild(document.createTextNode("…"));
  }

  function irACampo(el) {
    const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "center", behavior: sinMovimiento ? "auto" : "smooth" });
    el.focus({ preventScroll: true });
  }

  form.addEventListener("input", () => { debouncedRefresh(); pintarRevision(); });
  form.addEventListener("change", () => { debouncedRefresh(); pintarRevision(); });

  // ---------- Descarga ----------
  async function descargar(url, ext, boton) {
    const faltan = pendientes();
    if (faltan.length) {
      const genero = faltan.find((x) => x.etiqueta === "Género");
      if (genero) {
        // Sin género el texto saldría incorrecto («el/la»): aquí sí se detiene.
        window.avisar("Elige el género antes de descargar: cambia el texto «el alumno / la alumna».", "error");
        irACampo(genero.el);
        return;
      }
      const ok = await window.confirmar({
        titulo: "Hay campos vacíos",
        mensaje: "Estos campos quedarán en blanco en el documento: " + faltan.map((x) => x.etiqueta).join(", ") +
                 ". ¿Descargar de todos modos?",
        textoConfirmar: "Descargar así",
      });
      if (!ok) { irACampo(faltan[0].el); return; }
    }

    const fd = new FormData(form);
    boton.setAttribute("aria-busy", "true");
    boton.disabled = true;
    try {
      const res = await fetch(url, { method: "POST", body: fd });
      if (!res.ok) {
        window.avisar("No se pudo generar el archivo (error " + res.status + "). Inténtalo de nuevo; si sigue fallando, consulta Problemas frecuentes.", "error");
        return;
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "Constancia_" + G.cuenta + "." + ext;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);

      if (window.recientes) {
        window.recientes.agregar({ cuenta: G.cuenta, nombre: G.nombre, plantilla: G.plantilla, plantillaNombre: G.plantillaNombre });
      }
      mostrarListo(ext);
    } catch (e) {
      window.avisar("Sin conexión con el servidor. Revisa la red e inténtalo de nuevo.", "error");
    } finally {
      boton.removeAttribute("aria-busy");
      boton.disabled = false;
    }
  }

  function mostrarListo(ext) {
    document.getElementById("dlgListoTexto").textContent =
      "Se guardó «Constancia_" + G.cuenta + "." + ext + "» en tu carpeta de Descargas" +
      (ext === "pdf" ? ". Ya puedes imprimirla o enviarla." : ". Ábrela en Word si necesitas ajustar algo a mano.");
    if (dlgListo && dlgListo.showModal) {
      dlgListo.showModal();
      dlgListo.querySelector("a.btn").focus();
    } else {
      window.avisar("Constancia descargada", "exito");
    }
  }

  if (dlgListo) {
    document.getElementById("btnSeguirEditando").addEventListener("click", () => dlgListo.close());
    const btnOtra = document.getElementById("btnOtraPlantilla");
    if (btnOtra) btnOtra.addEventListener("click", () => {
      dlgListo.close();
      if (selPlantilla) { selPlantilla.focus(); selPlantilla.showPicker && selPlantilla.showPicker(); }
    });
  }

  btnDocx.addEventListener("click", () => descargar("/generar/docx", "docx", btnDocx));
  btnPdf.addEventListener("click", () => descargar("/generar/pdf", "pdf", btnPdf));
  // Ctrl+Enter = descargar PDF (atajo para quien hace muchas).
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); btnPdf.click(); }
  });

  // ---------- Líneas opcionales: interruptor incluir / omitir ----------
  // Apagado = controles deshabilitados = no viajan en el FormData = el
  // backend elimina el párrafo, sin que haya que borrar el texto.
  function controlesDe(field) {
    return field.querySelectorAll('textarea[name^="campo_"], input[name^="campo_"]:not([type=hidden]), input[name^="fecha_"]');
  }
  function aplicarToggle(toggle) {
    const field = toggle.closest(".field");
    const on = toggle.checked;
    field.classList.toggle("field--off", !on);
    controlesDe(field).forEach((el) => { el.disabled = !on; });
    const txt = field.querySelector(".switch-texto");
    if (txt) txt.textContent = on ? "Incluida" : "Omitida";
  }
  form.querySelectorAll(".opt-toggle").forEach((t) => {
    aplicarToggle(t);
    t.addEventListener("change", () => {
      aplicarToggle(t);
      if (t.checked) {
        const ctl = controlesDe(t.closest(".field"))[0];
        if (ctl) ctl.focus();
      }
    });
  });

  pintarRevision();
  refreshPreview();

  // ---------- Frases guardadas (comodines) para la línea libre ----------
  const taLibre = form.querySelector('textarea[name="campo_LINEA_LIBRE"]');
  const selComodin = document.getElementById("comodinSelector");
  const btnGuardarCmd = document.getElementById("btnGuardarComodin");
  const btnEliminarCmd = document.getElementById("btnEliminarComodin");

  if (taLibre && selComodin) {
    let comodinesCache = [];

    function pintarOpciones() {
      selComodin.innerHTML = '<option value="">' + (comodinesCache.length ? "Insertar frase guardada…" : "Aún no hay frases guardadas") + "</option>";
      for (const c of comodinesCache) {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.titulo;
        selComodin.appendChild(opt);
      }
    }

    async function cargar() {
      try {
        const res = await fetch("/comodines");
        comodinesCache = await res.json();
        pintarOpciones();
      } catch (e) { /* sin frases: el campo sigue funcionando */ }
    }

    selComodin.addEventListener("change", () => {
      const c = comodinesCache.find((x) => x.id === selComodin.value);
      if (!c) return;
      const tg = taLibre.closest(".field").querySelector(".opt-toggle");
      if (tg && !tg.checked) { tg.checked = true; aplicarToggle(tg); }
      taLibre.value = c.texto;
      taLibre.dispatchEvent(new Event("input", { bubbles: true }));
    });

    btnGuardarCmd.addEventListener("click", async () => {
      const texto = taLibre.value.trim();
      if (!texto) {
        window.avisar("Primero escribe el texto en la línea libre; luego guárdalo como frase.", "error");
        const tg = taLibre.closest(".field").querySelector(".opt-toggle");
        if (tg && !tg.checked) { tg.checked = true; aplicarToggle(tg); }
        taLibre.focus();
        return;
      }
      const titulo = await window.pedirTexto({
        titulo: "Guardar frase",
        mensaje: "Ponle un nombre corto para encontrarla después (lo verán todos los usuarios).",
        placeholder: "Ej. Trámite de beca",
        textoConfirmar: "Guardar",
      });
      if (!titulo) return;
      const fd = new FormData();
      fd.append("titulo", titulo);
      fd.append("texto", texto);
      const res = await fetch("/comodines", { method: "POST", body: fd });
      if (!res.ok) { window.avisar("No se pudo guardar la frase.", "error"); return; }
      const nuevo = await res.json();
      comodinesCache.push(nuevo);
      pintarOpciones();
      selComodin.value = nuevo.id;
      window.avisar("Frase «" + nuevo.titulo + "» guardada", "exito");
    });

    btnEliminarCmd.addEventListener("click", async () => {
      const id = selComodin.value;
      if (!id) { window.avisar("Elige en la lista la frase que quieres eliminar.", "error"); selComodin.focus(); return; }
      const c = comodinesCache.find((x) => x.id === id);
      const ok = await window.confirmar({
        titulo: "¿Eliminar frase?",
        mensaje: "Se eliminará «" + c.titulo + "» para todos los usuarios. El texto ya escrito en esta constancia no cambia.",
        peligro: true,
        textoConfirmar: "Eliminar",
      });
      if (!ok) return;
      const res = await fetch("/comodines/" + id, { method: "DELETE" });
      if (!res.ok) { window.avisar("No se pudo eliminar.", "error"); return; }
      comodinesCache = comodinesCache.filter((x) => x.id !== id);
      pintarOpciones();
    });

    cargar();
  }
})();
