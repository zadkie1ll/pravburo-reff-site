import { LogoutButton } from "@/features/auth/LogoutButton";
import { PushSubscribeButton } from "@/features/push/PushSubscribeButton";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useCabinet } from "./api";
import { ClientsTable } from "./ClientsTable";
import { FinanceCard } from "./FinanceCard";
import { LevelCard } from "./LevelCard";
import { LinkStatsCard } from "./LinkStatsCard";
import { ReferralLinkCard } from "./ReferralLinkCard";

export function CabinetPage() {
  usePageTitle("Кабинет агента");
  const { data: cabinet, isPending, isError } = useCabinet();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <>
      <section className="hero hero-wide">
        <p className="eyebrow">Личный кабинет</p>
        <div className="hero-header-row">
          <h1>{cabinet.name}</h1>
          <PushSubscribeButton />
        </div>
        <p>Ваша реферальная ссылка, статус клиентов и информация о вознаграждениях — всё здесь.</p>
      </section>

      <div className="dashboard-grid">
        <FinanceCard finance={cabinet.finance} />
        <ReferralLinkCard url={cabinet.referral_url} />
        <LinkStatsCard stats={cabinet.link_stats} />
      </div>

      <LevelCard level={cabinet.level} />
      <ClientsTable clients={cabinet.clients} />

      <div className="footer-actions">
        <span>
          <AppLink to="/payouts">Подробнее о выплатах</AppLink> ·{" "}
          <AppLink to="/profile">Профиль</AppLink> ·{" "}
          <AppLink to="/faq">Как это работает / FAQ</AppLink>
        </span>
        <LogoutButton />
      </div>
    </>
  );
}
