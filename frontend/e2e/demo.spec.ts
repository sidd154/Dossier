import { expect, test } from "@playwright/test";

test("demo console signs in and opens a department", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText(/Demo mode/)).toBeVisible();

  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/departments$/);
  await expect(
    page.getByRole("heading", { name: "Departments" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Open Sales" }).click();
  await expect(page).toHaveURL(/\/departments\/[^/]+$/);
  await expect(page.getByRole("heading", { name: "Sales" })).toBeVisible();

  await page.getByRole("link", { name: "Sources" }).click();
  await expect(page).toHaveURL(/\/sources$/);
  await expect(page.getByText("Sales Pipeline")).toBeVisible();
  await expect(page.getByText("Finance Ledger")).toBeVisible();

  await page.getByRole("link", { name: "Emails" }).click();
  await expect(page).toHaveURL(/\/emails$/);
  await expect(page.getByText("Sales pipeline brief")).toBeVisible();
  await expect(page.getByText("Next send")).toBeVisible();
});

test("demo mail execution history is visible", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/departments$/);

  await page.getByRole("link", { name: "Mail" }).click();
  await expect(page).toHaveURL(/\/mail/);
  await page.getByRole("link", { name: "Executions" }).click();
  await expect(page.getByText("Sales pipeline brief").first()).toBeVisible();

  await page.getByText("Sales pipeline brief").first().click();
  await expect(page.getByText("Recipients", { exact: true })).toBeVisible();
  await expect(page.getByText("sam@northwind.test")).toBeVisible();
});
