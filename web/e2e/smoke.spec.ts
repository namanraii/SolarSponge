import { expect, test } from "@playwright/test";

test("overview renders play controls against the offline fixture", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /midday dump/i })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /play/i })).toBeVisible();
  await page.getByRole("button", { name: /play/i }).click();
  await expect(page.getByRole("button", { name: /pause/i })).toBeVisible();
});
