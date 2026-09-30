import { useSearchParams } from "react-router-dom";

import { BackToCabinet } from "@/features/cabinet/BackToCabinet";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { usePayouts } from "./api";
import { PayoutFilterForm } from "./PayoutFilterForm";
import { PayoutsTable } from "./PayoutsTable";
import type { PayoutFilters } from "./types";

export function PayoutsPage() {
  usePageTitle("Выплаты");
  // Filters live in the URL: shareable, and the back button restores them.
  const [params, setParams] = useSearchParams();
  const applied: PayoutFilters = {
    month: params.get("month") ?? "",
    reward_type: params.get("reward_type") ?? "",
    status: params.get("status") ?? "",
  };
  const { data, isPending, isError } = usePayouts(applied);

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  function apply(filters: PayoutFilters) {
    setParams(Object.fromEntries(Object.entries(filters).filter(([, value]) => value)));
  }

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Кабинет агента</p>
        <h1>Выплаты</h1>
      </section>
      {/* key: remount with the applied values when the URL changes (e.g. browser back). */}
      <PayoutFilterForm
        key={params.toString()}
        applied={applied}
        rewardTypes={data.reward_types}
        statuses={data.statuses}
        onApply={apply}
      />
      <PayoutsTable rows={data.rows} />
      <BackToCabinet />
    </>
  );
}
