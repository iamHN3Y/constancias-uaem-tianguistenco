import { Link } from "react-router-dom";
import { useThemeContext } from "../context/ThemeContext";
import { useTour } from "../context/TourContext";
import { IconBack, IconHelp, IconMoon, IconSun } from "./Icons";

interface HeaderProps {
  title: string;
  subtitle?: string;
  backTo?: string;
  backLabel?: string;
  children?: React.ReactNode;
}

export function ThemeToggle() {
  const { theme, toggle } = useThemeContext();
  return (
    <button
      id="themeToggle"
      className="icon-btn"
      type="button"
      onClick={toggle}
      title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
      aria-label={theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
    >
      {theme === "dark" ? <IconSun /> : <IconMoon />}
    </button>
  );
}

export function Header({ title, subtitle, backTo, backLabel = "Volver", children }: HeaderProps) {
  const { start } = useTour();
  return (
    <header className="header">
      <div className="brand">
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="appbar-actions">
        {backTo && (
          <Link className="btn-ghost" to={backTo}>
            <IconBack />
            {backLabel}
          </Link>
        )}
        {children}
        <button
          className="icon-btn"
          type="button"
          onClick={start}
          title="Ver tutorial"
          aria-label="Ver tutorial"
        >
          <IconHelp />
        </button>
        <ThemeToggle />
      </div>
    </header>
  );
}
