import { useSearchParams } from "react-router-dom";
import { useInfoFromNavigation } from "@/features/auth/useInfoFromNavigation";
import { AdminIcon } from "../AdminIcon";

import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Pagination } from "@/shared/ui/Pagination";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { filtersToSearch, readListFilters, type ListFilters } from "../list/listFilters";
import { SearchFilterForm } from "../list/SearchFilterForm";
import { useBlockPartner, usePartners, useSaveNote, useUnblockPartner } from "./api";
import { PartnerCards } from "./PartnerCards";

export function AdminPartnersPage() {
  usePageTitle("Партнёры");
  const info = useInfoFromNavigation();
  const [params, setParams] = useSearchParams();
  const applied = readListFilters(params);
  const { data, isPending, isError } = usePartners(applied);
  const saveNote = useSaveNote();
  const block = useBlockPartner();
  const unblock = useUnblockPartner();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  const saving = saveNote.isPending || block.isPending || unblock.isPending;
  const failure = saveNote.error ?? block.error ?? unblock.error;

  function apply(filters: ListFilters) {
    setParams(new URLSearchParams(filtersToSearch(filters)));
  }

  return (
    <>
      <div className="admin-partner-toolbar">
        <AppLink className="admin-back" to="/admin?section=partners">
          <AdminIcon name="back" /> Партнёры
        </AppLink>
        <AppLink className="button" to="/admin/partners/new">
          <AdminIcon name="add" /> Создать партнёра
        </AppLink>
      </div>
      {info && (
        <p className="notice-success" role="status">
          {info}
        </p>
      )}
      <div className="admin-partners-filters">
        <SearchFilterForm
          key={`${applied.q}|${applied.status}`}
          title="Партнёры"
          searchLabel="Найти по имени, почте или телефону"
          statusLabel="Статус"
          statusOptions={data.statuses}
          applied={applied}
          totalCount={data.total_count}
          onApply={apply}
        />
      </div>
      {failure && (
        <p className="alert" role="alert">
          {errorMessage(failure, "Не удалось сохранить изменение.")}
        </p>
      )}
      <PartnerCards
        rows={data.rows}
        disabled={saving}
        onNote={(id, note) => saveNote.mutate({ id, note })}
        onBlock={(id, reason) => block.mutate({ id, reason })}
        onUnblock={(id) => unblock.mutate(id)}
      />
      <Pagination
        page={data.page}
        totalPages={data.total_pages}
        searchFor={(page) => filtersToSearch({ ...applied, page })}
      />
    </>
  );
}
