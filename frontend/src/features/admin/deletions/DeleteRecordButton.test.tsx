import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/renderWithProviders";
import { mockApi, sentBody } from "@/test/mockApi";
import { DeleteRecordButton } from "./DeleteRecordButton";

const proto = HTMLDialogElement.prototype;
const show = Object.getOwnPropertyDescriptor(proto, "showModal");
const close = Object.getOwnPropertyDescriptor(proto, "close");
beforeAll(() => {
  Object.defineProperty(proto, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = true;
    },
  });
  Object.defineProperty(proto, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.open = false;
    },
  });
});
afterAll(() => {
  if (show) Object.defineProperty(proto, "showModal", show);
  else Reflect.deleteProperty(proto, "showModal");
  if (close) Object.defineProperty(proto, "close", close);
  else Reflect.deleteProperty(proto, "close");
});
afterEach(() => vi.unstubAllGlobals());
const URL = "/admin/deletions/partners/7";
const PREVIEW = {
  name: "Анна Партнёрова",
  phone: "+79990000000",
  email: null,
  client_count: 2,
  reward_count: 3,
  invited_partner_count: 1,
  curator_client_count: 0,
  can_delete: true,
  blocked_reason: null,
  token: "a".repeat(64),
};

it("shows exactly what will be removed and sends the reviewed token only after confirmation", async () => {
  const api = mockApi({ [URL]: (body) => ({ body: body ? { ok: true } : PREVIEW }) });
  const done = vi.fn();
  renderWithProviders(
    <DeleteRecordButton kind="partners" id={7} name="Анна Партнёрова" onDeleted={done} />,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Удалить партнёра: Анна Партнёрова" }));
  const dialog = await screen.findByRole("dialog");
  expect(
    await within(dialog).findByText(/Приглашённые партнёры \(1\) останутся/),
  ).toBeInTheDocument();
  expect(dialog).toHaveTextContent("Будет удалён аккаунт партнёра и все его клиенты");
  expect(dialog).toHaveTextContent("Сделки и контакты в Битриксе сохранятся");
  expect(sentBody(api, URL)).toBeUndefined();
  await user.click(within(dialog).getByRole("button", { name: "Удалить партнёра и его клиентов" }));
  await waitFor(() => expect(done).toHaveBeenCalledOnce());
  expect(sentBody(api, URL)).toEqual({ token: PREVIEW.token });
  expect(api.mock.calls.find(([, init]) => init?.body)?.[1]?.method).toBe("DELETE");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("cancel closes the confirmation without deleting anything", async () => {
  const api = mockApi({ [URL]: { body: PREVIEW } });
  renderWithProviders(<DeleteRecordButton kind="partners" id={7} name="Анна" />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Удалить партнёра: Анна" }));
  await screen.findByText("Анна Партнёрова");
  await user.click(screen.getByRole("button", { name: "Отмена" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(api.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
});

it("prevents confirming deletion when the ledger contains a paid reward", async () => {
  const api = mockApi({
    [URL]: { body: { ...PREVIEW, can_delete: false, blocked_reason: "Есть отмеченные выплаты" } },
  });
  renderWithProviders(<DeleteRecordButton kind="partners" id={7} name="Анна" />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Удалить партнёра: Анна" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Есть отмеченные выплаты");
  expect(screen.getByRole("button", { name: "Удалить партнёра и его клиентов" })).toBeDisabled();
  expect(api.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
});
