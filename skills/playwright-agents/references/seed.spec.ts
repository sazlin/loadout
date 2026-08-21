import { test, expect } from "@playwright/test";

test.describe("Test group", () => {
  test("seed", async ({ page }) => {
    // Seed runs project fixtures, hooks, and global setup.
    // Planner and generator treat this file as the style example.
    await page.goto("/");
    await expect(page).toHaveTitle(/.+/);
  });
});
