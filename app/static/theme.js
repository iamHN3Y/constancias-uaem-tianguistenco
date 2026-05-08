(function(){
  const key = "theme";
  const attr = "data-theme";

  function apply(theme){
    document.documentElement.setAttribute(attr, theme);
    const btn = document.getElementById("themeToggle");
    if (btn) btn.textContent = (theme === "light") ? "Modo oscuro" : "Modo claro";
  }

  // default: dark
  const saved = localStorage.getItem(key);
  apply(saved || "dark");

  // wire button
  document.addEventListener("click", (e) => {
    const t = e.target;
    if (!t) return;
    if (t.id !== "themeToggle") return;

    const current = document.documentElement.getAttribute(attr) || "dark";
    const next = (current === "light") ? "dark" : "light";
    localStorage.setItem(key, next);
    apply(next);
  });
})();
