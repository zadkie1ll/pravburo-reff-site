import { useState } from "react";

import { pushSupported, subscribeToPush } from "./pushSubscription";

export function PushSubscribeButton() {
  const [state, setState] = useState<"idle" | "pending" | "done">("idle");

  if (!pushSupported()) return null;

  function subscribe() {
    setState("pending");
    subscribeToPush()
      .then(() => setState("done"))
      .catch((error: unknown) => {
        setState("idle");
        const reason = error instanceof Error ? error.message : "неизвестная ошибка";
        window.alert(`Не получилось включить уведомления: ${reason}`);
      });
  }

  return (
    <button
      className="button secondary"
      type="button"
      disabled={state !== "idle"}
      onClick={subscribe}
    >
      {state === "done" ? "Уведомления включены" : "Включить уведомления в браузере"}
    </button>
  );
}
