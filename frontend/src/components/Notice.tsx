import { IconCheck, IconWarning } from "./Icons";

export function Notice({ children, error = false }: { children: React.ReactNode; error?: boolean }) {
  return (
    <div className={"note" + (error ? " note-error" : "")}>
      {error ? <IconWarning /> : <IconCheck />}
      <span>{children}</span>
    </div>
  );
}
