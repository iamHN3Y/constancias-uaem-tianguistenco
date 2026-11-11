/* ============================================================
   ui.js — snackbars, confirmaciones accesibles y protección de
   formularios destructivos. JS vanilla, sin dependencias.
   ============================================================ */

(function () {
  "use strict";

  const SNACKBAR_MS = 5000;

  function regionSnackbar() {
    let region = document.querySelector(".snackbar-region");
    if (!region) {
      // Se crea vacía de antemano (ver bootstrap al final del archivo): los
      // lectores de pantalla no siempre anuncian contenido insertado en el
      // mismo tick en que la región aria-live entra al DOM.
      region = document.createElement("div");
      region.className = "snackbar-region";
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      document.body.appendChild(region);
    }
    return region;
  }

  /**
   * avisar(mensaje, tipo)
   * tipo: "info" | "exito" | "error"
   */
  function avisar(mensaje, tipo) {
    tipo = tipo || "info";
    const region = regionSnackbar();
    const item = document.createElement("div");
    item.className = "snackbar" + (tipo === "exito" ? " snackbar-exito" : tipo === "error" ? " snackbar-error" : "");
    item.textContent = mensaje;
    region.appendChild(item);

    const quitar = () => {
      item.classList.add("snackbar--saliendo");
      item.addEventListener("animationend", () => item.remove(), { once: true });
      // Respaldo por si prefers-reduced-motion anula la animación.
      setTimeout(() => item.remove(), 400);
    };
    setTimeout(quitar, SNACKBAR_MS);
  }

  /**
   * confirmar({titulo, mensaje, peligro, textoConfirmar, escribirPara})
   * Devuelve Promise<boolean>.
   */
  function confirmar(opts) {
    opts = opts || {};
    const titulo = opts.titulo || "¿Confirmar acción?";
    const mensaje = opts.mensaje || "";
    const peligro = !!opts.peligro;
    const textoConfirmar = opts.textoConfirmar || "Confirmar";
    const escribirPara = opts.escribirPara || null;

    return new Promise((resolve) => {
      const dialog = document.createElement("dialog");
      dialog.className = peligro ? "dialog-danger" : "";

      const body = document.createElement("div");
      body.className = "dialog-body";

      const h3 = document.createElement("h3");
      h3.textContent = titulo;
      body.appendChild(h3);

      if (mensaje) {
        const p = document.createElement("p");
        p.textContent = mensaje;
        body.appendChild(p);
      }

      let inputEscribir = null;
      if (escribirPara) {
        const field = document.createElement("div");
        field.className = "field";
        const label = document.createElement("label");
        label.textContent = `Escribe "${escribirPara}" para continuar`;
        inputEscribir = document.createElement("input");
        inputEscribir.type = "text";
        inputEscribir.autocomplete = "off";
        field.appendChild(label);
        field.appendChild(inputEscribir);
        body.appendChild(field);
      }

      const actions = document.createElement("div");
      actions.className = "dialog-actions";

      const btnCancelar = document.createElement("button");
      btnCancelar.type = "button";
      btnCancelar.className = "btn-ghost";
      btnCancelar.textContent = "Cancelar";

      const btnConfirmar = document.createElement("button");
      btnConfirmar.type = "button";
      btnConfirmar.className = "dialog-confirmar";
      btnConfirmar.textContent = textoConfirmar;

      if (escribirPara) {
        btnConfirmar.disabled = true;
        inputEscribir.addEventListener("input", () => {
          btnConfirmar.disabled = inputEscribir.value !== escribirPara;
        });
      }

      actions.appendChild(btnCancelar);
      actions.appendChild(btnConfirmar);
      body.appendChild(actions);
      dialog.appendChild(body);
      document.body.appendChild(dialog);

      let resuelto = false;
      function cerrar(valor) {
        if (resuelto) return;
        resuelto = true;
        resolve(valor);
        dialog.close();
      }

      btnCancelar.addEventListener("click", () => cerrar(false));
      btnConfirmar.addEventListener("click", () => cerrar(true));
      // Esc dispara "cancel" antes de cerrarse; lo tratamos como cancelación explícita.
      dialog.addEventListener("cancel", (e) => {
        e.preventDefault();
        cerrar(false);
      });
      dialog.addEventListener("close", () => {
        if (!resuelto) resolve(false);
        dialog.remove();
      });

      dialog.showModal();
      if (inputEscribir) {
        inputEscribir.focus();
      } else {
        btnConfirmar.focus();
      }
    });
  }

  /**
   * pedirTexto({titulo, mensaje, placeholder, textoConfirmar})
   * Reemplazo accesible de prompt(). Devuelve Promise<string|null>
   * (null si se cancela o se deja vacío).
   */
  function pedirTexto(opts) {
    opts = opts || {};
    return new Promise((resolve) => {
      const dialog = document.createElement("dialog");

      const body = document.createElement("div");
      body.className = "dialog-body";

      const h3 = document.createElement("h3");
      h3.textContent = opts.titulo || "Escribe un valor";
      body.appendChild(h3);

      if (opts.mensaje) {
        const p = document.createElement("p");
        p.textContent = opts.mensaje;
        body.appendChild(p);
      }

      const field = document.createElement("div");
      field.className = "field";
      const input = document.createElement("input");
      input.type = "text";
      input.autocomplete = "off";
      if (opts.placeholder) input.placeholder = opts.placeholder;
      field.appendChild(input);
      body.appendChild(field);

      const actions = document.createElement("div");
      actions.className = "dialog-actions";

      const btnCancelar = document.createElement("button");
      btnCancelar.type = "button";
      btnCancelar.className = "btn-ghost";
      btnCancelar.textContent = "Cancelar";

      const btnConfirmar = document.createElement("button");
      btnConfirmar.type = "button";
      btnConfirmar.className = "dialog-confirmar";
      btnConfirmar.textContent = opts.textoConfirmar || "Guardar";
      btnConfirmar.disabled = true;
      input.addEventListener("input", () => {
        btnConfirmar.disabled = input.value.trim() === "";
      });

      actions.appendChild(btnCancelar);
      actions.appendChild(btnConfirmar);
      body.appendChild(actions);
      dialog.appendChild(body);
      document.body.appendChild(dialog);

      let resuelto = false;
      function cerrar(valor) {
        if (resuelto) return;
        resuelto = true;
        resolve(valor);
        dialog.close();
      }

      btnCancelar.addEventListener("click", () => cerrar(null));
      btnConfirmar.addEventListener("click", () => cerrar(input.value.trim()));
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && input.value.trim() !== "") { e.preventDefault(); cerrar(input.value.trim()); }
      });
      dialog.addEventListener("cancel", (e) => {
        e.preventDefault();
        cerrar(null);
      });
      dialog.addEventListener("close", () => {
        if (!resuelto) resolve(null);
        dialog.remove();
      });

      dialog.showModal();
      input.focus();
    });
  }

  /**
   * protegerFormulario(form, {peligro, textoConfirmar, escribirPara, mensaje(form)})
   * Intercepta el submit para pedir confirmación antes de enviar.
   */
  function protegerFormulario(form, opts) {
    opts = opts || {};
    form.addEventListener("submit", async function (event) {
      if (form.dataset.confirmado === "1") {
        // Ya confirmado: dejar pasar este submit real.
        delete form.dataset.confirmado;
        return;
      }
      event.preventDefault();

      if (!form.reportValidity()) return;
      if (form.dataset.confirmando === "1") return; // diálogo ya abierto (doble clic/Enter)
      form.dataset.confirmando = "1";

      const submitter = event.submitter;
      const mensaje = typeof opts.mensaje === "function" ? opts.mensaje(form) : (opts.mensaje || "");
      const ok = await confirmar({
        titulo: opts.titulo,
        mensaje: mensaje,
        peligro: opts.peligro,
        textoConfirmar: opts.textoConfirmar,
        escribirPara: typeof opts.escribirPara === "function" ? opts.escribirPara(form) : opts.escribirPara,
      });
      delete form.dataset.confirmando;
      if (ok) {
        form.dataset.confirmado = "1";
        form.requestSubmit(submitter || undefined);
      }
    });
  }

  /**
   * Autowiring declarativo: cualquier <form data-confirmar> se protege
   * automáticamente leyendo sus data-confirmar-* como opciones.
   * Evita repetir JS de inicialización en cada plantilla.
   */
  function autoProteger() {
    document.querySelectorAll("form[data-confirmar]").forEach((form) => {
      if (form.dataset.confirmarListo === "1") return;
      form.dataset.confirmarListo = "1";
      protegerFormulario(form, {
        titulo: form.dataset.confirmarTitulo,
        mensaje: form.dataset.confirmarMensaje,
        peligro: form.dataset.confirmarPeligro !== undefined,
        textoConfirmar: form.dataset.confirmarTexto,
        escribirPara: form.dataset.confirmarEscribirPara,
      });
    });
  }

  /**
   * recientes — últimas constancias descargadas EN ESTE NAVEGADOR, para
   * regenerarlas con un clic. Solo localStorage: no se comparte entre
   * equipos ni llega al servidor. Si el almacenamiento falla (modo
   * privado, bloqueado), simplemente no hay lista.
   */
  const RECIENTES_KEY = "constancias_recientes";
  const RECIENTES_MAX = 6;
  const recientes = {
    listar() {
      try {
        const lista = JSON.parse(localStorage.getItem(RECIENTES_KEY) || "[]");
        return Array.isArray(lista) ? lista : [];
      } catch (e) { return []; }
    },
    agregar(item) {
      try {
        const ahora = new Date();
        item.cuando = ahora.toLocaleDateString("es-MX", { day: "numeric", month: "short" }) +
          ", " + ahora.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
        const lista = recientes.listar().filter(
          (r) => !(r.cuenta === item.cuenta && r.plantilla === item.plantilla)
        );
        lista.unshift(item);
        localStorage.setItem(RECIENTES_KEY, JSON.stringify(lista.slice(0, RECIENTES_MAX)));
      } catch (e) { /* sin almacenamiento: no pasa nada */ }
    },
    borrar() {
      try { localStorage.removeItem(RECIENTES_KEY); } catch (e) { /* idem */ }
    },
  };

  /**
   * Zonas para soltar archivos: cualquier <label class="dropzone"> que
   * contenga un input[type=file] muestra el nombre y tamaño del archivo
   * elegido y acepta arrastrar y soltar. El input real sigue dentro (los
   * formularios funcionan igual sin JS).
   */
  function tamanoLegible(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  function prepararDropzones() {
    document.querySelectorAll("label.dropzone").forEach((zona) => {
      const input = zona.querySelector('input[type="file"]');
      const estado = zona.querySelector(".dropzone-archivo");
      if (!input || zona.dataset.listo) return;
      zona.dataset.listo = "1";
      const aceptadas = (input.getAttribute("accept") || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);

      function mostrar() {
        const f = input.files && input.files[0];
        zona.classList.toggle("dropzone--lleno", !!f);
        if (!estado) return;
        estado.textContent = f ? "Elegido: " + f.name + " (" + tamanoLegible(f.size) + ")" : "";
        if (f && aceptadas.length && !aceptadas.some((ext) => f.name.toLowerCase().endsWith(ext))) {
          estado.textContent = "«" + f.name + "» no es un formato aceptado (" + aceptadas.join(", ") + ").";
          zona.classList.add("dropzone--error");
        } else {
          zona.classList.remove("dropzone--error");
        }
      }
      input.addEventListener("change", mostrar);
      ["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => {
        e.preventDefault();
        zona.classList.add("dropzone--encima");
      }));
      ["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, () => zona.classList.remove("dropzone--encima")));
      zona.addEventListener("drop", (e) => {
        e.preventDefault();
        if (e.dataTransfer && e.dataTransfer.files.length) {
          input.files = e.dataTransfer.files;
          mostrar();
        }
      });
      mostrar();
    });
  }

  function bootstrap() {
    regionSnackbar();
    autoProteger();
    prepararDropzones();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }

  window.avisar = avisar;
  window.confirmar = confirmar;
  window.pedirTexto = pedirTexto;
  window.protegerFormulario = protegerFormulario;
  window.recientes = recientes;
})();
