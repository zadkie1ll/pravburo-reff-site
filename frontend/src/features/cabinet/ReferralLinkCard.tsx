import { useId } from "react";

export function ReferralLinkCard({ url }: { url: string }) {
  const inputId = useId();

  return (
    <section className="card">
      <h2>Ваша реферальная ссылка</h2>
      <div className="copy-row">
        <input id={inputId} value={url} readOnly aria-label="Реферальная ссылка" />
        <button
          className="button"
          type="button"
          onClick={() => void navigator.clipboard.writeText(url)}
        >
          Копировать
        </button>
      </div>
      <img className="qr" src="/cabinet/referral-qr.png" alt="QR-код реферальной ссылки" />
    </section>
  );
}
