(function(){
  const key = "theme";
  const attr = "data-theme";

  const ICON_SUN = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7a5 5 0 100 10 5 5 0 000-10zm0-5a1 1 0 011 1v2a1 1 0 11-2 0V3a1 1 0 011-1zm0 16a1 1 0 011 1v2a1 1 0 11-2 0v-2a1 1 0 011-1zM4.2 5.6a1 1 0 011.4 0l1.5 1.4A1 1 0 015.7 8.4L4.2 7a1 1 0 010-1.4zm12.7 12.7a1 1 0 011.4 0l1.5 1.4a1 1 0 01-1.4 1.4l-1.5-1.4a1 1 0 010-1.4zM2 12a1 1 0 011-1h2a1 1 0 110 2H3a1 1 0 01-1-1zm17 0a1 1 0 011-1h2a1 1 0 110 2h-2a1 1 0 01-1-1zM5.6 19.8l1.4-1.5a1 1 0 011.4 1.4l-1.4 1.5a1 1 0 01-1.4-1.4zM18.3 7.1l1.4-1.5a1 1 0 011.4 1.4l-1.4 1.5a1 1 0 01-1.4-1.4z"/></svg>';
  const ICON_MOON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 109.8 9.8z"/></svg>';

  function apply(theme){
    document.documentElement.setAttribute(attr, theme);
    const btn = document.getElementById("themeToggle");
    if (btn){
      const dark = theme === "dark";
      btn.innerHTML = dark ? ICON_SUN : ICON_MOON;
      btn.setAttribute("aria-label", dark ? "Cambiar a modo claro" : "Cambiar a modo oscuro");
      btn.setAttribute("title", dark ? "Modo claro" : "Modo oscuro");
    }
  }

  // default: claro
  const saved = localStorage.getItem(key);
  apply(saved || "light");

  document.addEventListener("click", (e) => {
    const toggle = e.target.closest && e.target.closest("#themeToggle");
    if (!toggle) return;
    const current = document.documentElement.getAttribute(attr) || "light";
    const next = current === "light" ? "dark" : "light";
    localStorage.setItem(key, next);
    apply(next);
  });

  // ---------- Ripple Material en botones ----------
  document.addEventListener("pointerdown", (e) => {
    const btn = e.target.closest && e.target.closest("button, .btn, a.btn");
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const span = document.createElement("span");
    span.className = "ripple";
    span.style.width = span.style.height = size + "px";
    span.style.left = (e.clientX - rect.left - size / 2) + "px";
    span.style.top = (e.clientY - rect.top - size / 2) + "px";
    btn.appendChild(span);
    span.addEventListener("animationend", () => span.remove());
  });
})();
