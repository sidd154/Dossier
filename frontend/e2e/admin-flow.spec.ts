import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "Dossier-Admin-2026";

const suffix = Date.now().toString(36);
const DEPARTMENT_NAME = `E2E Department ${suffix}`;
const MEMBER_NAME = `E2E Member ${suffix}`;
const MEMBER_EMAIL = `e2e-${suffix}@example.com`;
const MEMBER_PASSWORD = "E2E-Member-Password-2026";

let temporaryPassword = "";

test.describe.configure({ mode: "serial" });

async function signIn(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function signOut(page: import("@playwright/test").Page) {
  await page
    .getByRole("button", { name: new RegExp(ADMIN_EMAIL) })
    .first()
    .click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
}

async function openUsers(page: import("@playwright/test").Page) {
  await page.goto("/settings/users");
  await expect(page).toHaveURL(/\/settings\/users/);
}

test("administrator onboards a department and a member", async ({ page }) => {
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/departments$/);
  await expect(
    page.getByRole("heading", { name: "Departments" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "New department" }).first().click();
  await page.getByLabel("Name").fill(DEPARTMENT_NAME);
  await page.getByRole("button", { name: "Create department" }).click();
  await expect(page.getByText(DEPARTMENT_NAME)).toBeVisible();

  await openUsers(page);
  await page.getByRole("button", { name: "Add user" }).first().click();

  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Email").fill(MEMBER_EMAIL);
  await dialog.getByLabel("Full name").fill(MEMBER_NAME);
  await dialog.getByRole("combobox").first().click();
  await page.getByRole("option", { name: DEPARTMENT_NAME }).click();
  await page.getByRole("button", { name: "Create user" }).click();

  await expect(dialog.getByText("Temporary password")).toBeVisible();
  temporaryPassword =
    (await dialog.locator("code").textContent())?.trim() ?? "";
  expect(temporaryPassword.length).toBeGreaterThanOrEqual(12);
  await dialog.getByRole("button", { name: "Done" }).click();

  await expect(page.getByText(MEMBER_EMAIL)).toBeVisible();
  await signOut(page);
});

test("member is forced to change password and cannot reach admin routes", async ({
  page,
}) => {
  expect(temporaryPassword).not.toBe("");

  await signIn(page, MEMBER_EMAIL, temporaryPassword);
  await expect(page).toHaveURL(/\/change-password/);

  await page.getByLabel("Temporary password").fill(temporaryPassword);
  await page.getByLabel("New password", { exact: true }).fill(MEMBER_PASSWORD);
  await page.getByLabel("Confirm new password").fill(MEMBER_PASSWORD);
  await page.getByRole("button", { name: "Update password" }).click();

  await expect(page).toHaveURL(/\/403$/);
  await expect(
    page.getByRole("heading", { name: "You do not have access to this page" }),
  ).toBeVisible();

  await page.goto("/settings/users");
  await expect(
    page.getByText("Access is limited to administrators"),
  ).toBeVisible();
});

test("a disabled member can no longer sign in", async ({ page }) => {
  await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/departments$/);

  await openUsers(page);
  await page
    .getByRole("button", { name: `Actions for ${MEMBER_NAME}` })
    .click();
  await page.getByRole("menuitem", { name: "Disable account" }).click();
  await page.getByRole("button", { name: "Disable account" }).click();
  await expect(page.getByText("User disabled")).toBeVisible();

  await signOut(page);

  await signIn(page, MEMBER_EMAIL, MEMBER_PASSWORD);
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText("Invalid email or password")).toBeVisible();
});
