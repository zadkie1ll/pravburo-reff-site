import { AppLink } from "./AppLink";

export function PageBack({ to, children }: { to: string; children: string }) {
  return (
    <nav className="page-back" aria-label="Возврат к разделу">
      <AppLink className="nav-link" to={to}>
        {children}
      </AppLink>
    </nav>
  );
}
