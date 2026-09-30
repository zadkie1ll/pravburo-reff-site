import { AppLink } from "@/shared/ui/AppLink";

export function BackToCabinet() {
  return (
    <p className="back-link">
      <AppLink to="/cabinet">← Вернуться в кабинет</AppLink>
    </p>
  );
}
