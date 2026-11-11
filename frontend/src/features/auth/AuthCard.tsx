import type { ReactNode } from "react";
import { PageBack } from "@/shared/ui/PageBack";

interface AuthCardProps {
  title: string;
  eyebrow?: string;
  /** Neutral notice shown under the title (e.g. "code sent"). */
  info?: string;
  error?: string;
  children: ReactNode;
  backTo?: string;
}

export function AuthCard({
  title,
  eyebrow,
  info,
  error,
  children,
  backTo = "/login",
}: AuthCardProps) {
  return (
    <section className="auth-card card">
      <PageBack to={backTo}>← Назад</PageBack>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {info && <p>{info}</p>}
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {children}
    </section>
  );
}
