import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useRates } from "./api";
import { RatesForm } from "./RatesForm";

export function AdminNetworkRatesPage() {
  usePageTitle("Суммы override по сети");
  const { data, isPending, isError } = useRates();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <section className="card">
      <p className="eyebrow">Администратор</p>
      <h1>Суммы override по сети</h1>
      <p>
        Партнёр получает эту фиксированную сумму с каждой награды тех, кого он привёл (и кого
        привели они, на 3 уровня вниз) — независимо от размера самой награды. У клиентов, ставших
        партнёрами, только 2 уровня — тип определяется автоматически, тут не настраивается.
      </p>
      <RatesForm rates={data.rates} />
      <p className="mt-20">
        <AppLink to="/admin">← Админ-панель</AppLink>
      </p>
    </section>
  );
}
