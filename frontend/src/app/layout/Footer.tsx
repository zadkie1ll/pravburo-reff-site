import { useSession } from "@/features/session/useSession";
import { AppLink } from "@/shared/ui/AppLink";
import { ExternalLink } from "@/shared/ui/ExternalLink";

import { Brand } from "./Brand";
import { footerNav, homeHref } from "./navigation";

export function Footer() {
  const { data: session } = useSession();
  const role = session?.role ?? null;
  const authenticated = session?.authenticated ?? false;

  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <Brand
          href={homeHref(role, authenticated)}
          title="Правбюро"
          subtitle="Агентская программа"
          className="footer-brand"
        />
        <nav className="footer-nav" aria-label="Навигация в подвале">
          {footerNav(role, authenticated, session?.onboarding_required).map((item) => (
            <AppLink key={item.to} to={item.to}>
              {item.label}
            </AppLink>
          ))}
          <AppLink to="/faq">FAQ</AppLink>
          <ExternalLink href="https://t.me/pravburo">Telegram</ExternalLink>
          <ExternalLink href="https://vk.com/pb.pravburo">VK</ExternalLink>
        </nav>
        <div className="footer-meta">
          ИП Свириденко С. В. · ИНН 616706684677 · ОГРНИП 325619600215683 · Правбюро
        </div>
      </div>
    </footer>
  );
}
