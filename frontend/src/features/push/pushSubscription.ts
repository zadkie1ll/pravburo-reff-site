import { apiGet, apiPost } from "@/shared/api/client";

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window;
}

export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const output = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

export async function subscribeToPush(): Promise<void> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("разрешение не дано");

  const registration = await navigator.serviceWorker.register("/sw.js");
  const { key } = await apiGet<{ key: string }>("/push/vapid-public-key");
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  const { endpoint, keys } = subscription.toJSON();
  await apiPost("/push/subscribe", { endpoint, keys });
}
