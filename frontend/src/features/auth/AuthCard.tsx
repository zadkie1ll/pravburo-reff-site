import type { ReactNode } from "react";

interface AuthCardProps {
  title: string;
  eyebrow?: string;
  /** Neutral notice shown under the title (e.g. "code sent"). */
  info?: string;
  error?: string;
  children: ReactNode;
}

export function AuthCard({ title, eyebrow, info, error, children }: AuthCardProps) {
  return (
    <section className="auth-card card">
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
