import { describe, expect, it } from "vitest";
import { isSpaPath, SPA_PATHS } from "@/app/spaRoutes";

describe("existing client routes", () => {
  it("keeps filtered lists and partner-specific imports in the SPA", () => {
    expect(SPA_PATHS).toContain("/admin/clients");
    expect(SPA_PATHS).toContain("/admin/clients/new");
    expect(isSpaPath("/admin/clients?q=432&page=2&agent_id=7")).toBe(true);
    expect(isSpaPath("/admin/clients/new?agent_id=7")).toBe(true);
    expect(isSpaPath("/api/v1/site/admin/clients")).toBe(false);
  });
});
