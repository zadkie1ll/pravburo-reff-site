import { useSearchParams } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Pagination } from "@/shared/ui/Pagination";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { filtersToSearch, readListFilters, type ListFilters } from "../list/listFilters";
import { SearchFilterForm } from "../list/SearchFilterForm";
import { useApplications, useSetManager, useSetProcessingStatus } from "./api";
import { ApplicationsTable } from "./ApplicationsTable";

export function AdminApplicationsPage() {
  usePageTitle("Заявки");
  // Filters and page live in the URL: shareable, and Back restores them.
  const [params, setParams] = useSearchParams();
  const applied = readListFilters(params);
  const { data, isPending, isError } = useApplications(applied);
  const setStatus = useSetProcessingStatus();
  const setManager = useSetManager();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  const saving = setStatus.isPending || setManager.isPending;
  const failure = setStatus.error ?? setManager.error;

  function apply(filters: ListFilters) {
    setParams(new URLSearchParams(filtersToSearch(filters)));
  }

  return (
    <>
      {/* key: remount with the applied values when the URL changes (e.g. browser back). */}
      <SearchFilterForm
        key={`${applied.q}|${applied.status}`}
        title="Заявки"
        searchLabel="Найти по имени или телефону"
        statusLabel="Статус доставки в Битрикс"
        statusOptions={data.delivery_statuses}
        applied={applied}
        totalCount={data.total_count}
        onApply={apply}
      />
      {failure && (
        <p className="alert" role="alert">
          {errorMessage(failure, "Не удалось сохранить изменение.")}
        </p>
      )}
      <ApplicationsTable
        rows={data.rows}
        processingStatuses={data.processing_statuses}
        managers={data.managers}
        disabled={saving}
        onStatus={(id, value) => setStatus.mutate({ id, value })}
        onManager={(id, value) => setManager.mutate({ id, value })}
      />
      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        searchFor={(page) => filtersToSearch({ ...applied, page })}
      />
      <p className="mt-20">
        <AppLink to="/admin">← Админ-панель</AppLink>
      </p>
    </>
  );
}
