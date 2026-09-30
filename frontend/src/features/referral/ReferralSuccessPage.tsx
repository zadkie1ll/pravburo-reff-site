import { usePageTitle } from "@/shared/hooks/usePageTitle";

export function ReferralSuccessPage() {
  usePageTitle("Заявка принята");
  return (
    <section className="not-found card">
      <span>Готово</span>
      <h1>Заявка принята</h1>
      <p>Специалист Правбюро свяжется с вами.</p>
    </section>
  );
}
