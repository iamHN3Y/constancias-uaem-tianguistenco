import { useCallback, useEffect, useState } from "react";

/** Tema claro/oscuro, portado de app/static/theme.js: localStorage + data-theme en <html>. */
export type Theme = "light" | "dark";
const KEY = "theme";

function leerInicial(): Theme {
  const saved = localStorage.getItem(KEY);
  return saved === "dark" ? "dark" : "light";
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(leerInicial);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => (t === "light" ? "dark" : "light"));
  }, []);

  return [theme, toggle];
}
