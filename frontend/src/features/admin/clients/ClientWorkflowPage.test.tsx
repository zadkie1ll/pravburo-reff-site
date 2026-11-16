import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/renderWithProviders";
import { mockApi, sentBody } from "@/test/mockApi";
import { ClientWorkflowPage } from "./ClientWorkflowPage";
import type { ClientWorkflow } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it("marks main and bonus paid using the current version and explicit date, then removes payment actions", async () => {
  const workflow: ClientWorkflow = {
    version: 2,
    status_label: "Ожидает основной выплаты",
    outstanding: "13000",
    curator_name: null,
    curator_id: null,
    input: {
      version: 1,
      contract_date: "2026-10-10",
      first_payment: "8000",
      deposit_paid_on: "2026-11-12",
      paid_in_full: true,
      advance_amount: "3000",
      main_amount: "10000",
      curator_amount: "0",
      advance_due_on: null,
      main_due_on: null,
      advance_paid_on: "2026-10-16",
      main_paid_on: null,
      curator_paid_on: null,
    },
    stages: [
      {
        key: "advance",
        label: "Аванс агенту",
        amount: "3000",
        due_on: "2026-10-16",
        paid_on: "2026-10-16",
        status: "paid",
        reward_id: null,
        recipient: null,
        historical: true,
      },
      {
        key: "main",
        label: "Основная сумма агенту",
        amount: "10000",
        due_on: "2026-12-03",
        paid_on: null,
        status: "ready",
        reward_id: 1,
        recipient: null,
        historical: false,
      },
      {
        key: "bonus",
        label: "Бонус 100%",
        amount: "3000",
        due_on: "2026-12-03",
        paid_on: null,
        status: "ready",
        reward_id: 2,
        recipient: null,
        historical: false,
      },
    ],
  };
  let current = workflow;
  const api = mockApi({
    "/client-workflows/1": () => ({
      body: { id: 1, agent_id: 7, full_name: "Иван Клиентов", workflow: current },
    }),
    "/client-workflows/1/main/pay": () => {
      current = {
        ...workflow,
        version: 3,
        status_label: "Всё выплачено",
        outstanding: "0",
        stages: workflow.stages.map((stage) => ({
          ...stage,
          status: "paid",
          paid_on: "2026-11-13",
        })),
      };
      return { body: current };
    },
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderWithProviders(
    <Routes>
      <Route path="/admin/clients/:id/workflow" element={<ClientWorkflowPage />} />
    </Routes>,
    "/admin/clients/1/workflow",
  );
  const user = userEvent.setup();
  expect(await screen.findByText("Иван Клиентов")).toBeInTheDocument();
  expect(screen.getAllByText("03.12.2026")).toHaveLength(2);
  expect(screen.getAllByRole("button", { name: "Основная и бонус выплачены" })).toHaveLength(1);
  await user.clear(screen.getByLabelText("Фактическая дата выплаты"));
  await user.type(screen.getByLabelText("Фактическая дата выплаты"), "2026-11-13");
  await user.click(screen.getByRole("button", { name: "Основная и бонус выплачены" }));
  await waitFor(() =>
    expect(sentBody(api, "/client-workflows/1/main/pay")).toEqual({
      version: 2,
      paid_on: "2026-11-13",
    }),
  );
  expect(await screen.findByText("Всё выплачено")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Основная и бонус выплачены" }),
  ).not.toBeInTheDocument();
});
