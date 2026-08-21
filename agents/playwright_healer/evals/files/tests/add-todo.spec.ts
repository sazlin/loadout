// spec: specs/basic-operations.md
// seed: tests/seed.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Adding New Todos", () => {
  test("Add Valid Todo", async ({ page }) => {
    await page.locator("#new-todo").fill("Buy groceries");
    await page.locator("#new-todo").press("Enter");
    await expect(page.getByText("Buy groceries")).toBeVisible();
  });
});
